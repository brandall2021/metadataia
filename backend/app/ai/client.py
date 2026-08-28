"""Cliente HTTP minimo para probar proveedores y modelos de IA (FASE 4).

Solo ejecuta llamadas minimas de conectividad:
- proveedor: lista los modelos disponibles (GET /models).
- modelo:  un mensaje corto de prueba (chat completions).

Tipos soportados:
- openai / openai-compatible / ollama: API estilo OpenAI (Authorization: Bearer).
- anthropic: API /v1/messages (x-api-key + anthropic-version).
"""

import time

import httpx

from app.core.config import settings

DEFAULT_BASE_URLS: dict[str, str] = {
    "openai": "https://api.openai.com/v1",
    "openai-compatible": "",
    "ollama": "http://127.0.0.1:11434/v1",
    "anthropic": "https://api.anthropic.com",
}


def _http() -> httpx.Client:
    return httpx.Client(timeout=settings.ai_timeout_seconds)


def _headers(provider_type: str, api_key: str | None) -> dict[str, str]:
    headers: dict[str, str] = {"Accept": "application/json"}
    if provider_type == "anthropic":
        if api_key:
            headers["x-api-key"] = api_key
        headers["anthropic-version"] = "2023-06-01"
    else:
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _base(base_url: str | None, provider_type: str) -> str:
    return (base_url or DEFAULT_BASE_URLS.get(provider_type, "")).rstrip("/")


def _error_result(start: float, message: str, detail: str | None = None) -> dict:
    return {
        "ok": False,
        "message": message,
        "time_ms": round((time.monotonic() - start) * 1000, 1),
        "detail": (detail or "")[:400],
    }


def test_provider(
    base_url: str | None,
    api_key: str | None,
    provider_type: str = "openai",
) -> dict:
    """Prueba minima de conexion con el proveedor: GET /models."""
    start = time.monotonic()
    base = _base(base_url, provider_type)
    if not base:
        return _error_result(start, "URL del proveedor no configurada")

    path = "/v1/models" if provider_type == "anthropic" else "/models"
    url = f"{base}{path}"
    try:
        with _http() as client:
            resp = client.get(url, headers=_headers(provider_type, api_key))
        if resp.status_code < 400:
            return {
                "ok": True,
                "message": f"Conexion correcta (HTTP {resp.status_code})",
                "time_ms": round((time.monotonic() - start) * 1000, 1),
                "detail": None,
            }
        return _error_result(
            start, f"Error HTTP {resp.status_code}", resp.text[:300]
        )
    except httpx.HTTPError as exc:
        return _error_result(start, "Error de conexion", str(exc))


def test_model(
    base_url: str | None,
    api_key: str | None,
    model_identifier: str,
    provider_type: str = "openai",
    max_tokens: int | None = None,
) -> dict:
    """Prueba minima de un modelo: un mensaje corto y devolucion del modelo usado."""
    start = time.monotonic()
    base = _base(base_url, provider_type)
    if not base:
        return _error_result(start, "URL del proveedor no configurada")

    headers = _headers(provider_type, api_key)
    if provider_type == "anthropic":
        url = f"{base}/v1/messages"
        body = {
            "model": model_identifier,
            "max_tokens": max_tokens or 16,
            "messages": [{"role": "user", "content": "ping"}],
        }
    else:
        url = f"{base}/chat/completions"
        body = {
            "model": model_identifier,
            "max_tokens": max_tokens or 5,
            "messages": [{"role": "user", "content": "ping"}],
        }
    try:
        with _http() as client:
            resp = client.post(url, json=body, headers=headers)
        if resp.status_code < 400:
            return {
                "ok": True,
                "message": f"Modelo '{model_identifier}' respondio correctamente",
                "time_ms": round((time.monotonic() - start) * 1000, 1),
                "detail": None,
            }
        return _error_result(
            start, f"Error HTTP {resp.status_code}", resp.text[:300]
        )
    except httpx.HTTPError as exc:
        return _error_result(start, "Error de conexion", str(exc))