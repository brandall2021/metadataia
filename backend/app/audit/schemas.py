"""Esquemas de auditoria (FASE 14)."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class AuditLogOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None = None
    username: str | None = None
    action: str
    entity_type: str | None = None
    entity_id: str | None = None
    old_value: dict | None = None
    new_value: dict | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    created_at: datetime


class AuditCollectionOut(BaseModel):
    items: list[AuditLogOut]
    total: int
    limit: int
    offset: int


class HistoryItemOut(BaseModel):
    type: str
    id: str
    at: datetime | None = None
    action: str | None = None
    user: str | None = None
    status: str | None = None
    job_type: str | None = None
    error: str | None = None
    external_item_id: str | None = None
    handle: str | None = None
    old_value: dict | None = None
    new_value: dict | None = None
    metadata: dict | None = None