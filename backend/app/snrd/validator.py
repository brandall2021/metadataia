"""Validacion SNRD (FASE 11).

Modulo separado de DSpace: verifica que el conjunto de metadatos cumpla
el perfil minimo de interoperabilidad SNRD (elementos obligatorios,
fechas en formato ISO, idioma recomendado). El perfil institucional se
configura por la definicion del esquema/tipo documental.
"""

from app.normalization.engine import normalize_date

SNRD_REQUIRED_ELEMENTS = ("title", "date")


def _field_key(field) -> str:
    return f"{field.element}.{field.qualifier}" if field.qualifier else (field.element or "")


def validate_snrd(records, doc_type_label: str | None = None) -> tuple[list[dict], list[dict]]:
    """Devuelve (errors, warnings) de interoperabilidad SNRD."""
    errors: list[dict] = []
    warnings: list[dict] = []
    by_key: dict[str, object] = {}
    for rec in records:
        field = rec.metadata_field
        if field is None:
            continue
        by_key[_field_key(field)] = rec

    for element in SNRD_REQUIRED_ELEMENTS:
        rec = by_key.get(element)
        if rec is None or not str(rec.value or "").strip():
            errors.append(
                {
                    "field": element,
                    "code": "missing_required",
                    "message": f"SNRD: el elemento '{element}' es obligatorio para interoperabilidad",
                }
            )

    date_rec = by_key.get("date")
    if date_rec is not None and str(date_rec.value or "").strip():
        if normalize_date(date_rec.value) is None:
            errors.append(
                {
                    "field": "date",
                    "code": "invalid_date",
                    "message": "SNRD: la fecha debe estar en formato ISO (YYYY-MM-DD)",
                    "value": date_rec.value,
                }
            )

    lang_rec = by_key.get("language")
    if lang_rec is None or not str(lang_rec.value or "").strip():
        warnings.append(
            {
                "field": "language",
                "code": "language_missing",
                "message": "SNRD: se recomienda indicar el idioma (codigo ISO 639-2)",
            }
        )
    return errors, warnings