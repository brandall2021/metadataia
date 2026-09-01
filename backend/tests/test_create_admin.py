"""Tests de create_admin: el rol ADMIN debe quedar con todos los permisos.

El servicio admin-init se ejecuta solo en produccion, asi que este test
protege el contrato que luego usa /api/auth/me y los guards RBAC.
"""

import uuid

from app.core.database import SessionLocal
from app.create_admin import run
from app.models import Role, User
from app.seed import PERMISSIONS


def test_create_admin_asigna_permisos_al_rol_admin(monkeypatch):
    db = SessionLocal()
    username = f"permfix_{uuid.uuid4().hex[:8]}"
    email = f"{username}@example.com"

    monkeypatch.setenv("ADMIN_EMAIL", email)
    monkeypatch.setenv("ADMIN_PASSWORD", "Contrasena123!")
    monkeypatch.setenv("ADMIN_USERNAME", username)
    monkeypatch.setenv("ADMIN_FIRST_NAME", "Admin")
    monkeypatch.setenv("ADMIN_LAST_NAME", "Permisos")

    try:
        run(db)

        admin_role = db.query(Role).filter_by(name="ADMIN").one()
        admin_codes = {p.code for p in admin_role.permissions}
        expected_codes = {code for code, _ in PERMISSIONS}

        assert expected_codes <= admin_codes

        user = db.query(User).filter_by(username=username).one()
        assert any(role.name == "ADMIN" for role in user.roles)
    finally:
        db.query(User).filter_by(username=username).delete(synchronize_session=False)
        db.commit()
        db.close()
