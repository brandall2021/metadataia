"""Rutas de autenticacion (FASE 3): login, refresh, logout y /me."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.audit.service import audit_log, request_context
from app.auth.schemas import LoginRequest, TokenResponse, UserMe
from app.auth.session import revoke_token, token_is_revoked
from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import security, get_current_user
from app.core.errors import AppError
from app.core.ratelimit import rate_limit
from app.core.security import create_access_token, decode_token, verify_password
from app.models import User

router = APIRouter(prefix="/auth", tags=["auth"])

# Codigos de error estandar (seccion 33): aditivos sobre el codigo HTTP.
AUTH_INVALID_CREDENTIALS = "AUTH_INVALID_CREDENTIALS"
AUTH_USER_INACTIVE = "AUTH_USER_INACTIVE"
AUTH_NOT_AUTHENTICATED = "AUTH_NOT_AUTHENTICATED"
AUTH_INVALID_TOKEN = "AUTH_INVALID_TOKEN"

LOGIN_RATE_LIMIT = (10, 300)  # 10 intentos / 300 s por IP
REFRESH_RATE_LIMIT = (30, 300)


def _token_response(user: User) -> TokenResponse:
    token = create_access_token(user.id, user.username, version=user.token_version)
    return TokenResponse(
        access_token=token,
        expires_in=settings.jwt_expire_minutes * 60,
    )


@router.post("/login", response_model=TokenResponse)
def login(
    body: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
    _rate: None = Depends(rate_limit(*LOGIN_RATE_LIMIT)),
) -> TokenResponse:
    user = db.query(User).filter(User.username == body.username).one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise AppError(
            AUTH_INVALID_CREDENTIALS,
            "Credenciales invalidas",
            status_code=401,
            detail="Credenciales invalidas",
        )
    if not user.active:
        raise AppError(
            AUTH_USER_INACTIVE,
            "Usuario inactivo",
            status_code=403,
            detail="Usuario inactivo",
        )
    audit_log(
        db,
        user=user,
        action="auth.login",
        entity_type="user",
        entity_id=str(user.id),
        new_value={"username": user.username},
        **request_context(request),
    )
    db.commit()
    return _token_response(user)


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    user: User = Depends(get_current_user),
    _rate: None = Depends(rate_limit(*REFRESH_RATE_LIMIT)),
) -> TokenResponse:
    return _token_response(user)


@router.post("/logout")
def logout(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
):
    if credentials is None:
        raise AppError(
            AUTH_NOT_AUTHENTICATED, "No autenticado", status_code=401, detail="No autenticado"
        )
    try:
        payload = decode_token(credentials.credentials)
    except Exception:
        raise AppError(
            AUTH_INVALID_TOKEN,
            "Token invalido o expirado",
            status_code=401,
            detail="Token invalido o expirado",
        )
    if payload.get("jti") and not token_is_revoked(db, payload.get("jti")):
        user = db.get(User, uuid.UUID(payload["sub"])) if payload.get("sub") else None
        if user is not None:
            revoke_token(db, payload["jti"], user.id, datetime.fromtimestamp(payload["exp"], tz=timezone.utc))
            audit_log(
                db,
                user=user,
                action="auth.logout",
                entity_type="user",
                entity_id=str(user.id),
                new_value={"username": user.username},
                **request_context(request),
            )
        db.commit()
    return {"message": "Sesion cerrada"}


@router.get("/me", response_model=UserMe)
def me(user: User = Depends(get_current_user)) -> UserMe:
    return UserMe(
        id=str(user.id),
        username=user.username,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        roles=[role.name for role in user.roles],
        permissions=sorted({p.code for role in user.roles for p in role.permissions}),
    )