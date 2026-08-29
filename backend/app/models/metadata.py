import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class MetadataSchema(Base):
    __tablename__ = "metadata_schemas"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    namespace: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1)

    fields: Mapped[list["MetadataField"]] = relationship(
        back_populates="schema", cascade="all, delete-orphan", passive_deletes=True
    )


class MetadataField(Base):
    __tablename__ = "metadata_fields"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    schema_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("metadata_schemas.id", ondelete="CASCADE"), nullable=False
    )
    element: Mapped[str] = mapped_column(String(100), nullable=False)
    qualifier: Mapped[str | None] = mapped_column(String(100))
    display_name: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    data_type: Mapped[str] = mapped_column(String(50), default="text")
    required: Mapped[bool] = mapped_column(Boolean, default=False)
    repeatable: Mapped[bool] = mapped_column(Boolean, default=False)
    editable: Mapped[bool] = mapped_column(Boolean, default=True)
    ai_extractable: Mapped[bool] = mapped_column(Boolean, default=True)
    validation_type: Mapped[str | None] = mapped_column(String(100))
    normalization_type: Mapped[str | None] = mapped_column(String(100))
    vocabulary_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("vocabularies.id", ondelete="SET NULL")
    )
    order_index: Mapped[int | None] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    schema: Mapped[MetadataSchema] = relationship(back_populates="fields")
    vocabulary: Mapped["Vocabulary | None"] = relationship(back_populates="fields")
    document_type_links: Mapped[list["DocumentTypeMetadataField"]] = relationship(
        back_populates="metadata_field", cascade="all, delete-orphan", passive_deletes=True
    )
    metadata_records: Mapped[list["MetadataRecord"]] = relationship(back_populates="metadata_field")


class DocumentType(Base):
    __tablename__ = "document_types"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    default_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey(
            "ai_agents.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_document_types_default_agent",
        ),
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    metadata_field_links: Mapped[list["DocumentTypeMetadataField"]] = relationship(
        back_populates="document_type", cascade="all, delete-orphan", passive_deletes=True
    )
    default_agent: Mapped["AIAgent | None"] = relationship(
        foreign_keys=[default_agent_id]
    )
    repository_collections: Mapped[list["RepositoryCollection"]] = relationship(
        back_populates="document_type"
    )


class DocumentTypeMetadataField(Base):
    __tablename__ = "document_type_metadata_fields"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    document_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("document_types.id", ondelete="CASCADE"), nullable=False
    )
    metadata_field_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("metadata_fields.id", ondelete="CASCADE"), nullable=False
    )
    required_override: Mapped[bool | None] = mapped_column(Boolean)
    order_index: Mapped[int | None] = mapped_column(Integer)
    extraction_instruction: Mapped[str | None] = mapped_column(Text)

    document_type: Mapped[DocumentType] = relationship(back_populates="metadata_field_links")
    metadata_field: Mapped[MetadataField] = relationship(back_populates="document_type_links")


class Vocabulary(Base):
    __tablename__ = "vocabularies"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(String(200))
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    values: Mapped[list["VocabularyValue"]] = relationship(
        back_populates="vocabulary", cascade="all, delete-orphan", passive_deletes=True
    )
    fields: Mapped[list[MetadataField]] = relationship(back_populates="vocabulary")


class VocabularyValue(Base):
    __tablename__ = "vocabulary_values"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    vocabulary_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("vocabularies.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_value: Mapped[str | None] = mapped_column(String(255))
    synonyms_json: Mapped[dict | None] = mapped_column(JSON)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    vocabulary: Mapped[Vocabulary] = relationship(back_populates="values")