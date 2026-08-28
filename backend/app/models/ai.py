import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AIProvider(Base):
    __tablename__ = "ai_providers"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    base_url: Mapped[str | None] = mapped_column(String(500))
    api_key_encrypted: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    configuration_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    models: Mapped[list["AIModel"]] = relationship(back_populates="provider")


class AIModel(Base):
    __tablename__ = "ai_models"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    provider_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("ai_providers.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    model_identifier: Mapped[str] = mapped_column(String(200), nullable=False)
    context_window: Mapped[int | None] = mapped_column(Integer)
    supports_json: Mapped[bool] = mapped_column(Boolean, default=False)
    supports_vision: Mapped[bool] = mapped_column(Boolean, default=False)
    temperature_default: Mapped[float | None] = mapped_column(Float)
    max_tokens_default: Mapped[int | None] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    configuration_json: Mapped[dict | None] = mapped_column(JSON)

    provider: Mapped[AIProvider] = relationship(back_populates="models")
    agent_versions: Mapped[list["AIAgentVersion"]] = relationship(back_populates="model")
    extraction_runs: Mapped[list["ExtractionRun"]] = relationship(back_populates="model")


class AIAgent(Base):
    __tablename__ = "ai_agents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    document_type_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("document_types.id", ondelete="SET NULL")
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("ai_agent_versions.id", use_alter=True, name="fk_ai_agents_current_version"),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    versions: Mapped[list["AIAgentVersion"]] = relationship(
        back_populates="agent",
        foreign_keys="AIAgentVersion.agent_id",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    current_version: Mapped["AIAgentVersion | None"] = relationship(
        foreign_keys=[current_version_id], post_update=True
    )


class AIAgentVersion(Base):
    __tablename__ = "ai_agent_versions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("ai_agents.id", ondelete="CASCADE"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    model_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("ai_models.id", ondelete="RESTRICT"), nullable=False
    )
    system_prompt: Mapped[str | None] = mapped_column(Text)
    extraction_prompt: Mapped[str | None] = mapped_column(Text)
    temperature: Mapped[float | None] = mapped_column(Float)
    max_tokens: Mapped[int | None] = mapped_column(Integer)
    output_schema_json: Mapped[dict | None] = mapped_column(JSON)
    configuration_json: Mapped[dict | None] = mapped_column(JSON)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    agent: Mapped[AIAgent] = relationship(
        back_populates="versions", foreign_keys=[agent_id]
    )
    model: Mapped[AIModel] = relationship(back_populates="agent_versions")
    extraction_runs: Mapped[list["ExtractionRun"]] = relationship(back_populates="agent_version")