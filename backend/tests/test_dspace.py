"""Tests de integracion con DSpace (FASE 13).

Configuracion del repositorio (Administracion > Repositorios), conector
Dspace9Connector (autenticacion, comunidades/colecciones, workspace item,
metadata, bitstream, submission) y deposito de un documento aprobado.
"""

import json
import uuid

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core import storage
from app.extraction import engine
from app.jobs.tasks import deposit_document, extract_metadata
from app.main import create_app
from test_normalization import NormStack


# ---------------------------------------------------------------------------
# Conectores falsos
# ---------------------------------------------------------------------------


class FakeSyncConnector:
    """Conector falsificado para sincronizar comunidades/colecciones."""

    def authenticate(self):
        return "fake-token"

    def get_communities(self, token=None):
        return [
            {"uuid": "c0ee0000-0000-4000-8000-0000000000aa", "name": "Comunidad 1", "handle": "123456789/0"},
        ]

    def get_collections(self, community_uuid=None, token=None):
        return [
            {"uuid": "c0aa0000-0000-4000-8000-0000000000c1", "name": "Coleccion Tesis", "handle": "123456789/10"},
            {"uuid": "c0aa0000-0000-4000-8000-0000000000c2", "name": "Coleccion Articulos", "handle": "123456789/11"},
        ]

    def get_collection(self, collection_uuid, token=None):
        for c in self.get_collections():
            if c["uuid"] == collection_uuid:
                return c
        raise RuntimeError("no encontrada")


class FixedConnector:
    """Conector falsificado que responde al flujo completo de deposito."""

    def __init__(self, fail_on=None, collection_uuid=None):
        self.fail_on = fail_on
        self.calls = []
        self.collection_uuid = collection_uuid or "c0aa0000-0000-4000-8000-0000000000c1"

    def authenticate(self):
        self.calls.append("authenticate")
        return "fake-token"

    def create_workspace_item(self, collection_uuid, token):
        self.calls.append(("create_workspace_item", collection_uuid))
        self._maybe_fail("create_workspace_item")
        return {"id": "ws-1000", "uuid": "11111111-0000-4000-8000-000000000001"}

    def add_metadata(self, workspace_id, metadata, token):
        self.calls.append(("add_metadata", workspace_id, metadata))

    def upload_bitstream(self, workspace_id, filename, content, token):
        self.calls.append(("upload_bitstream", workspace_id, filename, len(content)))
        return {"uuid": "22222222-0000-4000-8000-000000000002", "name": filename}

    def submit_workspace_item(self, workspace_id, token):
        self.calls.append(("submit_workspace_item", workspace_id))
        self._maybe_fail("submit_workspace_item")
        return {"item_uuid": "33333333-0000-4000-8000-000000000003", "handle": "123456789/42"}

    def get_item(self, item_uuid, token):
        self.calls.append(("get_item", item_uuid))
        return {"uuid": item_uuid, "handle": "123456789/42"}

    def get_workspace_item(self, workspace_id, token):
        self.calls.append(("get_workspace_item", workspace_id))
        return {"id": workspace_id}

    def _maybe_fail(self, step):
        if self.fail_on == step:
            raise RuntimeError(f"falla simulada en {step}")


class RecordingClient:
    """Cliente HTTP registrador para probar las llamadas REST del conector."""

    def __init__(self):
        self.requests = []
        self.login_token = "tok-abc-123"

    def request(self, method, url, **kwargs):
        self.requests.append((method, url, kwargs))
        path = url.split("/api/")[-1].split("?")[0]
        if method == "POST" and path == "authn/login":
            return httpx.Response(200, content=self.login_token.encode())
        if method == "GET" and path == "core/communities":
            return httpx.Response(200, json={"_embedded": {"communities": [
                {"uuid": "cc", "name": "C1", "handle": "h/0"}
            ]}})
        if method == "GET" and path == "core/collections":
            return httpx.Response(200, json={"_embedded": {"collections": [
                {"uuid": "u1", "name": "Col1", "handle": "h/10"}
            ]}})
        if method == "GET" and path.startswith("core/collections/"):
            return httpx.Response(200, json={"uuid": "u1", "name": "Col1", "handle": "h/10"})
        if method == "POST" and path.startswith("submission/workspaceitems"):
            return httpx.Response(201, json={"id": 7, "uuid": "wsid"})
        if method == "PATCH" and path.startswith("submission/workspaceitems/"):
            return httpx.Response(200, json={"id": 7})
        if method == "GET" and path.startswith("submission/workspaceitems/"):
            return httpx.Response(200, json={"id": 7})
        if method == "POST" and path.startswith("workflow/workflowitems"):
            return httpx.Response(201, json={"item": {"uuid": "item-123"}})
        if method == "GET" and path.startswith("core/items/"):
            return httpx.Response(200, json={"uuid": "item-123", "handle": "123456789/42"})
        return httpx.Response(404, json={"message": f"no mock para {method} {path}"})


# ---------------------------------------------------------------------------
# Fixtures
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
def stack(client, admin_headers):
    st = NormStack(client, admin_headers)
    yield st
    st.cleanup()


@pytest.fixture(autouse=True)
def _local_storage(tmp_path_factory, monkeypatch):
    path = tmp_path_factory.mktemp("storage-dspace")
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
    }
    monkeypatch.setattr(engine, "call_model", _fake_with(fields))
    return None


def _upload_extract_approve(stack, headers, client) -> dict:
    doc = stack.upload(headers)
    assert extract_metadata(doc["id"])["status"] == "COMPLETED"
    r = client.post(f"/api/documents/{doc['id']}/approve", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "APPROVED"
    return doc


def _setup_repo(client, admin_headers, stack, monkeypatch, sync=True) -> str:
    class Fake:  # noqa: N801 - objeto contenedor
        pass

    monkeypatch.setattr(
        "app.repositories.router.build_connector", lambda repo: FakeSyncConnector()
    )
    r = client.post(
        "/api/admin/repositories",
        headers=admin_headers,
        json={
            "name": "Repositorio Snrd",
            "code": f"repo-{uuid.uuid4().hex[:8]}",
            "base_url": "http://dspace:8080",
            "api_url": "http://dspace:8080/server/api",
            "authentication_type": "dspace",
            "username": "dspace@example.com",
            "credential": "supersecreto",
            "active": True,
        },
    )
    assert r.status_code == 201, r.text
    repo_id = r.json()["id"]
    if sync:
        s = client.post(f"/api/admin/repositories/{repo_id}/collections/sync", headers=admin_headers)
        assert s.status_code == 200, s.text
    return repo_id


def _link_collection_to_type(client, admin_headers, stack, repo_id) -> str:
    cols = client.get(f"/api/admin/repositories/{repo_id}/collections", headers=admin_headers).json()
    col = next(c for c in cols if c["external_id"] == "c0aa0000-0000-4000-8000-0000000000c1")
    r = client.put(
        f"/api/admin/repositories/{repo_id}/collections/{col['id']}",
        headers=admin_headers,
        json={"document_type_id": stack.type_id, "active": True},
    )
    assert r.status_code == 200, r.text
    return col["id"]


def _cleanup_doc(doc_id: str, headers, client):
    client.delete(f"/api/documents/{doc_id}", headers=headers)


def _cleanup_repo(client, admin_headers, repo_id):
    r = client.delete(f"/api/admin/repositories/{repo_id}", headers=admin_headers)
    assert r.status_code == 204, r.text


@pytest.fixture(autouse=True)
def _purge_repos_after(client, admin_headers):
    yield
    repos = client.get("/api/admin/repositories", headers=admin_headers).json()
    for r in repos:
        client.delete(f"/api/admin/repositories/{r['id']}", headers=admin_headers)


# ---------------------------------------------------------------------------
# Configuracion del repositorio (admin)
# ---------------------------------------------------------------------------


def test_crear_repositorio_y_enmascarar_credencial(client, admin_headers, catalogador_headers):
    r = client.post(
        "/api/admin/repositories",
        headers=admin_headers,
        json={
            "name": "Repo Principal",
            "code": f"repo-{uuid.uuid4().hex[:8]}",
            "base_url": "http://dspace:8080",
            "api_url": "http://dspace:8080/server/api",
            "username": "admin@dspace.org",
            "credential": "clave-123",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["active"] is True
    assert body["credential"] == "********"

    got = client.get(f"/api/admin/repositories/{body['id']}", headers=admin_headers).json()
    assert got["username"] == "admin@dspace.org"
    assert got["credential"] == "********"
    assert "clave-123" not in json.dumps(got)

    r2 = client.post("/api/admin/repositories", headers=catalogador_headers, json={"name": "x", "code": "y"})
    assert r2.status_code == 403
    client.delete(f"/api/admin/repositories/{body['id']}", headers=admin_headers)


def test_sincronizar_colecciones_y_asociar_tipo(
    client, admin_headers, stack, monkeypatch, _fake_call_model, _no_auto_chain
):
    repo_id = _setup_repo(client, admin_headers, stack, monkeypatch)
    cols = client.get(f"/api/admin/repositories/{repo_id}/collections", headers=admin_headers).json()
    assert len(cols) == 2
    tesis = next(c for c in cols if c["external_id"].endswith("c1"))
    assert tesis["name"] == "Coleccion Tesis"
    assert tesis["handle"] == "123456789/10"

    col_id = _link_collection_to_type(client, admin_headers, stack, repo_id)
    cols = client.get(f"/api/admin/repositories/{repo_id}/collections", headers=admin_headers).json()
    linked = next(c for c in cols if c["id"] == col_id)
    assert linked["document_type_id"] == stack.type_id
    client.delete(f"/api/admin/repositories/{repo_id}", headers=admin_headers)


# ---------------------------------------------------------------------------
# Conector DSpace 9 (fidelidad REST)
# ---------------------------------------------------------------------------


def test_connector_metodos_dspace9():
    from app.dspace.connector import Dspace9Connector

    rc = RecordingClient()
    conn = Dspace9Connector(
        api_url="http://dspace:8080/server/api",
        username="user@x.org",
        credential="pass",
        client=rc,
    )
    token = conn.authenticate()
    assert token == "tok-abc-123"
    method, url, kwargs = rc.requests[-1]
    assert method == "POST"
    assert url.endswith("/server/api/authn/login")
    assert kwargs["data"] == {"user": "user@x.org", "password": "pass"}

    conn.get_communities()
    assert rc.requests[-1][0] == "GET" and rc.requests[-1][1].endswith("core/communities")

    conn.get_collections()
    assert rc.requests[-1][1].endswith("core/collections")

    conn.get_collection("u1")
    assert rc.requests[-1][1].endswith("core/collections/u1")

    ws = conn.create_workspace_item("u1", token)
    assert ws["id"] == 7
    _, url, kw = rc.requests[-1]
    assert "submission/workspaceitems" in url
    assert kw["params"] == {"parent": "u1"}

    conn.add_metadata(7, {"dc.title": ["Titulo"], "dc.contributor.author": ["Autor"]}, token)
    _, url, kw = rc.requests[-1]
    assert url.endswith("submission/workspaceitems/7")
    ops = kw["json"]
    assert ops[0]["op"] == "add"
    assert ops[0]["path"] == "/sections/traditionalpageone/dc.title"
    assert ops[0]["value"][0]["value"] == "Titulo"

    conn.upload_bitstream(7, "tesis.pdf", b"%PDF-1.4", token)
    _, url, kw = rc.requests[-1]
    assert url.endswith("submission/workspaceitems/7")
    assert "files" in kw

    submitted = conn.submit_workspace_item(7, token)
    assert submitted["item_uuid"] == "item-123"
    assert submitted["handle"] == "123456789/42"
    assert "workflow/workflowitems" in rc.requests[-2][1]
    assert "text/uri-list" in rc.requests[-2][2]["headers"]["Content-Type"]

    item = conn.get_item("item-123", token)
    assert item["handle"] == "123456789/42"

    ws_item = conn.get_workspace_item(7, token)
    assert ws_item["id"] == 7


# ---------------------------------------------------------------------------
# Deposito de documentos aprobados
# ---------------------------------------------------------------------------


def test_depositar_documento_aprobado(
    client, stack, catalogador_headers, admin_headers, monkeypatch, _fake_call_model, _no_auto_chain
):
    fc = FixedConnector()
    monkeypatch.setattr("app.jobs.tasks.build_connector", lambda repo: fc)
    repo_id = _setup_repo(client, admin_headers, stack, monkeypatch)
    _link_collection_to_type(client, admin_headers, stack, repo_id)

    doc = _upload_extract_approve(stack, catalogador_headers, client)
    r = client.post(f"/api/documents/{doc['id']}/deposit", headers=catalogador_headers)
    assert r.status_code == 202, r.text

    res = deposit_document(doc["id"])
    assert res["status"] == "COMPLETED", res
    assert fc.calls[0] == "authenticate"
    assert fc.calls[1][0] == "create_workspace_item"
    assert fc.calls[2][0] == "add_metadata"

    detail = client.get(f"/api/documents/{doc['id']}", headers=catalogador_headers).json()
    assert detail["status"] == "DEPOSITED"

    deps = client.get(f"/api/documents/{doc['id']}/depositions", headers=catalogador_headers).json()
    assert len(deps) == 1
    dep = deps[0]
    assert dep["status"] == "COMPLETED"
    assert dep["external_item_id"] == "33333333-0000-4000-8000-000000000003"
    assert dep["handle"] == "123456789/42"
    assert dep["repository_id"] == repo_id

    jobs = client.get(f"/api/documents/{doc['id']}", headers=catalogador_headers).json()["jobs"]
    dep_job = next(j for j in jobs if j["job_type"] == "DEPOSIT")
    assert dep_job["status"] == "COMPLETED"
    assert dep_job["metadata_json"]["external_item_id"] == dep["external_item_id"]
    _cleanup_doc(doc["id"], catalogador_headers, client)
    _cleanup_repo(client, admin_headers, repo_id)


def test_deposito_no_duplica(
    client, stack, catalogador_headers, admin_headers, monkeypatch, _fake_call_model, _no_auto_chain
):
    fc = FixedConnector()
    monkeypatch.setattr("app.jobs.tasks.build_connector", lambda repo: fc)
    repo_id = _setup_repo(client, admin_headers, stack, monkeypatch)
    _link_collection_to_type(client, admin_headers, stack, repo_id)

    doc = _upload_extract_approve(stack, catalogador_headers, client)
    assert deposit_document(doc["id"])["status"] == "COMPLETED"

    r = client.post(f"/api/documents/{doc['id']}/deposit", headers=catalogador_headers)
    assert r.status_code == 409, r.text

    res = deposit_document(doc["id"])
    assert res["status"] == "NOOP"
    assert len(fc.calls) == 5
    _cleanup_doc(doc["id"], catalogador_headers, client)
    _cleanup_repo(client, admin_headers, repo_id)


def test_depositar_requiere_aprobado(
    client, stack, catalogador_headers, admin_headers, monkeypatch, _fake_call_model, _no_auto_chain
):
    fc = FixedConnector()
    monkeypatch.setattr("app.jobs.tasks.build_connector", lambda repo: fc)
    repo_id = _setup_repo(client, admin_headers, stack, monkeypatch)
    _link_collection_to_type(client, admin_headers, stack, repo_id)

    doc = stack.upload(catalogador_headers)
    assert extract_metadata(doc["id"])["status"] == "COMPLETED"
    r = client.post(f"/api/documents/{doc['id']}/deposit", headers=catalogador_headers)
    assert r.status_code == 409, r.text
    assert fc.calls == []
    _cleanup_doc(doc["id"], catalogador_headers, client)


def test_depositar_sin_repositorio_409(
    client, stack, catalogador_headers, _fake_call_model, _no_auto_chain
):
    doc = _upload_extract_approve(stack, catalogador_headers, client)
    r = client.post(f"/api/documents/{doc['id']}/deposit", headers=catalogador_headers)
    assert r.status_code == 409, r.text
    _cleanup_doc(doc["id"], catalogador_headers, client)


def test_deposito_fallido_y_reintento(
    client, stack, catalogador_headers, admin_headers, monkeypatch, _fake_call_model, _no_auto_chain
):
    fc = FixedConnector(fail_on="create_workspace_item")
    monkeypatch.setattr("app.jobs.tasks.build_connector", lambda repo: fc)
    repo_id = _setup_repo(client, admin_headers, stack, monkeypatch)
    _link_collection_to_type(client, admin_headers, stack, repo_id)

    doc = _upload_extract_approve(stack, catalogador_headers, client)
    res = deposit_document(doc["id"])
    assert res["status"] == "ERROR", res
    detail = client.get(f"/api/documents/{doc['id']}", headers=catalogador_headers).json()
    assert detail["status"] == "APPROVED"
    dep_job = next(j for j in detail["jobs"] if j["job_type"] == "DEPOSIT")
    assert dep_job["status"] == "ERROR"
    assert "falla simulada" in dep_job["error_message"]
    deps = client.get(f"/api/documents/{doc['id']}/depositions", headers=catalogador_headers).json()
    assert deps[-1]["status"] == "FAILED"

    fc.fail_on = None
    res2 = deposit_document(doc["id"])
    assert res2["status"] == "COMPLETED", res2
    assert client.get(f"/api/documents/{doc['id']}", headers=catalogador_headers).json()["status"] == "DEPOSITED"
    _cleanup_doc(doc["id"], catalogador_headers, client)
    _cleanup_repo(client, admin_headers, repo_id)


def test_export_snrd_json(
    client, stack, catalogador_headers, _fake_call_model, _no_auto_chain
):
    doc = stack.upload(catalogador_headers)
    assert extract_metadata(doc["id"])["status"] == "COMPLETED"
    r = client.get(f"/api/documents/{doc['id']}/snrd", headers=catalogador_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "dc.title" in body["metadata"]
    assert body["metadata"]["dc.title"][0]["value"] == "Impacto de la IA en bibliotecas"
    assert "dc.date.issued" in body["metadata"]
    _cleanup_doc(doc["id"], catalogador_headers, client)