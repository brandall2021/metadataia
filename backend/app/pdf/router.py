"""Motor de PDF (FASE 7): upload, SHA256, analisis y almacenamiento.

Criterio: el PDF queda almacenado (MinIO/filesystem) y analizado
(validacion, paginas, existencia de texto, necesidad de OCR).
El archivo original nunca se modifica.
"""

import io
import re
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.audit.service import audit_log, request_context
from app.core import storage
from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import require_permission
from app.core.errors import AppError, LOCKED_STATE
from app.core.storage import StorageError
from app.jobs.celery_app import celery_app
from app.models import Document, DocumentPage, DocumentType, ProcessingJob, RepositoryCollection, User
from app.pdf import analyzer
from app.pdf.schemas import DocumentDetailOut, DocumentOut, DocumentPageOut
from app.workflows import EDIT_LOCKED_STATES

router = APIRouter(prefix="/documents", tags=["documents"])

can_upload = require_permission("document.upload")
can_view = require_permission("document.view")

_UNSAFE_FILENAME_CHARS = re.compile(r'[\r\n"\x00-\x1f\x7f\\]')


def _safe_filename(filename: str) -> str:
    """Sanea el nombre para usarlo en Content-Disposition (FASE 17)."""
    cleaned = _UNSAFE_FILENAME_CHARS.sub("", filename or "").strip()
    return cleaned or "documento.pdf"


def _page_out(page: DocumentPage) -> DocumentPageOut:
    return DocumentPageOut(
        id=page.id,
        page_number=page.page_number,
        text=page.text,
        text_length=page.text_length,
        ocr_used=page.ocr_used,
    )


def _doc_out(doc: Document) -> DocumentOut:
    return DocumentOut(
        id=doc.id,
        original_filename=doc.original_filename,
        mime_type=doc.mime_type,
        file_size=doc.file_size,
        sha256=doc.sha256,
        page_count=doc.page_count,
        needs_ocr=doc.needs_ocr,
        status=doc.status,
        created_at=doc.created_at,
    )


def _extraction_run_out(run) -> dict:
    agent_version = run.agent_version
    agent_name = agent_version.agent.name if agent_version is not None else None
    return {
        "id": str(run.id),
        "agent_id": str(run.agent_id) if run.agent_id else None,
        "agent_name": agent_name,
        "agent_version_id": str(run.agent_version_id) if run.agent_version_id else None,
        "version_number": agent_version.version_number if agent_version is not None else None,
        "model_id": str(run.model_id) if run.model_id else None,
        "model_name": run.model.name if run.model is not None else None,
        "prompt_hash": run.prompt_hash,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "duration_seconds": (
            (run.finished_at - run.started_at).total_seconds()
            if run.finished_at and run.started_at
            else None
        ),
        "input_tokens": run.input_tokens,
        "output_tokens": run.output_tokens,
        "status": run.status,
        "error_message": run.error_message,
    }


def _doc_detail_out(doc: Document) -> DocumentDetailOut:
    total_text = sum(len(p.text or "") for p in doc.pages)
    jobs = [
        {
            "id": str(j.id),
            "job_type": j.job_type,
            "status": j.status,
            "progress": j.progress,
            "started_at": j.started_at,
            "finished_at": j.finished_at,
            "error_message": j.error_message,
            "metadata_json": j.metadata_json or {},
        }
        for j in sorted(doc.jobs, key=lambda j: (j.created_at or j.started_at) or j.id, reverse=False)
    ]
    extraction_runs = [
        _extraction_run_out(run)
        for run in sorted(doc.extraction_runs, key=lambda r: r.started_at or r.id)
    ]
    return DocumentDetailOut(
        **_doc_out(doc).model_dump(),
        document_type_id=doc.document_type_id,
        pages=[_page_out(p) for p in sorted(doc.pages, key=lambda p: p.page_number)],
        analysis={
            "total_text_length": total_text,
            "needs_ocr": doc.needs_ocr,
            "status": doc.status,
        },
        jobs=jobs,
        extraction_runs=extraction_runs,
    )


def _get_doc(db: Session, document_id: str) -> Document:
    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Documento no valido")
    doc = db.get(Document, doc_uuid)
    if doc is None:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    return doc


class DocumentUpdate(BaseModel):
    original_filename: str | None = None
    document_type_id: uuid.UUID | None = None
    repository_collection_id: uuid.UUID | None = None


def _enqueue_ocr(db: Session, doc: Document) -> ProcessingJob:
    job = ProcessingJob(document_id=doc.id, job_type="OCR", status="PENDING")
    db.add(job)
    db.commit()
    db.refresh(job)
    celery_app.send_task("app.jobs.tasks.run_ocr", args=[str(doc.id)])
    return job


@router.post("", response_model=DocumentDetailOut, status_code=201)
def upload_document(
    request: Request,
    file: UploadFile = File(...),
    document_type_id: str | None = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(can_upload),
):
    filename = _safe_filename(file.filename or "")

    if not analyzer.is_valid_extension(filename):
        raise HTTPException(status_code=422, detail="Solo se aceptan archivos PDF (.pdf)")
    content_type = file.content_type or "application/octet-stream"
    if not analyzer.is_valid_pdf_mime(content_type) and content_type != "application/octet-stream":
        raise HTTPException(status_code=422, detail="El MIME del archivo debe ser application/pdf")

    max_bytes = analyzer.max_upload_bytes()
    data = file.file.read(max_bytes + 1)
    if not data:
        raise HTTPException(status_code=422, detail="El archivo esta vacio")
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=413, detail=f"Excede el tamano maximo de {settings.default_max_file_size_mb} MB"
        )

    try:
        analysis = analyzer.analyze_pdf(data)
    except analyzer.InvalidPDFError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    sha256 = analyzer.sha256_of(data)

    existing = db.query(Document).filter(Document.sha256 == sha256).first()
    if existing:
        raise HTTPException(status_code=409, detail="El documento ya fue cargado anteriormente")

    if document_type_id:
        try:
            doc_type_uuid = uuid.UUID(document_type_id)
        except ValueError:
            raise HTTPException(status_code=422, detail="Tipo documental no valido")
        if db.get(DocumentType, doc_type_uuid) is None:
            raise HTTPException(status_code=404, detail="Tipo documental no encontrado")

    try:
        storage_key = storage.upload_original(sha256, data, content_type)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail="No se pudo almacenar el archivo") from exc

    doc = Document(
        original_filename=filename,
        storage_path=storage_key,
        mime_type=content_type,
        file_size=len(data),
        sha256=sha256,
        page_count=analysis["page_count"],
        needs_ocr=analysis["needs_ocr"],
        status="UPLOADED",
        uploaded_by=user.id,
    )
    if document_type_id:
        doc.document_type_id = uuid.UUID(document_type_id)
    db.add(doc)
    db.flush()
    for i, text in enumerate(analysis["pages_text"], start=1):
        db.add(
            DocumentPage(
                document_id=doc.id,
                page_number=i,
                text=text,
                text_length=len(text),
                ocr_used=False,
            )
        )
    db.commit()
    db.refresh(doc)
    audit_log(
        db,
        user=user,
        action="document.upload",
        entity_type="document",
        entity_id=str(doc.id),
        new_value={
            "filename": filename,
            "sha256": sha256,
            "file_size": len(data),
            "needs_ocr": doc.needs_ocr,
            "document_type_id": str(doc.document_type_id) if doc.document_type_id else None,
        },
        **request_context(request),
    )
    db.commit()
    if doc.needs_ocr and settings.auto_ocr:
        _enqueue_ocr(db, doc)
    elif settings.auto_ai and not doc.needs_ocr:
        from app.extraction.router import _enqueue_extraction

        _enqueue_extraction(db, doc)
    return _doc_detail_out(doc)


@router.get("", response_model=list[DocumentOut])
def list_documents(db: Session = Depends(get_db), _: User = Depends(can_view)):
    docs = db.query(Document).order_by(Document.created_at.desc()).all()
    return [_doc_out(d) for d in docs]


@router.get("/{document_id}", response_model=DocumentDetailOut)
def get_document(document_id: str, db: Session = Depends(get_db), _: User = Depends(can_view)):
    doc = _get_doc(db, document_id)
    return _doc_detail_out(doc)


@router.put("/{document_id}", response_model=DocumentOut)
def update_document(
    document_id: str,
    body: DocumentUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(can_upload),
):
    doc = _get_doc(db, document_id)
    if doc.status in EDIT_LOCKED_STATES:
        raise AppError(
            LOCKED_STATE,
            f"No se puede modificar un documento en estado {doc.status}",
            status_code=409,
        )
    old = {
        "original_filename": doc.original_filename,
        "document_type_id": str(doc.document_type_id) if doc.document_type_id else None,
        "repository_collection_id": str(doc.repository_collection_id) if doc.repository_collection_id else None,
    }
    if body.original_filename is not None:
        doc.original_filename = _safe_filename(body.original_filename)
    if body.document_type_id is not None:
        if db.get(DocumentType, body.document_type_id) is None:
            raise HTTPException(status_code=404, detail="Tipo documental no encontrado")
        doc.document_type_id = body.document_type_id
    if body.repository_collection_id is not None:
        if db.get(RepositoryCollection, body.repository_collection_id) is None:
            raise HTTPException(status_code=404, detail="Coleccion no encontrada")
        doc.repository_collection_id = body.repository_collection_id
    new = {
        "original_filename": doc.original_filename,
        "document_type_id": str(doc.document_type_id) if doc.document_type_id else None,
        "repository_collection_id": str(doc.repository_collection_id) if doc.repository_collection_id else None,
    }
    diff = {k: {"old": old[k], "new": new[k]} for k in old if old[k] != new[k]}
    if diff:
        audit_log(
            db,
            user=user,
            action="document.update",
            entity_type="document",
            entity_id=str(doc.id),
            old_value=diff,
            new_value={"changed": list(diff)},
            **request_context(request),
        )
    db.commit()
    db.refresh(doc)
    return _doc_out(doc)


@router.post("/{document_id}/ocr", status_code=202)
def request_ocr(document_id: str, request: Request, db: Session = Depends(get_db), _: User = Depends(can_upload)):
    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Documento no valido")
    doc = db.get(Document, doc_uuid)
    if doc is None:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    if not doc.needs_ocr:
        raise HTTPException(status_code=409, detail="El documento tiene texto; no requiere OCR")
    job = _enqueue_ocr(db, doc)
    audit_log(
        db,
        user=_,
        action="ocr.request",
        entity_type="document",
        entity_id=str(doc.id),
        new_value={"job_id": str(job.id), "languages": settings.ocr_languages},
        **request_context(request),
    )
    db.commit()
    return {
        "status": "QUEUED",
        "job_id": str(job.id),
        "document_id": str(doc.id),
        "message": "OCR encolado; consulte el detalle del documento para ver el progreso",
    }


@router.get("/{document_id}/download")
def download_document(document_id: str, db: Session = Depends(get_db), _: User = Depends(can_view)):
    doc = db.get(Document, uuid.UUID(document_id))
    if doc is None:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    try:
        content = storage.download_original(doc.storage_path)
    except StorageError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    filename = _safe_filename(doc.original_filename or f"{doc.sha256 or doc.id}.pdf")
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/{document_id}", status_code=204)
def delete_document(document_id: str, request: Request, db: Session = Depends(get_db), _: User = Depends(can_upload)):
    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Documento no valido")
    doc = db.get(Document, doc_uuid)
    if doc is None:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    storage.delete_original(doc.storage_path)
    if doc.sha256 and storage.object_exists(f"ocr/{doc.sha256}.pdf"):
        storage.delete_object(f"ocr/{doc.sha256}.pdf")
    for run in doc.extraction_runs:
        if run.raw_response_storage_path and storage.object_exists(run.raw_response_storage_path):
            storage.delete_object(run.raw_response_storage_path)
    audit_log(
        db,
        user=_,
        action="document.delete",
        entity_type="document",
        entity_id=str(doc.id),
        old_value={"filename": doc.original_filename, "sha256": doc.sha256},
        **request_context(request),
    )
    db.delete(doc)
    db.commit()