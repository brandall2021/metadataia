from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth.router import router as auth_router
from app.ai.router import router as ai_admin_router
from app.metadata.router import router as metadata_router
from app.pdf.router import router as documents_router
from app.extraction.router import router as extraction_router
from app.normalization.router import router as normalization_router
from app.core import storage
from app.core.config import settings
from app.core.database import get_db
from app.users.router import router as users_router


def create_app() -> FastAPI:
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

    app.include_router(auth_router, prefix="/api")
    app.include_router(users_router, prefix="/api")
    app.include_router(ai_admin_router, prefix="/api")
    app.include_router(metadata_router, prefix="/api")
    app.include_router(documents_router, prefix="/api")
    app.include_router(extraction_router, prefix="/api")
    app.include_router(normalization_router, prefix="/api")

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