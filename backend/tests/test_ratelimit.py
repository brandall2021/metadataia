"""Tests de rate limiting (seccion 32).

Unit: comportamiento de ``SlidingWindowLimiter`` (ventana deslizante).
Integracion: una ruta limitada responde 429 tras alcanzar el cupo.

El enforcement de ``rate_limit`` solo esta activo en produccion (o cuando
``RATE_LIMIT_ENABLED=true``); los tests que lo fuerzan usan monkeypatch para
no depender del entorno.
"""

from types import SimpleNamespace

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.errors import RATE_LIMITED
from app.core.ratelimit import SlidingWindowLimiter, rate_limit


# --- unit: SlidingWindowLimiter --------------------------------------------


class _Clock:
    def __init__(self) -> None:
        self.t = 0.0

    def monotonic(self) -> float:
        return self.t


def _use_clock(monkeypatch, clock: _Clock) -> None:
    monkeypatch.setattr(
        "app.core.ratelimit.time", SimpleNamespace(monotonic=clock.monotonic)
    )


def test_limiter_permite_hasta_n_requests(monkeypatch):
    _use_clock(monkeypatch, _Clock())
    limiter = SlidingWindowLimiter(3, 60)
    for _ in range(3):
        assert limiter.check("ip-a") == (True, 0)


def test_limiter_bloquea_n_mas_1_y_devuelve_retry_after(monkeypatch):
    _use_clock(monkeypatch, _Clock())
    limiter = SlidingWindowLimiter(3, 60)
    for _ in range(3):
        assert limiter.check("ip-a")[0]
    allowed, retry_after = limiter.check("ip-a")
    assert allowed is False
    assert retry_after >= 1


def test_ventana_desliza_y_vuelve_a_permitir(monkeypatch):
    clock = _Clock()
    _use_clock(monkeypatch, clock)
    limiter = SlidingWindowLimiter(2, 60)
    assert limiter.check("ip-a")[0]
    assert limiter.check("ip-a")[0]
    assert not limiter.check("ip-a")[0]
    clock.t = 61  # la ventana de 60 s ya paso
    assert limiter.check("ip-a")[0]


def test_reset_libera_la_clave(monkeypatch):
    _use_clock(monkeypatch, _Clock())
    limiter = SlidingWindowLimiter(1, 60)
    assert limiter.check("ip-a")[0]
    assert not limiter.check("ip-a")[0]
    limiter.reset("ip-a")
    assert limiter.check("ip-a")[0]


def test_claves_independientes(monkeypatch):
    _use_clock(monkeypatch, _Clock())
    limiter = SlidingWindowLimiter(2, 60)
    assert limiter.check("ip-a")[0]
    assert limiter.check("ip-b")[0]
    assert limiter.check("ip-a")[0]
    assert not limiter.check("ip-a")[0]
    assert limiter.check("ip-b")[0]  # ip-b conserva su cupo


# --- integracion: ruta limitada con 429 ------------------------------------


def _mini_app() -> FastAPI:
    app = FastAPI()

    @app.get("/limitada")
    def limitada(_: None = Depends(rate_limit(3, 60))) -> dict:
        return {"ok": True}

    return app


def test_integracion_429_despues_del_cupo(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    client = TestClient(_mini_app())
    for _ in range(3):
        assert client.get("/limitada").status_code == 200
    r = client.get("/limitada")
    assert r.status_code == 429
    assert r.json()["detail"]["code"] == RATE_LIMITED
    assert int(r.headers["Retry-After"]) >= 1


def test_integracion_no_limita_en_development(monkeypatch):
    monkeypatch.delenv("RATE_LIMIT_ENABLED", raising=False)
    monkeypatch.setattr(settings, "app_env", "development")
    client = TestClient(_mini_app())
    for _ in range(10):
        assert client.get("/limitada").status_code == 200


def test_integracion_login_429_en_produccion(monkeypatch):
    """Con app_env=production el login real responde 429 tras 10 intentos."""
    from app.main import create_app

    client = TestClient(create_app())
    monkeypatch.setattr(settings, "app_env", "production")
    payload = {"username": "admin", "password": "metadataia123"}
    for _ in range(10):
        r = client.post("/api/auth/login", json=payload)
        assert r.status_code == 200, r.text
    r = client.post("/api/auth/login", json=payload)
    assert r.status_code == 429
    assert r.json()["detail"]["code"] == RATE_LIMITED