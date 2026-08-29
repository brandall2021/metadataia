"""Revisión humana de metadatos (FASE 12).

El catalogador/revisor puede corregir TODOS los metadatos antes del depósito:
editar valores, crear registros faltantes, borrar registros erróneos, aprobar
(revalidando primero) o rechazar el documento.
"""

import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.audit.service import audit_log, request_context
from app.core.database import get_db
from app.core.dependencies import require_permission
from app.extraction.engine import field_key
from app.jobs.tasks import validate_metadata
from app.models import Document, MetadataField, MetadataRecord, User

router = APIRouter(prefix="/documents", tags=["review"])

can_review = require_permission("document.review")
can_approve = require_permission("document.approve")

REVIEWABLE_EDIT_BLOCK = ("APPROVED", "DEPOSITANDO", "DEPOSITED")
NOT_FOUND_DOC = "Documento no encontrado"
NOT_FOUND_REC = "Registro de metadato no encontrado"


class RecordUpdate(BaseModel):
    value: str


class RecordCreate(BaseModel):
    field_id: UUID
    value: str
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class ReviewResult(BaseModel):
    document_id: UUID
    status: str


def _get_doc(db: Session, document_id: UUID) -> Document:
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NOT_FOUND_DOC)
    return doc


def _get_record(db: Session, document_id: UUID, record_id: UUID) -> MetadataRecord:
    rec = db.get(MetadataRecord, record_id)
    if rec is None or rec.document_id != document_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NOT_FOUND_REC)
    return rec


def _ensure_editable(doc: Document) -> None:
    if doc.status in REVIEWABLE_EDIT_BLOCK:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se puede modificar un documento aprobado o ya depositado",
        )


def _mark_review(db: Session, doc: Document) -> None:
    doc.status = "NEEDS_REVIEW"


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


@router.put("/{document_id}/records/{record_id}", response_model=dict, status_code=status.HTTP_200_OK)
def update_record(
    document_id: UUID,
    record_id: UUID,
    body: RecordUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(can_review),
):
    doc = _get_doc(db, document_id)
    rec = _get_record(db, document_id, record_id)
    _ensure_editable(doc)
    field = field_key(rec.metadata_field.element, rec.metadata_field.qualifier)
    old = {"field": field, "value": rec.value}
    rec.value = body.value
    rec.manually_modified = True
    rec.validated = False
    rec.normalized = False
    _mark_review(db, doc)
    audit_log(
        db,
        user=user,
        action="record.update",
        entity_type="document",
        entity_id=str(doc.id),
        old_value=old,
        new_value={"field": field, "value": body.value},
        **request_context(request),
    )
    db.commit()
    db.refresh(rec)
    return _record_out(rec)


@router.post("/{document_id}/records", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_record(
    document_id: UUID,
    body: RecordCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(can_review),
):
    doc = _get_doc(db, document_id)
    _ensure_editable(doc)
    fld = db.get(MetadataField, body.field_id)
    if fld is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campo de metadato no encontrado")
    type_ids = {link.metadata_field_id for link in (doc.document_type.metadata_field_links or [])}
    if body.field_id not in type_ids:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El campo no pertenece al tipo documental del documento",
        )
    existing = (
        db.query(MetadataRecord)
        .filter(MetadataRecord.document_id == document_id, MetadataRecord.metadata_field_id == body.field_id)
        .one_or_none()
    )
    if existing is not None and existing.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El campo ya tiene un valor; use PUT para corregirlo",
        )
    rec = MetadataRecord(
        document_id=doc.id,
        metadata_field_id=body.field_id,
        value=body.value,
        confidence=body.confidence,
        source="MANUAL",
        manually_modified=True,
        validated=False,
    )
    db.add(rec)
    _mark_review(db, doc)
    audit_log(
        db,
        user=user,
        action="record.create",
        entity_type="document",
        entity_id=str(doc.id),
        new_value={"field": field_key(fld.element, fld.qualifier), "value": body.value, "source": "MANUAL"},
        **request_context(request),
    )
    db.commit()
    db.refresh(rec)
    return _record_out(rec)


@router.delete("/{document_id}/records/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_record(
    document_id: UUID,
    record_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(can_review),
):
    doc = _get_doc(db, document_id)
    rec = _get_record(db, document_id, record_id)
    _ensure_editable(doc)
    audit_log(
        db,
        user=user,
        action="record.delete",
        entity_type="document",
        entity_id=str(doc.id),
        old_value={"field": field_key(rec.metadata_field.element, rec.metadata_field.qualifier), "value": rec.value},
        **request_context(request),
    )
    db.delete(rec)
    _mark_review(db, doc)
    db.commit()


@router.post("/{document_id}/approve", response_model=ReviewResult)
def approve_document(
    document_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(can_approve),
):
    doc = _get_doc(db, document_id)
    if doc.status in ("DEPOSITANDO", "DEPOSITED"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El documento ya esta en proceso de deposito",
        )
    if doc.status == "APPROVED":
        return ReviewResult(document_id=doc.id, status=doc.status)
    has_records = (
        db.query(MetadataRecord)
        .filter(MetadataRecord.document_id == document_id, MetadataRecord.value.isnot(None))
        .first()
    )
    if has_records is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El documento no tiene metadatos para aprobar",
        )
    result = validate_metadata(str(document_id))
    if result.get("status") == "ERROR" or result.get("valid") is not True:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se puede aprobar: la validacion tiene errores",
        )
    doc = _get_doc(db, document_id)
    doc.status = "APPROVED"
    audit_log(
        db,
        user=user,
        action="document.approve",
        entity_type="document",
        entity_id=str(doc.id),
        new_value={"status": "APPROVED"},
        **request_context(request),
    )
    db.commit()
    db.refresh(doc)
    return ReviewResult(document_id=doc.id, status=doc.status)


@router.post("/{document_id}/reject", response_model=ReviewResult)
def reject_document(
    document_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(can_review),
):
    doc = _get_doc(db, document_id)
    if doc.status == "APPROVED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se puede rechazar un documento ya aprobado",
        )
    doc.status = "REJECTED"
    audit_log(
        db,
        user=user,
        action="document.reject",
        entity_type="document",
        entity_id=str(doc.id),
        new_value={"status": "REJECTED"},
        **request_context(request),
    )
    db.commit()
    db.refresh(doc)
    return ReviewResult(document_id=doc.id, status=doc.status)