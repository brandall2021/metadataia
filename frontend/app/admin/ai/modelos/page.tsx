"use client";

import { FormEvent, useEffect, useState } from "react";
import { Cpu, Save } from "lucide-react";

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
  type Model,
  type Provider,
} from "@/components/admin/ai/common";
import {
  presetByCode,
  type SuggestedModel,
} from "@/lib/ai-providers";
import { apiFetch } from "@/lib/api";

const emptyModelForm = {
  provider_id: "",
  name: "",
  model_identifier: "",
  context_window: "",
  supports_json: true,
  supports_vision: false,
  temperature_default: "",
  max_tokens_default: "",
  active: true,
};

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
        <StatusBadge active={model.active} onClick={() => onToggle(model)} />
      </div>
      <div className="mt-4 flex flex-wrap gap-1.5 text-xs text-muted-foreground">
        {model.context_window != null && (
          <span className="rounded-full bg-muted/40 px-2.5 py-1">{Math.round(model.context_window / 1000)}k</span>
        )}
        {model.supports_json && <span className="rounded-full bg-muted/40 px-2.5 py-1">JSON</span>}
        {model.supports_vision && <span className="rounded-full bg-muted/40 px-2.5 py-1">Visión</span>}
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <Button size="sm" variant="outline" disabled={busy} onClick={() => onSelect(model)}>
          Editar
        </Button>
        <Button size="sm" variant="outline" disabled={busy} onClick={() => onTest(model)}>
          Probar
        </Button>
        <Button size="sm" variant="destructive" disabled={busy} onClick={() => onDelete(model)}>
          Eliminar
        </Button>
      </div>
    </div>
  );
}

export default function ModelosPage() {
  const [models, setModels] = useState<Model[]>([]);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [modelForm, setModelForm] = useState(emptyModelForm);
  const [selectedModelId, setSelectedModelId] = useState<string | null>(null);
  const [modelBusy, setModelBusy] = useState<Record<string, boolean>>({});
  const [modelTest, setModelTest] = useState<{ ok: boolean; message: string; time_ms: number } | null>(null);

  const selectedModel = selectedModelId
    ? models.find((model) => model.id === selectedModelId) ?? null
    : null;
  const selectedProvider = providers.find((provider) => provider.id === modelForm.provider_id);
  const modelSuggestions = (presetByCode(selectedProvider?.code)?.models ?? []).filter(
    (suggestion) =>
      !models.some(
        (model) =>
          model.provider_id === selectedProvider?.id &&
          model.model_identifier === suggestion.modelIdentifier,
      ),
  );

  async function load() {
    try {
      const [m, p] = await Promise.all([
        apiFetch<Model[]>("/api/admin/ai/models"),
        apiFetch<Provider[]>("/api/admin/ai/providers"),
      ]);
      setModels(m);
      setProviders(p);
      setModelForm((prev) => (prev.provider_id ? prev : { ...prev, provider_id: p[0]?.id ?? "" }));
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
    setModelForm({ ...emptyModelForm, provider_id: providers[0]?.id ?? "" });
    setModelTest(null);
  }

  function applyModelSuggestion(suggestion: SuggestedModel) {
    setModelForm((prev) => ({
      ...prev,
      name: suggestion.name,
      model_identifier: suggestion.modelIdentifier,
      context_window: suggestion.contextWindow?.toString() ?? "",
      supports_json: suggestion.supportsJson ?? false,
      supports_vision: suggestion.supportsVision ?? false,
    }));
  }

  async function handleSaveModel(e: FormEvent) {
    e.preventDefault();
    if (!modelForm.provider_id) {
      setError("Seleccioná un proveedor primero (conectá uno en la pestaña Proveedores)");
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
      const res = await apiFetch<{ ok: boolean; message: string; time_ms: number }>(
        `/api/admin/ai/models/${model.id}/test`,
        { method: "POST" },
      );
      setModelTest(res);
      selectModel(model);
    } catch (err) {
      setModelTest({ ok: false, message: err instanceof Error ? err.message : "Error al probar", time_ms: 0 });
    } finally {
      setModelBusy((b) => ({ ...b, [model.id]: false }));
    }
  }

  return (
    <div className="space-y-6">
      <ErrorBanner message={error} />

      <Card className="overflow-hidden rounded-[1.75rem] border-border/70 shadow-sm">
        <CardHeader className="space-y-2 border-b border-slate-200 bg-slate-50/80">
          <CardTitle className="flex items-center gap-2 text-lg">
            <Cpu className="size-4" />
            Modelos
          </CardTitle>
          <CardDescription>
            Crea, edita, prueba y desactiva los modelos que usan los agentes.
          </CardDescription>
        </CardHeader>
        <CardContent className="p-6">
          <div className="grid gap-6 xl:grid-cols-[minmax(360px,0.96fr)_1.04fr]">
            <div className="space-y-3">
              <h3 className="text-sm font-medium">{selectedModelId ? "Editar modelo" : "Nuevo modelo"}</h3>
              {selectedModel && (
                <div className="rounded-2xl border border-primary/20 bg-primary/5 px-4 py-3 text-sm shadow-sm">
                  <p className="text-[11px] uppercase tracking-[0.2em] text-primary/80">Editando</p>
                  <p className="mt-1 font-medium text-foreground">{selectedModel.name}</p>
                  <p className="mt-2 font-mono text-xs text-muted-foreground">
                    {selectedModel.provider_name} · {selectedModel.model_identifier}
                  </p>
                </div>
              )}
              <form onSubmit={handleSaveModel} className="flex flex-col gap-3 text-sm">
                <label className="flex flex-col gap-1.5">
                  <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                    Proveedor
                  </span>
                  <select
                    className={inputCls}
                    value={modelForm.provider_id}
                    onChange={(e) => setModelForm({ ...modelForm, provider_id: e.target.value })}
                    required
                  >
                    <option value="" disabled>
                      Seleccionar…
                    </option>
                    {providers.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name} ({p.code})
                      </option>
                    ))}
                  </select>
                </label>
                {!selectedModelId && modelSuggestions.length > 0 && (
                  <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                    <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-muted-foreground">
                      Sugerencias de {selectedProvider?.name}
                    </p>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {modelSuggestions.map((suggestion) => (
                        <button
                          key={suggestion.modelIdentifier}
                          type="button"
                          onClick={() => applyModelSuggestion(suggestion)}
                          className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] text-muted-foreground transition-colors hover:border-primary/30 hover:text-primary"
                        >
                          {suggestion.name}
                          {suggestion.contextWindow ? ` · ${Math.round(suggestion.contextWindow / 1000)}k` : ""}
                          {suggestion.supportsVision ? " · visión" : ""}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
                <label className="flex flex-col gap-1.5">
                  <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                    Nombre
                  </span>
                  <input
                    className={inputCls}
                    value={modelForm.name}
                    onChange={(e) => setModelForm({ ...modelForm, name: e.target.value })}
                    required
                  />
                </label>
                <label className="flex flex-col gap-1.5">
                  <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                    Identificador
                  </span>
                  <input
                    className={inputCls}
                    value={modelForm.model_identifier}
                    onChange={(e) => setModelForm({ ...modelForm, model_identifier: e.target.value })}
                    required
                  />
                </label>
                <div className="grid grid-cols-2 gap-3">
                  <label className="flex flex-col gap-1.5">
                    <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                      Contexto
                    </span>
                    <input
                      className={inputCls}
                      type="number"
                      value={modelForm.context_window}
                      onChange={(e) => setModelForm({ ...modelForm, context_window: e.target.value })}
                      placeholder="8192"
                    />
                  </label>
                  <div className="grid grid-cols-2 gap-3">
                    <label className="flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm">
                      <input
                        type="checkbox"
                        checked={modelForm.supports_json}
                        onChange={(e) => setModelForm({ ...modelForm, supports_json: e.target.checked })}
                      />
                      JSON
                    </label>
                    <label className="flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm">
                      <input
                        type="checkbox"
                        checked={modelForm.supports_vision}
                        onChange={(e) => setModelForm({ ...modelForm, supports_vision: e.target.checked })}
                      />
                      Visión
                    </label>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <label className="flex flex-col gap-1.5">
                    <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                      Temp. por defecto
                    </span>
                    <input
                      className={inputCls}
                      type="number"
                      step="0.1"
                      value={modelForm.temperature_default}
                      onChange={(e) => setModelForm({ ...modelForm, temperature_default: e.target.value })}
                      placeholder="0.0"
                    />
                  </label>
                  <label className="flex flex-col gap-1.5">
                    <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                      Max tokens
                    </span>
                    <input
                      className={inputCls}
                      type="number"
                      value={modelForm.max_tokens_default}
                      onChange={(e) => setModelForm({ ...modelForm, max_tokens_default: e.target.value })}
                      placeholder="4096"
                    />
                  </label>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button type="submit" disabled={saving} className="gap-2">
                    {saving ? (
                      "Guardando…"
                    ) : (
                      <>
                        <Save className="size-4" /> Guardar modelo
                      </>
                    )}
                  </Button>
                  <Button type="button" variant="outline" onClick={clearModelForm}>
                    Nuevo
                  </Button>
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
  );
}
