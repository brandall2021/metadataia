"""Tests de OCR (FASE 8).

Criterio: un PDF escaneado queda procesable mediante texto.
El OCR real (ocrmypdf+tesseract) se mockea en los tests; la logica del
pipeline (encolado, ejecucion de la tarea, actualizacion de paginas, jobs,
errores) se prueba de forma determinista.
"""

import io
import uuid

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from app.core import storage
from app.jobs.tasks import run_ocr
from app.main import create_app
from app.models import Document, DocumentPage, ProcessingJob
from app.ocr import engine
from app.core.database import SessionLocal


@pytest.fixture(autouse=True)
def _local_storage(tmp_path_factory, monkeypatch):
    path = tmp_path_factory.mktemp("storage")
    monkeypatch.setattr(storage.settings, "storage_backend", "filesystem")
    monkeypatch.setattr(storage.settings, "local_storage_path", str(path))
    storage.ensure_bucket()
    yield path


@pytest.fixture(autouse=True)
def _no_auto_ocr(monkeypatch):
    monkeypatch.setattr(storage.settings, "auto_ocr", False)


@pytest.fixture(autouse=True)
def _fake_send_task(monkeypatch):
    calls = []

    def fake_send(task, args=None, **kwargs):
        calls.append((task, args))
        return None

    from app.pdf import router as pdf_router

    monkeypatch.setattr(pdf_router.celery_app, "send_task", fake_send)
    yield calls


@pytest.fixture(autouse=True)
def _fake_ocr_engine(monkeypatch):
    monkeypatch.setattr(engine, "perform_ocr", _fake_perform_ocr)
    monkeypatch.setattr(engine, "extract_text_pdf", _fake_extract_text)
    yield


FAKE_SEARCHABLE = b"%PDF-1.4 fake searchable"


def _fake_perform_ocr(pdf_bytes, languages, timeout=600):
    return {
        "pdf": FAKE_SEARCHABLE,
        "meta": {
            "tool": "ocrmypdf",
            "version": "16.7.0",
            "languages": languages,
            "elapsed_seconds": 1.2,
        },
    }


def _fake_extract_text(pdf_bytes):
    return ["TITULO: Impacto de la IA (pagina 1)", "Resumen del trabajo (pagina 2)"]


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_app())


@pytest.fixture(scope="module")
def catalogador_headers(client) -> dict:
    r = client.post("/api/auth/login", json={"username": "catalogador", "password": "metadataia123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _blank_pdf(pages: int = 2) -> bytes:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=612, height=792)
    buf = io.BytesIO()
    writer.write(buf)
    unique = b"\n% metadataia-unique-" + uuid.uuid4().hex.encode()
    return buf.getvalue() + unique


def _text_pdf(text: str = "TITULO: Impacto de la IA") -> bytes:
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        _stream(text),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    return _build_pdf(objects)


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


def _upload_scan(client, headers, filename="scan.pdf", pages=2) -> dict:
    r = client.post(
        "/api/documents",
        files={"file": (filename, _blank_pdf(pages), "application/pdf")},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    doc = r.json()
    assert doc["needs_ocr"] is True
    return doc


def _cleanup(doc_id, headers, client):
    client.delete(f"/api/documents/{doc_id}", headers=headers)


def test_request_ocr_encola_y_crea_job(client, catalogador_headers, _fake_send_task):
    doc = _upload_scan(client, catalogador_headers)
    try:
        r = client.post(f"/api/documents/{doc['id']}/ocr", headers=catalogador_headers)
        assert r.status_code == 202, r.text
        data = r.json()
        assert data["status"] == "QUEUED"
        assert data["document_id"] == doc["id"]
        assert any(task == "app.jobs.tasks.run_ocr" for task, _ in _fake_send_task)

        r2 = client.get(f"/api/documents/{doc['id']}", headers=catalogador_headers)
        jobs = r2.json()["jobs"]
        assert any(j["job_type"] == "OCR" and j["status"] == "PENDING" for j in jobs)
    finally:
        _cleanup(doc["id"], catalogador_headers, client)


def test_request_ocr_documento_con_texto_409(client, catalogador_headers, tmp_path):
    db = SessionLocal()
    try:
        r = client.post(
            "/api/documents",
            files={"file": ("contexto.pdf", _text_pdf(), "application/pdf")},
            headers=catalogador_headers,
        )
    finally:
        db.close()
    assert r.status_code == 201, r.text
    doc = r.json()
    assert doc["needs_ocr"] is False
    try:
        r2 = client.post(f"/api/documents/{doc['id']}/ocr", headers=catalogador_headers)
        assert r2.status_code == 409
    finally:
        _cleanup(doc["id"], catalogador_headers, client)


def test_run_ocr_task_completa_paginas_y_job(client, catalogador_headers):
    doc = _upload_scan(client, catalogador_headers, pages=2)
    try:
        result = run_ocr(doc["id"])
        assert result["status"] == "COMPLETED"
        assert result["pages"] == 2
        assert result["ocr"]["tool"] == "ocrmypdf"
        assert result["ocr"]["languages"] == "spa+eng+por"
        assert result["ocr"]["output_object"] == f"ocr/{doc['sha256']}.pdf"
        assert storage.object_exists(f"ocr/{doc['sha256']}.pdf")

        r = client.get(f"/api/documents/{doc['id']}", headers=catalogador_headers)
        detail = r.json()
        assert detail["status"] == "OCR_COMPLETED"
        assert detail["analysis"]["needs_ocr"] is True
        pages = {p["page_number"]: p for p in detail["pages"]}
        assert "Impacto de la IA" in pages[1]["text"]
        assert pages[1]["ocr_used"] is True
        assert pages[2]["ocr_used"] is True

        ocr_job = [j for j in detail["jobs"] if j["job_type"] == "OCR"][-1]
        assert ocr_job["status"] == "COMPLETED"
        assert ocr_job["metadata_json"]["version"] == "16.7.0"
        assert ocr_job["metadata_json"]["pages_processed"] == 2
    finally:
        _cleanup(doc["id"], catalogador_headers, client)


def test_run_ocr_task_error_registra_job(client, catalogador_headers, monkeypatch):
    def _fail(pdf_bytes, languages, timeout=600):
        raise engine.OcrError("tesseract no disponible")

    monkeypatch.setattr(engine, "perform_ocr", _fail)
    doc = _upload_scan(client, catalogador_headers, pages=1)
    try:
        result = run_ocr(doc["id"])
        assert result["status"] == "ERROR"
        assert "tesseract" in result["error"]

        db = SessionLocal()
        try:
            d = db.get(Document, uuid.UUID(doc["id"]))
            assert d.status == "UPLOADED"
            job = (
                db.query(ProcessingJob)
                .filter(ProcessingJob.document_id == d.id, ProcessingJob.job_type == "OCR")
                .order_by(ProcessingJob.started_at.desc())
                .first()
            )
            assert job is not None
            assert job.status == "ERROR"
            assert "tesseract" in (job.error_message or "")
        finally:
            db.close()
    finally:
        _cleanup(doc["id"], catalogador_headers, client)


def test_run_ocr_documento_inexistente():
    result = run_ocr(str(uuid.uuid4()))
    assert result["status"] == "ERROR"


def test_deteccion_texto_insuficiente():
    assert engine.needs_ocr_for_pages(["", "", ""]) is True
    assert engine.needs_ocr_for_pages(["", "Texto", ""]) is False
    assert engine.needs_ocr_for_pages([]) is False


def test_auto_ocr_encola_al_subir(client, catalogador_headers, _fake_send_task, monkeypatch):
    monkeypatch.setattr(storage.settings, "auto_ocr", True)
    doc = _upload_scan(client, catalogador_headers, pages=1)
    try:
        assert any(task == "app.jobs.tasks.run_ocr" for task, _ in _fake_send_task)
        r = client.get(f"/api/documents/{doc['id']}", headers=catalogador_headers)
        jobs = r.json()["jobs"]
        assert any(j["job_type"] == "OCR" and j["status"] == "PENDING" for j in jobs)
    finally:
        _cleanup(doc["id"], catalogador_headers, client)


def test_ocr_404_documento_inexistente(client, catalogador_headers):
    r = client.post(f"/api/documents/{uuid.uuid4()}/ocr", headers=catalogador_headers)
    assert r.status_code == 404


def test_delete_document_limpia_objeto_ocr(client, catalogador_headers):
    doc = _upload_scan(client, catalogador_headers, pages=1)
    try:
        run_ocr(doc["id"])
        key = f"ocr/{doc['sha256']}.pdf"
        assert storage.object_exists(key)
        r = client.delete(f"/api/documents/{doc['id']}", headers=catalogador_headers)
        assert r.status_code in (204, 200), r.text
        assert storage.object_exists(key) is False
    except Exception:
        _cleanup(doc["id"], catalogador_headers, client)
        raise