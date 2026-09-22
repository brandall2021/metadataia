"""Tests de brechas de la fase 13 y endpoints nuevos de documentos.

Cubre el cierre de brechas de F13/F16/F17:
- alias de enqueue: analyze / extract-text / extract-metadata (202 + cola).
- gate de deposito: 409 NOT_DEPOSITABLE si la ultima validacion tiene errores.
- /deposit/retry: 409 si no hay una deposicion FAILED; reintento completo OK.
- POST /admin/repositories/{id}/test (exito y error) sin filtrar credenciales.
- delete_collection ya no tira NameError.
- PUT /documents/{id}: actualiza datos editoriales y bloquea estados locked.
- PUT /documents/{id}/metadata: edicion por lotes + bloqueo de aprobado/locked.
- historial y detalle de documento incluyen las corridas de extraccion.
"""

import json
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core import storage
from app.core.database import SessionLocal
from app.extraction import engine
from app.jobs.tasks import deposit_document, extract_metadata, validate_metadata
from app.main import create_app
from app.models import Document
from test_dspace import FixedConnector, _link_collection_to_type, _setup_repo
from test_normalization import NormStack


# ---------------------------------------------------------------------------
# Fixtures (mismas convenciones que el resto de la suite)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_app())


@pytest.fixture(scope="module")
def admin_headers(client) -> dict:
    r = client.post("/api/auth/login", json={"username": "admin", "password": "metadataia123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def catalogador_headers(client) -> dict:
    r = client.post("/api/auth/login", json={"username": "catalogador", "password": "metadataia123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def stack(client, admin_headers):
    st = NormStack(client, admin_headers)
    yield st
    st.cleanup()


@pytest.fixture(autouse=True)
def _local_storage(tmp_path_factory, monkeypatch):
    path = tmp_path_factory.mktemp("storage-gaps")
    monkeypatch.setattr(storage.settings, "storage_backend", "filesystem")
    monkeypatch.setattr(storage.settings, "local_storage_path", str(path))
    storage.ensure_bucket()
    yield path


@pytest.fixture(autouse=True)
def send_calls(monkeypatch):
    """Desactiva el broker real y registra cada send_task como (nombre, args)."""
    calls = []

    def fake(name, args=None, **kw):
        calls.append((name, list(args or [])))

    for mod in (
        "app.pdf.router",
        "app.extraction.router",
        "app.jobs.tasks",
        "app.normalization.router",
        "app.validation.router",
        "app.deposit.router",
    ):
        monkeypatch.setattr(f"{mod}.celery_app.send_task", fake)
    return calls


@pytest.fixture
def _no_auto_chain(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "auto_normalize", False)
    monkeypatch.setattr(settings, "auto_validate", False)


def _fake_with(fields: dict):
    return lambda *a, **k: {
        "content": json.dumps({"fields": {name: {"value": v, "confidence": 0.9} for name, v in fields.items()}}),
        "input_tokens": 1,
        "output_tokens": 1,
        "time_ms": 1.0,
    }


@pytest.fixture
def _fake_call_model(monkeypatch):
    fields = {
        "creator": "juan  perez",
        "date": "10/05/2023",
        "language": "Spanish",
        "title": "Impacto de la IA en bibliotecas",
        "subject": ["IA", "Metadatos"],
        "description": "Resumen de la tesis",
        "type": "Tesis de maestria",
        "rights": "openAccess",
    }
    monkeypatch.setattr(engine, "call_model", _fake_with(fields))
    return None


def _upload_extract(stack, headers, client) -> dict:
    doc = stack.upload(headers)
    assert extract_metadata(doc["id"])["status"] == "COMPLETED"
    return doc


def _upload_extract_approve(stack, headers, client) -> dict:
    doc = _upload_extract(stack, headers, client)
    r = client.post(f"/api/documents/{doc['id']}/approve", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "APPROVED"
    return doc


def _cleanup_doc(doc_id: str, headers, client):
    client.delete(f"/api/documents/{doc_id}", headers=headers)


@pytest.fixture(autouse=True)
def _purge_repos_after(client, admin_headers):
    yield
    repos = client.get("/api/admin/repositories", headers=admin_headers).json()
    for r in repos:
        client.delete(f"/api/admin/repositories/{r['id']}", headers=admin_headers)


def _set_status(doc_id: str, status: str) -> None:
    db = SessionLocal()
    try:
        doc = db.get(Document, uuid.UUID(doc_id))
        assert doc is not None
        doc.status = status
        db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Enqueue: analyze / extract-text / extract-metadata
# ---------------------------------------------------------------------------


def test_analyze_extract_text_extract_metadata_202(
    client, stack, catalogador_headers, send_calls, _fake_call_model
):
    doc = stack.upload(catalogador_headers)
    send_calls.clear()

    r = client.post(f"/api/documents/{doc['id']}/analyze", headers=catalogador_headers)
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["status"] == "QUEUED"
    assert body["document_id"] == doc["id"] and body["job_id"]

    r = client.post(f"/api/documents/{doc['id']}/extract-text", headers=catalogador_headers)
    assert r.status_code == 202, r.text
    assert r.json()["status"] == "QUEUED"

    r = client.post(f"/api/documents/{doc['id']}/extract-metadata", headers=catalogador_headers)
    assert r.status_code == 202, r.text
    assert r.json()["status"] == "QUEUED"

    names = [name for name, _ in send_calls]
    assert "app.jobs.tasks.analyze_document" in names
    assert "app.jobs.tasks.extract_text" in names
    assert "app.jobs.tasks.extract_metadata" in names
    _cleanup_doc(doc["id"], catalogador_headers, client)


def test_analyze_extract_text_requieren_permiso_upload(client, stack, admin_headers):
    doc = stack.upload(admin_headers)
    r = client.post(f"/api/documents/{doc['id']}/analyze", headers=admin_headers)
    assert r.status_code in (200, 202), r.text
    _cleanup_doc(doc["id"], admin_headers, client)


# ---------------------------------------------------------------------------
# Gate de deposito: validacion bloqueante
# ---------------------------------------------------------------------------


def test_deposit_409_con_validacion_bloqueante(
    client, stack, catalogador_headers, admin_headers, monkeypatch, send_calls, _no_auto_chain
):
    monkeypatch.setattr("app.repositories.router.build_connector", lambda repo: _StubSync())
    repo_id = _setup_repo(client, admin_headers, stack, monkeypatch)
    _link_collection_to_type(client, admin_headers, stack, repo_id)

    monkeypatch.setattr(engine, "call_model", _fake_with({"creator": "Juan", "date": "2023-05-10"}))
    doc = stack.upload(catalogador_headers)
    assert extract_metadata(doc["id"])["status"] == "COMPLETED"
    res = validate_metadata(doc["id"])
    assert res["status"] == "COMPLETED" and res["valid"] is False

    _set_status(doc["id"], "APPROVED")
    r = client.post(f"/api/documents/{doc['id']}/deposit", headers=catalogador_headers)
    assert r.status_code == 409, r.text
    assert r.json()["code"] == "NOT_DEPOSITABLE"
    _cleanup_doc(doc["id"], catalogador_headers, client)
    client.delete(f"/api/admin/repositories/{repo_id}", headers=admin_headers)


# ---------------------------------------------------------------------------
# Retry de deposito
# ---------------------------------------------------------------------------


def test_retry_deposit_sin_fallo_409(
    client, stack, catalogador_headers, admin_headers, monkeypatch, _fake_call_model, _no_auto_chain
):
    fc = FixedConnector()
    monkeypatch.setattr("app.jobs.tasks.build_connector", lambda repo: fc)
    repo_id = _setup_repo(client, admin_headers, stack, monkeypatch)
    _link_collection_to_type(client, admin_headers, stack, repo_id)

    doc = _upload_extract_approve(stack, catalogador_headers, client)
    r = client.post(f"/api/documents/{doc['id']}/deposit", headers=catalogador_headers)
    assert r.status_code == 202, r.text

    r = client.post(f"/api/documents/{doc['id']}/deposit/retry", headers=catalogador_headers)
    assert r.status_code == 409, r.text
    assert "fallido" in r.json()["detail"]
    _cleanup_doc(doc["id"], catalogador_headers, client)
    client.delete(f"/api/admin/repositories/{repo_id}", headers=admin_headers)


def test_retry_deposit_flujo_completo(
    client, stack, catalogador_headers, admin_headers, monkeypatch, _fake_call_model, _no_auto_chain
):
    fc = FixedConnector(fail_on="create_workspace_item")
    monkeypatch.setattr("app.jobs.tasks.build_connector", lambda repo: fc)
    repo_id = _setup_repo(client, admin_headers, stack, monkeypatch)
    _link_collection_to_type(client, admin_headers, stack, repo_id)

    doc = _upload_extract_approve(stack, catalogador_headers, client)
    res = deposit_document(doc["id"])
    assert res["status"] == "ERROR", res

    r = client.post(f"/api/documents/{doc['id']}/deposit/retry", headers=catalogador_headers)
    assert r.status_code == 202, r.text
    assert r.json()["status"] == "PENDING"

    fc.fail_on = None
    assert deposit_document(doc["id"])["status"] == "COMPLETED"

    latest = client.get(f"/api/documents/{doc['id']}/deposition", headers=catalogador_headers)
    assert latest.status_code == 200, latest.text
    assert latest.json()["status"] == "COMPLETED"
    assert latest.json()["external_item_id"] == "33333333-0000-4000-8000-000000000003"
    _cleanup_doc(doc["id"], catalogador_headers, client)
    client.delete(f"/api/admin/repositories/{repo_id}", headers=admin_headers)


# ---------------------------------------------------------------------------
# Test endpoint de repositorio
# ---------------------------------------------------------------------------


class _StubSync:
    def authenticate(self):
        return "token"

    def get_communities(self, token=None):
        return [{"uuid": "x", "name": "C1", "handle": "h/0"}]

    def get_collections(self, community_uuid=None, token=None):
        return [{"uuid": "y", "name": "Col1", "handle": "h/10"}]


def test_repository_test_endpoint_ok(
    client, admin_headers, stack, monkeypatch, _no_auto_chain
):
    repo_id = _setup_repo(client, admin_headers, stack, monkeypatch)
    r = client.post(f"/api/admin/repositories/{repo_id}/test", headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert "supersecreto" not in json.dumps(body)
    assert "time_ms" in body
    client.delete(f"/api/admin/repositories/{repo_id}", headers=admin_headers)


def test_repository_test_endpoint_error(client, admin_headers, monkeypatch):
    def boom(repo):
        raise RuntimeError("boom dspace")

    monkeypatch.setattr("app.repositories.router.build_connector", boom)
    r = client.post(
        "/api/admin/repositories",
        headers=admin_headers,
        json={
            "name": "Repo Roto",
            "code": f"repo-{uuid.uuid4().hex[:8]}",
            "api_url": "http://dspace:8080/server/api",
            "username": "user@x.org",
            "credential": "secreto-no-filtrable",
            "authentication_type": "dspace",
            "active": True,
        },
    )
    assert r.status_code == 201, r.text
    repo_id = r.json()["id"]

    t = client.post(f"/api/admin/repositories/{repo_id}/test", headers=admin_headers)
    assert t.status_code == 200, t.text
    body = t.json()
    assert body["ok"] is False
    assert "boom dspace" in body["message"]
    assert "secreto-no-filtrable" not in json.dumps(body)
    client.delete(f"/api/admin/repositories/{repo_id}", headers=admin_headers)


def test_repository_test_permiso(client, admin_headers, catalogador_headers, stack, monkeypatch):
    repo_id = _setup_repo(client, admin_headers, stack, monkeypatch)
    r = client.post(f"/api/admin/repositories/{repo_id}/test", headers=catalogador_headers)
    assert r.status_code == 403, r.text
    client.delete(f"/api/admin/repositories/{repo_id}", headers=admin_headers)


# ---------------------------------------------------------------------------
# delete_collection no debe tirar NameError
# ---------------------------------------------------------------------------


def test_delete_collection_204(client, admin_headers, stack, monkeypatch, _no_auto_chain):
    repo_id = _setup_repo(client, admin_headers, stack, monkeypatch)
    cols = client.get(f"/api/admin/repositories/{repo_id}/collections", headers=admin_headers).json()
    assert len(cols) == 2
    r = client.delete(
        f"/api/admin/repositories/{repo_id}/collections/{cols[0]['id']}", headers=admin_headers
    )
    assert r.status_code == 204, r.text
    remaining = client.get(f"/api/admin/repositories/{repo_id}/collections", headers=admin_headers).json()
    assert len(remaining) == 1
    client.delete(f"/api/admin/repositories/{repo_id}", headers=admin_headers)


# ---------------------------------------------------------------------------
# PUT /documents/{id}
# ---------------------------------------------------------------------------


def test_put_document_actualiza_y_bloquea_estado(client, stack, catalogador_headers):
    doc = stack.upload(catalogador_headers)
    r = client.put(
        f"/api/documents/{doc['id']}", headers=catalogador_headers, json={"original_filename": "renombrado.pdf"}
    )
    assert r.status_code == 200, r.text
    assert r.json()["original_filename"] == "renombrado.pdf"

    _set_status(doc["id"], "DEPOSITING")
    r = client.put(
        f"/api/documents/{doc['id']}", headers=catalogador_headers, json={"original_filename": "no.pdf"}
    )
    assert r.status_code == 409, r.text
    assert r.json()["code"] == "LOCKED_STATE"
    _cleanup_doc(doc["id"], catalogador_headers, client)


# ---------------------------------------------------------------------------
# PUT /documents/{id}/metadata (edicion por lotes)
# ---------------------------------------------------------------------------


def test_put_metadata_bulk_edita_y_marca_revision(
    client, stack, admin_headers, catalogador_headers, _fake_call_model, _no_auto_chain
):
    doc = _upload_extract(stack, catalogador_headers, client)
    recs = client.get(f"/api/documents/{doc['id']}/metadata", headers=catalogador_headers).json()["records"]
    creator = next(r for r in recs if r["field"] == "creator")
    date = next(r for r in recs if r["field"] == "date")
    old_date = date["value"]

    r = client.put(
        f"/api/documents/{doc['id']}/metadata",
        headers=catalogador_headers,
        json={
            "records": [
                {"record_id": creator["id"], "value": "Garcia, Ana"},
                {"record_id": date["id"], "value": old_date, "confidence": 1.0},
            ]
        },
    )
    assert r.status_code == 200, r.text
    out = {o["field"]: o for o in r.json()}
    assert out["creator"]["value"] == "Garcia, Ana"
    assert out["creator"]["manually_modified"] is True
    assert out["date"]["confidence"] == 1.0

    detail = client.get(f"/api/documents/{doc['id']}", headers=catalogador_headers).json()
    assert detail["status"] == "NEEDS_REVIEW"

    audit = client.get(
        f"/api/admin/audit?action=document.metadata.bulkupdate&entity_id={doc['id']}",
        headers=admin_headers,
    ).json()
    assert audit["items"]
    _cleanup_doc(doc["id"], catalogador_headers, client)


def test_put_metadata_bloqueado_aprobado(
    client, stack, catalogador_headers, _fake_call_model, _no_auto_chain
):
    doc = _upload_extract(stack, catalogador_headers, client)
    assert client.post(f"/api/documents/{doc['id']}/approve", headers=catalogador_headers).status_code == 200
    recs = client.get(f"/api/documents/{doc['id']}/metadata", headers=catalogador_headers).json()["records"]
    creator = next(r for r in recs if r["field"] == "creator")

    r = client.put(
        f"/api/documents/{doc['id']}/metadata",
        headers=catalogador_headers,
        json={"records": [{"record_id": creator["id"], "value": "No deberia"}]},
    )
    assert r.status_code == 409, r.text
    assert r.json()["code"] == "LOCKED_STATE"
    _cleanup_doc(doc["id"], catalogador_headers, client)


# ---------------------------------------------------------------------------
# Detalle e historial con corridas de extraccion
# ---------------------------------------------------------------------------


def test_detalle_e_historial_incluyen_extracciones(
    client, stack, catalogador_headers, _fake_call_model, _no_auto_chain
):
    doc = _upload_extract(stack, catalogador_headers, client)
    detail = client.get(f"/api/documents/{doc['id']}", headers=catalogador_headers).json()
    assert "extraction_runs" in detail
    assert isinstance(detail["extraction_runs"], list)
    assert len(detail["extraction_runs"]) >= 1

    timeline = client.get(f"/api/documents/{doc['id']}/history", headers=catalogador_headers).json()
    assert any(item["type"] == "extraction" for item in timeline)
    run = next(item for item in timeline if item["type"] == "extraction")
    assert run["status"] == "COMPLETED"
    _cleanup_doc(doc["id"], catalogador_headers, client)