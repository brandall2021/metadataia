from datetime import datetime, timezone
from uuid import UUID

from celery import shared_task

from app.core import storage
from app.core.config import settings
from app.core.database import SessionLocal
from app.models import Document, ProcessingJob
from app.ocr import engine


@shared_task(name="app.jobs.tasks.analyze_document")
def analyze_document(document_id: str) -> dict:
    """Job placeholder: analisis de documento (FASE 7 ya cubre el analisis)."""
    return {"document_id": document_id, "status": "PENDING"}


@shared_task(name="app.jobs.tasks.run_ocr")
def run_ocr(document_id: str, languages: str | None = None) -> dict:
    """OCR sobre un documento escaneado (FASE 8).

    PDF original -> OCRmyPDF+Tesseract -> PDF buscable -> texto por pagina.
    El original nunca se modifica; el buscable se guarda en ocr/{sha256}.pdf.
    """
    db = SessionLocal()
    job = None
    try:
        doc = db.get(Document, UUID(document_id))
        if doc is None:
            return {"status": "ERROR", "error": "documento no encontrado"}

        job = ProcessingJob(document_id=doc.id, job_type="OCR", status="RUNNING")
        job.started_at = datetime.now(timezone.utc)
        db.add(job)
        doc.status = "PROCESSING"
        db.commit()
        db.refresh(job)

        original = storage.download_original(doc.storage_path)
        langs = languages or settings.ocr_languages
        result = engine.perform_ocr(original, langs)
        searchable_pdf = result["pdf"]
        ocr_key = storage.upload_searchable(doc.sha256 or "", searchable_pdf)
        texts = engine.extract_text_pdf(searchable_pdf)

        pages = sorted(doc.pages, key=lambda p: p.page_number)
        for i, page in enumerate(pages, start=1):
            if i <= len(texts):
                page.text = texts[i - 1] or ""
                page.text_length = len(page.text or "")
                page.ocr_used = True

        doc.status = "OCR_COMPLETED"
        job.status = "COMPLETED"
        job.finished_at = datetime.now(timezone.utc)
        job.metadata_json = {
            **result["meta"],
            "pages_processed": len(texts),
            "output_object": ocr_key,
        }
        db.commit()
        return {
            "status": "COMPLETED",
            "document_id": document_id,
            "pages": len(texts),
            "ocr": {**result["meta"], "output_object": ocr_key},
        }
    except Exception as exc:  # noqa: BLE001 - el error queda registrado en el job
        db.rollback()
        if job is not None:
            job.status = "ERROR"
            job.error_message = str(exc)[:2000]
            job.finished_at = datetime.now(timezone.utc)
            doc = db.get(Document, UUID(document_id))
            if doc is not None and doc.status == "PROCESSING":
                doc.status = "UPLOADED"
            db.commit()
        return {"status": "ERROR", "document_id": document_id, "error": str(exc)[:1000]}
    finally:
        db.close()


@shared_task(name="app.jobs.tasks.extract_text")
def extract_text(document_id: str) -> dict:
    """Job placeholder: extraccion de texto por pagina (FASE 8/16)."""
    return {"document_id": document_id, "status": "PENDING"}


@shared_task(name="app.jobs.tasks.extract_metadata")
def extract_metadata(document_id: str) -> dict:
    """Job placeholder: extraccion de metadatos con IA (FASE 9)."""
    return {"document_id": document_id, "status": "PENDING"}


@shared_task(name="app.jobs.tasks.normalize_metadata")
def normalize_metadata(document_id: str) -> dict:
    """Job placeholder: normalizacion de metadatos (FASE 10)."""
    return {"document_id": document_id, "status": "PENDING"}


@shared_task(name="app.jobs.tasks.validate_metadata")
def validate_metadata(document_id: str) -> dict:
    """Job placeholder: validacion de metadatos (FASE 11)."""
    return {"document_id": document_id, "status": "PENDING"}


@shared_task(name="app.jobs.tasks.deposit_dspace")
def deposit_dspace(document_id: str) -> dict:
    """Job placeholder: deposito en DSpace (FASE 13)."""
    return {"document_id": document_id, "status": "PENDING"}