from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth.router import router as auth_router
from app.ai.router import router as ai_admin_router
from app.metadata.router import router as metadata_router
from app.pdf.router import router as documents_router
from app.extraction.router import router as extraction_router
from app.normalization.router import router as normalization_router
from app.validation.router import router as validation_router
from app.review.router import router as review_router
from app.repositories.router import router as repositories_router
from app.deposit.router import router as deposit_router
from app.audit.router import router as audit_router, history_router as audit_history_router
from app.dashboard.router import router as dashboard_router
from app.core import storage
from app.core.config import settings
from app.core.database import get_db
from app.users.router import router as users_router

# Defaults de desarrollo: en produccion el arranque debe fallar si se conservan.
DEV_DEFAULTS = {
    "jwt_secret": "clave-jwt-desarrollo-metadataia-32-caracteres-minimo",
    "app_secret_key": "clave-desarrollo-metadataia-32-caracteres-minimo",
}

_DEV_CORS = {"", "*", "http://localhost:3000", "http://127.0.0.1:3000"}


def _ensure_production_guard() -> None:
    """FASE 17: en APP_ENV=production no se admiten secretos ni CORS de desarrollo."""
    if settings.app_env != "production":
        return
    if settings.jwt_secret in DEV_DEFAULTS.values() or settings.app_secret_key in DEV_DEFAULTS.values():
        raise RuntimeError(
            "APP_ENV=production requiere JWT_SECRET y APP_SECRET_KEY propios (no los defaults de desarrollo)"
        )
    if settings.cors_origins in _DEV_CORS:
        raise RuntimeError(
            "APP_ENV=production requiere cors_origins restringido (no se admite el default de desarrollo)"
        )


def create_app() -> FastAPI:
    _ensure_production_guard()
    storage.ensure_bucket()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Sistema de extraccion, normalizacion, validacion y deposito de metadatos "
        "desde documentos PDF mediante OCR + Agentes de IA + SNRD + DSpace 9",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["X-XSS-Protection"] = "0"
        return response

    app.include_router(auth_router, prefix="/api")
    app.include_router(users_router, prefix="/api")
    app.include_router(ai_admin_router, prefix="/api")
    app.include_router(metadata_router, prefix="/api")
    app.include_router(documents_router, prefix="/api")
    app.include_router(extraction_router, prefix="/api")
    app.include_router(normalization_router, prefix="/api")
    app.include_router(validation_router, prefix="/api")
    app.include_router(review_router, prefix="/api")
    app.include_router(repositories_router, prefix="/api")
    app.include_router(deposit_router, prefix="/api")
    app.include_router(audit_router, prefix="/api")
    app.include_router(audit_history_router, prefix="/api")
    app.include_router(dashboard_router, prefix="/api")

    @app.get("/health", tags=["core"])
    def health(db: Session = Depends(get_db)) -> dict:
        db_ok = True
        try:
            db.execute(text("SELECT 1"))
        except Exception:
            db_ok = False
        return {
            "status": "ok" if db_ok else "degraded",
            "app": settings.app_name,
            "env": settings.app_env,
            "database": "ok" if db_ok else "error",
        }

    return app


app = create_app()