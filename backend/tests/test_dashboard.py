"""Tests del dashboard de estadisticas (FASE 15).

`GET /api/admin/dashboard` (permiso ``dashboard.view``, disponible para todos
los roles) agrega: documentos por estado (total, procesados, pendientes de
revision, aprobados, rechazados, depositados), procesamiento (OCR ejecutados,
extracciones IA, tiempo promedio, errores por tipo), IA (ejecuciones, tokens,
errores por agente y por modelo) y depositos.
"""

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.core import storage
from app.core.database import SessionLocal
from app.extraction import engine
from app.jobs.tasks import deposit_document, extract_metadata
from app.main import create_app
from app.models import ProcessingJob, ExtractionRun
from test_dspace import FixedConnector, _link_collection_to_type, _setup_repo
from test_normalization import NormStack


# ---------------------------------------------------------------------------
# Fixtures (mismas convenciones que test_audit / test_review)
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
    path = tmp_path_factory.mktemp("storage-dash")
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
        "title": "Dashboard de estadisticas",
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


@pytest.fixture(autouse=True)
def _purge_repos_after(client, admin_headers):
    yield
    repos = client.get("/api/admin/repositories", headers=admin_headers).json()
    for r in repos:
        client.delete(f"/api/admin/repositories/{r['id']}", headers=admin_headers)


def _dash(client, headers) -> dict:
    r = client.get("/api/admin/dashboard", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def _upload_extract(stack, headers, client) -> dict:
    doc = stack.upload(headers)
    assert extract_metadata(doc["id"])["status"] == "COMPLETED"
    return doc


def _cleanup_doc(doc_id: str, headers, client):
    client.delete(f"/api/documents/{doc_id}", headers=headers)


def _add_job(doc_id: str, job_type: str, status: str, **kw) -> None:
    db = SessionLocal()
    try:
        db.add(
            ProcessingJob(
                document_id=uuid.UUID(doc_id),
                job_type=job_type,
                status=status,
                started_at=kw.get("started_at"),
                finished_at=kw.get("finished_at"),
                error_message=kw.get("error_message"),
            )
        )
        db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


def test_dashboard_requiere_token(client):
    assert client.get("/api/admin/dashboard").status_code == 401


def test_dashboard_estructura_y_permisos(client, admin_headers, catalogador_headers, revisor_headers):
    for headers in (admin_headers, catalogador_headers, revisor_headers):
        data = _dash(client, headers)
        assert "documentos" in data
        assert "procesamiento" in data
        assert "ia" in data
        assert "depositos" in data
        assert data["documentos"]["total"] >= 0


def test_dashboard_metricas_documentos(client, stack, admin_headers, catalogador_headers, _fake_call_model):
    doc = _upload_extract(stack, catalogador_headers, client)
    data = _dash(client, admin_headers)
    assert data["documentos"]["total"] >= 1
    assert data["documentos"]["procesados"] >= 1
    by_state = data["documentos"]["por_estado"]
    assert by_state.get("METADATA_EXTRACTED", 0) >= 1

    r = client.post(f"/api/documents/{doc['id']}/approve", headers=catalogador_headers)
    assert r.status_code == 200, r.text
    data = _dash(client, admin_headers)
    assert data["documentos"]["por_estado"]["APPROVED"] >= 1
    assert data["documentos"]["aprobados"] >= 1
    _cleanup_doc(doc["id"], catalogador_headers, client)


def test_dashboard_procesamiento_jobs(client, stack, admin_headers, catalogador_headers, _fake_call_model):
    doc = _upload_extract(stack, catalogador_headers, client)
    data = _dash(client, admin_headers)
    pc = data["procesamiento"]
    assert pc["extracciones_ia"] >= 1
    assert pc["tiempo_promedio_ms"] is None or pc["tiempo_promedio_ms"] >= 0
    assert pc["jobs_por_estado"].get("COMPLETED", 0) >= 1
    _cleanup_doc(doc["id"], catalogador_headers, client)


def test_dashboard_errores_procesamiento(client, stack, admin_headers, catalogador_headers, _fake_call_model):
    doc = _upload_extract(stack, catalogador_headers, client)
    now = datetime.now(timezone.utc)
    _add_job(doc["id"], "OCR", "ERROR",
             started_at=now - timedelta(seconds=2), finished_at=now,
             error_message="fallo ocr")
    data = _dash(client, admin_headers)
    assert data["procesamiento"]["errores"] >= 1
    assert data["procesamiento"]["errores_por_tipo"].get("OCR", 0) >= 1
    _cleanup_doc(doc["id"], catalogador_headers, client)


def test_dashboard_ia_errores_por_agente_y_modelo(client, stack, admin_headers, catalogador_headers, _fake_call_model):
    doc = _upload_extract(stack, catalogador_headers, client)
    agent_id, model_id = None, None
    db = SessionLocal()
    try:
        from app.models import AIAgent, AIModel
        agent = db.query(AIAgent).order_by(AIAgent.code.asc()).first()
        model = db.query(AIModel).order_by(AIModel.model_identifier.asc()).first()
        agent_id, model_id = agent.id, model.id
        if agent and model:
            db.add(
                ExtractionRun(
                    document_id=uuid.UUID(doc["id"]),
                    agent_id=agent.id,
                    agent_version_id=None,
                    model_id=model.id,
                    prompt_hash="abcd1234",
                    started_at=datetime.now(timezone.utc),
                    finished_at=datetime.now(timezone.utc),
                    input_tokens=10,
                    output_tokens=5,
                    status="ERROR",
                    error_message="fallo ia",
                )
            )
            db.commit()
    finally:
        db.close()
    data = _dash(client, admin_headers)
    ia = data["ia"]
    assert ia["ejecuciones"] >= 1
    assert ia["errores"] >= 1
    by_agent = ia["errores_por_agente"]
    by_model = ia["errores_por_modelo"]
    if agent_id:
        assert any(a["errores"] >= 1 for a in by_agent)
    if model_id:
        assert any(m["errores"] >= 1 for m in by_model)
    _cleanup_doc(doc["id"], catalogador_headers, client)


def test_dashboard_depositos(
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
    data = _dash(client, admin_headers)
    assert data["depositos"]["completados"] >= 1
    assert data["depositos"]["total"] >= 1
    assert data["documentos"]["por_estado"]["DEPOSITED"] >= 1
    _cleanup_doc(doc["id"], catalogador_headers, client)
    client.delete(f"/api/admin/repositories/{repo_id}", headers=admin_headers)