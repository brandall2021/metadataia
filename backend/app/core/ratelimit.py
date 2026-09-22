"""Rate limiting simple en memoria (seccion 32).

Ventana deslizante por clave (por defecto IP cliente). Sin dependencias
externas: suficiente para un MVP con un solo worker uvicorn. Para despliegues
multiworker usar Redis; aqui se mantiene intencionalmente minimalista.
"""

import os
import threading
import time
from collections import deque

from fastapi import HTTPException, Request

from app.core.config import settings
from app.core.errors import RATE_LIMITED


class SlidingWindowLimiter:
    def __init__(self, max_requests: int, window_seconds: int, max_entries: int = 20000) -> None:
        self.max_requests = max_requests
        self.window = window_seconds
        self.max_entries = max_entries
        self._hits: dict[str, deque] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> tuple[bool, int]:
        """Devuelve (permitido, segundos_hasta_liberar)."""
        now = time.monotonic()
        with self._lock:
            hits = self._hits.get(key)
            if hits is None:
                if len(self._hits) >= self.max_entries:
                    self._hits.clear()
                self._hits[key] = hits = deque()
            # Podar eventos viejos.
            while hits and now - hits[0] >= self.window:
                hits.popleft()
            if len(hits) >= self.max_requests:
                retry_after = int(self.window - (now - hits[0])) + 1
                return False, max(retry_after, 1)
            hits.append(now)
            return True, 0

    def reset(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)


# Limiter global compartido. Las rutas sensibles (login, admin) definen limites
# mas bajos via ``rate_limit(...)``.
_limiter = SlidingWindowLimiter(max_requests=120, window_seconds=60)


def client_key(request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client is not None:
        return request.client.host
    return "unknown"


def _rate_limit_enabled() -> bool:
    """Indica si el rate limiting debe aplicarse.

    Por defecto solo aplica en produccion (``settings.app_env == "production"``)
    para no entorpecer el desarrollo ni la suite de tests. ``RATE_LIMIT_ENABLED``
    permite forzar/prohibir el enforcement por entorno explicitamente.
    """
    raw = os.environ.get("RATE_LIMIT_ENABLED")
    if raw is not None and raw.strip():
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    return settings.app_env == "production"


def rate_limit(max_requests: int, window_seconds: int):
    """Dependencia FastAPI de rate limiting por IP cliente.

    El ``SlidingWindowLimiter`` se crea UNA vez por ``rate_limit(...)`` (en el
    sitio de llamada, al definir la ruta) y se reutiliza entre requests; si se
    instanciara dentro de ``dependency`` el limite nunca llegaria a dispararse.
    """

    limiter = SlidingWindowLimiter(max_requests, window_seconds)

    def dependency(request: Request) -> None:
        if not _rate_limit_enabled():
            return
        allowed, retry_after = limiter.check(client_key(request))
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail={
                    "code": RATE_LIMITED,
                    "message": "Demasiadas solicitudes, intente mas tarde",
                    "retry_after": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )

    return dependency