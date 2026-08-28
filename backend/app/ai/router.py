"""Rutas de administracion de IA (FASE 4): proveedores y modelos."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ai import client as ai_client
from app.ai.schemas import (
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
from app.models import AIModel, AIProvider

router = APIRouter(prefix="/admin/ai", tags=["ai"])

admin_providers = require_permission("admin.ai.providers.manage")
admin_models = require_permission("admin.ai.models.manage")


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