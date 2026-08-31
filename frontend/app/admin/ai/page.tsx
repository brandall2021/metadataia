"use client";

import { FormEvent, useEffect, useState } from "react";
import { Bot, Plus, Power, Trash2 } from "lucide-react";

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

const inputCls =
  "w-full rounded-lg border border-border bg-muted/30 px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground/60 outline-none transition-colors focus:border-ring focus:bg-muted/50 focus:ring-2 focus:ring-ring/30";

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

export default function AIPage() {
  const [models, setModels] = useState<Model[]>([]);
  const [docTypes, setDocTypes] = useState<DocType[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
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

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold tracking-tight">
            <Bot className="size-6 text-primary" />
            Agentes IA
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Agentes de extracción de metadatos. Cada agente referencia un modelo,
            un tipo documental y prompts; al editar se crea una nueva versión.
          </p>
        </div>
      </div>

      {error && (
        <p className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </p>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="h-fit">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Plus className="size-4" />
              Nuevo agente
            </CardTitle>
            <CardDescription>
              Requiere un modelo activo. El tipo documental es opcional.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form
              onSubmit={handleCreate}
              className="flex flex-col gap-3 text-sm"
            >
              <label className="flex flex-col gap-1.5">
                <span className="text-xs font-medium text-muted-foreground">Nombre</span>
                <input
                  className={inputCls}
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="Extractor de resoluciones"
                  required
                />
              </label>
              <label className="flex flex-col gap-1.5">
                <span className="text-xs font-medium text-muted-foreground">Código</span>
                <input
                  className={inputCls}
                  value={form.code}
                  onChange={(e) => setForm({ ...form, code: e.target.value })}
                  placeholder="resoluciones"
                  required
                />
              </label>
              <label className="flex flex-col gap-1.5">
                <span className="text-xs font-medium text-muted-foreground">Descripción</span>
                <input
                  className={inputCls}
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                  placeholder="Opcional"
                />
              </label>
              <label className="flex flex-col gap-1.5">
                <span className="text-xs font-medium text-muted-foreground">Tipo documental</span>
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
                <span className="text-xs font-medium text-muted-foreground">Modelo</span>
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
                <span className="text-xs font-medium text-muted-foreground">Prompt de sistema</span>
                <textarea
                  className={`${inputCls} min-h-16 resize-y`}
                  value={form.system_prompt}
                  onChange={(e) => setForm({ ...form, system_prompt: e.target.value })}
                  placeholder="Instrucciones fijas del agente"
                />
              </label>
              <label className="flex flex-col gap-1.5">
                <span className="text-xs font-medium text-muted-foreground">Prompt de extracción</span>
                <textarea
                  className={`${inputCls} min-h-16 resize-y`}
                  value={form.extraction_prompt}
                  onChange={(e) => setForm({ ...form, extraction_prompt: e.target.value })}
                  placeholder="Usa {{document_text}} para el contenido del documento"
                />
              </label>
              <div className="grid grid-cols-2 gap-3">
                <label className="flex flex-col gap-1.5">
                  <span className="text-xs font-medium text-muted-foreground">Temperatura</span>
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
                  <span className="text-xs font-medium text-muted-foreground">Max tokens</span>
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

        <div className="lg:col-span-2 overflow-hidden rounded-xl ring-1 ring-foreground/10">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 text-left text-xs text-muted-foreground">
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
                  <td className="px-4 py-3">
                    <div className="font-medium">{a.name}</div>
                    <div className="font-mono text-xs text-muted-foreground">{a.code}</div>
                    {a.description && (
                      <div className="mt-1 text-xs text-muted-foreground">{a.description}</div>
                    )}
                  </td>
                  <td className="px-4 py-3 text-xs">
                    {docTypes.find((d) => d.id === a.document_type_id)?.name ?? (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-xs">
                    {a.current_version ? (
                      <>
                        <div>
                          <span className="font-mono">v{a.current_version.version_number}</span> ·{" "}
                          {a.current_version.model_name}
                        </div>
                        <div className="font-mono text-muted-foreground">
                          {a.current_version.model_identifier}
                        </div>
                      </>
                    ) : (
                      <span className="text-muted-foreground">sin versión</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge active={a.active} onClick={() => toggleAgent(a)} />
                  </td>
                  <td className="px-4 py-3 text-right">
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
                  <td
                    colSpan={5}
                    className="px-4 py-12 text-center text-sm text-muted-foreground"
                  >
                    <Bot className="mx-auto mb-2 size-8 opacity-40" />
                    Sin agentes todavía. Cree el primero con el formulario.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
