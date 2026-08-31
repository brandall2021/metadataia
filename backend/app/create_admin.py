"""Crea o actualiza un usuario administrador (idempotente).

Las credenciales se toman de env vars para no exponerse en el repo:
  ADMIN_EMAIL, ADMIN_PASSWORD, ADMIN_USERNAME, ADMIN_FIRST_NAME, ADMIN_LAST_NAME

Requiere que las migraciones esten aplicadas (el rol ADMIN se crea si no existe).
Puede ejecutarse multiples veces sin duplicar datos (por email o username).
"""

import os

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import Role, User
from app.models.user import user_roles


def run(db: Session) -> None:
    email = os.environ["ADMIN_EMAIL"]
    password = os.environ["ADMIN_PASSWORD"]
    username = os.environ.get("ADMIN_USERNAME", "admin")
    first_name = os.environ.get("ADMIN_FIRST_NAME", "Administrador")
    last_name = os.environ.get("ADMIN_LAST_NAME", "Sistema")

    role = db.query(Role).filter_by(name="ADMIN").one_or_none()
    if role is None:
        role = Role(name="ADMIN", description="Administrador del sistema con acceso total.")
        db.add(role)
        db.flush()

    user = (
        db.query(User)
        .filter((User.email == email) | (User.username == username))
        .first()
    )
    if user is None:
        user = User(
            username=username,
            email=email,
            password_hash=hash_password(password),
            first_name=first_name,
            last_name=last_name,
            active=True,
        )
        db.add(user)
        db.flush()
    else:
        user.email = email
        user.password_hash = hash_password(password)
        user.first_name = first_name
        user.last_name = last_name
        user.active = True

    assigned = {
        rid
        for (rid,) in db.query(user_roles.c.role_id).filter(
            user_roles.c.user_id == user.id
        )
    }
    if role.id not in assigned:
        db.execute(user_roles.insert().values(user_id=user.id, role_id=role.id))

    db.commit()
    print(f"Admin configurado: {email} (roles: ADMIN)")


def main() -> None:
    db = SessionLocal()
    try:
        run(db)
        print("create_admin: listo.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
