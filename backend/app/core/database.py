from collections.abc import Generator
import sys

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings


class Base(DeclarativeBase):
    """Base declarativa para todos los modelos ORM."""


def _is_test_runtime() -> bool:
    return settings.app_env == "test" or "pytest" in sys.modules


def _create_engine():
    if _is_test_runtime():
        test_engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        event.listen(test_engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
        return test_engine
    return create_engine(settings.database_url, pool_pre_ping=True)


engine = _create_engine()

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _bootstrap_test_database() -> None:
    if not _is_test_runtime():
        return
    from app import models  # noqa: F401
    from app.seed import run

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        run(db)
    finally:
        db.close()


_bootstrap_test_database()


def get_db() -> Generator[Session, None, None]:
    """Dependencia FastAPI: provee una sesion de base de datos por request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
