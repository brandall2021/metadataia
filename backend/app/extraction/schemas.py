"""Schemas de extraccion de metadatos con IA (FASE 9)."""

from datetime import datetime

from pydantic import BaseModel


class MetadataRecordOut(BaseModel):
    id: str
    metadata_field_id: str
    field: str
    display_name: str
    value: str | None
    language: str | None
    confidence: float | None
    source: str | None
    source_page: int | None
    source_text: str | None
    extraction_run_id: str | None
    normalized: bool
    validated: bool
    manually_modified: bool


class ExtractionRunOut(BaseModel):
    id: str
    agent_id: str | None
    agent_version_id: str | None
    model_id: str | None
    prompt_hash: str | None
    started_at: datetime | None
    finished_at: datetime | None
    input_tokens: int | None
    output_tokens: int | None
    status: str
    raw_response_storage_path: str | None
    error_message: str | None
    summary: dict = {}


class ExtractionRequestOut(BaseModel):
    status: str
    job_id: str
    document_id: str
    message: str


class MetadataCollectionOut(BaseModel):
    document_id: str
    document_status: str
    runs: list[ExtractionRunOut]
    records: list[MetadataRecordOut]