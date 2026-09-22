"""Servicio de configuracion global administrable (seccion 40).

Resuelve el valor efectivo de cada setting: si existe override en
``app_settings`` (DB) se usa ese; si no, el default de ``core/config.py``
(env). Devuelve valores tipados.
"""

from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.settings import AppSetting

# Registro: key (publica) -> (attr de Settings, tipo). Solo lo que debe poderse
# administrar desde el panel. El resto de la configuracion es de entorno.
ENV_DEFAULTS: dict[str, tuple[str, type]] = {
    "max_file_size_mb": ("default_max_file_size_mb", int),
    "allowed_extensions": ("allowed_extensions", list),
    "ocr_languages": ("ocr_languages", str),
    "max_retries": ("max_retries", int),
    "ai_timeout_seconds": ("ai_timeout_seconds", int),
    "dspace_timeout_seconds": ("dspace_timeout_seconds", int),
    "min_confidence_recommended": ("min_confidence_recommended", float),
    "auto_ocr": ("auto_ocr", bool),
    "auto_ai": ("auto_ai", bool),
    "auto_normalize": ("auto_normalize", bool),
    "auto_validate": ("auto_validate", bool),
    "institution": ("institution", str),
    "repository": ("repository", str),
}

DESCRIPTIONS: dict[str, str] = {
    "max_file_size_mb": "Tamano maximo de PDF subido (MB)",
    "allowed_extensions": "Extensiones de archivo permitidas (separadas por comas)",
    "ocr_languages": "Idiomas OCR (tesseract: spa+eng+por)",
    "max_retries": "Cantidad maxima de reintentos para errores transitorios",
    "ai_timeout_seconds": "Timeout de llamadas IA (segundos)",
    "dspace_timeout_seconds": "Timeout de llamadas DSpace (segundos)",
    "min_confidence_recommended": "Confianza minima recomendada (0-1) para revisar",
    "auto_ocr": "Ejecutar OCR automaticamente cuando el PDF es escaneado",
    "auto_ai": "Ejecutar extraccion IA automaticamente",
    "auto_normalize": "Normalizar automaticamente tras la extraccion IA",
    "auto_validate": "Validar automaticamente tras normalizar",
    "institution": "Nombre de la institucion (LLM no confiable)",
    "repository": "Repositorio destino por defecto",
}


def _env_value(key: str) -> Any | None:
    entry = ENV_DEFAULTS.get(key)
    if entry is None:
        return None
    attr, _typ = entry
    value = getattr(settings, attr, None)
    if isinstance(value, str) and key == "allowed_extensions":
        return [x.strip() for x in value.split(",") if x.strip()]
    return value


def get_setting(db: Session, key: str, default: Any = None) -> Any:
    """Valor efectivo: override DB si existe, si no default env/clave."""
    stored = db.get(AppSetting, key)
    if stored is not None and stored.value_json is not None:
        return stored.value_json.get("value")
    value = _env_value(key)
    if value is not None:
        return value
    return default


def set_setting(db: Session, key: str, value: Any, *, user=None) -> AppSetting:
    entry = db.get(AppSetting, key)
    if entry is None:
        entry = AppSetting(key=key, value_json={"value": value})
        db.add(entry)
    else:
        entry.value_json = {"value": value}
    entry.description = DESCRIPTIONS.get(key, entry.description)
    entry.section = "configuracion"
    from app.audit.service import audit_log

    audit_log(
        db,
        user=user,
        action="settings.update",
        entity_type="settings",
        entity_id=key,
        new_value={"value": value},
    )
    return entry


def clear_setting(db: Session, key: str, *, user=None) -> bool:
    entry = db.get(AppSetting, key)
    if entry is None:
        return False
    from app.audit.service import audit_log

    audit_log(
        db,
        user=user,
        action="settings.delete",
        entity_type="settings",
        entity_id=key,
        old_value={"value": entry.value_json},
    )
    db.delete(entry)
    return True


def settings_catalog(db: Session) -> list[dict]:
    """Lista completa de settings (default env + overrides DB) para el panel."""
    overrides = {s.key: s for s in db.query(AppSetting).all()}
    keys = set(ENV_DEFAULTS.keys()) | {k for k in overrides if k not in ENV_DEFAULTS}
    result: list[dict] = []
    for key in sorted(keys):
        stored = overrides.get(key)
        result.append(
            {
                "key": key,
                "value": stored.value_json.get("value") if stored else _env_value(key),
                "description": DESCRIPTIONS.get(key) or "Sin descripcion",
                "section": "configuracion",
                "source": "db" if stored else "env",
            }
        )
    return result
