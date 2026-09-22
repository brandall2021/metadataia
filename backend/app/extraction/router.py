"""API de extraccion de metadatos con IA (FASE 9).

- POST /api/documents/{id}/extract : encola la extraccion (202).
- GET  /api/documents/{id}/metadata : registros extraidos + historial de runs.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.audit.service import audit_log, request_context
from app.core.database import get_db
from app.core.dependencies import require_permission
from app.core.errors import AppError, LOCKED_STATE
from app.extraction.engine import field_key
from app.extraction.schemas import (
    ExtractionRequestOut,
    MetadataCollectionOut,
    MetadataRecordOut,
)
from app.jobs.celery_app import celery_app
from app.jobs.tasks import analyze_document, extract_text
from app.models import Document, MetadataRecord, ProcessingJob, User
from app.workflows import DocumentStatus, EDIT_LOCKED_STATES, set_document_status

router = APIRouter(prefix="/documents", tags=["documents-extraction"])

can_upload = require_permission("document.upload")
can_view = require_permission("document.view")
can_review = require_permission("document.review")

# Nombres registrados de las tareas Celery (para enqueue por send_task).
_ANALYZE_TASK = analyze_document.name
_TEXT_TASK = extract_text.name
_EXTRACTION_TASK = "app.jobs.tasks.extract_metadata"


def _enqueue_extraction(db: Session, doc: Document) -> ProcessingJob:
    job = ProcessingJob(document_id=doc.id, job_type="EXTRACTION", status="PENDING")
    db.add(job)
    db.commit()
    db.refresh(job)
    celery_app.send_task(_EXTRACTION_TASK, args=[str(doc.id)])
    return job


def _enqueue_task(db: Session, doc: Document, job_type: str, task_name: str) -> ProcessingJob:
    job = ProcessingJob(document_id=doc.id, job_type=job_type, status="PENDING")
    db.add(job)
    db.commit()
    db.refresh(job)
    celery_app.send_task(task_name, args=[str(doc.id)])
    return job


def _get_doc(db: Session, document_id: str) -> Document:
    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Documento no valido")
    doc = db.get(Document, doc_uuid)
    if doc is None:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    return doc


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


@router.post("/{document_id}/analyze", response_model=ExtractionRequestOut, status_code=202)
def request_analysis(
    document_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(can_upload),
):
    doc = _get_doc(db, document_id)
    if doc.status in EDIT_LOCKED_STATES:
        raise HTTPException(status_code=409, detail="El documento esta en procesamiento")
    if doc.needs_ocr:
        raise HTTPException(status_code=409, detail="El documento requiere OCR antes de analizarse")
    job = _enqueue_task(db, doc, "ANALYSIS", _ANALYZE_TASK)
    return ExtractionRequestOut(
        status="QUEUED",
        job_id=str(job.id),
        document_id=str(doc.id),
        message="Analisis del documento encolado",
    )


@router.post("/{document_id}/extract-text", response_model=ExtractionRequestOut, status_code=202)
def request_text_extraction(
    document_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(can_upload),
):
    doc = _get_doc(db, document_id)
    if doc.status in EDIT_LOCKED_STATES:
        raise HTTPException(status_code=409, detail="El documento esta en procesamiento")
    if doc.needs_ocr:
        raise HTTPException(status_code=409, detail="El documento requiere OCR antes de extraer texto")
    job = _enqueue_task(db, doc, "TEXT_EXTRACTION", _TEXT_TASK)
    return ExtractionRequestOut(
        status="QUEUED",
        job_id=str(job.id),
        document_id=str(doc.id),
        message="Extraccion de texto encolada",
    )


@router.post("/{document_id}/extract-metadata", response_model=ExtractionRequestOut, status_code=202)
def request_extract_metadata_alias(
    document_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(can_upload),
):
    doc = _get_doc(db, document_id)
    if doc.status in EDIT_LOCKED_STATES:
        raise HTTPException(status_code=409, detail="El documento esta en procesamiento")
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
        message="Extraccion de metadatos encolada",
    )


class MetadataBulkEditItem(BaseModel):
    record_id: uuid.UUID
    value: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    source: str | None = None


class MetadataBulkEditBody(BaseModel):
    records: list[MetadataBulkEditItem]


def _record_out(rec: MetadataRecord) -> dict:
    fld = rec.metadata_field
    return {
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


@router.put("/{document_id}/metadata", response_model=list[MetadataRecordOut], status_code=200)
def update_metadata_bulk(
    document_id: str,
    body: MetadataBulkEditBody,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(can_review),
):
    doc = _get_doc(db, document_id)
    blocked = EDIT_LOCKED_STATES | {DocumentStatus.APPROVED}
    if doc.status in blocked:
        raise AppError(
            LOCKED_STATE,
            f"No se puede editar la metadata de un documento en estado {doc.status}",
            status_code=409,
        )
    changed: list[MetadataRecord] = []
    old_values = []
    for item in body.records:
        rec = db.get(MetadataRecord, item.record_id)
        if rec is None or rec.document_id != doc.id:
            raise HTTPException(status_code=404, detail="Registro de metadato no encontrado")
        fld = rec.metadata_field
        if fld is not None and not fld.editable:
            raise HTTPException(
                status_code=409,
                detail=f"El campo {fld.display_name or field_key(fld.element, fld.qualifier)} no es editable",
            )
        old_values.append(
            {
                "field": field_key(fld.element, fld.qualifier),
                "value": rec.value,
                "confidence": rec.confidence,
            }
        )
        if item.value is not None:
            rec.value = item.value
        if item.confidence is not None:
            rec.confidence = item.confidence
        if item.source is not None:
            rec.source = item.source
        rec.manually_modified = True
        rec.validated = False
        rec.normalized = False
        changed.append(rec)
    if changed:
        set_document_status(db, doc, DocumentStatus.NEEDS_REVIEW, user=user)
        audit_log(
            db,
            user=user,
            action="document.metadata.bulkupdate",
            entity_type="document",
            entity_id=str(doc.id),
            old_value={"records": old_values},
            new_value={"records": [_record_out(r) for r in changed]},
            **request_context(request),
        )
    db.commit()
    return [_record_out(rec) for rec in changed]


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