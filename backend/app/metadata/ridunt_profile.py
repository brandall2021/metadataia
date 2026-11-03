"""Perfil de metadatos RIDUNT / SNRD.

Los campos reproducen las claves DSpace que publica RIDUNT en sus fichas
(p. ej. ``dc.contributor.advisor``, ``dc.description.abstract`` o
``dc.identifier.citation``), con etiquetas y ayudas en espanol para el
formulario de carga.
"""

from sqlalchemy.orm import Session

from app.models.metadata import (
    DocumentType,
    DocumentTypeMetadataField,
    MetadataField,
    MetadataSchema,
    Vocabulary,
)

RIDUNT_SCHEMA = {
    "name": "RIDUNT / SNRD",
    "code": "snrd-dc",
    "namespace": "dc",
    "description": (
        "Perfil institucional basado en Dublin Core y SNRD. Reproduce los metadatos "
        "que publica RIDUNT en sus fichas de recursos."
    ),
    "active": True,
}

RIDUNT_PROFILE_FIELDS = [
    {
        "element": "title",
        "qualifier": None,
        "display_name": "Titulo",
        "description": "Titulo principal del recurso, tal como figura en el documento.",
        "data_type": "text",
        "required": True,
        "repeatable": False,
        "ai_extractable": True,
        "order_index": 0,
    },
    {
        "element": "title",
        "qualifier": "alternative",
        "display_name": "Titulo alternativo",
        "description": "Subtitulo, traduccion o variante del titulo principal.",
        "data_type": "text",
        "required": False,
        "repeatable": True,
        "ai_extractable": True,
        "order_index": 1,
    },
    {
        "element": "creator",
        "qualifier": None,
        "display_name": "Autor",
        "description": "Autor o autores personales del trabajo. Un autor por valor.",
        "data_type": "text",
        "required": True,
        "repeatable": True,
        "ai_extractable": True,
        "order_index": 2,
    },
    {
        "element": "contributor",
        "qualifier": "advisor",
        "display_name": "Director / tutor",
        "description": "Director, directora o tutor del trabajo (tesis, tesina, pasantia).",
        "data_type": "text",
        "required": False,
        "repeatable": True,
        "ai_extractable": True,
        "order_index": 3,
    },
    {
        "element": "contributor",
        "qualifier": None,
        "display_name": "Colaborador",
        "description": "Otros aportantes que no son autores ni directores.",
        "data_type": "text",
        "required": False,
        "repeatable": True,
        "ai_extractable": True,
        "order_index": 4,
    },
    {
        "element": "date",
        "qualifier": "issued",
        "display_name": "Fecha de publicacion",
        "description": "Anio o fecha de publicacion del recurso (ISO 8601: AAAA o AAAA-MM-DD).",
        "data_type": "date",
        "required": True,
        "repeatable": False,
        "ai_extractable": True,
        "validation_type": "date",
        "order_index": 5,
    },
    {
        "element": "type",
        "qualifier": None,
        "display_name": "Tipo de recurso",
        "description": "Tipo documental normalizado (tesis, articulo, libro, ponencia...).",
        "data_type": "text",
        "required": True,
        "repeatable": False,
        "ai_extractable": True,
        "vocabulary_code": "ridunt-type",
        "order_index": 6,
    },
    {
        "element": "type",
        "qualifier": "subtype",
        "display_name": "Subtipo documental",
        "description": "Detalle del tipo, por ejemplo Tesis doctoral o Articulo original.",
        "data_type": "text",
        "required": False,
        "repeatable": False,
        "ai_extractable": True,
        "order_index": 7,
    },
    {
        "element": "language",
        "qualifier": "iso",
        "display_name": "Idioma",
        "description": "Idioma principal del contenido en codigo ISO 639-2 (spa, eng, por).",
        "data_type": "text",
        "required": True,
        "repeatable": False,
        "ai_extractable": True,
        "vocabulary_code": "ridunt-language",
        "order_index": 8,
    },
    {
        "element": "publisher",
        "qualifier": None,
        "display_name": "Editorial / institucion",
        "description": "Institucion, facultad o editorial responsable de la publicacion.",
        "data_type": "text",
        "required": False,
        "repeatable": False,
        "ai_extractable": True,
        "order_index": 9,
    },
    {
        "element": "description",
        "qualifier": "abstract",
        "display_name": "Resumen",
        "description": "Resumen o abstract del recurso en el idioma original.",
        "data_type": "textarea",
        "required": False,
        "repeatable": False,
        "ai_extractable": True,
        "order_index": 10,
    },
    {
        "element": "description",
        "qualifier": "sponsorship",
        "display_name": "Financiamiento",
        "description": "Becas, proyectos o instituciones que financiaron el trabajo.",
        "data_type": "textarea",
        "required": False,
        "repeatable": False,
        "ai_extractable": True,
        "order_index": 11,
    },
    {
        "element": "subject",
        "qualifier": None,
        "display_name": "Palabras clave / materias",
        "description": "Descriptores tematicos del recurso. Un valor por palabra clave.",
        "data_type": "text",
        "required": False,
        "repeatable": True,
        "ai_extractable": True,
        "order_index": 12,
    },
    {
        "element": "subject",
        "qualifier": "other",
        "display_name": "Grado / nota de titulo",
        "description": "Titulo academico obtenido o nota adicional, por ejemplo Doctora en Ciencias Biologicas.",
        "data_type": "text",
        "required": False,
        "repeatable": True,
        "ai_extractable": True,
        "order_index": 13,
    },
    {
        "element": "identifier",
        "qualifier": "citation",
        "display_name": "Cita bibliografica",
        "description": "Referencia completa del recurso en el estilo institucional.",
        "data_type": "textarea",
        "required": False,
        "repeatable": False,
        "ai_extractable": True,
        "order_index": 14,
    },
    {
        "element": "identifier",
        "qualifier": "uri",
        "display_name": "URI del recurso",
        "description": "Enlace persistente al recurso (handle, DOI o URL institucional).",
        "data_type": "text",
        "required": False,
        "repeatable": False,
        "ai_extractable": False,
        "order_index": 15,
    },
    {
        "element": "relation",
        "qualifier": "ispartofseries",
        "display_name": "Serie / coleccion",
        "description": "Serie, coleccion o numero dentro de una publicacion seriada.",
        "data_type": "text",
        "required": False,
        "repeatable": True,
        "ai_extractable": True,
        "order_index": 16,
    },
    {
        "element": "format",
        "qualifier": None,
        "display_name": "Formato",
        "description": "Formato del archivo depositado, por ejemplo application/pdf.",
        "data_type": "text",
        "required": False,
        "repeatable": False,
        "ai_extractable": False,
        "order_index": 17,
    },
    {
        "element": "rights",
        "qualifier": None,
        "display_name": "Derechos de uso",
        "description": "Condiciones de acceso y uso del recurso.",
        "data_type": "textarea",
        "required": False,
        "repeatable": False,
        "ai_extractable": True,
        "order_index": 18,
    },
    {
        "element": "rights",
        "qualifier": "license",
        "display_name": "Licencia",
        "description": "Nombre de la licencia, por ejemplo Creative Commons BY-NC-ND 4.0.",
        "data_type": "text",
        "required": False,
        "repeatable": False,
        "ai_extractable": True,
        "order_index": 19,
    },
    {
        "element": "rights",
        "qualifier": "uri",
        "display_name": "URI de licencia",
        "description": "Enlace a los terminos de la licencia.",
        "data_type": "text",
        "required": False,
        "repeatable": False,
        "ai_extractable": False,
        "order_index": 20,
    },
]

# Campos que generaba el seed anterior. Si ya no forman parte del perfil se
# desactivan (no se borran) para no perder registros cargados.
LEGACY_SEED_FIELDS = {
    ("title", None),
    ("creator", None),
    ("contributor", None),
    ("date", None),
    ("type", None),
    ("language", None),
    ("subject", None),
    ("description", None),
    ("publisher", None),
    ("identifier", None),
    ("source", None),
    ("relation", None),
    ("coverage", None),
    ("format", None),
    ("rights", None),
}


def _link_active_fields_to_document_types(db: Session, schema: MetadataSchema) -> int:
    """Asigna el perfil a los tipos documentales sin seleccion propia.

    Un tipo que ya tiene campos configurados se respeta tal cual: solo se
    completa la asociacion cuando esta vacia.
    """
    fields = (
        db.query(MetadataField)
        .filter_by(schema_id=schema.id, active=True)
        .order_by(MetadataField.order_index)
        .all()
    )
    if not fields:
        return 0

    linked = 0
    for document_type in db.query(DocumentType).filter(DocumentType.active.is_(True)).all():
        has_links = (
            db.query(DocumentTypeMetadataField.id)
            .filter(DocumentTypeMetadataField.document_type_id == document_type.id)
            .first()
        )
        if has_links is not None:
            continue
        for field in fields:
            db.add(
                DocumentTypeMetadataField(
                    document_type_id=document_type.id,
                    metadata_field_id=field.id,
                    order_index=field.order_index,
                )
            )
        linked += 1
    return linked


def sync_ridunt_profile(db: Session) -> MetadataSchema:
    """Crea o actualiza el esquema RIDUNT y sus campos de forma idempotente."""
    schema = db.query(MetadataSchema).filter_by(code=RIDUNT_SCHEMA["code"]).one_or_none()
    if schema is None:
        schema = MetadataSchema(**RIDUNT_SCHEMA)
        db.add(schema)
        db.flush()
    else:
        schema.name = RIDUNT_SCHEMA["name"]
        schema.namespace = RIDUNT_SCHEMA["namespace"]
        schema.description = RIDUNT_SCHEMA["description"]
        schema.active = True

    vocabulary_by_code = {
        vocab.code: vocab for vocab in db.query(Vocabulary).all()
    }
    existing = {
        (field.element, field.qualifier): field
        for field in db.query(MetadataField).filter_by(schema_id=schema.id).all()
    }
    profile_keys = {
        (data["element"], data["qualifier"]) for data in RIDUNT_PROFILE_FIELDS
    }

    for key, field in existing.items():
        if key not in profile_keys and key in LEGACY_SEED_FIELDS:
            field.active = False

    for data in RIDUNT_PROFILE_FIELDS:
        key = (data["element"], data["qualifier"])
        field = existing.get(key)
        if field is None:
            field = MetadataField(
                schema_id=schema.id,
                element=data["element"],
                qualifier=data["qualifier"],
            )
            db.add(field)
        field.display_name = data["display_name"]
        field.description = data["description"]
        field.data_type = data["data_type"]
        field.required = data["required"]
        field.repeatable = data["repeatable"]
        field.editable = True
        field.ai_extractable = data["ai_extractable"]
        field.validation_type = data.get("validation_type")
        field.normalization_type = data.get("normalization_type")
        vocabulary_code = data.get("vocabulary_code")
        vocabulary = vocabulary_by_code.get(vocabulary_code) if vocabulary_code else None
        field.vocabulary_id = vocabulary.id if vocabulary else None
        field.order_index = data["order_index"]
        field.active = True

    db.flush()
    _link_active_fields_to_document_types(db, schema)
    db.commit()
    db.refresh(schema)
    return schema
