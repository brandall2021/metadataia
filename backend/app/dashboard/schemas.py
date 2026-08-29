"""Esquemas del dashboard de estadisticas (FASE 15)."""

from pydantic import BaseModel


class DocumentosStats(BaseModel):
    total: int
    procesados: int
    pendientes_revision: int
    aprobados: int
    rechazados: int
    depositados: int
    por_estado: dict[str, int]


class ProcesamientoStats(BaseModel):
    ocr_ejecutados: int
    extracciones_ia: int
    normalizaciones: int
    validaciones: int
    tiempo_promedio_ms: float | None = None
    tiempo_promedio_por_tipo: dict[str, float]
    errores: int
    errores_por_tipo: dict[str, int]
    jobs_por_estado: dict[str, int]


class ErrorPorAgente(BaseModel):
    agente: str | None = None
    ejecuciones: int
    errores: int


class ErrorPorModelo(BaseModel):
    modelo: str | None = None
    ejecuciones: int
    errores: int


class IaStats(BaseModel):
    ejecuciones: int
    ok: int
    errores: int
    tokens_promedio: dict[str, float | None]
    tiempo_promedio_ms: float | None = None
    errores_por_agente: list[ErrorPorAgente]
    errores_por_modelo: list[ErrorPorModelo]


class DepositosStats(BaseModel):
    total: int
    completados: int
    fallidos: int
    pendientes: int


class TendenciaDia(BaseModel):
    fecha: str
    documentos: int


class DashboardOut(BaseModel):
    documentos: DocumentosStats
    procesamiento: ProcesamientoStats
    ia: IaStats
    depositos: DepositosStats
    tendencia_7d: list[TendenciaDia]
    usuarios: int
    repositorios: int