"""Datos iniciales (seed): usuarios, roles, permisos y metadatos base.

Idempotente: puede ejecutarse multiples veces sin duplicar datos.
Requiere que las migraciones esten aplicadas (make migrate).
"""

import os

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.security import encrypt_secret, hash_password
from app.models import (
    AIAgent,
    AIAgentVersion,
    AIModel,
    AIProvider,
    DocumentType,
    MetadataField,
    MetadataSchema,
    Permission,
    Repository,
    RepositoryCollection,
    Role,
    Vocabulary,
    VocabularyValue,
    User,
)
from app.models.user import role_permissions, user_roles

RIDUNT_REPOSITORY_CODE = "ridunt"
RIDUNT_REPOSITORY_NAME = "RIDUNT"
RIDUNT_REPOSITORY_BASE_URL = "https://ridunt.unt.edu.ar"
RIDUNT_REPOSITORY_API_URL = "https://riunt.face-unt.ar/server/api"
RIDUNT_REPOSITORY_USERNAME = "cpereyra@face.unt.edu.ar"
RIDUNT_REPOSITORY_CREDENTIAL_ENV = "RIDUNT_REPOSITORY_CREDENTIAL"
RIDUNT_REPOSITORY_AUTH_TYPE = "basic"
RIDUNT_COLLECTION_HANDLE = "123456789/1732"
RIDUNT_SYNC_COMMUNITY_UUID = "9bed1cdd-b1c6-4be9-90ec-435bcba374ac"

RIDUNT_SCHEMA_CODE = "snrd-dc"
RIDUNT_SCHEMA_NAME = "RIDUNT / SNRD Dublin Core"
RIDUNT_SCHEMA_NAMESPACE = "dc"

RIDUNT_VOCABULARIES = [
    {
        "code": "unesco-thesaurus",
        "name": "UNESCO Thesaurus",
        "description": "Tesauro UNESCO para materias y descriptores tematicos.",
        "source": "UNESCO Thesaurus",
        "values": [
            {"code": "educacion", "label": "Educacion", "normalized_value": "educacion", "synonyms": ["education"]},
            {"code": "ensenanza-superior", "label": "Ensenanza superior", "normalized_value": "ensenanza superior", "synonyms": ["higher education", "universidad"]},
            {"code": "investigacion", "label": "Investigacion", "normalized_value": "investigacion", "synonyms": ["research"]},
            {"code": "ciencia", "label": "Ciencia", "normalized_value": "ciencia", "synonyms": ["science"]},
            {"code": "tecnologia", "label": "Tecnologia", "normalized_value": "tecnologia", "synonyms": ["technology"]},
            {"code": "informacion-cientifica", "label": "Informacion cientifica", "normalized_value": "informacion cientifica", "synonyms": ["scientific information"]},
            {"code": "comunicacion", "label": "Comunicacion", "normalized_value": "comunicacion", "synonyms": ["communication"]},
            {"code": "ciencias-sociales", "label": "Ciencias sociales", "normalized_value": "ciencias sociales", "synonyms": ["social sciences"]},
            {"code": "economia", "label": "Economia", "normalized_value": "economia", "synonyms": ["economics"]},
            {"code": "derecho", "label": "Derecho", "normalized_value": "derecho", "synonyms": ["law"]},
            {"code": "salud", "label": "Salud", "normalized_value": "salud", "synonyms": ["health"]},
            {"code": "medio-ambiente", "label": "Medio ambiente", "normalized_value": "medio ambiente", "synonyms": ["environment"]},
            {"code": "agricultura", "label": "Agricultura", "normalized_value": "agricultura", "synonyms": ["agriculture"]},
            {"code": "ingenieria", "label": "Ingenieria", "normalized_value": "ingenieria", "synonyms": ["engineering"]},
            {"code": "matematica", "label": "Matematica", "normalized_value": "matematica", "synonyms": ["mathematics"]},
            {"code": "fisica", "label": "Fisica", "normalized_value": "fisica", "synonyms": ["physics"]},
            {"code": "quimica", "label": "Quimica", "normalized_value": "quimica", "synonyms": ["chemistry"]},
            {"code": "biologia", "label": "Biologia", "normalized_value": "biologia", "synonyms": ["biology"]},
            {"code": "historia", "label": "Historia", "normalized_value": "historia", "synonyms": ["history"]},
            {"code": "cultura", "label": "Cultura", "normalized_value": "cultura", "synonyms": ["culture"]},
        ],
    },
    {
        "code": "ridunt-language",
        "name": "RIDUNT Languages",
        "description": "Idiomas controlados para RIDUNT/SNRD.",
        "source": "RIDUNT",
        "values": [
            {"code": "spa", "label": "Espa\u00f1ol", "normalized_value": "spa", "synonyms": ["es", "spanish"]},
            {"code": "eng", "label": "Ingles", "normalized_value": "eng", "synonyms": ["en", "english"]},
            {"code": "por", "label": "Portugues", "normalized_value": "por", "synonyms": ["pt", "portuguese"]},
        ],
    },
    {
        "code": "ridunt-type",
        "name": "RIDUNT Types",
        "description": "Tipos documentales controlados para RIDUNT/SNRD.",
        "source": "RIDUNT",
        "values": [
            {"code": "tesis", "label": "Tesis", "normalized_value": "tesis", "synonyms": ["tesis de maestria", "tesis de doctorado"]},
            {"code": "articulo", "label": "Articulo", "normalized_value": "articulo", "synonyms": ["paper", "article"]},
            {"code": "libro", "label": "Libro", "normalized_value": "libro", "synonyms": ["book"]},
            {"code": "capitulo_libro", "label": "Capitulo de libro", "normalized_value": "capitulo_libro", "synonyms": ["chapter"]},
            {"code": "informe", "label": "Informe", "normalized_value": "informe", "synonyms": ["report"]},
            {"code": "ponencia", "label": "Ponencia", "normalized_value": "ponencia", "synonyms": ["conference paper", "paper de congreso"]},
            {"code": "preprint", "label": "Preprint", "normalized_value": "preprint", "synonyms": ["pre-print"]},
            {"code": "dataset", "label": "Dataset", "normalized_value": "dataset", "synonyms": ["data set"]},
            {"code": "software", "label": "Software", "normalized_value": "software", "synonyms": ["code", "app"]},
            {"code": "imagen", "label": "Imagen", "normalized_value": "imagen", "synonyms": ["image", "figure"]},
            {"code": "audio", "label": "Audio", "normalized_value": "audio", "synonyms": ["sound"]},
            {"code": "video", "label": "Video", "normalized_value": "video", "synonyms": ["film", "movie"]},
        ],
    },
    {
        "code": "ridunt-rights",
        "name": "RIDUNT Rights",
        "description": "Derechos y niveles de acceso controlados para RIDUNT/SNRD.",
        "source": "RIDUNT",
        "values": [
            {"code": "openAccess", "label": "Open Access", "normalized_value": "openAccess", "synonyms": ["open access", "oa"]},
            {"code": "restrictedAccess", "label": "Restricted Access", "normalized_value": "restrictedAccess", "synonyms": ["restricted", "limited access"]},
            {"code": "embargoedAccess", "label": "Embargoed Access", "normalized_value": "embargoedAccess", "synonyms": ["embargo", "embargoed"]},
            {"code": "closedAccess", "label": "Closed Access", "normalized_value": "closedAccess", "synonyms": ["closed", "private"]},
        ],
    },
]

RIDUNT_DOCUMENT_TYPES = [
    {"code": "tesis", "name": "Tesis", "description": "Trabajos de tesis y disertaciones."},
    {"code": "articulo", "name": "Articulo", "description": "Articulos cientificos y tecnicos."},
    {"code": "libro", "name": "Libro", "description": "Libros y monografias."},
    {"code": "capitulo_libro", "name": "Capitulo de libro", "description": "Capitulos de libros."},
    {"code": "informe", "name": "Informe", "description": "Informes tecnicos o institucionales."},
    {"code": "ponencia", "name": "Ponencia", "description": "Ponencias y trabajos de congreso."},
    {"code": "preprint", "name": "Preprint", "description": "Versiones preliminares de articulos."},
    {"code": "dataset", "name": "Dataset", "description": "Conjuntos de datos de investigacion."},
    {"code": "software", "name": "Software", "description": "Software, codigo o aplicaciones."},
    {"code": "imagen", "name": "Imagen", "description": "Imagenes, figuras y material grafico."},
    {"code": "audio", "name": "Audio", "description": "Archivos y materiales de audio."},
    {"code": "video", "name": "Video", "description": "Archivos y materiales audiovisuales."},
]

RIDUNT_FIELD_VOCABULARIES = {
    "subject": "unesco-thesaurus",
    "language": "ridunt-language",
    "type": "ridunt-type",
    "rights": "ridunt-rights",
}

RIDUNT_FIELDS = [
    {
        "element": "title",
        "display_name": "Titulo",
        "description": "Titulo principal del recurso",
        "required": True,
        "repeatable": False,
        "data_type": "text",
        "order_index": 0,
    },
    {
        "element": "creator",
        "display_name": "Autor",
        "description": "Autor o autores principales",
        "required": True,
        "repeatable": True,
        "data_type": "text",
        "order_index": 1,
    },
    {
        "element": "contributor",
        "display_name": "Contribuyente",
        "description": "Colaboradores, directores y otros aportantes",
        "required": False,
        "repeatable": True,
        "data_type": "text",
        "order_index": 2,
    },
    {
        "element": "date",
        "display_name": "Fecha",
        "description": "Fecha de publicacion o emision",
        "required": True,
        "repeatable": False,
        "data_type": "date",
        "validation_type": "date",
        "order_index": 3,
    },
    {
        "element": "type",
        "display_name": "Tipo documental",
        "description": "Libro, tesis, articulo, informe u otro tipo documental",
        "required": True,
        "repeatable": False,
        "data_type": "text",
        "order_index": 4,
    },
    {
        "element": "language",
        "display_name": "Idioma",
        "description": "Idioma principal del recurso",
        "required": True,
        "repeatable": False,
        "data_type": "text",
        "order_index": 5,
    },
    {
        "element": "subject",
        "display_name": "Tema",
        "description": "Palabras clave o materias",
        "required": False,
        "repeatable": True,
        "data_type": "text",
        "order_index": 6,
    },
    {
        "element": "description",
        "display_name": "Resumen",
        "description": "Resumen o abstract del recurso",
        "required": False,
        "repeatable": False,
        "data_type": "text",
        "order_index": 7,
    },
    {
        "element": "publisher",
        "display_name": "Editorial / institucion",
        "description": "Institucion o editorial responsable",
        "required": False,
        "repeatable": False,
        "data_type": "text",
        "order_index": 8,
    },
    {
        "element": "identifier",
        "display_name": "Identificador",
        "description": "DOI, URL, handle u otro identificador",
        "required": False,
        "repeatable": True,
        "data_type": "text",
        "order_index": 9,
    },
    {
        "element": "source",
        "display_name": "Fuente",
        "description": "Coleccion, serie o fuente original",
        "required": False,
        "repeatable": False,
        "data_type": "text",
        "order_index": 10,
    },
    {
        "element": "relation",
        "display_name": "Relacion",
        "description": "Relacion con otros recursos",
        "required": False,
        "repeatable": True,
        "data_type": "text",
        "order_index": 11,
    },
    {
        "element": "coverage",
        "display_name": "Cobertura",
        "description": "Cobertura temporal o espacial",
        "required": False,
        "repeatable": True,
        "data_type": "text",
        "order_index": 12,
    },
    {
        "element": "format",
        "display_name": "Formato",
        "description": "Formato fisico o digital del recurso",
        "required": False,
        "repeatable": True,
        "data_type": "text",
        "order_index": 13,
    },
    {
        "element": "rights",
        "display_name": "Derechos",
        "description": "Licencia, acceso o restricciones de uso",
        "required": False,
        "repeatable": False,
        "data_type": "text",
        "order_index": 14,
    },
]

RIDUNT_AGENT_SYSTEM_PROMPT = (
    "Eres un catalogador experto en RIDUNT y SNRD. Extraes metadatos de documentos "
    "académicos de la UNT. Prioriza precisión sobre cobertura, no inventes datos, "
    "conserva nombres propios y títulos tal como aparecen y normaliza fechas a ISO 8601 "
    "e idiomas a códigos SNRD cuando sea posible. Si un campo no tiene evidencia suficiente, "
    "omítelo. Responde solo con JSON válido."
)

RIDUNT_AGENT_EXTRACTION_PROMPT = """Extrae los metadatos del documento.

Tipo documental: {{document_type}}
Esquema: {{metadata_schema}}
Campos disponibles:
{{metadata_fields}}
Texto del documento:
{{document_text}}

Devuelve solo JSON con esta estructura:
{
  "fields": {
    "title": {"value": "...", "confidence": 0.0, "source_page": 1, "source_text": "..."},
    "creator": [{"value": "...", "confidence": 0.0, "source_page": 1, "source_text": "..."}],
    "date": {"value": "YYYY-MM-DD", "confidence": 0.0, "source_page": 1, "source_text": "..."},
    "type": {"value": "...", "confidence": 0.0, "source_page": 1, "source_text": "..."},
    "language": {"value": "spa", "confidence": 0.0, "source_page": 1, "source_text": "..."},
    "subject": [{"value": "...", "confidence": 0.0, "source_page": 1, "source_text": "..."}],
    "description": {"value": "...", "confidence": 0.0, "source_page": 1, "source_text": "..."},
    "publisher": {"value": "...", "confidence": 0.0, "source_page": 1, "source_text": "..."},
    "identifier": [{"value": "...", "confidence": 0.0, "source_page": 1, "source_text": "..."}],
    "source": {"value": "...", "confidence": 0.0, "source_page": 1, "source_text": "..."},
    "relation": [{"value": "...", "confidence": 0.0, "source_page": 1, "source_text": "..."}],
    "coverage": [{"value": "...", "confidence": 0.0, "source_page": 1, "source_text": "..."}],
    "format": [{"value": "...", "confidence": 0.0, "source_page": 1, "source_text": "..."}],
    "rights": {"value": "...", "confidence": 0.0, "source_page": 1, "source_text": "..."},
    "contributor": [{"value": "...", "confidence": 0.0, "source_page": 1, "source_text": "..."}]
  }
}

Reglas:
- Usa solo campos del esquema.
- Si el campo admite múltiples valores, devuelve una lista.
- No agregues texto fuera del JSON.
- Prioriza title, creator, date, type y language.
- language debe ser spa, eng o por si puedes inferirlo.
- Si la fecha no puede normalizarse a ISO, devuelve el valor exacto que aparece.
- Si no hay evidencia suficiente, omite el campo.
"""


def _upsert_ridunt_metadata(db: Session) -> None:
    schema = db.query(MetadataSchema).filter_by(code=RIDUNT_SCHEMA_CODE).one_or_none()
    if schema is None:
        schema = MetadataSchema(
            name=RIDUNT_SCHEMA_NAME,
            code=RIDUNT_SCHEMA_CODE,
            namespace=RIDUNT_SCHEMA_NAMESPACE,
            description="Perfil RIDUNT basado en Dublin Core y SNRD.",
            active=True,
        )
        db.add(schema)
        db.flush()
    else:
        schema.name = RIDUNT_SCHEMA_NAME
        schema.namespace = RIDUNT_SCHEMA_NAMESPACE
        schema.description = "Perfil RIDUNT basado en Dublin Core y SNRD."
        schema.active = True

    for field_data in RIDUNT_FIELDS:
        field = (
            db.query(MetadataField)
            .filter_by(schema_id=schema.id, element=field_data["element"], qualifier=None)
            .one_or_none()
        )
        if field is None:
            field = MetadataField(schema_id=schema.id, element=field_data["element"])
            db.add(field)
            db.flush()
        field.display_name = field_data["display_name"]
        field.description = field_data["description"]
        field.data_type = field_data.get("data_type", "text")
        field.required = field_data.get("required", False)
        field.repeatable = field_data.get("repeatable", False)
        field.editable = True
        field.ai_extractable = True
        field.validation_type = field_data.get("validation_type")
        field.normalization_type = field_data.get("normalization_type")
        field.order_index = field_data.get("order_index")
        if field_data["element"] in RIDUNT_FIELD_VOCABULARIES:
            vocab = db.query(Vocabulary).filter_by(code=RIDUNT_FIELD_VOCABULARIES[field_data["element"]]).one_or_none()
            field.vocabulary_id = vocab.id if vocab else None
        field.active = True


def _upsert_ridunt_repository(db: Session) -> None:
    repo = db.query(Repository).filter_by(code=RIDUNT_REPOSITORY_CODE).one_or_none()
    credential = os.getenv(RIDUNT_REPOSITORY_CREDENTIAL_ENV, "").strip()
    credential_reference = f"repository.{RIDUNT_REPOSITORY_CODE}.credential" if credential else None
    configuration_json = {"sync_community_uuid": RIDUNT_SYNC_COMMUNITY_UUID}
    if credential:
        configuration_json["credential"] = encrypt_secret(credential)

    if repo is None:
        repo = Repository(
            name=RIDUNT_REPOSITORY_NAME,
            code=RIDUNT_REPOSITORY_CODE,
            base_url=RIDUNT_REPOSITORY_BASE_URL,
            api_url=RIDUNT_REPOSITORY_API_URL,
            authentication_type=RIDUNT_REPOSITORY_AUTH_TYPE,
            username=RIDUNT_REPOSITORY_USERNAME,
            credential_reference=credential_reference,
            active=True,
            configuration_json=configuration_json,
        )
        db.add(repo)
        db.flush()
        return

    repo.name = RIDUNT_REPOSITORY_NAME
    repo.base_url = RIDUNT_REPOSITORY_BASE_URL
    repo.api_url = RIDUNT_REPOSITORY_API_URL
    repo.authentication_type = RIDUNT_REPOSITORY_AUTH_TYPE
    repo.username = RIDUNT_REPOSITORY_USERNAME
    repo.active = True
    cfg = dict(repo.configuration_json or {})
    cfg["sync_community_uuid"] = RIDUNT_SYNC_COMMUNITY_UUID
    if credential:
        repo.credential_reference = credential_reference
        cfg["credential"] = encrypt_secret(credential)
    repo.configuration_json = cfg


def _upsert_ridunt_collection(db: Session) -> None:
    repo = db.query(Repository).filter_by(code=RIDUNT_REPOSITORY_CODE).one_or_none()
    if repo is None:
        return

    collection = (
        db.query(RepositoryCollection)
        .filter(
            RepositoryCollection.repository_id == repo.id,
            RepositoryCollection.handle == RIDUNT_COLLECTION_HANDLE,
        )
        .one_or_none()
    )
    if collection is None:
        collection = RepositoryCollection(
            repository_id=repo.id,
            external_id=RIDUNT_COLLECTION_HANDLE,
            name="RIDUNT",
            handle=RIDUNT_COLLECTION_HANDLE,
            document_type_id=None,
            active=True,
        )
        db.add(collection)
        return

    collection.external_id = RIDUNT_COLLECTION_HANDLE
    collection.name = "RIDUNT"
    collection.handle = RIDUNT_COLLECTION_HANDLE
    collection.document_type_id = None
    collection.active = True


def _upsert_ridunt_vocabularies(db: Session) -> None:
    for vocab_data in RIDUNT_VOCABULARIES:
        vocab = db.query(Vocabulary).filter_by(code=vocab_data["code"]).one_or_none()
        if vocab is None:
            vocab = Vocabulary(
                name=vocab_data["name"],
                code=vocab_data["code"],
                description=vocab_data["description"],
                source=vocab_data["source"],
                active=True,
            )
            db.add(vocab)
            db.flush()
        else:
            vocab.name = vocab_data["name"]
            vocab.description = vocab_data["description"]
            vocab.source = vocab_data["source"]
            vocab.active = True

        for value_data in vocab_data["values"]:
            value = (
                db.query(VocabularyValue)
                .filter_by(vocabulary_id=vocab.id, code=value_data["code"])
                .one_or_none()
            )
            normalized_value = value_data.get("normalized_value") or value_data["label"]
            synonyms = sorted({s.strip() for s in value_data.get("synonyms", []) if s.strip()})
            if value is None:
                value = VocabularyValue(
                    vocabulary_id=vocab.id,
                    code=value_data["code"],
                    label=value_data["label"],
                    normalized_value=normalized_value,
                    synonyms_json=synonyms,
                    active=True,
                )
                db.add(value)
            else:
                value.label = value_data["label"]
                value.normalized_value = normalized_value
                value.synonyms_json = synonyms
                value.active = True


def _upsert_ridunt_document_types(db: Session) -> None:
    for type_data in RIDUNT_DOCUMENT_TYPES:
        type_ = db.query(DocumentType).filter_by(code=type_data["code"]).one_or_none()
        if type_ is None:
            type_ = DocumentType(
                name=type_data["name"],
                code=type_data["code"],
                description=type_data["description"],
                active=True,
            )
            db.add(type_)
            continue

        type_.name = type_data["name"]
        type_.description = type_data["description"]
        type_.active = True


def _upsert_ridunt_ai_seed(db: Session) -> None:
    provider = db.query(AIProvider).filter_by(code="ridunt-local").one_or_none()
    if provider is None:
        provider = AIProvider(
            name="RIDUNT Local",
            code="ridunt-local",
            type="openai-compatible",
            base_url=None,
            active=False,
        )
        db.add(provider)
        db.flush()
    else:
        provider.name = "RIDUNT Local"
        provider.type = "openai-compatible"
        provider.base_url = None
        provider.active = False

    model = db.query(AIModel).filter_by(provider_id=provider.id, model_identifier="ridunt-extract").one_or_none()
    if model is None:
        model = AIModel(
            provider_id=provider.id,
            name="RIDUNT Extractor",
            model_identifier="ridunt-extract",
            context_window=8192,
            supports_json=True,
            supports_vision=False,
            temperature_default=0.1,
            max_tokens_default=2048,
            active=False,
        )
        db.add(model)
        db.flush()
    else:
        model.name = "RIDUNT Extractor"
        model.context_window = 8192
        model.supports_json = True
        model.supports_vision = False
        model.temperature_default = 0.1
        model.max_tokens_default = 2048
        model.active = False

    agent = db.query(AIAgent).filter_by(code="ridunt-snrd").one_or_none()
    if agent is None:
        agent = AIAgent(
            name="RIDUNT / SNRD",
            code="ridunt-snrd",
            description="Agente base para extracción de metadatos RIDUNT/SNRD.",
            document_type_id=None,
            active=False,
        )
        db.add(agent)
        db.flush()
    else:
        agent.name = "RIDUNT / SNRD"
        agent.description = "Agente base para extracción de metadatos RIDUNT/SNRD."
        agent.document_type_id = None
        agent.active = False

    version = agent.current_version
    if version is None:
        next_version_number = (
            db.query(AIAgentVersion.version_number)
            .filter(AIAgentVersion.agent_id == agent.id)
            .order_by(AIAgentVersion.version_number.desc())
            .first()
        )
        version = AIAgentVersion(
            agent_id=agent.id,
            version_number=(next_version_number[0] + 1 if next_version_number else 1),
            model_id=model.id,
            system_prompt=RIDUNT_AGENT_SYSTEM_PROMPT,
            extraction_prompt=RIDUNT_AGENT_EXTRACTION_PROMPT,
            temperature=0.1,
            max_tokens=2048,
            output_schema_json={
                "type": "object",
                "properties": {
                    "fields": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "object"},
                            "creator": {"type": "array"},
                            "date": {"type": "object"},
                            "type": {"type": "object"},
                            "language": {"type": "object"},
                        },
                    }
                },
            },
            configuration_json=None,
            active=True,
        )
        db.add(version)
        db.flush()
        agent.current_version_id = version.id
    else:
        version.model_id = model.id
        version.system_prompt = RIDUNT_AGENT_SYSTEM_PROMPT
        version.extraction_prompt = RIDUNT_AGENT_EXTRACTION_PROMPT
        version.temperature = 0.1
        version.max_tokens = 2048
        version.output_schema_json = {
            "type": "object",
            "properties": {
                "fields": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "object"},
                        "creator": {"type": "array"},
                        "date": {"type": "object"},
                        "type": {"type": "object"},
                        "language": {"type": "object"},
                    },
                }
            },
        }
        version.active = True
        agent.current_version_id = version.id

PERMISSIONS = [
    ("dashboard.view", "Ver dashboard"),
    ("document.upload", "Subir documentos"),
    ("document.view", "Ver documentos"),
    ("document.review", "Revisar metadatos"),
    ("document.approve", "Aprobar documentos"),
    ("document.deposit", "Depositar en repositorio"),
    ("admin.users.manage", "Administrar usuarios"),
    ("admin.roles.manage", "Administrar roles y permisos"),
    ("admin.ai.providers.manage", "Administrar proveedores de IA"),
    ("admin.ai.models.manage", "Administrar modelos de IA"),
    ("admin.ai.agents.manage", "Administrar agentes de IA"),
    ("admin.metadata.manage", "Administrar esquemas y campos de metadatos"),
    ("admin.vocabularies.manage", "Administrar vocabularios"),
    ("admin.document_types.manage", "Administrar tipos documentales"),
    ("admin.repositories.manage", "Administrar repositorios"),
    ("admin.settings.manage", "Administrar configuracion global"),
    ("audit.view", "Ver registros de auditoria"),
]

ROLES = {
    "ADMIN": "Administrador del sistema con acceso total.",
    "CATALOGADOR": "Carga documentos, revisa metadatos, aprueba y deposita.",
    "REVISOR": "Revisa y corrige metadatos antes del deposito.",
}

ROLE_PERMISSIONS = {
    "ADMIN": [code for code, _ in PERMISSIONS],
    "CATALOGADOR": [
        "dashboard.view",
        "document.upload",
        "document.view",
        "document.review",
        "document.approve",
        "document.deposit",
    ],
    "REVISOR": ["dashboard.view", "document.view", "document.review"],
}

USERS = [
    {"username": "admin", "email": "admin@example.com", "password": "metadataia123",
     "first_name": "Administrador", "last_name": "Sistema", "roles": ["ADMIN"]},
    {"username": "catalogador", "email": "catalogador@example.com", "password": "metadataia123",
     "first_name": "Catalina", "last_name": "Catalogadora", "roles": ["CATALOGADOR"]},
    {"username": "revisor", "email": "revisor@example.com", "password": "metadataia123",
     "first_name": "Ramiro", "last_name": "Revisor", "roles": ["REVISOR"]},
]


def run(db: Session) -> None:
    _upsert_ridunt_repository(db)
    _upsert_ridunt_collection(db)
    _upsert_ridunt_vocabularies(db)
    _upsert_ridunt_document_types(db)
    _upsert_ridunt_metadata(db)
    _upsert_ridunt_ai_seed(db)

    # Permisos
    perm_by_code: dict[str, Permission] = {}
    for code, description in PERMISSIONS:
        perm = db.query(Permission).filter_by(code=code).one_or_none()
        if perm is None:
            perm = Permission(code=code, description=description)
            db.add(perm)
        else:
            perm.description = description
        perm_by_code[code] = perm
    db.flush()

    # Roles
    role_by_name: dict[str, Role] = {}
    for name, description in ROLES.items():
        role = db.query(Role).filter_by(name=name).one_or_none()
        if role is None:
            role = Role(name=name, description=description)
            db.add(role)
            db.flush()
        else:
            role.description = description
        role_by_name[name] = role
    db.flush()

    # Asociaciones rol -> permiso (reemplaza el conjunto)
    for role_name, codes in ROLE_PERMISSIONS.items():
        role = role_by_name[role_name]
        desired = {perm_by_code[c].id for c in codes}
        current = {pid for (pid,) in db.query(role_permissions.c.permission_id).filter(
            role_permissions.c.role_id == role.id)}
        for pid in desired - current:
            db.execute(role_permissions.insert().values(role_id=role.id, permission_id=pid))
        for pid in current - desired:
            db.execute(role_permissions.delete().where(
                role_permissions.c.role_id == role.id,
                role_permissions.c.permission_id == pid,
            ))

    # Usuarios
    for data in USERS:
        user = db.query(User).filter_by(username=data["username"]).one_or_none()
        if user is None:
            user = User(
                username=data["username"],
                email=data["email"],
                password_hash=hash_password(data["password"]),
                first_name=data["first_name"],
                last_name=data["last_name"],
            )
            db.add(user)
            db.flush()
        else:
            user.email = data["email"]
            user.first_name = data["first_name"]
            user.last_name = data["last_name"]
            if not user.active:
                user.active = True

        desired = {role_by_name[r].id for r in data["roles"]}
        current = {rid for (rid,) in db.query(user_roles.c.role_id).filter(
            user_roles.c.user_id == user.id)}
        for rid in desired - current:
            db.execute(user_roles.insert().values(user_id=user.id, role_id=rid))

    db.commit()


def main() -> None:
    db = SessionLocal()
    try:
        run(db)
        print("Seed completado: usuarios, roles y permisos configurados.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
