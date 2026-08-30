"""Pruebas e2e (FASE 16): pipeline completo por HTTP REAL.

A diferencia del resto de la suite (mocks en proceso), este modulo arranca
los servidores de mentira de IA (scripts/mock_ai_server.py) y de DSpace 9
(scripts/mock_dspace_server.py) como subprocesos en puertos libres, de modo
que ``engine.call_model`` (extraccion) y ``Dspace9Connector`` (sync y
deposito) hacen conexiones HTTP reales de punta a punta sin monkeypatch.

Lo unico que se mantiene simulado es el broker de celery (las tareas se
invocan directamente, como en toda la suite) y el almacenamiento
(filesystem temporal), ambos ajenos al alcance de esta fase.
"""

import socket
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core import storage
from app.core.database import SessionLocal
from app.jobs.tasks import deposit_document, extract_metadata, run_ocr
from app.main import create_app
from app.models import DocumentPage, ExtractionRun
from app.ocr import engine as ocr_engine
from test_normalization import NormStack
from test_ocr import _blank_pdf

ROOT = Path(__file__).resolve().parents[2]


def _scripts_dir() -> Path:
    candidates = [
        Path("/app/scripts"),
        ROOT / "scripts",
    ]
    for cand in candidates:
        if (cand / "mock_ai_server.py").exists():
            return cand
    raise RuntimeError("scripts/ no encontrado (mock_ai_server.py)")


# ---------------------------------------------------------------------------
# Subprocesos: servidores mock fuera de proceso
# ---------------------------------------------------------------------------


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_port(port: int, proc: subprocess.Popen, tries: int = 50) -> None:
    import time

    for _ in range(tries):
        if proc.poll() is not None:
            raise RuntimeError(f"servidor mock murio al arrancar: {proc.poll()}")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError(f"servidor mock no respondio en el puerto {port}")


@pytest.fixture(scope="module")
def _servers():
    procs = []
    try:
        ports = {}
        scripts = _scripts_dir()
        for key, script in (
            ("ai", "mock_ai_server.py"),
            ("dspace", "mock_dspace_server.py"),
        ):
            port = _free_port()
            proc = subprocess.Popen(
                [sys.executable, str(scripts / script), str(port)],
                cwd=str(scripts),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            procs.append(proc)
            _wait_port(port, proc)
            ports[key] = port
        yield ports
    finally:
        for proc in procs:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


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
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def revisor_headers(client) -> dict:
    r = client.post("/api/auth/login", json={"username": "revisor", "password": "metadataia123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def stack(client, admin_headers, _servers):
    st = NormStack(
        client,
        admin_headers,
        ai_base_url=f"http://localhost:{_servers['ai']}/v1",
    )
    yield st
    st.cleanup()


@pytest.fixture(autouse=True)
def _local_storage(tmp_path_factory, monkeypatch):
    path = tmp_path_factory.mktemp("storage-e2e")
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _setup_repo_real(client, admin_headers, stack, dspace_port) -> str:
    """Repositorio sobre el conector REAL apuntando al mock DSpace (sin patch)."""
    r = client.post(
        "/api/admin/repositories",
        headers=admin_headers,
        json={
            "name": f"Repo E2E {uuid.uuid4().hex[:6]}",
            "code": f"repo-e2e-{uuid.uuid4().hex[:8]}",
            "base_url": f"http://localhost:{dspace_port}",
            "api_url": f"http://localhost:{dspace_port}",
            "authentication_type": "dspace",
            "username": "dspace@example.com",
            "credential": "supersecreto",
            "active": True,
        },
    )
    assert r.status_code == 201, r.text
    repo_id = r.json()["id"]
    s = client.post(
        f"/api/admin/repositories/{repo_id}/collections/sync", headers=admin_headers
    )
    assert s.status_code == 200, s.text
    cols = client.get(
        f"/api/admin/repositories/{repo_id}/collections", headers=admin_headers
    ).json()
    assert cols, "sync no trajo colecciones"
    first = next(
        (c for c in cols if c["external_id"] == "c0aa0000-0000-4000-8000-0000000000c1"),
        cols[0],
    )
    r = client.put(
        f"/api/admin/repositories/{repo_id}/collections/{first['id']}",
        headers=admin_headers,
        json={"document_type_id": stack.type_id, "active": True},
    )
    assert r.status_code == 200, r.text
    return repo_id


def _cleanup_doc(doc_id: str, headers, client) -> None:
    client.delete(f"/api/documents/{doc_id}", headers=headers)


def _real_run(doc_id: str) -> dict:
    """Datos del ExtractionRun real (HTTP) para comprobar origen y tokens."""
    db = SessionLocal()
    try:
        run = (
            db.query(ExtractionRun)
            .filter(ExtractionRun.document_id == uuid.UUID(doc_id))
            .order_by(ExtractionRun.started_at.desc())
            .first()
        )
        if run is None:
            return {}
        return {
            "status": run.status,
            "input_tokens": run.input_tokens,
            "output_tokens": run.output_tokens,
            "agent": run.agent_version.agent.code if run.agent_version else None,
            "model": run.model.model_identifier if run.model else None,
            "provider": (
                run.model.provider.code
                if run.model and run.model.provider is not None
                else None
            ),
        }
    finally:
        db.close()


def _depositions(client, doc_id: str, headers) -> list:
    r = client.get(f"/api/documents/{doc_id}/depositions", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def _audit(client, headers, **params) -> list:
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    r = client.get(f"/api/admin/audit?{qs}", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["items"]


# ---------------------------------------------------------------------------
# E2E: flujo completo del usuario final
# ---------------------------------------------------------------------------


def test_e2e_flujo_completo(
    client, stack, admin_headers, catalogador_headers, _servers, _local_storage, _no_broker
):
    repo_id = _setup_repo_real(client, admin_headers, stack, _servers["dspace"])

    # --- subida + extraccion IA por HTTP real ---------------------------
    doc = stack.upload(catalogador_headers)
    assert doc["needs_ocr"] is False
    res = extract_metadata(doc["id"])
    assert res["status"] == "COMPLETED", res
    assert res["records"] == 4

    info = _real_run(doc["id"])
    assert info["status"] == "COMPLETED"
    assert info["input_tokens"] == 123 and info["output_tokens"] == 45  # valores del mock real
    assert info["agent"] == stack.agent_code
    assert info["model"] == "mock-model-norm"
    assert info["provider"] == stack.provider_code

    # --- cadena automatica: extraccion -> normalizacion -> validacion ---
    d = client.get(f"/api/documents/{doc['id']}", headers=catalogador_headers).json()
    assert d["status"] == "VALIDATED"

    # --- correccion humana de un registro -------------------------------
    meta = client.get(
        f"/api/documents/{doc['id']}/metadata", headers=catalogador_headers
    ).json()["records"]
    creator = next(r for r in meta if r["field"] == "creator")
    r = client.put(
        f"/api/documents/{doc['id']}/records/{creator['id']}",
        headers=catalogador_headers,
        json={"value": "Gonzalez, Maria"},
    )
    assert r.status_code == 200, r.text
    updated = client.get(
        f"/api/documents/{doc['id']}/metadata", headers=catalogador_headers
    ).json()["records"]
    assert any(
        rec["id"] == creator["id"] and rec["value"] == "Gonzalez, Maria" for rec in updated
    )

    # --- aprobacion (revalida) ------------------------------------------
    r = client.post(f"/api/documents/{doc['id']}/approve", headers=catalogador_headers)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "APPROVED"

    # --- deposito real contra DSpace mock --------------------------------
    r = client.post(f"/api/documents/{doc['id']}/deposit", headers=catalogador_headers)
    assert r.status_code == 202, r.text
    dr = deposit_document(doc["id"])
    assert dr["status"] == "COMPLETED", dr

    d = client.get(f"/api/documents/{doc['id']}", headers=catalogador_headers).json()
    assert d["status"] == "DEPOSITED"
    deps = _depositions(client, doc["id"], catalogador_headers)
    assert len(deps) == 1
    assert deps[0]["status"] == "COMPLETED"
    assert deps[0]["handle"] == "123456789/42"
    assert str(deps[0]["external_item_id"]).startswith("33333333-")

    # --- no duplica el deposito -----------------------------------------
    assert deposit_document(doc["id"])["status"] == "NOOP"
    assert len(_depositions(client, doc["id"], catalogador_headers)) == 1

    # --- auditoria del flujo --------------------------------------------
    entry = _audit(
        client, admin_headers, action="ai.extraction", entity_id=doc["id"]
    )[0]["new_value"]
    assert entry["agent"] == stack.agent_code
    assert entry["provider"] == stack.provider_code
    assert entry["input_tokens"] == 123

    up = _audit(client, admin_headers, action="document.upload", entity_id=doc["id"])[0]
    assert up["username"] == "catalogador"
    assert _audit(client, admin_headers, action="document.approve", entity_id=doc["id"])
    assert _audit(client, admin_headers, action="deposit.completed", entity_id=doc["id"])

    # --- historial unificado --------------------------------------------
    hist = client.get(
        f"/api/documents/{doc['id']}/history", headers=catalogador_headers
    ).json()
    types = {item["type"] for item in hist}
    assert {"audit", "job", "deposition"} <= types

    # --- el dashboard refleja el pipeline real --------------------------
    dash = client.get("/api/admin/dashboard", headers=admin_headers).json()
    assert dash["documentos"]["depositados"] >= 1
    assert dash["ia"]["ejecuciones"] >= 1
    assert dash["ia"]["ok"] >= 1
    assert any(a["ejecuciones"] >= 1 for a in dash["ia"]["errores_por_agente"])

    _cleanup_doc(doc["id"], catalogador_headers, client)
    r = client.delete(f"/api/admin/repositories/{repo_id}", headers=admin_headers)
    assert r.status_code == 204, r.text


def test_e2e_deposito_vs_estado(
    client, stack, catalogador_headers, _local_storage, _no_broker
):
    doc = stack.upload(catalogador_headers)
    r = client.post(f"/api/documents/{doc['id']}/deposit", headers=catalogador_headers)
    assert r.status_code == 409, r.text
    assert deposit_document(doc["id"])["status"] == "ERROR"
    _cleanup_doc(doc["id"], catalogador_headers, client)


def test_e2e_permisos(
    client,
    stack,
    admin_headers,
    catalogador_headers,
    revisor_headers,
    _local_storage,
    _no_broker,
):
    assert client.get("/api/admin/dashboard").status_code == 401
    assert client.get("/api/admin/audit").status_code == 401

    # el revisor tiene dashboard.view pero no audit.view
    assert client.get("/api/admin/dashboard", headers=revisor_headers).status_code == 200
    assert client.get("/api/admin/audit", headers=revisor_headers).status_code == 403
    assert client.get("/api/admin/repositories", headers=revisor_headers).status_code == 403

    # la historia del documento es visible para quien tiene document.view
    doc = stack.upload(catalogador_headers)
    assert client.get(
        f"/api/documents/{doc['id']}/history", headers=revisor_headers
    ).status_code == 200
    _cleanup_doc(doc["id"], catalogador_headers, client)


def test_e2e_ocr_real(
    client, stack, admin_headers, catalogador_headers, _local_storage, _no_broker
):
    if not ocr_engine.is_executable():
        pytest.skip("ocrmypdf/tesseract no estan disponibles")
    r = client.post(
        "/api/documents",
        headers=catalogador_headers,
        files={"file": ("scan.pdf", _blank_pdf(2), "application/pdf")},
        data={"document_type_id": stack.type_id},
    )
    assert r.status_code == 201, r.text
    doc = r.json()
    assert doc["needs_ocr"] is True

    res = run_ocr(doc["id"])
    assert res["status"] == "COMPLETED", res

    db = SessionLocal()
    try:
        pages = (
            db.query(DocumentPage)
            .filter(DocumentPage.document_id == uuid.UUID(doc["id"]))
            .all()
        )
        assert pages and all(p.ocr_used for p in pages)
    finally:
        db.close()

    assert _audit(client, admin_headers, action="ocr.completed", entity_id=doc["id"])
    _cleanup_doc(doc["id"], catalogador_headers, client)