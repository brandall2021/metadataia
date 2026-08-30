"""Rutas de usuarios y roles (FASE 3, RBAC). Solo administradores."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.core.security import hash_password
from app.models import Permission, Role, User
from app.users.schemas import (
    RoleOut,
    RolePermissionsUpdate,
    RoleUpdate,
    UserCreate,
    UserOut,
    UserUpdate,
)

router = APIRouter(tags=["users"])

admin_users = require_permission("admin.users.manage")
admin_roles = require_permission("admin.roles.manage")


def _user_out(user: User) -> UserOut:
    return UserOut(
        id=str(user.id),
        username=user.username,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        active=user.active,
        created_at=user.created_at,
        updated_at=user.updated_at,
        roles=[role.name for role in user.roles],
    )


def _role_out(role: Role) -> RoleOut:
    return RoleOut(
        id=str(role.id),
        name=role.name,
        description=role.description,
        permissions=sorted({p.code for p in role.permissions}),
    )


def _get_user_by_id(db: Session, user_id: str) -> User:
    user = db.get(User, uuid.UUID(user_id))
    if user is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return user


def _apply_roles(db: Session, user: User, role_codes: list[str] | None) -> None:
    if role_codes is None:
        return
    roles = db.query(Role).filter(Role.name.in_(role_codes)).all()
    if len(roles) != len(set(role_codes)):
        raise HTTPException(status_code=422, detail="Algun rol indicado no existe")
    user.roles = roles


# --- Usuarios --------------------------------------------------------------


@router.get("/users", response_model=list[UserOut])
def list_users(_: User = Depends(admin_users), db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.username).all()
    return [_user_out(u) for u in users]


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(body: UserCreate, _: User = Depends(admin_users), db: Session = Depends(get_db)):
    user = User(
        username=body.username,
        email=body.email,
        password_hash=hash_password(body.password),
        first_name=body.first_name,
        last_name=body.last_name,
        active=body.active,
    )
    db.add(user)
    try:
        db.flush()
        _apply_roles(db, user, body.role_codes)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="El nombre de usuario o email ya esta en uso"
        )
    db.refresh(user)
    return _user_out(user)


@router.put("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: str,
    body: UserUpdate,
    user: User = Depends(admin_users),
    db: Session = Depends(get_db),
):
    target = _get_user_by_id(db, user_id)
    if target.id == user.id:
        if body.active is False:
            raise HTTPException(status_code=400, detail="No puede desactivarse a si mismo")
        if body.role_codes is not None and "ADMIN" not in body.role_codes:
            raise HTTPException(
                status_code=400, detail="No puede quitarse el rol de administrador a si mismo"
            )
    if body.email is not None:
        target.email = body.email
    if body.password is not None:
        target.password_hash = hash_password(body.password)
        target.token_version += 1
    if body.first_name is not None:
        target.first_name = body.first_name
    if body.last_name is not None:
        target.last_name = body.last_name
    if body.active is not None:
        target.active = body.active
        if not body.active:
            target.token_version += 1
    if body.role_codes is not None:
        _apply_roles(db, target, body.role_codes)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="El email ya esta en uso")
    db.refresh(target)
    return _user_out(target)


@router.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: str, user: User = Depends(admin_users), db: Session = Depends(get_db)):
    target = _get_user_by_id(db, user_id)
    if target.id == user.id:
        raise HTTPException(status_code=400, detail="No puede eliminarse a si mismo")
    db.delete(target)
    db.commit()


# --- Roles y permisos ------------------------------------------------------


@router.get("/roles", response_model=list[RoleOut])
def list_roles(_: User = Depends(admin_roles), db: Session = Depends(get_db)):
    roles = db.query(Role).order_by(Role.name).all()
    return [_role_out(r) for r in roles]


@router.put("/roles/{role_id}", response_model=RoleOut)
def update_role(
    role_id: str,
    body: RoleUpdate,
    _: User = Depends(admin_roles),
    db: Session = Depends(get_db),
):
    role = db.get(Role, uuid.UUID(role_id))
    if role is None:
        raise HTTPException(status_code=404, detail="Rol no encontrado")
    if body.name is not None:
        role.name = body.name
    if body.description is not None:
        role.description = body.description
    db.commit()
    db.refresh(role)
    return _role_out(role)


@router.put("/roles/{role_id}/permissions", response_model=RoleOut)
def update_role_permissions(
    role_id: str,
    body: RolePermissionsUpdate,
    _: User = Depends(admin_roles),
    db: Session = Depends(get_db),
):
    role = db.get(Role, uuid.UUID(role_id))
    if role is None:
        raise HTTPException(status_code=404, detail="Rol no encontrado")
    permissions = db.query(Permission).filter(Permission.code.in_(body.permission_codes)).all()
    if len(permissions) != len(set(body.permission_codes)):
        raise HTTPException(status_code=422, detail="Algun permiso indicado no existe")
    role.permissions = permissions
    db.commit()
    db.refresh(role)
    return _role_out(role)