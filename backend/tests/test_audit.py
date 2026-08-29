"""Tests de auditoria (FASE 14).

Toda operacion relevante queda registrada en `audit_logs` (usuario, accion,
entidad, valores anterior/nuevo, IP, user-agent): login, upload/borrado de
documentos, extraccion IA (agente/modelo/tokens/duracion), cambios humanos
sobre metadatos, aprobacion/rechazo y depositos. Los registros se consultan
via `GET /api/admin/audit` (solo ADMIN) y el historial por documento via
`GET /api/documents/{id}/history`.
"""

import json
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core import storage
from app.extraction import engine
from app.jobs.tasks import deposit_document, extract_metadata
from app.main import create_app
from test_dspace import FixedConnector, _link_collection_to_type, _setup_repo
from test_normalization import NormStack


# ---------------------------------------------------------------------------
# Fixtures (mismas convenciones que test_review / test_dspace)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_app())


@pytest.fixture(scope="module")
def admin_headers(client) -> dict:
    r = client.post("/api/auth/login", json={"username": "admin", "password": "metadataia123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def catalogador_headers(client) -> dict:
    r = client.post("/api/auth/login", json={"username": "catalogador", "password": "metadataia123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def revisor_headers(client) -> dict:
    r = client.post("/api/auth/login", json={"username": "revisor", "password": "metadataia123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def stack(client, admin_headers):
    st = NormStack(client, admin_headers)
    yield st
    st.cleanup()


@pytest.fixture(autouse=True)
def _local_storage(tmp_path_factory, monkeypatch):
    path = tmp_path_factory.mktemp("storage-audit")
    monkeypatch.setattr(storage.settings, "storage_backend", "filesystem")
    monkeypatch.setattr(storage.settings, "local_storage_path", str(path))
    storage.ensure_bucket()
    yield path


@pytest.fixture(autouse=True)
def _no_broker(monkeypatch):
    for mod in (
        "app.pdf.router",
        "app.extraction.router",
        "app.jobs.tasks",
        "app.normalization.router",
        "app.validation.router",
        "app.deposit.router",
    ):
        monkeypatch.setattr(f"{mod}.celery_app.send_task", lambda name, args=None, **kw: None)
    return None


@pytest.fixture
def _fake_call_model(monkeypatch):
    fields = {
        "creator": "juan  perez",
        "date": "10/05/2023",
        "language": "Spanish",
        "title": "Auditoria de metadatos automatizada",
    }
    monkeypatch.setattr(
        engine,
        "call_model",
        lambda *a, **k: {
            "content": json.dumps(
                {"fields": {name: {"value": v, "confidence": 0.9} for name, v in fields.items()}}
            ),
            "input_tokens": 11,
            "output_tokens": 22,
            "time_ms": 33.0,
        },
    )
    return None


def _audit(client, admin_headers, **params) -> dict:
    q = "&".join(f"{k}={v}" for k, v in params.items())
    r = client.get(f"/api/admin/audit?{q}", headers=admin_headers)
    assert r.status_code == 200, r.text
    return r.json()


def _upload_extract(stack, headers, client) -> dict:
    doc = stack.upload(headers)
    assert extract_metadata(doc["id"])["status"] == "COMPLETED"
    return doc


def _cleanup_doc(doc_id: str, headers, client):
    client.delete(f"/api/documents/{doc_id}", headers=headers)


@pytest.fixture(autouse=True)
def _purge_repos_after(client, admin_headers):
    yield
    repos = client.get("/api/admin/repositories", headers=admin_headers).json()
    for r in repos:
        client.delete(f"/api/admin/repositories/{r['id']}", headers=admin_headers)


# ---------------------------------------------------------------------------
# Registro de auditoria
# ---------------------------------------------------------------------------


def test_login_registra_auditoria(client, admin_headers, catalogador_headers):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "metadataia123"})
    assert r.status_code == 200
    items = _audit(client, admin_headers, action="auth.login")["items"]
    assert items, "debe haber un registro de login"
    entry = next(i for i in items if (i.get("new_value") or {}).get("username") == "admin")
    assert entry["entity_type"] == "user"
    assert entry["user_id"]
    assert entry["ip_address"], "se debe registrar la IP del cliente"


def test_upload_registra_auditoria(client, stack, admin_headers, catalogador_headers, _fake_call_model):
    doc = _upload_extract(stack, catalogador_headers, client)
    items = _audit(client, admin_headers, action="document.upload", entity_id=doc["id"])["items"]
    assert items, "el upload debe quedar auditado"
    entry = items[0]
    assert entry["entity_type"] == "document"
    assert entry["entity_id"] == doc["id"]
    assert entry["new_value"]["filename"].endswith(".pdf")
    assert entry["new_value"]["sha256"]
    assert entry["user_id"]
    _cleanup_doc(doc["id"], catalogador_headers, client)


def test_borrado_registra_auditoria(client, stack, admin_headers, catalogador_headers, _fake_call_model):
    doc = _upload_extract(stack, catalogador_headers, client)
    r = client.delete(f"/api/documents/{doc['id']}", headers=catalogador_headers)
    assert r.status_code == 204
    items = _audit(client, admin_headers, action="document.delete", entity_id=doc["id"])["items"]
    assert items
    assert items[0]["entity_type"] == "document"


def test_edicion_registra_auditoria(client, stack, admin_headers, catalogador_headers, _fake_call_model):
    doc = _upload_extract(stack, catalogador_headers, client)
    items = client.get(f"/api/documents/{doc['id']}/metadata", headers=catalogador_headers).json()["records"]
    title = next(r for r in items if r["field"] == "creator")
    old_value = title["value"]
    r = client.put(
        f"/api/documents/{doc['id']}/records/{title['id']}",
        headers=catalogador_headers,
        json={"value": "Gonzalez, Maria"},
    )
    assert r.status_code == 200, r.text
    entries = _audit(client, admin_headers, action="record.update", entity_id=doc["id"])["items"]
    assert entries
    entry = entries[0]
    assert entry["new_value"]["value"] == "Gonzalez, Maria"
    assert entry["old_value"]["value"] == old_value
    assert entry["new_value"]["field"] == "creator"
    _cleanup_doc(doc["id"], catalogador_headers, client)


def test_crear_y_borrar_registro_auditoria(client, stack, admin_headers, catalogador_headers, _fake_call_model):
    doc = _upload_extract(stack, catalogador_headers, client)
    items = client.get(f"/api/documents/{doc['id']}/metadata", headers=catalogador_headers).json()["records"]
    existing_date = next(r for r in items if r["field"] == "date")
    r = client.delete(
        f"/api/documents/{doc['id']}/records/{existing_date['id']}", headers=catalogador_headers
    )
    assert r.status_code == 204
    r = client.post(
        f"/api/documents/{doc['id']}/records",
        headers=catalogador_headers,
        json={"field_id": stack.field_date, "value": "2024-06-01", "confidence": 1.0},
    )
    assert r.status_code == 201, r.text
    rec_id = r.json()["id"]
    entries = _audit(client, admin_headers, action="record.create", entity_id=doc["id"])["items"]
    assert entries and entries[0]["new_value"]["field"] == "date"
    r = client.delete(
        f"/api/documents/{doc['id']}/records/{rec_id}", headers=catalogador_headers
    )
    assert r.status_code == 204
    entries = _audit(client, admin_headers, action="record.delete", entity_id=doc["id"])["items"]
    assert entries and entries[0]["old_value"]["field"] == "date"
    _cleanup_doc(doc["id"], catalogador_headers, client)


def test_aprobacion_y_rechazo_registran_auditoria(client, stack, admin_headers, catalogador_headers, _fake_call_model):
    doc = _upload_extract(stack, catalogador_headers, client)
    r = client.post(f"/api/documents/{doc['id']}/approve", headers=catalogador_headers)
    assert r.status_code == 200, r.text
    entries = _audit(client, admin_headers, action="document.approve", entity_id=doc["id"])["items"]
    assert entries and entries[0]["new_value"]["status"] == "APPROVED"
    # aprobar de nuevo no registra duplicado (ya esta aprobado)
    first_total = _audit(client, admin_headers, action="document.approve", entity_id=doc["id"])["total"]
    client.post(f"/api/documents/{doc['id']}/approve", headers=catalogador_headers)
    second_total = _audit(client, admin_headers, action="document.approve", entity_id=doc["id"])["total"]
    assert second_total == first_total
    # rechazo se registra sobre el documento (se crea otro para rechazar)
    doc2 = _upload_extract(stack, catalogador_headers, client)
    r = client.post(f"/api/documents/{doc2['id']}/reject", headers=catalogador_headers)
    assert r.status_code == 200, r.text
    entries = _audit(client, admin_headers, action="document.reject", entity_id=doc2["id"])["items"]
    assert entries and entries[0]["new_value"]["status"] == "REJECTED"
    _cleanup_doc(doc["id"], catalogador_headers, client)
    _cleanup_doc(doc2["id"], catalogador_headers, client)


def test_extraccion_ia_registra_auditoria(client, stack, admin_headers, catalogador_headers, _fake_call_model):
    doc = _upload_extract(stack, catalogador_headers, client)
    entries = _audit(client, admin_headers, action="ai.extraction", entity_id=doc["id"])["items"]
    assert entries
    entry = entries[0]
    assert entry["new_value"]["agent"]
    assert entry["new_value"]["model"]
    assert entry["new_value"]["records"] == 4
    assert entry["new_value"]["input_tokens"] == 11
    assert entry["new_value"]["output_tokens"] == 22
    _cleanup_doc(doc["id"], catalogador_headers, client)


def test_deposito_registra_auditoria(
    client, stack, admin_headers, catalogador_headers, monkeypatch, _fake_call_model
):
    fc = FixedConnector()
    monkeypatch.setattr("app.jobs.tasks.build_connector", lambda repo: fc)
    repo_id = _setup_repo(client, admin_headers, stack, monkeypatch)
    _link_collection_to_type(client, admin_headers, stack, repo_id)
    doc = _upload_extract(stack, catalogador_headers, client)
    r = client.post(f"/api/documents/{doc['id']}/approve", headers=catalogador_headers)
    assert r.status_code == 200, r.text
    r = client.post(f"/api/documents/{doc['id']}/deposit", headers=catalogador_headers)
    assert r.status_code == 202, r.text
    assert deposit_document(doc["id"])["status"] == "COMPLETED"

    req = _audit(client, admin_headers, action="deposit.request", entity_id=doc["id"])["items"]
    assert req
    done = _audit(client, admin_headers, action="deposit.completed", entity_id=doc["id"])["items"]
    assert done
    entry = done[0]
    assert entry["new_value"]["external_item_id"] == "33333333-0000-4000-8000-000000000003"
    assert entry["new_value"]["handle"] == "123456789/42"
    assert entry["new_value"]["repository_code"]
    _cleanup_doc(doc["id"], catalogador_headers, client)
    client.delete(f"/api/admin/repositories/{repo_id}", headers=admin_headers)


# ---------------------------------------------------------------------------
# Consulta de auditoria
# ---------------------------------------------------------------------------


def test_audit_requiere_permiso(client, revisor_headers):
    r = client.get("/api/admin/audit", headers=revisor_headers)
    assert r.status_code == 403


def test_audit_filtros_y_paginacion(client, stack, admin_headers, catalogador_headers, _fake_call_model):
    doc = _upload_extract(stack, catalogador_headers, client)
    only_uploads = _audit(client, admin_headers, action="document.upload")["items"]
    assert only_uploads and all(i["action"] == "document.upload" for i in only_uploads)
    for_doc = _audit(client, admin_headers, entity_type="document", entity_id=doc["id"])["items"]
    assert for_doc and all(i["entity_id"] == doc["id"] for i in for_doc)
    page = _audit(client, admin_headers, limit=1)["items"]
    assert len(page) <= 1
    _cleanup_doc(doc["id"], catalogador_headers, client)


def test_historial_documento(client, stack, admin_headers, catalogador_headers, _fake_call_model):
    doc = _upload_extract(stack, catalogador_headers, client)
    r = client.get(f"/api/documents/{doc['id']}/history", headers=catalogador_headers)
    assert r.status_code == 200, r.text
    timeline = r.json()
    assert timeline
    types = {item["type"] for item in timeline}
    assert "audit" in types
    assert "job" in types
    assert any(item["action"] == "document.upload" and item["type"] == "audit" for item in timeline)
    assert any(item["job_type"] == "EXTRACTION" and item["type"] == "job" for item in timeline)
    _cleanup_doc(doc["id"], catalogador_headers, client)