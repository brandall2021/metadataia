"use client";

import { FormEvent, useEffect, useState } from "react";
import { Bot, Cpu, Database, KeyRound, Layers3, Plus, Power, Sparkles, Trash2, type LucideIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { apiFetch } from "@/lib/api";

type Model = {
  id: string;
  provider_id: string;
  provider_name: string;
  name: string;
  model_identifier: string;
  active: boolean;
};
type AgentVersion = {
  id: string;
  version_number: number;
  model_id: string;
  model_name: string;
  model_identifier: string;
  system_prompt: string | null;
  extraction_prompt: string | null;
  temperature: number | null;
  max_tokens: number | null;
  created_at: string;
};
type Agent = {
  id: string;
  name: string;
  code: string;
  description: string | null;
  document_type_id: string | null;
  active: boolean;
  current_version: AgentVersion | null;
};
type DocType = { id: string; name: string; code: string };
type Provider = {
  id: string;
  name: string;
  code: string;
  type: string;
  base_url: string | null;
  active: boolean;
  api_key_masked: string;
};

const inputCls =
  "w-full rounded-xl border border-border bg-muted/30 px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground/60 outline-none transition-colors focus:border-ring focus:bg-muted/50 focus:ring-2 focus:ring-ring/30";

function StatusBadge({ active, onClick }: { active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      title={active ? "Desactivar" : "Activar"}
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium transition-colors ${
        active
          ? "bg-emerald-500/15 text-emerald-500 hover:bg-emerald-500/25"
          : "bg-muted text-muted-foreground hover:bg-muted/70"
      }`}
    >
      <span className={`size-1.5 rounded-full ${active ? "bg-emerald-500" : "bg-muted-foreground/60"}`} />
      {active ? "Activo" : "Inactivo"}
    </button>
  );
}

function MiniStat({ label, value, icon: Icon }: { label: string; value: string; icon: LucideIcon }) {
  return (
    <div className="rounded-2xl border border-border/70 bg-background/75 px-4 py-3 shadow-sm">
      <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.22em] text-muted-foreground">
        <Icon className="size-3.5" />
        {label}
      </div>
      <div className="mt-2 text-xl font-semibold tracking-tight">{value}</div>
    </div>
  );
}

function ModelCard({ model }: { model: Model }) {
  return (
    <div className="rounded-2xl border border-border/70 bg-background/70 p-4 shadow-sm transition-colors hover:border-primary/25 hover:bg-muted/20">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <p className="font-medium leading-none">{model.name}</p>
            <span className="rounded-full bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">
              {model.provider_name}
            </span>
          </div>
          <p className="mt-2 font-mono text-xs text-muted-foreground">{model.model_identifier}</p>
        </div>
        <span
          className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium ${
            model.active ? "bg-emerald-500/15 text-emerald-500" : "bg-muted text-muted-foreground"
          }`}
        >
          <span className={`size-1.5 rounded-full ${model.active ? "bg-emerald-500" : "bg-muted-foreground/60"}`} />
          {model.active ? "Activo" : "Inactivo"}
        </span>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-2 text-xs text-muted-foreground">
        <div className="rounded-xl bg-muted/40 px-3 py-2">
          <span className="block text-[10px] uppercase tracking-[0.18em]">Proveedor</span>
          <span className="mt-1 block font-medium text-foreground">{model.provider_id.slice(0, 8)}</span>
        </div>
        <div className="rounded-xl bg-muted/40 px-3 py-2">
          <span className="block text-[10px] uppercase tracking-[0.18em]">Estado</span>
          <span className="mt-1 block font-medium text-foreground">
            {model.active ? "Listo" : "Pausado"}
          </span>
        </div>
      </div>
    </div>
  );
}

export default function AIPage() {
  const [models, setModels] = useState<Model[]>([]);
  const [docTypes, setDocTypes] = useState<DocType[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    name: "",
    code: "",
    description: "",
    document_type_id: "",
    model_id: "",
    system_prompt: "",
    extraction_prompt: "",
    temperature: "",
    max_tokens: "",
  });
  const [providerForm, setProviderForm] = useState({
    name: "",
    code: "",
    type: "openai",
    base_url: "",
    api_key: "",
  });
  const [providerKeys, setProviderKeys] = useState<Record<string, string>>({});
  const [providerResults, setProviderResults] = useState<Record<string, string>>({});
  const [providerBusy, setProviderBusy] = useState<Record<string, boolean>>({});
  const [modelTest, setModelTest] = useState<{
    ok: boolean;
    message: string;
    time_ms: number;
  } | null>(null);
  const [modelTesting, setModelTesting] = useState(false);

  const activeModels = models.filter((model) => model.active).length;
  const activeAgents = agents.filter((agent) => agent.active).length;

  async function load() {
    try {
      const [m, d, a, p] = await Promise.all([
        apiFetch<Model[]>("/api/admin/ai/models"),
        apiFetch<DocType[]>("/api/admin/document-types"),
        apiFetch<Agent[]>("/api/admin/ai/agents"),
        apiFetch<Provider[]>("/api/admin/ai/providers"),
      ]);
      setModels(m);
      setDocTypes(d);
      setAgents(a);
      setProviders(p);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al cargar datos");
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await apiFetch<Agent>("/api/admin/ai/agents", {
        method: "POST",
        body: JSON.stringify({
          name: form.name.trim(),
          code: form.code.trim(),
          description: form.description.trim() || null,
          document_type_id: form.document_type_id || null,
          model_id: form.model_id,
          system_prompt: form.system_prompt || null,
          extraction_prompt: form.extraction_prompt || null,
          temperature: form.temperature ? Number(form.temperature) : null,
          max_tokens: form.max_tokens ? Number(form.max_tokens) : null,
        }),
      });
      setForm({
        name: "",
        code: "",
        description: "",
        document_type_id: "",
        model_id: "",
        system_prompt: "",
        extraction_prompt: "",
        temperature: "",
        max_tokens: "",
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al crear el agente");
    } finally {
      setSaving(false);
    }
  }

  async function toggleAgent(agent: Agent) {
    setError(null);
    try {
      await apiFetch<Agent>(`/api/admin/ai/agents/${agent.id}`, {
        method: "PUT",
        body: JSON.stringify({ active: !agent.active }),
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al actualizar");
    }
  }

  async function deleteAgent(agent: Agent) {
    if (!window.confirm(`¿Eliminar el agente "${agent.name}"?`)) return;
    setError(null);
    try {
      await apiFetch<void>(`/api/admin/ai/agents/${agent.id}`, { method: "DELETE" });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al eliminar");
    }
  }

  async function handleCreateProvider(e: FormEvent) {
    e.preventDefault();
    setProviderBusy((b) => ({ ...b, create: true }));
    setError(null);
    try {
      await apiFetch<Provider>("/api/admin/ai/providers", {
        method: "POST",
        body: JSON.stringify({
          name: providerForm.name.trim(),
          code: providerForm.code.trim(),
          type: providerForm.type,
          base_url: providerForm.base_url.trim() || null,
          api_key: providerForm.api_key.trim() || undefined,
        }),
      });
      setProviderForm({ name: "", code: "", type: "openai", base_url: "", api_key: "" });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al crear proveedor");
    } finally {
      setProviderBusy((b) => ({ ...b, create: false }));
    }
  }

  async function saveProviderKey(p: Provider) {
    const key = (providerKeys[p.id] ?? "").trim();
    if (!key) {
      setProviderResults((r) => ({ ...r, [p.id]: "Escribí una clave para guardar." }));
      return;
    }
    setProviderBusy((b) => ({ ...b, [p.id]: true }));
    setError(null);
    try {
      await apiFetch<Provider>(`/api/admin/ai/providers/${p.id}`, {
        method: "PUT",
        body: JSON.stringify({ api_key: key }),
      });
      setProviderKeys((k) => ({ ...k, [p.id]: "" }));
      setProviderResults((r) => ({ ...r, [p.id]: "Clave guardada." }));
      await load();
    } catch (err) {
      setProviderResults((r) => ({ ...r, [p.id]: err instanceof Error ? err.message : "Error al guardar" }));
    } finally {
      setProviderBusy((b) => ({ ...b, [p.id]: false }));
    }
  }

  async function toggleProvider(p: Provider) {
    setError(null);
    try {
      await apiFetch<Provider>(`/api/admin/ai/providers/${p.id}`, {
        method: "PUT",
        body: JSON.stringify({ active: !p.active }),
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al actualizar");
    }
  }

  async function deleteProvider(p: Provider) {
    if (!window.confirm(`¿Eliminar el proveedor "${p.name}"?`)) return;
    setError(null);
    try {
      await apiFetch<void>(`/api/admin/ai/providers/${p.id}`, { method: "DELETE" });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al eliminar");
    }
  }

  async function testProvider(p: Provider) {
    setProviderBusy((b) => ({ ...b, [p.id]: true }));
    setError(null);
    try {
      const res = await apiFetch<{
        ok: boolean;
        message: string;
        time_ms: number;
        detail?: string | null;
      }>(`/api/admin/ai/providers/${p.id}/test`, { method: "POST" });
      setProviderResults((r) => ({
        ...r,
        [p.id]: `${res.ok ? "OK" : "Falló"} · ${res.message} (${res.time_ms} ms)`,
      }));
    } catch (err) {
      setProviderResults((r) => ({ ...r, [p.id]: err instanceof Error ? err.message : "Error al probar" }));
    } finally {
      setProviderBusy((b) => ({ ...b, [p.id]: false }));
    }
  }

  async function testModel() {
    if (!form.model_id) return;
    setModelTesting(true);
    setModelTest(null);
    setError(null);
    try {
      const res = await apiFetch<{
        ok: boolean;
        message: string;
        time_ms: number;
        detail?: string | null;
      }>(`/api/admin/ai/models/${form.model_id}/test`, { method: "POST" });
      setModelTest(res);
    } catch (err) {
      setModelTest({
        ok: false,
        message: err instanceof Error ? err.message : "Error al probar el modelo",
        time_ms: 0,
      });
    } finally {
      setModelTesting(false);
    }
  }

  return (
    <div className="space-y-6">
      <section className="rounded-3xl border border-border/70 bg-gradient-to-br from-primary/[0.08] via-background to-muted/40 p-6 shadow-sm">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-2xl space-y-3">
            <span className="inline-flex items-center gap-2 rounded-full border border-primary/15 bg-primary/10 px-3 py-1 text-[11px] uppercase tracking-[0.22em] text-primary">
              <Sparkles className="size-3.5" />
              Administración IA
            </span>
            <div className="space-y-2">
              <h1 className="text-3xl font-semibold tracking-tight">Agentes IA</h1>
              <p className="max-w-xl text-sm leading-6 text-muted-foreground">
                Acá se gobiernan los modelos y agentes de extracción: qué modelo usa cada
                agente, sobre qué tipo documental actúa y con qué prompts trabaja.
              </p>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3 sm:min-w-[360px] lg:w-[420px]">
            <MiniStat label="Modelos" value={`${models.length}`} icon={Cpu} />
            <MiniStat label="Activos" value={`${activeModels}`} icon={Database} />
            <MiniStat label="Agentes" value={`${agents.length}`} icon={Layers3} />
            <MiniStat label="Vivos" value={`${activeAgents}`} icon={Bot} />
          </div>
        </div>
      </section>

      {error && (
        <p className="rounded-xl border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </p>
      )}

      <Card className="border-border/70 shadow-sm">
        <CardHeader className="space-y-2 border-b border-border/60 bg-muted/20">
          <CardTitle className="flex items-center gap-2 text-lg">
            <KeyRound className="size-4" />
            Proveedores de IA
          </CardTitle>
          <CardDescription>
            Conectá proveedores (OpenAI, Anthropic, Ollama…) y cargá la API key que usan sus modelos.
          </CardDescription>
        </CardHeader>
        <CardContent className="p-6">
          <div className="grid gap-6 xl:grid-cols-[minmax(360px,0.96fr)_1.04fr]">
            <div className="space-y-3">
              <h3 className="text-sm font-medium">Nuevo proveedor</h3>
              <form onSubmit={handleCreateProvider} className="flex flex-col gap-3 text-sm">
                <label className="flex flex-col gap-1.5">
                  <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                    Nombre
                  </span>
                  <input
                    className={inputCls}
                    value={providerForm.name}
                    onChange={(e) => setProviderForm({ ...providerForm, name: e.target.value })}
                    placeholder="OpenAI"
                    required
                  />
                </label>
                <label className="flex flex-col gap-1.5">
                  <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                    Código
                  </span>
                  <input
                    className={inputCls}
                    value={providerForm.code}
                    onChange={(e) => setProviderForm({ ...providerForm, code: e.target.value })}
                    placeholder="openai"
                    required
                  />
                </label>
                <label className="flex flex-col gap-1.5">
                  <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                    Tipo
                  </span>
                  <select
                    className={inputCls}
                    value={providerForm.type}
                    onChange={(e) => setProviderForm({ ...providerForm, type: e.target.value })}
                  >
                    <option value="openai">openai</option>
                    <option value="openai-compatible">openai-compatible</option>
                    <option value="ollama">ollama</option>
                    <option value="anthropic">anthropic</option>
                  </select>
                </label>
                <label className="flex flex-col gap-1.5">
                  <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                    Base URL
                  </span>
                  <input
                    className={inputCls}
                    value={providerForm.base_url}
                    onChange={(e) => setProviderForm({ ...providerForm, base_url: e.target.value })}
                    placeholder="https://api.openai.com/v1 (opcional, según tipo)"
                  />
                </label>
                <label className="flex flex-col gap-1.5">
                  <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                    API key
                  </span>
                  <input
                    type="password"
                    className={inputCls}
                    value={providerForm.api_key}
                    onChange={(e) => setProviderForm({ ...providerForm, api_key: e.target.value })}
                    placeholder="sk-… (opcional al crear)"
                  />
                </label>
                <Button type="submit" disabled={providerBusy.create} className="mt-1">
                  {providerBusy.create ? "Creando…" : "Crear proveedor"}
                </Button>
              </form>
            </div>

            <div className="space-y-4">
              <h3 className="text-sm font-medium">Cargados ({providers.length})</h3>
              {providers.length > 0 ? (
                providers.map((p) => (
                  <div key={p.id} className="rounded-2xl border border-border/70 bg-background/70 p-4 shadow-sm transition-colors hover:border-primary/25 hover:bg-muted/20">
                    <div className="flex flex-col gap-3">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <p className="font-medium leading-none">{p.name}</p>
                            <span className="rounded-full bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">
                              {p.type}
                            </span>
                            <StatusBadge active={p.active} onClick={() => toggleProvider(p)} />
                          </div>
                          <p className="mt-2 font-mono text-xs text-muted-foreground">{p.code}</p>
                          {p.base_url && <p className="mt-1 text-xs text-muted-foreground">{p.base_url}</p>}
                        </div>
                        <div className="flex shrink-0 items-center gap-1">
                          <Button
                            variant="ghost"
                            size="icon-sm"
                            title={p.active ? "Desactivar" : "Activar"}
                            onClick={() => toggleProvider(p)}
                          >
                            <Power />
                          </Button>
                          <Button
                            variant="destructive"
                            size="icon-sm"
                            title="Eliminar"
                            onClick={() => deleteProvider(p)}
                          >
                            <Trash2 />
                          </Button>
                        </div>
                      </div>
                      <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
                        <label className="flex flex-1 flex-col gap-1">
                          <span className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                            API key {p.api_key_masked ? `(en uso: ${p.api_key_masked})` : "(sin clave)"}
                          </span>
                          <input
                            type="password"
                            className={inputCls}
                            placeholder={p.api_key_masked ? "Nueva clave (vacío = mantener)" : "sk-…"}
                            value={providerKeys[p.id] ?? ""}
                            onChange={(e) => setProviderKeys((k) => ({ ...k, [p.id]: e.target.value }))}
                          />
                        </label>
                        <Button size="sm" disabled={providerBusy[p.id]} onClick={() => saveProviderKey(p)}>
                          Guardar clave
                        </Button>
                        <Button size="sm" variant="outline" disabled={providerBusy[p.id]} onClick={() => testProvider(p)}>
                          Probar conexión
                        </Button>
                      </div>
                      {providerResults[p.id] && (
                        <p
                          className={`text-xs ${
                            providerResults[p.id].startsWith("OK") || providerResults[p.id] === "Clave guardada."
                              ? "text-emerald-600"
                              : "text-muted-foreground"
                          }`}
                        >
                          {providerResults[p.id]}
                        </p>
                      )}
                    </div>
                  </div>
                ))
              ) : (
                <p className="rounded-xl border border-dashed border-border bg-muted/20 p-6 text-center text-sm text-muted-foreground">
                  Sin proveedores todavía. Creá el primero con el formulario.
                </p>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-6 xl:grid-cols-[minmax(360px,0.96fr)_1.04fr]">
        <Card className="h-fit border-border/70 shadow-sm">
          <CardHeader className="space-y-2">
            <CardTitle className="flex items-center gap-2 text-lg">
              <Plus className="size-4" />
              Nuevo agente
            </CardTitle>
            <CardDescription>
              Requiere un modelo activo. El tipo documental es opcional.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleCreate} className="flex flex-col gap-3 text-sm">
              <label className="flex flex-col gap-1.5">
                <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                  Nombre
                </span>
                <input
                  className={inputCls}
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="Extractor de resoluciones"
                  required
                />
              </label>
              <label className="flex flex-col gap-1.5">
                <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                  Código
                </span>
                <input
                  className={inputCls}
                  value={form.code}
                  onChange={(e) => setForm({ ...form, code: e.target.value })}
                  placeholder="resoluciones"
                  required
                />
              </label>
              <label className="flex flex-col gap-1.5">
                <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                  Descripción
                </span>
                <input
                  className={inputCls}
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                  placeholder="Opcional"
                />
              </label>
              <label className="flex flex-col gap-1.5">
                <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                  Tipo documental
                </span>
                <select
                  className={inputCls}
                  value={form.document_type_id}
                  onChange={(e) => setForm({ ...form, document_type_id: e.target.value })}
                >
                  <option value="">Sin asociar</option>
                  {docTypes.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name} ({d.code})
                    </option>
                  ))}
                </select>
              </label>
              <div>
                <div className="flex items-end justify-between gap-2">
                  <label className="flex flex-1 flex-col gap-1.5">
                    <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                      Modelo
                    </span>
                    <select
                      className={inputCls}
                      value={form.model_id}
                      onChange={(e) => {
                        setForm({ ...form, model_id: e.target.value });
                        setModelTest(null);
                      }}
                      required
                    >
                      <option value="" disabled>
                        Seleccionar…
                      </option>
                      {models.map((m) => (
                        <option key={m.id} value={m.id}>
                          {m.name} · {m.provider_name} ({m.model_identifier})
                        </option>
                      ))}
                    </select>
                  </label>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    disabled={modelTesting || !form.model_id}
                    onClick={testModel}
                  >
                    {modelTesting ? "Probando…" : "Probar modelo"}
                  </Button>
                </div>
                {modelTest && (
                  <p
                    className={`mt-1.5 text-xs ${
                      modelTest.ok ? "text-emerald-600" : "text-destructive"
                    }`}
                  >
                    {modelTest.ok ? "OK" : "Falló"} · {modelTest.message}
                    {modelTest.time_ms > 0 ? ` (${modelTest.time_ms} ms)` : ""}
                  </p>
                )}
              </div>
              <label className="flex flex-col gap-1.5">
                <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                  Prompt de sistema
                </span>
                <textarea
                  className={`${inputCls} min-h-20 resize-y`}
                  value={form.system_prompt}
                  onChange={(e) => setForm({ ...form, system_prompt: e.target.value })}
                  placeholder="Instrucciones fijas del agente"
                />
              </label>
              <label className="flex flex-col gap-1.5">
                <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                  Prompt de extracción
                </span>
                <textarea
                  className={`${inputCls} min-h-20 resize-y`}
                  value={form.extraction_prompt}
                  onChange={(e) => setForm({ ...form, extraction_prompt: e.target.value })}
                  placeholder="Usa {{document_text}} para el contenido del documento"
                />
              </label>
              <div className="grid grid-cols-2 gap-3">
                <label className="flex flex-col gap-1.5">
                  <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                    Temperatura
                  </span>
                  <input
                    type="number"
                    step="0.1"
                    className={inputCls}
                    value={form.temperature}
                    onChange={(e) => setForm({ ...form, temperature: e.target.value })}
                    placeholder="0.0"
                  />
                </label>
                <label className="flex flex-col gap-1.5">
                  <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                    Max tokens
                  </span>
                  <input
                    type="number"
                    className={inputCls}
                    value={form.max_tokens}
                    onChange={(e) => setForm({ ...form, max_tokens: e.target.value })}
                    placeholder="4096"
                  />
                </label>
              </div>
              <Button type="submit" disabled={saving || !form.model_id} className="mt-1">
                {saving ? "Creando…" : "Crear agente"}
              </Button>
            </form>
          </CardContent>
        </Card>

        <Card className="border-border/70 shadow-sm">
          <CardHeader className="space-y-2 border-b border-border/60 bg-muted/20">
            <CardTitle className="text-lg">Modelos cargados</CardTitle>
            <CardDescription>
              Estos son los modelos disponibles para enlazar con agentes.
            </CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            {models.length > 0 ? (
              <div className="grid gap-3 p-4 md:grid-cols-2">
                {models.map((model) => (
                  <ModelCard key={model.id} model={model} />
                ))}
              </div>
            ) : (
              <div className="flex min-h-[240px] items-center justify-center p-10 text-center text-sm text-muted-foreground">
                <div className="max-w-sm space-y-2">
                  <Cpu className="mx-auto size-8 opacity-40" />
                  <p>No hay modelos cargados.</p>
                  <p className="text-xs">Cuando el backend responda con permiso, aparecerán acá.</p>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <Card className="overflow-hidden border-border/70 shadow-sm">
        <CardHeader className="space-y-2 border-b border-border/60 bg-muted/20">
          <CardTitle className="text-lg">Agentes configurados</CardTitle>
          <CardDescription>
            Estado, modelo actual y acciones rápidas para cada agente.
          </CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 text-left text-xs uppercase tracking-[0.16em] text-muted-foreground">
              <tr>
                <th className="px-4 py-3 font-medium">Agente</th>
                <th className="px-4 py-3 font-medium">Tipo</th>
                <th className="px-4 py-3 font-medium">Versión</th>
                <th className="px-4 py-3 font-medium">Estado</th>
                <th className="px-4 py-3 text-right font-medium">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {agents.map((a) => (
                <tr key={a.id} className="border-t align-top transition-colors hover:bg-muted/30">
                  <td className="px-4 py-4">
                    <div className="font-medium">{a.name}</div>
                    <div className="mt-1 font-mono text-xs text-muted-foreground">{a.code}</div>
                    {a.description && <div className="mt-2 text-xs text-muted-foreground">{a.description}</div>}
                  </td>
                  <td className="px-4 py-4 text-xs text-muted-foreground">
                    {docTypes.find((d) => d.id === a.document_type_id)?.name ?? <span>—</span>}
                  </td>
                  <td className="px-4 py-4 text-xs">
                    {a.current_version ? (
                      <>
                        <div>
                          <span className="font-mono">v{a.current_version.version_number}</span> · {a.current_version.model_name}
                        </div>
                        <div className="mt-1 font-mono text-muted-foreground">
                          {a.current_version.model_identifier}
                        </div>
                      </>
                    ) : (
                      <span className="text-muted-foreground">sin versión</span>
                    )}
                  </td>
                  <td className="px-4 py-4">
                    <StatusBadge active={a.active} onClick={() => toggleAgent(a)} />
                  </td>
                  <td className="px-4 py-4 text-right">
                    <div className="inline-flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        title={a.active ? "Desactivar" : "Activar"}
                        onClick={() => toggleAgent(a)}
                      >
                        <Power />
                      </Button>
                      <Button
                        variant="destructive"
                        size="icon-sm"
                        title="Eliminar"
                        onClick={() => deleteAgent(a)}
                      >
                        <Trash2 />
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
              {agents.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-14 text-center text-sm text-muted-foreground">
                    <Bot className="mx-auto mb-3 size-10 opacity-35" />
                    Sin agentes todavía. Cree el primero con el formulario.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );
}
