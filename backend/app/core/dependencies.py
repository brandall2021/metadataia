"""Dependencias de autenticacion y autorizacion (RBAC)."""

import uuid

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token
from app.models import User

security = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """Obtiene el usuario autenticado a partir del Bearer token."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_token(credentials.credentials)
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalido")
    user = db.get(User, uuid.UUID(user_id))
    if user is None or not user.active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario inactivo")
    return user


def require_permission(code: str):
    """Dependencia que exige un permiso concreto del usuario autenticado."""

    def _dependency(user: User = Depends(get_current_user)) -> User:
        allowed = {p.code for role in user.roles for p in role.permissions}
        if code not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tiene permisos para esta operacion",
            )
        return user

    return _dependency