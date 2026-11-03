"""Cliente HTTP minimo para probar proveedores y modelos de IA (FASE 4).

Solo ejecuta llamadas minimas de conectividad:
- proveedor: lista los modelos disponibles (GET /models).
- modelo:  un mensaje corto de prueba (chat completions).

Tipos soportados:
- openai / openai-compatible / ollama / google: API estilo OpenAI (Authorization: Bearer).
- anthropic: API /v1/messages (x-api-key + anthropic-version).
- azure-openai: deployment de Azure (api-key + api-version).
"""

import re
import time

import httpx

from app.core.config import settings

SUPPORTED_PROVIDER_TYPES = (
    "openai",
    "openai-compatible",
    "ollama",
    "anthropic",
    "google",
    "azure-openai",
)

DEFAULT_BASE_URLS: dict[str, str] = {
    "openai": "https://api.openai.com/v1",
    "openai-compatible": "",
    "ollama": "http://127.0.0.1:11434/v1",
    "anthropic": "https://api.anthropic.com",
    # Gemini expone una capa compatible con OpenAI (chat/completions + models).
    "google": "https://generativelanguage.googleapis.com/v1beta/openai",
    "azure-openai": "",
}

DEFAULT_AZURE_API_VERSION = "2024-10-21"


def _http() -> httpx.Client:
    return httpx.Client(timeout=settings.ai_timeout_seconds)


def _extra_headers(configuration: dict | None) -> dict[str, str]:
    extra = (configuration or {}).get("extra_headers")
    if not isinstance(extra, dict):
        return {}
    return {str(key): str(value) for key, value in extra.items() if value}


def _headers(
    provider_type: str,
    api_key: str | None,
    configuration: dict | None = None,
) -> dict[str, str]:
    headers: dict[str, str] = {"Accept": "application/json"}
    if provider_type == "anthropic":
        if api_key:
            headers["x-api-key"] = api_key
        headers["anthropic-version"] = "2023-06-01"
    elif provider_type == "azure-openai":
        if api_key:
            headers["api-key"] = api_key
    else:
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
    headers.update(_extra_headers(configuration))
    return headers


def _base(base_url: str | None, provider_type: str) -> str:
    return (base_url or DEFAULT_BASE_URLS.get(provider_type, "")).rstrip("/")


def _with_api_version(url: str, provider_type: str, configuration: dict | None) -> str:
    if provider_type != "azure-openai":
        return url
    version = (configuration or {}).get("api_version") or DEFAULT_AZURE_API_VERSION
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}api-version={version}"


def completion_tokens_key(provider_type: str, model_identifier: str) -> str:
    """Devuelve el nombre del parametro de tokens de salida para el modelo.

    Los modelos OpenAI mas nuevos (p. ej. gpt-5) usan `max_completion_tokens`.
    El resto de proveedores/modelos siguen con `max_tokens`.
    """
    if provider_type in ("openai", "azure-openai") and re.match(
        r"^(gpt-5|o1|o3)", model_identifier, re.IGNORECASE
    ):
        return "max_completion_tokens"
    return "max_tokens"


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


def _test_azure_deployment(
    start: float,
    base: str,
    api_key: str | None,
    configuration: dict | None,
) -> dict:
    url = _with_api_version(f"{base}/chat/completions", "azure-openai", configuration)
    body = {"messages": [{"role": "user", "content": "ping"}]}
    try:
        with _http() as client:
            resp = client.post(
                url, json=body, headers=_headers("azure-openai", api_key, configuration)
            )
        if resp.status_code < 400:
            return {
                "ok": True,
                "message": f"Deployment de Azure respondio correctamente (HTTP {resp.status_code})",
                "time_ms": round((time.monotonic() - start) * 1000, 1),
                "detail": None,
            }
        return _error_result(start, f"Error HTTP {resp.status_code}", resp.text[:300])
    except httpx.HTTPError as exc:
        return _error_result(start, "Error de conexion", str(exc))


def test_provider(
    base_url: str | None,
    api_key: str | None,
    provider_type: str = "openai",
    configuration: dict | None = None,
) -> dict:
    """Prueba minima de conexion con el proveedor.

    OpenAI-style: GET /models. Anthropic: GET /v1/models.
    Azure: un POST minimo al deployment configurado en la base_url.
    """
    start = time.monotonic()
    base = _base(base_url, provider_type)
    if not base:
        return _error_result(start, "URL del proveedor no configurada")

    if provider_type == "azure-openai":
        return _test_azure_deployment(start, base, api_key, configuration)

    path = "/v1/models" if provider_type == "anthropic" else "/models"
    url = f"{base}{path}"
    try:
        with _http() as client:
            resp = client.get(url, headers=_headers(provider_type, api_key, configuration))
        if resp.status_code < 400:
            return {
                "ok": True,
                "message": f"Conexion correcta (HTTP {resp.status_code})",
                "time_ms": round((time.monotonic() - start) * 1000, 1),
                "detail": None,
            }
        probe_model = (configuration or {}).get("probe_model")
        if resp.status_code in (404, 405) and provider_type != "anthropic" and probe_model:
            # Algunos proveedores no publican /models; se valida con un chat minimo.
            return test_model(
                base_url,
                api_key,
                str(probe_model),
                provider_type,
                max_tokens=1,
                configuration=configuration,
            )
        return _error_result(
            start, f"Error HTTP {resp.status_code}", resp.text[:300]
        )
    except httpx.HTTPError as exc:
        return _error_result(start, "Error de conexion", str(exc))


def discover_models(
    base_url: str | None,
    api_key: str | None,
    provider_type: str = "openai",
    configuration: dict | None = None,
) -> dict:
    """Lista los modelos que expone el proveedor (GET /models)."""
    start = time.monotonic()
    base = _base(base_url, provider_type)
    if not base:
        return {
            "ok": False,
            "message": "URL del proveedor no configurada",
            "models": [],
            "detail": None,
        }
    if provider_type == "azure-openai":
        return {
            "ok": True,
            "message": "Azure no lista deployments; cargá los modelos manualmente.",
            "models": [],
            "detail": None,
        }

    path = "/v1/models" if provider_type == "anthropic" else "/models"
    url = f"{base}{path}"
    try:
        with _http() as client:
            resp = client.get(url, headers=_headers(provider_type, api_key, configuration))
        if resp.status_code >= 400:
            message = (
                "El proveedor no expone /models; cargá los modelos manualmente"
                if resp.status_code in (404, 405)
                else f"Error HTTP {resp.status_code}"
            )
            return {
                "ok": False,
                "message": message,
                "models": [],
                "detail": resp.text[:300],
            }
        data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        return {
            "ok": False,
            "message": "Error de conexion",
            "models": [],
            "detail": str(exc)[:400],
        }

    raw = data.get("data") if isinstance(data, dict) else None
    if raw is None and isinstance(data, dict):
        raw = data.get("models")
    models: list[dict] = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        identifier = item.get("id") or item.get("name")
        if not identifier:
            continue
        models.append(
            {
                "id": str(identifier),
                "owned_by": item.get("owned_by"),
                "created": item.get("created") if isinstance(item.get("created"), int) else None,
            }
        )
    models.sort(key=lambda m: m["id"].lower())
    return {
        "ok": True,
        "message": f"{len(models)} modelos disponibles ({round((time.monotonic() - start) * 1000, 1)} ms)",
        "models": models,
        "detail": None,
    }


def test_agent_prompt(
    base_url: str | None,
    api_key: str | None,
    model_identifier: str,
    provider_type: str,
    system_prompt: str | None,
    extraction_prompt: str | None,
    document_text: str | None = None,
    max_tokens: int | None = None,
    configuration: dict | None = None,
) -> dict:
    """Prueba minima de un agente: envia su prompt real con variables de ejemplo."""
    start = time.monotonic()
    base = _base(base_url, provider_type)
    if not base:
        return _error_result(start, "URL del proveedor no configurada")

    context = _test_context(document_text)
    user_message = render_prompt(extraction_prompt or "", context)
    system_message = system_prompt or ""

    headers = _headers(provider_type, api_key, configuration)
    if provider_type == "anthropic":
        url = f"{base}/v1/messages"
        body = {
            "model": model_identifier,
            "max_tokens": max_tokens or 64,
            "system": system_message,
            "messages": [{"role": "user", "content": user_message}],
        }
    else:
        url = _with_api_version(f"{base}/chat/completions", provider_type, configuration)
        messages = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": user_message})
        body = {
            "model": model_identifier,
            completion_tokens_key(provider_type, model_identifier): max_tokens or 100,
            "messages": messages,
        }
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
    configuration: dict | None = None,
) -> dict:
    """Prueba minima de un modelo: un mensaje corto y devolucion del modelo usado."""
    start = time.monotonic()
    base = _base(base_url, provider_type)
    if not base:
        return _error_result(start, "URL del proveedor no configurada")

    headers = _headers(provider_type, api_key, configuration)
    if provider_type == "anthropic":
        url = f"{base}/v1/messages"
        body = {
            "model": model_identifier,
            "max_tokens": max_tokens or 16,
            "messages": [{"role": "user", "content": "ping"}],
        }
    else:
        url = _with_api_version(f"{base}/chat/completions", provider_type, configuration)
        max_tokens_key = completion_tokens_key(provider_type, model_identifier)
        body = {
            "model": model_identifier,
            max_tokens_key: max_tokens or 5,
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
