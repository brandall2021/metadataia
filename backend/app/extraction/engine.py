"""Motor de extraccion de metadatos con IA (FASE 9).

Flujo (spec FASE 9):
1. Seleccion automatica de agente (default del tipo documental -> agente del
   tipo -> agente generico activo).
2. Construccion del prompt: system + instrucciones con variables del contexto
   (render_prompt: el contenido del documento solo ocupa los placeholders).
3. Llamada al modelo (OpenAI-compatible o Anthropic), con response_format
   JSON cuando el modelo lo soporta.
4. Validacion de la salida contra el JSON Schema (output_schema_json) y
   mapeo a campos del esquema de metadatos.
5. Por cada campo: MetadataRecord con value, confidence y evidencia
   (pagina y texto fuente).

Criterio: una tesis produce metadatos estructurados.
"""

import hashlib
import json
import re
import time
from typing import Any

import httpx

from app.ai.client import render_prompt
from app.core.config import settings
from app.core.security import decrypt_secret
from app.models import AIAgent, AIAgentVersion, AIProvider, Document

MAX_DOCUMENT_TEXT_CHARS = 60000
DEFAULT_CONFIDENCE = 0.9


class ExtractionError(Exception):
    """Error general del pipeline de extraccion."""


class NoAgentError(ExtractionError):
    """No hay un agente de IA configurado para el documento."""


class NoTextError(ExtractionError):
    """El documento no tiene texto; primero debe ejecutarse el OCR."""


# ---------------------------------------------------------------------------
# Contexto y prompt
# ---------------------------------------------------------------------------


def document_text(doc: Document) -> str:
    """Texto completo por pagina con marcadores (evidencia de pagina)."""
    parts = []
    for page in sorted(doc.pages, key=lambda p: p.page_number):
        text = (page.text or "").strip()
        if text:
            parts.append(f"[Pagina {page.page_number}]\n{text}")
    return "\n\n".join(parts)


def field_key(element: str, qualifier: str | None = None) -> str:
    return f"{element}.{qualifier}" if qualifier else element


def build_field_defs(doc_type, db) -> list[dict]:
    """Campos extraibles: los asociados al tipo documental o los del esquema."""
    if doc_type is not None and doc_type.metadata_field_links:
        links = sorted(
            doc_type.metadata_field_links,
            key=lambda l: (l.order_index if l.order_index is not None else 0, l.id.hex),
        )
        return [
            {
                "id": str(link.metadata_field_id),
                "element": link.metadata_field.element,
                "qualifier": link.metadata_field.qualifier,
                "display_name": link.metadata_field.display_name
                or field_key(link.metadata_field.element, link.metadata_field.qualifier),
                "data_type": link.metadata_field.data_type,
                "required": bool(link.required_override or link.metadata_field.required),
                "repeatable": link.metadata_field.repeatable,
                "extraction_instruction": link.extraction_instruction,
                "order": link.order_index or 0,
            }
            for link in links
            if link.metadata_field.ai_extractable and link.metadata_field.active
        ]
    from app.models import MetadataSchema

    schema = db.query(MetadataSchema).filter_by(code=settings.default_metadata_schema).first()
    if schema is None:
        schema = db.query(MetadataSchema).order_by(MetadataSchema.name.asc()).first()
    if schema is None:
        return []
    fields = sorted(schema.fields, key=lambda f: (f.order_index or 0, f.element))
    return [
        {
            "id": str(f.id),
            "element": f.element,
            "qualifier": f.qualifier,
            "display_name": f.display_name or field_key(f.element, f.qualifier),
            "data_type": f.data_type or "text",
            "required": f.required,
            "repeatable": f.repeatable,
            "extraction_instruction": None,
            "order": f.order_index or 0,
        }
        for f in fields
        if f.ai_extractable and f.active
    ]


def build_context(doc: Document, doc_type, field_defs: list[dict]) -> dict:
    schema_name = "SNRD Dublin Core"
    if doc_type is not None and doc_type.metadata_field_links:
        from app.models import MetadataField

        schemas = {f.metadata_field.schema.name for f in doc_type.metadata_field_links}
        if schemas:
            schema_name = ", ".join(sorted(schemas))
    fields_desc = "\n".join(
        f"- {f['element']}{('.' + f['qualifier']) if f['qualifier'] else ''} "
        f"({f['display_name']}, {'requerido' if f['required'] else 'opcional'}, "
        f"{'repetible' if f['repeatable'] else 'unico'}"
        f"{'; ' + f['extraction_instruction'] if f.get('extraction_instruction') else ''})"
        for f in field_defs
    )
    text = document_text(doc)
    return {
        "document_type": doc_type.name if doc_type else "Documento",
        "metadata_schema": schema_name,
        "metadata_fields": fields_desc,
        "document_text": text[:MAX_DOCUMENT_TEXT_CHARS],
        "language": "es",
        "institution": settings.institution or "[institucion]",
        "repository": settings.repository or "[repositorio]",
    }


def build_prompt(version: AIAgentVersion, context: dict) -> tuple[str, str]:
    system = render_prompt(version.system_prompt or "", context)
    user = render_prompt(version.extraction_prompt or "", context)
    return system, user


def prompt_hash(system: str, user: str) -> str:
    return hashlib.sha256(f"{system}\n<sep>\n{user}".encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Seleccion de agente
# ---------------------------------------------------------------------------


def select_agent(doc_type, db) -> AIAgent | None:
    """Agente activo: default del tipo documental -> del tipo -> generico."""
    if doc_type is not None:
        default = doc_type.default_agent
        if default is not None and default.active and default.current_version is not None:
            return default
    from sqlalchemy import or_

    q = db.query(AIAgent).filter(AIAgent.active.is_(True))
    if doc_type is not None:
        q = q.filter(
            or_(AIAgent.document_type_id == doc_type.id, AIAgent.document_type_id.is_(None))
        )
        specific = (
            q.filter(AIAgent.document_type_id == doc_type.id)
            .order_by(AIAgent.created_at.asc())
            .first()
        )
        if specific is not None and specific.current_version is not None:
            return specific
        q = db.query(AIAgent).filter(
            AIAgent.active.is_(True), AIAgent.document_type_id.is_(None)
        )
    agent = q.order_by(AIAgent.created_at.asc()).first()
    if agent is not None and agent.current_version is None:
        return None
    return agent


# ---------------------------------------------------------------------------
# Llamada al modelo
# ---------------------------------------------------------------------------


def call_model(
    provider: AIProvider,
    model_identifier: str,
    system: str,
    user: str,
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
    supports_json: bool = False,
    transport: Any = None,
    timeout: float | None = None,
) -> dict:
    """Llamada chat completions / messages. Devuelve contenido + tokens + ms."""
    from app.ai.client import DEFAULT_BASE_URLS, _base as ai_base

    base = ai_base(provider.base_url, provider.type) or DEFAULT_BASE_URLS.get(provider.type, "")
    if not base:
        raise ExtractionError("URL del proveedor de IA no configurada")

    api_key = decrypt_secret(provider.api_key_encrypted)
    headers: dict[str, str] = {"Accept": "application/json"}
    if provider.type == "anthropic":
        if api_key:
            headers["x-api-key"] = api_key
        headers["anthropic-version"] = "2023-06-01"
    else:
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

    max_tokens = max_tokens or 2000
    temperature = temperature if temperature is not None else 0.2

    if provider.type == "anthropic":
        url = f"{base}/v1/messages"
        body = {
            "model": model_identifier,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
    else:
        url = f"{base}/chat/completions"
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})
        body = {
            "model": model_identifier,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if supports_json:
            body["response_format"] = {"type": "json_object"}

    t0 = time.monotonic()
    client = httpx.Client(transport=transport, timeout=timeout or settings.ai_timeout_seconds)
    try:
        resp = client.post(url, json=body, headers=headers)
    finally:
        client.close()
    if resp.status_code >= 400:
        raise ExtractionError(f"La IA respondio HTTP {resp.status_code}: {resp.text[:300]}")

    data = resp.json()
    if provider.type == "anthropic":
        content = " ".join(
            b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"
        )
        usage = data.get("usage") or {}
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
    else:
        choices = data.get("choices") or []
        content = (choices[0].get("message") or {}).get("content", "") if choices else ""
        usage = data.get("usage") or {}
        input_tokens = usage.get("prompt_tokens")
        output_tokens = usage.get("completion_tokens")

    return {
        "content": content,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "time_ms": round((time.monotonic() - t0) * 1000, 1),
    }


# ---------------------------------------------------------------------------
# Parseo y validacion
# ---------------------------------------------------------------------------


def parse_content(content: str) -> dict:
    """Extrae un objeto JSON de la respuesta del modelo (tolerante a fences)."""
    text = (content or "").strip()
    if not text:
        raise ExtractionError("La IA devolvio una respuesta vacia")
    if text.startswith("```"):
        text = re.sub(r"^```\w*\n?|\n?```$", "", text).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            try:
                data = json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                raise ExtractionError("La IA no devolvio JSON valido") from None
        else:
            raise ExtractionError("La IA no devolvio JSON valido") from None
    if not isinstance(data, dict):
        raise ExtractionError("La IA no devolvio un objeto JSON")
    return data


def validate_schema(data: dict, schema: dict | None) -> list[str]:
    """Validacion minima contra el JSON Schema configurado (required + tipos)."""
    schema = schema or {}
    errors: list[str] = []
    props = schema.get("properties", {}) if isinstance(schema.get("properties"), dict) else {}
    for req in schema.get("required", []) or []:
        if req not in data:
            errors.append(f"falta el campo '{req}'")
    _types = {"string": str, "integer": int, "number": (int, float), "boolean": bool}
    for key, spec in props.items():
        if key not in data or data[key] is None:
            continue
        want = spec.get("type")
        if want == "array" and not isinstance(data[key], list):
            errors.append(f"'{key}' debe ser una lista")
        elif want in _types and not isinstance(data[key], _types[want]):
            errors.append(f"'{key}' debe ser {want}")
    return errors


def parse_fields(data: dict, field_defs: list[dict]) -> list[dict]:
    """Mapea la respuesta de la IA a registros de metadatos.

    Formato aceptado:
      {"fields": {"title.alternative": "valor" | {"value": ..., "confidence": ...}}}
      o plano: {"title.alternative": ...}
    """
    payload = data.get("fields", data) if isinstance(data, dict) else {}
    if not isinstance(payload, dict):
        raise ExtractionError("Formato de campos invalido en la respuesta")
    records: list[dict] = []
    by_key = {field_key(f["element"], f["qualifier"]): f for f in field_defs}
    for key, fd in by_key.items():
        value = payload.get(key)
        if value is None:
            continue
        items = value if isinstance(value, list) else [value]
        for item in items:
            rec = _record_for(fd, item)
            if rec is not None:
                records.append(rec)
    return records


def _record_for(fd: dict, item) -> dict | None:
    if isinstance(item, dict):
        value = item.get("value")
        confidence = item.get("confidence")
        if value is None:
            return None
        return {
            "metadata_field_id": fd["id"],
            "value": str(value),
            "confidence": _coerce_confidence(confidence),
            "source_page": item.get("source_page"),
            "source_text": (item.get("source_text") or "")[:2000] or None,
        }
    return {
        "metadata_field_id": fd["id"],
        "value": str(item),
        "confidence": DEFAULT_CONFIDENCE,
        "source_page": None,
        "source_text": None,
    }


def _coerce_confidence(value) -> float:
    if value is None:
        return DEFAULT_CONFIDENCE
    try:
        conf = float(value)
    except (TypeError, ValueError):
        return DEFAULT_CONFIDENCE
    return max(0.0, min(1.0, conf))