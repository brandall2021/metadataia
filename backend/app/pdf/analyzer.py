"""Analisis de PDFs (FASE 7): validacion, paginas, texto y necesidad de OCR.

Flujo de la spec sec. 14:
1. Validar extension -> 2. Validar MIME -> 3. Verificar PDF valido ->
4. Tamanio maximo -> 5. SHA256 -> 6. Guardar original -> 7. Contar paginas ->
8. Analizar existencia de texto -> 9. Determinar necesidad de OCR.
"""

import hashlib
import io

from pypdf import PdfReader

from app.core.config import settings


class InvalidPDFError(Exception):
    """El archivo no es un PDF valido."""


def is_valid_pdf_mime(content_type: str) -> bool:
    return content_type.lower() in {"application/pdf", "application/x-pdf"}
    # application/octet-stream se acepta en el router por compatibilidad de navegadores


def is_valid_extension(filename: str) -> bool:
    return filename.lower().endswith(".pdf")


def max_upload_bytes() -> int:
    return max(1, settings.default_max_file_size_mb) * 1024 * 1024


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def analyze_pdf(data: bytes) -> dict:
    """Analiza el PDF y devuelve paginas, texto por pagina y necesidad de OCR.

    Nunca modifica el archivo original: trabaja sobre los bytes recibidos.
    """
    if not data:
        raise InvalidPDFError("El archivo esta vacio")
    if len(data) > max_upload_bytes():
        raise InvalidPDFError(
            f"Excede el tama\u00f1o m\u00e1ximo de {settings.default_max_file_size_mb} MB"
        )
    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception as exc:  # noqa: BLE001 - pypdf lanza varios tipos de error
        raise InvalidPDFError("El archivo no es un PDF valido") from exc

    pages = []
    total_text = 0
    for page in reader.pages:
        try:
            text = page.extract_text() or ""
        except Exception:  # noqa: BLE001 - una pagina danada no debe romper el analisis
            text = ""
        pages.append(text)
        total_text += len(text)

    page_count = len(pages)
    needs_ocr = page_count > 0 and total_text == 0

    return {
        "page_count": page_count,
        "pages_text": pages,
        "total_text_length": total_text,
        "needs_ocr": needs_ocr,
    }