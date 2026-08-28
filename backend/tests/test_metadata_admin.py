"""Tests de administracion de metadatos (FASE 6).

Criterio: el administrador puede crear un nuevo campo y verlo automaticamente
en el frontend (la API lo devuelve en el listado dinamicamente).
Incluye: esquemas, campos, vocabularios (+CSV/sinonimos), tipos documentales
y asociaciones.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.main import create_app
from app.models import AIAgent, AIModel, AIProvider, DocumentType, MetadataField, MetadataSchema, Vocabulary

UUID = str


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


CODE = f"md-{uuid.uuid4().hex[:8]}"


def _make_schema(name="Schema Test") -> MetadataSchema:
    db = SessionLocal()
    try:
        schema = MetadataSchema(name=name, code=CODE, namespace="dc")
        db.add(schema)
        db.commit()
        db.refresh(schema)
        return schema
    finally:
        db.close()


def _delete_schema(schema_id) -> None:
    db = SessionLocal()
    try:
        schema = db.get(MetadataSchema, schema_id)
        if schema:
            db.delete(schema)
            db.commit()
    finally:
        db.close()


def _make_agent() -> AIAgent:
    from app.models import AIAgentVersion

    db = SessionLocal()
    try:
        provider = AIProvider(name=f"P-{uuid.uuid4().hex[:6]}", code=f"p-{uuid.uuid4().hex[:8]}", type="openai")
        db.add(provider)
        db.flush()
        model = AIModel(provider_id=provider.id, name="M", model_identifier="m")
        db.add(model)
        db.flush()
        agent = AIAgent(name="Agente", code=f"a-{uuid.uuid4().hex[:8]}")
        db.add(agent)
        db.flush()
        version = AIAgentVersion(agent_id=agent.id, version_number=1, model_id=model.id)
        db.add(version)
        db.flush()
        agent.current_version_id = version.id
        db.commit()
        db.refresh(agent)
        return agent, (provider.id, model.id)
    finally:
        db.close()


def _cleanup_type_and_agent(agent_id=None, provider_id=None, model_id=None) -> None:
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


# --- acceso ----------------------------------------------------------------


def test_schemas_sin_token_401(client):
    assert client.get("/api/admin/metadata/schemas").status_code == 401


def test_schemas_sin_permiso_403(client, catalogador_headers):
    assert client.get("/api/admin/metadata/schemas", headers=catalogador_headers).status_code == 403


# --- esquemas ----------------------------------------------------------------

def test_crear_esquema_y_listar(client, admin_headers):
    r = client.post(
        "/api/admin/metadata/schemas",
        json={"name": "SNRD Dublin Core", "code": CODE, "namespace": "dc"},
        headers=admin_headers,
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["code"] == CODE
    assert data["namespace"] == "dc"

    r2 = client.get("/api/admin/metadata/schemas", headers=admin_headers)
    assert any(s["code"] == CODE for s in r2.json())

    _delete_schema(data["id"])


def test_crear_esquema_codigo_duplicado_409(client, admin_headers):
    schema = _make_schema()
    try:
        r = client.post(
            "/api/admin/metadata/schemas",
            json={"name": "Otro", "code": CODE},
            headers=admin_headers,
        )
        assert r.status_code == 409
    finally:
        _delete_schema(schema.id)


def test_actualizar_esquema(client, admin_headers):
    schema = _make_schema()
    try:
        r = client.put(
            f"/api/admin/metadata/schemas/{schema.id}",
            json={"name": "Renombrado", "active": False},
            headers=admin_headers,
        )
        assert r.status_code == 200
        assert r.json()["name"] == "Renombrado"
        assert r.json()["active"] is False
    finally:
        _delete_schema(schema.id)


def test_eliminar_esquema_borra_campos(client, admin_headers):
    db = SessionLocal()
    try:
        schema = _make_schema()
        field = MetadataField(schema_id=schema.id, element="title", display_name="Titulo")
        db.add(field)
        db.commit()
        fid = field.id
        r = client.delete(f"/api/admin/metadata/schemas/{schema.id}", headers=admin_headers)
        assert r.status_code == 204
        db.expire_all()
        assert db.get(MetadataField, fid) is None
    finally:
        db.close()


# --- campos ------------------------------------------------------------------

def test_crear_campo_aparece_en_listado(client, admin_headers):
    schema = _make_schema()
    try:
        r = client.post(
            "/api/admin/metadata/fields",
            json={
                "schema_id": str(schema.id),
                "element": "title",
                "qualifier": "alternative",
                "display_name": "Titulo alternativo",
                "required": False,
                "repeatable": True,
                "ai_extractable": True,
            },
            headers=admin_headers,
        )
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["element"] == "title"
        assert data["schema_code"] == CODE

        r2 = client.get("/api/admin/metadata/fields", headers=admin_headers)
        assert any(f["id"] == data["id"] for f in r2.json())

        r3 = client.get(f"/api/admin/metadata/fields?schema_id={schema.id}", headers=admin_headers)
        ids = [f["id"] for f in r3.json()]
        assert data["id"] in ids
    finally:
        _delete_schema(schema.id)


def test_crear_campo_schemas_inexistente_404(client, admin_headers):
    r = client.post(
        "/api/admin/metadata/fields",
        json={"schema_id": str(uuid.uuid4()), "element": "title"},
        headers=admin_headers,
    )
    assert r.status_code in (404, 422)


def test_actualizar_campo(client, admin_headers):
    schema = _make_schema()
    db = SessionLocal()
    try:
        field = MetadataField(schema_id=schema.id, element="title", display_name="Titulo")
        db.add(field)
        db.commit()
        fid = field.id
        r = client.put(
            f"/api/admin/metadata/fields/{fid}",
            json={"display_name": "Titulo editado", "required": True, "validation_type": "url"},
            headers=admin_headers,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["display_name"] == "Titulo editado"
        assert data["required"] is True
        assert data["validation_type"] == "url"
    finally:
        _delete_schema(schema.id)
        db.close()


def test_eliminar_campo_204(client, admin_headers):
    schema = _make_schema()
    db = SessionLocal()
    try:
        field = MetadataField(schema_id=schema.id, element="title")
        db.add(field)
        db.commit()
        fid = field.id
        r = client.delete(f"/api/admin/metadata/fields/{fid}", headers=admin_headers)
        assert r.status_code == 204
        db.expire_all()
        assert db.get(MetadataField, fid) is None
    finally:
        _delete_schema(schema.id)
        db.close()


# --- vocabularios -------------------------------------------------------------

def test_vocabulario_crud_ok(client, admin_headers):
    r = client.post(
        "/api/admin/vocabularies",
        json={"name": "Idiomas", "code": f"{CODE}-idiomas", "description": "ISO 639"},
        headers=admin_headers,
    )
    assert r.status_code == 201, r.text
    vocab_id = r.json()["id"]

    r2 = client.get("/api/admin/vocabularies", headers=admin_headers)
    assert any(v["id"] == vocab_id for v in r2.json())

    r3 = client.put(f"/api/admin/vocabularies/{vocab_id}", json={"name": "Lenguas"}, headers=admin_headers)
    assert r3.status_code == 200
    assert r3.json()["name"] == "Lenguas"

    r4 = client.delete(f"/api/admin/vocabularies/{vocab_id}", headers=admin_headers)
    assert r4.status_code == 204


def test_vocabulario_valores_y_sinonimos(client, admin_headers):
    r = client.post(
        "/api/admin/vocabularies",
        json={"name": "Idiomas", "code": f"{CODE}-idiomas"},
        headers=admin_headers,
    )
    vocab_id = r.json()["id"]
    try:
        r = client.post(
            f"/api/admin/vocabularies/{vocab_id}/values",
            json={"code": "spa", "label": "Español", "synonyms": ["Castellano", "Spanish"]},
            headers=admin_headers,
        )
        assert r.status_code == 201, r.text
        value = r.json()
        assert value["code"] == "spa"
        assert "Castellano" in value["synonyms"]
        assert value["normalized_value"] == "espanol"  # normalizado al guardar

        r2 = client.get(f"/api/admin/vocabularies/{vocab_id}/values", headers=admin_headers)
        assert any(v["id"] == value["id"] for v in r2.json())

        r3 = client.post(
            f"/api/admin/vocabularies/{vocab_id}/normalize",
            json={"value": "Castellano"},
            headers=admin_headers,
        )
        assert r3.status_code == 200
        n = r3.json()
        assert n["found"] is True
        assert n["code"] == "spa"

        r4 = client.post(
            f"/api/admin/vocabularies/{vocab_id}/normalize",
            json={"value": "Klingon"},
            headers=admin_headers,
        )
        assert r4.json()["found"] is False

        r5 = client.delete(f"/api/admin/vocabularies/{vocab_id}/values/{value['id']}", headers=admin_headers)
        assert r5.status_code == 204
    finally:
        client.delete(f"/api/admin/vocabularies/{vocab_id}", headers=admin_headers)


def test_vocabulario_import_csv(client, admin_headers):
    r = client.post(
        "/api/admin/vocabularies",
        json={"name": "Lenguas CSV", "code": f"{CODE}-csv"},
        headers=admin_headers,
    )
    vocab_id = r.json()["id"]
    try:
        csv_content = b"code,label,synonyms\nspa,Espa\xc3\xb1ol,Castellano|Spanish\neng,Ingles\npor,Portugues\n"
        r = client.post(
            f"/api/admin/vocabularies/{vocab_id}/import",
            files={"file": ("lenguas.csv", csv_content, "text/csv")},
            headers=admin_headers,
        )
        assert r.status_code == 200, r.text
        result = r.json()
        assert result["added"] == 3
        assert result["total"] == 3

        r2 = client.get(f"/api/admin/vocabularies/{vocab_id}/values", headers=admin_headers)
        assert len(r2.json()) == 3

        # idempotente: re-importar no duplica
        r3 = client.post(
            f"/api/admin/vocabularies/{vocab_id}/import",
            files={"file": ("lenguas.csv", csv_content, "text/csv")},
            headers=admin_headers,
        )
        assert r3.json()["added"] == 0
    finally:
        client.delete(f"/api/admin/vocabularies/{vocab_id}", headers=admin_headers)


# --- tipos documentales -------------------------------------------------------

def test_tipo_documental_crud(client, admin_headers):
    r = client.post(
        "/api/admin/document-types",
        json={"name": "Tesis", "code": f"{CODE}-tesis", "description": "Tesis de grado"},
        headers=admin_headers,
    )
    assert r.status_code == 201, r.text
    type_id = r.json()["id"]

    r2 = client.get("/api/admin/document-types", headers=admin_headers)
    assert any(t["id"] == type_id for t in r2.json())

    r3 = client.put(f"/api/admin/document-types/{type_id}", json={"name": "Tesis academica"}, headers=admin_headers)
    assert r3.status_code == 200
    assert r3.json()["name"] == "Tesis academica"

    r4 = client.delete(f"/api/admin/document-types/{type_id}", headers=admin_headers)
    assert r4.status_code == 204


def test_tipo_documental_duplicado_409(client, admin_headers):
    r = client.post(
        "/api/admin/document-types",
        json={"name": "Tesis", "code": f"{CODE}-tesis"},
        headers=admin_headers,
    )
    type_id = r.json()["id"]
    try:
        r2 = client.post(
            "/api/admin/document-types",
            json={"name": "Otra", "code": f"{CODE}-tesis"},
            headers=admin_headers,
        )
        assert r2.status_code == 409
    finally:
        client.delete(f"/api/admin/document-types/{type_id}", headers=admin_headers)


def test_tipo_documental_asocia_campos_y_agente(client, admin_headers):
    schema = _make_schema()
    db = SessionLocal()
    agent, (provider_id, model_id) = _make_agent()
    try:
        field1 = MetadataField(schema_id=schema.id, element="title", display_name="Titulo")
        field2 = MetadataField(schema_id=schema.id, element="creator", display_name="Autor")
        db.add_all([field1, field2])
        db.commit()

        r = client.post(
            "/api/admin/document-types",
            json={"name": "Tesis", "code": f"{CODE}-tesis", "default_agent_id": str(agent.id)},
            headers=admin_headers,
        )
        type_id = r.json()["id"]
        try:
            r2 = client.put(
                f"/api/admin/document-types/{type_id}/fields",
                json={
                    "fields": [
                        {"field_id": str(field1.id), "order_index": 1, "required_override": True},
                        {"field_id": str(field2.id), "order_index": 2},
                    ]
                },
                headers=admin_headers,
            )
            assert r2.status_code == 200, r2.text
            data = r2.json()
            assert data["default_agent_code"] == agent.code
            field_codes = [f["element"] for f in data["fields"]]
            assert field_codes == ["title", "creator"]
            assert data["fields"][0]["required_override"] is True

            r3 = client.get(f"/api/admin/document-types/{type_id}", headers=admin_headers)
            assert len(r3.json()["fields"]) == 2
        finally:
            client.delete(f"/api/admin/document-types/{type_id}", headers=admin_headers)
    finally:
        db.close()
        _cleanup_type_and_agent(agent_id=agent.id, provider_id=provider_id, model_id=model_id)
        _delete_schema(schema.id)


def test_tipo_documental_agente_inexistente_404(client, admin_headers):
    r = client.post(
        "/api/admin/document-types",
        json={"name": "X", "code": f"{CODE}-x", "default_agent_id": str(uuid.uuid4())},
        headers=admin_headers,
    )
    assert r.status_code in (404, 422)