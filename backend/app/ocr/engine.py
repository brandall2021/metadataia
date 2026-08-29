"""Motor de OCR (FASE 8): OCRmyPDF + Tesseract + extraccion de texto por pagina.

Flujo (spec sec. 15):
PDF original -> analisis -> texto insuficiente -> OCRmyPDF ->
PDF searchable -> extraccion de texto por pagina.

Nunca modifica el archivo original: los bytes se procesan en memoria/archivos
temporales y el resultado buscable se guarda aparte (ocr/{sha256}.pdf).
Registra: herramienta, version, idioma, tiempo, errores y paginas procesadas.
"""

import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from pypdf import PdfReader

OCR_TOOL = "ocrmypdf"


class OcrError(Exception):
    """Error al ejecutar el OCR."""


def ocr_version() -> str:
    try:
        out = subprocess.run(
            [OCR_TOOL, "--version"], capture_output=True, text=True, timeout=10
        )
        return (out.stdout or out.stderr).strip().splitlines()[0]
    except Exception:  # noqa: BLE001
        return "desconocida"


def is_executable() -> bool:
    return shutil.which(OCR_TOOL) is not None and shutil.which("tesseract") is not None


def perform_ocr(pdf_bytes: bytes, languages: str, timeout: int = 600) -> dict:
    """Aplica OCRmyPDF a un PDF y devuelve el PDF buscable + metadatos.

    Devuelve {"pdf": bytes_del_pdf_buscable, "meta": {...}}.
    Lanza OcrError si la herramienta no esta disponible o falla.
    """
    if not is_executable():
        raise OcrError("ocrmypdf/tesseract no estan instalados en este entorno")

    with tempfile.TemporaryDirectory() as tmp:
        in_path = Path(tmp) / "input.pdf"
        out_path = Path(tmp) / "output.pdf"
        in_path.write_bytes(pdf_bytes)

        t0 = time.monotonic()
        proc = subprocess.run(
            [
                OCR_TOOL,
                "--skip-text",
                "--language",
                languages,
                str(in_path),
                str(out_path),
            ],
            capture_output=True,
            timeout=timeout,
        )
        elapsed = round(time.monotonic() - t0, 3)

        if proc.returncode != 0:
            stderr = proc.stderr.decode("utf-8", errors="replace")[-2000:]
            raise OcrError(f"ocrmypdf fallo (codigo {proc.returncode}): {stderr}")

        if not out_path.exists():
            raise OcrError("ocrmypdf no genero el PDF buscable")

        return {
            "pdf": out_path.read_bytes(),
            "meta": {
                "tool": OCR_TOOL,
                "version": ocr_version(),
                "languages": languages,
                "elapsed_seconds": elapsed,
            },
        }


def extract_text_pdf(pdf_bytes: bytes) -> list[str]:
    """Extrae el texto de cada pagina (pypdf). Index-driven: page_number -> texto."""
    import io

    reader = PdfReader(io.BytesIO(pdf_bytes))
    pages = []
    for page in reader.pages:
        try:
            text = page.extract_text() or ""
        except Exception:  # noqa: BLE001
            text = ""
        pages.append(text)
    return pages


def needs_ocr_for_pages(pages_text: list[str]) -> bool:
    """deteccion de texto: un documento pide OCR si ninguna pagina tiene texto."""
    return len(pages_text) > 0 and all(not (t or "").strip() for t in pages_text)