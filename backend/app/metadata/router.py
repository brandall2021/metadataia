"""Rutas de administracion de metadatos, vocabularios y tipos documentales (FASE 6).

Criterio: el administrador crea un campo en la API y el frontend lo muestra
dinamicamente en el formulario, sin modificar codigo frontend.
"""

import csv
import io
import unicodedata
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.metadata.schemas import (
    DocumentTypeCreate,
    DocumentTypeFieldLink,
    DocumentTypeFieldsUpdate,
    DocumentTypeFieldOut,
    DocumentTypeOut,
    DocumentTypeUpdate,
    FieldCreate,
    FieldOut,
    FieldUpdate,
    NormalizeRequest,
    NormalizeResult,
    SchemaCreate,
    SchemaOut,
    SchemaUpdate,
    VocabularyCreate,
    VocabularyImportResult,
    VocabularyOut,
    VocabularyUpdate,
    VocabularyValueCreate,
    VocabularyValueOut,
    VocabularyValueUpdate,
)
from app.models import (
    AIAgent,
    DocumentType,
    DocumentTypeMetadataField,
    MetadataField,
    MetadataSchema,
    Vocabulary,
    VocabularyValue,
)

router = APIRouter(tags=["metadatos"])

admin_metadata = require_permission("admin.metadata.manage")
admin_vocabularies = require_permission("admin.vocabularies.manage")
admin_document_types = require_permission("admin.document_types.manage")


def _normalize(value: str) -> str:
    nfkd = unicodedata.normalize("NFKD", value.strip().lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _parse_uuid(raw: str, msg: str) -> uuid.UUID:
    try:
        return uuid.UUID(raw)
    except ValueError:
        raise HTTPException(status_code=422, detail=msg)


def _get_schema(db: Session, schema_id: str) -> MetadataSchema:
    schema = db.get(MetadataSchema, _parse_uuid(schema_id, "Esquema no valido"))
    if schema is None:
        raise HTTPException(status_code=404, detail="Esquema no encontrado")
    return schema


def _get_field(db: Session, field_id: str) -> MetadataField:
    field = db.get(MetadataField, _parse_uuid(field_id, "Campo no valido"))
    if field is None:
        raise HTTPException(status_code=404, detail="Campo no encontrado")
    return field


def _get_vocabulary(db: Session, vocab_id: str) -> Vocabulary:
    vocab = db.get(Vocabulary, _parse_uuid(vocab_id, "Vocabulario no valido"))
    if vocab is None:
        raise HTTPException(status_code=404, detail="Vocabulario no encontrado")
    return vocab


def _get_value(db: Session, value_id: str, vocab: Vocabulary) -> VocabularyValue:
    value = db.get(VocabularyValue, _parse_uuid(value_id, "Valor no valido"))
    if value is None or value.vocabulary_id != vocab.id:
        raise HTTPException(status_code=404, detail="Valor no encontrado")
    return value


def _get_document_type(db: Session, type_id: str) -> DocumentType:
    type_ = db.get(DocumentType, _parse_uuid(type_id, "Tipo documental no valido"))
    if type_ is None:
        raise HTTPException(status_code=404, detail="Tipo documental no encontrado")
    return type_


def _check_duplicate_code(db: Session, model_cls, code: str, exclude_id: uuid.UUID | None = None) -> None:
    q = select(model_cls.id).where(model_cls.code == code)
    if exclude_id is not None:
        q = q.where(model_cls.id != exclude_id)
    if db.execute(q).first() is not None:
        raise HTTPException(status_code=409, detail=f"El codigo '{code}' ya existe")


def _schema_out(schema: MetadataSchema) -> SchemaOut:
    return SchemaOut(
        id=schema.id,
        name=schema.name,
        code=schema.code,
        namespace=schema.namespace,
        description=schema.description,
        active=schema.active,
        version=schema.version,
        field_count=len(schema.fields),
    )


def _field_out(field: MetadataField) -> FieldOut:
    return FieldOut(
        id=field.id,
        schema_id=field.schema_id,
        schema_name=field.schema.name if field.schema else "",
        schema_code=field.schema.code if field.schema else "",
        element=field.element,
        qualifier=field.qualifier,
        display_name=field.display_name,
        description=field.description,
        data_type=field.data_type,
        required=field.required,
        repeatable=field.repeatable,
        editable=field.editable,
        ai_extractable=field.ai_extractable,
        validation_type=field.validation_type,
        normalization_type=field.normalization_type,
        vocabulary_id=field.vocabulary_id,
        vocabulary_code=field.vocabulary.code if field.vocabulary else None,
        order_index=field.order_index,
        active=field.active,
    )


def _vocab_out(vocab: Vocabulary) -> VocabularyOut:
    return VocabularyOut(
        id=vocab.id,
        name=vocab.name,
        code=vocab.code,
        description=vocab.description,
        source=vocab.source,
        active=vocab.active,
        value_count=len(vocab.values),
    )


def _value_out(value: VocabularyValue) -> VocabularyValueOut:
    return VocabularyValueOut(
        id=value.id,
        vocabulary_id=value.vocabulary_id,
        code=value.code,
        label=value.label,
        normalized_value=value.normalized_value,
        synonyms=sorted(value.synonyms_json or []),
        active=value.active,
    )


def _field_in_type(link: DocumentTypeMetadataField) -> DocumentTypeFieldOut:
    f = link.metadata_field
    return DocumentTypeFieldOut(
        id=f.id,
        schema_id=f.schema_id,
        schema_code=f.schema.code if f.schema else "",
        element=f.element,
        qualifier=f.qualifier,
        display_name=f.display_name,
        data_type=f.data_type,
        required=f.required,
        repeatable=f.repeatable,
        ai_extractable=f.ai_extractable,
        vocabulary_id=f.vocabulary_id,
        vocabulary_code=f.vocabulary.code if f.vocabulary else None,
        required_override=link.required_override,
        order_index=link.order_index,
        extraction_instruction=link.extraction_instruction,
    )


def _type_out(type_: DocumentType, with_fields: bool = True) -> DocumentTypeOut:
    agent = type_.default_agent
    return DocumentTypeOut(
        id=type_.id,
        name=type_.name,
        code=type_.code,
        description=type_.description,
        default_agent_id=type_.default_agent_id,
        default_agent_code=agent.code if agent else None,
        default_agent_name=agent.name if agent else None,
        active=type_.active,
        created_at=type_.created_at,
        updated_at=type_.updated_at,
        fields=[_field_in_type(l) for l in sorted(type_.metadata_field_links, key=lambda l: (l.order_index or 0, l.metadata_field.display_name or ""))] if with_fields else [],
    )


# --- esquemas ---------------------------------------------------------------


@router.get("/admin/metadata/schemas", response_model=list[SchemaOut])
def list_schemas(db: Session = Depends(get_db), _: None = Depends(admin_metadata)):
    return [_schema_out(s) for s in db.query(MetadataSchema).order_by(MetadataSchema.name)]


@router.post("/admin/metadata/schemas", response_model=SchemaOut, status_code=201)
def create_schema(
    payload: SchemaCreate,
    db: Session = Depends(get_db),
    _: None = Depends(admin_metadata),
):
    _check_duplicate_code(db, MetadataSchema, payload.code)
    schema = MetadataSchema(**payload.model_dump())
    db.add(schema)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"El codigo '{payload.code}' ya existe")
    db.refresh(schema)
    return _schema_out(schema)


@router.put("/admin/metadata/schemas/{schema_id}", response_model=SchemaOut)
def update_schema(
    schema_id: str,
    payload: SchemaUpdate,
    db: Session = Depends(get_db),
    _: None = Depends(admin_metadata),
):
    schema = _get_schema(db, schema_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(schema, key, value)
    db.commit()
    db.refresh(schema)
    return _schema_out(schema)


@router.delete("/admin/metadata/schemas/{schema_id}", status_code=204)
def delete_schema(schema_id: str, db: Session = Depends(get_db), _: None = Depends(admin_metadata)):
    schema = _get_schema(db, schema_id)
    db.delete(schema)
    db.commit()


# --- campos -----------------------------------------------------------------


@router.get("/admin/metadata/fields", response_model=list[FieldOut])
def list_fields(
    schema_id: str | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(admin_metadata),
):
    query = db.query(MetadataField)
    if schema_id:
        query = query.filter(
            MetadataField.schema_id == _parse_uuid(schema_id, "Esquema no valido")
        )
    return [
        _field_out(f)
        for f in query.order_by(MetadataSchema.name, MetadataField.order_index, MetadataField.element).join(
            MetadataSchema, MetadataField.schema_id == MetadataSchema.id
        )
    ]


@router.post("/admin/metadata/fields", response_model=FieldOut, status_code=201)
def create_field(
    payload: FieldCreate,
    db: Session = Depends(get_db),
    _: None = Depends(admin_metadata),
):
    _get_schema(db, str(payload.schema_id))
    if payload.vocabulary_id:
        _get_vocabulary(db, str(payload.vocabulary_id))
    field = MetadataField(**payload.model_dump())
    db.add(field)
    db.commit()
    db.refresh(field)
    return _field_out(field)


@router.put("/admin/metadata/fields/{field_id}", response_model=FieldOut)
def update_field(
    field_id: str,
    payload: FieldUpdate,
    db: Session = Depends(get_db),
    _: None = Depends(admin_metadata),
):
    field = _get_field(db, field_id)
    data = payload.model_dump(exclude_unset=True)
    if data.get("vocabulary_id") is not None:
        _get_vocabulary(db, str(data["vocabulary_id"]))
    for key, value in data.items():
        setattr(field, key, value)
    db.commit()
    db.refresh(field)
    return _field_out(field)


@router.delete("/admin/metadata/fields/{field_id}", status_code=204)
def delete_field(field_id: str, db: Session = Depends(get_db), _: None = Depends(admin_metadata)):
    field = _get_field(db, field_id)
    db.delete(field)
    db.commit()


# --- vocabularios -----------------------------------------------------------


@router.get("/admin/vocabularies", response_model=list[VocabularyOut])
def list_vocabularies(db: Session = Depends(get_db), _: None = Depends(admin_vocabularies)):
    return [_vocab_out(v) for v in db.query(Vocabulary).order_by(Vocabulary.name)]


@router.post("/admin/vocabularies", response_model=VocabularyOut, status_code=201)
def create_vocabulary(
    payload: VocabularyCreate,
    db: Session = Depends(get_db),
    _: None = Depends(admin_vocabularies),
):
    _check_duplicate_code(db, Vocabulary, payload.code)
    vocab = Vocabulary(**payload.model_dump())
    db.add(vocab)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"El codigo '{payload.code}' ya existe")
    db.refresh(vocab)
    return _vocab_out(vocab)


@router.put("/admin/vocabularies/{vocab_id}", response_model=VocabularyOut)
def update_vocabulary(
    vocab_id: str,
    payload: VocabularyUpdate,
    db: Session = Depends(get_db),
    _: None = Depends(admin_vocabularies),
):
    vocab = _get_vocabulary(db, vocab_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(vocab, key, value)
    db.commit()
    db.refresh(vocab)
    return _vocab_out(vocab)


@router.delete("/admin/vocabularies/{vocab_id}", status_code=204)
def delete_vocabulary(vocab_id: str, db: Session = Depends(get_db), _: None = Depends(admin_vocabularies)):
    vocab = _get_vocabulary(db, vocab_id)
    db.delete(vocab)
    db.commit()


@router.get("/admin/vocabularies/{vocab_id}/values", response_model=list[VocabularyValueOut])
def list_values(vocab_id: str, db: Session = Depends(get_db), _: None = Depends(admin_vocabularies)):
    vocab = _get_vocabulary(db, vocab_id)
    values = (
        db.query(VocabularyValue)
        .filter(VocabularyValue.vocabulary_id == vocab.id)
        .order_by(VocabularyValue.code)
    )
    db.expire_all()
    values = values.all()
    return [_value_out(v) for v in values]


@router.post("/admin/vocabularies/{vocab_id}/values", response_model=VocabularyValueOut, status_code=201)
def create_value(
    vocab_id: str,
    payload: VocabularyValueCreate,
    db: Session = Depends(get_db),
    _: None = Depends(admin_vocabularies),
):
    vocab = _get_vocabulary(db, vocab_id)
    exists = (
        db.query(VocabularyValue.id)
        .filter(VocabularyValue.vocabulary_id == vocab.id, VocabularyValue.code == payload.code)
        .first()
    )
    if exists:
        raise HTTPException(status_code=409, detail=f"El codigo '{payload.code}' ya existe en el vocabulario")
    normalized = payload.normalized_value or _normalize(payload.label)
    synonyms = sorted({s.strip() for s in payload.synonyms if s.strip()})
    value = VocabularyValue(
        vocabulary_id=vocab.id,
        code=payload.code,
        label=payload.label,
        normalized_value=normalized,
        synonyms_json=synonyms,
        active=payload.active,
    )
    db.add(value)
    db.commit()
    db.refresh(value)
    return _value_out(value)


@router.put("/admin/vocabularies/{vocab_id}/values/{value_id}", response_model=VocabularyValueOut)
def update_value(
    vocab_id: str,
    value_id: str,
    payload: VocabularyValueUpdate,
    db: Session = Depends(get_db),
    _: None = Depends(admin_vocabularies),
):
    vocab = _get_vocabulary(db, vocab_id)
    value = _get_value(db, value_id, vocab)
    data = payload.model_dump(exclude_unset=True)
    if data.get("label") is not None and "normalized_value" not in data:
        data["normalized_value"] = _normalize(data["label"])
    if data.get("synonyms") is not None:
        data["synonyms_json"] = sorted({s.strip() for s in data["synonyms"] if s.strip()})
        data.pop("synonyms", None)
    for key, val in data.items():
        setattr(value, key, val)
    db.commit()
    db.refresh(value)
    return _value_out(value)


@router.delete("/admin/vocabularies/{vocab_id}/values/{value_id}", status_code=204)
def delete_value(vocab_id: str, value_id: str, db: Session = Depends(get_db), _: None = Depends(admin_vocabularies)):
    vocab = _get_vocabulary(db, vocab_id)
    value = _get_value(db, value_id, vocab)
    db.delete(value)
    db.commit()


@router.post("/admin/vocabularies/{vocab_id}/import", response_model=VocabularyImportResult)
def import_vocabulary_csv(
    vocab_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: None = Depends(admin_vocabularies),
):
    vocab = _get_vocabulary(db, vocab_id)
    raw = io.StringIO(file.file.read().decode("utf-8-sig"), newline="")
    reader = csv.reader(raw)
    added = 0
    updated = 0
    for row in reader:
        row = [c.strip() for c in row]
        if not row or not row[0] or row[0].startswith("#") or row[0].lower() == "code":
            continue
        code = row[0]
        label = row[1] if len(row) > 1 and row[1] else code
        synonyms = row[2].split("|") if len(row) > 2 and row[2] else []
        existing = (
            db.query(VocabularyValue)
            .filter(VocabularyValue.vocabulary_id == vocab.id, VocabularyValue.code == code)
            .first()
        )
        if existing:
            existing.label = label
            existing.normalized_value = _normalize(label)
            if synonyms:
                existing.synonyms_json = sorted({s.strip() for s in synonyms})
            updated += 1
        else:
            db.add(
                VocabularyValue(
                    vocabulary_id=vocab.id,
                    code=code,
                    label=label,
                    normalized_value=_normalize(label),
                    synonyms_json=sorted({s.strip() for s in synonyms}),
                )
            )
            added += 1
    db.commit()
    return VocabularyImportResult(added=added, updated=updated, total=added + updated)


@router.post("/admin/vocabularies/{vocab_id}/normalize", response_model=NormalizeResult)
def normalize_value(
    vocab_id: str,
    payload: NormalizeRequest,
    db: Session = Depends(get_db),
    _: None = Depends(admin_vocabularies),
):
    vocab = _get_vocabulary(db, vocab_id)
    normalized = _normalize(payload.value)
    values = (
        db.query(VocabularyValue)
        .filter(VocabularyValue.vocabulary_id == vocab.id, VocabularyValue.active.is_(True))
        .all()
    )
    for value in values:
        candidates = {_normalize(value.code), _normalize(value.label)}
        if value.normalized_value:
            candidates.add(_normalize(value.normalized_value))
        candidates.update(_normalize(s) for s in (value.synonyms_json or []))
        if normalized in candidates:
            return NormalizeResult(found=True, code=value.code, label=value.label, normalized_value=value.normalized_value)
    return NormalizeResult(found=False, normalized_value=normalized)


# --- tipos documentales ------------------------------------------------------


@router.get("/admin/document-types", response_model=list[DocumentTypeOut])
def list_document_types(db: Session = Depends(get_db), _: None = Depends(admin_document_types)):
    return [_type_out(t, with_fields=False) for t in db.query(DocumentType).order_by(DocumentType.name)]


@router.get("/admin/document-types/{type_id}", response_model=DocumentTypeOut)
def get_document_type(type_id: str, db: Session = Depends(get_db), _: None = Depends(admin_document_types)):
    return _type_out(_get_document_type(db, type_id), with_fields=True)


@router.post("/admin/document-types", response_model=DocumentTypeOut, status_code=201)
def create_document_type(
    payload: DocumentTypeCreate,
    db: Session = Depends(get_db),
    _: None = Depends(admin_document_types),
):
    _check_duplicate_code(db, DocumentType, payload.code)
    if payload.default_agent_id:
        if db.get(AIAgent, payload.default_agent_id) is None:
            raise HTTPException(status_code=404, detail="Agente no encontrado")
    type_ = DocumentType(**payload.model_dump())
    db.add(type_)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"El codigo '{payload.code}' ya existe")
    db.refresh(type_)
    return _type_out(type_, with_fields=False)


@router.put("/admin/document-types/{type_id}", response_model=DocumentTypeOut)
def update_document_type(
    type_id: str,
    payload: DocumentTypeUpdate,
    db: Session = Depends(get_db),
    _: None = Depends(admin_document_types),
):
    type_ = _get_document_type(db, type_id)
    data = payload.model_dump(exclude_unset=True)
    if data.get("default_agent_id") is not None and db.get(AIAgent, data["default_agent_id"]) is None:
        raise HTTPException(status_code=404, detail="Agente no encontrado")
    for key, value in data.items():
        setattr(type_, key, value)
    db.commit()
    db.refresh(type_)
    return _type_out(type_, with_fields=True)


@router.delete("/admin/document-types/{type_id}", status_code=204)
def delete_document_type(type_id: str, db: Session = Depends(get_db), _: None = Depends(admin_document_types)):
    type_ = _get_document_type(db, type_id)
    db.delete(type_)
    db.commit()


@router.put("/admin/document-types/{type_id}/fields", response_model=DocumentTypeOut)
def set_document_type_fields(
    type_id: str,
    payload: DocumentTypeFieldsUpdate,
    db: Session = Depends(get_db),
    _: None = Depends(admin_document_types),
):
    type_ = _get_document_type(db, type_id)
    field_ids = [l.field_id for l in payload.fields]
    if len(set(field_ids)) != len(field_ids):
        raise HTTPException(status_code=422, detail="Campos duplicados en la asociacion")
    fields = db.query(MetadataField).filter(MetadataField.id.in_(field_ids)).all()
    if len(fields) != len(set(field_ids)):
        raise HTTPException(status_code=404, detail="Algun campo no existe")
    db.query(DocumentTypeMetadataField).filter(
        DocumentTypeMetadataField.document_type_id == type_.id
    ).delete(synchronize_session=False)
    for i, link in enumerate(payload.fields):
        db.add(
            DocumentTypeMetadataField(
                document_type_id=type_.id,
                metadata_field_id=link.field_id,
                required_override=link.required_override,
                order_index=link.order_index if link.order_index is not None else i,
            )
        )
    db.commit()
    db.refresh(type_)
    return _type_out(type_, with_fields=True)