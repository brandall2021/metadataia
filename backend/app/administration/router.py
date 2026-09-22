"""Rutas de administracion general (seccion 40: configuracion global)."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.administration import service
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_permission
from app.models import User

router = APIRouter(prefix="/admin", tags=["administration"])


class SettingUpdate(BaseModel):
    value: Any


@router.get("/settings")
def list_settings(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("admin.settings.manage")),
) -> list[dict]:
    return service.settings_catalog(db)


@router.put("/settings/{key}")
def update_setting(
    key: str,
    payload: SettingUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("admin.settings.manage")),
) -> dict:
    service.set_setting(db, key=key, value=payload.value, user=user)
    db.commit()
    return {"key": key, "value": payload.value, "source": "db"}


@router.delete("/settings/{key}")
def delete_setting(
    key: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("admin.settings.manage")),
) -> dict:
    if not service.clear_setting(db, key=key, user=user):
        raise HTTPException(status_code=404, detail="Setting no encontrado")
    db.commit()
    return {"key": key, "deleted": True}