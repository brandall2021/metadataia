"""Rutas de autenticacion (FASE 3): login, refresh, logout y /me."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.auth.schemas import LoginRequest, TokenResponse, UserMe
from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import security, get_current_user
from app.core.security import create_access_token, decode_token, verify_password
from app.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


def _token_response(user: User) -> TokenResponse:
    token = create_access_token(user.id, user.username)
    return TokenResponse(
        access_token=token,
        expires_in=settings.jwt_expire_minutes * 60,
    )


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(User).filter(User.username == body.username).one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Credenciales invalidas")
    if not user.active:
        raise HTTPException(status_code=403, detail="Usuario inactivo")
    return _token_response(user)


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> TokenResponse:
    if credentials is None:
        raise HTTPException(status_code=401, detail="No autenticado")
    try:
        payload = decode_token(credentials.credentials)
    except Exception:
        raise HTTPException(status_code=401, detail="Token invalido o expirado")
    token = create_access_token(
        payload["sub"], payload.get("username", ""), expires_minutes=None
    )
    return TokenResponse(
        access_token=token,
        expires_in=settings.jwt_expire_minutes * 60,
    )


@router.post("/logout")
def logout(credentials: HTTPAuthorizationCredentials | None = Depends(security)):
    if credentials is None:
        raise HTTPException(status_code=401, detail="No autenticado")
    # JWT stateless: el cliente descarta el token. Revocacion real en FASE 17.
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