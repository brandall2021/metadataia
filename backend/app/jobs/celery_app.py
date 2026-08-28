from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "metadataia",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.jobs.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    broker_connection_retry_on_startup=True,
)


@celery_app.task(name="app.jobs.ping")
def ping() -> str:
    """Tarea minima para verificar que el worker responde."""
    return "pong"