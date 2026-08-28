"""Tests de autenticacion (FASE 3).

Ejecucion contra la base de datos de desarrollo con el seed aplicado
(admin/metadataia123). Usa TestClient de FastAPI.
"""

import pytest
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.main import create_app
from app.models import User


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_app())


def _admin_login(client: TestClient) -> dict:
    r = client.post("/api/auth/login", json={"username": "admin", "password": "metadataia123"})
    assert r.status_code == 200, r.text
    return r.json()


def _create_inactive_user(username: str) -> User:
    db = SessionLocal()
    try:
        user = User(
            username=username,
            email=f"{username}@example.com",
            password_hash=hash_password("contraseña-test-1"),
            active=False,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


def _delete_user(user_id) -> None:
    db = SessionLocal()
    try:
        user = db.get(User, user_id)
        if user:
            db.delete(user)
            db.commit()
    finally:
        db.close()


# --- login ----------------------------------------------------------------


def test_login_ok_devuelve_token(client):
    data = _admin_login(client)
    assert data["access_token"]
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0


def test_login_credenciales_invalidas_401(client):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "incorrecta"})
    assert r.status_code == 401


def test_login_usuario_desconocido_401(client):
    r = client.post("/api/auth/login", json={"username": "nadie", "password": "x"})
    assert r.status_code == 401


def test_login_usuario_inactivo_403(client):
    user = _create_inactive_user("inactivotest")
    try:
        r = client.post("/api/auth/login", json={"username": "inactivotest", "password": "contraseña-test-1"})
        assert r.status_code == 403
    finally:
        _delete_user(user.id)


def test_login_falta_campo_422(client):
    r = client.post("/api/auth/login", json={"username": "admin"})
    assert r.status_code == 422


# --- /me ------------------------------------------------------------------


def test_me_sin_token_401(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 401


def test_me_token_invalido_401(client):
    r = client.get("/api/auth/me", headers={"Authorization": "Bearer tokeninvalido"})
    assert r.status_code == 401


def test_me_admin_contiene_roles_y_permisos(client):
    token = _admin_login(client)["access_token"]
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert data["username"] == "admin"
    assert "ADMIN" in data["roles"]
    assert "admin.users.manage" in data["permissions"]


# --- refresh / logout -----------------------------------------------------


def test_refresh_con_token_valido_devuelve_token_nuevo(client):
    token = _admin_login(client)["access_token"]
    r = client.post("/api/auth/refresh", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["access_token"]


def test_refresh_con_token_invalido_401(client):
    r = client.post("/api/auth/refresh", headers={"Authorization": "Bearer basura"})
    assert r.status_code == 401


def test_logout_responde_ok(client):
    token = _admin_login(client)["access_token"]
    r = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200