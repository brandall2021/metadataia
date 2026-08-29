"use client";

import { useEffect, useState } from "react";

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
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Auditoría</h1>
        <p className="text-sm text-muted-foreground">
          Registro de todas las operaciones: login, subida/borrado de
          documentos, extracción IA, cambios humanos, aprobaciones y depósitos.
        </p>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <Card>
        <CardHeader>
          <CardTitle>Filtros</CardTitle>
          <CardDescription>
            Filtre por acción y por ID de documento/entidad. Solo visible para
            administradores.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap items-end gap-3 text-sm">
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
        <div className="overflow-hidden rounded-xl ring-1 ring-foreground/10">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 text-left text-xs text-muted-foreground">
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
                <tr key={it.id} className="border-t align-top">
                  <td className="whitespace-nowrap px-3 py-2 text-xs">
                    {fmt(it.created_at)}
                  </td>
                  <td className="px-3 py-2">{it.username ?? "sistema"}</td>
                  <td className="whitespace-nowrap px-3 py-2 font-mono text-xs">
                    {it.action}
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
            >
              Anterior
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={offset + LIMIT >= data.total}
              onClick={() => load(offset + LIMIT)}
            >
              Siguiente
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}