"""Rutas de administracion de IA (FASE 4-5): proveedores, modelos y agentes."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ai import client as ai_client
from app.ai.schemas import (
    AgentCreate,
    AgentOut,
    AgentUpdate,
    AgentVersionCreate,
    AgentVersionOut,
    ModelCreate,
    ModelOut,
    ModelUpdate,
    ProviderCreate,
    ProviderOut,
    ProviderUpdate,
    TestResult,
)
from app.core.database import get_db
from app.core.dependencies import require_permission
from app.core.security import decrypt_secret, encrypt_secret, mask_secret
from app.models import AIAgent, AIAgentVersion, AIModel, AIProvider, User

router = APIRouter(prefix="/admin/ai", tags=["ai"])

admin_providers = require_permission("admin.ai.providers.manage")
admin_models = require_permission("admin.ai.models.manage")
admin_agents = require_permission("admin.ai.agents.manage")


def _provider_out(provider: AIProvider) -> ProviderOut:
    decrypted = decrypt_secret(provider.api_key_encrypted)
    return ProviderOut(
        id=str(provider.id),
        name=provider.name,
        code=provider.code,
        type=provider.type,
        base_url=provider.base_url,
        active=provider.active,
        configuration_json=provider.configuration_json,
        api_key_masked=mask_secret(decrypted),
        created_at=provider.created_at,
        updated_at=provider.updated_at,
    )


def _get_provider(db: Session, provider_id: str) -> AIProvider:
    provider = db.get(AIProvider, uuid.UUID(provider_id))
    if provider is None:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    return provider


def _model_out(model: AIModel) -> ModelOut:
    return ModelOut(
        id=str(model.id),
        provider_id=str(model.provider_id),
        provider_name=model.provider.name,
        name=model.name,
        model_identifier=model.model_identifier,
        context_window=model.context_window,
        supports_json=model.supports_json,
        supports_vision=model.supports_vision,
        temperature_default=model.temperature_default,
        max_tokens_default=model.max_tokens_default,
        active=model.active,
        configuration_json=model.configuration_json,
    )


def _get_model(db: Session, model_id: str) -> AIModel:
    model = db.get(AIModel, uuid.UUID(model_id))
    if model is None:
        raise HTTPException(status_code=404, detail="Modelo no encontrado")
    return model


# --- Proveedores ------------------------------------------------------------


@router.get("/providers", response_model=list[ProviderOut])
def list_providers(_: AIProvider = Depends(admin_providers), db: Session = Depends(get_db)):
    providers = db.query(AIProvider).order_by(AIProvider.name).all()
    return [_provider_out(p) for p in providers]


@router.post("/providers", response_model=ProviderOut, status_code=201)
def create_provider(
    body: ProviderCreate,
    _: AIProvider = Depends(admin_providers),
    db: Session = Depends(get_db),
):
    provider = AIProvider(
        name=body.name,
        code=body.code,
        type=body.type,
        base_url=body.base_url,
        api_key_encrypted=encrypt_secret(body.api_key or ""),
        active=body.active,
        configuration_json=body.configuration_json,
    )
    db.add(provider)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="El codigo del proveedor ya existe")
    db.refresh(provider)
    return _provider_out(provider)


@router.get("/providers/{provider_id}", response_model=ProviderOut)
def get_provider(
    provider_id: str,
    _: AIProvider = Depends(admin_providers),
    db: Session = Depends(get_db),
):
    return _provider_out(_get_provider(db, provider_id))


@router.put("/providers/{provider_id}", response_model=ProviderOut)
def update_provider(
    provider_id: str,
    body: ProviderUpdate,
    _: AIProvider = Depends(admin_providers),
    db: Session = Depends(get_db),
):
    provider = _get_provider(db, provider_id)
    if body.name is not None:
        provider.name = body.name
    if body.code is not None:
        provider.code = body.code
    if body.type is not None:
        provider.type = body.type
    if body.base_url is not None:
        provider.base_url = body.base_url
    if body.api_key is not None:
        provider.api_key_encrypted = encrypt_secret(body.api_key)
    if body.active is not None:
        provider.active = body.active
    if body.configuration_json is not None:
        provider.configuration_json = body.configuration_json
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="El codigo del proveedor ya existe")
    db.refresh(provider)
    return _provider_out(provider)


@router.delete("/providers/{provider_id}", status_code=204)
def delete_provider(
    provider_id: str,
    _: AIProvider = Depends(admin_providers),
    db: Session = Depends(get_db),
):
    provider = _get_provider(db, provider_id)
    in_use = db.query(AIModel).filter(AIModel.provider_id == provider.id).count()
    if in_use > 0:
        raise HTTPException(
            status_code=409,
            detail="El proveedor esta siendo utilizado por modelos; no se puede eliminar",
        )
    db.delete(provider)
    db.commit()


@router.post("/providers/{provider_id}/test", response_model=TestResult)
def test_provider_connection(
    provider_id: str,
    _: AIProvider = Depends(admin_providers),
    db: Session = Depends(get_db),
):
    provider = _get_provider(db, provider_id)
    api_key = decrypt_secret(provider.api_key_encrypted)
    return TestResult(
        **ai_client.test_provider(provider.base_url, api_key, provider.type)
    )


# --- Modelos ----------------------------------------------------------------


@router.get("/models", response_model=list[ModelOut])
def list_models(_: AIModel = Depends(admin_models), db: Session = Depends(get_db)):
    models = db.query(AIModel).order_by(AIModel.name).all()
    return [_model_out(m) for m in models]


@router.post("/models", response_model=ModelOut, status_code=201)
def create_model(
    body: ModelCreate,
    _: AIModel = Depends(admin_models),
    db: Session = Depends(get_db),
):
    provider = _get_provider(db, body.provider_id)
    model = AIModel(
        provider_id=provider.id,
        name=body.name,
        model_identifier=body.model_identifier,
        context_window=body.context_window,
        supports_json=body.supports_json,
        supports_vision=body.supports_vision,
        temperature_default=body.temperature_default,
        max_tokens_default=body.max_tokens_default,
        active=body.active,
        configuration_json=body.configuration_json,
    )
    db.add(model)
    db.commit()
    db.refresh(model)
    return _model_out(model)


@router.put("/models/{model_id}", response_model=ModelOut)
def update_model(
    model_id: str,
    body: ModelUpdate,
    _: AIModel = Depends(admin_models),
    db: Session = Depends(get_db),
):
    model = _get_model(db, model_id)
    if body.provider_id is not None:
        model.provider_id = _get_provider(db, body.provider_id).id
    if body.name is not None:
        model.name = body.name
    if body.model_identifier is not None:
        model.model_identifier = body.model_identifier
    if body.context_window is not None:
        model.context_window = body.context_window
    if body.supports_json is not None:
        model.supports_json = body.supports_json
    if body.supports_vision is not None:
        model.supports_vision = body.supports_vision
    if body.temperature_default is not None:
        model.temperature_default = body.temperature_default
    if body.max_tokens_default is not None:
        model.max_tokens_default = body.max_tokens_default
    if body.active is not None:
        model.active = body.active
    if body.configuration_json is not None:
        model.configuration_json = body.configuration_json
    db.commit()
    db.refresh(model)
    return _model_out(model)


@router.delete("/models/{model_id}", status_code=204)
def delete_model(
    model_id: str,
    _: AIModel = Depends(admin_models),
    db: Session = Depends(get_db),
):
    model = _get_model(db, model_id)
    db.delete(model)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="El modelo esta siendo utilizado por agentes; no se puede eliminar",
        )


@router.post("/models/{model_id}/test", response_model=TestResult)
def test_model_call(
    model_id: str,
    _: AIModel = Depends(admin_models),
    db: Session = Depends(get_db),
):
    model = _get_model(db, model_id)
    provider = model.provider
    api_key = decrypt_secret(provider.api_key_encrypted)
    return TestResult(
        **ai_client.test_model(
            provider.base_url,
            api_key,
            model.model_identifier,
            provider.type,
            max_tokens=model.max_tokens_default,
        )
    )


# --- Agentes ----------------------------------------------------------------


def _get_agent(db: Session, agent_id: str) -> AIAgent:
    agent = db.get(AIAgent, uuid.UUID(agent_id))
    if agent is None:
        raise HTTPException(status_code=404, detail="Agente no encontrado")
    return agent


def _version_out(version: AIAgentVersion) -> AgentVersionOut:
    return AgentVersionOut(
        id=str(version.id),
        agent_id=str(version.agent_id),
        version_number=version.version_number,
        model_id=str(version.model_id),
        model_name=version.model.name,
        model_identifier=version.model.model_identifier,
        system_prompt=version.system_prompt,
        extraction_prompt=version.extraction_prompt,
        temperature=version.temperature,
        max_tokens=version.max_tokens,
        output_schema_json=version.output_schema_json,
        configuration_json=version.configuration_json,
        active=version.active,
        created_at=version.created_at,
    )


def _agent_out(agent: AIAgent) -> AgentOut:
    current = agent.current_version
    return AgentOut(
        id=str(agent.id),
        name=agent.name,
        code=agent.code,
        description=agent.description,
        document_type_id=str(agent.document_type_id) if agent.document_type_id else None,
        active=agent.active,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
        current_version=_version_out(current) if current else None,
    )


def _create_version(
    db: Session,
    agent: AIAgent,
    model_id: str,
    system_prompt: str | None = None,
    extraction_prompt: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    output_schema_json: dict | None = None,
    configuration_json: dict | None = None,
    created_by: uuid.UUID | None = None,
) -> AIAgentVersion:
    model = _get_model(db, model_id)
    max_number = (
        db.query(func.max(AIAgentVersion.version_number))
        .filter(AIAgentVersion.agent_id == agent.id)
        .scalar()
        or 0
    )
    version = AIAgentVersion(
        agent_id=agent.id,
        version_number=int(max_number) + 1,
        model_id=model.id,
        system_prompt=system_prompt,
        extraction_prompt=extraction_prompt,
        temperature=temperature,
        max_tokens=max_tokens,
        output_schema_json=output_schema_json,
        configuration_json=configuration_json,
        created_by=created_by,
    )
    db.add(version)
    db.flush()
    agent.current_version = version  # post_update: se actualiza la FK circular
    return version


@router.get("/agents", response_model=list[AgentOut])
def list_agents(_: AIAgent = Depends(admin_agents), db: Session = Depends(get_db)):
    agents = db.query(AIAgent).order_by(AIAgent.name).all()
    return [_agent_out(a) for a in agents]


@router.post("/agents", response_model=AgentOut, status_code=201)
def create_agent(
    body: AgentCreate,
    user: User = Depends(admin_agents),
    db: Session = Depends(get_db),
):
    agent = AIAgent(
        name=body.name,
        code=body.code,
        description=body.description,
        document_type_id=uuid.UUID(body.document_type_id) if body.document_type_id else None,
        active=body.active,
    )
    db.add(agent)
    try:
        db.flush()
        _create_version(
            db,
            agent,
            body.model_id,
            body.system_prompt,
            body.extraction_prompt,
            body.temperature,
            body.max_tokens,
            body.output_schema_json,
            body.configuration_json,
            created_by=user.id,
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="El codigo del agente ya existe")
    db.refresh(agent)
    return _agent_out(agent)


@router.get("/agents/{agent_id}", response_model=AgentOut)
def get_agent(
    agent_id: str,
    _: AIAgent = Depends(admin_agents),
    db: Session = Depends(get_db),
):
    return _agent_out(_get_agent(db, agent_id))


@router.put("/agents/{agent_id}", response_model=AgentOut)
def update_agent(
    agent_id: str,
    body: AgentUpdate,
    user: User = Depends(admin_agents),
    db: Session = Depends(get_db),
):
    agent = _get_agent(db, agent_id)
    if body.name is not None:
        agent.name = body.name
    if body.code is not None:
        agent.code = body.code
    if body.description is not None:
        agent.description = body.description
    if body.document_type_id is not None:
        agent.document_type_id = uuid.UUID(body.document_type_id)
    if body.active is not None:
        agent.active = body.active

    version_fields = {
        "model_id": body.model_id,
        "system_prompt": body.system_prompt,
        "extraction_prompt": body.extraction_prompt,
        "temperature": body.temperature,
        "max_tokens": body.max_tokens,
        "output_schema_json": body.output_schema_json,
        "configuration_json": body.configuration_json,
    }
    if any(v is not None for v in version_fields.values()):
        base = agent.current_version
        model_id = body.model_id or (str(base.model_id) if base else None)
        if model_id is None:
            raise HTTPException(status_code=422, detail="Se requiere model_id o una version previa")
        _create_version(
            db,
            agent,
            model_id,
            body.system_prompt if body.system_prompt is not None else (base.system_prompt if base else None),
            body.extraction_prompt if body.extraction_prompt is not None else (base.extraction_prompt if base else None),
            body.temperature if body.temperature is not None else (base.temperature if base else None),
            body.max_tokens if body.max_tokens is not None else (base.max_tokens if base else None),
            body.output_schema_json if body.output_schema_json is not None else (base.output_schema_json if base else None),
            body.configuration_json if body.configuration_json is not None else (base.configuration_json if base else None),
            created_by=user.id,
        )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="El codigo del agente ya existe")
    db.refresh(agent)
    return _agent_out(agent)


@router.get("/agents/{agent_id}/versions", response_model=list[AgentVersionOut])
def list_agent_versions(
    agent_id: str,
    _: AIAgent = Depends(admin_agents),
    db: Session = Depends(get_db),
):
    agent = _get_agent(db, agent_id)
    versions = (
        db.query(AIAgentVersion)
        .filter(AIAgentVersion.agent_id == agent.id)
        .order_by(AIAgentVersion.version_number.desc())
        .all()
    )
    return [_version_out(v) for v in versions]


@router.post("/agents/{agent_id}/versions", response_model=AgentVersionOut, status_code=201)
def create_agent_version(
    agent_id: str,
    body: AgentVersionCreate,
    user: User = Depends(admin_agents),
    db: Session = Depends(get_db),
):
    agent = _get_agent(db, agent_id)
    version = _create_version(
        db,
        agent,
        body.model_id,
        body.system_prompt,
        body.extraction_prompt,
        body.temperature,
        body.max_tokens,
        body.output_schema_json,
        body.configuration_json,
        created_by=user.id,
    )
    db.commit()
    db.refresh(version)
    return _version_out(version)


@router.post("/agents/{agent_id}/clone", response_model=AgentOut, status_code=201)
def clone_agent(
    agent_id: str,
    user: User = Depends(admin_agents),
    db: Session = Depends(get_db),
):
    agent = _get_agent(db, agent_id)
    base = agent.current_version
    if base is None:
        raise HTTPException(status_code=422, detail="El agente no tiene version para clonar")
    clone = AIAgent(
        name=f"{agent.name} (copia)",
        code=f"{agent.code}-copia",
        description=agent.description,
        document_type_id=agent.document_type_id,
        active=False,
    )
    db.add(clone)
    try:
        db.flush()
        _create_version(
            db,
            clone,
            str(base.model_id),
            base.system_prompt,
            base.extraction_prompt,
            base.temperature,
            base.max_tokens,
            base.output_schema_json,
            base.configuration_json,
            created_by=user.id,
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Ya existe un agente con ese codigo")
    db.refresh(clone)
    return _agent_out(clone)


@router.delete("/agents/{agent_id}", status_code=204)
def delete_agent(
    agent_id: str,
    _: AIAgent = Depends(admin_agents),
    db: Session = Depends(get_db),
):
    agent = _get_agent(db, agent_id)
    db.delete(agent)  # versiones en cascada (ondelete CASCADE)
    db.commit()


@router.post("/agents/{agent_id}/test", response_model=TestResult)
def test_agent(
    agent_id: str,
    _: AIAgent = Depends(admin_agents),
    db: Session = Depends(get_db),
):
    agent = _get_agent(db, agent_id)
    version = agent.current_version
    if version is None:
        raise HTTPException(status_code=422, detail="El agente no tiene una version activa")
    provider = version.model.provider
    api_key = decrypt_secret(provider.api_key_encrypted)
    return TestResult(
        **ai_client.test_agent_prompt(
            provider.base_url,
            api_key,
            version.model.model_identifier,
            provider.type,
            version.system_prompt,
            version.extraction_prompt,
            max_tokens=version.max_tokens,
        )
    )