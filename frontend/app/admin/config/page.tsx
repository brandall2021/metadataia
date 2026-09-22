"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { apiFetch } from "@/lib/api";

type Setting = {
  key: string;
  value: unknown;
  description: string;
  section: string | null;
  source: string;
};

const inputCls =
  "w-full rounded-xl border border-border bg-muted/30 px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground/60 outline-none transition-colors focus:border-ring focus:bg-muted/50 focus:ring-2 focus:ring-ring/30";

function formatValue(value: unknown): string {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value ?? "", null, 2);
}

function parseValue(raw: string): unknown {
  const text = raw.trim();
  if (!text) return "";
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

export default function ConfigPage() {
  const [settings, setSettings] = useState<Setting[]>([]);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState<string | null>(null);

  async function load() {
    try {
      const data = await apiFetch<Setting[]>("/api/admin/settings");
      setSettings(data);
      setDrafts(Object.fromEntries(data.map((s) => [s.key, formatValue(s.value)])));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al cargar configuracion");
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function saveSetting(key: string) {
    setSaving(key);
    setError(null);
    try {
      await apiFetch(`/api/admin/settings/${key}`, {
        method: "PUT",
        body: JSON.stringify({ value: parseValue(drafts[key] ?? "") }),
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo guardar");
    } finally {
      setSaving(null);
    }
  }

  async function deleteSetting(key: string) {
    if (!window.confirm(`¿Eliminar el override de ${key}?`)) return;
    setSaving(key);
    setError(null);
    try {
      await apiFetch(`/api/admin/settings/${key}`, { method: "DELETE" });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo eliminar");
    } finally {
      setSaving(null);
    }
  }

  return (
    <div className="space-y-6">
      <section className="rounded-3xl border border-border/70 bg-gradient-to-br from-primary/[0.08] via-background to-muted/40 p-6 shadow-sm">
        <div className="space-y-2">
          <h1 className="text-3xl font-semibold tracking-tight">Configuración global</h1>
          <p className="max-w-2xl text-sm leading-6 text-muted-foreground">
            Ajustes administrables del sistema: OCR, IA, tamaños máximos y políticas generales.
          </p>
        </div>
      </section>

      {error && <p className="rounded-xl border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}

      <Card className="border-border/70 shadow-sm">
        <CardHeader className="space-y-2 border-b border-border/60 bg-muted/20">
          <CardTitle className="text-lg">Ajustes</CardTitle>
          <CardDescription>Los valores en DB tienen prioridad sobre las variables de entorno.</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <div className="divide-y divide-border/60">
            {settings.map((setting) => (
              <div key={setting.key} className="grid gap-4 p-4 xl:grid-cols-[260px_1fr_auto] xl:items-start">
                <div>
                  <p className="font-medium">{setting.key}</p>
                  <p className="mt-1 text-xs uppercase tracking-[0.18em] text-muted-foreground">{setting.source}</p>
                  <p className="mt-2 text-sm text-muted-foreground">{setting.description}</p>
                </div>
                <textarea
                  className={`${inputCls} min-h-24 font-mono text-xs`}
                  value={drafts[setting.key] ?? ""}
                  onChange={(e) => setDrafts({ ...drafts, [setting.key]: e.target.value })}
                />
                <div className="flex gap-2 xl:flex-col">
                  <Button size="sm" disabled={saving === setting.key} onClick={() => void saveSetting(setting.key)}>
                    {saving === setting.key ? "Guardando…" : "Guardar"}
                  </Button>
                  <Button variant="outline" size="sm" disabled={saving === setting.key || setting.source === "env"} onClick={() => void deleteSetting(setting.key)}>
                    Eliminar override
                  </Button>
                </div>
              </div>
            ))}
            {settings.length === 0 && <div className="p-6 text-sm text-muted-foreground">Sin ajustes disponibles.</div>}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
