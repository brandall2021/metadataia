"""Rutas de administracion de repositorios y colecciones (FASE 13).

Ruta: Administracion > Repositorios. Configuracion de DSpace (nombre, URL,
API, autenticacion, usuario, credencial), sincronizacion de comunidades y
colecciones, y asociacion de tipo documental con coleccion.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.audit.service import audit_log, request_context
from app.core.database import get_db
from app.core.dependencies import require_permission
from app.dspace.connector import build_connector
from app.models import DocumentType, Repository, RepositoryCollection, User

router = APIRouter(tags=["repositories"])

can_manage = require_permission("admin.repositories.manage")

MASKED = "********"


class RepositoryCreate(BaseModel):
    name: str
    code: str
    base_url: str | None = None
    api_url: str | None = None
    authentication_type: str | None = None
    username: str | None = None
    credential: str | None = None
    active: bool = True


class RepositoryUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    base_url: str | None = None
    api_url: str | None = None
    authentication_type: str | None = None
    username: str | None = None
    credential: str | None = None
    active: bool | None = None


class RepositoryOut(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    base_url: str | None = None
    api_url: str | None = None
    authentication_type: str | None = None
    username: str | None = None
    credential: str | None = None
    active: bool


class CollectionOut(BaseModel):
    id: uuid.UUID
    repository_id: uuid.UUID
    external_id: str | None = None
    name: str | None = None
    handle: str | None = None
    document_type_id: uuid.UUID | None = None
    document_type_code: str | None = None
    active: bool


class CollectionUpdate(BaseModel):
    document_type_id: uuid.UUID | None = None
    active: bool | None = None


class SyncOut(BaseModel):
    repository_id: uuid.UUID
    communities: int
    collections: int


def _repo_out(repo: Repository) -> RepositoryOut:
    return RepositoryOut(
        id=repo.id,
        name=repo.name,
        code=repo.code,
        base_url=repo.base_url,
        api_url=repo.api_url,
        authentication_type=repo.authentication_type,
        username=repo.username,
        credential=MASKED if (repo.configuration_json or {}).get("credential") else None,
        active=repo.active,
    )


def _public_repo_state(repo: Repository) -> dict:
    """Estado de un repositorio sin exponer la credencial."""
    return {
        "name": repo.name,
        "code": repo.code,
        "base_url": repo.base_url,
        "api_url": repo.api_url,
        "authentication_type": repo.authentication_type,
        "username": repo.username,
        "active": repo.active,
    }


def _collection_out(col: RepositoryCollection) -> CollectionOut:
    doc_type: DocumentType | None = col.document_type
    return CollectionOut(
        id=col.id,
        repository_id=col.repository_id,
        external_id=col.external_id,
        name=col.name,
        handle=col.handle,
        document_type_id=col.document_type_id,
        document_type_code=doc_type.code if doc_type else None,
        active=col.active,
    )


def _get_repo(db: Session, repo_id: uuid.UUID) -> Repository:
    repo = db.get(Repository, repo_id)
    if repo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repositorio no encontrado")
    return repo


def _get_collection(db: Session, repo_id: uuid.UUID, collection_id: uuid.UUID) -> RepositoryCollection:
    col = db.get(RepositoryCollection, collection_id)
    if col is None or col.repository_id != repo_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Coleccion no encontrada")
    return col


@router.get("/admin/repositories", response_model=list[RepositoryOut])
def list_repositories(db: Session = Depends(get_db), _: str = Depends(can_manage)):
    return [_repo_out(r) for r in db.query(Repository).order_by(Repository.name).all()]


@router.post("/admin/repositories", response_model=RepositoryOut, status_code=201)
def create_repository(
    body: RepositoryCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(can_manage),
):
    existing = db.query(Repository).filter(Repository.code == body.code).one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Ya existe un repositorio con ese codigo")
    cfg = {"credential": body.credential} if body.credential else None
    repo = Repository(
        name=body.name,
        code=body.code,
        base_url=body.base_url,
        api_url=body.api_url,
        authentication_type=body.authentication_type,
        username=body.username,
        active=body.active,
        configuration_json=cfg,
    )
    db.add(repo)
    new_value = _public_repo_state(repo)
    new_value["credential"] = MASKED if body.credential else None
    audit_log(
        db,
        user=user,
        action="repository.create",
        entity_type="repository",
        entity_id=str(repo.id),
        new_value=new_value,
        **request_context(request),
    )
    db.commit()
    db.refresh(repo)
    return _repo_out(repo)


@router.get("/admin/repositories/{repository_id}", response_model=RepositoryOut)
def get_repository(repository_id: uuid.UUID, db: Session = Depends(get_db), _: str = Depends(can_manage)):
    return _repo_out(_get_repo(db, repository_id))


@router.put("/admin/repositories/{repository_id}", response_model=RepositoryOut)
def update_repository(
    repository_id: uuid.UUID,
    body: RepositoryUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(can_manage),
):
    repo = _get_repo(db, repository_id)
    old = _public_repo_state(repo)
    if body.code is not None and body.code != repo.code:
        dup = db.query(Repository).filter(Repository.code == body.code).one_or_none()
        if dup is not None:
            raise HTTPException(status_code=409, detail="Ya existe un repositorio con ese codigo")
        repo.code = body.code
    for field in ("name", "base_url", "api_url", "authentication_type", "username"):
        value = getattr(body, field)
        if value is not None:
            setattr(repo, field, value)
    if body.active is not None:
        repo.active = body.active
    if body.credential:
        cfg = dict(repo.configuration_json or {})
        cfg["credential"] = body.credential
        repo.configuration_json = cfg
    new = _public_repo_state(repo)
    if body.credential:
        new["credential"] = MASKED
    diff = {k: {"old": old[k], "new": new[k]} for k in old if old[k] != new[k]}
    if diff:
        audit_log(
            db,
            user=user,
            action="repository.update",
            entity_type="repository",
            entity_id=str(repo.id),
            old_value=diff,
            new_value={"changed": list(diff)},
            **request_context(request),
        )
    db.commit()
    db.refresh(repo)
    return _repo_out(repo)


@router.delete("/admin/repositories/{repository_id}", status_code=204)
def delete_repository(
    repository_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(can_manage),
):
    repo = _get_repo(db, repository_id)
    audit_log(
        db,
        user=user,
        action="repository.delete",
        entity_type="repository",
        entity_id=str(repo.id),
        old_value=_public_repo_state(repo),
        **request_context(request),
    )
    db.delete(repo)
    db.commit()


@router.post("/admin/repositories/{repository_id}/collections/sync", response_model=SyncOut)
def sync_collections(
    repository_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(can_manage),
):
    repo = _get_repo(db, repository_id)
    connector = build_connector(repo)
    token = connector.authenticate()
    communities = connector.get_communities(token)
    seen: set[str] = set()
    for community in communities:
        for col in connector.get_collections(community.get("uuid"), token):
            seen.add(str(col.get("uuid")))
            existing = (
                db.query(RepositoryCollection)
                .filter(
                    RepositoryCollection.repository_id == repo.id,
                    RepositoryCollection.external_id == str(col.get("uuid")),
                )
                .one_or_none()
            )
            if existing is None:
                existing = RepositoryCollection(
                    repository_id=repo.id,
                    external_id=str(col.get("uuid")),
                    name=col.get("name"),
                    handle=col.get("handle"),
                    active=True,
                )
                db.add(existing)
            else:
                existing.name = col.get("name") or existing.name
                existing.handle = col.get("handle") or existing.handle
            existing.active = True
    for col in db.query(RepositoryCollection).filter(RepositoryCollection.repository_id == repo.id).all():
        if col.external_id and col.external_id not in seen and col.document_type_id is None:
            col.active = False
    db.commit()
    total = db.query(RepositoryCollection).filter(RepositoryCollection.repository_id == repo.id).count()
    audit_log(
        db,
        user=user,
        action="repository.sync",
        entity_type="repository",
        entity_id=str(repo.id),
        new_value={"communities": len(communities), "collections": len(seen) or total},
        **request_context(request),
    )
    db.commit()
    return SyncOut(repository_id=repo.id, communities=len(communities), collections=len(seen) or total)


@router.get("/admin/repositories/{repository_id}/collections", response_model=list[CollectionOut])
def list_collections(repository_id: uuid.UUID, db: Session = Depends(get_db), _: str = Depends(can_manage)):
    _get_repo(db, repository_id)
    cols = (
        db.query(RepositoryCollection)
        .filter(RepositoryCollection.repository_id == repository_id)
        .order_by(RepositoryCollection.name)
        .all()
    )
    return [_collection_out(c) for c in cols]


@router.put("/admin/repositories/{repository_id}/collections/{collection_id}", response_model=CollectionOut)
def update_collection(
    repository_id: uuid.UUID,
    collection_id: uuid.UUID,
    body: CollectionUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(can_manage),
):
    col = _get_collection(db, repository_id, collection_id)
    old = {"name": col.name, "handle": col.handle, "document_type_id": str(col.document_type_id) if col.document_type_id else None, "active": col.active}
    if body.document_type_id is not None:
        if db.get(DocumentType, body.document_type_id) is None:
            raise HTTPException(status_code=404, detail="Tipo documental no encontrado")
        col.document_type_id = body.document_type_id
    if body.active is not None:
        col.active = body.active
    new = {"name": col.name, "handle": col.handle, "document_type_id": str(col.document_type_id) if col.document_type_id else None, "active": col.active}
    changed = any(old[k] != new[k] for k in old)
    if changed:
        audit_log(
            db,
            user=user,
action="collection.update",
                entity_type="repository",
                entity_id=str(repository_id),
            old_value=old,
            new_value=new,
            **request_context(request),
        )
    db.commit()
    db.refresh(col)
    return _collection_out(col)


@router.delete("/admin/repositories/{repository_id}/collections/{collection_id}", status_code=204)
def delete_collection(
    repository_id: uuid.UUID,
    collection_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(can_manage),
):
    col = _get_collection(db, repository_id, collection_id)
    audit_log(
        db,
        user=user,
        action="collection.delete",
        entity_type="repository",
        entity_id=str(repo_id),
        old_value={"name": col.name, "handle": col.handle},
        **request_context(request),
    )
    db.delete(col)
    db.commit()