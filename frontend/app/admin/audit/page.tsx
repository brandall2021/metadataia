"use client";

import { useEffect, useState } from "react";
import { Activity, ArrowLeft, ArrowRight, Filter, Shield } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { apiFetch } from "@/lib/api";

const ACTIONS = [
  "auth.login",
  "document.upload",
  "document.delete",
  "ocr.request",
  "ocr.completed",
  "ai.extraction",
  "ai.extraction.failed",
  "metadata.normalize",
  "document.validate",
  "record.create",
  "record.update",
  "record.delete",
  "document.approve",
  "document.reject",
  "deposit.request",
  "deposit.completed",
  "deposit.failed",
  "repository.create",
  "repository.update",
  "repository.delete",
  "repository.sync",
  "collection.update",
  "collection.delete",
];

type AuditLogOut = {
  id: string;
  user_id: string | null;
  username: string | null;
  action: string;
  entity_type: string | null;
  entity_id: string | null;
  old_value: Record<string, unknown> | null;
  new_value: Record<string, unknown> | null;
  ip_address: string | null;
  user_agent: string | null;
  created_at: string;
};

type AuditCollectionOut = {
  items: AuditLogOut[];
  total: number;
  limit: number;
  offset: number;
};

const LIMIT = 25;

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-border/70 bg-background/80 px-4 py-3 shadow-sm backdrop-blur">
      <div className="text-[11px] uppercase tracking-[0.22em] text-muted-foreground">{label}</div>
      <div className="mt-2 text-xl font-semibold tracking-tight">{value}</div>
    </div>
  );
}

function Badge({ children }: { children: string }) {
  return (
    <span className="rounded-full bg-muted px-2.5 py-1 text-[11px] font-medium text-muted-foreground">
      {children}
    </span>
  );
}

function fmt(ts: string): string {
  return new Date(ts).toLocaleString("es-AR");
}

function summary(v: Record<string, unknown> | null): string {
  if (!v) return "—";
  const keys = Object.keys(v);
  if (keys.length === 0) return "—";
  return keys
    .map((k) => `${k}: ${JSON.stringify(v[k])}`)
    .join(" · ")
    .slice(0, 160);
}

export default function AuditPage() {
  const [data, setData] = useState<AuditCollectionOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [action, setAction] = useState("");
  const [entityId, setEntityId] = useState("");
  const [offset, setOffset] = useState(0);
  const total = data?.total ?? 0;
  const current = data?.items.length ?? 0;
  const entityFilterActive = Boolean(entityId.trim());

  async function load(nextOffset: number) {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        limit: String(LIMIT),
        offset: String(nextOffset),
      });
      if (action) params.set("action", action);
      if (entityId.trim()) params.set("entity_id", entityId.trim());
      const res = await apiFetch<AuditCollectionOut>(
        `/api/admin/audit?${params.toString()}`,
      );
      setData(res);
      setOffset(nextOffset);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al cargar auditoría");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load(0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="space-y-6">
      <section className="overflow-hidden rounded-[2rem] border border-border/70 bg-gradient-to-br from-primary/[0.08] via-background to-muted/50 p-6 shadow-[0_24px_90px_-60px_rgba(15,23,42,0.45)]">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="space-y-3">
            <span className="inline-flex items-center gap-2 rounded-full border border-primary/15 bg-primary/10 px-3 py-1 text-[11px] uppercase tracking-[0.22em] text-primary">
              <Shield className="size-3.5" />
              Auditoría
            </span>
            <div className="space-y-2">
              <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">Auditoría</h1>
              <p className="max-w-2xl text-sm leading-6 text-muted-foreground">
                Registro de todas las operaciones: login, subida/borrado de documentos, extracción IA, cambios humanos, aprobaciones y depósitos.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge>Eventos</Badge>
              <Badge>Filtros</Badge>
              <Badge>Entidad</Badge>
              <Badge>Detalle</Badge>
            </div>
          </div>
          <div className="grid gap-3 sm:min-w-[360px] lg:w-[420px]">
            <div className="grid grid-cols-2 gap-3">
              <MiniStat label="Registros" value={String(total || 0)} />
              <MiniStat label="Página" value={String(current)} />
            </div>
            <div className="rounded-2xl border border-border/70 bg-background/80 p-4 shadow-sm backdrop-blur">
              <div className="flex items-center justify-between gap-3">
                <p className="text-[11px] uppercase tracking-[0.22em] text-muted-foreground">Centro de control</p>
                <span className="rounded-full bg-emerald-500/15 px-2.5 py-1 text-[11px] font-medium text-emerald-600 dark:text-emerald-300">
                  {entityFilterActive ? "Filtrado" : "Completo"}
                </span>
              </div>
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                <MiniStat label="Offset" value={String(offset)} />
                <MiniStat label="Límite" value={String(LIMIT)} />
              </div>
            </div>
          </div>
        </div>
      </section>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <Card className="overflow-hidden rounded-[1.75rem] border-border/70 shadow-sm">
        <CardHeader className="border-b border-border/60 bg-muted/20">
          <CardTitle className="flex items-center gap-2">
            <Filter className="size-4" />
            Filtros
          </CardTitle>
          <CardDescription>
            Filtre por acción y por ID de documento/entidad. Solo visible para
            administradores.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap items-end gap-3 p-6 text-sm">
          <label className="flex flex-col gap-1">
            Acción
            <select
              className="rounded-lg border border-border bg-background px-3 py-2"
              value={action}
              onChange={(e) => setAction(e.target.value)}
            >
              <option value="">Todas</option>
              {ACTIONS.map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            ID de entidad
            <input
              className="rounded-lg border border-border bg-background px-3 py-2"
              value={entityId}
              onChange={(e) => setEntityId(e.target.value)}
              placeholder="uuid del documento/repositorio…"
            />
          </label>
          <Button onClick={() => load(0)} disabled={loading}>
            {loading ? "Cargando…" : "Filtrar"}
          </Button>
        </CardContent>
      </Card>

      {data && (
        <div className="overflow-hidden rounded-[1.75rem] border border-border/70 shadow-sm">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 text-left text-xs uppercase tracking-[0.16em] text-muted-foreground">
              <tr>
                <th className="px-3 py-2">Fecha</th>
                <th className="px-3 py-2">Usuario</th>
                <th className="px-3 py-2">Acción</th>
                <th className="px-3 py-2">Entidad</th>
                <th className="px-3 py-2">Detalle</th>
                <th className="px-3 py-2">IP</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((it) => (
                <tr key={it.id} className="border-t align-top transition-colors hover:bg-muted/30">
                  <td className="whitespace-nowrap px-3 py-2 text-xs">
                    {fmt(it.created_at)}
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex flex-col gap-1">
                      <span className="font-medium">{it.username ?? "sistema"}</span>
                      <span className="text-xs text-muted-foreground">{it.user_id ? it.user_id.slice(0, 8) : "—"}</span>
                    </div>
                  </td>
                  <td className="whitespace-nowrap px-3 py-2">
                    <span className="rounded-full bg-primary/10 px-2.5 py-1 font-mono text-xs text-primary">
                      {it.action}
                    </span>
                  </td>
                  <td className="px-3 py-2 font-mono text-xs">
                    {it.entity_type ? `${it.entity_type} ${(it.entity_id ?? "").slice(0, 8)}` : "—"}
                  </td>
                  <td className="px-3 py-2 text-xs text-muted-foreground">
                    {it.new_value &&
                      it.old_value &&
                      Object.keys(it.new_value).some(
                        (k) =>
                          it.old_value &&
                          JSON.stringify(it.old_value[k]) !== JSON.stringify(it.new_value?.[k]),
                      )
                      ? `anterior: ${summary(it.old_value)}`
                      : summary(it.new_value)}
                  </td>
                  <td className="px-3 py-2 font-mono text-xs">{it.ip_address ?? "—"}</td>
                </tr>
              ))}
              {data.items.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-3 py-8 text-center text-muted-foreground">
                    Sin registros para los filtros seleccionados.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {data && data.total > LIMIT && (
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">
            {data.total} registros · mostrando {offset + 1}–{Math.min(offset + LIMIT, data.total)}
          </span>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={offset === 0}
              onClick={() => load(Math.max(0, offset - LIMIT))}
              className="gap-2"
            >
              <ArrowLeft className="size-4" />
              Anterior
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={offset + LIMIT >= data.total}
              onClick={() => load(offset + LIMIT)}
              className="gap-2"
            >
              Siguiente
              <ArrowRight className="size-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
