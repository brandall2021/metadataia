"""Deposito de documentos aprobados en el repositorio (FASE 13).

Flujo: APPROVED -> validacion final -> workspace item -> metadata -> PDF ->
submission -> registro del resultado (Deposition). Reintentos permitidos;
un deposito exitoso nunca se duplica.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.audit.service import audit_log, request_context
from app.core.database import get_db
from app.core.dependencies import require_permission
from app.core.errors import AppError, NOT_DEPOSITABLE
from app.jobs.celery_app import celery_app
from app.models import Deposition, Document, ProcessingJob, Repository, RepositoryCollection, User, ValidationResult
from app.snrd.export import dc_fields
from app.workflows import DocumentStatus

router = APIRouter(prefix="/documents", tags=["documents-deposit"])

can_deposit = require_permission("document.deposit")
can_view = require_permission("document.view")


class DepositRequestOut(BaseModel):
    document_id: uuid.UUID
    status: str
    job_id: uuid.UUID | None = None


class DepositionOut(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    repository_id: uuid.UUID | None = None
    collection_id: uuid.UUID | None = None
    external_item_id: str | None = None
    handle: str | None = None
    status: str
    error_message: str | None = None
    started_at: object | None = None
    finished_at: object | None = None


class SnrdExportOut(BaseModel):
    document_id: uuid.UUID
    document_status: str
    scheme: str
    metadata: dict


def _get_doc(db: Session, document_id: uuid.UUID) -> Document:
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento no encontrado")
    return doc


def _resolve_collection(db: Session, doc: Document) -> RepositoryCollection | None:
    if doc.repository_collection_id is not None:
        return db.get(RepositoryCollection, doc.repository_collection_id)
    if doc.document_type is not None:
        for col in doc.document_type.repository_collections:
            if col.active:
                return col
    return None


def _latest_blocking_validation(db: Session, doc: Document) -> ValidationResult | None:
    """Si la ultima corrida de validacion (metadata/snrd) tiene errores bloqueantes."""
    latest_at = (
        db.query(func.max(ValidationResult.created_at))
        .filter(
            ValidationResult.document_id == doc.id,
            func.lower(ValidationResult.validator_type).in_(("metadata", "snrd")),
        )
        .scalar()
    )
    if latest_at is None:
        return None
    results = (
        db.query(ValidationResult)
        .filter(ValidationResult.document_id == doc.id, ValidationResult.created_at == latest_at)
        .all()
    )
    for result in results:
        if result.status == "FAILED" and result.errors_json:
            return result
    return None


def _check_depositable(db: Session, doc: Document) -> tuple[RepositoryCollection, Repository]:
    """Devuelve (collection, repo) si el documento puede depositarse."""
    if doc.status == DocumentStatus.DEPOSITED:
        raise HTTPException(status_code=409, detail="El documento ya fue depositado")
    if doc.status != DocumentStatus.APPROVED:
        raise HTTPException(status_code=409, detail="El documento debe estar APROBADO para depositarse")
    blocking = _latest_blocking_validation(db, doc)
    if blocking is not None:
        raise AppError(
            NOT_DEPOSITABLE,
            "Existen errores de validacion bloqueantes en el documento; corrijalos antes de depositar",
            status_code=409,
        )
    collection = _resolve_collection(db, doc)
    if collection is None:
        raise HTTPException(
            status_code=409,
            detail="No hay un repositorio configurado para el tipo documental del documento",
        )
    repo = collection.repository
    if repo is None or not repo.active:
        raise HTTPException(status_code=409, detail="El repositorio destino no esta activo")
    prev = (
        db.query(Deposition)
        .filter(Deposition.document_id == doc.id, Deposition.status == "COMPLETED")
        .first()
    )
    if prev is not None:
        raise HTTPException(status_code=409, detail="El documento ya fue depositado")
    return collection, repo


def _latest_deposition(db: Session, document_id: uuid.UUID) -> Deposition | None:
    """La deposicion mas reciente del documento (por inicio e id)."""
    return (
        db.query(Deposition)
        .filter(Deposition.document_id == document_id)
        .order_by(Deposition.started_at.desc().nullsfirst(), Deposition.id.desc())
        .first()
    )


def _deposition_out(d: Deposition) -> DepositionOut:
    return DepositionOut(
        id=d.id,
        document_id=d.document_id,
        repository_id=d.repository_id,
        collection_id=d.collection_id,
        external_item_id=d.external_item_id,
        handle=d.handle,
        status=d.status,
        error_message=d.error_message,
        started_at=d.started_at,
        finished_at=d.finished_at,
    )


@router.post("/{document_id}/deposit", response_model=DepositRequestOut, status_code=202)
def request_deposit(
    document_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(can_deposit),
):
    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Documento no valido")
    doc = _get_doc(db, doc_uuid)
    collection, repo = _check_depositable(db, doc)
    job = _enqueue_deposit(db, doc)
    audit_log(
        db,
        user=user,
        action="deposit.request",
        entity_type="document",
        entity_id=str(doc.id),
        new_value={"job_id": str(job.id), "repository_id": str(repo.id), "collection": collection.name},
        **request_context(request),
    )
    db.commit()
    return DepositRequestOut(document_id=doc.id, status="PENDING", job_id=job.id)


@router.post("/{document_id}/deposit/retry", response_model=DepositRequestOut, status_code=202)
def retry_deposit(
    document_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(can_deposit),
):
    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Documento no valido")
    doc = _get_doc(db, doc_uuid)
    latest = _latest_deposition(db, doc.id)
    if latest is None or latest.status != "FAILED":
        raise HTTPException(
            status_code=409,
            detail="No hay un deposito fallido para reintentar",
        )
    collection, repo = _check_depositable(db, doc)
    job = _enqueue_deposit(db, doc)
    audit_log(
        db,
        user=user,
        action="deposit.retry",
        entity_type="document",
        entity_id=str(doc.id),
        new_value={
            "job_id": str(job.id),
            "repository_id": str(repo.id),
            "collection": collection.name,
            "previous_deposition_id": str(latest.id),
        },
        **request_context(request),
    )
    db.commit()
    return DepositRequestOut(document_id=doc.id, status="PENDING", job_id=job.id)


@router.get("/{document_id}/deposition", response_model=DepositionOut)
def get_latest_deposition(
    document_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(can_view),
):
    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Documento no valido")
    _get_doc(db, doc_uuid)
    latest = _latest_deposition(db, doc_uuid)
    if latest is None:
        raise HTTPException(status_code=404, detail="No hay depositos para el documento")
    return _deposition_out(latest)


@router.get("/{document_id}/depositions", response_model=list[DepositionOut])
def list_depositions(
    document_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(can_view),
):
    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Documento no valido")
    _get_doc(db, doc_uuid)
    deps = (
        db.query(Deposition)
        .filter(Deposition.document_id == doc_uuid)
        .order_by(Deposition.started_at.asc().nullsfirst(), Deposition.id.asc())
        .all()
    )
    return [_deposition_out(d) for d in deps]


@router.get("/{document_id}/snrd", response_model=SnrdExportOut)
def export_snrd(
    document_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(can_view),
):
    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Documento no valido")
    doc = _get_doc(db, doc_uuid)
    records = [
        r
        for r in doc.metadata_records
        if r.value and r.metadata_field is not None
    ]
    metadata = dc_fields(records, identifier=doc.sha256)
    return SnrdExportOut(
        document_id=doc.id,
        document_status=doc.status,
        scheme="snrd-dc",
        metadata=metadata,
    )


def _enqueue_deposit(db: Session, doc: Document) -> ProcessingJob:
    """Crea el job DEPOSIT y encola la tarea al worker."""
    job = ProcessingJob(document_id=doc.id, job_type="DEPOSIT", status="PENDING")
    db.add(job)
    db.commit()
    db.refresh(job)
    celery_app.send_task("app.jobs.tasks.deposit_document", args=[str(doc.id)])
    return job