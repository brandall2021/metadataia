"""Schemas de administracion de metadatos, vocabularios y tipos documentales (FASE 6)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SchemaCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    code: str = Field(min_length=1, max_length=100)
    namespace: str | None = Field(default=None, max_length=100)
    description: str | None = None
    active: bool = True
    version: int = 1

    @field_validator("name", "code", "namespace")
    @classmethod
    def strip_blank(cls, v):
        return v.strip() if isinstance(v, str) else v


class SchemaUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    namespace: str | None = Field(default=None, max_length=100)
    description: str | None = None
    active: bool | None = None
    version: int | None = None


class SchemaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    code: str
    namespace: str | None
    description: str | None
    active: bool
    version: int
    field_count: int = 0


class FieldCreate(BaseModel):
    schema_id: uuid.UUID
    element: str = Field(min_length=1, max_length=100)
    qualifier: str | None = Field(default=None, max_length=100)
    display_name: str | None = Field(default=None, max_length=255)
    description: str | None = None
    data_type: str = "text"
    required: bool = False
    repeatable: bool = False
    editable: bool = True
    ai_extractable: bool = True
    validation_type: str | None = Field(default=None, max_length=100)
    normalization_type: str | None = Field(default=None, max_length=100)
    vocabulary_id: uuid.UUID | None = None
    order_index: int | None = None
    active: bool = True

    @field_validator("element", "qualifier", "display_name")
    @classmethod
    def strip_blank(cls, v):
        return v.strip() if isinstance(v, str) else v


class FieldUpdate(BaseModel):
    element: str | None = Field(default=None, min_length=1, max_length=100)
    qualifier: str | None = Field(default=None, max_length=100)
    display_name: str | None = Field(default=None, max_length=255)
    description: str | None = None
    data_type: str | None = None
    required: bool | None = None
    repeatable: bool | None = None
    editable: bool | None = None
    ai_extractable: bool | None = None
    validation_type: str | None = Field(default=None, max_length=100)
    normalization_type: str | None = Field(default=None, max_length=100)
    vocabulary_id: uuid.UUID | None = None
    order_index: int | None = None
    active: bool | None = None


class FieldOut(BaseModel):
    id: uuid.UUID
    schema_id: uuid.UUID
    schema_name: str = ""
    schema_code: str = ""
    element: str
    qualifier: str | None
    display_name: str | None
    description: str | None
    data_type: str
    required: bool
    repeatable: bool
    editable: bool
    ai_extractable: bool
    validation_type: str | None
    normalization_type: str | None
    vocabulary_id: uuid.UUID | None
    vocabulary_code: str | None
    order_index: int | None
    active: bool


class VocabularyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    code: str = Field(min_length=1, max_length=100)
    description: str | None = None
    source: str | None = Field(default=None, max_length=200)
    active: bool = True


class VocabularyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = None
    source: str | None = Field(default=None, max_length=200)
    active: bool | None = None


class VocabularyOut(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    description: str | None
    source: str | None
    active: bool
    value_count: int = 0


class VocabularyValueCreate(BaseModel):
    code: str = Field(min_length=1, max_length=100)
    label: str = Field(min_length=1, max_length=255)
    normalized_value: str | None = None
    synonyms: list[str] = []
    active: bool = True


class VocabularyValueUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=100)
    label: str | None = Field(default=None, min_length=1, max_length=255)
    normalized_value: str | None = None
    synonyms: list[str] | None = None
    active: bool | None = None


class VocabularyValueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    vocabulary_id: uuid.UUID
    code: str
    label: str
    normalized_value: str | None
    synonyms: list[str] = []
    active: bool


class VocabularyImportResult(BaseModel):
    added: int
    updated: int
    total: int


class NormalizeRequest(BaseModel):
    value: str = Field(min_length=1)


class NormalizeResult(BaseModel):
    found: bool
    code: str | None = None
    label: str | None = None
    normalized_value: str | None = None


class DocumentTypeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    code: str = Field(min_length=1, max_length=100)
    description: str | None = None
    default_agent_id: uuid.UUID | None = None
    active: bool = True


class DocumentTypeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = None
    default_agent_id: uuid.UUID | None = None
    active: bool | None = None


class DocumentTypeFieldLink(BaseModel):
    field_id: uuid.UUID
    required_override: bool | None = None
    order_index: int | None = None


class DocumentTypeFieldsUpdate(BaseModel):
    fields: list[DocumentTypeFieldLink] = []


class DocumentTypeFieldOut(BaseModel):
    id: uuid.UUID
    schema_id: uuid.UUID
    schema_code: str
    element: str
    qualifier: str | None
    display_name: str | None
    data_type: str
    required: bool
    repeatable: bool
    ai_extractable: bool
    vocabulary_id: uuid.UUID | None
    vocabulary_code: str | None
    required_override: bool | None
    order_index: int | None
    extraction_instruction: str | None


class DocumentTypeOut(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    description: str | None
    default_agent_id: uuid.UUID | None
    default_agent_code: str | None
    default_agent_name: str | None
    active: bool
    created_at: datetime
    updated_at: datetime
    fields: list[DocumentTypeFieldOut] = []