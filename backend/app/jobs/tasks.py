import json
from datetime import datetime, timezone
from uuid import UUID

from celery import shared_task

from app.audit.service import audit_log
from app.core import storage
from app.core.config import settings
from app.core.database import SessionLocal
from app.extraction import engine
from app.normalization import engine as norm_engine
from app.jobs.celery_app import celery_app
from app.models import (
    Deposition,
    Document,
    ExtractionRun,
    MetadataRecord,
    ProcessingJob,
    Repository,
    RepositoryCollection,
    ValidationResult,
    VocabularyValue,
)
from app.ocr import engine as ocr_engine
from app.dspace.connector import build_connector
from app.snrd.export import dc_fields
from app.snrd.validator import validate_snrd
from app.validation import engine as validation_engine
from app.workflows import DocumentStatus, set_document_status


def _set_progress(job: ProcessingJob | None, value: int) -> None:
    if job is not None:
        job.progress = max(0, min(100, value))


def _repair_json_response(provider, model_identifier, system, user, *, temperature, max_tokens):
    repair_user = (
        user
        + "\n\nLa respuesta anterior no era JSON valido. Devuelve SOLO un objeto JSON valido, sin markdown ni texto adicional."
    )
    return engine.call_model(
        provider,
        model_identifier,
        system,
        repair_user,
        temperature=0.0,
        max_tokens=max_tokens,
        supports_json=True,
    )


@shared_task(name="app.jobs.tasks.analyze_document")
def analyze_document(document_id: str) -> dict:
    """Analisis liviano del PDF antes de OCR/extraccion.

    Recalcula las propiedades principales del documento y deja trazabilidad en
    ``processing_jobs``. Si el PDF ya tenia el texto extraido no altera el
    contenido: solo refresca metadatos de analisis.
    """
    db = SessionLocal()
    job = None
    try:
        doc = db.get(Document, UUID(document_id))
        if doc is None:
            return {"status": "ERROR", "document_id": document_id, "error": "documento no encontrado"}
        job = (
            db.query(ProcessingJob)
            .filter(
                ProcessingJob.document_id == doc.id,
                ProcessingJob.job_type == "ANALYSIS",
                ProcessingJob.status == "PENDING",
            )
            .order_by(ProcessingJob.created_at.asc())
            .first()
        )
        if job is None:
            job = ProcessingJob(document_id=doc.id, job_type="ANALYSIS", status="PENDING")
            db.add(job)
            db.flush()
        job.status = "RUNNING"
        job.started_at = datetime.now(timezone.utc)
        _set_progress(job, 10)
        set_document_status(db, doc, DocumentStatus.ANALYZING)
        db.commit()

        original = storage.download_original(doc.storage_path)
        analysis = engine.analyze_pdf(original)
        doc.page_count = analysis["page_count"]
        doc.needs_ocr = analysis["needs_ocr"]
        for i, text in enumerate(analysis["pages_text"], start=1):
            page = next((p for p in doc.pages if p.page_number == i), None)
            if page is None:
                page = None
            if page is not None:
                page.text = text
                page.text_length = len(text or "")
        _set_progress(job, 80)
        set_document_status(db, doc, DocumentStatus.TEXT_EXTRACTED)
        job.status = "COMPLETED"
        job.finished_at = datetime.now(timezone.utc)
        job.metadata_json = {
            "page_count": analysis["page_count"],
            "needs_ocr": analysis["needs_ocr"],
            "text_pages": len(analysis.get("pages_text", []) or []),
        }
        _set_progress(job, 100)
        db.commit()
        return {
            "status": "COMPLETED",
            "document_id": document_id,
            "page_count": analysis["page_count"],
            "needs_ocr": analysis["needs_ocr"],
        }
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        if job is not None:
            job.status = "ERROR"
            job.error_message = str(exc)[:2000]
            job.finished_at = datetime.now(timezone.utc)
            _set_progress(job, 0)
        doc = db.get(Document, UUID(document_id)) if document_id else None
        if doc is not None:
            set_document_status(db, doc, DocumentStatus.ERROR)
            db.commit()
        return {"status": "ERROR", "document_id": document_id, "error": str(exc)[:1000]}
    finally:
        db.close()


@shared_task(name="app.jobs.tasks.run_ocr")
def run_ocr(document_id: str, languages: str | None = None) -> dict:
    """OCR sobre un documento escaneado (FASE 8).

    PDF original -> OCRmyPDF+Tesseract -> PDF buscable -> texto por pagina.
    El original nunca se modifica; el buscable se guarda en ocr/{sha256}.pdf.
    """
    db = SessionLocal()
    job = None
    try:
        doc = db.get(Document, UUID(document_id))
        if doc is None:
            return {"status": "ERROR", "error": "documento no encontrado"}

        job = (
            db.query(ProcessingJob)
            .filter(
                ProcessingJob.document_id == doc.id,
                ProcessingJob.job_type == "OCR",
                ProcessingJob.status == "PENDING",
            )
            .order_by(ProcessingJob.created_at.asc())
            .first()
        )
        if job is None:
            job = ProcessingJob(document_id=doc.id, job_type="OCR", status="PENDING")
            db.add(job)
            db.flush()
        job.status = "RUNNING"
        job.started_at = datetime.now(timezone.utc)
        set_document_status(db, doc, DocumentStatus.OCR_PROCESSING)
        db.commit()
        db.refresh(job)

        original = storage.download_original(doc.storage_path)
        langs = ocr_engine.resolve_ocr_languages(db, doc, languages)
        result = ocr_engine.perform_ocr(original, langs)
        searchable_pdf = result["pdf"]
        ocr_key = storage.upload_searchable(doc.sha256 or "", searchable_pdf)
        texts = ocr_engine.extract_text_pdf(searchable_pdf)

        pages = sorted(doc.pages, key=lambda p: p.page_number)
        for i, page in enumerate(pages, start=1):
            if i <= len(texts):
                page.text = texts[i - 1] or ""
                page.text_length = len(page.text or "")
                page.ocr_used = True

        doc.status = "OCR_COMPLETED"
        job.status = "COMPLETED"
        job.finished_at = datetime.now(timezone.utc)
        job.metadata_json = {
            **result["meta"],
            "pages_processed": len(texts),
            "output_object": ocr_key,
        }
        audit_log(
            db,
            action="ocr.completed",
            entity_type="document",
            entity_id=document_id,
            new_value={
                "pages_processed": len(texts),
                "languages": langs,
                "duration_ms": (result["meta"] or {}).get("duration_ms"),
            },
        )
        db.commit()
        if settings.auto_ai:
            celery_app.send_task("app.jobs.tasks.extract_metadata", args=[str(doc.id)])
        return {
            "status": "COMPLETED",
            "document_id": document_id,
            "pages": len(texts),
            "ocr": {**result["meta"], "output_object": ocr_key},
        }
    except Exception as exc:  # noqa: BLE001 - el error queda registrado en el job
        db.rollback()
        if job is not None:
            job.status = "ERROR"
            job.error_message = str(exc)[:2000]
            job.finished_at = datetime.now(timezone.utc)
            doc = db.get(Document, UUID(document_id))
            if doc is not None and doc.status == DocumentStatus.OCR_PROCESSING:
                doc.status = DocumentStatus.UPLOADED
            db.commit()
        return {"status": "ERROR", "document_id": document_id, "error": str(exc)[:1000]}
    finally:
        db.close()


@shared_task(name="app.jobs.tasks.extract_text")
def extract_text(document_id: str) -> dict:
    """Extraccion de texto por pagina.

    Si el documento requiere OCR, ejecuta OCRmyPDF; si no, refresca el texto
    ya disponible desde el PDF original.
    """
    db = SessionLocal()
    job = None
    try:
        doc = db.get(Document, UUID(document_id))
        if doc is None:
            return {"status": "ERROR", "document_id": document_id, "error": "documento no encontrado"}
        job = (
            db.query(ProcessingJob)
            .filter(
                ProcessingJob.document_id == doc.id,
                ProcessingJob.job_type == "TEXT_EXTRACTION",
                ProcessingJob.status == "PENDING",
            )
            .order_by(ProcessingJob.created_at.asc())
            .first()
        )
        if job is None:
            job = ProcessingJob(document_id=doc.id, job_type="TEXT_EXTRACTION", status="PENDING")
            db.add(job)
            db.flush()
        job.status = "RUNNING"
        job.started_at = datetime.now(timezone.utc)
        _set_progress(job, 10)
        set_document_status(db, doc, DocumentStatus.ANALYZING)
        db.commit()

        original = storage.download_original(doc.storage_path)
        needs_ocr = doc.needs_ocr
        pages_text = ocr_engine.extract_text_pdf(original)
        if needs_ocr or not any((t or "").strip() for t in pages_text):
            _set_progress(job, 40)
            langs = ocr_engine.resolve_ocr_languages(db, doc)
            result = ocr_engine.perform_ocr(original, langs)
            searchable_pdf = result["pdf"]
            pages_text = ocr_engine.extract_text_pdf(searchable_pdf)
            storage.upload_searchable(doc.sha256 or "", searchable_pdf)
            doc.needs_ocr = False
            doc.status = "OCR_COMPLETED"
        for i, text in enumerate(pages_text, start=1):
            page = next((p for p in doc.pages if p.page_number == i), None)
            if page is None:
                continue
            page.text = text or ""
            page.text_length = len(page.text)
            page.ocr_used = needs_ocr
        _set_progress(job, 90)
        set_document_status(db, doc, DocumentStatus.TEXT_EXTRACTED)
        job.status = "COMPLETED"
        job.finished_at = datetime.now(timezone.utc)
        job.metadata_json = {"pages": len(pages_text)}
        _set_progress(job, 100)
        db.commit()
        return {"status": "COMPLETED", "document_id": document_id, "pages": len(pages_text)}
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        if job is not None:
            job.status = "ERROR"
            job.error_message = str(exc)[:2000]
            job.finished_at = datetime.now(timezone.utc)
            _set_progress(job, 0)
        doc = db.get(Document, UUID(document_id)) if document_id else None
        if doc is not None:
            set_document_status(db, doc, DocumentStatus.ERROR)
            db.commit()
        return {"status": "ERROR", "document_id": document_id, "error": str(exc)[:1000]}
    finally:
        db.close()


@shared_task(name="app.jobs.tasks.extract_metadata")
def extract_metadata(document_id: str) -> dict:
    """Extraccion de metadatos con IA (FASE 9).

    Documento con texto (o con OCR aplicado) -> agente automatico ->
    prompt con el esquema de metadatos -> modelo -> JSON validado ->
    MetadataRecord por campo (value + confidence + evidencia de pagina).
    """
    db = SessionLocal()
    job = None
    run = None
    try:
        doc = db.get(Document, UUID(document_id))
        if doc is None:
            return {"status": "ERROR", "document_id": document_id, "error": "documento no encontrado"}

        doc_type = doc.document_type
        agent = engine.select_agent(doc_type, db)
        if agent is None or agent.current_version is None:
            return {"status": "ERROR", "document_id": document_id,
                    "error": "no hay un agente de IA activo con version para este documento"}
        version = agent.current_version
        model = version.model
        provider = model.provider

        text = engine.document_text(doc)
        if not text.strip():
            raise engine.NoTextError("el documento no tiene texto; ejecute OCR primero")

        field_defs = engine.build_field_defs(doc_type, db)
        context = engine.build_context(doc, doc_type, field_defs)
        system, user = engine.build_prompt(version, context)

        run = ExtractionRun(
            document_id=doc.id,
            agent_id=agent.id,
            agent_version_id=version.id,
            model_id=model.id,
            prompt_hash=engine.prompt_hash(system, user),
            started_at=datetime.now(timezone.utc),
            status="RUNNING",
        )
        db.add(run)
        job = (
            db.query(ProcessingJob)
            .filter(
                ProcessingJob.document_id == doc.id,
                ProcessingJob.job_type == "EXTRACTION",
                ProcessingJob.status == "PENDING",
            )
            .order_by(ProcessingJob.created_at.asc())
            .first()
        )
        if job is None:
            job = ProcessingJob(document_id=doc.id, job_type="EXTRACTION", status="PENDING")
            db.add(job)
            db.flush()
        job.status = "RUNNING"
        job.started_at = datetime.now(timezone.utc)
        set_document_status(db, doc, DocumentStatus.AI_PROCESSING)
        db.commit()
        db.refresh(run)

        call = engine.call_model(
            provider,
            model.model_identifier,
            system,
            user,
            temperature=version.temperature,
            max_tokens=version.max_tokens,
            supports_json=model.supports_json,
        )
        try:
            data = engine.parse_content(call["content"])
        except engine.ExtractionError:
            repair = _repair_json_response(
                provider,
                model.model_identifier,
                system,
                user,
                temperature=version.temperature,
                max_tokens=version.max_tokens,
            )
            call = {**call, **repair}
            data = engine.parse_content(repair["content"])
        payload = data.get("fields", data) if isinstance(data, dict) else data
        schema_errors = engine.validate_schema(payload, version.output_schema_json or {})
        if schema_errors:
            raise engine.ExtractionError("salida no valida: " + "; ".join(schema_errors))
        records = engine.parse_fields(data, field_defs)

        raw_key = storage.upload_object(
            f"raw/{run.id}.json",
            json.dumps(
                {"prompt_hash": run.prompt_hash, "response": data, "call": call},
                ensure_ascii=False,
            ).encode("utf-8"),
            "application/json",
        )

        for rec in records:
            db.add(
                MetadataRecord(
                    document_id=doc.id,
                    metadata_field_id=UUID(rec["metadata_field_id"]),
                    value=rec["value"],
                    language=context["language"],
                    confidence=rec["confidence"],
                    source="IA",
                    source_page=rec["source_page"],
                    source_text=rec["source_text"],
                    extraction_run_id=run.id,
                )
            )

        set_document_status(db, doc, DocumentStatus.METADATA_EXTRACTED)
        run.status = "COMPLETED"
        run.finished_at = datetime.now(timezone.utc)
        run.raw_response_storage_path = raw_key
        run.input_tokens = call["input_tokens"]
        run.output_tokens = call["output_tokens"]
        job.status = "COMPLETED"
        job.finished_at = datetime.now(timezone.utc)
        job.metadata_json = {
            "run_id": str(run.id),
            "agent_code": agent.code,
            "model": model.model_identifier,
            "provider": provider.code,
            "records": len(records),
            "time_ms": call["time_ms"],
            "input_tokens": call["input_tokens"],
            "output_tokens": call["output_tokens"],
            "raw_object": raw_key,
        }
        audit_log(
            db,
            action="ai.extraction",
            entity_type="document",
            entity_id=document_id,
            new_value={
                "agent": agent.code,
                "model": model.model_identifier,
                "provider": provider.code,
                "prompt_hash": run.prompt_hash,
                "records": len(records),
                "time_ms": call["time_ms"],
                "input_tokens": call["input_tokens"],
                "output_tokens": call["output_tokens"],
            },
        )
        db.commit()
        if settings.auto_normalize and records:
            normalize_metadata(document_id)
        if settings.auto_validate and records:
            validate_metadata(document_id)
        return {
            "status": "COMPLETED",
            "document_id": document_id,
            "records": len(records),
            "agent": agent.code,
            "model": model.model_identifier,
        }
    except Exception as exc:  # noqa: BLE001 - el error queda registrado
        db.rollback()
        doc = db.get(Document, UUID(document_id))
        if doc is not None and doc.status == DocumentStatus.AI_PROCESSING:
            doc.status = DocumentStatus.UPLOADED
        if run is not None:
            run = db.get(ExtractionRun, run.id)
            if run is not None:
                run.status = "AI_ERROR" if any(code in str(exc) for code in ("AI_INVALID_JSON", "AI_TIMEOUT", "AI_CONNECTION_ERROR", "AI_SCHEMA_ERROR")) else "ERROR"
                run.finished_at = datetime.now(timezone.utc)
                run.error_message = str(exc)[:2000]
        if job is not None:
            job = db.get(ProcessingJob, job.id)
            if job is not None:
                job.status = "ERROR"
                job.finished_at = datetime.now(timezone.utc)
                job.error_message = str(exc)[:2000]
        audit_log(
            db,
            action="ai.extraction.failed",
            entity_type="document",
            entity_id=document_id,
            new_value={"error": str(exc)[:1000]},
        )
        db.commit()
        return {"status": "ERROR", "document_id": document_id, "error": str(exc)[:1000]}
    finally:
        db.close()


@shared_task(name="app.jobs.tasks.normalize_metadata")
def normalize_metadata(document_id: str) -> dict:
    """Normalizacion de metadatos (FASE 10).

    Convierte los valores extraidos por IA al formato configurado mediante
    reglas deterministas (vocabularios con sinonimos, fechas ISO, DOI, ORCID,
    nombres, espacios/mayusculas). Un valor no convertible se deja intacto
    (normalized=False).
    """
    db = SessionLocal()
    job = None
    try:
        doc = db.get(Document, UUID(document_id))
        if doc is None:
            return {"status": "ERROR", "document_id": document_id, "error": "documento no encontrado"}

        records = (
            db.query(MetadataRecord)
            .filter(MetadataRecord.document_id == doc.id, MetadataRecord.value.isnot(None))
            .all()
        )
        if not records:
            return {"status": "NOOP", "document_id": document_id, "records": 0}

        job = (
            db.query(ProcessingJob)
            .filter(
                ProcessingJob.document_id == doc.id,
                ProcessingJob.job_type == "NORMALIZATION",
                ProcessingJob.status == "PENDING",
            )
            .order_by(ProcessingJob.created_at.asc())
            .first()
        )
        if job is None:
            job = ProcessingJob(document_id=doc.id, job_type="NORMALIZATION", status="PENDING")
            db.add(job)
            db.flush()
        job.status = "RUNNING"
        job.started_at = datetime.now(timezone.utc)
        set_document_status(db, doc, DocumentStatus.NORMALIZING)
        db.commit()

        vocab_cache: dict = {}
        changed = 0
        for rec in records:
            field = rec.metadata_field
            if field is None:
                continue
            vocab_values = []
            if field.vocabulary_id:
                if field.vocabulary_id not in vocab_cache:
                    vocab_cache[field.vocabulary_id] = (
                        db.query(VocabularyValue)
                        .filter(
                            VocabularyValue.vocabulary_id == field.vocabulary_id,
                            VocabularyValue.active.is_(True),
                        )
                        .all()
                    )
                vocab_values = vocab_cache[field.vocabulary_id]
            result = norm_engine.normalize_record_value(
                field, rec.value or "", vocab_values=vocab_values
            )
            if result.ok and result.value != (rec.value or ""):
                rec.value = result.value
                rec.normalized = True
                changed += 1

        set_document_status(db, doc, DocumentStatus.NORMALIZED)
        job.status = "COMPLETED"
        job.finished_at = datetime.now(timezone.utc)
        job.metadata_json = {
            "records": len(records),
            "changed": changed,
            "rule": "deterministic",
        }
        audit_log(
            db,
            action="metadata.normalize",
            entity_type="document",
            entity_id=document_id,
            new_value={"records": len(records), "changed": changed},
        )
        db.commit()
        return {
            "status": "COMPLETED",
            "document_id": document_id,
            "records": len(records),
            "changed": changed,
        }
    except Exception as exc:  # noqa: BLE001 - el error queda registrado
        db.rollback()
        if job is not None:
            job = db.get(ProcessingJob, job.id)
            if job is not None:
                job.status = "ERROR"
                job.finished_at = datetime.now(timezone.utc)
                job.error_message = str(exc)[:2000]
            db.commit()
        return {"status": "ERROR", "document_id": document_id, "error": str(exc)[:1000]}
    finally:
        db.close()


@shared_task(name="app.jobs.tasks.validate_metadata")
def validate_metadata(document_id: str) -> dict:
    """Validacion de metadatos (FASE 11).

    Ejecuta las reglas por campo (obligatorios, formatos, vocabularios) y
    la verificacion SNRD sobre los registros del documento, registrando un
    ValidationResult por validador. El documento pasa a VALIDATED si no hay
    errores, o VALIDATION_FAILED si los hay.
    """
    db = SessionLocal()
    job = None
    try:
        doc = db.get(Document, UUID(document_id))
        if doc is None:
            return {"status": "ERROR", "document_id": document_id, "error": "documento no encontrado"}

        records = (
            db.query(MetadataRecord)
            .filter(MetadataRecord.document_id == doc.id, MetadataRecord.value.isnot(None))
            .all()
        )
        if not records:
            return {"status": "NOOP", "document_id": document_id, "records": 0}

        job = (
            db.query(ProcessingJob)
            .filter(
                ProcessingJob.document_id == doc.id,
                ProcessingJob.job_type == "VALIDATION",
                ProcessingJob.status == "PENDING",
            )
            .order_by(ProcessingJob.created_at.asc())
            .first()
        )
        if job is None:
            job = ProcessingJob(document_id=doc.id, job_type="VALIDATION", status="PENDING")
            db.add(job)
            db.flush()
        job.status = "RUNNING"
        job.started_at = datetime.now(timezone.utc)
        set_document_status(db, doc, DocumentStatus.VALIDATING)
        db.commit()

        vocab_cache: dict = {}
        for rec in records:
            field = rec.metadata_field
            if field is not None and field.vocabulary_id and field.vocabulary_id not in vocab_cache:
                vocab_cache[field.vocabulary_id] = (
                    db.query(VocabularyValue)
                    .filter(
                        VocabularyValue.vocabulary_id == field.vocabulary_id,
                        VocabularyValue.active.is_(True),
                    )
                    .all()
                )

        outcome = validation_engine.validate_records(records, vocab_cache, db=db)
        type_fields = []
        if doc.document_type is not None:
            type_fields = [
                link.metadata_field
                for link in doc.document_type.metadata_field_links
                if link.metadata_field is not None and link.metadata_field.active
            ]
        outcome.errors = validation_engine.missing_required(type_fields, records) + outcome.errors
        snrd_errors, snrd_warnings = validate_snrd(
            records, doc_type_label=doc.document_type.code if doc.document_type else None, db=db
        )
        errors = outcome.errors + snrd_errors
        warnings = outcome.warnings + snrd_warnings

        meta_result = ValidationResult(
            document_id=doc.id,
            validator_type="METADATA",
            status="COMPLETED" if not outcome.errors else "FAILED",
            errors_json=outcome.errors,
            warnings_json=outcome.warnings,
        )
        snrd_result = ValidationResult(
            document_id=doc.id,
            validator_type="SNRD",
            status="COMPLETED" if not snrd_errors else "FAILED",
            errors_json=snrd_errors,
            warnings_json=snrd_warnings,
        )
        db.add_all([meta_result, snrd_result])

        set_document_status(db, doc, DocumentStatus.VALIDATED if not errors else DocumentStatus.VALIDATION_FAILED)
        job.status = "COMPLETED"
        job.finished_at = datetime.now(timezone.utc)
        job.metadata_json = {
            "errors": len(errors),
            "warnings": len(warnings),
            "valid": not errors,
        }
        audit_log(
            db,
            action="document.validate",
            entity_type="document",
            entity_id=document_id,
            new_value={
                "valid": not errors,
                "errors": len(errors),
                "warnings": len(warnings),
                "status": doc.status,
            },
        )
        db.commit()
        return {
            "status": "COMPLETED",
            "document_id": document_id,
            "errors": len(errors),
            "warnings": len(warnings),
            "valid": not errors,
        }
    except Exception as exc:  # noqa: BLE001 - el error queda registrado
        db.rollback()
        if job is not None:
            job = db.get(ProcessingJob, job.id)
            if job is not None:
                job.status = "ERROR"
                job.finished_at = datetime.now(timezone.utc)
                job.error_message = str(exc)[:2000]
            db.commit()
        return {"status": "ERROR", "document_id": document_id, "error": str(exc)[:1000]}
    finally:
        db.close()


@shared_task(name="app.jobs.tasks.deposit_dspace")
def deposit_dspace(document_id: str) -> dict:
    """Alias del job de deposito para compatibilidad con la cola."""
    return deposit_document(document_id)


@shared_task(name="app.jobs.tasks.deposit_document")
def deposit_document(document_id: str) -> dict:
    """Deposito de un documento aprobado en DSpace (FASE 13).

    Flujo: APPOVED -> validacion final -> workspace item -> metadata SNRD-DC
    -> PDF -> submission -> registro del resultado (Deposition). Si algo
    falla el documento vuelve a APPROVED (reintento permitido) y el error
    queda en el job y en la deposicion. Un deposito exitoso no se duplica
    (guard por estado del documento y por Deposition COMPLETED).
    """
    db = SessionLocal()
    job = None
    try:
        doc = db.get(Document, UUID(document_id))
        if doc is None:
            return {"status": "ERROR", "document_id": document_id, "error": "documento no encontrado"}

        job = (
            db.query(ProcessingJob)
            .filter(
                ProcessingJob.document_id == doc.id,
                ProcessingJob.job_type == "DEPOSIT",
                ProcessingJob.status == "PENDING",
            )
            .order_by(ProcessingJob.created_at.asc())
            .first()
        )
        if job is None:
            job = ProcessingJob(document_id=doc.id, job_type="DEPOSIT", status="PENDING")
            db.add(job)
            db.flush()

        if doc.status == "DEPOSITED":
            job.status = "NOOP"
            job.finished_at = datetime.now(timezone.utc)
            job.metadata_json = {"reason": "ya depositado"}
            db.commit()
            return {"status": "NOOP", "document_id": document_id, "reason": "ya depositado"}

        existing = (
            db.query(Deposition)
            .filter(Deposition.document_id == doc.id, Deposition.status == "COMPLETED")
            .first()
        )
        if existing is not None:
            job.status = "NOOP"
            job.finished_at = datetime.now(timezone.utc)
            job.metadata_json = {"reason": "ya depositado", "external_item_id": existing.external_item_id}
            db.commit()
            return {"status": "NOOP", "document_id": document_id, "reason": "ya depositado"}

        if doc.status != "APPROVED":
            job.status = "ERROR"
            job.finished_at = datetime.now(timezone.utc)
            job.error_message = "el documento no esta APROBADO"
            db.commit()
            return {"status": "ERROR", "document_id": document_id, "error": "el documento no esta APROBADO"}

        collection = None
        if doc.repository_collection_id is not None:
            collection = db.get(RepositoryCollection, doc.repository_collection_id)
        elif doc.document_type is not None:
            collection = next((c for c in doc.document_type.repository_collections if c.active), None)
        if collection is None:
            job.status = "ERROR"
            job.finished_at = datetime.now(timezone.utc)
            job.error_message = "no hay coleccion configurada para el tipo documental"
            db.commit()
            return {"status": "ERROR", "document_id": document_id, "error": "coleccion no configurada"}

        repo: Repository | None = db.get(Repository, collection.repository_id)
        if repo is None or not repo.active:
            job.status = "ERROR"
            job.finished_at = datetime.now(timezone.utc)
            job.error_message = "repositorio destino no configurado o inactivo"
            db.commit()
            return {"status": "ERROR", "document_id": document_id, "error": "repositorio no configurado"}

        vres = validate_metadata(document_id)
        if vres.get("status") != "COMPLETED" or not vres.get("valid"):
            job.status = "ERROR"
            job.finished_at = datetime.now(timezone.utc)
            job.error_message = "validacion final con errores"
            db.commit()
            return {"status": "ERROR", "document_id": document_id, "error": "validacion final con errores"}

        job.status = "RUNNING"
        job.started_at = datetime.now(timezone.utc)
        set_document_status(db, doc, DocumentStatus.DEPOSITING)
        dep = Deposition(
            document_id=doc.id,
            repository_id=repo.id,
            collection_id=collection.id,
            status="RUNNING",
            started_at=datetime.now(timezone.utc),
            request_json={"collection": collection.external_id, "collection_name": collection.name},
        )
        db.add(dep)
        db.commit()

        records = (
            db.query(MetadataRecord)
            .filter(MetadataRecord.document_id == doc.id, MetadataRecord.value.isnot(None))
            .all()
        )
        metadata = dc_fields(records, identifier=doc.sha256)
        content = storage.download_original(doc.storage_path)

        connector = build_connector(repo)
        token = connector.authenticate()
        ws = connector.create_workspace_item(collection.external_id or "", token)
        connector.add_metadata(str(ws.get("id")), metadata, token)
        bitstream = connector.upload_bitstream(
            str(ws.get("id")), doc.original_filename or "documento.pdf", content, token
        )
        submitted = connector.submit_workspace_item(str(ws.get("id")), token)

        dep.external_item_id = submitted.get("item_uuid")
        dep.handle = submitted.get("handle")
        dep.status = "COMPLETED"
        dep.finished_at = datetime.now(timezone.utc)
        dep.response_json = {
            "workspace_item": ws.get("id"),
            "bitstream": bitstream.get("uuid") or bitstream.get("name"),
            "item": submitted.get("item_uuid"),
            "handle": submitted.get("handle"),
        }
        doc.status = "DEPOSITED"
        job.status = "COMPLETED"
        job.finished_at = datetime.now(timezone.utc)
        job.metadata_json = {
            "external_item_id": submitted.get("item_uuid"),
            "handle": submitted.get("handle"),
            "workspace_item": ws.get("id"),
        }
        audit_log(
            db,
            action="deposit.completed",
            entity_type="document",
            entity_id=document_id,
            new_value={
                "repository_code": repo.code,
                "collection": collection.name,
                "external_item_id": submitted.get("item_uuid"),
                "handle": submitted.get("handle"),
            },
        )
        db.commit()
        return {
            "status": "COMPLETED",
            "document_id": document_id,
            "external_item_id": submitted.get("item_uuid"),
            "handle": submitted.get("handle"),
        }
    except Exception as exc:  # noqa: BLE001 - el error queda registrado
        db.rollback()
        if job is not None:
            job = db.get(ProcessingJob, job.id)
            if job is not None:
                job.status = "ERROR"
                job.finished_at = datetime.now(timezone.utc)
                job.error_message = str(exc)[:2000]
            dep_row = (
                db.query(Deposition)
                .filter(
                    Deposition.document_id == UUID(document_id),
                    Deposition.status.in_(["RUNNING", "PENDING"]),
                )
                .order_by(Deposition.started_at.asc().nullsfirst(), Deposition.id.asc())
                .first()
            )
            if dep_row is not None:
                dep_row.status = "FAILED"
                dep_row.finished_at = datetime.now(timezone.utc)
                dep_row.error_message = str(exc)[:2000]
            doc = db.get(Document, UUID(document_id))
            if doc is not None and doc.status == DocumentStatus.DEPOSITING:
                doc.status = "APPROVED"
            audit_log(
                db,
                action="deposit.failed",
                entity_type="document",
                entity_id=document_id,
                new_value={"error": str(exc)[:1000]},
            )
            db.commit()
        return {"status": "ERROR", "document_id": document_id, "error": str(exc)[:1000]}
