"use client";

import { useEffect, useState } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiFetch } from "@/lib/api";
import { Activity, ArrowRight, Database, FileText, Gauge, Shield, Sparkles, Users } from "lucide-react";

type DashboardOut = {
  documentos: {
    total: number;
    procesados: number;
    pendientes_revision: number;
    aprobados: number;
    rechazados: number;
    depositados: number;
    por_estado: Record<string, number>;
  };
  procesamiento: {
    ocr_ejecutados: number;
    extracciones_ia: number;
    normalizaciones: number;
    validaciones: number;
    tiempo_promedio_ms: number | null;
    tiempo_promedio_por_tipo: Record<string, number>;
    errores: number;
    errores_por_tipo: Record<string, number>;
    jobs_por_estado: Record<string, number>;
  };
  ia: {
    ejecuciones: number;
    ok: number;
    errores: number;
    tokens_promedio: { input: number | null; output: number | null };
    tiempo_promedio_ms: number | null;
    errores_por_agente: { agente: string | null; ejecuciones: number; errores: number }[];
    errores_por_modelo: { modelo: string | null; ejecuciones: number; errores: number }[];
  };
  depositos: { total: number; completados: number; fallidos: number; pendientes: number };
  tendencia_7d: { fecha: string; documentos: number }[];
  usuarios: number;
  repositorios: number;
};

const ESTADOS: Record<string, string> = {
  UPLOADED: "Subidos",
  PROCESSING: "Procesando",
  METADATA_EXTRACTED: "Extraídos",
  NORMALIZED: "Normalizados",
  NEEDS_REVIEW: "Requieren revisión",
  VALIDATED: "Validados",
  APPROVED: "Aprobados",
  REJECTED: "Rechazados",
  DEPOSITED: "Depositados",
};

function Stat({
  label,
  value,
  hint,
}: {
  label: string;
  value: number | string;
  hint?: string;
}) {
  return (
    <Card className="border-border/70 shadow-sm">
      <CardHeader className="pb-1">
        <CardTitle className="text-sm font-medium text-muted-foreground">{label}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold tracking-tight">{value}</div>
        {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
      </CardContent>
    </Card>
  );
}

function MiniStat({ label, value, icon: Icon }: { label: string; value: string; icon: typeof Gauge }) {
  return (
    <div className="rounded-2xl border border-border/70 bg-background/80 px-4 py-3 shadow-sm backdrop-blur">
      <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.22em] text-muted-foreground">
        <Icon className="size-3.5" />
        {label}
      </div>
      <div className="mt-2 text-xl font-semibold tracking-tight">{value}</div>
    </div>
  );
}

function SignalPill({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-border/70 bg-muted/25 px-3 py-2.5 shadow-sm">
      <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">{label}</div>
      <div className="mt-1 text-sm font-medium text-foreground">{value}</div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card className="overflow-hidden rounded-[1.75rem] border-border/70 shadow-sm">
      <CardHeader className="border-b border-border/60 bg-muted/20">
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent className="p-4">{children}</CardContent>
    </Card>
  );
}

function BarRow({ fecha, count, max }: { fecha: string; count: number; max: number }) {
  const label = new Date(fecha + "T00:00:00").toLocaleDateString("es-AR", {
    day: "2-digit",
    month: "2-digit",
  });
  return (
    <div className="flex items-center gap-3">
      <span className="w-10 text-right font-mono text-xs text-muted-foreground">{label}</span>
      <div className="h-5 flex-1 overflow-hidden rounded bg-muted">
        <div
          className="h-full rounded bg-primary/80"
          style={{ width: `${max === 0 ? 0 : Math.max(4, (count / max) * 100)}%` }}
        />
      </div>
      <span className="w-8 font-mono text-xs">{count}</span>
    </div>
  );
}

const fmtNum = (n: number | null | undefined): string =>
  n === null || n === undefined ? "—" : n.toLocaleString("es-AR");

const fmtTipo = (t: string): string =>
  ({
    OCR: "OCR",
    EXTRACTION: "Extracción IA",
    NORMALIZATION: "Normalización",
    VALIDATION: "Validación",
    DEPOSIT: "Depósito",
  })[t] ?? t;

const fmtJobEstado = (t: string): string =>
  ({
    PENDING: "Pendiente",
    RUNNING: "En curso",
    COMPLETED: "Completado",
    FAILED: "Fallido",
    CANCELLED: "Cancelado",
  })[t] ?? t;

export default function DashboardPage() {
  const [data, setData] = useState<DashboardOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<DashboardOut>("/api/admin/dashboard")
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : "Error al cargar el dashboard"));
  }, []);

  if (error) return <p className="text-sm text-destructive">{error}</p>;
  if (!data) return <p className="text-sm text-muted-foreground">Cargando estadísticas…</p>;

  const { documentos, procesamiento, ia, depositos, tendencia_7d } = data;
  const maxTendencia = Math.max(1, ...tendencia_7d.map((d) => d.documentos));
  const estPend = ["NORMALIZED", "METADATA_EXTRACTED", "VALIDATED", "PROCESSING", "UPLOADED"];
  const topDay = tendencia_7d.reduce(
    (acc, curr) => (curr.documentos > acc.documentos ? curr : acc),
    tendencia_7d[0] ?? { fecha: "", documentos: 0 },
  );
  const avgTiming = ia.tiempo_promedio_ms ?? procesamiento.tiempo_promedio_ms;

  return (
    <div className="space-y-6">
      <section className="overflow-hidden rounded-[2rem] border border-border/70 bg-gradient-to-br from-primary/[0.08] via-background to-muted/50 p-6 shadow-[0_24px_90px_-60px_rgba(15,23,42,0.45)]">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="space-y-3">
            <span className="inline-flex items-center gap-2 rounded-full border border-primary/15 bg-primary/10 px-3 py-1 text-[11px] uppercase tracking-[0.22em] text-primary">
              <Activity className="size-3.5" />
              Dashboard operativo
            </span>
            <div className="space-y-2">
              <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">Dashboard</h1>
              <p className="max-w-2xl text-sm leading-6 text-muted-foreground">
                Estado general del sistema: documentos, procesamiento, extracción IA y depósitos.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              <span className="inline-flex items-center gap-1.5 rounded-full border border-border/70 bg-background/70 px-3 py-1 shadow-sm">
                <Shield className="size-3.5" />
                Sistema estable
              </span>
              <span className="inline-flex items-center gap-1.5 rounded-full border border-border/70 bg-background/70 px-3 py-1 shadow-sm">
                <ArrowRight className="size-3.5" />
                Vista resumen
              </span>
            </div>
          </div>

          <div className="grid gap-3 sm:min-w-[360px] lg:w-[420px]">
            <div className="grid grid-cols-2 gap-3">
              <MiniStat label="Documentos" value={fmtNum(documentos.total)} icon={FileText} />
              <MiniStat label="Usuarios" value={fmtNum(data.usuarios)} icon={Users} />
              <MiniStat label="Repositorios" value={fmtNum(data.repositorios)} icon={Database} />
              <MiniStat label="IA" value={fmtNum(ia.ejecuciones)} icon={Sparkles} />
            </div>
            <div className="rounded-2xl border border-border/70 bg-background/80 p-4 shadow-sm backdrop-blur">
              <div className="flex items-center justify-between gap-3">
                <p className="text-[11px] uppercase tracking-[0.22em] text-muted-foreground">Centro de control</p>
                <span className="rounded-full bg-emerald-500/15 px-2.5 py-1 text-[11px] font-medium text-emerald-600 dark:text-emerald-300">
                  Activo
                </span>
              </div>
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                <SignalPill label="Pendientes" value={fmtNum(documentos.pendientes_revision)} />
                <SignalPill label="Depositados" value={fmtNum(documentos.depositados)} />
              </div>
            </div>
          </div>
        </div>
      </section>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Stat label="Documentos totales" value={fmtNum(documentos.total)} />
        <Stat label="Procesados" value={fmtNum(documentos.procesados)} hint="con metadatos IA aplicados" />
        <Stat label="Depositados" value={fmtNum(documentos.depositados)} />
        <Stat label="En revisión" value={fmtNum(documentos.pendientes_revision)} />
        <Stat label="Aprobados" value={fmtNum(documentos.aprobados)} />
        <Stat label="Rechazados" value={fmtNum(documentos.rechazados)} />
        <Stat label="Usuarios" value={fmtNum(data.usuarios)} />
        <Stat label="Repositorios" value={fmtNum(data.repositorios)} />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Section title="Procesamiento">
          <div className="grid grid-cols-2 gap-3 text-sm md:grid-cols-4">
            <Stat label="OCR" value={fmtNum(procesamiento.ocr_ejecutados)} />
            <Stat label="Extracciones IA" value={fmtNum(procesamiento.extracciones_ia)} />
            <Stat label="Normalizaciones" value={fmtNum(procesamiento.normalizaciones)} />
            <Stat label="Validaciones" value={fmtNum(procesamiento.validaciones)} />
          </div>
          <dl className="mt-4 grid grid-cols-1 gap-2 text-sm md:grid-cols-2">
            <div className="flex justify-between rounded-lg bg-muted/50 px-3 py-2">
              <dt>Tiempo promedio</dt>
              <dd className="font-mono">{fmtNum(procesamiento.tiempo_promedio_ms)} ms</dd>
            </div>
            <div className="flex justify-between rounded-lg bg-muted/50 px-3 py-2">
              <dt>Errores de jobs</dt>
              <dd className="font-mono">{fmtNum(procesamiento.errores)}</dd>
            </div>
          </dl>
          {Object.keys(procesamiento.tiempo_promedio_por_tipo).length > 0 && (
            <table className="mt-3 w-full text-sm">
              <tbody>
                {Object.entries(procesamiento.tiempo_promedio_por_tipo).map(([tipo, ms]) => (
                  <tr key={tipo} className="border-t">
                    <td className="py-1.5">{fmtTipo(tipo)}</td>
                    <td className="py-1.5 text-right font-mono">{fmtNum(ms)} ms</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {Object.keys(procesamiento.errores_por_tipo).length > 0 && (
            <div className="mt-3 rounded-2xl border border-destructive/20 bg-destructive/5 px-3 py-2 text-xs text-destructive">
              Errores: {Object.entries(procesamiento.errores_por_tipo)
                .map(([tipo, n]) => `${fmtTipo(tipo)}: ${n}`)
                .join(" · ")}
            </div>
          )}
          {Object.keys(procesamiento.jobs_por_estado).length > 0 && (
            <div className="mt-4 border-t border-border/60 pt-4">
              <p className="text-xs uppercase tracking-[0.22em] text-muted-foreground">Jobs por estado</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {Object.entries(procesamiento.jobs_por_estado).map(([estado, n]) => (
                  <span key={estado} className="rounded-full border border-border/70 bg-background px-3 py-1 text-xs">
                    {fmtJobEstado(estado)}: <b>{n}</b>
                  </span>
                ))}
              </div>
            </div>
          )}
        </Section>

        <Section title="Extracción IA">
          <div className="grid grid-cols-2 gap-3 text-sm md:grid-cols-4">
            <Stat label="Ejecuciones" value={fmtNum(ia.ejecuciones)} />
            <Stat label="Exitosas" value={fmtNum(ia.ok)} />
            <Stat label="Errores" value={fmtNum(ia.errores)} />
            <Stat label="Tiempo prom." value={avgTiming === null ? "—" : `${fmtNum(avgTiming)} ms`} />
          </div>
          <dl className="mt-4 grid grid-cols-1 gap-2 text-sm md:grid-cols-2">
            <div className="flex justify-between rounded-lg bg-muted/50 px-3 py-2">
              <dt>Tokens promedio</dt>
              <dd className="font-mono">
                in {fmtNum(ia.tokens_promedio.input)} · out {fmtNum(ia.tokens_promedio.output)}
              </dd>
            </div>
            <div className="flex justify-between rounded-lg bg-muted/50 px-3 py-2">
              <dt>Faltas por agente/modelo</dt>
              <dd className="font-mono">↓</dd>
            </div>
          </dl>
          <table className="mt-3 w-full text-sm">
            <thead className="text-left text-xs text-muted-foreground">
              <tr>
                <th className="py-1">Agente</th>
                <th className="py-1 text-right">Ejecuciones</th>
                <th className="py-1 text-right">Errores</th>
              </tr>
            </thead>
            <tbody>
              {ia.errores_por_agente.map((a, i) => (
                <tr key={i} className="border-t">
                  <td className="py-1 font-mono text-xs">{a.agente ?? "sin agente"}</td>
                  <td className="py-1 text-right font-mono">{a.ejecuciones}</td>
                  <td className="py-1 text-right font-mono">{a.errores}</td>
                </tr>
              ))}
              {ia.errores_por_agente.length === 0 && (
                <tr>
                  <td colSpan={3} className="py-3 text-center text-muted-foreground">
                    Sin ejecuciones registradas.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
          <table className="mt-3 w-full text-sm">
            <thead className="text-left text-xs text-muted-foreground">
              <tr>
                <th className="py-1">Modelo</th>
                <th className="py-1 text-right">Ejecuciones</th>
                <th className="py-1 text-right">Errores</th>
              </tr>
            </thead>
            <tbody>
              {ia.errores_por_modelo.map((m, i) => (
                <tr key={i} className="border-t">
                  <td className="py-1 font-mono text-xs">{m.modelo ?? "sin modelo"}</td>
                  <td className="py-1 text-right font-mono">{m.ejecuciones}</td>
                  <td className="py-1 text-right font-mono">{m.errores}</td>
                </tr>
              ))}
              {ia.errores_por_modelo.length === 0 && (
                <tr>
                  <td colSpan={3} className="py-3 text-center text-muted-foreground">
                    Sin ejecuciones registradas.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </Section>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Section title="Depósitos">
          <div className="grid grid-cols-2 gap-3 text-sm md:grid-cols-4">
            <Stat label="Total" value={fmtNum(depositos.total)} />
            <Stat label="Completados" value={fmtNum(depositos.completados)} />
            <Stat label="Fallidos" value={fmtNum(depositos.fallidos)} />
            <Stat label="Pendientes" value={fmtNum(depositos.pendientes)} />
          </div>
        </Section>

        <Section title="Documentos por estado">
          <div className="flex flex-wrap gap-2">
            {Object.entries(documentos.por_estado)
              .sort(([a], [b]) => estPend.indexOf(a) - estPend.indexOf(b))
              .map(([estado, n]) => (
                <span key={estado} className="rounded-full border px-3 py-1 text-xs">
                  {ESTADOS[estado] ?? estado}: <b>{n}</b>
                </span>
              ))}
          </div>
        </Section>
      </div>

      <Section title="Documentos por día (últimos 7 días)">
        <div className="space-y-2">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2 text-sm text-muted-foreground">
            <span>Máximo diario: {fmtNum(maxTendencia)} documentos</span>
            <span>
              Mayor día: {topDay.fecha ? new Date(topDay.fecha + "T00:00:00").toLocaleDateString("es-AR") : "—"}
            </span>
          </div>
          {tendencia_7d.map((d) => (
            <BarRow key={d.fecha} fecha={d.fecha} count={d.documentos} max={maxTendencia} />
          ))}
        </div>
      </Section>
    </div>
  );
}
