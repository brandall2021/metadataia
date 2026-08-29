"""Tests de extraccion de metadatos con IA (FASE 9).

Criterio: una tesis produce metadatos estructurados.
- Seleccion automatica de agente (default del tipo -> del tipo -> generico).
- Prompt con contexto documental + llamada al modelo (OpenAI-compatible).
- Validacion JSON Schema + mapeo a campos con confidence y evidencia.
- ExtractionRun de auditoria + MetadataRecord por campo + raw de evidencia.
La llamada HTTP real al proveedor se simula con httpx.MockTransport y el
motor se mockea a nivel de tarea para resultados deterministas.
"""

import io
import json
import uuid
from datetime import datetime, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core import storage
from app.extraction import engine
from app.extraction.engine import ExtractionError, select_agent
from app.jobs.tasks import extract_metadata
from app.main import create_app
from app.models import (
    AIAgent,
    AIAgentVersion,
    AIModel,
    AIProvider,
    Document,
    DocumentType,
    ExtractionRun,
    MetadataRecord,
    MetadataSchema,
    ProcessingJob,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _text_pdf(text: str = "TITULO DE LA TESIS: Impacto de la IA en bibliotecas") -> bytes:
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        _stream(text),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    unique = b"\n% metadataia-x-" + uuid.uuid4().hex.encode()
    return _build_pdf(objects) + unique


def _stream(text: str) -> bytes:
    content = f"BT /F1 24 Tf 72 720 Td ({text}) Tj ET".encode("latin-1")
    return b"<< /Length %d >>\nstream\n%s\nendstream" % (len(content), content)


def _build_pdf(objects: list[bytes]) -> bytes:
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode()
        out += obj + b"\nendobj\n"
    xref_pos = len(out)
    out += b"xref\n0 6\n"
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode()
    )
    return bytes(out)


class AIStack:
    """Proveedor + modelo + agente + esquema + tipo documental creados via API."""

    def __init__(self, client, admin_headers):
        self.client = client
        self.headers = admin_headers
        self.ids: list[str] = []
        uniq = uuid.uuid4().hex[:8]

        r = client.post(
            "/api/admin/metadata/schemas",
            headers=admin_headers,
            json={"name": f"Esquema {uniq}", "code": f"test-sd-{uniq}", "namespace": f"test-{uniq}"},
        )
        assert r.status_code == 201, r.text
        self.schema_id = r.json()["id"]

        self.field_title = self._field("title", "Titulo")
        self.field_creator = self._field("creator", "Autor")

        r = client.post(
            "/api/admin/document-types",
            headers=admin_headers,
            json={"name": f"Tesis {uniq}", "code": f"tesis-{uniq}"},
        )
        assert r.status_code == 201, r.text
        self.type_id = r.json()["id"]
        self.ids.append(self.type_id)
        r = client.put(
            f"/api/admin/document-types/{self.type_id}/fields",
            headers=admin_headers,
            json={"fields": [{"field_id": self.field_title}, {"field_id": self.field_creator}]},
        )
        assert r.status_code == 200, r.text

        r = client.post(
            "/api/admin/ai/providers",
            headers=admin_headers,
            json={
                "name": f"Mock {uniq}",
                "code": f"mock-provider-{uniq}",
                "type": "openai-compatible",
                "base_url": "http://mock-ai/v1",
                "api_key": "",
                "active": True,
            },
        )
        assert r.status_code == 201, r.text
        self.provider_id = r.json()["id"]

        r = client.post(
            "/api/admin/ai/models",
            headers=admin_headers,
            json={
                "provider_id": self.provider_id,
                "name": "Mock Model",
                "model_identifier": "mock-model-v1",
                "supports_json": True,
                "max_tokens_default": 2000,
                "active": True,
            },
        )
        assert r.status_code == 201, r.text
        self.model_id = r.json()["id"]

        self.output_schema = {
            "type": "object",
            "properties": {
                "title": {"type": "object"},
                "creator": {"type": "object"},
            },
            "required": [],
        }
        r = client.post(
            "/api/admin/ai/agents",
            headers=admin_headers,
            json={
                "name": f"Agente Tesis {uniq}",
                "code": f"agente-tesis-{uniq}",
                "document_type_id": self.type_id,
                "model_id": self.model_id,
                "system_prompt": "Eres un catalogador experto en SNRD.",
                "extraction_prompt": (
                    "Extrae los metadatos del documento.\n"
                    "Tipo documental: {{document_type}}\n"
                    "Esquema: {{metadata_schema}}\n"
                    "Campos disponibles:\n{{metadata_fields}}\n"
                    "Texto:\n{{document_text}}\n"
                    'Responde solo JSON: {"fields": {"nombre-campo": {"value": "...", "confidence": 0.0-1.0, "source_page": N, "source_text": "..."}}}'
                ),
                "temperature": 0.1,
                "max_tokens": 1500,
                "output_schema_json": self.output_schema,
                "active": True,
            },
        )
        assert r.status_code == 201, r.text
        self.agent_id = r.json()["id"]

        r = client.put(
            f"/api/admin/document-types/{self.type_id}",
            headers=admin_headers,
            json={"default_agent_id": self.agent_id},
        )
        assert r.status_code == 200, r.text

    def _field(self, element: str, name: str) -> str:
        r = self.client.post(
            "/api/admin/metadata/fields",
            headers=self.headers,
            json={
                "schema_id": self.schema_id,
                "element": element,
                "display_name": name,
                "required": False,
                "repeatable": False,
                "ai_extractable": True,
                "order_index": 1 if element == "title" else 2,
            },
        )
        assert r.status_code == 201, r.text
        return r.json()["id"]

    def upload_tesis(self, headers, filename="tesis.pdf", text=None) -> dict:
        r = self.client.post(
            "/api/documents",
            headers=headers,
            files={"file": (filename, _text_pdf(text) if text else _text_pdf(), "application/pdf")},
            data={"document_type_id": self.type_id},
        )
        assert r.status_code == 201, r.text
        return r.json()

    def cleanup(self, meta_headers):
        for _id in reversed(self.ids):
            self.client.delete(f"/api/admin/document-types/{_id}", headers=self.headers)
        r = self.client.delete(f"/api/admin/ai/agents/{self.agent_id}", headers=self.headers)
        assert r.status_code == 204, r.text
        r = self.client.delete(f"/api/admin/ai/models/{self.model_id}", headers=self.headers)
        assert r.status_code == 204, r.text
        r = self.client.delete(f"/api/admin/ai/providers/{self.provider_id}", headers=self.headers)
        assert r.status_code == 204, r.text
        r = self.client.delete(f"/api/admin/metadata/schemas/{self.schema_id}", headers=self.headers)
        assert r.status_code == 204, r.text


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
def stack(client, admin_headers):
    st = AIStack(client, admin_headers)
    yield st
    st.cleanup(admin_headers)


@pytest.fixture(autouse=True)
def _local_storage(tmp_path_factory, monkeypatch):
    path = tmp_path_factory.mktemp("storage")
    monkeypatch.setattr(storage.settings, "storage_backend", "filesystem")
    monkeypatch.setattr(storage.settings, "local_storage_path", str(path))
    storage.ensure_bucket()
    yield path


@pytest.fixture(autouse=True)
def _fake_send_task(monkeypatch):
    calls = []

    def fake_send(task, args=None, **kwargs):
        calls.append((task, args))

    from app.jobs.celery_app import celery_app as app
    from app.pdf import router as pdf_router

    monkeypatch.setattr(app, "send_task", fake_send)
    monkeypatch.setattr(pdf_router.celery_app, "send_task", fake_send)
    yield calls


FAKE_RESPONSE = {
    "content": json.dumps(
        {
            "fields": {
                "title": {
                    "value": "Impacto de la IA en repositorios",
                    "confidence": 0.95,
                    "source_page": 1,
                    "source_text": "TITULO DE LA TESIS: Impacto de la IA en bibliotecas",
                },
                "creator": "Juan Perez",
            }
        }
    ),
    "input_tokens": 120,
    "output_tokens": 60,
    "time_ms": 780.5,
}


@pytest.fixture()
def _fake_call_model(monkeypatch):
    monkeypatch.setattr(engine, "call_model", lambda *a, **k: dict(FAKE_RESPONSE))
    yield


def _cleanup_doc(doc_id, headers, client):
    client.delete(f"/api/documents/{doc_id}", headers=headers)


# ---------------------------------------------------------------------------
# Unidades del motor
# ---------------------------------------------------------------------------


def test_call_model_envia_body_json_y_soporta_response_format():
    provider = AIProvider(
        name="Mock", code=f"p-{uuid.uuid4().hex[:6]}", type="openai-compatible",
        base_url="http://mock-ai/v1", api_key_encrypted=None,
    )
    captured: dict = {}
    recorded: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200, json={"choices": [{"message": {"content": '{"ok": true}'}}],
                       "usage": {"prompt_tokens": 10, "completion_tokens": 5}}
        )

    result = engine.call_model(
        provider,
        "mock-model-v1",
        "system prompt",
        "user prompt {{var}}",
        supports_json=True,
        transport=httpx.MockTransport(handler),
    )
    assert captured["url"].endswith("/chat/completions")
    body = captured["body"]
    assert body["model"] == "mock-model-v1"
    assert body["response_format"] == {"type": "json_object"}
    assert body["messages"][0]["role"] == "system"
    assert body["messages"][1]["content"] == "user prompt {{var}}"
    assert result["content"] == '{"ok": true}'
    assert result["input_tokens"] == 10
    assert result["output_tokens"] == 5


def test_call_model_error_http_levanta_extraction_error():
    provider = AIProvider(
        name="Mock", code=f"p-{uuid.uuid4().hex[:6]}", type="openai-compatible",
        base_url="http://mock-ai/v1", api_key_encrypted=None,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="rate limited")

    with pytest.raises(ExtractionError):
        engine.call_model(
            provider, "m", "s", "u", transport=httpx.MockTransport(handler)
        )


def test_parse_content_tolerante_a_fences_y_json_plano():
    data = engine.parse_content('```json\n{"fields": {"title": "x"}}\n```')
    assert data == {"fields": {"title": "x"}}
    data2 = engine.parse_content('texto previo {"a": 1} mas texto')
    assert data2 == {"a": 1}
    with pytest.raises(ExtractionError):
        engine.parse_content("nada de json")


def test_validate_schema_required_y_tipos():
    schema = {
        "type": "object",
        "properties": {"title": {"type": "string"}, "pages": {"type": "integer"}},
        "required": ["title"],
    }
    assert engine.validate_schema({"title": "ok", "pages": 3}, schema) == []
    errs = engine.validate_schema({"pages": "no"}, schema)
    assert any("title" in e for e in errs)
    assert any("pages" in e for e in errs)


def test_parse_fields_mapa_valor_confidence_y_evidencia():
    field_defs = [
        {"id": "f1", "element": "title", "qualifier": None, "required": False, "repeatable": False},
        {"id": "f2", "element": "creator", "qualifier": None, "required": False, "repeatable": False},
    ]
    data = {
        "fields": {
            "title": {"value": "Impacto", "confidence": 0.9, "source_page": 1, "source_text": "abc"},
            "creator": "Juan Perez",
        }
    }
    recs = engine.parse_fields(data, field_defs)
    assert len(recs) == 2
    t = next(r for r in recs if r["metadata_field_id"] == "f1")
    assert t["value"] == "Impacto"
    assert t["confidence"] == 0.9
    assert t["source_page"] == 1
    assert t["source_text"] == "abc"
    c = next(r for r in recs if r["metadata_field_id"] == "f2")
    assert c["confidence"] == engine.DEFAULT_CONFIDENCE


# ---------------------------------------------------------------------------
# Seleccion de agente
# ---------------------------------------------------------------------------


def test_select_agent_prioriza_default_del_tipo(client, admin_headers):
    uniq = uuid.uuid4().hex[:6]

    def _agent(code, doc_type_id):
        r = client.post(
            "/api/admin/ai/agents",
            headers=admin_headers,
            json={"name": code, "code": code, "model_id": "00000000-0000-0000-0000-000000000001"},
        )
        return r

    # Construimos el escenario directo en DB (evita el validador del admin)
    from app.core.database import SessionLocal

    db = SessionLocal()
    provider = AIProvider(name="Mock", code=f"inst-{uniq}", type="openai-compatible")
    db.add(provider)
    db.flush()
    model = AIModel(
        provider_id=provider.id, name="m", model_identifier="m1",
        supports_json=True, max_tokens_default=1000,
    )
    db.add(model)
    db.flush()

    general = AIAgent(name="General", code=f"gen-{uniq}", active=True, document_type_id=None)
    dt = DocumentType(name="Tesis", code=f"dt-{uniq}", active=True)
    db.add_all([general, dt])
    db.flush()
    vg = AIAgentVersion(agent_id=general.id, version_number=1, model_id=model.id, extraction_prompt="x")
    db.add(vg)
    db.flush()
    general.current_version_id = vg.id
    db.commit()

    try:
        # 1. solo agente general -> se usa
        assert select_agent(dt, db) is not None

        # 2. agente especifico del tipo gana al general
        specific = AIAgent(name="Spec", code=f"spec-{uniq}", active=True, document_type_id=dt.id)
        db.add(specific)
        db.flush()
        vs = AIAgentVersion(agent_id=specific.id, version_number=1, model_id=model.id, extraction_prompt="x")
        db.add(vs)
        db.flush()
        specific.current_version_id = vs.id
        db.commit()
        assert select_agent(dt, db) is specific

        # 3. el default del tipo gana a todos
        dt.default_agent_id = general.id
        db.commit()
        assert select_agent(dt, db) is general
    finally:
        db.delete(dt)
        db.delete(specific)
        db.delete(general)
        db.flush()
        db.delete(model)
        db.delete(provider)
        db.commit()
        db.close()


# ---------------------------------------------------------------------------
# Pipeline completo (tarea + API)
# ---------------------------------------------------------------------------


def test_extraccion_completa_produce_metadatos(
    client, stack, catalogador_headers, admin_headers, _fake_call_model
):
    doc = stack.upload_tesis(catalogador_headers)
    try:
        result = extract_metadata(doc["id"])
        assert result["status"] == "COMPLETED", result
        assert result["records"] == 2
        assert result["agent"].startswith("agente-tesis-")
        assert result["model"] == "mock-model-v1"

        r = client.get(f"/api/documents/{doc['id']}", headers=catalogador_headers)
        detail = r.json()
        assert detail["status"] == "NORMALIZED"

        r = client.get(f"/api/documents/{doc['id']}/metadata", headers=catalogador_headers)
        meta = r.json()
        assert meta["document_status"] == "NORMALIZED"
        assert len(meta["records"]) == 2
        title = next(rec for rec in meta["records"] if rec["field"] == "title")
        assert title["value"] == "Impacto de la IA en repositorios"
        assert title["confidence"] == 0.95
        assert title["source"] == "IA"
        assert title["source_page"] == 1
        assert "TITULO DE LA TESIS" in (title["source_text"] or "")
        creator = next(rec for rec in meta["records"] if rec["field"] == "creator")
        assert creator["value"] == "Juan Perez"
        assert creator["source_page"] is None

        run = meta["runs"][0]
        assert run["status"] == "COMPLETED"
        assert len(run["prompt_hash"]) == 64
        assert run["input_tokens"] == 120
        assert run["output_tokens"] == 60
        assert run["raw_response_storage_path"] is not None
        assert storage.object_exists(run["raw_response_storage_path"])

        # evidencia guardada en storage
        from app.core.storage import download_original

        raw = json.loads(download_original(run["raw_response_storage_path"]))
        assert raw["response"]["fields"]["title"]["value"] == "Impacto de la IA en repositorios"
        assert raw["prompt_hash"] == run["prompt_hash"]

        # el borrado limpia la evidencia
        r = client.delete(f"/api/documents/{doc['id']}", headers=catalogador_headers)
        assert r.status_code == 204
        assert storage.object_exists(run["raw_response_storage_path"]) is False
        return

    finally:
        r = client.get(f"/api/documents/{doc['id']}", headers=catalogador_headers)
        if r.status_code == 200:
            _cleanup_doc(doc["id"], catalogador_headers, client)


def test_extraccion_error_registra_run_y_restaura_estado(client, stack, catalogador_headers, monkeypatch):
    doc = stack.upload_tesis(catalogador_headers)
    try:
        def _fail(*a, **k):
            raise ExtractionError("servicio de IA caido (HTTP 503)")

        monkeypatch.setattr(engine, "call_model", _fail)
        result = extract_metadata(doc["id"])
        assert result["status"] == "ERROR"
        assert "503" in result["error"]

        r = client.get(f"/api/documents/{doc['id']}/metadata", headers=catalogador_headers)
        meta = r.json()
        assert meta["document_status"] == "UPLOADED"
        run = meta["runs"][0]
        assert run["status"] == "ERROR"
        assert "503" in (run["error_message"] or "")
        assert len(meta["records"]) == 0
    finally:
        _cleanup_doc(doc["id"], catalogador_headers, client)


def test_extraccion_sin_agente_error(client, catalogador_headers, admin_headers, monkeypatch, _fake_call_model):
    # tipo documental sin agente asignado y sin agente generico -> ERROR
    uniq = uuid.uuid4().hex[:6]
    r = client.post(
        "/api/admin/document-types",
        headers=admin_headers,
        json={"name": f"Tipo sin agente {uniq}", "code": f"sin-agente-{uniq}"},
    )
    assert r.status_code == 201, r.text
    tipo = r.json()["id"]
    try:
        r = client.post(
            "/api/documents",
            headers=catalogador_headers,
            files={"file": ("sueltos.pdf", _text_pdf(), "application/pdf")},
            data={"document_type_id": tipo},
        )
        assert r.status_code == 201, r.text
        doc = r.json()
        try:
            result = extract_metadata(doc["id"])
            assert result["status"] == "ERROR"
            assert "agente" in result["error"]
        finally:
            _cleanup_doc(doc["id"], catalogador_headers, client)
    finally:
        client.delete(f"/api/admin/document-types/{tipo}", headers=admin_headers)


def test_request_extraccion_encola_202(client, stack, catalogador_headers, _fake_send_task):
    doc = stack.upload_tesis(catalogador_headers)
    try:
        r = client.post(f"/api/documents/{doc['id']}/extract", headers=catalogador_headers)
        assert r.status_code == 202, r.text
        data = r.json()
        assert data["status"] == "QUEUED"
        assert data["document_id"] == doc["id"]
        assert any(task == "app.jobs.tasks.extract_metadata" for task, _ in _fake_send_task)
    finally:
        _cleanup_doc(doc["id"], catalogador_headers, client)


def test_request_extraccion_documento_escaneado_409(client, stack, catalogador_headers):
    # documento needs_ocr -> 409
    from test_ocr import _blank_pdf

    r = client.post(
        "/api/documents",
        headers=catalogador_headers,
        files={"file": ("scan.pdf", _blank_pdf(1), "application/pdf")},
        data={"document_type_id": stack.type_id},
    )
    assert r.status_code == 201, r.text
    doc = r.json()
    assert doc["needs_ocr"] is True
    try:
        r = client.post(f"/api/documents/{doc['id']}/extract", headers=catalogador_headers)
        assert r.status_code == 409
    finally:
        _cleanup_doc(doc["id"], catalogador_headers, client)


def test_extraccion_404(client, stack, catalogador_headers):
    r = client.post(f"/api/documents/{uuid.uuid4()}/extract", headers=catalogador_headers)
    assert r.status_code == 404


def test_auto_extraccion_al_subir_con_texto(client, stack, catalogador_headers, _fake_send_task, monkeypatch):
    monkeypatch.setattr(storage.settings, "auto_ai", True)
    doc = stack.upload_tesis(catalogador_headers)
    try:
        assert any(
            task == "app.jobs.tasks.extract_metadata" and args == [doc["id"]]
            for task, args in _fake_send_task
        )
    finally:
        _cleanup_doc(doc["id"], catalogador_headers, client)