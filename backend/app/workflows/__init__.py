"""Maquina de estados del workflow de documentos (seccion 24).

Cada cambio de estado queda registrado en auditoria. Los estados cubren todo el
recorrido: PDF -> OCR -> texto -> IA -> normalizacion -> validacion -> revision
humana -> deposito.
"""

import time

from sqlalchemy.orm import Session

from app.audit.service import audit_log
from app.models import Document, User


class DocumentStatus:
    UPLOADED = "UPLOADED"
    ANALYZING = "ANALYZING"
    OCR_PROCESSING = "OCR_PROCESSING"
    TEXT_EXTRACTED = "TEXT_EXTRACTED"
    AI_PROCESSING = "AI_PROCESSING"
    METADATA_EXTRACTED = "METADATA_EXTRACTED"
    NORMALIZING = "NORMALIZING"
    NORMALIZED = "NORMALIZED"
    VALIDATING = "VALIDATING"
    VALIDATED = "VALIDATED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    REJECTED = "REJECTED"
    APPROVED = "APPROVED"
    DEPOSITING = "DEPOSITING"
    DEPOSITED = "DEPOSITED"
    ERROR = "ERROR"


# El orden cronologico del pipeline automatico. La revision humana rompe este
# orden: cualquier estado previo a DEPOSITED puede volver a NEEDS_REVIEW.
AUTO_SEQUENCE = [
    DocumentStatus.UPLOADED,
    DocumentStatus.ANALYZING,
    DocumentStatus.OCR_PROCESSING,
    DocumentStatus.TEXT_EXTRACTED,
    DocumentStatus.AI_PROCESSING,
    DocumentStatus.METADATA_EXTRACTED,
    DocumentStatus.NORMALIZING,
    DocumentStatus.NORMALIZED,
    DocumentStatus.VALIDATING,
    DocumentStatus.VALIDATED,
    DocumentStatus.NEEDS_REVIEW,
    DocumentStatus.APPROVED,
    DocumentStatus.DEPOSITING,
    DocumentStatus.DEPOSITED,
]

# Estados previos al deposito que pueden volver a revision (reextraccion).
REVIEWABLE_STATES = {
    DocumentStatus.UPLOADED,
    DocumentStatus.TEXT_EXTRACTED,
    DocumentStatus.METADATA_EXTRACTED,
    DocumentStatus.NORMALIZED,
    DocumentStatus.VALIDATED,
    DocumentStatus.VALIDATION_FAILED,
    DocumentStatus.NEEDS_REVIEW,
    DocumentStatus.REJECTED,
}

# Un documento en estas etapas no puede editarse (en curso de procesamiento).
EDIT_LOCKED_STATES = {
    DocumentStatus.ANALYZING,
    DocumentStatus.OCR_PROCESSING,
    DocumentStatus.AI_PROCESSING,
    DocumentStatus.NORMALIZING,
    DocumentStatus.VALIDATING,
    DocumentStatus.DEPOSITING,
    DocumentStatus.DEPOSITED,
}

ERROR_RETRYABLE_STATES = {
    DocumentStatus.UPLOADED,
    DocumentStatus.TEXT_EXTRACTED,
    DocumentStatus.METADATA_EXTRACTED,
    DocumentStatus.NORMALIZED,
    DocumentStatus.VALIDATED,
    DocumentStatus.NEEDS_REVIEW,
    DocumentStatus.APPROVED,
}


def can_transition(current: str, next_state: str) -> bool:
    """Chequeo de transiciones explicitas; devuelve False si no esta permitido."""
    if next_state == DocumentStatus.ERROR:
        return current not in {
            DocumentStatus.DEPOSITED,
            DocumentStatus.REJECTED,
        }
    if next_state == DocumentStatus.REJECTED:
        return current in REVIEWABLE_STATES or current == DocumentStatus.APPROVED
    if current == DocumentStatus.ERROR:
        return next_state in ERROR_RETRYABLE_STATES
    # Prohibir retrocesos salvo hacia revision / reproceso.
    allowed: set[str] = {
        DocumentStatus.NEEDS_REVIEW,
        DocumentStatus.REJECTED,
        DocumentStatus.APPROVED,
    }
    if next_state == DocumentStatus.NEEDS_REVIEW and current in REVIEWABLE_STATES:
        return True
    if next_state == DocumentStatus.APPROVED and current in (
        REVIEWABLE_STATES | {DocumentStatus.ERROR}
    ):
        return True
    if next_state in allowed or current in allowed:
        return current != next_state
    if current not in AUTO_SEQUENCE or next_state not in AUTO_SEQUENCE:
        return True
    return AUTO_SEQUENCE.index(current) < AUTO_SEQUENCE.index(next_state)


def set_document_status(
    db: Session,
    document: Document,
    new_status: str,
    *,
    user: User | None = None,
    message: str | None = None,
    action: str = "document.status",
) -> Document:
    """Cambia el estado de un documento y lo audita. Devuelve el documento."""
    previous = document.status or DocumentStatus.UPLOADED
    if previous != new_status:
        audit_log(
            db,
            user=user,
            action=action,
            entity_type="document",
            entity_id=str(document.id),
            old_value={"status": previous},
            new_value={"status": new_status, "message": message},
        )
        document.status = new_status
    return document


def throttle_seconds(seconds: float) -> float:
    """Pequeño helper para evitar import circular de ``time`` en los modulos."""
    time.sleep(seconds)
    return seconds