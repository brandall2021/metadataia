from celery import shared_task


@shared_task(name="app.jobs.tasks.analyze_document")
def analyze_document(document_id: str) -> dict:
    """Job placeholder: analisis de documento (se implementa en FASE 7)."""
    return {"document_id": document_id, "status": "PENDING"}


@shared_task(name="app.jobs.tasks.run_ocr")
def run_ocr(document_id: str) -> dict:
    """Job placeholder: OCR sobre documento escaneado (FASE 8)."""
    return {"document_id": document_id, "status": "PENDING"}


@shared_task(name="app.jobs.tasks.extract_text")
def extract_text(document_id: str) -> dict:
    """Job placeholder: extraccion de texto por pagina (FASE 8/16)."""
    return {"document_id": document_id, "status": "PENDING"}


@shared_task(name="app.jobs.tasks.extract_metadata")
def extract_metadata(document_id: str) -> dict:
    """Job placeholder: extraccion de metadatos con IA (FASE 9)."""
    return {"document_id": document_id, "status": "PENDING"}


@shared_task(name="app.jobs.tasks.normalize_metadata")
def normalize_metadata(document_id: str) -> dict:
    """Job placeholder: normalizacion de metadatos (FASE 10)."""
    return {"document_id": document_id, "status": "PENDING"}


@shared_task(name="app.jobs.tasks.validate_metadata")
def validate_metadata(document_id: str) -> dict:
    """Job placeholder: validacion de metadatos (FASE 11)."""
    return {"document_id": document_id, "status": "PENDING"}


@shared_task(name="app.jobs.tasks.deposit_dspace")
def deposit_dspace(document_id: str) -> dict:
    """Job placeholder: deposito en DSpace (FASE 13)."""
    return {"document_id": document_id, "status": "PENDING"}