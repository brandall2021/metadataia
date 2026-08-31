"use client";

import { FormEvent, useEffect, useState } from "react";

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
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Agentes IA</h1>
        <p className="text-sm text-muted-foreground">
          Agentes de extracción de metadatos. Cada agente referencia un modelo,
          un tipo documental y prompts; al editar se crea una nueva versión.
        </p>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Nuevo agente</CardTitle>
            <CardDescription>
              Requiere un modelo activo (visto en la pestaña de modelos si está
              habilitada en la API).
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleCreate} className="flex flex-col gap-3 text-sm">
              <label className="flex flex-col gap-1">
                Nombre
                <input
                  className="rounded-lg border border-border bg-background px-3 py-2"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="Extractor de resoluciones"
                  required
                />
              </label>
              <label className="flex flex-col gap-1">
                Código
                <input
                  className="rounded-lg border border-border bg-background px-3 py-2"
                  value={form.code}
                  onChange={(e) => setForm({ ...form, code: e.target.value })}
                  placeholder="resoluciones"
                  required
                />
              </label>
              <label className="flex flex-col gap-1">
                Descripción
                <input
                  className="rounded-lg border border-border bg-background px-3 py-2"
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                  placeholder="Opcional"
                />
              </label>
              <label className="flex flex-col gap-1">
                Tipo documental
                <select
                  className="rounded-lg border border-border bg-background px-3 py-2"
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
              <label className="flex flex-col gap-1">
                Modelo
                <select
                  className="rounded-lg border border-border bg-background px-3 py-2"
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
              <label className="flex flex-col gap-1">
                Prompt de sistema
                <textarea
                  className="rounded-lg border border-border bg-background px-3 py-2 min-h-16"
                  value={form.system_prompt}
                  onChange={(e) => setForm({ ...form, system_prompt: e.target.value })}
                  placeholder="Instrucciones fijas del agente"
                />
              </label>
              <label className="flex flex-col gap-1">
                Prompt de extracción
                <textarea
                  className="rounded-lg border border-border bg-background px-3 py-2 min-h-16"
                  value={form.extraction_prompt}
                  onChange={(e) => setForm({ ...form, extraction_prompt: e.target.value })}
                  placeholder="Usa {{document_text}} para el contenido del documento"
                />
              </label>
              <div className="grid grid-cols-2 gap-3">
                <label className="flex flex-col gap-1">
                  Temperatura
                  <input
                    type="number"
                    step="0.1"
                    className="rounded-lg border border-border bg-background px-3 py-2"
                    value={form.temperature}
                    onChange={(e) => setForm({ ...form, temperature: e.target.value })}
                    placeholder="0.0"
                  />
                </label>
                <label className="flex flex-col gap-1">
                  Max tokens
                  <input
                    type="number"
                    className="rounded-lg border border-border bg-background px-3 py-2"
                    value={form.max_tokens}
                    onChange={(e) => setForm({ ...form, max_tokens: e.target.value })}
                    placeholder="4096"
                  />
                </label>
              </div>
              <Button type="submit" disabled={saving || !form.model_id}>
                {saving ? "Creando…" : "Crear agente"}
              </Button>
            </form>
          </CardContent>
        </Card>

        <div className="lg:col-span-2 overflow-hidden rounded-xl ring-1 ring-foreground/10">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 text-left text-xs text-muted-foreground">
              <tr>
                <th className="px-3 py-2">Agente</th>
                <th className="px-3 py-2">Tipo</th>
                <th className="px-3 py-2">Versión</th>
                <th className="px-3 py-2">Estado</th>
                <th className="px-3 py-2">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {agents.map((a) => (
                <tr key={a.id} className="border-t align-top">
                  <td className="px-3 py-2">
                    <div className="font-medium">{a.name}</div>
                    <div className="font-mono text-xs text-muted-foreground">{a.code}</div>
                    {a.description && (
                      <div className="mt-1 text-xs text-muted-foreground">{a.description}</div>
                    )}
                  </td>
                  <td className="px-3 py-2 text-xs">
                    {docTypes.find((d) => d.id === a.document_type_id)?.name ?? "—"}
                  </td>
                  <td className="px-3 py-2 text-xs">
                    {a.current_version ? (
                      <>
                        <div>
                          v{a.current_version.version_number} ·{" "}
                          {a.current_version.model_name}
                        </div>
                        <div className="font-mono text-muted-foreground">
                          {a.current_version.model_identifier}
                        </div>
                      </>
                    ) : (
                      "sin versión"
                    )}
                  </td>
                  <td className="px-3 py-2 text-xs">
                    <button
                      onClick={() => toggleAgent(a)}
                      className={
                        a.active
                          ? "rounded-full bg-emerald-500/15 px-2 py-0.5 text-emerald-600"
                          : "rounded-full bg-muted px-2 py-0.5 text-muted-foreground"
                      }
                    >
                      {a.active ? "Activo" : "Inactivo"}
                    </button>
                  </td>
                  <td className="px-3 py-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => deleteAgent(a)}
                    >
                      Eliminar
                    </Button>
                  </td>
                </tr>
              ))}
              {agents.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-3 py-8 text-center text-muted-foreground">
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
