"""Tests de revision humana (FASE 12).

El catalogador puede corregir TODOS los metadatos antes del deposito:
editar registros, crear faltantes, borrar errores, revalidar, aprobar y
rechazar. No se permite aprobar si la validacion tiene errores.
"""

import json
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core import storage
from app.core.database import SessionLocal
from app.extraction import engine
from app.jobs.tasks import extract_metadata, validate_metadata
from app.main import create_app
from test_normalization import NormStack


# ---------------------------------------------------------------------------
# Fixtures
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
    path = tmp_path_factory.mktemp("storage-review")
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
    ):
        monkeypatch.setattr(f"{mod}.celery_app.send_task", lambda name, args=None, **kw: None)
    return None


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
    fields = {"creator": "juan  perez", "date": "10/05/2023", "language": "Spanish", "title": "Titulo original"}
    monkeypatch.setattr(engine, "call_model", _fake_with(fields))
    return None


def _cleanup_doc(doc_id: str, headers, client):
    client.delete(f"/api/documents/{doc_id}", headers=headers)


def _records(client, doc_id, headers) -> dict:
    return {r["field"]: r for r in client.get(f"/api/documents/{doc_id}/metadata", headers=headers).json()["records"]}


def _upload_and_extract(stack, headers, client) -> dict:
    doc = stack.upload(headers)
    assert extract_metadata(doc["id"])["status"] == "COMPLETED"
    return doc


# ---------------------------------------------------------------------------
# Edicion de registros
# ---------------------------------------------------------------------------


def test_editar_registro_marca_manual(client, stack, catalogador_headers, _fake_call_model, _no_auto_chain):
    doc = _upload_and_extract(stack, catalogador_headers, client)
    by_field = _records(client, doc["id"], catalogador_headers)
    creator = by_field["creator"]

    r = client.put(
        f"/api/documents/{doc['id']}/records/{creator['id']}",
        headers=catalogador_headers,
        json={"value": "Maria Lopez"},
    )
    assert r.status_code == 200, r.text
    rec = r.json()
    assert rec["value"] == "Maria Lopez"
    assert rec["manually_modified"] is True
    assert rec["validated"] is False

    detail = client.get(f"/api/documents/{doc['id']}", headers=catalogador_headers).json()
    assert detail["status"] == "NEEDS_REVIEW"
    _cleanup_doc(doc["id"], catalogador_headers, client)


def test_crear_registro_faltante(client, stack, catalogador_headers, admin_headers, monkeypatch, _no_auto_chain):
    monkeypatch.setattr(
        engine, "call_model", _fake_with({"creator": "Juan", "date": "2023-05-10", "language": "spa"})
    )
    doc = _upload_and_extract(stack, catalogador_headers, client)
    assert "title" not in _records(client, doc["id"], catalogador_headers)

    r = client.post(
        f"/api/documents/{doc['id']}/records",
        headers=catalogador_headers,
        json={"field_id": stack.field_title, "value": "Tesis corregida por catalogador"},
    )
    assert r.status_code == 201, r.text
    rec = r.json()
    assert rec["field"] == "title"
    assert rec["source"] == "MANUAL"
    assert rec["manually_modified"] is True

    by_field = _records(client, doc["id"], catalogador_headers)
    assert by_field["title"]["value"] == "Tesis corregida por catalogador"
    assert client.get(f"/api/documents/{doc['id']}", headers=catalogador_headers).json()["status"] == "NEEDS_REVIEW"
    _cleanup_doc(doc["id"], catalogador_headers, client)


def test_crear_registro_campo_no_del_tipo_409(
    client, stack, catalogador_headers, _fake_call_model, _no_auto_chain
):
    unlinked = stack._field("coverage", "Cobertura")
    doc = _upload_and_extract(stack, catalogador_headers, client)
    r = client.post(
        f"/api/documents/{doc['id']}/records",
        headers=catalogador_headers,
        json={"field_id": unlinked, "value": "Argentina"},
    )
    assert r.status_code == 409, r.text
    _cleanup_doc(doc["id"], catalogador_headers, client)


def test_borrar_registro(client, stack, catalogador_headers, _fake_call_model, _no_auto_chain):
    doc = _upload_and_extract(stack, catalogador_headers, client)
    creator = _records(client, doc["id"], catalogador_headers)["creator"]
    r = client.delete(
        f"/api/documents/{doc['id']}/records/{creator['id']}", headers=catalogador_headers
    )
    assert r.status_code == 204, r.text
    assert "creator" not in _records(client, doc["id"], catalogador_headers)
    assert client.get(f"/api/documents/{doc['id']}", headers=catalogador_headers).json()["status"] == "NEEDS_REVIEW"
    _cleanup_doc(doc["id"], catalogador_headers, client)


def test_editar_registro_404(client, stack, catalogador_headers, _fake_call_model, _no_auto_chain):
    doc = _upload_and_extract(stack, catalogador_headers, client)
    r = client.put(
        f"/api/documents/{doc['id']}/records/00000000-0000-0000-0000-000000000000",
        headers=catalogador_headers,
        json={"value": "x"},
    )
    assert r.status_code == 404
    _cleanup_doc(doc["id"], catalogador_headers, client)


# ---------------------------------------------------------------------------
# Permisos
# ---------------------------------------------------------------------------


def test_revisor_edita_pero_no_aprueba(
    client, stack, catalogador_headers, revisor_headers, _fake_call_model, _no_auto_chain
):
    doc = _upload_and_extract(stack, catalogador_headers, client)
    creator = _records(client, doc["id"], catalogador_headers)["creator"]

    r = client.put(
        f"/api/documents/{doc['id']}/records/{creator['id']}",
        headers=revisor_headers,
        json={"value": "Ramiro Firma"},
    )
    assert r.status_code == 200, r.text

    r = client.post(f"/api/documents/{doc['id']}/approve", headers=revisor_headers)
    assert r.status_code == 403, r.text
    _cleanup_doc(doc["id"], catalogador_headers, client)


# ---------------------------------------------------------------------------
# Aprobacion y rechazo
# ---------------------------------------------------------------------------


def test_aprobar_revalida_y_marca_aprobado(
    client, stack, catalogador_headers, _fake_call_model, _no_auto_chain
):
    doc = _upload_and_extract(stack, catalogador_headers, client)
    assert validate_metadata(doc["id"])["valid"] is True

    r = client.post(f"/api/documents/{doc['id']}/approve", headers=catalogador_headers)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "APPROVED"
    assert client.get(f"/api/documents/{doc['id']}", headers=catalogador_headers).json()["status"] == "APPROVED"
    _cleanup_doc(doc["id"], catalogador_headers, client)


def test_aprobar_con_errores_de_validacion_409(
    client, stack, catalogador_headers, monkeypatch, _no_auto_chain
):
    monkeypatch.setattr(engine, "call_model", _fake_with({"creator": "Juan", "date": "2023-05-10"}))
    doc = _upload_and_extract(stack, catalogador_headers, client)
    assert validate_metadata(doc["id"])["valid"] is False

    r = client.post(f"/api/documents/{doc['id']}/approve", headers=catalogador_headers)
    assert r.status_code == 409, r.text
    assert client.get(f"/api/documents/{doc['id']}", headers=catalogador_headers).json()["status"] == "VALIDATION_FAILED"
    _cleanup_doc(doc["id"], catalogador_headers, client)


def test_aprobar_sin_metadatos_409(client, stack, catalogador_headers, _fake_call_model):
    doc = stack.upload(catalogador_headers)
    r = client.post(f"/api/documents/{doc['id']}/approve", headers=catalogador_headers)
    assert r.status_code == 409, r.text
    _cleanup_doc(doc["id"], catalogador_headers, client)


def test_rechazar_documento(client, stack, catalogador_headers, _fake_call_model, _no_auto_chain):
    doc = _upload_and_extract(stack, catalogador_headers, client)
    r = client.post(f"/api/documents/{doc['id']}/reject", headers=catalogador_headers)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "REJECTED"
    assert client.get(f"/api/documents/{doc['id']}", headers=catalogador_headers).json()["status"] == "REJECTED"
    _cleanup_doc(doc["id"], catalogador_headers, client)


def test_no_se_puede_editar_documento_aprobado(
    client, stack, catalogador_headers, _fake_call_model, _no_auto_chain
):
    doc = _upload_and_extract(stack, catalogador_headers, client)
    assert validate_metadata(doc["id"])["valid"] is True
    assert client.post(f"/api/documents/{doc['id']}/approve", headers=catalogador_headers).status_code == 200

    creator = _records(client, doc["id"], catalogador_headers)["creator"]
    r = client.put(
        f"/api/documents/{doc['id']}/records/{creator['id']}",
        headers=catalogador_headers,
        json={"value": "no deberia poder"},
    )
    assert r.status_code == 409, r.text
    _cleanup_doc(doc["id"], catalogador_headers, client)