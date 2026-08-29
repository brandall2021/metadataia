"""API de normalizacion de metadatos (FASE 10).

- POST /api/documents/{id}/normalize : encola la normalizacion (202).
Los valores extraidos por IA se convierten al formato configurado
(vocabularios con sinonimos, fechas ISO, identificadores, nombres).
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.jobs.celery_app import celery_app
from app.models import Document, MetadataRecord, ProcessingJob, User

router = APIRouter(prefix="/documents", tags=["documents-normalization"])

can_upload = require_permission("document.upload")
can_view = require_permission("document.view")


class NormalizationRequestOut(BaseModel):
    status: str
    job_id: str
    document_id: str
    message: str


def _enqueue_normalization(db: Session, doc: Document) -> ProcessingJob:
    job = ProcessingJob(document_id=doc.id, job_type="NORMALIZATION", status="PENDING")
    db.add(job)
    db.commit()
    db.refresh(job)
    celery_app.send_task("app.jobs.tasks.normalize_metadata", args=[str(doc.id)])
    return job


@router.post("/{document_id}/normalize", response_model=NormalizationRequestOut, status_code=202)
def request_normalization(
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
            status_code=409, detail="El documento no tiene metadatos para normalizar"
        )
    job = _enqueue_normalization(db, doc)
    return NormalizationRequestOut(
        status="QUEUED",
        job_id=str(job.id),
        document_id=str(doc.id),
        message="Normalizacion encolada; consulte /metadata para ver el resultado",
    )