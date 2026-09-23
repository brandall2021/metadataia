"use client";

import { useEffect, useState } from "react";
import { Database, Gauge, Sparkles, Tags } from "lucide-react";

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

function MiniStat({ label, value, icon: Icon }: { label: string; value: string; icon: typeof Database }) {
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

export default function ConfigPage() {
  const [settings, setSettings] = useState<Setting[]>([]);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState<string | null>(null);
  const dbCount = settings.filter((setting) => setting.source === "db").length;
  const envCount = settings.filter((setting) => setting.source === "env").length;
  const jsonCount = settings.filter((setting) => typeof setting.value === "object").length;

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
      <section className="overflow-hidden rounded-[2rem] border border-border/70 bg-gradient-to-br from-primary/[0.08] via-background to-muted/50 p-6 shadow-[0_24px_90px_-60px_rgba(15,23,42,0.45)]">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="space-y-2">
            <span className="inline-flex items-center gap-2 rounded-full border border-primary/15 bg-primary/10 px-3 py-1 text-[11px] uppercase tracking-[0.22em] text-primary">
              <Sparkles className="size-3.5" />
              Configuración global
            </span>
            <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">Configuración global</h1>
            <p className="max-w-2xl text-sm leading-6 text-muted-foreground">
              Ajustes administrables del sistema: OCR, IA, tamaños máximos y políticas generales.
            </p>
            <div className="flex flex-wrap gap-2">
              <span className="rounded-full border border-border/70 bg-background/70 px-3 py-1 text-xs text-muted-foreground shadow-sm">Overrides</span>
              <span className="rounded-full border border-border/70 bg-background/70 px-3 py-1 text-xs text-muted-foreground shadow-sm">Entorno</span>
              <span className="rounded-full border border-border/70 bg-background/70 px-3 py-1 text-xs text-muted-foreground shadow-sm">Persistencia</span>
              <span className="rounded-full border border-border/70 bg-background/70 px-3 py-1 text-xs text-muted-foreground shadow-sm">JSON</span>
            </div>
          </div>
          <div className="grid gap-3 sm:min-w-[360px] lg:w-[420px]">
            <div className="grid grid-cols-2 gap-3">
              <MiniStat label="Ajustes" value={String(settings.length)} icon={Gauge} />
              <MiniStat label="DB" value={String(dbCount)} icon={Database} />
              <MiniStat label="Env" value={String(envCount)} icon={Tags} />
              <MiniStat label="JSON" value={String(jsonCount)} icon={Sparkles} />
            </div>
            <div className="rounded-2xl border border-border/70 bg-background/80 p-4 shadow-sm backdrop-blur">
              <div className="flex items-center justify-between gap-3">
                <p className="text-[11px] uppercase tracking-[0.22em] text-muted-foreground">Centro de control</p>
                <span className="rounded-full bg-emerald-500/15 px-2.5 py-1 text-[11px] font-medium text-emerald-600 dark:text-emerald-300">
                  Operativo
                </span>
              </div>
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                <SignalPill label="Origen DB" value={`${dbCount} overrides`} />
                <SignalPill label="Origen env" value={`${envCount} de entorno`} />
              </div>
            </div>
          </div>
        </div>
      </section>

      {error && <p className="rounded-xl border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}

      <Card className="overflow-hidden rounded-[1.75rem] border-border/70 shadow-sm">
        <CardHeader className="space-y-2 border-b border-border/60 bg-muted/20">
          <CardTitle className="text-lg">Ajustes</CardTitle>
          <CardDescription>Los valores en DB tienen prioridad sobre las variables de entorno.</CardDescription>
        </CardHeader>
        <CardContent className="p-4">
          <div className="grid gap-3">
            {settings.map((setting) => (
              <div key={setting.key} className="grid gap-4 rounded-2xl border border-border/70 bg-background/80 p-4 shadow-sm xl:grid-cols-[280px_1fr_auto] xl:items-start">
                <div className="space-y-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="font-medium tracking-tight">{setting.key}</p>
                    <span className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${setting.source === "db" ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground"}`}>
                      {setting.source}
                    </span>
                  </div>
                  <p className="text-sm text-muted-foreground">{setting.description}</p>
                </div>
                <textarea
                  className={`${inputCls} min-h-24 font-mono text-xs`}
                  value={drafts[setting.key] ?? ""}
                  onChange={(e) => setDrafts({ ...drafts, [setting.key]: e.target.value })}
                />
                <div className="flex gap-2 xl:flex-col xl:items-end">
                  <Button size="sm" disabled={saving === setting.key} onClick={() => void saveSetting(setting.key)}>
                    {saving === setting.key ? "Guardando…" : "Guardar"}
                  </Button>
                  <Button variant="outline" size="sm" disabled={saving === setting.key || setting.source === "env"} onClick={() => void deleteSetting(setting.key)}>
                    Eliminar override
                  </Button>
                </div>
              </div>
            ))}
            {settings.length === 0 && <div className="rounded-2xl border border-dashed border-border/70 bg-background p-6 text-sm text-muted-foreground">Sin ajustes disponibles.</div>}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
