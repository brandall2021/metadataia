"use client";

import { FormEvent, useEffect, useState } from "react";
import { Bot, Cpu, Database, KeyRound, Layers3, Plus, Power, Save, Sparkles, Trash2, type LucideIcon } from "lucide-react";

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
  context_window: number | null;
  supports_json: boolean;
  supports_vision: boolean;
  temperature_default: number | null;
  max_tokens_default: number | null;
  active: boolean;
  configuration_json: Record<string, unknown> | null;
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
  output_schema_json: Record<string, unknown> | null;
  configuration_json: Record<string, unknown> | null;
  active: boolean;
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
    <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 shadow-sm">
      <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.22em] text-slate-500">
        <Icon className="size-3.5" />
        {label}
      </div>
      <div className="mt-2 text-xl font-semibold tracking-tight">{value}</div>
    </div>
  );
}

function SignalPill({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2.5 shadow-sm">
      <div className="text-[10px] uppercase tracking-[0.2em] text-slate-500">{label}</div>
      <div className="mt-1 text-sm font-medium text-foreground">{value}</div>
    </div>
  );
}

function ModelCard({
  model,
  onSelect,
  onToggle,
  onDelete,
  onTest,
  busy,
  selected,
}: {
  model: Model;
  onSelect: (model: Model) => void;
  onToggle: (model: Model) => void;
  onDelete: (model: Model) => void;
  onTest: (model: Model) => void;
  busy: boolean;
  selected: boolean;
}) {
  return (
    <div
      className={`rounded-2xl border bg-background/70 p-4 shadow-sm transition-colors hover:border-primary/25 hover:bg-muted/20 ${
        selected ? "border-primary/35 ring-1 ring-primary/20" : "border-border/70"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <button type="button" className="flex items-center gap-2 text-left" onClick={() => onSelect(model)}>
            <p className="font-medium leading-none">{model.name}</p>
            <span className="rounded-full bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">
              {model.provider_name}
            </span>
          </button>
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
      <div className="mt-4 grid gap-2 text-xs text-muted-foreground sm:grid-cols-2">
        <div className="rounded-xl bg-muted/40 px-3 py-2">Contexto: {model.context_window ?? "—"}</div>
        <div className="rounded-xl bg-muted/40 px-3 py-2">Temp: {model.temperature_default ?? "—"}</div>
        <div className="rounded-xl bg-muted/40 px-3 py-2">JSON: {model.supports_json ? "sí" : "no"}</div>
        <div className="rounded-xl bg-muted/40 px-3 py-2">Visión: {model.supports_vision ? "sí" : "no"}</div>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <Button size="sm" variant="outline" disabled={busy} onClick={() => onSelect(model)}>
          Editar
        </Button>
        <Button size="sm" variant="outline" disabled={busy} onClick={() => onTest(model)}>
          Probar
        </Button>
        <Button size="sm" variant="outline" disabled={busy} onClick={() => onToggle(model)}>
          {model.active ? "Desactivar" : "Activar"}
        </Button>
        <Button size="sm" variant="destructive" disabled={busy} onClick={() => onDelete(model)}>
          Eliminar
        </Button>
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
  const [modelForm, setModelForm] = useState({
    provider_id: "",
    name: "",
    model_identifier: "",
    context_window: "",
    supports_json: true,
    supports_vision: false,
    temperature_default: "",
    max_tokens_default: "",
    active: true,
  });
  const [selectedModelId, setSelectedModelId] = useState<string | null>(null);
  const [providerKeys, setProviderKeys] = useState<Record<string, string>>({});
  const [providerResults, setProviderResults] = useState<Record<string, string>>({});
  const [providerBusy, setProviderBusy] = useState<Record<string, boolean>>({});
  const [modelBusy, setModelBusy] = useState<Record<string, boolean>>({});
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const [agentVersions, setAgentVersions] = useState<AgentVersion[]>([]);
  const [versionForm, setVersionForm] = useState({
    model_id: "",
    system_prompt: "",
    extraction_prompt: "",
    temperature: "",
    max_tokens: "",
  });
  const [versionSaving, setVersionSaving] = useState(false);
  const [modelTest, setModelTest] = useState<{
    ok: boolean;
    message: string;
    time_ms: number;
  } | null>(null);
  const [modelTesting, setModelTesting] = useState(false);

  const activeModels = models.filter((model) => model.active).length;
  const activeAgents = agents.filter((agent) => agent.active).length;
  const selectedModel = selectedModelId ? models.find((model) => model.id === selectedModelId) ?? null : null;
  const selectedAgent = selectedAgentId ? agents.find((agent) => agent.id === selectedAgentId) ?? null : null;

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
      if (selectedAgentId === agent.id) {
        setSelectedAgentId(null);
        setAgentVersions([]);
      }
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al eliminar");
    }
  }

  async function loadAgentVersions(agentId: string) {
    const versions = await apiFetch<AgentVersion[]>(`/api/admin/ai/agents/${agentId}/versions`);
    setAgentVersions(versions);
    const current = agents.find((agent) => agent.id === agentId)?.current_version ?? null;
    setVersionForm({
      model_id: current?.model_id ?? models[0]?.id ?? "",
      system_prompt: current?.system_prompt ?? "",
      extraction_prompt: current?.extraction_prompt ?? "",
      temperature: current?.temperature?.toString() ?? "",
      max_tokens: current?.max_tokens?.toString() ?? "",
    });
  }

  async function selectAgent(agent: Agent) {
    setSelectedAgentId(agent.id);
    setError(null);
    try {
      await loadAgentVersions(agent.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al cargar versiones");
    }
  }

  async function createAgentVersion() {
    if (!selectedAgentId || !versionForm.model_id) return;
    setVersionSaving(true);
    setError(null);
    try {
      await apiFetch(`/api/admin/ai/agents/${selectedAgentId}/versions`, {
        method: "POST",
        body: JSON.stringify({
          model_id: versionForm.model_id,
          system_prompt: versionForm.system_prompt || null,
          extraction_prompt: versionForm.extraction_prompt || null,
          temperature: versionForm.temperature ? Number(versionForm.temperature) : null,
          max_tokens: versionForm.max_tokens ? Number(versionForm.max_tokens) : null,
        }),
      });
      await load();
      await loadAgentVersions(selectedAgentId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al crear la versión");
    } finally {
      setVersionSaving(false);
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

  function selectModel(model: Model) {
    setSelectedModelId(model.id);
    setModelForm({
      provider_id: model.provider_id,
      name: model.name,
      model_identifier: model.model_identifier,
      context_window: model.context_window?.toString() ?? "",
      supports_json: model.supports_json,
      supports_vision: model.supports_vision,
      temperature_default: model.temperature_default?.toString() ?? "",
      max_tokens_default: model.max_tokens_default?.toString() ?? "",
      active: model.active,
    });
    setModelTest(null);
  }

  function clearModelForm() {
    setSelectedModelId(null);
    setModelForm({
      provider_id: providers[0]?.id ?? "",
      name: "",
      model_identifier: "",
      context_window: "",
      supports_json: true,
      supports_vision: false,
      temperature_default: "",
      max_tokens_default: "",
      active: true,
    });
    setModelTest(null);
  }

  useEffect(() => {
    if (!modelForm.provider_id && providers[0]) {
      setModelForm((prev) => ({ ...prev, provider_id: providers[0].id }));
    }
  }, [providers, modelForm.provider_id]);

  async function handleSaveModel(e: FormEvent) {
    e.preventDefault();
    if (!modelForm.provider_id) {
      setError("Seleccioná un proveedor primero");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const payload = {
        provider_id: modelForm.provider_id,
        name: modelForm.name.trim(),
        model_identifier: modelForm.model_identifier.trim(),
        context_window: modelForm.context_window ? Number(modelForm.context_window) : null,
        supports_json: modelForm.supports_json,
        supports_vision: modelForm.supports_vision,
        temperature_default: modelForm.temperature_default ? Number(modelForm.temperature_default) : null,
        max_tokens_default: modelForm.max_tokens_default ? Number(modelForm.max_tokens_default) : null,
        active: modelForm.active,
      };
      if (selectedModelId) {
        await apiFetch<Model>(`/api/admin/ai/models/${selectedModelId}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
      } else {
        await apiFetch<Model>("/api/admin/ai/models", {
          method: "POST",
          body: JSON.stringify(payload),
        });
      }
      clearModelForm();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al guardar el modelo");
    } finally {
      setSaving(false);
    }
  }

  async function toggleModel(model: Model) {
    setModelBusy((b) => ({ ...b, [model.id]: true }));
    setError(null);
    try {
      await apiFetch<Model>(`/api/admin/ai/models/${model.id}`, {
        method: "PUT",
        body: JSON.stringify({ active: !model.active }),
      });
      await load();
      if (selectedModelId === model.id) selectModel({ ...model, active: !model.active });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al actualizar el modelo");
    } finally {
      setModelBusy((b) => ({ ...b, [model.id]: false }));
    }
  }

  async function deleteModel(model: Model) {
    if (!window.confirm(`¿Eliminar el modelo "${model.name}"?`)) return;
    setModelBusy((b) => ({ ...b, [model.id]: true }));
    setError(null);
    try {
      await apiFetch<void>(`/api/admin/ai/models/${model.id}`, { method: "DELETE" });
      if (selectedModelId === model.id) clearModelForm();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al eliminar el modelo");
    } finally {
      setModelBusy((b) => ({ ...b, [model.id]: false }));
    }
  }

  async function testModelById(model: Model) {
    setModelBusy((b) => ({ ...b, [model.id]: true }));
    setError(null);
    try {
      const res = await apiFetch<{ ok: boolean; message: string; time_ms: number }>(`/api/admin/ai/models/${model.id}/test`, { method: "POST" });
      setModelTest(res);
      setSelectedModelId(model.id);
      selectModel(model);
    } catch (err) {
      setModelTest({ ok: false, message: err instanceof Error ? err.message : "Error al probar", time_ms: 0 });
    } finally {
      setModelBusy((b) => ({ ...b, [model.id]: false }));
    }
  }

  async function cloneAgent(agent: Agent) {
    setModelBusy((b) => ({ ...b, [agent.id]: true }));
    setError(null);
    try {
      await apiFetch<Agent>(`/api/admin/ai/agents/${agent.id}/clone`, { method: "POST" });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al clonar agente");
    } finally {
      setModelBusy((b) => ({ ...b, [agent.id]: false }));
    }
  }

  async function testAgent(agent: Agent) {
    setModelBusy((b) => ({ ...b, [agent.id]: true }));
    setError(null);
    try {
      const res = await apiFetch<{ ok: boolean; message: string; time_ms: number }>(`/api/admin/ai/agents/${agent.id}/test`, { method: "POST" });
      setError(`${agent.name}: ${res.ok ? "OK" : "Falló"} · ${res.message} (${res.time_ms} ms)`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al probar el agente");
    } finally {
      setModelBusy((b) => ({ ...b, [agent.id]: false }));
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
      <section className="rounded-[1.75rem] border border-slate-200 bg-white p-6 shadow-[0_20px_50px_-34px_rgba(15,23,42,0.36)]">
        <div className="flex flex-col gap-8 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-2xl space-y-4">
            <span className="inline-flex items-center gap-2 rounded-full border border-indigo-100 bg-indigo-50 px-3 py-1 text-[11px] font-medium uppercase tracking-[0.22em] text-[#4F46E5]">
              <Sparkles className="size-3.5" />
              Administración IA
            </span>
            <div className="space-y-3">
              <h1 className="text-3xl font-semibold tracking-tight text-slate-950 sm:text-4xl">Agentes IA</h1>
              <p className="max-w-xl text-sm leading-6 text-slate-500">
                Acá se gobiernan los modelos y agentes de extracción: qué modelo usa cada
                agente, sobre qué tipo documental actúa y con qué prompts trabaja.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs text-slate-500 shadow-sm">Proveedores</span>
              <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs text-slate-500 shadow-sm">Modelos</span>
              <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs text-slate-500 shadow-sm">Agentes</span>
              <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs text-slate-500 shadow-sm">Versiones</span>
            </div>
          </div>
          <div className="grid gap-3 sm:min-w-[360px] lg:w-[420px]">
            <div className="grid grid-cols-2 gap-3">
              <MiniStat label="Modelos" value={`${models.length}`} icon={Cpu} />
              <MiniStat label="Activos" value={`${activeModels}`} icon={Database} />
              <MiniStat label="Agentes" value={`${agents.length}`} icon={Layers3} />
              <MiniStat label="Vivos" value={`${activeAgents}`} icon={Bot} />
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 shadow-sm">
              <div className="flex items-center justify-between gap-3">
                <p className="text-[11px] uppercase tracking-[0.22em] text-slate-500">Centro de control</p>
                <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-[11px] font-medium text-emerald-700">
                  Operativo
                </span>
              </div>
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                <SignalPill label="Proveedores" value={`${providers.length} cargados`} />
                <SignalPill label="Tipos doc." value={`${docTypes.length} disponibles`} />
              </div>
              <p className="mt-3 text-xs leading-5 text-muted-foreground">
                Editá proveedor, modelo y agente sin salir de la misma vista. La selección activa se mantiene visible para que el contexto no se pierda.
              </p>
            </div>
          </div>
        </div>
      </section>

      {error && (
        <p className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {error}
        </p>
      )}

      <Card className="overflow-hidden rounded-[1.5rem] border-slate-200 shadow-[0_14px_30px_-24px_rgba(15,23,42,0.32)]">
        <CardHeader className="space-y-2 border-b border-slate-200 bg-slate-50/80">
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
        <Card className="h-fit overflow-hidden rounded-[1.75rem] border-border/70 shadow-sm">
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

        <Card className="overflow-hidden rounded-[1.75rem] border-border/70 shadow-sm">
          <CardHeader className="space-y-2 border-b border-slate-200 bg-slate-50/80">
            <CardTitle className="flex items-center gap-2 text-lg">
              <Cpu className="size-4" />
              Modelos
            </CardTitle>
            <CardDescription>
              Crea, edita, prueba y desactiva modelos usados por los agentes.
            </CardDescription>
          </CardHeader>
          <CardContent className="p-6">
            <div className="grid gap-6 xl:grid-cols-[minmax(360px,0.96fr)_1.04fr]">
              <div className="space-y-3">
                <h3 className="text-sm font-medium">{selectedModelId ? "Editar modelo" : "Nuevo modelo"}</h3>
                {selectedModel && (
                  <div className="rounded-2xl border border-primary/20 bg-primary/5 px-4 py-3 text-sm shadow-sm">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="text-[11px] uppercase tracking-[0.2em] text-primary/80">Modelo activo</p>
                        <p className="mt-1 font-medium text-foreground">{selectedModel.name}</p>
                      </div>
                      <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${selectedModel.active ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-300" : "bg-muted text-muted-foreground"}`}>
                        {selectedModel.active ? "Activo" : "Inactivo"}
                      </span>
                    </div>
                    <p className="mt-2 font-mono text-xs text-muted-foreground">{selectedModel.provider_name} · {selectedModel.model_identifier}</p>
                  </div>
                )}
                <form onSubmit={handleSaveModel} className="flex flex-col gap-3 text-sm">
                  <label className="flex flex-col gap-1.5">
                    <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Proveedor</span>
                    <select className={inputCls} value={modelForm.provider_id} onChange={(e) => setModelForm({ ...modelForm, provider_id: e.target.value })} required>
                      <option value="" disabled>Seleccionar…</option>
                      {providers.map((p) => (
                        <option key={p.id} value={p.id}>{p.name} ({p.code})</option>
                      ))}
                    </select>
                  </label>
                  <label className="flex flex-col gap-1.5">
                    <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Nombre</span>
                    <input className={inputCls} value={modelForm.name} onChange={(e) => setModelForm({ ...modelForm, name: e.target.value })} required />
                  </label>
                  <label className="flex flex-col gap-1.5">
                    <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Identificador</span>
                    <input className={inputCls} value={modelForm.model_identifier} onChange={(e) => setModelForm({ ...modelForm, model_identifier: e.target.value })} required />
                  </label>
                  <div className="grid grid-cols-2 gap-3">
                    <label className="flex flex-col gap-1.5">
                      <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Contexto</span>
                      <input className={inputCls} type="number" value={modelForm.context_window} onChange={(e) => setModelForm({ ...modelForm, context_window: e.target.value })} placeholder="8192" />
                    </label>
                    <label className="flex flex-col gap-1.5">
                      <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Estado</span>
                      <select className={inputCls} value={modelForm.active ? "true" : "false"} onChange={(e) => setModelForm({ ...modelForm, active: e.target.value === "true" })}>
                        <option value="true">Activo</option>
                        <option value="false">Inactivo</option>
                      </select>
                    </label>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <label className="flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm">
                      <input type="checkbox" checked={modelForm.supports_json} onChange={(e) => setModelForm({ ...modelForm, supports_json: e.target.checked })} />
                      JSON
                    </label>
                    <label className="flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm">
                      <input type="checkbox" checked={modelForm.supports_vision} onChange={(e) => setModelForm({ ...modelForm, supports_vision: e.target.checked })} />
                      Visión
                    </label>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <label className="flex flex-col gap-1.5">
                      <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Temp. por defecto</span>
                      <input className={inputCls} type="number" step="0.1" value={modelForm.temperature_default} onChange={(e) => setModelForm({ ...modelForm, temperature_default: e.target.value })} placeholder="0.0" />
                    </label>
                    <label className="flex flex-col gap-1.5">
                      <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Max tokens</span>
                      <input className={inputCls} type="number" value={modelForm.max_tokens_default} onChange={(e) => setModelForm({ ...modelForm, max_tokens_default: e.target.value })} placeholder="4096" />
                    </label>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button type="submit" disabled={saving} className="gap-2">{saving ? "Guardando…" : <><Save className="size-4" /> Guardar modelo</>}</Button>
                    <Button type="button" variant="outline" onClick={clearModelForm}>Nuevo</Button>
                    {selectedModelId && <Button type="button" variant="outline" onClick={clearModelForm}>Cancelar edición</Button>}
                  </div>
                  {modelTest && (
                    <p className={`text-xs ${modelTest.ok ? "text-emerald-600" : "text-destructive"}`}>
                      {modelTest.ok ? "OK" : "Falló"} · {modelTest.message}
                      {modelTest.time_ms > 0 ? ` (${modelTest.time_ms} ms)` : ""}
                    </p>
                  )}
                </form>
              </div>

              <div className="space-y-4">
                <h3 className="text-sm font-medium">Cargados ({models.length})</h3>
                {models.length > 0 ? (
                  <div className="grid gap-3 md:grid-cols-2">
                    {models.map((model) => (
                      <ModelCard
                        key={model.id}
                        model={model}
                        selected={selectedModelId === model.id}
                        busy={Boolean(modelBusy[model.id])}
                        onSelect={selectModel}
                        onToggle={toggleModel}
                        onDelete={deleteModel}
                        onTest={testModelById}
                      />
                    ))}
                  </div>
                ) : (
                  <p className="rounded-xl border border-dashed border-border bg-muted/20 p-6 text-center text-sm text-muted-foreground">
                    Sin modelos todavía. Creá el primero con el formulario.
                  </p>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card className="overflow-hidden rounded-[1.5rem] border-slate-200 shadow-[0_14px_30px_-24px_rgba(15,23,42,0.32)]">
        <CardHeader className="space-y-2 border-b border-slate-200 bg-slate-50/80">
          <CardTitle className="text-lg">Agentes configurados</CardTitle>
          <CardDescription>
            Estado, modelo actual y acciones rápidas para cada agente.
          </CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
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
                        size="sm"
                        title="Ver versiones"
                        onClick={() => void selectAgent(a)}
                      >
                        Versiones
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        title="Probar agente"
                        onClick={() => void testAgent(a)}
                      >
                        <Sparkles />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        title="Clonar agente"
                        onClick={() => void cloneAgent(a)}
                      >
                        <Plus />
                      </Button>
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
          </div>
        </CardContent>
      </Card>

      <Card className="overflow-hidden rounded-[1.75rem] border-border/70 shadow-sm">
        <CardHeader className="space-y-2 border-b border-slate-200 bg-slate-50/80">
          <CardTitle className="text-lg">Versiones del agente</CardTitle>
          <CardDescription>
            {selectedAgentId ? "Historial y nueva versión para el agente seleccionado." : "Elegí un agente para ver su historial de versiones."}
          </CardDescription>
        </CardHeader>
        <CardContent className="p-6">
          {selectedAgentId ? (
            <div className="grid gap-6 xl:grid-cols-[0.92fr_1.08fr]">
              <div className="space-y-3">
                <h3 className="text-sm font-medium">Nueva versión</h3>
                {selectedAgent && (
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 shadow-sm">
                    <p className="text-[11px] uppercase tracking-[0.2em] text-slate-500">Agente seleccionado</p>
                    <p className="mt-1 font-medium text-foreground">{selectedAgent.name}</p>
                    <p className="mt-1 font-mono text-xs text-muted-foreground">{selectedAgent.code}</p>
                  </div>
                )}
                <div className="space-y-3 rounded-2xl border border-slate-200 bg-white p-4">
                  <label className="flex flex-col gap-1.5 text-sm">
                    <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Modelo</span>
                    <select className={inputCls} value={versionForm.model_id} onChange={(e) => setVersionForm({ ...versionForm, model_id: e.target.value })} required>
                      <option value="" disabled>Seleccionar…</option>
                      {models.map((model) => (
                        <option key={model.id} value={model.id}>{model.name} · {model.provider_name}</option>
                      ))}
                    </select>
                  </label>
                  <label className="flex flex-col gap-1.5 text-sm">
                    <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Prompt de sistema</span>
                    <textarea className={`${inputCls} min-h-20 resize-y`} value={versionForm.system_prompt} onChange={(e) => setVersionForm({ ...versionForm, system_prompt: e.target.value })} />
                  </label>
                  <label className="flex flex-col gap-1.5 text-sm">
                    <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Prompt de extracción</span>
                    <textarea className={`${inputCls} min-h-20 resize-y`} value={versionForm.extraction_prompt} onChange={(e) => setVersionForm({ ...versionForm, extraction_prompt: e.target.value })} />
                  </label>
                  <div className="grid grid-cols-2 gap-3">
                    <label className="flex flex-col gap-1.5 text-sm">
                      <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Temperatura</span>
                      <input className={inputCls} type="number" step="0.1" value={versionForm.temperature} onChange={(e) => setVersionForm({ ...versionForm, temperature: e.target.value })} />
                    </label>
                    <label className="flex flex-col gap-1.5 text-sm">
                      <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Max tokens</span>
                      <input className={inputCls} type="number" value={versionForm.max_tokens} onChange={(e) => setVersionForm({ ...versionForm, max_tokens: e.target.value })} />
                    </label>
                  </div>
                  <Button type="button" className="gap-2" disabled={versionSaving || !versionForm.model_id} onClick={() => void createAgentVersion()}>
                    <Save className="size-4" />
                    {versionSaving ? "Guardando…" : "Crear versión"}
                  </Button>
                </div>
              </div>

              <div className="space-y-3">
                <h3 className="text-sm font-medium">Historial</h3>
                <div className="space-y-3">
                  {agentVersions.map((version) => (
                    <div key={version.id} className={`rounded-2xl border p-4 shadow-sm ${version.active ? "border-primary/25 bg-primary/5" : "border-border/60 bg-background"}`}>
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="font-medium">Versión {version.version_number}</p>
                          <p className="mt-1 text-xs text-muted-foreground">{version.model_name} · {version.model_identifier}</p>
                        </div>
                        <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${version.active ? "bg-emerald-500/15 text-emerald-500" : "bg-muted text-muted-foreground"}`}>
                          {version.active ? "Activa" : "Histórica"}
                        </span>
                      </div>
                      <div className="mt-3 grid gap-2 text-xs text-muted-foreground sm:grid-cols-2">
                        <div className="rounded-xl bg-muted/40 px-3 py-2">Temp: {version.temperature ?? "—"}</div>
                        <div className="rounded-xl bg-muted/40 px-3 py-2">Max tokens: {version.max_tokens ?? "—"}</div>
                      </div>
                      {version.system_prompt && <p className="mt-3 line-clamp-3 text-xs text-muted-foreground">{version.system_prompt}</p>}
                    </div>
                  ))}
                  {agentVersions.length === 0 && (
                    <div className="rounded-2xl border border-dashed border-border/70 bg-background p-6 text-sm text-muted-foreground">
                      Todavía no hay versiones para este agente.
                    </div>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <div className="rounded-2xl border border-dashed border-border/70 bg-background p-6 text-sm text-muted-foreground">
              Seleccioná un agente desde la lista para ver y crear versiones.
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
