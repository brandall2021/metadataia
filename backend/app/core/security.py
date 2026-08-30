"""Seguridad: hashing de passwords (bcrypt), JWT y cifrado de secretos (Fernet)."""

import base64
import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

# --- Passwords -------------------------------------------------------------


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


# --- JWT --------------------------------------------------------------------


def create_access_token(
    user_id: uuid.UUID, username: str, expires_minutes: int | None = None, version: int = 0
) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or settings.jwt_expire_minutes
    )
    payload = {
        "sub": str(user_id),
        "username": username,
        "jti": str(uuid.uuid4()),
        "version": version,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    """Decodifica y valida un JWT. Lanza jwt.PyJWTError en cualquier fallo."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


# --- Secretos (API Keys) ----------------------------------------------------


def _fernet() -> Fernet:
    key = base64.urlsafe_b64encode(
        hashlib.sha256(settings.app_secret_key.encode("utf-8")).digest()
    )
    return Fernet(key)


def encrypt_secret(value: str) -> str:
    """Cifra un secreto (API Key) en reposo. Cadena vacia -> vacia."""
    if not value:
        return ""
    return _fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(value: str | None) -> str | None:
    """Descifra un secreto. Si la clave cambio y no se puede descifrar, devuelve None."""
    if not value:
        return None
    try:
        return _fernet().decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        return None


def mask_secret(value: str | None) -> str:
    """Mascara un secreto para mostrar: nunca se expone completo (spec sec. 7)."""
    if not value:
        return ""
    if len(value) <= 4:
        return "*" * len(value)
    return "****" + value[-4:]