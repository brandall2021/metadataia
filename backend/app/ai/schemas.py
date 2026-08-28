"""Schemas de administracion de IA: proveedores y modelos."""

from datetime import datetime

from pydantic import BaseModel, Field


# --- Proveedores -----------------------------------------------------------


class ProviderCreate(BaseModel):
    name: str = Field(min_length=1)
    code: str = Field(min_length=1)
    type: str = Field(min_length=1)
    base_url: str | None = None
    api_key: str | None = None
    active: bool = True
    configuration_json: dict | None = None


class ProviderUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    type: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    active: bool | None = None
    configuration_json: dict | None = None


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
    provider_id: str
    name: str = Field(min_length=1)
    model_identifier: str = Field(min_length=1)
    context_window: int | None = None
    supports_json: bool = False
    supports_vision: bool = False
    temperature_default: float | None = None
    max_tokens_default: int | None = None
    active: bool = True
    configuration_json: dict | None = None


class ModelUpdate(BaseModel):
    provider_id: str | None = None
    name: str | None = None
    model_identifier: str | None = None
    context_window: int | None = None
    supports_json: bool | None = None
    supports_vision: bool | None = None
    temperature_default: float | None = None
    max_tokens_default: int | None = None
    active: bool | None = None
    configuration_json: dict | None = None


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
    document_type_id: str | None = None
    active: bool = True
    model_id: str
    system_prompt: str | None = None
    extraction_prompt: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    output_schema_json: dict | None = None
    configuration_json: dict | None = None


class AgentUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    description: str | None = None
    document_type_id: str | None = None
    active: bool | None = None
    model_id: str | None = None
    system_prompt: str | None = None
    extraction_prompt: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    output_schema_json: dict | None = None
    configuration_json: dict | None = None


class AgentVersionCreate(BaseModel):
    model_id: str
    system_prompt: str | None = None
    extraction_prompt: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    output_schema_json: dict | None = None
    configuration_json: dict | None = None


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