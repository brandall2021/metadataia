"use client";

import { FormEvent, useEffect, useState } from "react";
import { Bot, Plus, Power, Save, Sparkles, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  inputCls,
  ErrorBanner,
  StatusBadge,
  type Agent,
  type AgentVersion,
  type DocType,
  type Model,
} from "@/components/admin/ai/common";
import { apiFetch } from "@/lib/api";

const emptyForm = {
  name: "",
  code: "",
  description: "",
  document_type_id: "",
  model_id: "",
  system_prompt: "",
  extraction_prompt: "",
  temperature: "",
  max_tokens: "",
};

const emptyVersionForm = {
  model_id: "",
  system_prompt: "",
  extraction_prompt: "",
  temperature: "",
  max_tokens: "",
};

export default function AgentesPage() {
  const [models, setModels] = useState<Model[]>([]);
  const [docTypes, setDocTypes] = useState<DocType[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [agentBusy, setAgentBusy] = useState<Record<string, boolean>>({});
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const [agentVersions, setAgentVersions] = useState<AgentVersion[]>([]);
  const [versionForm, setVersionForm] = useState(emptyVersionForm);
  const [versionSaving, setVersionSaving] = useState(false);

  const selectedAgent = selectedAgentId
    ? agents.find((agent) => agent.id === selectedAgentId) ?? null
    : null;

  async function load() {
    try {
      const [m, d, a] = await Promise.all([
        apiFetch<Model[]>("/api/admin/ai/models"),
        apiFetch<DocType[]>("/api/admin/document-types"),
        apiFetch<Agent[]>("/api/admin/ai/agents"),
      ]);
      setModels(m);
      setDocTypes(d);
      setAgents(a);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al cargar datos");
    }
  }

  useEffect(() => {
    void (async () => {
      await load();
    })();
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
      setForm(emptyForm);
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

  async function cloneAgent(agent: Agent) {
    setAgentBusy((b) => ({ ...b, [agent.id]: true }));
    setError(null);
    try {
      await apiFetch<Agent>(`/api/admin/ai/agents/${agent.id}/clone`, { method: "POST" });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al clonar agente");
    } finally {
      setAgentBusy((b) => ({ ...b, [agent.id]: false }));
    }
  }

  async function testAgent(agent: Agent) {
    setAgentBusy((b) => ({ ...b, [agent.id]: true }));
    setError(null);
    try {
      const res = await apiFetch<{ ok: boolean; message: string; time_ms: number }>(
        `/api/admin/ai/agents/${agent.id}/test`,
        { method: "POST" },
      );
      setError(`${agent.name}: ${res.ok ? "OK" : "Falló"} · ${res.message} (${res.time_ms} ms)`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al probar el agente");
    } finally {
      setAgentBusy((b) => ({ ...b, [agent.id]: false }));
    }
  }

  return (
    <div className="space-y-6">
      <ErrorBanner message={error} />

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
              <label className="flex flex-col gap-1.5">
                <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                  Modelo
                </span>
                <select
                  className={inputCls}
                  value={form.model_id}
                  onChange={(e) => setForm({ ...form, model_id: e.target.value })}
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
            <CardTitle className="text-lg">Agentes configurados</CardTitle>
            <CardDescription>
              Estado, modelo actual y acciones para cada agente.
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
                        {a.description && (
                          <div className="mt-2 text-xs text-muted-foreground">{a.description}</div>
                        )}
                      </td>
                      <td className="px-4 py-4 text-xs text-muted-foreground">
                        {docTypes.find((d) => d.id === a.document_type_id)?.name ?? <span>—</span>}
                      </td>
                      <td className="px-4 py-4 text-xs">
                        {a.current_version ? (
                          <>
                            <div>
                              <span className="font-mono">v{a.current_version.version_number}</span>{" "}
                              · {a.current_version.model_name}
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
                            disabled={Boolean(agentBusy[a.id])}
                            onClick={() => void testAgent(a)}
                          >
                            <Sparkles />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon-sm"
                            title="Clonar agente"
                            disabled={Boolean(agentBusy[a.id])}
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
                        Sin agentes todavía. Creá el primero con el formulario.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      </div>

      {selectedAgentId && (
        <Card className="overflow-hidden rounded-[1.75rem] border-border/70 shadow-sm">
          <CardHeader className="space-y-2 border-b border-slate-200 bg-slate-50/80">
            <CardTitle className="text-lg">Versiones · {selectedAgent?.name}</CardTitle>
            <CardDescription>Historial y nueva versión para el agente seleccionado.</CardDescription>
          </CardHeader>
          <CardContent className="p-6">
            <div className="grid gap-6 xl:grid-cols-[0.92fr_1.08fr]">
              <div className="space-y-3">
                <h3 className="text-sm font-medium">Nueva versión</h3>
                <div className="space-y-3 rounded-2xl border border-slate-200 bg-white p-4">
                  <label className="flex flex-col gap-1.5 text-sm">
                    <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                      Modelo
                    </span>
                    <select
                      className={inputCls}
                      value={versionForm.model_id}
                      onChange={(e) => setVersionForm({ ...versionForm, model_id: e.target.value })}
                      required
                    >
                      <option value="" disabled>
                        Seleccionar…
                      </option>
                      {models.map((model) => (
                        <option key={model.id} value={model.id}>
                          {model.name} · {model.provider_name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="flex flex-col gap-1.5 text-sm">
                    <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                      Prompt de sistema
                    </span>
                    <textarea
                      className={`${inputCls} min-h-20 resize-y`}
                      value={versionForm.system_prompt}
                      onChange={(e) =>
                        setVersionForm({ ...versionForm, system_prompt: e.target.value })
                      }
                    />
                  </label>
                  <label className="flex flex-col gap-1.5 text-sm">
                    <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                      Prompt de extracción
                    </span>
                    <textarea
                      className={`${inputCls} min-h-20 resize-y`}
                      value={versionForm.extraction_prompt}
                      onChange={(e) =>
                        setVersionForm({ ...versionForm, extraction_prompt: e.target.value })
                      }
                    />
                  </label>
                  <div className="grid grid-cols-2 gap-3">
                    <label className="flex flex-col gap-1.5 text-sm">
                      <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                        Temperatura
                      </span>
                      <input
                        className={inputCls}
                        type="number"
                        step="0.1"
                        value={versionForm.temperature}
                        onChange={(e) =>
                          setVersionForm({ ...versionForm, temperature: e.target.value })
                        }
                      />
                    </label>
                    <label className="flex flex-col gap-1.5 text-sm">
                      <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                        Max tokens
                      </span>
                      <input
                        className={inputCls}
                        type="number"
                        value={versionForm.max_tokens}
                        onChange={(e) =>
                          setVersionForm({ ...versionForm, max_tokens: e.target.value })
                        }
                      />
                    </label>
                  </div>
                  <Button
                    type="button"
                    className="gap-2"
                    disabled={versionSaving || !versionForm.model_id}
                    onClick={() => void createAgentVersion()}
                  >
                    <Save className="size-4" />
                    {versionSaving ? "Guardando…" : "Crear versión"}
                  </Button>
                </div>
              </div>

              <div className="space-y-3">
                <h3 className="text-sm font-medium">Historial</h3>
                <div className="space-y-3">
                  {agentVersions.map((version) => (
                    <div
                      key={version.id}
                      className={`rounded-2xl border p-4 shadow-sm ${
                        version.active ? "border-primary/25 bg-primary/5" : "border-border/60 bg-background"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="font-medium">Versión {version.version_number}</p>
                          <p className="mt-1 text-xs text-muted-foreground">
                            {version.model_name} · {version.model_identifier}
                          </p>
                        </div>
                        <span
                          className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                            version.active
                              ? "bg-emerald-500/15 text-emerald-500"
                              : "bg-muted text-muted-foreground"
                          }`}
                        >
                          {version.active ? "Activa" : "Histórica"}
                        </span>
                      </div>
                      <div className="mt-3 grid gap-2 text-xs text-muted-foreground sm:grid-cols-2">
                        <div className="rounded-xl bg-muted/40 px-3 py-2">
                          Temp: {version.temperature ?? "—"}
                        </div>
                        <div className="rounded-xl bg-muted/40 px-3 py-2">
                          Max tokens: {version.max_tokens ?? "—"}
                        </div>
                      </div>
                      {version.system_prompt && (
                        <p className="mt-3 line-clamp-3 text-xs text-muted-foreground">
                          {version.system_prompt}
                        </p>
                      )}
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
          </CardContent>
        </Card>
      )}
    </div>
  );
}
