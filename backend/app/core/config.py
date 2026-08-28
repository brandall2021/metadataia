from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuracion global de la aplicacion, cargada desde variables de entorno / .env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Entorno -----------------------------------------------------------
    app_name: str = "METADATAIA"
    app_env: str = "development"
    app_secret_key: str = "cambiar-en-produccion"

    # --- Base de datos ------------------------------------------------------
    database_url: str = Field(
        default="postgresql+psycopg://metadataia:metadataia@postgres:5432/metadataia"
    )

    # --- Redis / Celery ------------------------------------------------------
    redis_url: str = "redis://redis:6379/0"

    # --- JWT -----------------------------------------------------------------
    jwt_secret: str = "cambiar-en-produccion"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 30

    # --- MinIO (S3) -----------------------------------------------------------
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "metadataia"
    minio_secret_key: str = "metadataia-secret"
    minio_bucket: str = "metadataia"
    storage_backend: str = "s3"  # s3 | filesystem

    # --- Reglas generales (FASE 40) -------------------------------------------
    default_max_file_size_mb: int = 100
    ocr_languages: str = "spa+eng+por"
    ai_timeout_seconds: int = 120
    dspace_timeout_seconds: int = 120
    auto_ocr: bool = True
    auto_ai: bool = True

    # --- CORS ------------------------------------------------------------------
    cors_origins: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()