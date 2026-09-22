import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AppSetting(Base):
    """Configuracion global administrable (seccion 40 de la especificacion).

    Los valores guardados en DB tienen prioridad sobre los defaults de
    ``core/config.py`` (env). ``value_json`` conserva el tipo (int/bool/str/list).
    """

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(150), primary_key=True)
    value_json: Mapped[dict | None] = mapped_column(JSON)
    description: Mapped[str | None] = mapped_column(Text)
    section: Mapped[str | None] = mapped_column(String(100))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )