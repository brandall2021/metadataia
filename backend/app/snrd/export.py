"""Exportación SNRD-DC (FASE 13): registros de metadatos → metadatos DSpace."""

DC_ALIASES = {
    "creator": "dc.contributor.author",
    "date": "dc.date.issued",
    "description": "dc.description.abstract",
    "language": "dc.language.iso",
}


def dc_key(element: str, qualifier: str | None = None) -> str:
    if element in DC_ALIASES:
        return DC_ALIASES[element]
    return "dc." + element + (f".{qualifier}" if qualifier else "")


def dc_fields(records, identifier: str | None = None) -> dict:
    """Convierte el listado de MetadataRecord en el mapa SNRD-DC de DSpace."""
    out: dict = {}
    for rec in sorted(records, key=lambda r: (r.metadata_field.display_name or "") if r.metadata_field else ""):
        fld = rec.metadata_field
        if fld is None or not rec.value:
            continue
        key = dc_key(fld.element, fld.qualifier or None)
        out.setdefault(key, []).append(
            {"value": rec.value, "language": rec.language, "authority": None, "confidence": -1}
        )
    if identifier:
        out.setdefault("dc.identifier.other", []).append(
            {"value": identifier, "language": None, "authority": None, "confidence": -1}
        )
    return out