"""Tests de normalizacion de metadatos (FASE 10).

Reglas deterministas: vocabularios con sinonimos, fechas ISO, DOI/ORCID,
nombres, espacios y mayusculas. La extraccion con IA queda intacta; la
normalizacion NUNCA depende del LLM.
"""

import json
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core import storage
from app.core.database import SessionLocal
from app.extraction import engine
from app.jobs.tasks import extract_metadata, normalize_metadata
from app.main import create_app
from app.models import MetadataField, MetadataRecord, ProcessingJob, VocabularyValue
from app.normalization import engine as norm_engine
from test_extraction import _text_pdf


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
def stack(client, admin_headers):
    st = NormStack(client, admin_headers)
    yield st
    st.cleanup()


@pytest.fixture(autouse=True)
def _local_storage(tmp_path_factory, monkeypatch):
    path = tmp_path_factory.mktemp("storage-norm")
    monkeypatch.setattr(storage.settings, "storage_backend", "filesystem")
    monkeypatch.setattr(storage.settings, "local_storage_path", str(path))
    storage.ensure_bucket()
    yield path


@pytest.fixture
def _fake_call_model(monkeypatch):
    fake = lambda *a, **k: dict(FAKE_RESPONSE)  # noqa: E731
    monkeypatch.setattr(engine, "call_model", fake)
    return fake


@pytest.fixture
def _no_auto_normalize(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "auto_normalize", False)


@pytest.fixture(autouse=True)
def _no_broker(monkeypatch):
    """Desactiva el broker real: los tests ejecutan las tareas en proceso."""
    for mod in ("app.pdf.router", "app.extraction.router", "app.jobs.tasks", "app.normalization.router"):
        monkeypatch.setattr(f"{mod}.celery_app.send_task", lambda name, args=None, **kw: None)
    return None


@pytest.fixture
def _fake_send_task(monkeypatch):
    calls = []

    def fake_send_task(name, args=None, **kw):
        calls.append((name, args))

    monkeypatch.setattr("app.normalization.router.celery_app.send_task", fake_send_task)
    return calls


FAKE_RESPONSE = {
    "content": json.dumps(
        {
            "fields": {
                "creator": "juan  perez",
                "date": "10/05/2023",
                "language": "Spanish",
            }
        }
    ),
    "input_tokens": 90,
    "output_tokens": 40,
    "time_ms": 500.0,
}


class NormStack:
    """Esquema + vocabulario de idiomas + tipo + proveedor/modelo/agente via API."""

    def __init__(self, client, admin_headers, ai_base_url: str = "http://mock-ai/v1"):
        self.client = client
        self.headers = admin_headers
        self.ids: list[str] = []
        uniq = uuid.uuid4().hex[:8]

        r = client.post(
            "/api/admin/metadata/schemas",
            headers=admin_headers,
            json={"name": f"Esquema {uniq}", "code": f"nrm-sd-{uniq}", "namespace": f"nrm-{uniq}"},
        )
        assert r.status_code == 201, r.text
        self.schema_id = r.json()["id"]

        r = client.post(
            "/api/admin/vocabularies",
            headers=admin_headers,
            json={"name": "Idiomas", "code": f"idiomas-{uniq}", "source": "ISO 639-2"},
        )
        assert r.status_code == 201, r.text
        self.vocab_id = r.json()["id"]
        self.ids.insert(0, self.vocab_id)
        for code, label, synonyms in [
            ("spa", "Español", ["Spanish", "Castellano"]),
            ("eng", "Inglés", ["English"]),
            ("por", "Portugués", ["Portuguese"]),
        ]:
            r = client.post(
                f"/api/admin/vocabularies/{self.vocab_id}/values",
                headers=admin_headers,
                json={"code": code, "label": label, "normalized_value": code, "synonyms": synonyms},
            )
            assert r.status_code == 201, r.text

        self.field_title = self._field("title", "Titulo", data_type="text")
        self.field_creator = self._field("creator", "Autor", data_type="text")
        self.field_date = self._field("date", "Fecha", data_type="date")
        self.field_language = self._field(
            "language", "Idioma", data_type="text", vocabulary_id=self.vocab_id
        )

        r = client.post(
            "/api/admin/document-types",
            headers=admin_headers,
            json={"name": f"Tesis {uniq}", "code": f"tesis-nrm-{uniq}"},
        )
        assert r.status_code == 201, r.text
        self.type_id = r.json()["id"]
        self.ids.append(self.type_id)
        r = client.put(
            f"/api/admin/document-types/{self.type_id}/fields",
            headers=admin_headers,
            json={
                "fields": [
                    {"field_id": self.field_title},
                    {"field_id": self.field_creator},
                    {"field_id": self.field_date},
                    {"field_id": self.field_language},
                ]
            },
        )
        assert r.status_code == 200, r.text

        r = client.post(
            "/api/admin/ai/providers",
            headers=admin_headers,
            json={
                "name": f"Mock {uniq}",
                "code": f"mock-provider-{uniq}",
                "type": "openai-compatible",
                "base_url": ai_base_url,
                "api_key": "",
            },
        )
        assert r.status_code == 201, r.text
        self.provider_id = r.json()["id"]
        self.provider_code = f"mock-provider-{uniq}"

        r = client.post(
            "/api/admin/ai/models",
            headers=admin_headers,
            json={
                "provider_id": self.provider_id,
                "name": "Mock Model",
                "model_identifier": "mock-model-norm",
                "supports_json": True,
                "max_tokens_default": 2000,
            },
        )
        assert r.status_code == 201, r.text
        self.model_id = r.json()["id"]

        r = client.post(
            "/api/admin/ai/agents",
            headers=admin_headers,
            json={
                "name": f"Agente Tesis {uniq}",
                "code": f"agente-tesis-{uniq}",
                "document_type_id": self.type_id,
                "model_id": self.model_id,
                "system_prompt": "Eres un catalogador experto en SNRD.",
                "extraction_prompt": "Extrae los metadatos.\n{{document_text}}\nResponde solo JSON.",
                "temperature": 0.1,
                "output_schema_json": {
                    "type": "object",
                    "properties": {
                        "creator": {"type": "object"},
                        "date": {"type": "object"},
                        "language": {"type": "object"},
                    },
                    "required": [],
                },
            },
        )
        assert r.status_code == 201, r.text
        self.agent_id = r.json()["id"]
        self.agent_code = f"agente-tesis-{uniq}"

        r = client.put(
            f"/api/admin/document-types/{self.type_id}",
            headers=admin_headers,
            json={"default_agent_id": self.agent_id},
        )
        assert r.status_code == 200, r.text

    def _field(self, element: str, name: str, **kw) -> str:
        body = {
            "schema_id": self.schema_id,
            "element": element,
            "display_name": name,
            "required": False,
            "repeatable": False,
            "ai_extractable": True,
        }
        body.update(kw)
        r = self.client.post("/api/admin/metadata/fields", headers=self.headers, json=body)
        assert r.status_code == 201, r.text
        return r.json()["id"]

    def upload(self, headers) -> dict:
        r = self.client.post(
            "/api/documents",
            headers=headers,
            files={"file": ("tesis.pdf", _text_pdf(), "application/pdf")},
            data={"document_type_id": self.type_id},
        )
        assert r.status_code == 201, r.text
        return r.json()

    def cleanup(self):
        for _id in reversed(self.ids):
            self.client.delete(f"/api/admin/document-types/{_id}", headers=self.headers)
        self.client.delete(f"/api/admin/ai/agents/{self.agent_id}", headers=self.headers)
        self.client.delete(f"/api/admin/ai/models/{self.model_id}", headers=self.headers)
        self.client.delete(f"/api/admin/ai/providers/{self.provider_id}", headers=self.headers)
        r = self.client.delete(f"/api/admin/metadata/schemas/{self.schema_id}", headers=self.headers)
        assert r.status_code == 204, r.text


def _cleanup_doc(doc_id: str, headers, client):
    client.delete(f"/api/documents/{doc_id}", headers=headers)


# ---------------------------------------------------------------------------
# Unit: fechas
# ---------------------------------------------------------------------------


def test_normalize_date_iso_y_formatos_comunes():
    assert norm_engine.normalize_date("2023-05-10") == "2023-05-10"
    assert norm_engine.normalize_date("10/05/2023") == "2023-05-10"
    assert norm_engine.normalize_date("10-05-2023") == "2023-05-10"
    assert norm_engine.normalize_date("10.05.2023") == "2023-05-10"
    assert norm_engine.normalize_date("10 de mayo de 2023") == "2023-05-10"
    assert norm_engine.normalize_date("May 10, 2023") == "2023-05-10"
    assert norm_engine.normalize_date("2023-05") == "2023-05"
    assert norm_engine.normalize_date("2023") == "2023"


def test_normalize_date_invalidas():
    assert norm_engine.normalize_date("31/02/2023") is None
    assert norm_engine.normalize_date("foo bar") is None
    assert norm_engine.normalize_date("") is None
    assert norm_engine.normalize_date(None) is None


# ---------------------------------------------------------------------------
# Unit: identificadores
# ---------------------------------------------------------------------------


def test_normalize_doi():
    assert norm_engine.normalize_doi("doi: 10.1000/xyz123") == "10.1000/xyz123"
    assert (
        norm_engine.normalize_doi("https://doi.org/10.1234/ABC-2023.1")
        == "10.1234/ABC-2023.1"
    )
    assert norm_engine.normalize_doi("10.1000/xyz") == "10.1000/xyz"
    assert norm_engine.normalize_doi("sin doi") is None


def test_normalize_orcid():
    assert norm_engine.normalize_orcid("0000-0002-1825-0097") == "0000-0002-1825-0097"
    assert norm_engine.normalize_orcid("https://orcid.org/0000-0002-1825-0097") == (
        "0000-0002-1825-0097"
    )
    assert norm_engine.normalize_orcid("0000000218250097") == "0000-0002-1825-0097"
    assert norm_engine.normalize_orcid("123") is None


def test_normalize_identifier_prueba_doi_y_orcid():
    assert norm_engine.normalize_identifier("https://doi.org/10.1000/xyz") == "10.1000/xyz"
    assert norm_engine.normalize_identifier("orcid.org/0000-0002-1825-0097") == (
        "0000-0002-1825-0097"
    )
    assert norm_engine.normalize_identifier("nada") is None


# ---------------------------------------------------------------------------
# Unit: nombres
# ---------------------------------------------------------------------------


def test_normalize_name():
    assert norm_engine.normalize_name("juan  perez") == "Juan Perez"
    assert norm_engine.normalize_name("PEREZ, juan") == "Perez, Juan"
    assert norm_engine.normalize_name("de la cruz, maria elena") == "de la Cruz, Maria Elena"
    assert norm_engine.normalize_name("ana garcia; jose martin") == "Ana Garcia; Jose Martin"


# ---------------------------------------------------------------------------
# Unit: vocabularios y reglas por campo
# ---------------------------------------------------------------------------


def _value(code, label, normalized=None, synonyms=()):
    return VocabularyValue(
        code=code,
        label=label,
        normalized_value=normalized or code,
        synonyms_json=list(synonyms),
        active=True,
    )


def test_normalize_vocabulary_sinonimos_idiomas():
    values = [
        _value("spa", "Español", "spa", ["Spanish", "Castellano"]),
        _value("eng", "Inglés", "eng", ["English"]),
    ]
    assert norm_engine.normalize_vocabulary("Spanish", values) == ("spa", "spa")
    assert norm_engine.normalize_vocabulary("Castellano", values) == ("spa", "spa")
    assert norm_engine.normalize_vocabulary("Español", values) == ("spa", "spa")
    assert norm_engine.normalize_vocabulary("English", values) == ("eng", "eng")
    assert norm_engine.normalize_vocabulary("Klingon", values) is None
    assert norm_engine.normalize_vocabulary("", values) is None


def test_normalize_record_value_por_regla():
    campo_lengua = MetadataField(
        element="language", data_type="text", vocabulary_id=None, normalization_type="language"
    )
    res = norm_engine.normalize_record_value(campo_lengua, "español")
    assert res.ok and res.value == "español"

    campo_fecha = MetadataField(
        element="date", data_type="date", vocabulary_id=None, normalization_type=None
    )
    res = norm_engine.normalize_record_value(campo_fecha, "10/05/2023")
    assert res.ok and res.value == "2023-05-10" and res.rule == "date"
    res = norm_engine.normalize_record_value(campo_fecha, "fecha rara")
    assert not res.ok and res.value == "fecha rara"

    campo_doi = MetadataField(element="identifier", normalization_type="identifier")
    res = norm_engine.normalize_record_value(campo_doi, "doi:10.1000/abc")
    assert res.ok and res.value == "10.1000/abc"

    campo_autor = MetadataField(element="creator")
    res = norm_engine.normalize_record_value(campo_autor, "juan  perez")
    assert res.ok and res.value == "Juan Perez" and res.rule == "name"


def test_normalize_record_value_vocabulario_sin_coincidencia_deja_valor():
    campo = MetadataField(
        element="language",
        vocabulary_id=uuid.uuid4(),
        normalization_type=None,
    )
    values = [_value("spa", "Español", "spa", ["Spanish"])]
    res = norm_engine.normalize_record_value(campo, "Klingon", vocab_values=values)
    assert not res.ok and res.value == "Klingon"


# ---------------------------------------------------------------------------
# API + tareas
# ---------------------------------------------------------------------------


def test_request_normalizacion_202_y_job(
    client, stack, catalogador_headers, _fake_call_model, _fake_send_task, _no_auto_normalize
):
    doc = stack.upload(catalogador_headers)
    assert extract_metadata(doc["id"])["status"] == "COMPLETED"
    r = client.post(
        f"/api/documents/{doc['id']}/normalize", headers=catalogador_headers
    )
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["status"] == "QUEUED" and body["job_id"]
    assert any(
        j["job_type"] == "NORMALIZATION" and j["status"] == "PENDING"
        for j in client.get(
            f"/api/documents/{doc['id']}", headers=catalogador_headers
        ).json()["jobs"]
    )
    _cleanup_doc(doc["id"], catalogador_headers, client)


def test_request_normalizacion_404_y_409(client, stack, catalogador_headers):
    r = client.post(
        "/api/documents/00000000-0000-0000-0000-000000000000/normalize",
        headers=catalogador_headers,
    )
    assert r.status_code == 404
    doc = stack.upload(catalogador_headers)
    try:
        r = client.post(f"/api/documents/{doc['id']}/normalize", headers=catalogador_headers)
        assert r.status_code == 409, r.text
    finally:
        _cleanup_doc(doc["id"], catalogador_headers, client)


def test_normalize_metadata_convierte_y_marca(
    client, stack, catalogador_headers, _fake_call_model, _no_auto_normalize
):
    doc = stack.upload(catalogador_headers)
    assert extract_metadata(doc["id"])["status"] == "COMPLETED"
    r = client.get(f"/api/documents/{doc['id']}/metadata", headers=catalogador_headers)
    assert r.status_code == 200, r.text
    records = r.json()["records"]
    assert any(rec["field"] == "creator" and rec["value"] == "juan  perez" for rec in records)
    assert any(rec["field"] == "date" and rec["value"] == "10/05/2023" for rec in records)
    assert any(rec["field"] == "language" and rec["value"] == "Spanish" for rec in records)

    result = normalize_metadata(doc["id"])
    assert result["status"] == "COMPLETED"
    assert result["records"] == 3 and result["changed"] >= 3

    records = client.get(
        f"/api/documents/{doc['id']}/metadata", headers=catalogador_headers
    ).json()["records"]
    by_field = {rec["field"]: rec for rec in records}
    assert by_field["creator"]["value"] == "Juan Perez"
    assert by_field["creator"]["normalized"] is True
    assert by_field["date"]["value"] == "2023-05-10"
    assert by_field["date"]["normalized"] is True
    assert by_field["language"]["value"] == "spa"
    assert by_field["language"]["normalized"] is True

    detail = client.get(
        f"/api/documents/{doc['id']}", headers=catalogador_headers
    ).json()
    assert detail["status"] == "NORMALIZED"
    jobs = {j["job_type"]: j["status"] for j in detail["jobs"]}
    assert jobs.get("EXTRACTION") == "COMPLETED"
    assert jobs.get("NORMALIZATION") == "COMPLETED"

    _cleanup_doc(doc["id"], catalogador_headers, client)


def test_extraccion_encadena_normalizacion_automatica(
    client, stack, catalogador_headers, _fake_call_model
):
    doc = stack.upload(catalogador_headers)
    try:
        result = extract_metadata(doc["id"])
        assert result["status"] == "COMPLETED"
        metadata = client.get(
            f"/api/documents/{doc['id']}/metadata", headers=catalogador_headers
        ).json()
        by_field = {rec["field"]: rec for rec in metadata["records"]}
        assert by_field["creator"]["value"] == "Juan Perez"
        assert by_field["date"]["value"] == "2023-05-10"
        assert by_field["language"]["value"] == "spa"
        # El FAKE no devuelve title -> SNRD lo marca como faltante
        assert client.get(
            f"/api/documents/{doc['id']}", headers=catalogador_headers
        ).json()["status"] == "VALIDATION_FAILED"
    finally:
        _cleanup_doc(doc["id"], catalogador_headers, client)


def test_normalize_metadata_no_rompe_valor_no_normalizable(
    client, stack, catalogador_headers, _no_auto_normalize
):
    doc = stack.upload(catalogador_headers)
    db = SessionLocal()
    try:
        field = db.query(MetadataField).filter_by(id=uuid.UUID(stack.field_date)).one()
        rec = MetadataRecord(
            document_id=uuid.UUID(doc["id"]),
            metadata_field_id=field.id,
            value="fecha desconocida",
            confidence=0.8,
            source="IA",
        )
        db.add(rec)
        db.commit()
        db.refresh(rec)
        rec_id = rec.id
    finally:
        db.close()
    try:
        result = normalize_metadata(doc["id"])
        assert result["status"] == "COMPLETED"
        db = SessionLocal()
        try:
            rec = db.get(MetadataRecord, rec_id)
            assert rec.value == "fecha desconocida"
            assert rec.normalized is False
        finally:
            db.close()
    finally:
        _cleanup_doc(doc["id"], catalogador_headers, client)


def test_normalize_metadata_sin_registros_noop(client, stack, catalogador_headers):
    doc = stack.upload(catalogador_headers)
    try:
        result = normalize_metadata(doc["id"])
        assert result["status"] == "NOOP"
    finally:
        _cleanup_doc(doc["id"], catalogador_headers, client)