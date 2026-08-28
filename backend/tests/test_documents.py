"""Tests del motor de PDF (FASE 7).

Criterio: el PDF queda almacenado y analizado (validacion, SHA256, paginas,
texto por pagina, necesidad de OCR). El archivo original nunca se modifica.
"""

import hashlib
import io
import uuid

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader, PdfWriter

from app.core import storage
from app.main import create_app


@pytest.fixture(autouse=True)
def _local_storage(tmp_path_factory, monkeypatch):
    """Usa filesystem como backend de almacenamiento en los tests."""
    path = tmp_path_factory.mktemp("storage")
    monkeypatch.setattr(storage.settings, "storage_backend", "filesystem")
    monkeypatch.setattr(storage.settings, "local_storage_path", str(path))
    monkeypatch.setattr(storage, "_s3_client", lambda: (_ for _ in ()).throw(AssertionError("S3 no debe usarse en tests")))
    storage.ensure_bucket()
    yield path


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_app())


@pytest.fixture(scope="module")
def catalogador_headers(client) -> dict:
    r = client.post("/api/auth/login", json={"username": "catalogador", "password": "metadataia123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def revisor_headers(client) -> dict:
    r = client.post("/api/auth/login", json={"username": "revisor", "password": "metadataia123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _blank_pdf(pages: int = 2) -> bytes:
    """PDF sin texto (simula un escaneo): 2 paginas en blanco."""
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=612, height=792)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _text_pdf(text: str = "Titulo de la tesis: METADATAIA") -> bytes:
    """PDF con una pagina con texto, construido con xref correcto."""
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


def test_pdf_generado_text_es_valido():
    data = _text_pdf()
    reader = PdfReader(io.BytesIO(data))
    assert reader.pages
    assert "METADATAIA" in (reader.pages[0].extract_text() or "")


def test_upload_sin_token_401(client):
    assert client.post("/api/documents", files={"file": ("a.pdf", b"x", "application/pdf")}).status_code == 401


def test_upload_catalogador_ok_analiza_y_almacena(client, catalogador_headers, _local_storage):
    pdf = _text_pdf()
    expected_sha = hashlib.sha256(pdf).hexdigest()

    r = client.post(
        "/api/documents",
        files={"file": ("tesis.pdf", pdf, "application/pdf")},
        headers=catalogador_headers,
    )
    assert r.status_code == 201, r.text
    doc = r.json()
    assert doc["page_count"] == 1
    assert doc["sha256"] == expected_sha
    assert doc["needs_ocr"] is False
    assert len(doc["pages"]) == 1
    assert doc["pages"][0]["text_length"] > 0
    assert doc["pages"][0]["ocr_used"] is False
    assert doc["status"] == "UPLOADED"

    stored_key = f"documents/{expected_sha}.pdf"
    assert storage.object_exists(stored_key)

    r2 = client.get(f"/api/documents/{doc['id']}", headers=catalogador_headers)
    assert r2.status_code == 200
    assert r2.json()["needs_ocr"] is False

    r3 = client.delete(f"/api/documents/{doc['id']}", headers=catalogador_headers)
    assert r3.status_code == 204


def test_upload_pdf_escaneado_detecta_needs_ocr(client, catalogador_headers, _local_storage):
    pdf = _blank_pdf(pages=3)
    r = client.post(
        "/api/documents",
        files={"file": ("scan.pdf", pdf, "application/pdf")},
        headers=catalogador_headers,
    )
    assert r.status_code == 201, r.text
    doc = r.json()
    assert doc["page_count"] == 3
    assert doc["needs_ocr"] is True
    assert [p["text_length"] for p in doc["pages"]] == [0, 0, 0]

    r2 = client.delete(f"/api/documents/{doc['id']}", headers=catalogador_headers)
    assert r2.status_code == 204


def test_upload_duplicado_409(client, catalogador_headers, _local_storage):
    pdf = _text_pdf()
    r1 = client.post(
        "/api/documents", files={"file": ("a.pdf", pdf, "application/pdf")}, headers=catalogador_headers
    )
    doc_id = r1.json()["id"]
    try:
        r2 = client.post(
            "/api/documents", files={"file": ("copia.pdf", pdf, "application/pdf")}, headers=catalogador_headers
        )
        assert r2.status_code == 409
    finally:
        client.delete(f"/api/documents/{doc_id}", headers=catalogador_headers)


def test_upload_extension_invalida_422(client, catalogador_headers):
    r = client.post(
        "/api/documents", files={"file": ("nota.txt", b"hola", "text/plain")}, headers=catalogador_headers
    )
    assert r.status_code == 422


def test_upload_mime_invalido_422(client, catalogador_headers):
    r = client.post(
        "/api/documents",
        files={"file": ("foto.pdf", b"not a pdf", "image/png")},
        headers=catalogador_headers,
    )
    assert r.status_code == 422


def test_upload_no_es_pdf_valido_422(client, catalogador_headers):
    r = client.post(
        "/api/documents",
        files={"file": ("falso.pdf", b"not a pdf at all", "application/pdf")},
        headers=catalogador_headers,
    )
    assert r.status_code == 422


def test_upload_vacio_422(client, catalogador_headers):
    r = client.post(
        "/api/documents",
        files={"file": ("vacio.pdf", b"", "application/pdf")},
        headers=catalogador_headers,
    )
    assert r.status_code == 422


def test_upload_oversize_413(client, catalogador_headers, monkeypatch):
    monkeypatch.setattr("app.pdf.analyzer.settings.default_max_file_size_mb", 1)
    big = b"%PDF-1.4\n" + b"x" * (2 * 1024 * 1024)
    r = client.post(
        "/api/documents",
        files={"file": ("grande.pdf", big, "application/pdf")},
        headers=catalogador_headers,
    )
    assert r.status_code in (413, 422)


def test_download_devuelve_original_idéntico(client, catalogador_headers, _local_storage):
    """El original guardado es identico (SHA256) al recibido: nunca se modifica."""
    pdf = _text_pdf("PDF ORIGINAL INMODIFICABLE")
    r = client.post(
        "/api/documents",
        files={"file": ("original.pdf", pdf, "application/pdf")},
        headers=catalogador_headers,
    )
    doc = r.json()
    try:
        r2 = client.get(f"/api/documents/{doc['id']}/download", headers=catalogador_headers)
        assert r2.status_code == 200
        assert r2.headers["content-type"].startswith("application/pdf")
        assert hashlib.sha256(r2.content).hexdigest() == doc["sha256"]
    finally:
        client.delete(f"/api/documents/{doc['id']}", headers=catalogador_headers)


def test_listar_documentos_y_borrar_archivo(client, catalogador_headers, _local_storage):
    pdf = _text_pdf("Para listar")
    r = client.post(
        "/api/documents",
        files={"file": ("list.pdf", pdf, "application/pdf")},
        headers=catalogador_headers,
    )
    doc = r.json()
    r2 = client.get("/api/documents", headers=catalogador_headers)
    assert any(d["id"] == doc["id"] for d in r2.json())

    client.delete(f"/api/documents/{doc['id']}", headers=catalogador_headers)
    assert storage.object_exists(f"documents/{doc['sha256']}.pdf") is False
    r3 = client.get(f"/api/documents/{doc['id']}", headers=catalogador_headers)
    assert r3.status_code == 404


def test_revisor_sin_permiso_upload_403(client, revisor_headers):
    r = client.post(
        "/api/documents",
        files={"file": ("a.pdf", _text_pdf(), "application/pdf")},
        headers=revisor_headers,
    )
    assert r.status_code == 403


def test_documento_inexistente_404(client, catalogador_headers):
    assert client.get(f"/api/documents/{uuid.uuid4()}", headers=catalogador_headers).status_code == 404