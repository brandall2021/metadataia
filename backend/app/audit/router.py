"""Consulta de auditoria (FASE 14).

- ``GET /api/admin/audit``: registros con filtros (solo ADMIN, permiso
  ``audit.view``) y paginacion.
- ``GET /api/documents/{id}/history``: linea de tiempo de un documento
  combinando auditoria, jobs del pipeline y deposiciones.
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import UUID4
from sqlalchemy.orm import Session

from app.audit.schemas import AuditCollectionOut, AuditLogOut, HistoryItemOut
from app.core.database import get_db
from app.core.dependencies import require_permission
from app.models import AuditLog, Deposition, Document, User

router = APIRouter(prefix="/admin/audit", tags=["audit"])
history_router = APIRouter(prefix="/documents", tags=["audit"])

can_view_audit = require_permission("audit.view")
can_view = require_permission("document.view")


def _usernames(db: Session, entries: list[AuditLog]) -> dict:
    uids = {e.user_id for e in entries if e.user_id is not None}
    if not uids:
        return {}
    rows = db.query(User.id, User.username).filter(User.id.in_(uids)).all()
    return {uid: name for uid, name in rows}


@router.get("", response_model=AuditCollectionOut)
def list_audit(  # noqa: PLR0913 - parametros de filtrado del listado
    action: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    user_id: UUID4 | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(can_view_audit),
):
    q = db.query(AuditLog)
    if action:
        q = q.filter(AuditLog.action == action)
    if entity_type:
        q = q.filter(AuditLog.entity_type == entity_type)
    if entity_id:
        q = q.filter(AuditLog.entity_id == entity_id)
    if user_id is not None:
        q = q.filter(AuditLog.user_id == user_id)
    if from_date is not None:
        q = q.filter(AuditLog.created_at >= from_date)
    if to_date is not None:
        q = q.filter(AuditLog.created_at <= to_date)

    total = q.count()
    entries = (
        q.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    names = _usernames(db, entries)
    return AuditCollectionOut(
        items=[
            AuditLogOut(
                id=e.id,
                user_id=e.user_id,
                username=names.get(e.user_id),
                action=e.action,
                entity_type=e.entity_type,
                entity_id=e.entity_id,
                old_value=e.old_value_json,
                new_value=e.new_value_json,
                ip_address=e.ip_address,
                user_agent=e.user_agent,
                created_at=e.created_at,
            )
            for e in entries
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@history_router.get("/{document_id}/history", response_model=list[HistoryItemOut])
def document_history(
    document_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(can_view),
):
    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Documento no valido")
    doc = db.get(Document, doc_uuid)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento no encontrado")

    items: list[HistoryItemOut] = []

    audits = (
        db.query(AuditLog)
        .filter(AuditLog.entity_id == str(doc.id))
        .order_by(AuditLog.created_at.asc())
        .all()
    )
    if audits:
        names = _usernames(db, audits)
        for a in audits:
            items.append(
                HistoryItemOut(
                    type="audit",
                    id=str(a.id),
                    at=a.created_at,
                    action=a.action,
                    user=names.get(a.user_id),
                    old_value=a.old_value_json,
                    new_value=a.new_value_json,
                )
            )

    for j in sorted(doc.jobs, key=lambda j: (j.created_at or j.started_at) or j.id):
        items.append(
            HistoryItemOut(
                type="job",
                id=str(j.id),
                at=j.created_at or j.started_at,
                job_type=j.job_type,
                status=j.status,
                error=j.error_message,
                metadata=(j.metadata_json or {}),
            )
        )

    for d in sorted(doc.depositions, key=lambda d: d.started_at or d.id):
        items.append(
            HistoryItemOut(
                type="deposition",
                id=str(d.id),
                at=d.started_at or d.finished_at,
                status=d.status,
                error=d.error_message,
                external_item_id=d.external_item_id,
                handle=d.handle,
                metadata=d.response_json,
            )
        )

    items.sort(key=lambda i: (i.at is not None, i.at), reverse=True)
    return items