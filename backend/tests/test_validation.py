"""Tests de validacion de metadatos (FASE 11).

El motor de validacion ejecuta reglas deterministas por campo
(obligatorios, formatos, vocabularios, longitudes) y el modulo SNRD
verifica el perfil de interoperabilidad. Criterio: el sistema identifica
registros incompletos o invalidos (errores) y avisa de dudas (warnings).
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
from app.models import MetadataField, ValidationResult, VocabularyValue
from app.normalization import engine as norm_engine
from app.snrd.validator import validate_snrd
from app.validation import engine as vengine
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
def stack(client, admin_headers):
    st = NormStack(client, admin_headers)
    yield st
    st.cleanup()


@pytest.fixture(autouse=True)
def _local_storage(tmp_path_factory, monkeypatch):
    path = tmp_path_factory.mktemp("storage-val")
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


FAKE_RESPONSE = {
    "content": json.dumps(
        {
            "fields": {
                "title": {"value": "Impacto de la IA en repositorios", "confidence": 0.98},
                "creator": {"value": "juan  perez", "confidence": 0.95},
                "date": {"value": "10/05/2023", "confidence": 0.92},
                "language": {"value": "Spanish", "confidence": 0.99},
            }
        }
    ),
    "input_tokens": 90,
    "output_tokens": 40,
    "time_ms": 500.0,
}


@pytest.fixture
def _fake_call_model(monkeypatch):
    fake = lambda *a, **k: dict(FAKE_RESPONSE)  # noqa: E731
    monkeypatch.setattr(engine, "call_model", fake)
    return fake


def _custom_fake(monkeypatch, fields):
    monkeypatch.setattr(
        engine,
        "call_model",
        lambda *a, **k: {
            "content": json.dumps({"fields": fields}),
            "input_tokens": 1,
            "output_tokens": 1,
            "time_ms": 1.0,
        },
    )


def _cleanup_doc(doc_id: str, headers, client):
    client.delete(f"/api/documents/{doc_id}", headers=headers)


# ---------------------------------------------------------------------------
# Unit: motor de validacion (reglas por campo)
# ---------------------------------------------------------------------------


def _f(element="title", **kw):
    return MetadataField(
        element=element,
        qualifier=kw.get("qualifier"),
        display_name=kw.get("display_name", element),
        data_type=kw.get("data_type", "text"),
        validation_type=kw.get("validation_type"),
        required=kw.get("required", False),
        vocabulary_id=kw.get("vocabulary_id"),
    )


def test_required_vacio_genera_error():
    errs = vengine.check_value(_f("title", required=True), "   ")
    assert errs and errs[0]["code"] == "required"
    assert vengine.check_value(_f("title", required=True), "Un titulo") == []


def test_required_sin_registro_genera_error():
    f = _f("rights", required=True)
    errs = vengine.missing_required([f], [])
    assert errs and errs[0]["code"] == "required"
    assert errs[0]["field"] == "rights"
    assert vengine.missing_required([_f("rights", required=False)], []) == []


def test_formatos_invalidos():
    assert vengine.check_value(_f("email", validation_type="email"), "no-es-un-correo")[0]["code"] == "invalid_email"
    assert vengine.check_value(_f("email", validation_type="email"), "a@b.com") == []
    assert vengine.check_value(_f("url", validation_type="url"), "hola")[0]["code"] == "invalid_url"
    assert vengine.check_value(_f("url", validation_type="url"), "https://example.org/x") == []
    assert vengine.check_value(_f("date", validation_type="date"), "no-es-fecha")[0]["code"] == "invalid_date"
    assert vengine.check_value(_f("date", validation_type="date"), "2023-05-10") == []
    assert vengine.check_value(_f("page_count", validation_type="integer"), "abc")[0]["code"] == "invalid_integer"
    assert vengine.check_value(_f("page_count", validation_type="integer"), "12") == []
    assert vengine.check_value(_f("weight", validation_type="float"), "abc")[0]["code"] == "invalid_float"
    assert vengine.check_value(_f("weight", validation_type="float"), "1.5") == []


def test_longitudes_y_regex():
    f = _f("abstract", validation_type="min_length:10")
    assert vengine.check_value(f, "corto")[0]["code"] == "min_length"
    assert vengine.check_value(f, "suficientemente largo") == []
    f = _f("code", validation_type="regex:^[A-Z]{2}-\\d{4}$")
    assert vengine.check_value(f, "AB-123")[0]["code"] == "regex"
    assert vengine.check_value(f, "AB-1234") == []


def test_identificadores():
    f = _f("identifier", validation_type="identifier")
    assert vengine.check_value(f, "doi:10.1000/abc") == []
    assert vengine.check_value(f, "0000-0002-1825-0097") == []
    assert vengine.check_value(f, "texto libre")[0]["code"] == "invalid_identifier"
    f = _f("issn", validation_type="issn")
    assert vengine.check_value(f, "1234-5678") == []


def test_vocabulario_valida():
    values = [
        VocabularyValue(
            code="spa", label="Español", normalized_value="spa", synonyms_json=["Spanish"], active=True
        )
    ]
    f = _f("language", vocabulary_id=uuid.uuid4())
    assert vengine.check_value(f, "Spanish", vocab_values=values) == []
    assert vengine.check_value(f, "Klingon", vocab_values=values)[0]["code"] == "vocabulary"


def test_warning_confianza_baja():
    out = vengine.validate_records(
        [_Rec(_f("creator"), "Juan", 0.4), _Rec(_f("title", required=True), "T", 0.99)]
    )
    assert any(w["code"] == "low_confidence" for w in out.warnings)
    assert out.errors == []


def test_validate_records_agrega_errores():
    out = vengine.validate_records([_Rec(_f("title", required=True), " ", 1.0)])
    assert out.errors and out.errors[0]["code"] == "required"
    assert out.errors[0]["field"] == "title"


# ---------------------------------------------------------------------------
# Unit: SNRD
# ---------------------------------------------------------------------------


def test_snrd_faltantes_y_fecha_no_iso():
    recs = [_Rec(_f("date"), "fecha rara", 0.9)]
    errors, warnings = validate_snrd(recs)
    codes = {e["code"] for e in errors}
    assert "missing_required" in codes  # title faltante
    assert "invalid_date" in codes
    assert any(w["code"] == "language_missing" for w in warnings)


def test_snrd_ok():
    recs = [
        _Rec(_f("title"), "Titulo", 0.9),
        _Rec(_f("date"), "2023-05-10", 0.9),
        _Rec(_f("language"), "spa", 0.9),
    ]
    errors, warnings = validate_snrd(recs)
    assert errors == []
    assert warnings == []


# ---------------------------------------------------------------------------
# API + tareas
# ---------------------------------------------------------------------------


def test_request_validate_202_y_get_validation(
    client, stack, catalogador_headers, _fake_call_model, _no_auto_chain
):
    doc = stack.upload(catalogador_headers)
    assert extract_metadata(doc["id"])["status"] == "COMPLETED"
    r = client.post(f"/api/documents/{doc['id']}/validate", headers=catalogador_headers)
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["status"] == "QUEUED" and body["job_id"]

    result = validate_metadata(doc["id"])
    assert result["status"] == "COMPLETED" and result["valid"] is True

    r = client.get(f"/api/documents/{doc['id']}/validation", headers=catalogador_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["document_status"] == "VALIDATED"
    types = {res["validator_type"] for res in data["results"]}
    assert types == {"METADATA", "SNRD"}
    for res in data["results"]:
        assert res["status"] == "COMPLETED"
        assert res["errors_json"] in ([], None)
        assert res["warnings_json"] in ([], None)

    _cleanup_doc(doc["id"], catalogador_headers, client)


def test_request_validate_404_y_409(client, stack, catalogador_headers):
    r = client.post(
        "/api/documents/00000000-0000-0000-0000-000000000000/validate",
        headers=catalogador_headers,
    )
    assert r.status_code == 404
    doc = stack.upload(catalogador_headers)
    r = client.post(f"/api/documents/{doc['id']}/validate", headers=catalogador_headers)
    assert r.status_code == 409, r.text
    _cleanup_doc(doc["id"], catalogador_headers, client)


def test_validate_metadata_identifica_incompleto(
    client, stack, catalogador_headers, monkeypatch, _no_auto_chain
):
    _custom_fake(monkeypatch, {"creator": "Juan", "date": "2023-05-10"})  # sin title ni language
    doc = stack.upload(catalogador_headers)
    assert extract_metadata(doc["id"])["status"] == "COMPLETED"

    result = validate_metadata(doc["id"])
    assert result["status"] == "COMPLETED" and result["valid"] is False
    assert result["errors"] >= 1

    data = client.get(
        f"/api/documents/{doc['id']}/validation", headers=catalogador_headers
    ).json()
    assert data["document_status"] == "VALIDATION_FAILED"
    snrd = next(r for r in data["results"] if r["validator_type"] == "SNRD")
    codes = {e["code"] for e in snrd["errors_json"]}
    assert "missing_required" in codes
    _cleanup_doc(doc["id"], catalogador_headers, client)


def test_extraccion_encadena_validacion_automatica(
    client, stack, catalogador_headers, _fake_call_model
):
    doc = stack.upload(catalogador_headers)
    assert extract_metadata(doc["id"])["status"] == "COMPLETED"
    detail = client.get(f"/api/documents/{doc['id']}", headers=catalogador_headers).json()
    assert detail["status"] == "VALIDATED"
    jobs = {j["job_type"]: j["status"] for j in detail["jobs"]}
    assert jobs.get("VALIDATION") == "COMPLETED"
    data = client.get(
        f"/api/documents/{doc['id']}/validation", headers=catalogador_headers
    ).json()
    assert len(data["results"]) == 2
    _cleanup_doc(doc["id"], catalogador_headers, client)


class _Rec:
    """MetadataRecord simplificado para pruebas unitarias del motor."""

    def __init__(self, field, value, confidence):
        self.metadata_field = field
        self.value = value
        self.confidence = confidence