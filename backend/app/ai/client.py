"""Cliente HTTP minimo para probar proveedores y modelos de IA (FASE 4).

Solo ejecuta llamadas minimas de conectividad:
- proveedor: lista los modelos disponibles (GET /models).
- modelo:  un mensaje corto de prueba (chat completions).

Tipos soportados:
- openai / openai-compatible / ollama: API estilo OpenAI (Authorization: Bearer).
- anthropic: API /v1/messages (x-api-key + anthropic-version).
"""

import re
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


def render_prompt(template: str, context: dict) -> str:
    """Rellena variables {{name}} de la plantilla con el contexto dado.

    Solo se reemplazan variables conocidas; las desconocidas quedan intactas
    (genera una plantilla segura: el contenido del documento nunca modifica
    instrucciones, solo ocupa el placeholder — spec sec. 10).
    """
    if not template:
        return ""

    def _replace(match: "re.Match[str]") -> str:
        key = match.group(1).strip()
        if key in context:
            return str(context[key])
        return match.group(0)

    return re.sub(r"\{\{\s*(\w+)\s*\}\}", _replace, template)


TEST_CONTEXT = {
    "document_type": "[tipo documental]",
    "metadata_schema": "[esquema de metadatos]",
    "metadata_fields": "[campos de metadatos]",
    "document_text": "[texto del documento extraido, pagina 1 de N]",
    "language": "es",
    "institution": "[institucion]",
    "repository": "[repositorio]",
}


def _test_context(document_text: str | None) -> dict:
    context = dict(TEST_CONTEXT)
    if document_text:
        context["document_text"] = document_text
    return context


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


def test_agent_prompt(
    base_url: str | None,
    api_key: str | None,
    model_identifier: str,
    provider_type: str,
    system_prompt: str | None,
    extraction_prompt: str | None,
    document_text: str | None = None,
    max_tokens: int | None = None,
) -> dict:
    """Prueba minima de un agente: envia su prompt real con variables de ejemplo."""
    start = time.monotonic()
    base = _base(base_url, provider_type)
    if not base:
        return _error_result(start, "URL del proveedor no configurada")

    context = _test_context(document_text)
    user_message = render_prompt(extraction_prompt or "", context)
    system_message = system_prompt or ""

    headers = _headers(provider_type, api_key)
    if provider_type == "anthropic":
        url = f"{base}/v1/messages"
        body = {
            "model": model_identifier,
            "max_tokens": max_tokens or 64,
            "system": system_message,
            "messages": [{"role": "user", "content": user_message}],
        }
    else:
        url = f"{base}/chat/completions"
        messages = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": user_message})
        body = {"model": model_identifier, "max_tokens": max_tokens or 100, "messages": messages}
    try:
        with _http() as client:
            resp = client.post(url, json=body, headers=headers)
        if resp.status_code < 400:
            data = resp.json()
            content = ""
            if provider_type == "anthropic":
                content = " ".join(
                    b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"
                )
            else:
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return {
                "ok": True,
                "message": "El agente respondio correctamente",
                "time_ms": round((time.monotonic() - start) * 1000, 1),
                "detail": content[:400],
            }
        return _error_result(start, f"Error HTTP {resp.status_code}", resp.text[:300])
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