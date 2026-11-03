"""Schemas de administracion de IA: proveedores y modelos."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

PROVIDER_TYPES = {
    "openai",
    "openai-compatible",
    "ollama",
    "anthropic",
    "google",
    "azure-openai",
}


# --- Proveedores -----------------------------------------------------------


class ProviderCreate(BaseModel):
    name: str = Field(min_length=1)
    code: str = Field(min_length=1)
    type: str = Field(min_length=1)
    base_url: str | None = None
    api_key: str | None = None
    active: bool = True
    configuration_json: dict | None = None

    @field_validator("name", "code", "type", "base_url", "api_key")
    @classmethod
    def strip_blank(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("type")
    @classmethod
    def supported_type(cls, value: str) -> str:
        if value not in PROVIDER_TYPES:
            raise ValueError(f"Tipo de proveedor no soportado: {value}")
        return value


class ProviderUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    type: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    active: bool | None = None
    configuration_json: dict | None = None

    @field_validator("name", "code", "type", "base_url", "api_key")
    @classmethod
    def strip_blank(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("type")
    @classmethod
    def supported_type(cls, value: str | None) -> str | None:
        if value is not None and value not in PROVIDER_TYPES:
            raise ValueError(f"Tipo de proveedor no soportado: {value}")
        return value


class ProviderOut(BaseModel):
    id: str
    name: str
    code: str
    type: str
    base_url: str | None = None
    active: bool
    configuration_json: dict | None = None
    api_key_masked: str = ""
    created_at: datetime
    updated_at: datetime


# --- Modelos ----------------------------------------------------------------


class ModelCreate(BaseModel):
    provider_id: uuid.UUID
    name: str = Field(min_length=1)
    model_identifier: str = Field(min_length=1)
    context_window: int | None = Field(default=None, ge=1)
    supports_json: bool = False
    supports_vision: bool = False
    temperature_default: float | None = Field(default=None, ge=0, le=2)
    max_tokens_default: int | None = Field(default=None, ge=1)
    active: bool = True
    configuration_json: dict | None = None

    @field_validator("name", "model_identifier")
    @classmethod
    def strip_blank(cls, value):
        return value.strip() if isinstance(value, str) else value


class ModelUpdate(BaseModel):
    provider_id: uuid.UUID | None = None
    name: str | None = None
    model_identifier: str | None = None
    context_window: int | None = Field(default=None, ge=1)
    supports_json: bool | None = None
    supports_vision: bool | None = None
    temperature_default: float | None = Field(default=None, ge=0, le=2)
    max_tokens_default: int | None = Field(default=None, ge=1)
    active: bool | None = None
    configuration_json: dict | None = None

    @field_validator("name", "model_identifier")
    @classmethod
    def strip_blank(cls, value):
        return value.strip() if isinstance(value, str) else value


class ModelOut(BaseModel):
    id: str
    provider_id: str
    provider_name: str
    name: str
    model_identifier: str
    context_window: int | None = None
    supports_json: bool
    supports_vision: bool
    temperature_default: float | None = None
    max_tokens_default: int | None = None
    active: bool
    configuration_json: dict | None = None


# --- Resultado de pruebas ----------------------------------------------------


class TestResult(BaseModel):
    ok: bool
    message: str
    time_ms: float
    detail: str | None = None


# --- Agentes ----------------------------------------------------------------


class AgentCreate(BaseModel):
    name: str = Field(min_length=1)
    code: str = Field(min_length=1)
    description: str | None = None
    document_type_id: uuid.UUID | None = None
    active: bool = True
    model_id: uuid.UUID
    system_prompt: str | None = None
    extraction_prompt: str | None = None
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=1)
    output_schema_json: dict | None = None
    configuration_json: dict | None = None

    @field_validator("name", "code", "description", "system_prompt", "extraction_prompt")
    @classmethod
    def strip_blank(cls, value):
        return value.strip() if isinstance(value, str) else value


class AgentUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    description: str | None = None
    document_type_id: uuid.UUID | None = None
    active: bool | None = None
    model_id: uuid.UUID | None = None
    system_prompt: str | None = None
    extraction_prompt: str | None = None
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=1)
    output_schema_json: dict | None = None
    configuration_json: dict | None = None

    @field_validator("name", "code", "description", "system_prompt", "extraction_prompt")
    @classmethod
    def strip_blank(cls, value):
        return value.strip() if isinstance(value, str) else value


class AgentVersionCreate(BaseModel):
    model_id: uuid.UUID
    system_prompt: str | None = None
    extraction_prompt: str | None = None
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=1)
    output_schema_json: dict | None = None
    configuration_json: dict | None = None

    @field_validator("system_prompt", "extraction_prompt")
    @classmethod
    def strip_blank(cls, value):
        return value.strip() if isinstance(value, str) else value


class AgentVersionOut(BaseModel):
    id: str
    agent_id: str
    version_number: int
    model_id: str
    model_name: str
    model_identifier: str
    system_prompt: str | None = None
    extraction_prompt: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    output_schema_json: dict | None = None
    configuration_json: dict | None = None
    active: bool
    created_at: datetime


class AgentOut(BaseModel):
    id: str
    name: str
    code: str
    description: str | None = None
    document_type_id: str | None = None
    active: bool
    created_at: datetime
    updated_at: datetime
    current_version: AgentVersionOut | None = None


# --- Descubrimiento e importacion de modelos --------------------------------


class DiscoveredModel(BaseModel):
    id: str
    owned_by: str | None = None
    created: int | None = None


class ProviderModelsOut(BaseModel):
    ok: bool
    message: str
    models: list[DiscoveredModel] = Field(default_factory=list)
    detail: str | None = None


class ModelImportItem(BaseModel):
    model_identifier: str = Field(min_length=1)
    name: str | None = None
    context_window: int | None = Field(default=None, ge=1)
    supports_json: bool = False
    supports_vision: bool = False

    @field_validator("model_identifier", "name")
    @classmethod
    def strip_blank(cls, value):
        return value.strip() if isinstance(value, str) else value


class ModelImportRequest(BaseModel):
    models: list[ModelImportItem] = Field(min_length=1)


class ModelImportOut(BaseModel):
    created: list[ModelOut]
    skipped: list[str] = Field(default_factory=list)
