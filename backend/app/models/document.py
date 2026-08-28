import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    original_filename: Mapped[str | None] = mapped_column(String(500))
    storage_path: Mapped[str | None] = mapped_column(String(1000))
    mime_type: Mapped[str | None] = mapped_column(String(150))
    file_size: Mapped[int | None] = mapped_column(Integer)
    sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    page_count: Mapped[int | None] = mapped_column(Integer)
    document_type_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("document_types.id", ondelete="SET NULL")
    )
    repository_collection_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("repository_collections.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(50), default="UPLOADED", index=True)
    needs_ocr: Mapped[bool] = mapped_column(Boolean, default=False)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    pages: Mapped[list["DocumentPage"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    jobs: Mapped[list["ProcessingJob"]] = relationship(back_populates="document")
    extraction_runs: Mapped[list["ExtractionRun"]] = relationship(back_populates="document")
    metadata_records: Mapped[list["MetadataRecord"]] = relationship(back_populates="document")
    validation_results: Mapped[list["ValidationResult"]] = relationship(back_populates="document")
    depositions: Mapped[list["Deposition"]] = relationship(back_populates="document")
    document_type: Mapped["DocumentType | None"] = relationship()  # noqa: F821


class DocumentPage(Base):
    __tablename__ = "document_pages"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str | None] = mapped_column(Text)
    ocr_used: Mapped[bool] = mapped_column(Boolean, default=False)
    text_length: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict | None] = mapped_column(JSON)

    document: Mapped[Document] = relationship(back_populates="pages")


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    job_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="PENDING")
    progress: Mapped[int | None] = mapped_column(Integer)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    worker_id: Mapped[str | None] = mapped_column(String(200))
    metadata_json: Mapped[dict | None] = mapped_column(JSON)

    document: Mapped[Document] = relationship(back_populates="jobs")


class ExtractionRun(Base):
    __tablename__ = "extraction_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("ai_agents.id", ondelete="SET NULL")
    )
    agent_version_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("ai_agent_versions.id", ondelete="SET NULL")
    )
    model_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("ai_models.id", ondelete="SET NULL")
    )
    prompt_hash: Mapped[str | None] = mapped_column(String(64))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(50), default="PENDING")
    raw_response_storage_path: Mapped[str | None] = mapped_column(String(1000))
    error_message: Mapped[str | None] = mapped_column(Text)

    document: Mapped[Document] = relationship(back_populates="extraction_runs")
    agent_version: Mapped["AIAgentVersion | None"] = relationship(back_populates="extraction_runs")  # noqa: F821
    model: Mapped["AIModel | None"] = relationship(back_populates="extraction_runs")  # noqa: F821
    metadata_records: Mapped[list["MetadataRecord"]] = relationship(back_populates="extraction_run")


class MetadataRecord(Base):
    __tablename__ = "metadata_records"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    metadata_field_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("metadata_fields.id", ondelete="CASCADE"), nullable=False
    )
    value: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(String(10))
    authority_value: Mapped[str | None] = mapped_column(String(500))
    confidence: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str | None] = mapped_column(String(50))
    source_page: Mapped[int | None] = mapped_column(Integer)
    source_text: Mapped[str | None] = mapped_column(Text)
    extraction_run_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("extraction_runs.id", ondelete="SET NULL")
    )
    normalized: Mapped[bool] = mapped_column(Boolean, default=False)
    validated: Mapped[bool] = mapped_column(Boolean, default=False)
    manually_modified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    document: Mapped[Document] = relationship(back_populates="metadata_records")
    metadata_field: Mapped["MetadataField"] = relationship(back_populates="metadata_records")  # noqa: F821
    extraction_run: Mapped[ExtractionRun | None] = relationship(back_populates="metadata_records")


class ValidationResult(Base):
    __tablename__ = "validation_results"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    validator_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="PENDING")
    errors_json: Mapped[dict | None] = mapped_column(JSON)
    warnings_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    document: Mapped[Document] = relationship(back_populates="validation_results")


class Deposition(Base):
    __tablename__ = "depositions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    repository_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("repositories.id", ondelete="SET NULL")
    )
    collection_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("repository_collections.id", ondelete="SET NULL")
    )
    external_item_id: Mapped[str | None] = mapped_column(String(200))
    handle: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(50), default="PENDING")
    request_json: Mapped[dict | None] = mapped_column(JSON)
    response_json: Mapped[dict | None] = mapped_column(JSON)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)

    document: Mapped[Document] = relationship(back_populates="depositions")