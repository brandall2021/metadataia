"""Dashboard de estadisticas (FASE 15).

``GET /api/admin/dashboard`` agrega todo el estado del sistema (spec 30):
documentos por estado, procesamiento (OCR, extracciones IA, tiempos,
errores), extraccion IA (tokens, errores por agente y por modelo) y
depositos. Disponible para quien tenga el permiso ``dashboard.view``.
"""

from collections import Counter
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.dashboard.schemas import (
    DashboardOut,
    DepositosStats,
    DocumentosStats,
    ErrorPorAgente,
    ErrorPorModelo,
    IaStats,
    ProcesamientoStats,
    TendenciaDia,
)
from app.models import (
    AIAgent,
    AIModel,
    Deposition,
    Document,
    ExtractionRun,
    ProcessingJob,
    Repository,
    User,
)

router = APIRouter(prefix="/admin/dashboard", tags=["dashboard"])

can_view_dashboard = require_permission("dashboard.view")

PROCESSED_STATES = "PROCESSING", "METADATA_EXTRACTED", "NEEDS_REVIEW", "VALIDATED", "APPROVED", "REJECTED", "DEPOSITED"


def _ms_stats(rows) -> dict:
    """rows: (key, avg_seconds) desde una consulta agrupada; devuelve ms por key."""
    out = {}
    for key, avg in rows:
        if avg is not None:
            out[key] = round(float(avg) * 1000, 1)
    return out


@router.get("", response_model=DashboardOut)
def dashboard(db: Session = Depends(get_db), _: User = Depends(can_view_dashboard)) -> DashboardOut:
    # --- documentos -------------------------------------------------------
    by_state = dict(
        db.query(Document.status, func.count(Document.id)).group_by(Document.status).all()
    )
    total_docs = sum(by_state.values())
    processed = sum(n for s, n in by_state.items() if s in PROCESSED_STATES)

    # --- jobs (procesamiento) --------------------------------------------
    jobs_by_type_status = (
        db.query(ProcessingJob.job_type, ProcessingJob.status, func.count(ProcessingJob.id))
        .group_by(ProcessingJob.job_type, ProcessingJob.status)
        .all()
    )
    ocr_done = sum(n for t, s, n in jobs_by_type_status if t == "OCR" and s == "COMPLETED")
    extract_done = sum(n for t, s, n in jobs_by_type_status if t == "EXTRACTION" and s == "COMPLETED")
    norm_done = sum(n for t, s, n in jobs_by_type_status if t == "NORMALIZATION" and s == "COMPLETED")
    valid_done = sum(n for t, s, n in jobs_by_type_status if t == "VALIDATION" and s == "COMPLETED")
    jobs_errors = sum(n for _, s, n in jobs_by_type_status if s == "ERROR")
    errors_by_type: Counter[str] = Counter()
    jobs_by_state: Counter[str] = Counter()
    for job_type, status, n in jobs_by_type_status:
        jobs_by_state[status] += n
        if status == "ERROR":
            errors_by_type[job_type] += n

    diff = func.extract("epoch", ProcessingJob.finished_at - ProcessingJob.started_at)
    avg_all = db.query(func.avg(diff)).filter(
        ProcessingJob.status == "COMPLETED",
        ProcessingJob.started_at.isnot(None),
        ProcessingJob.finished_at.isnot(None),
    ).scalar()
    avg_by_type = _ms_stats(
        db.query(ProcessingJob.job_type, func.avg(diff))
        .filter(
            ProcessingJob.status == "COMPLETED",
            ProcessingJob.started_at.isnot(None),
            ProcessingJob.finished_at.isnot(None),
        )
        .group_by(ProcessingJob.job_type)
        .all()
    )

    # --- extraccion IA ----------------------------------------------------
    runs_total = db.query(func.count(ExtractionRun.id)).scalar() or 0
    runs_ok = (
        db.query(func.count(ExtractionRun.id))
        .filter(ExtractionRun.status == "COMPLETED")
        .scalar()
        or 0
    )
    runs_err = (
        db.query(func.count(ExtractionRun.id)).filter(ExtractionRun.status == "ERROR").scalar() or 0
    )
    avg_tokens_in = db.query(func.avg(ExtractionRun.input_tokens)).filter(
        ExtractionRun.input_tokens.isnot(None)
    ).scalar()
    avg_tokens_out = db.query(func.avg(ExtractionRun.output_tokens)).filter(
        ExtractionRun.output_tokens.isnot(None)
    ).scalar()
    avg_run_ms = db.query(func.avg(func.extract("epoch", ExtractionRun.finished_at - ExtractionRun.started_at))).filter(
        ExtractionRun.started_at.isnot(None),
        ExtractionRun.finished_at.isnot(None),
    ).scalar()
    avg_run_ms = round(float(avg_run_ms) * 1000, 1) if avg_run_ms is not None else None

    # errores por agente
    agent_rows = (
        db.query(ExtractionRun.agent_id, ExtractionRun.status, func.count(ExtractionRun.id))
        .group_by(ExtractionRun.agent_id, ExtractionRun.status)
        .all()
    )
    agent_names = {
        a.id: a.code
        for a in db.query(AIAgent).filter(
            AIAgent.id.in_([r[0] for r in agent_rows if r[0] is not None])
        ).all()
    }
    agg_by_agent: dict = {}
    for agent_id, status, n in agent_rows:
        key = agent_id or "NULL"
        bucket = agg_by_agent.setdefault(
            key, {"ejecuciones": 0, "errores": 0}
        )
        bucket["ejecuciones"] += n
        if status == "ERROR":
            bucket["errores"] += n
    errores_por_agente = [
        ErrorPorAgente(
            agente=agent_names.get(aid) if aid != "NULL" else None,
            ejecuciones=v["ejecuciones"],
            errores=v["errores"],
        )
        for aid, v in sorted(agg_by_agent.items(), key=lambda kv: -kv[1]["errores"])
    ]

    # errores por modelo
    model_rows = (
        db.query(ExtractionRun.model_id, ExtractionRun.status, func.count(ExtractionRun.id))
        .group_by(ExtractionRun.model_id, ExtractionRun.status)
        .all()
    )
    model_names = {
        m.id: m.model_identifier
        for m in db.query(AIModel).filter(
            AIModel.id.in_([r[0] for r in model_rows if r[0] is not None])
        ).all()
    }
    agg_by_model: dict = {}
    for model_id, status, n in model_rows:
        key = model_id or "NULL"
        bucket = agg_by_model.setdefault(key, {"ejecuciones": 0, "errores": 0})
        bucket["ejecuciones"] += n
        if status == "ERROR":
            bucket["errores"] += n
    errores_por_modelo = [
        ErrorPorModelo(
            modelo=model_names.get(mid) if mid != "NULL" else None,
            ejecuciones=v["ejecuciones"],
            errores=v["errores"],
        )
        for mid, v in sorted(agg_by_model.items(), key=lambda kv: -kv[1]["errores"])
    ]

    # --- depositos --------------------------------------------------------
    dep_rows = dict(
        db.query(Deposition.status, func.count(Deposition.id)).group_by(Deposition.status).all()
    )
    depositos = DepositosStats(
        total=sum(dep_rows.values()),
        completados=dep_rows.get("COMPLETED", 0),
        fallidos=dep_rows.get("ERROR", 0),
        pendientes=dep_rows.get("PENDING", 0),
    )

    # --- tendencia ultimos 7 dias ----------------------------------------
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=6)
    daily = dict(
        db.query(
            func.date(Document.created_at), func.count(Document.id)
        )
        .filter(Document.created_at >= datetime.combine(start, datetime.min.time()))
        .group_by(func.date(Document.created_at))
        .all()
    )
    tendencia = [
        TendenciaDia(fecha=(start + timedelta(days=i)).isoformat(), documentos=daily.get(start + timedelta(days=i), 0))
        for i in range(7)
    ]

    usuarios = db.query(func.count(User.id)).scalar() or 0
    repositorios = db.query(func.count(Repository.id)).scalar() or 0

    return DashboardOut(
        documentos=DocumentosStats(
            total=total_docs,
            procesados=processed,
            pendientes_revision=by_state.get("NEEDS_REVIEW", 0),
            aprobados=by_state.get("APPROVED", 0),
            rechazados=by_state.get("REJECTED", 0),
            depositados=by_state.get("DEPOSITED", 0),
            por_estado=by_state,
        ),
        procesamiento=ProcesamientoStats(
            ocr_ejecutados=ocr_done,
            extracciones_ia=extract_done,
            normalizaciones=norm_done,
            validaciones=valid_done,
            tiempo_promedio_ms=round(float(avg_all) * 1000, 1) if avg_all is not None else None,
            tiempo_promedio_por_tipo=avg_by_type,
            errores=jobs_errors,
            errores_por_tipo=dict(errors_by_type),
            jobs_por_estado=dict(jobs_by_state),
        ),
        ia=IaStats(
            ejecuciones=runs_total,
            ok=runs_ok,
            errores=runs_err,
            tokens_promedio={
                "input": round(float(avg_tokens_in), 1) if avg_tokens_in is not None else None,
                "output": round(float(avg_tokens_out), 1) if avg_tokens_out is not None else None,
            },
            tiempo_promedio_ms=avg_run_ms,
            errores_por_agente=errores_por_agente,
            errores_por_modelo=errores_por_modelo,
        ),
        depositos=depositos,
        tendencia_7d=tendencia,
        usuarios=usuarios,
        repositorios=repositorios,
    )