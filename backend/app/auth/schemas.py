"""Schemas del modulo de autenticacion."""

from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserMe(BaseModel):
    id: str
    username: str
    email: str
    first_name: str | None = None
    last_name: str | None = None
    roles: list[str] = []
    permissions: list[str] = []