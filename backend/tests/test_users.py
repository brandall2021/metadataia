"""Tests de usuarios y roles (FASE 3, RBAC)."""

import pytest
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.main import create_app
from app.models import Role, User


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_app())


@pytest.fixture(scope="module")
def admin_headers(client) -> dict:
    r = client.post("/api/auth/login", json={"username": "admin", "password": "metadataia123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def catalogador_headers(client) -> dict:
    r = client.post("/api/auth/login", json={"username": "catalogador", "password": "metadataia123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _create_temp_user(db_session, username: str, role_names: list[str] | None = None) -> User:
    db = db_session
    user = User(
        username=username,
        email=f"{username}@example.com",
        password_hash="temporal-no-usado",
    )
    db.add(user)
    db.flush()
    if role_names:
        roles = db.query(Role).filter(Role.name.in_(role_names)).all()
        user.roles = roles
    db.commit()
    db.refresh(user)
    return user


def _delete_user(user_id) -> None:
    db = SessionLocal()
    try:
        user = db.get(User, user_id)
        if user:
            for role in list(user.roles):
                user.roles.remove(role)
            db.delete(user)
            db.commit()
    finally:
        db.close()


TEMP_USER = "testusuario"


# --- acceso ---------------------------------------------------------------


def test_listar_usuarios_sin_token_401(client):
    assert client.get("/api/users").status_code == 401


def test_listar_usuarios_sin_permiso_403(client, catalogador_headers):
    assert client.get("/api/users", headers=catalogador_headers).status_code == 403


def test_listar_usuarios_admin_ok(client, admin_headers):
    r = client.get("/api/users", headers=admin_headers)
    assert r.status_code == 200
    usernames = [u["username"] for u in r.json()]
    assert "admin" in usernames


# --- CRUD usuarios --------------------------------------------------------


def test_crear_usuario_admin_ok(client, admin_headers):
    db = SessionLocal()
    try:
        payload = {
            "username": TEMP_USER,
            "email": f"{TEMP_USER}@example.com",
            "password": "contraseña-segura-1",
            "first_name": "Test",
            "last_name": "Usuario",
            "role_codes": ["CATALOGADOR"],
        }
        r = client.post("/api/users", json=payload, headers=admin_headers)
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["username"] == TEMP_USER
        assert data["roles"] == ["CATALOGADOR"]

        # Visible en el listado
        r2 = client.get("/api/users", headers=admin_headers)
        usernames = [u["username"] for u in r2.json()]
        assert TEMP_USER in usernames
    finally:
        user = db.query(User).filter_by(username=TEMP_USER).one_or_none()
        if user:
            _delete_user(user.id)
        db.close()


def test_crear_usuario_username_duplicado_409(client, admin_headers):
    r = client.post(
        "/api/users",
        json={
            "username": "admin",
            "email": "otro@example.com",
            "password": "contraseña-segura-1",
        },
        headers=admin_headers,
    )
    assert r.status_code == 409


def test_crear_usuario_email_duplicado_409(client, admin_headers):
    db = SessionLocal()
    try:
        user = _create_temp_user(db, TEMP_USER)
        try:
            r = client.post(
                "/api/users",
                json={
                    "username": "otrousuario",
                    "email": f"{TEMP_USER}@example.com",
                    "password": "contraseña-segura-1",
                },
                headers=admin_headers,
            )
            assert r.status_code == 409
        finally:
            _delete_user(user.id)
    finally:
        db.close()


def test_crear_usuario_sin_permiso_403(client, catalogador_headers):
    r = client.post("/api/users", json={"username": "x", "email": "x@y.z", "password": "12345678"},
                    headers=catalogador_headers)
    assert r.status_code == 403


def test_actualizar_usuario_admin_ok(client, admin_headers):
    db = SessionLocal()
    try:
        user = _create_temp_user(db, TEMP_USER)
        try:
            r = client.put(
                f"/api/users/{user.id}",
                json={"first_name": "Renombrado", "active": False},
                headers=admin_headers,
            )
            assert r.status_code == 200
            assert r.json()["first_name"] == "Renombrado"
            assert r.json()["active"] is False
        finally:
            _delete_user(user.id)
    finally:
        db.close()


def test_eliminar_usuario_admin_ok(client, admin_headers):
    db = SessionLocal()
    try:
        user = _create_temp_user(db, TEMP_USER)
        uid = user.id
        try:
            assert client.delete(f"/api/users/{uid}", headers=admin_headers).status_code == 204
            r = client.get("/api/users", headers=admin_headers)
            usernames = [u["username"] for u in r.json()]
            assert TEMP_USER not in usernames
        finally:
            _delete_user(uid)
    finally:
        db.close()


def test_eliminar_usuario_inexistente_404(client, admin_headers):
    import uuid
    r = client.delete(f"/api/users/{uuid.uuid4()}", headers=admin_headers)
    assert r.status_code == 404


# --- roles y permisos -----------------------------------------------------


def test_listar_roles_contiene_seed(client, admin_headers):
    r = client.get("/api/roles", headers=admin_headers)
    assert r.status_code == 200
    names = {role["name"] for role in r.json()}
    assert {"ADMIN", "CATALOGADOR", "REVISOR"} <= names
    admin_role = next(role for role in r.json() if role["name"] == "ADMIN")
    assert "admin.users.manage" in admin_role["permissions"]


def test_roles_sin_permiso_403(client, catalogador_headers):
    assert client.get("/api/roles", headers=catalogador_headers).status_code == 403


def test_actualizar_descripcion_rol(client, admin_headers):
    db = SessionLocal()
    try:
        role = db.query(Role).filter_by(name="REVISOR").one()
        original = role.description
        try:
            r = client.put(f"/api/roles/{role.id}", json={"description": "Nueva descripcion"},
                           headers=admin_headers)
            assert r.status_code == 200
            assert r.json()["description"] == "Nueva descripcion"
        finally:
            db.query(Role).filter_by(id=role.id).update({"description": original})
            db.commit()
    finally:
        db.close()


def test_actualizar_permisos_de_rol(client, admin_headers):
    db = SessionLocal()
    try:
        role = db.query(Role).filter_by(name="REVISOR").one()
        original_codes = {p.code for p in role.permissions}
        cambio = sorted(original_codes | {"admin.users.manage"})
        try:
            r = client.put(f"/api/roles/{role.id}/permissions",
                           json={"permission_codes": cambio}, headers=admin_headers)
            assert r.status_code == 200
            assert "admin.users.manage" in r.json()["permissions"]
        finally:
            r2 = client.put(
                f"/api/roles/{role.id}/permissions",
                json={"permission_codes": sorted(original_codes)},
                headers=admin_headers,
            )
            assert r2.status_code == 200
    finally:
        db.close()