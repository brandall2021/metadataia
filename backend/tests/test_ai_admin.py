"""Tests de administracion IA - proveedores y modelos (FASE 4).

Criterio: el administrador puede registrar un proveedor y probar un modelo.

Las llamadas HTTP reales a proveedores externos se simulan con
httpx.MockTransport (dependencia externa inevitable); los caminos de error
(host inalcanzable) se prueban de forma real contra un puerto local cerrado.
"""

import uuid

import httpx
import pytest
from fastapi.testclient import TestClient

from app.ai import client as ai_client
from app.core.database import SessionLocal
from app.main import create_app
from app.models import AIModel, AIProvider

TEMP_PROVIDER_CODE = "prov-test-temp"


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


def _make_provider(db, code: str, base_url: str | None = None, api_key: str | None = None) -> AIProvider:
    provider = AIProvider(
        name=f"Proveedor {code}",
        code=code,
        type="openai",
        base_url=base_url,
        api_key_encrypted=api_key,
        active=True,
    )
    db.add(provider)
    db.commit()
    db.refresh(provider)
    return provider


def _delete_provider(provider_id) -> None:
    db = SessionLocal()
    try:
        provider = db.get(AIProvider, provider_id)
        if provider:
            db.delete(provider)
            db.commit()
    finally:
        db.close()


# --- proveedores: acceso ---------------------------------------------------


def test_providers_sin_token_401(client):
    assert client.get("/api/admin/ai/providers").status_code == 401


def test_providers_sin_permiso_403(client, catalogador_headers):
    assert client.get("/api/admin/ai/providers", headers=catalogador_headers).status_code == 403


# --- proveedores: CRUD -----------------------------------------------------


def test_crear_proveedor_y_key_nunca_expuesta(client, admin_headers):
    db = SessionLocal()
    try:
        payload = {
            "name": "Proveedor Test",
            "code": TEMP_PROVIDER_CODE,
            "type": "openai",
            "base_url": "https://api.openai.com/v1",
            "api_key": "sk-secreto-super-secreto-1234",
        }
        r = client.post("/api/admin/ai/providers", json=payload, headers=admin_headers)
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["code"] == TEMP_PROVIDER_CODE
        assert "1234" in data["api_key_masked"]
        assert data["api_key_masked"].startswith("****")
        assert "sk-secreto-super-secreto-1234" not in r.text

        r2 = client.get("/api/admin/ai/providers", headers=admin_headers)
        found = next(p for p in r2.json() if p["code"] == TEMP_PROVIDER_CODE)
        assert found["api_key_masked"].startswith("****")
        assert "sk-secreto-super-secreto-1234" not in r2.text
    finally:
        _delete_provider(db.query(AIProvider).filter_by(code=TEMP_PROVIDER_CODE).first().id)
        db.close()


def test_crear_proveedor_codigo_duplicado_409(client, admin_headers):
    db = SessionLocal()
    try:
        provider = _make_provider(db, TEMP_PROVIDER_CODE)
        try:
            r = client.post(
                "/api/admin/ai/providers",
                json={"name": "Otro", "code": TEMP_PROVIDER_CODE, "type": "openai"},
                headers=admin_headers,
            )
            assert r.status_code == 409
        finally:
            _delete_provider(provider.id)
    finally:
        db.close()


def test_actualizar_proveedor(client, admin_headers):
    db = SessionLocal()
    try:
        provider = _make_provider(db, TEMP_PROVIDER_CODE)
        try:
            r = client.put(
                f"/api/admin/ai/providers/{provider.id}",
                json={"name": "Nombre Actualizado"},
                headers=admin_headers,
            )
            assert r.status_code == 200
            assert r.json()["name"] == "Nombre Actualizado"
        finally:
            _delete_provider(provider.id)
    finally:
        db.close()


def test_eliminar_proveedor_sin_modelos_204(client, admin_headers):
    db = SessionLocal()
    try:
        provider = _make_provider(db, TEMP_PROVIDER_CODE)
        pid = provider.id
        r = client.delete(f"/api/admin/ai/providers/{pid}", headers=admin_headers)
        assert r.status_code == 204
        check = SessionLocal()
        try:
            assert check.get(AIProvider, pid) is None
        finally:
            check.close()
    finally:
        _delete_provider(pid if 'pid' in locals() else provider.id)
        db.close()


def test_eliminar_proveedor_con_modelo_409(client, admin_headers):
    db = SessionLocal()
    try:
        provider = _make_provider(db, TEMP_PROVIDER_CODE)
        model = AIModel(
            provider_id=provider.id,
            name="Modelo X",
            model_identifier="gpt-x",
            supports_json=True,
        )
        db.add(model)
        db.commit()
        try:
            r = client.delete(f"/api/admin/ai/providers/{provider.id}", headers=admin_headers)
            assert r.status_code == 409
        finally:
            db.delete(model)
            db.commit()
            _delete_provider(provider.id)
    finally:
        db.close()


def test_proveedor_inexistente_404(client, admin_headers):
    r = client.get(f"/api/admin/ai/providers/{uuid.uuid4()}", headers=admin_headers)
    assert r.status_code in (404, 405)


# --- proveedores: prueba de conexion ---------------------------------------


def _mock_http(monkeypatch, handler):
    def factory(*args, **kwargs):
        return httpx.Client(transport=httpx.MockTransport(handler), *args, **kwargs)

    monkeypatch.setattr(ai_client, "_http", factory)


def test_prueba_conexion_exitosa(client, admin_headers, monkeypatch):
    calls = {}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["url"] = str(request.url)
        return httpx.Response(200, json={"data": [{"id": "gpt-4o"}]})

    _mock_http(monkeypatch, handler)

    db = SessionLocal()
    try:
        provider = _make_provider(db, TEMP_PROVIDER_CODE, base_url="https://fake.test/v1")
        try:
            r = client.post(
                f"/api/admin/ai/providers/{provider.id}/test", headers=admin_headers
            )
            assert r.status_code == 200, r.text
            data = r.json()
            assert data["ok"] is True
            assert calls["url"] == "https://fake.test/v1/models"
        finally:
            _delete_provider(provider.id)
    finally:
        db.close()


def test_prueba_conexion_host_inalcanzable_reporte_error(client, admin_headers):
    db = SessionLocal()
    try:
        provider = _make_provider(db, TEMP_PROVIDER_CODE, base_url="http://127.0.0.1:1")
        try:
            r = client.post(
                f"/api/admin/ai/providers/{provider.id}/test", headers=admin_headers
            )
            assert r.status_code == 200, r.text
            data = r.json()
            assert data["ok"] is False
            assert data["message"]
        finally:
            _delete_provider(provider.id)
    finally:
        db.close()


# --- modelos ---------------------------------------------------------------


def _make_model(db, provider_id) -> AIModel:
    model = AIModel(
        provider_id=provider_id,
        name="Modelo Test",
        model_identifier="gpt-test",
        supports_json=True,
        temperature_default=0.1,
        max_tokens_default=1000,
    )
    db.add(model)
    db.commit()
    db.refresh(model)
    return model


def test_crear_modelo_ok(client, admin_headers):
    db = SessionLocal()
    try:
        provider = _make_provider(db, TEMP_PROVIDER_CODE)
        try:
            r = client.post(
                "/api/admin/ai/models",
                json={
                    "provider_id": str(provider.id),
                    "name": "Modelo Test",
                    "model_identifier": "gpt-test",
                    "supports_json": True,
                    "temperature_default": 0.1,
                },
                headers=admin_headers,
            )
            assert r.status_code == 201, r.text
            data = r.json()
            assert data["model_identifier"] == "gpt-test"
            assert data["provider_name"] == provider.name
            model_id = data["id"]

            r2 = client.get("/api/admin/ai/models", headers=admin_headers)
            models = r2.json()
            assert any(m["id"] == model_id for m in models)

            model = db.get(AIModel, uuid.UUID(model_id))
            db.delete(model)
            db.commit()
        finally:
            _delete_provider(provider.id)
    finally:
        db.close()


def test_crear_modelo_proveedor_inexistente_422(client, admin_headers):
    r = client.post(
        "/api/admin/ai/models",
        json={"provider_id": str(uuid.uuid4()), "name": "M", "model_identifier": "m"},
        headers=admin_headers,
    )
    assert r.status_code in (404, 422)


def test_actualizar_modelo(client, admin_headers):
    db = SessionLocal()
    try:
        provider = _make_provider(db, TEMP_PROVIDER_CODE)
        model = _make_model(db, provider.id)
        try:
            r = client.put(
                f"/api/admin/ai/models/{model.id}",
                json={"name": "Modelo Renombrado", "active": False},
                headers=admin_headers,
            )
            assert r.status_code == 200
            data = r.json()
            assert data["name"] == "Modelo Renombrado"
            assert data["active"] is False
        finally:
            db.delete(db.get(AIModel, model.id))
            db.commit()
            _delete_provider(provider.id)
    finally:
        db.close()


def test_eliminar_modelo_204(client, admin_headers):
    db = SessionLocal()
    try:
        provider = _make_provider(db, TEMP_PROVIDER_CODE)
        model = _make_model(db, provider.id)
        try:
            r = client.delete(f"/api/admin/ai/models/{model.id}", headers=admin_headers)
            assert r.status_code == 204
            check = SessionLocal()
            try:
                assert check.get(AIModel, model.id) is None
            finally:
                check.close()
        finally:
            _delete_provider(provider.id)
    finally:
        db.close()


def test_modelo_inexistente_404(client, admin_headers):
    r = client.put(
        f"/api/admin/ai/models/{uuid.uuid4()}",
        json={"name": "X"},
        headers=admin_headers,
    )
    assert r.status_code == 404


# --- modelos: probar modelo -------------------------------------------------


def test_probar_modelo_exitoso(client, admin_headers, monkeypatch):
    calls = {}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["url"] = str(request.url)
        calls["method"] = request.method
        body = json_loads(request.content)
        calls["model"] = body.get("model")
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "pong"}}], "model": "gpt-test"}
        )

    _mock_http(monkeypatch, handler)

    db = SessionLocal()
    try:
        provider = _make_provider(db, TEMP_PROVIDER_CODE, base_url="https://fake.test/v1")
        model = _make_model(db, provider.id)
        try:
            r = client.post(
                f"/api/admin/ai/models/{model.id}/test", headers=admin_headers
            )
            assert r.status_code == 200, r.text
            data = r.json()
            assert data["ok"] is True
            assert calls["method"] == "POST"
            assert calls["url"] == "https://fake.test/v1/chat/completions"
            assert calls["model"] == "gpt-test"
        finally:
            db.delete(db.get(AIModel, model.id))
            db.commit()
            _delete_provider(provider.id)
    finally:
        db.close()


def test_probar_modelo_error_controlado(client, admin_headers):
    db = SessionLocal()
    try:
        provider = _make_provider(db, TEMP_PROVIDER_CODE, base_url="http://127.0.0.1:1")
        model = _make_model(db, provider.id)
        try:
            r = client.post(
                f"/api/admin/ai/models/{model.id}/test", headers=admin_headers
            )
            assert r.status_code == 200, r.text
            data = r.json()
            assert data["ok"] is False
            assert data["message"]
        finally:
            db.delete(db.get(AIModel, model.id))
            db.commit()
            _delete_provider(provider.id)
    finally:
        db.close()


def json_loads(content: bytes) -> dict:
    import json
    return json.loads(content)