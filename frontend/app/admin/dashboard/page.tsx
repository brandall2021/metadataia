"use client";

import { useEffect, useState } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiFetch } from "@/lib/api";

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
    <Card>
      <CardHeader className="pb-1">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {label}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
        {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
      </CardContent>
    </Card>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent>{children}</CardContent>
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
      <span className="w-10 text-right font-mono text-xs text-muted-foreground">
        {label}
      </span>
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

export default function DashboardPage() {
  const [data, setData] = useState<DashboardOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<DashboardOut>("/api/admin/dashboard")
      .then(setData)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Error al cargar el dashboard"),
      );
  }, []);

  if (error) return <p className="text-sm text-destructive">{error}</p>;
  if (!data) return <p className="text-sm text-muted-foreground">Cargando estadísticas…</p>;

  const { documentos, procesamiento, ia, depositos, tendencia_7d } = data;
  const maxTendencia = Math.max(1, ...tendencia_7d.map((d) => d.documentos));
  const estPend = ["NORMALIZED", "METADATA_EXTRACTED", "VALIDATED", "PROCESSING", "UPLOADED"];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-sm text-muted-foreground">
          Estado general del sistema: documentos, procesamiento, extracción IA y
          depósitos.
        </p>
      </div>

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
            <p className="mt-3 text-xs text-destructive">
              Errores:{" "}
              {Object.entries(procesamiento.errores_por_tipo)
                .map(([tipo, n]) => `${fmtTipo(tipo)}: ${n}`)
                .join(" · ")}
            </p>
          )}
        </Section>

        <Section title="Extracción IA">
          <div className="grid grid-cols-2 gap-3 text-sm md:grid-cols-4">
            <Stat label="Ejecuciones" value={fmtNum(ia.ejecuciones)} />
            <Stat label="Exitosas" value={fmtNum(ia.ok)} />
            <Stat label="Errores" value={fmtNum(ia.errores)} />
            <Stat label="Tiempo prom." value={ia.tiempo_promedio_ms ? `${fmtNum(ia.tiempo_promedio_ms)} ms` : "—"} />
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
                <span
                  key={estado}
                  className="rounded-full border px-3 py-1 text-xs"
                >
                  {ESTADOS[estado] ?? estado}: <b>{n}</b>
                </span>
              ))}
          </div>
        </Section>
      </div>

      <Section title="Documentos por día (últimos 7 días)">
        <div className="space-y-2">
          {tendencia_7d.map((d) => (
            <BarRow key={d.fecha} fecha={d.fecha} count={d.documentos} max={maxTendencia} />
          ))}
        </div>
      </Section>
    </div>
  );
}