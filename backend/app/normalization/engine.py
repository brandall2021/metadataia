"""Motor de normalizacion de metadatos (FASE 10).

MetadataNormalizer convierte los valores extraidos por la IA al formato
configurado, con reglas deterministas (NUNCA depende del LLM):

- texto: espacios multiples, recorte, mayusculas/minusculas
- fechas: formatos comunes -> ISO 8601 (YYYY-MM-DD | YYYY-MM | YYYY)
- idiomas, tipos, derechos: vocabularios configurables con sinonimos
  ("Español" / "Spanish" / "Castellano" -> "spa" segun sinonimos de la
  entrada del vocabulario)
- nombres (creator / contributor): limpieza y capitalizacion conservando
  el orden "APELLIDO, Nombre"
- identificadores: DOI y ORCID a su formato canonico

Reglas por campo:
  field.vocabulary_id      -> normaliza contra el vocabulario
  field.normalization_type -> text | spaces | lowercase | uppercase | title
                              | date | language | name | doi | orcid
                              | identifier
  (si no esta configurado, se infiere del element / data_type)
"""

import re
from typing import Any

from app.models import MetadataField, VocabularyValue

# ---------------------------------------------------------------------------
# Utilidades de texto
# ---------------------------------------------------------------------------


def collapse(value: str | None) -> str:
    """Recorta y colapsa espacios multiples."""
    if value is None:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def _key(value: str) -> str:
    """Clave de comparacion: espacios colapsados, minusculas."""
    return collapse(value).lower()


# ---------------------------------------------------------------------------
# Fechas
# ---------------------------------------------------------------------------

MONTHS_ES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11,
    "diciembre": 12,
}
MONTHS_ES_ABBR = {
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dic": 12,
}
MONTHS_EN = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}
MONTHS_EN_ABBR = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _month_number(name: str) -> int | None:
    key = _key(name).rstrip(".")
    return (
        MONTHS_ES.get(key)
        or MONTHS_ES_ABBR.get(key)
        or MONTHS_EN.get(key)
        or MONTHS_EN_ABBR.get(key)
    )


def _valid_date(d: int, m: int, y: int) -> bool:
    if not (1900 <= y <= 2100 and 1 <= m <= 12 and 1 <= d <= 31):
        return False
    import calendar

    return d <= calendar.monthrange(y, m)[1]


def normalize_date(value: str | None) -> str | None:
    """Convierte formatos comunes a ISO. Devuelve None si no puede parsear."""
    v = collapse(value)
    if not v:
        return None
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", v)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if _valid_date(d, mo, y):
            return f"{y:04d}-{mo:02d}-{d:02d}"
        return None
    m = re.fullmatch(r"(\d{4})-(\d{2})", v)
    if m:
        y, mo = int(m.group(1)), int(m.group(2))
        return f"{y:04d}-{mo:02d}" if 1 <= mo <= 12 else None
    m = re.fullmatch(r"(\d{4})", v)
    if m:
        return v
    m = re.fullmatch(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})", v)
    if m:
        a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        for d, mo in ((a, b), (b, a)):  # DD/MM primero (es-AR), luego MM/DD
            if _valid_date(d, mo, y):
                return f"{y:04d}-{mo:02d}-{d:02d}"
        return None
    m = re.fullmatch(r"(\d{1,2}) de ([A-Za-z]+)(?: de)? (\d{4})", v)
    if m:
        d, month, y = int(m.group(1)), _month_number(m.group(2)), int(m.group(3))
        if month and _valid_date(d, month, y):
            return f"{y:04d}-{month:02d}-{d:02d}"
        return None
    m = re.fullmatch(r"([A-Za-z]+)[\.,]? (\d{1,2}),? (\d{4})", v)
    if m:
        month, d, y = _month_number(m.group(1)), int(m.group(2)), int(m.group(3))
        if month and _valid_date(d, month, y):
            return f"{y:04d}-{month:02d}-{d:02d}"
        return None
    m = re.fullmatch(r"(\d{1,2}) ([A-Za-z]+)[\.,]? (\d{4})", v)
    if m:
        d, month, y = int(m.group(1)), _month_number(m.group(2)), int(m.group(3))
        if month and _valid_date(d, month, y):
            return f"{y:04d}-{month:02d}-{d:02d}"
        return None
    return None


# ---------------------------------------------------------------------------
# Identificadores
# ---------------------------------------------------------------------------

DOI_RE = re.compile(r"\b(10\.\d{4,9}/[A-Za-z0-9._\-;():/\u0080-\uffff]+)")


def normalize_doi(value: str | None) -> str | None:
    v = collapse(value)
    m = DOI_RE.search(v)
    if m:
        return m.group(1).rstrip(".,;") 
    return None


ORCID_RE = re.compile(r"(\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{3}[\dXx])")


def normalize_orcid(value: str | None) -> str | None:
    v = collapse(value)
    m = ORCID_RE.search(v)
    if m:
        raw = re.sub(r"[-\s]", "", m.group(1)).upper()
        if len(raw) == 16:
            return f"{raw[:4]}-{raw[4:8]}-{raw[8:12]}-{raw[12:]}"
    return None


def normalize_identifier(value: str | None) -> str | None:
    """Prueba DOI y ORCID; devuelve el identificador canonico o None."""
    return normalize_doi(value) or normalize_orcid(value)


# ---------------------------------------------------------------------------
# Nombres
# ---------------------------------------------------------------------------

_STOP_WORDS = {"de", "del", "la", "los", "las", "el", "y", "van", "von", "do", "da"}


def _cap(word: str) -> str:
    return word if _key(word) in _STOP_WORDS else word.capitalize()


def normalize_name(value: str | None) -> str:
    """Limpia y capitaliza nombres de personas, conservando 'APELLIDO, Nombre'."""
    v = collapse(value)
    parts = [p.strip() for p in v.split(";") if p.strip()]
    out: list[str] = []
    for part in parts:
        if "," in part:
            surname, given = [w.strip() for w in part.split(",", 1)]
            surname = " ".join(_cap(w) for w in surname.split())
            given = " ".join(_cap(w) for w in given.split())
            out.append(f"{surname}, {given}")
        else:
            out.append(" ".join(_cap(w) for w in part.split()))
    return "; ".join(out)


# ---------------------------------------------------------------------------
# Vocabularios
# ---------------------------------------------------------------------------


def normalize_vocabulary(
    value: str | None, values: list[VocabularyValue]
) -> tuple[str, str] | None:
    """Devuelve (canonico, code) si el valor coincide con code, label,
    normalized_value o algun sinonimo de una entrada activa. None si no."""
    v = _key(value)
    if not v:
        return None
    for entry in values:
        candidates = {_key(entry.code), _key(entry.label)}
        if entry.normalized_value:
            candidates.add(_key(entry.normalized_value))
        candidates.update(_key(s) for s in (entry.synonyms_json or []))
        if v in candidates:
            return (entry.normalized_value or entry.label, entry.code)
    return None


# ---------------------------------------------------------------------------
# Reglas por campo
# ---------------------------------------------------------------------------

_TEXT_TYPES = {"text", "spaces", None}
_INFER_BY_ELEMENT = {
    "date": "date",
    "language": "language",
    "language.iso639-2": "language",
    "type": "vocabulary",
    "resource.type": "vocabulary",
    "rights": "vocabulary",
    "rights.access": "vocabulary",
    "creator": "name",
    "contributor": "name",
    "author": "name",
    "doi": "doi",
    "identifier.doi": "doi",
    "orcid": "orcid",
    "identifier.orcid": "orcid",
    "identifier": "identifier",
}


def field_normalization_type(field: MetadataField) -> str:
    """Tipo de regla de normalizacion configurado o inferido para el campo."""
    if field.normalization_type:
        return field.normalization_type
    if field.data_type == "date":
        return "date"
    return _INFER_BY_ELEMENT.get((field.element or "").lower(), "text")


class NormalizationResult:
    """Resultado de normalizar un valor."""

    __slots__ = ("value", "ok", "rule", "note")

    def __init__(self, value: str, ok: bool, rule: str, note: str | None = None):
        self.value = value
        self.ok = ok
        self.rule = rule
        self.note = note


def normalize_record_value(
    field: MetadataField,
    value: str | None,
    *,
    vocab_values: list[VocabularyValue] | None = None,
) -> NormalizationResult:
    """Aplica la regla del campo al valor. ok=False => dejar el valor original."""
    original = collapse(value)
    if not original:
        return NormalizationResult(original, False, "empty")

    if field.vocabulary_id:
        if vocab_values:
            hit = normalize_vocabulary(original, vocab_values)
            if hit:
                canonical, code = hit
                return NormalizationResult(canonical, True, "vocabulary", code)
        return NormalizationResult(original, False, "vocabulary")

    ntype = field_normalization_type(field)

    if ntype == "date":
        normalized = normalize_date(original)
        if normalized is not None and normalized != original:
            return NormalizationResult(normalized, True, "date")
        return NormalizationResult(original, normalized is not None, "date")

    if ntype == "doi":
        normalized = normalize_doi(original)
        if normalized is not None and normalized != original:
            return NormalizationResult(normalized, True, "doi")
        return NormalizationResult(original, normalized is not None, "doi")

    if ntype == "orcid":
        normalized = normalize_orcid(original)
        if normalized is not None and normalized != original:
            return NormalizationResult(normalized, True, "orcid")
        return NormalizationResult(original, normalized is not None, "orcid")

    if ntype == "identifier":
        normalized = normalize_identifier(original)
        if normalized is not None and normalized != original:
            return NormalizationResult(normalized, True, "identifier")
        return NormalizationResult(original, normalized is not None, "identifier")

    if ntype == "name":
        normalized = normalize_name(original)
        return NormalizationResult(normalized, True, "name")

    if ntype == "lowercase":
        return NormalizationResult(original.lower(), True, "lowercase")
    if ntype == "uppercase":
        return NormalizationResult(original.upper(), True, "uppercase")
    if ntype == "title":
        return NormalizationResult(original.title(), True, "title")
    if ntype == "language" or ntype == "vocabulary" or ntype in _TEXT_TYPES:
        return NormalizationResult(original, True, ntype or "text")

    return NormalizationResult(original, True, "text")