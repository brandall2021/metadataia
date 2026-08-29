"""API de validacion de metadatos (FASE 11).

- POST /api/documents/{id}/validate : encola la validacion (202).
- GET  /api/documents/{id}/validation : resultados por validador.

El motor valida los registros (obligatorios, formatos, vocabularios) y
el modulo SNRD verifica el perfil de interoperabilidad.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.jobs.celery_app import celery_app
from app.models import Document, MetadataRecord, ProcessingJob, User

router = APIRouter(prefix="/documents", tags=["documents-validation"])

can_upload = require_permission("document.upload")
can_view = require_permission("document.view")


class ValidationResultOut(BaseModel):
    id: uuid.UUID
    validator_type: str
    status: str
    errors_json: list | None
    warnings_json: list | None
    created_at: object | None = None


class ValidationCollectionOut(BaseModel):
    document_id: uuid.UUID
    document_status: str
    results: list[ValidationResultOut]


class ValidationRequestOut(BaseModel):
    status: str
    job_id: str
    document_id: str
    message: str


def _enqueue_validation(db: Session, doc: Document) -> ProcessingJob:
    job = ProcessingJob(document_id=doc.id, job_type="VALIDATION", status="PENDING")
    db.add(job)
    db.commit()
    db.refresh(job)
    celery_app.send_task("app.jobs.tasks.validate_metadata", args=[str(doc.id)])
    return job


@router.post("/{document_id}/validate", response_model=ValidationRequestOut, status_code=202)
def request_validation(
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
    has_records = (
        db.query(MetadataRecord.id)
        .filter(MetadataRecord.document_id == doc.id, MetadataRecord.value.isnot(None))
        .first()
    )
    if not has_records:
        raise HTTPException(
            status_code=409, detail="El documento no tiene metadatos para validar"
        )
    job = _enqueue_validation(db, doc)
    return ValidationRequestOut(
        status="QUEUED",
        job_id=str(job.id),
        document_id=str(doc.id),
        message="Validacion encolada; consulte /validation para ver el resultado",
    )


@router.get("/{document_id}/validation", response_model=ValidationCollectionOut)
def get_document_validation(
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
    results = sorted(doc.validation_results, key=lambda r: r.created_at or r.id, reverse=True)
    return ValidationCollectionOut(
        document_id=doc.id,
        document_status=doc.status,
        results=[
            ValidationResultOut(
                id=r.id,
                validator_type=r.validator_type,
                status=r.status,
                errors_json=r.errors_json,
                warnings_json=r.warnings_json,
                created_at=r.created_at,
            )
            for r in results
        ],
    )