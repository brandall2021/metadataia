import uuid

from sqlalchemy import JSON, Boolean, String, Uuid, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    base_url: Mapped[str | None] = mapped_column(String(500))
    api_url: Mapped[str | None] = mapped_column(String(500))
    authentication_type: Mapped[str | None] = mapped_column(String(100))
    username: Mapped[str | None] = mapped_column(String(150))
    credential_reference: Mapped[str | None] = mapped_column(String(500))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    configuration_json: Mapped[dict | None] = mapped_column(JSON)

    collections: Mapped[list["RepositoryCollection"]] = relationship(
        back_populates="repository", passive_deletes=True
    )


class RepositoryCollection(Base):
    __tablename__ = "repository_collections"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    external_id: Mapped[str | None] = mapped_column(String(200))
    name: Mapped[str | None] = mapped_column(String(255))
    handle: Mapped[str | None] = mapped_column(String(100))
    document_type_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("document_types.id", ondelete="SET NULL")
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    repository: Mapped[Repository] = relationship(back_populates="collections")
    document_type: Mapped["DocumentType | None"] = relationship(  # noqa: F821
        back_populates="repository_collections"
    )