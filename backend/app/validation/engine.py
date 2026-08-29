"""Motor de validacion de metadatos (FASE 11).

Ejecuta reglas deterministas por campo configuradas en MetadataField:
obligatorios, formatos (email, url, fecha ISO, identificadores, enteros,
flotantes, regex), longitudes minimas/maximas y vocabularios. Genera
errores (registros invalidos) y warnings (dudas, confianza baja). El
motor SNRD (modulo aparte) agrega la verificacion de interoperabilidad.
"""

import re
from dataclasses import dataclass, field as dataclass_field

from app.normalization.engine import normalize_date, normalize_doi, normalize_orcid

CONFIDENCE_WARNING_THRESHOLD = 0.6

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
URL_RE = re.compile(r"^https?://[A-Za-z0-9.\-]+(/[^\s]*)?$")
ISBN_RE = re.compile(r"^(97[89][\-\s]?)?\d{1,5}[\-\s]?\d+[\-\s]?\d+[\-\s]?[\dX]$")
ISSN_RE = re.compile(r"^\d{4}-\d{3}[\dX]$")
DOI_RE = re.compile(r"\b(10\.\d{4,9}/[A-Za-z0-9._\-;():/\u0080-\uffff]+)")
ORCID_RE = re.compile(r"(\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{3}[\dXx])")


def collapse(value: str | None) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def field_key(element: str | None, qualifier: str | None = None) -> str:
    return f"{element}.{qualifier}" if qualifier else (element or "")


@dataclass
class ValidationOutcome:
    errors: list[dict] = dataclass_field(default_factory=list)
    warnings: list[dict] = dataclass_field(default_factory=list)


def _error(field, code: str, message: str, value=None) -> dict:
    return {
        "field": field_key(field.element, field.qualifier),
        "field_id": str(field.id) if field.id is not None else None,
        "code": code,
        "message": message,
        "value": value,
    }


def check_value(field, value, vocab_values: list | None = None) -> list[dict]:
    """Valida el valor de un campo contra su configuracion. Devuelve errores."""
    errors: list[dict] = []
    if value is None or (isinstance(value, str) and not collapse(value)):
        if field.required:
            errors.append(
                _error(field, "required", f"El campo '{field_key(field.element, field.qualifier)}' es obligatorio")
            )
        return errors

    v = str(value).strip()
    vt = (field.validation_type or "").strip()
    rule = vt.lower()
    param = None
    m = re.match(r"^([a-z_]+)(?::(.*))?$", vt, re.IGNORECASE)
    if m:
        rule = m.group(1).lower()
        param = m.group(2)

    if field.vocabulary_id:
        values = list(vocab_values or [])
        matches = (
            v == x.code
            or v == x.label
            or v == (x.normalized_value or "")
            or (x.synonyms_json and v in x.synonyms_json)
            for x in values
        )
        if not any(matches):
            errors.append(
                _error(field, "vocabulary", f"El valor '{v}' no pertenece al vocabulario del campo", v)
            )
    elif rule == "email":
        if not EMAIL_RE.fullmatch(v):
            errors.append(_error(field, "invalid_email", f"El campo no es un correo valido: '{v}'", v))
    elif rule == "url":
        if not URL_RE.fullmatch(v):
            errors.append(_error(field, "invalid_url", f"El campo no es una URL valida: '{v}'", v))
    elif rule in ("date", "iso8601", "fecha"):
        if normalize_date(v) is None:
            errors.append(_error(field, "invalid_date", f"Fecha invalida (formato ISO esperado): '{v}'", v))
    elif rule == "integer":
        try:
            int(v)
        except ValueError:
            errors.append(_error(field, "invalid_integer", f"Se espera un entero: '{v}'", v))
    elif rule == "float":
        try:
            float(v)
        except ValueError:
            errors.append(_error(field, "invalid_float", f"Se espera un numero: '{v}'", v))
    elif rule in ("doi",):
        if normalize_doi(v) is None:
            errors.append(_error(field, "invalid_doi", f"DOI invalido: '{v}'", v))
    elif rule in ("orcid",):
        if normalize_orcid(v) is None:
            errors.append(_error(field, "invalid_orcid", f"ORCID invalido: '{v}'", v))
    elif rule == "isbn":
        if ISBN_RE.fullmatch(v) is None:
            errors.append(_error(field, "invalid_isbn", f"ISBN invalido: '{v}'", v))
    elif rule == "issn":
        if ISSN_RE.fullmatch(v) is None:
            errors.append(_error(field, "invalid_issn", f"ISSN invalido: '{v}'", v))
    elif rule == "identifier":
        if not (
            DOI_RE.search(v)
            or ORCID_RE.search(v)
            or ISBN_RE.fullmatch(v)
            or ISSN_RE.fullmatch(v)
        ):
            errors.append(
                _error(field, "invalid_identifier", f"Identificador no reconocido (DOI/ORCID/ISBN/ISSN): '{v}'", v)
            )
    elif rule == "regex" and param:
        try:
            if re.fullmatch(param, v) is None:
                errors.append(_error(field, "regex", f"El valor no cumple el patron configurado: '{v}'", v))
        except re.error:
            pass
    elif rule == "min_length" and param:
        try:
            n = int(param)
            if len(v) < n:
                errors.append(_error(field, "min_length", f"Longitud minima {n}: '{v}'", v))
        except ValueError:
            pass
    elif rule == "max_length" and param:
        try:
            n = int(param)
            if len(v) > n:
                errors.append(_error(field, "max_length", f"Longitud maxima {n}: '{v}'", v))
        except ValueError:
            pass
    return errors


def missing_required(type_fields: list, records) -> list[dict]:
    """Campos obligatorios de un tipo documental sin registro extraido."""
    errors: list[dict] = []
    present = {str(r.metadata_field_id) for r in records if getattr(r, "metadata_field_id", None)}
    for f in type_fields:
        if f.required and str(f.id) not in present:
            errors.append(
                _error(
                    f,
                    "required",
                    f"El campo '{field_key(f.element, f.qualifier)}' es obligatorio y no fue extraido",
                )
            )
    return errors


def validate_records(records, vocab_cache: dict | None = None) -> ValidationOutcome:
    """Ejecuta las reglas por campo sobre los registros de un documento."""
    outcome = ValidationOutcome()
    vocab_cache = vocab_cache or {}
    for rec in records:
        field = rec.metadata_field
        if field is None:
            continue
        vocab_values = vocab_cache.get(field.vocabulary_id, []) if field.vocabulary_id else []
        for err in check_value(field, rec.value, vocab_values):
            outcome.errors.append(err)
        conf = getattr(rec, "confidence", None)
        if conf is not None and conf < CONFIDENCE_WARNING_THRESHOLD:
            outcome.warnings.append(
                {
                    "field": field_key(field.element, field.qualifier),
                    "field_id": str(field.id) if field.id is not None else None,
                    "code": "low_confidence",
                    "message": "Confianza baja; se recomienda revision humana",
                    "value": rec.value,
                    "confidence": conf,
                }
            )
    return outcome