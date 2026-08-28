"""Datos iniciales (seed): usuarios, roles y permisos.

Idempotente: puede ejecutarse multiples veces sin duplicar datos.
Requiere que las migraciones esten aplicadas (make migrate).
"""

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import Permission, Role, User
from app.models.user import role_permissions, user_roles

PERMISSIONS = [
    ("dashboard.view", "Ver dashboard"),
    ("document.upload", "Subir documentos"),
    ("document.view", "Ver documentos"),
    ("document.review", "Revisar metadatos"),
    ("document.approve", "Aprobar documentos"),
    ("document.deposit", "Depositar en repositorio"),
    ("admin.users.manage", "Administrar usuarios"),
    ("admin.roles.manage", "Administrar roles y permisos"),
    ("admin.ai.providers.manage", "Administrar proveedores de IA"),
    ("admin.ai.models.manage", "Administrar modelos de IA"),
    ("admin.ai.agents.manage", "Administrar agentes de IA"),
    ("admin.metadata.manage", "Administrar esquemas y campos de metadatos"),
    ("admin.vocabularies.manage", "Administrar vocabularios"),
    ("admin.document_types.manage", "Administrar tipos documentales"),
    ("admin.repositories.manage", "Administrar repositorios"),
    ("audit.view", "Ver registros de auditoria"),
]

ROLES = {
    "ADMIN": "Administrador del sistema con acceso total.",
    "CATALOGADOR": "Carga documentos, revisa metadatos, aprueba y deposita.",
    "REVISOR": "Revisa y corrige metadatos antes del deposito.",
}

ROLE_PERMISSIONS = {
    "ADMIN": [code for code, _ in PERMISSIONS],
    "CATALOGADOR": [
        "dashboard.view",
        "document.upload",
        "document.view",
        "document.review",
        "document.approve",
        "document.deposit",
    ],
    "REVISOR": ["dashboard.view", "document.view", "document.review"],
}

USERS = [
    {"username": "admin", "email": "admin@example.com", "password": "metadataia123",
     "first_name": "Administrador", "last_name": "Sistema", "roles": ["ADMIN"]},
    {"username": "catalogador", "email": "catalogador@example.com", "password": "metadataia123",
     "first_name": "Catalina", "last_name": "Catalogadora", "roles": ["CATALOGADOR"]},
    {"username": "revisor", "email": "revisor@example.com", "password": "metadataia123",
     "first_name": "Ramiro", "last_name": "Revisor", "roles": ["REVISOR"]},
]


def run(db: Session) -> None:
    # Permisos
    perm_by_code: dict[str, Permission] = {}
    for code, description in PERMISSIONS:
        perm = db.query(Permission).filter_by(code=code).one_or_none()
        if perm is None:
            perm = Permission(code=code, description=description)
            db.add(perm)
        else:
            perm.description = description
        perm_by_code[code] = perm
    db.flush()

    # Roles
    role_by_name: dict[str, Role] = {}
    for name, description in ROLES.items():
        role = db.query(Role).filter_by(name=name).one_or_none()
        if role is None:
            role = Role(name=name, description=description)
            db.add(role)
            db.flush()
        else:
            role.description = description
        role_by_name[name] = role
    db.flush()

    # Asociaciones rol -> permiso (reemplaza el conjunto)
    for role_name, codes in ROLE_PERMISSIONS.items():
        role = role_by_name[role_name]
        desired = {perm_by_code[c].id for c in codes}
        current = {pid for (pid,) in db.query(role_permissions.c.permission_id).filter(
            role_permissions.c.role_id == role.id)}
        for pid in desired - current:
            db.execute(role_permissions.insert().values(role_id=role.id, permission_id=pid))
        for pid in current - desired:
            db.execute(role_permissions.delete().where(
                role_permissions.c.role_id == role.id,
                role_permissions.c.permission_id == pid,
            ))

    # Usuarios
    for data in USERS:
        user = db.query(User).filter_by(username=data["username"]).one_or_none()
        if user is None:
            user = User(
                username=data["username"],
                email=data["email"],
                password_hash=hash_password(data["password"]),
                first_name=data["first_name"],
                last_name=data["last_name"],
            )
            db.add(user)
            db.flush()
        else:
            user.email = data["email"]
            user.first_name = data["first_name"]
            user.last_name = data["last_name"]
            if not user.active:
                user.active = True

        desired = {role_by_name[r].id for r in data["roles"]}
        current = {rid for (rid,) in db.query(user_roles.c.role_id).filter(
            user_roles.c.user_id == user.id)}
        for rid in desired - current:
            db.execute(user_roles.insert().values(user_id=user.id, role_id=rid))

    db.commit()


def main() -> None:
    db = SessionLocal()
    try:
        run(db)
        print("Seed completado: usuarios, roles y permisos configurados.")
    finally:
        db.close()


if __name__ == "__main__":
    main()