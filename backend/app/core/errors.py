"""Codigos de error estandar (seccion 33 de la especificacion).

Todos los servicios deben lanzar errores con un ``code`` estable para que el
frontend y el dashboard puedan clasificar fallos (PDF_INVALID, AI_TIMEOUT, ...)
y mostrar mensajes entendibles al usuario.
"""

from typing import Any

from fastapi import HTTPException
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Error de dominio con codigo estandar.

    ``code`` es el identificador estable (p. ej. ``AI_TIMEOUT``); ``message`` es
    el mensaje entendible para el usuario y ``detail`` el detalle tecnico que se
    guarda en logs (nunca secretos).
    """

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 400,
        detail: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.detail = detail


# --- Codigos -------------------------------------------------------------

PDF_INVALID = "PDF_INVALID"
PDF_TOO_LARGE = "PDF_TOO_LARGE"
PDF_NOT_FOUND = "PDF_NOT_FOUND"
DUPLICATE_DOCUMENT = "DUPLICATE_DOCUMENT"
TEXT_EXTRACTION_ERROR = "TEXT_EXTRACTION_ERROR"
OCR_ERROR = "OCR_ERROR"
AI_CONNECTION_ERROR = "AI_CONNECTION_ERROR"
AI_TIMEOUT = "AI_TIMEOUT"
AI_INVALID_JSON = "AI_INVALID_JSON"
AI_SCHEMA_ERROR = "AI_SCHEMA_ERROR"
AI_ERROR = "AI_ERROR"
NO_AGENT_AVAILABLE = "NO_AGENT_AVAILABLE"
NO_TEXT_AVAILABLE = "NO_TEXT_AVAILABLE"
NORMALIZATION_ERROR = "NORMALIZATION_ERROR"
VALIDATION_ERROR = "VALIDATION_ERROR"
SNRD_VALIDATION_ERROR = "SNRD_VALIDATION_ERROR"
DSPACE_AUTH_ERROR = "DSPACE_AUTH_ERROR"
DSPACE_UPLOAD_ERROR = "DSPACE_UPLOAD_ERROR"
DSPACE_SUBMISSION_ERROR = "DSPACE_SUBMISSION_ERROR"
STORAGE_ERROR = "STORAGE_ERROR"
RATE_LIMITED = "RATE_LIMITED"
NOT_DEPOSITABLE = "NOT_DEPOSITABLE"
LOCKED_STATE = "LOCKED_STATE"

# Codigos "transitorios" que justifican reintento automatico (seccion 35).
RETRYABLE_CODES = {
    AI_TIMEOUT,
    AI_CONNECTION_ERROR,
    DSPACE_AUTH_ERROR,
    DSPACE_UPLOAD_ERROR,
    DSPACE_SUBMISSION_ERROR,
}


def app_error_handler(_request, exc: AppError):
    body: dict[str, Any] = {"code": exc.code, "message": exc.message}
    if exc.detail:
        body["detail"] = exc.detail
    return JSONResponse(status_code=exc.status_code, content=body)


def as_http_exception(exc: AppError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)