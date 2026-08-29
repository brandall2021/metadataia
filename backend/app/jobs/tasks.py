import json
from datetime import datetime, timezone
from uuid import UUID

from celery import shared_task

from app.core import storage
from app.core.config import settings
from app.core.database import SessionLocal
from app.extraction import engine
from app.normalization import engine as norm_engine
from app.jobs.celery_app import celery_app
from app.models import (
    Document,
    ExtractionRun,
    MetadataRecord,
    ProcessingJob,
    ValidationResult,
    VocabularyValue,
)
from app.ocr import engine as ocr_engine
from app.snrd.validator import validate_snrd
from app.validation import engine as validation_engine


@shared_task(name="app.jobs.tasks.analyze_document")
def analyze_document(document_id: str) -> dict:
    """Job placeholder: analisis de documento (FASE 7 ya cubre el analisis)."""
    return {"document_id": document_id, "status": "PENDING"}


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
        doc.status = "PROCESSING"
        db.commit()
        db.refresh(job)

        original = storage.download_original(doc.storage_path)
        langs = languages or settings.ocr_languages
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
            if doc is not None and doc.status == "PROCESSING":
                doc.status = "UPLOADED"
            db.commit()
        return {"status": "ERROR", "document_id": document_id, "error": str(exc)[:1000]}
    finally:
        db.close()


@shared_task(name="app.jobs.tasks.extract_text")
def extract_text(document_id: str) -> dict:
    """Job placeholder: extraccion de texto por pagina (FASE 8/16)."""
    return {"document_id": document_id, "status": "PENDING"}


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
        doc.status = "PROCESSING"
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
        data = engine.parse_content(call["content"])
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

        doc.status = "METADATA_EXTRACTED"
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
        if doc is not None and doc.status == "PROCESSING":
            doc.status = "UPLOADED"
        if run is not None:
            run = db.get(ExtractionRun, run.id)
            if run is not None:
                run.status = "ERROR"
                run.finished_at = datetime.now(timezone.utc)
                run.error_message = str(exc)[:2000]
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
        doc.status = "PROCESSING"
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

        doc.status = "NORMALIZED"
        job.status = "COMPLETED"
        job.finished_at = datetime.now(timezone.utc)
        job.metadata_json = {
            "records": len(records),
            "changed": changed,
            "rule": "deterministic",
        }
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
        doc.status = "PROCESSING"
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

        outcome = validation_engine.validate_records(records, vocab_cache)
        type_fields = []
        if doc.document_type is not None:
            type_fields = [
                link.metadata_field
                for link in doc.document_type.metadata_field_links
                if link.metadata_field is not None and link.metadata_field.active
            ]
        outcome.errors = validation_engine.missing_required(type_fields, records) + outcome.errors
        snrd_errors, snrd_warnings = validate_snrd(
            records, doc_type_label=doc.document_type.code if doc.document_type else None
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

        doc.status = "VALIDATED" if not errors else "VALIDATION_FAILED"
        job.status = "COMPLETED"
        job.finished_at = datetime.now(timezone.utc)
        job.metadata_json = {
            "errors": len(errors),
            "warnings": len(warnings),
            "valid": not errors,
        }
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
    """Job placeholder: deposito en DSpace (FASE 13)."""
    return {"document_id": document_id, "status": "PENDING"}