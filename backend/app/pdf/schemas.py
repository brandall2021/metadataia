"""Schemas de documentos y su analisis (FASE 7)."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class DocumentPageOut(BaseModel):
    id: uuid.UUID
    page_number: int
    text: str | None
    text_length: int | None
    ocr_used: bool


class DocumentOut(BaseModel):
    id: uuid.UUID
    original_filename: str | None
    mime_type: str | None
    file_size: int | None
    sha256: str | None
    page_count: int | None
    needs_ocr: bool
    status: str
    created_at: datetime


class DocumentDetailOut(DocumentOut):
    document_type_id: uuid.UUID | None
    pages: list[DocumentPageOut] = []
    analysis: dict = {}