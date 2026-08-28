"""Tests de administracion de agentes IA (FASE 5).

Criterio: el administrador puede crear un agente sin modificar codigo:
crear, editar, clonar, activar/desactivar, versionar, probar e historial.
"""

import uuid

import httpx
import pytest
from fastapi.testclient import TestClient

from app.ai import client as ai_client
from app.core.database import SessionLocal
from app.main import create_app
from app.models import AIAgent, AIAgentVersion, AIModel, AIProvider

TEMP_CODE = f"agente-{uuid.uuid4().hex[:8]}"


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


def _make_provider_and_model(db) -> tuple[AIProvider, AIModel]:
    provider = AIProvider(name=f"Prov {uuid.uuid4()}", code=f"prov-{uuid.uuid4().hex[:8]}", type="openai")
    db.add(provider)
    db.flush()
    model = AIModel(provider_id=provider.id, name="Modelo Test", model_identifier="gpt-test")
    db.add(model)
    db.commit()
    db.refresh(provider)
    db.refresh(model)
    return provider, model


def _cleanup(agent_id=None, model_id=None, provider_id=None) -> None:
    db = SessionLocal()
    try:
        if agent_id:
            agent = db.get(AIAgent, agent_id)
            if agent:
                db.delete(agent)
                db.commit()
        if model_id:
            model = db.get(AIModel, model_id)
            if model:
                db.delete(model)
                db.commit()
        if provider_id:
            provider = db.get(AIProvider, provider_id)
            if provider:
                db.delete(provider)
                db.commit()
    finally:
        db.close()


def _agent_payload(model_id: str, **overrides) -> dict:
    payload = {
        "name": "Extractor de Tesis",
        "code": TEMP_CODE,
        "description": "Extrae metadatos de tesis",
        "model_id": str(model_id),
        "system_prompt": "Eres un catalogador experto.",
        "extraction_prompt": (
            "Extrae los campos del documento.\n"
            "Tipo documental: {{document_type}}\n"
            "Texto: {{document_text}}"
        ),
        "temperature": 0.1,
        "max_tokens": 2000,
    }
    payload.update(overrides)
    return payload


# --- acceso ----------------------------------------------------------------


def test_agentes_sin_token_401(client):
    assert client.get("/api/admin/ai/agents").status_code == 401


def test_agentes_sin_permiso_403(client, catalogador_headers):
    assert client.get("/api/admin/ai/agents", headers=catalogador_headers).status_code == 403


# --- crear ----------------------------------------------------------------


def test_crear_agente_sin_modelo_422(client, admin_headers):
    r = client.post(
        "/api/admin/ai/agents",
        json={"name": "Agente", "code": TEMP_CODE},
        headers=admin_headers,
    )
    assert r.status_code == 422


def test_crear_agente_ok_con_version_1(client, admin_headers):
    db = SessionLocal()
    try:
        provider, model = _make_provider_and_model(db)
        try:
            r = client.post("/api/admin/ai/agents", json=_agent_payload(model.id), headers=admin_headers)
            assert r.status_code == 201, r.text
            data = r.json()
            assert data["code"] == TEMP_CODE
            assert data["current_version"]["version_number"] == 1
            assert data["current_version"]["model_identifier"] == "gpt-test"
            agent_id = data["id"]
            _cleanup(agent_id=agent_id, model_id=model.id, provider_id=provider.id)
        finally:
            _cleanup(model_id=model.id, provider_id=provider.id)
    finally:
        db.close()


def test_crear_agente_codigo_duplicado_409(client, admin_headers):
    db = SessionLocal()
    try:
        provider, model = _make_provider_and_model(db)
        agent = AIAgent(name="A", code=TEMP_CODE)
        db.add(agent)
        db.commit()
        agent_id = agent.id
        try:
            r = client.post("/api/admin/ai/agents", json=_agent_payload(model.id), headers=admin_headers)
            assert r.status_code == 409
        finally:
            _cleanup(agent_id=agent_id, model_id=model.id, provider_id=provider.id)
    finally:
        db.close()


# --- listar / detalle -------------------------------------------------------


def test_listar_agentes_contiene_creado(client, admin_headers):
    db = SessionLocal()
    try:
        provider, model = _make_provider_and_model(db)
        r = client.post("/api/admin/ai/agents", json=_agent_payload(model.id), headers=admin_headers)
        agent_id = r.json()["id"]
        try:
            r2 = client.get("/api/admin/ai/agents", headers=admin_headers)
            codes = [a["code"] for a in r2.json()]
            assert TEMP_CODE in codes
        finally:
            _cleanup(agent_id=agent_id, model_id=model.id, provider_id=provider.id)
    finally:
        db.close()


def test_get_agente_detalle(client, admin_headers):
    db = SessionLocal()
    try:
        provider, model = _make_provider_and_model(db)
        agent_id = client.post("/api/admin/ai/agents", json=_agent_payload(model.id), headers=admin_headers).json()["id"]
        try:
            r = client.get(f"/api/admin/ai/agents/{agent_id}", headers=admin_headers)
            assert r.status_code == 200
            data = r.json()
            assert data["id"] == agent_id
            assert data["current_version"]["version_number"] == 1
        finally:
            _cleanup(agent_id=agent_id, model_id=model.id, provider_id=provider.id)
    finally:
        db.close()


def test_get_agente_inexistente_404(client, admin_headers):
    r = client.get(f"/api/admin/ai/agents/{uuid.uuid4()}", headers=admin_headers)
    assert r.status_code == 404


# --- editar / activar-desactivar / versionar --------------------------------


def test_actualizar_agente_y_generar_version_nueva(client, admin_headers):
    db = SessionLocal()
    try:
        provider1, model1 = _make_provider_and_model(db)
        agent_id = client.post("/api/admin/ai/agents", json=_agent_payload(model1.id), headers=admin_headers).json()["id"]
        provider2, model2 = _make_provider_and_model(db)
        try:
            r = client.put(
                f"/api/admin/ai/agents/{agent_id}",
                json={
                    "name": "Extractor Renombrado",
                    "model_id": str(model2.id),
                    "extraction_prompt": "Nuevo prompt v2",
                    "temperature": 0.5,
                },
                headers=admin_headers,
            )
            assert r.status_code == 200, r.text
            data = r.json()
            assert data["name"] == "Extractor Renombrado"
            assert data["current_version"]["version_number"] == 2
            assert data["current_version"]["model_id"] == str(model2.id)
            assert data["current_version"]["extraction_prompt"] == "Nuevo prompt v2"
        finally:
            _cleanup(agent_id=agent_id, model_id=model1.id, provider_id=provider1.id)
            _cleanup(model_id=model2.id, provider_id=provider2.id)
    finally:
        db.close()


def test_desactivar_agente_sin_nueva_version(client, admin_headers):
    db = SessionLocal()
    try:
        provider, model = _make_provider_and_model(db)
        agent_id = client.post("/api/admin/ai/agents", json=_agent_payload(model.id), headers=admin_headers).json()["id"]
        try:
            r = client.put(f"/api/admin/ai/agents/{agent_id}", json={"active": False}, headers=admin_headers)
            assert r.status_code == 200
            data = r.json()
            assert data["active"] is False
            assert data["current_version"]["version_number"] == 1
        finally:
            _cleanup(agent_id=agent_id, model_id=model.id, provider_id=provider.id)
    finally:
        db.close()


def test_crear_version_explicita(client, admin_headers):
    db = SessionLocal()
    try:
        provider, model = _make_provider_and_model(db)
        agent_id = client.post("/api/admin/ai/agents", json=_agent_payload(model.id), headers=admin_headers).json()["id"]
        try:
            r = client.post(
                f"/api/admin/ai/agents/{agent_id}/versions",
                json={"model_id": str(model.id), "extraction_prompt": "Prompt v3", "temperature": 0.9},
                headers=admin_headers,
            )
            assert r.status_code == 201, r.text
            data = r.json()
            assert data["version_number"] == 2

            r2 = client.get(f"/api/admin/ai/agents/{agent_id}", headers=admin_headers)
            assert r2.json()["current_version"]["version_number"] == 2
        finally:
            _cleanup(agent_id=agent_id, model_id=model.id, provider_id=provider.id)
    finally:
        db.close()


# --- historial de versiones -------------------------------------------------


def test_historial_de_versiones_ordenado(client, admin_headers):
    db = SessionLocal()
    try:
        provider, model = _make_provider_and_model(db)
        agent_id = client.post("/api/admin/ai/agents", json=_agent_payload(model.id), headers=admin_headers).json()["id"]
        try:
            client.post(
                f"/api/admin/ai/agents/{agent_id}/versions",
                json={"model_id": str(model.id), "extraction_prompt": "v2"},
                headers=admin_headers,
            )
            r = client.get(f"/api/admin/ai/agents/{agent_id}/versions", headers=admin_headers)
            assert r.status_code == 200
            versions = r.json()
            assert len(versions) == 2
            assert versions[0]["version_number"] == 2  # mas reciente primero
            assert versions[1]["version_number"] == 1
            assert versions[0]["extraction_prompt"] == "v2"
        finally:
            _cleanup(agent_id=agent_id, model_id=model.id, provider_id=provider.id)
    finally:
        db.close()


# --- clonar -----------------------------------------------------------------


def test_clonar_agente(client, admin_headers):
    db = SessionLocal()
    try:
        provider, model = _make_provider_and_model(db)
        agent_id = client.post("/api/admin/ai/agents", json=_agent_payload(model.id), headers=admin_headers).json()["id"]
        clone_id = None
        try:
            r = client.post(f"/api/admin/ai/agents/{agent_id}/clone", headers=admin_headers)
            assert r.status_code == 201, r.text
            clone = r.json()
            clone_id = clone["id"]
            assert clone["code"] == f"{TEMP_CODE}-copia"
            assert clone["current_version"]["version_number"] == 1
            assert clone["current_version"]["extraction_prompt"] == _agent_payload(model.id)["extraction_prompt"]
            assert clone["id"] != agent_id
        finally:
            _cleanup(agent_id=clone_id)
            _cleanup(agent_id=agent_id, model_id=model.id, provider_id=provider.id)
    finally:
        db.close()


# --- eliminar ----------------------------------------------------------------


def test_eliminar_agente_borra_versiones(client, admin_headers):
    db = SessionLocal()
    try:
        provider, model = _make_provider_and_model(db)
        agent_id = client.post("/api/admin/ai/agents", json=_agent_payload(model.id), headers=admin_headers).json()["id"]
        r = client.delete(f"/api/admin/ai/agents/{agent_id}", headers=admin_headers)
        assert r.status_code == 204
        assert db.get(AIAgent, agent_id) is None
        remaining = db.query(AIAgentVersion).filter(AIAgentVersion.agent_id == agent_id).count()
        assert remaining == 0
        _cleanup(model_id=model.id, provider_id=provider.id)
    finally:
        db.close()


def test_eliminar_agente_inexistente_404(client, admin_headers):
    r = client.delete(f"/api/admin/ai/agents/{uuid.uuid4()}", headers=admin_headers)
    assert r.status_code == 404


# --- probar agente ----------------------------------------------------------


def _mock_http(monkeypatch, handler):
    def factory(*args, **kwargs):
        return httpx.Client(transport=httpx.MockTransport(handler), *args, **kwargs)

    monkeypatch.setattr(ai_client, "_http", factory)


def test_probar_agente_exitoso(client, admin_headers, monkeypatch):
    calls = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json
        body = json.loads(request.content)
        calls["user_message"] = body["messages"][-1]["content"]
        calls["model"] = body.get("model")
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "{\"titulo\": \"X\"}"}}], "model": "gpt-test"}
        )

    _mock_http(monkeypatch, handler)

    db = SessionLocal()
    try:
        provider, model = _make_provider_and_model(db)
        agent_id = client.post(
            "/api/admin/ai/agents",
            json=_agent_payload(model.id, extraction_prompt="Contenido: {{document_text}}"),
            headers=admin_headers,
        ).json()["id"]
        try:
            r = client.post(f"/api/admin/ai/agents/{agent_id}/test", headers=admin_headers)
            assert r.status_code == 200, r.text
            data = r.json()
            assert data["ok"] is True
            assert calls["model"] == "gpt-test"
            assert "document_text" not in calls["user_message"]  # variable reemplazada
            assert len(calls["user_message"]) > 20
        finally:
            _cleanup(agent_id=agent_id, model_id=model.id, provider_id=provider.id)
    finally:
        db.close()


def test_probar_agente_error_controlado(client, admin_headers):
    db = SessionLocal()
    try:
        provider = AIProvider(name="Prov", code=f"prov-{uuid.uuid4().hex[:8]}", type="openai",
                              base_url="http://127.0.0.1:1")
        db.add(provider)
        db.flush()
        model = AIModel(provider_id=provider.id, name="M", model_identifier="m")
        db.add(model)
        db.commit()
        agent_id = client.post(
            "/api/admin/ai/agents", json=_agent_payload(model.id), headers=admin_headers
        ).json()["id"]
        try:
            r = client.post(f"/api/admin/ai/agents/{agent_id}/test", headers=admin_headers)
            assert r.status_code == 200, r.text
            data = r.json()
            assert data["ok"] is False
            assert data["message"]
        finally:
            _cleanup(agent_id=agent_id, model_id=model.id, provider_id=provider.id)
    finally:
        db.close()


# --- variables de prompt ------------------------------------------------------


def test_render_prompt_variables_conocidas_y_desconocidas():
    from app.ai.client import render_prompt

    context = {"document_text": "EL TEXTO DEL PDF", "language": "es"}
    rendered = render_prompt(
        "{{document_text}} fin {{language}} {{desconocida}}",
        context,
    )
    assert "EL TEXTO DEL PDF" in rendered
    assert "es" in rendered
    assert "{{desconocida}}" in rendered  # se deja intacta, no se inventa