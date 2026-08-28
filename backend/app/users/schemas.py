"""Schemas de usuarios, roles y permisos."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    username: str = Field(min_length=1)
    email: EmailStr
    password: str
    first_name: str | None = None
    last_name: str | None = None
    active: bool = True
    role_codes: list[str] = []


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    password: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    active: bool | None = None
    role_codes: list[str] | None = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    email: str
    first_name: str | None = None
    last_name: str | None = None
    active: bool
    created_at: datetime
    updated_at: datetime
    roles: list[str] = []


class RoleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None = None
    permissions: list[str] = []


class RoleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class RolePermissionsUpdate(BaseModel):
    permission_codes: list[str]