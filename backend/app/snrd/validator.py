"""Validacion SNRD (FASE 11).

Modulo separado de DSpace: verifica que el conjunto de metadatos cumpla el
perfil minimo de interoperabilidad SNRD (elementos obligatorios, fechas ISO,
idioma en codigo del perfil, identificadores DOI/ORCID, embargo).

El perfil institucional es configurable:
  * ``SNRDProfile.code_defaults()`` define el perfil por defecto
    (obligatorios: title, date, type, language; recomendado: rights;
    idiomas: spa, eng, por; sin embargo).
  * La configuracion global ``app_settings`` permite reemplazarlo con la key
    ``snrd_profile_json`` (JSON con required_elements, recommended_elements,
    allow_embargo, date_format, languages) resuelta via ``get_setting``.

Dos modos de uso:
  * ``validate_snrd(records, doc_type_label=None)``        # modo historico
  * ``validate_snrd(db=db, document=document, ...)``       # desde una tarea

Cada error/warning se clasifica con la constante canonica
``SNRD_VALIDATION_ERROR`` (campo ``error_class``) ademas de su codigo
especifico por fallo.
"""

from dataclasses import dataclass, field as dataclass_field

from app.administration.service import get_setting
from app.core.errors import SNRD_VALIDATION_ERROR
from app.normalization.engine import normalize_date, normalize_doi, normalize_orcid

# Clasificacion canonica de fallos SNRD (core/errors.py).
ERROR_CLASS = SNRD_VALIDATION_ERROR

DEFAULT_REQUIRED_ELEMENTS = ("title", "date", "type", "language")
DEFAULT_RECOMMENDED_ELEMENTS = ("rights",)
DEFAULT_LANGUAGES = ("spa", "eng", "por")
DEFAULT_DATE_FORMAT = "iso"

# Sinonimos basicos de los codigos ISO 639-2 por defecto: permiten validar
# valores aun no normalizados por el vocabulario ("Spanish" -> spa).
_BASE_LANGUAGE_ALIASES: dict[str, set[str]] = {
    "spa": {"spanish", "castellano", "espanol", "esp", "es"},
    "eng": {"english", "english", "ingles", "en"},
    "por": {"portuguese", "portugues", "portuges", "pt"},
}


@dataclass
class SNRDProfile:
    """Perfil de interoperabilidad SNRD efectivo para un documento."""

    required_elements: list[str] = dataclass_field(
        default_factory=lambda: list(DEFAULT_REQUIRED_ELEMENTS)
    )
    recommended_elements: list[str] = dataclass_field(
        default_factory=lambda: list(DEFAULT_RECOMMENDED_ELEMENTS)
    )
    allow_embargo: bool = False
    date_format: str = DEFAULT_DATE_FORMAT
    languages: list[str] = dataclass_field(default_factory=lambda: list(DEFAULT_LANGUAGES))

    @classmethod
    def code_defaults(cls) -> "SNRDProfile":
        return cls()

    @classmethod
    def from_json(cls, payload: object) -> "SNRDProfile":
        """Construye el perfil desde la configuracion almacenada en ``app_settings``.

        Solo se reemplazan las claves presentes; el resto conserva los defaults.
        """
        profile = cls.code_defaults()
        if not isinstance(payload, dict):
            return profile
        if isinstance(payload.get("required_elements"), list):
            cleaned = [str(e).strip() for e in payload["required_elements"] if str(e).strip()]
            if cleaned:
                profile.required_elements = cleaned
        if isinstance(payload.get("recommended_elements"), list):
            cleaned = [str(e).strip() for e in payload["recommended_elements"] if str(e).strip()]
            if cleaned:
                profile.recommended_elements = cleaned
        if isinstance(payload.get("languages"), list):
            cleaned = [str(l).lower().strip() for l in payload["languages"] if str(l).strip()]
            if cleaned:
                profile.languages = cleaned
        if isinstance(payload.get("allow_embargo"), bool):
            profile.allow_embargo = payload["allow_embargo"]
        if isinstance(payload.get("date_format"), str) and payload["date_format"].strip():
            profile.date_format = payload["date_format"].strip()
        return profile

    def to_dict(self) -> dict:
        return {
            "required_elements": self.required_elements,
            "recommended_elements": self.recommended_elements,
            "allow_embargo": self.allow_embargo,
            "date_format": self.date_format,
            "languages": self.languages,
        }


def _field_key(field) -> str:
    return f"{field.element}.{field.qualifier}" if field.qualifier else (field.element or "")


def _snrd_error(field: str, code: str, message: str, value=None) -> dict:
    return {
        "field": field,
        "code": code,
        "message": message,
        "value": value,
        "error_class": ERROR_CLASS,
    }


def _profile_for(db) -> SNRDProfile:
    profile = SNRDProfile.code_defaults()
    if db is None:
        return profile
    try:
        payload = get_setting(db, "snrd_profile_json", None)
    except Exception:  # noqa: BLE001 - configuracion ausente o corrupta
        payload = None
    if payload:
        profile = SNRDProfile.from_json(payload)
    return profile


def validate_snrd(
    records=None,
    doc_type_label: str | None = None,
    *,
    db=None,
    document=None,
) -> tuple[list[dict], list[dict]]:
    """Devuelve (errors, warnings) de interoperabilidad SNRD.

    ``records`` es una coleccion de MetadataRecord (u objeto con los atributos
    ``metadata_field`` y ``value``). Alternativamente se puede pasar
    ``db`` + ``document`` y los registros se obtienen de la base.
    """
    if document is not None:
        if records is not None:
            raise TypeError("validate_snrd recibe o 'records' o 'document', no ambos")
        if db is not None:
            from app.models import MetadataRecord

            records = (
                db.query(MetadataRecord)
                .filter(
                    MetadataRecord.document_id == document.id,
                    MetadataRecord.value.isnot(None),
                )
                .all()
            )
        else:
            records = list(getattr(document, "metadata_records", None) or [])
        if doc_type_label is None and getattr(document, "document_type", None) is not None:
            doc_type_label = document.document_type.code
    if records is None:
        raise TypeError("validate_snrd requiere 'records' o 'document'")
    return _validate(records, _profile_for(db), doc_type_label)


def _validate(
    records, profile: SNRDProfile, doc_type_label: str | None
) -> tuple[list[dict], list[dict]]:
    errors: list[dict] = []
    warnings: list[dict] = []
    by_key: dict[str, list] = {}
    for rec in records:
        field = rec.metadata_field
        if field is None:
            continue
        by_key.setdefault(_field_key(field), []).append(rec)

    def values(element: str) -> list:
        return [r for r in by_key.get(element, []) if str(r.value or "").strip()]

    if not any(by_key.values()):
        errors.append(
            _snrd_error(
                "_document",
                "no_records",
                "SNRD: el documento no tiene registros de metadatos para validar",
            )
        )
        return errors, warnings

    # Elementos obligatorios del perfil.
    for element in profile.required_elements:
        if not values(element):
            code = "language_missing" if element == "language" else "missing_required"
            errors.append(
                _snrd_error(
                    element,
                    code,
                    f"SNRD: el elemento '{element}' es obligatorio para interoperabilidad",
                )
            )

    # Elementos recomendados del perfil.
    for element in profile.recommended_elements:
        if not values(element):
            warnings.append(
                _snrd_error(
                    element,
                    "recommended_missing",
                    f"SNRD: se recomienda incluir el elemento '{element}'",
                )
            )

    # Consistencia del conjunto: al menos un titulo y un autor.
    if not values("title"):
        if "title" not in profile.required_elements:
            errors.append(
                _snrd_error("title", "missing_required", "SNRD: se requiere al menos un titulo")
            )
    if not values("creator"):
        errors.append(
            _snrd_error("creator", "missing_creator", "SNRD: se requiere al menos un autor (creator)")
        )

    # Fechas en el formato del perfil (ISO por defecto) y sin valor vacio.
    for rec in values("date"):
        if profile.date_format != "iso":
            break
        if normalize_date(rec.value) is None:
            errors.append(
                _snrd_error(
                    "date",
                    "invalid_date",
                    "SNRD: la fecha debe estar en formato ISO (YYYY-MM-DD)",
                    rec.value,
                )
            )

    # Idioma dentro de los codigos permitidos por el perfil.
    for rec in values("language"):
        value = str(rec.value or "").strip()
        if _language_allowed(value, profile.languages):
            continue
        errors.append(
            _snrd_error(
                "language",
                "invalid_language",
                f"SNRD: el idioma '{value}' no esta en el perfil {profile.languages}",
                rec.value,
            )
        )

    # Identificadores DOI/ORCID con formato valido.
    for element in ("doi", "orcid", "identifier"):
        for rec in values(element):
            value = str(rec.value or "").strip()
            ok = (
                normalize_doi(value) is not None
                if element == "doi"
                else normalize_orcid(value) is not None
                if element == "orcid"
                else normalize_doi(value) is not None or normalize_orcid(value) is not None
            )
            if ok:
                continue
            code = {
                "doi": "invalid_doi",
                "orcid": "invalid_orcid",
                "identifier": "invalid_identifier",
            }[element]
            errors.append(_snrd_error(element, code, f"SNRD: identificador invalido: '{value}'", rec.value))

    # Embargo: solo permitido si el perfil lo habilita.
    if not profile.allow_embargo:
        for rec in values("rights"):
            if "embargo" in str(rec.value or "").lower():
                warnings.append(
                    _snrd_error(
                        "rights",
                        "embargo_not_allowed",
                        "SNRD: el perfil institucional no habilita el embargo",
                        rec.value,
                    )
                )
    return errors, warnings


def _language_allowed(value: str, languages: list[str]) -> bool:
    low = value.lower()
    exact = value in languages or low in languages
    if exact:
        return True
    for code in languages:
        aliases = _BASE_LANGUAGE_ALIASES.get(code.lower())
        if aliases and low in aliases:
            return True
    return False