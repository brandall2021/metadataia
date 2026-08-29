"""Servicio de auditoria (FASE 14).

``audit_log`` registra una operacion en ``audit_logs`` (usuario, accion,
entidad, valores anterior/nuevo, IP y user-agent). ``request_context`` extrae
la IP y el user-agent de una peticion FastAPI para las operaciones HTTP; las
tareas asincronas pasan usuario/IP nulos.
"""

from fastapi import Request
from sqlalchemy.orm import Session

from app.models import AuditLog, User


def audit_log(  # noqa: PLR0913 - todos los campos son parte del contrato de auditoria
    db: Session,
    *,
    user: User | None = None,
    action: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
    old_value: dict | None = None,
    new_value: dict | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> AuditLog:
    entry = AuditLog(
        user_id=user.id if user else None,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        old_value_json=old_value,
        new_value_json=new_value,
        ip_address=ip_address,
        user_agent=(user_agent or "")[:500] or None,
    )
    db.add(entry)
    return entry


def request_context(request: Request) -> dict:
    """Extrae ip_address y user_agent de una peticion HTTP."""
    ip = None
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    elif request.client is not None:
        ip = request.client.host
    return {
        "ip_address": ip,
        "user_agent": request.headers.get("user-agent"),
    }