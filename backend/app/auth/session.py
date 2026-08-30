"""Gestion de sesiones: revocacion de JWT por jti (FASE 17).

Un JWT es stateless, pero para permitir logout real se mantiene una tabla de
tokens revocados (revoked_tokens). Todo endpoint autenticado pasa por
get_current_user, que rechaza cualquier token cuyo jti este registrado.
"""

from datetime import datetime, timezone

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models import RevokedToken


def token_is_revoked(db: Session, jti: str | None) -> bool:
    """Devuelve True si el jti fue revocado (logout)."""
    if not jti:
        return False
    return db.get(RevokedToken, jti) is not None


def revoke_token(db: Session, jti: str, user_id, expires_at: datetime) -> None:
    """Registra un jti como revocado y limpia tokens ya expirados."""
    db.execute(delete(RevokedToken).where(RevokedToken.expires_at <= datetime.now(timezone.utc)))
    db.add(RevokedToken(jti=jti, user_id=user_id, expires_at=expires_at))
    db.flush()