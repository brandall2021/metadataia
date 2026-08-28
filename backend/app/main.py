from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db


def create_app() -> FastAPI:
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