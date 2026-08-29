"""API de extraccion de metadatos con IA (FASE 9).

- POST /api/documents/{id}/extract : encola la extraccion (202).
- GET  /api/documents/{id}/metadata : registros extraidos + historial de runs.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.extraction.engine import field_key
from app.extraction.schemas import (
    ExtractionRequestOut,
    MetadataCollectionOut,
    MetadataRecordOut,
)
from app.jobs.celery_app import celery_app
from app.models import Document, MetadataRecord, ProcessingJob, User

router = APIRouter(prefix="/documents", tags=["documents-extraction"])

can_upload = require_permission("document.upload")
can_view = require_permission("document.view")


def _enqueue_extraction(db: Session, doc: Document) -> ProcessingJob:
    job = ProcessingJob(document_id=doc.id, job_type="EXTRACTION", status="PENDING")
    db.add(job)
    db.commit()
    db.refresh(job)
    celery_app.send_task("app.jobs.tasks.extract_metadata", args=[str(doc.id)])
    return job


@router.post("/{document_id}/extract", response_model=ExtractionRequestOut, status_code=202)
def request_extraction(
    document_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(can_upload),
):
    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Documento no valido")
    doc = db.get(Document, doc_uuid)
    if doc is None:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    if doc.needs_ocr:
        raise HTTPException(status_code=409, detail="El documento requiere OCR antes de extraer")
    has_text = any(p.text and p.text.strip() for p in doc.pages)
    if not has_text:
        raise HTTPException(status_code=409, detail="El documento no tiene texto; ejecute OCR")
    job = _enqueue_extraction(db, doc)
    return ExtractionRequestOut(
        status="QUEUED",
        job_id=str(job.id),
        document_id=str(doc.id),
        message="Extraccion de metadatos encolada; consulte /metadata para ver el resultado",
    )


@router.get("/{document_id}/metadata", response_model=MetadataCollectionOut)
def get_document_metadata(
    document_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(can_view),
):
    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Documento no valido")
    doc = db.get(Document, doc_uuid)
    if doc is None:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    jobs_by_run: dict[str, ProcessingJob] = {}
    for j in doc.jobs:
        if j.job_type == "EXTRACTION" and j.metadata_json and j.metadata_json.get("run_id"):
            jobs_by_run[str(j.metadata_json["run_id"])] = j

    runs = []
    for run in sorted(doc.extraction_runs, key=lambda r: r.started_at or r.id):
        job = jobs_by_run.get(str(run.id))
        runs.append(
            {
                "id": str(run.id),
                "agent_id": str(run.agent_id) if run.agent_id else None,
                "agent_version_id": str(run.agent_version_id) if run.agent_version_id else None,
                "model_id": str(run.model_id) if run.model_id else None,
                "prompt_hash": run.prompt_hash,
                "started_at": run.started_at,
                "finished_at": run.finished_at,
                "input_tokens": run.input_tokens,
                "output_tokens": run.output_tokens,
                "status": run.status,
                "raw_response_storage_path": run.raw_response_storage_path,
                "error_message": run.error_message,
                "summary": job.metadata_json if job is not None else {},
            }
        )

    records = []
    for rec in sorted(doc.metadata_records, key=lambda r: (r.metadata_field.display_name or "")):
        fld = rec.metadata_field
        records.append(
            {
                "id": str(rec.id),
                "metadata_field_id": str(rec.metadata_field_id),
                "field": field_key(fld.element, fld.qualifier),
                "display_name": fld.display_name or field_key(fld.element, fld.qualifier),
                "value": rec.value,
                "language": rec.language,
                "confidence": rec.confidence,
                "source": rec.source,
                "source_page": rec.source_page,
                "source_text": rec.source_text,
                "extraction_run_id": str(rec.extraction_run_id) if rec.extraction_run_id else None,
                "normalized": rec.normalized,
                "validated": rec.validated,
                "manually_modified": rec.manually_modified,
            }
        )

    return MetadataCollectionOut(
        document_id=str(doc.id),
        document_status=doc.status,
        runs=runs,
        records=records,
    )