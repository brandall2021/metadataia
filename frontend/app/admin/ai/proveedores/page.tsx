"use client";

import { FormEvent, useEffect, useState } from "react";
import { Check, ExternalLink, KeyRound, Pencil, Plus, Power, RefreshCw, Save, Trash2 } from "lucide-react";

import { ProviderCatalog } from "@/components/admin/provider-catalog";
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
  type Discovery,
  type ImportResult,
  type Model,
  type Provider,
} from "@/components/admin/ai/common";
import {
  PROVIDER_CATALOG,
  PROVIDER_TYPE_OPTIONS,
  nextAvailableCode,
  presetByCode,
  providerTypeLabel,
  type ProviderPreset,
  type SuggestedModel,
} from "@/lib/ai-providers";
import { apiFetch } from "@/lib/api";

const emptyProviderForm = {
  name: "",
  code: "",
  type: "openai",
  base_url: "",
  api_key: "",
  api_version: "2024-10-21",
};

export default function ProveedoresPage() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [models, setModels] = useState<Model[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [providerForm, setProviderForm] = useState(emptyProviderForm);
  const [formOpen, setFormOpen] = useState(false);
  const [selectedPresetCode, setSelectedPresetCode] = useState<string | null>(null);
  const [suggestedSelection, setSuggestedSelection] = useState<string[]>([]);
  const [discoveries, setDiscoveries] = useState<Record<string, Discovery>>({});
  const [importBusy, setImportBusy] = useState<Record<string, boolean>>({});
  const [editingProviderId, setEditingProviderId] = useState<string | null>(null);
  const [providerDraft, setProviderDraft] = useState({ name: "", base_url: "", type: "openai" });
  const [providerKeys, setProviderKeys] = useState<Record<string, string>>({});
  const [providerResults, setProviderResults] = useState<Record<string, string>>({});
  const [providerBusy, setProviderBusy] = useState<Record<string, boolean>>({});

  const selectedPreset = presetByCode(selectedPresetCode);
  const connectedCodes = new Set(providers.map((provider) => provider.code));

  async function load() {
    try {
      const [p, m] = await Promise.all([
        apiFetch<Provider[]>("/api/admin/ai/providers"),
        apiFetch<Model[]>("/api/admin/ai/models"),
      ]);
      setProviders(p);
      setModels(m);
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

  function importPayload(items: SuggestedModel[]) {
    return items.map((item) => ({
      model_identifier: item.modelIdentifier,
      name: item.name,
      context_window: item.contextWindow ?? null,
      supports_json: item.supportsJson ?? false,
      supports_vision: item.supportsVision ?? false,
    }));
  }

  function applyPreset(preset: ProviderPreset) {
    setSelectedPresetCode(preset.code);
    setFormOpen(true);
    setProviderForm({
      name: preset.name,
      code: nextAvailableCode(preset.code, connectedCodes),
      type: preset.type,
      base_url: preset.baseUrl,
      api_key: "",
      api_version:
        typeof preset.configuration?.api_version === "string"
          ? preset.configuration.api_version
          : "2024-10-21",
    });
    setSuggestedSelection(preset.models.map((model) => model.modelIdentifier));
    setProviderResults((results) => ({ ...results, create: "" }));
  }

  function openCustomForm() {
    setSelectedPresetCode(null);
    setFormOpen(true);
    setProviderForm(emptyProviderForm);
    setSuggestedSelection([]);
  }

  function closeForm() {
    setFormOpen(false);
    setSelectedPresetCode(null);
    setProviderForm(emptyProviderForm);
    setSuggestedSelection([]);
  }

  async function handleCreateProvider(e: FormEvent) {
    e.preventDefault();
    setProviderBusy((b) => ({ ...b, create: true }));
    setError(null);
    try {
      const configuration =
        providerForm.type === "azure-openai"
          ? {
              ...(selectedPreset?.configuration ?? {}),
              api_version: providerForm.api_version.trim() || "2024-10-21",
            }
          : (selectedPreset?.configuration ?? null);
      const created = await apiFetch<Provider>("/api/admin/ai/providers", {
        method: "POST",
        body: JSON.stringify({
          name: providerForm.name.trim(),
          code: providerForm.code.trim(),
          type: providerForm.type,
          base_url: providerForm.base_url.trim() || null,
          api_key: providerForm.api_key.trim() || undefined,
          configuration_json: configuration,
        }),
      });
      const chosen = selectedPreset
        ? selectedPreset.models.filter((model) => suggestedSelection.includes(model.modelIdentifier))
        : [];
      let notice = "Proveedor creado.";
      if (chosen.length > 0) {
        try {
          const imported = await apiFetch<ImportResult>(
            `/api/admin/ai/providers/${created.id}/models/import`,
            { method: "POST", body: JSON.stringify({ models: importPayload(chosen) }) },
          );
          notice = `Proveedor creado con ${imported.created.length} modelo(s)${
            imported.skipped.length ? ` · ${imported.skipped.length} ya existían` : ""
          }.`;
        } catch (importErr) {
          notice = `Proveedor creado, pero falló la importación de modelos: ${
            importErr instanceof Error ? importErr.message : "error desconocido"
          }`;
        }
      }
      setProviderResults((results) => ({ ...results, create: notice }));
      closeForm();
      await load();
    } catch (err) {
      setProviderResults((results) => ({
        ...results,
        create: err instanceof Error ? err.message : "Error al crear proveedor",
      }));
    } finally {
      setProviderBusy((b) => ({ ...b, create: false }));
    }
  }

  async function discoverModels(provider: Provider) {
    setImportBusy((b) => ({ ...b, [provider.id]: true }));
    setError(null);
    try {
      const result = await apiFetch<Discovery>(`/api/admin/ai/providers/${provider.id}/available-models`);
      setDiscoveries((items) => ({ ...items, [provider.id]: result }));
      if (!result.ok) {
        setProviderResults((results) => ({ ...results, [provider.id]: result.message }));
      }
    } catch (err) {
      setProviderResults((results) => ({
        ...results,
        [provider.id]: err instanceof Error ? err.message : "Error al detectar modelos",
      }));
    } finally {
      setImportBusy((b) => ({ ...b, [provider.id]: false }));
    }
  }

  async function importDiscovered(provider: Provider) {
    const found = discoveries[provider.id]?.models ?? [];
    if (found.length === 0) return;
    setImportBusy((b) => ({ ...b, [provider.id]: true }));
    setError(null);
    try {
      const imported = await apiFetch<ImportResult>(
        `/api/admin/ai/providers/${provider.id}/models/import`,
        {
          method: "POST",
          body: JSON.stringify({
            models: found.map((model) => ({ model_identifier: model.id, name: model.id })),
          }),
        },
      );
      setProviderResults((results) => ({
        ...results,
        [provider.id]: `${imported.created.length} modelos importados${
          imported.skipped.length ? ` · ${imported.skipped.length} ya existían` : ""
        }.`,
      }));
      await load();
    } catch (err) {
      setProviderResults((results) => ({
        ...results,
        [provider.id]: err instanceof Error ? err.message : "Error al importar modelos",
      }));
    } finally {
      setImportBusy((b) => ({ ...b, [provider.id]: false }));
    }
  }

  function startEditProvider(provider: Provider) {
    setEditingProviderId(provider.id);
    setProviderDraft({
      name: provider.name,
      base_url: provider.base_url ?? "",
      type: provider.type,
    });
  }

  async function saveProviderDetails(provider: Provider) {
    setProviderBusy((b) => ({ ...b, [provider.id]: true }));
    setError(null);
    try {
      await apiFetch<Provider>(`/api/admin/ai/providers/${provider.id}`, {
        method: "PUT",
        body: JSON.stringify({
          name: providerDraft.name.trim(),
          type: providerDraft.type,
          base_url: providerDraft.base_url.trim() || null,
        }),
      });
      setEditingProviderId(null);
      setProviderResults((results) => ({ ...results, [provider.id]: "Proveedor actualizado." }));
      await load();
    } catch (err) {
      setProviderResults((results) => ({
        ...results,
        [provider.id]: err instanceof Error ? err.message : "Error al actualizar",
      }));
    } finally {
      setProviderBusy((b) => ({ ...b, [provider.id]: false }));
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

  return (
    <div className="space-y-6">
      <ErrorBanner message={error} />

      <Card className="overflow-hidden rounded-[1.5rem] border-slate-200 shadow-[0_14px_30px_-24px_rgba(15,23,42,0.32)]">
        <CardHeader className="space-y-2 border-b border-slate-200 bg-slate-50/80">
          <CardTitle className="flex items-center gap-2 text-lg">
            <KeyRound className="size-4" />
            Proveedores de IA
          </CardTitle>
          <CardDescription>
            Buscá un proveedor, conectalo con tu API key y detectá sus modelos.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6 p-6">
          <ProviderCatalog
            presets={PROVIDER_CATALOG}
            connectedCodes={connectedCodes}
            selectedCode={selectedPresetCode}
            onSelect={applyPreset}
          />
          <Button type="button" variant="outline" onClick={openCustomForm} className="gap-2">
            <Plus className="size-4" />
            Proveedor personalizado
          </Button>

          {formOpen && (
            <div className="space-y-3 rounded-2xl border border-slate-200 bg-slate-50/60 p-4">
              <div className="flex items-center justify-between gap-2">
                <h3 className="text-sm font-medium">
                  {selectedPreset ? `Conectar ${selectedPreset.name}` : "Proveedor personalizado"}
                </h3>
                <Button type="button" variant="ghost" size="xs" onClick={closeForm}>
                  Cerrar
                </Button>
              </div>
              {selectedPreset && (
                <div className="rounded-2xl border border-primary/20 bg-primary/5 p-4">
                  <p className="text-xs leading-5 text-muted-foreground">{selectedPreset.description}</p>
                  <div className="mt-2 flex flex-wrap gap-3 text-xs">
                    <a
                      href={selectedPreset.docsUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1 text-primary hover:underline"
                    >
                      Documentación
                      <ExternalLink className="size-3" />
                    </a>
                    {selectedPreset.keysUrl && (
                      <a
                        href={selectedPreset.keysUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 text-primary hover:underline"
                      >
                        Obtener API key
                        <ExternalLink className="size-3" />
                      </a>
                    )}
                  </div>
                </div>
              )}
              <form onSubmit={handleCreateProvider} className="flex flex-col gap-3 text-sm">
                <div className="grid gap-3 sm:grid-cols-2">
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
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <label className="flex flex-col gap-1.5">
                    <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                      Tipo de API
                    </span>
                    <select
                      className={inputCls}
                      value={providerForm.type}
                      onChange={(e) => setProviderForm({ ...providerForm, type: e.target.value })}
                    >
                      {PROVIDER_TYPE_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
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
                      placeholder={
                        selectedPreset && !selectedPreset.requiresKey
                          ? "No requerida para este proveedor"
                          : "sk-… (podés cargarla después)"
                      }
                    />
                  </label>
                </div>
                <label className="flex flex-col gap-1.5">
                  <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                    Base URL
                  </span>
                  <input
                    className={inputCls}
                    value={providerForm.base_url}
                    onChange={(e) => setProviderForm({ ...providerForm, base_url: e.target.value })}
                    placeholder="https://api.proveedor.com/v1"
                  />
                </label>
                {providerForm.type === "azure-openai" && (
                  <label className="flex flex-col gap-1.5">
                    <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                      API version
                    </span>
                    <input
                      className={inputCls}
                      value={providerForm.api_version}
                      onChange={(e) =>
                        setProviderForm({ ...providerForm, api_version: e.target.value })
                      }
                      placeholder="2024-10-21"
                    />
                    <span className="text-[11px] text-muted-foreground">
                      La Base URL debe incluir <span className="font-mono">/openai/deployments/&lt;deployment&gt;</span>.
                    </span>
                  </label>
                )}
                {selectedPreset && selectedPreset.models.length > 0 && (
                  <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[11px] font-medium uppercase tracking-[0.16em] text-muted-foreground">
                        Modelos a importar ({suggestedSelection.length}/{selectedPreset.models.length})
                      </span>
                      <button
                        type="button"
                        className="text-xs text-primary hover:underline"
                        onClick={() =>
                          setSuggestedSelection(
                            suggestedSelection.length === selectedPreset.models.length
                              ? []
                              : selectedPreset.models.map((model) => model.modelIdentifier),
                          )
                        }
                      >
                        {suggestedSelection.length === selectedPreset.models.length ? "Ninguno" : "Todos"}
                      </button>
                    </div>
                    <div className="mt-2 grid gap-1.5">
                      {selectedPreset.models.map((model) => (
                        <label
                          key={model.modelIdentifier}
                          className="flex items-start gap-2 text-xs text-muted-foreground"
                        >
                          <input
                            type="checkbox"
                            className="mt-0.5"
                            checked={suggestedSelection.includes(model.modelIdentifier)}
                            onChange={(event) =>
                              setSuggestedSelection((prev) =>
                                event.target.checked
                                  ? [...prev, model.modelIdentifier]
                                  : prev.filter((item) => item !== model.modelIdentifier),
                              )
                            }
                          />
                          <span>
                            <span className="font-medium text-foreground">{model.name}</span>
                            {" · "}
                            <span className="font-mono">{model.modelIdentifier}</span>
                          </span>
                        </label>
                      ))}
                    </div>
                    <p className="mt-2 text-[11px] text-muted-foreground">
                      Se crean junto con el proveedor. También podés detectarlos después.
                    </p>
                  </div>
                )}
                <div className="flex flex-wrap items-center gap-2">
                  <Button type="submit" disabled={providerBusy.create}>
                    {providerBusy.create
                      ? "Creando…"
                      : selectedPreset
                        ? `Conectar ${selectedPreset.name}`
                        : "Crear proveedor"}
                  </Button>
                  {providerResults.create && (
                    <p
                      className={`text-xs ${
                        providerResults.create.toLowerCase().includes("creado")
                          ? "text-emerald-600"
                          : "text-destructive"
                      }`}
                    >
                      {providerResults.create}
                    </p>
                  )}
                </div>
              </form>
            </div>
          )}

          <div className="space-y-4">
            <h3 className="text-sm font-medium">Cargados ({providers.length})</h3>
            {providers.length > 0 ? (
              providers.map((p) => {
                const preset = presetByCode(p.code);
                const modelCount = models.filter((model) => model.provider_id === p.id).length;
                const discovery = discoveries[p.id];
                const editing = editingProviderId === p.id;
                const result = providerResults[p.id] ?? "";
                const resultOk =
                  result.startsWith("OK") || /importados|agregados|actualizado|guardada/i.test(result);
                return (
                  <div
                    key={p.id}
                    className="rounded-2xl border border-border/70 bg-background/70 p-4 shadow-sm transition-colors hover:border-primary/25 hover:bg-muted/20"
                  >
                    <div className="flex flex-col gap-3">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="font-medium leading-none">{p.name}</p>
                            <span className="rounded-full bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">
                              {providerTypeLabel(p.type)}
                            </span>
                            <StatusBadge active={p.active} onClick={() => toggleProvider(p)} />
                          </div>
                          <p className="mt-2 font-mono text-xs text-muted-foreground">{p.code}</p>
                          {p.base_url && (
                            <p className="mt-1 break-all text-xs text-muted-foreground">{p.base_url}</p>
                          )}
                          <div className="mt-2 flex flex-wrap items-center gap-3 text-[11px] text-muted-foreground">
                            <span>
                              {modelCount} modelo{modelCount === 1 ? "" : "s"}
                            </span>
                            {preset && !preset.requiresKey && (
                              <span className="inline-flex items-center gap-1 text-emerald-600">
                                <Check className="size-3" />
                                Sin API key
                              </span>
                            )}
                          </div>
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

                      {editing ? (
                        <div className="grid gap-2 rounded-xl border border-slate-200 bg-slate-50 p-3">
                          <input
                            className={inputCls}
                            value={providerDraft.name}
                            onChange={(e) => setProviderDraft({ ...providerDraft, name: e.target.value })}
                            placeholder="Nombre"
                          />
                          <input
                            className={inputCls}
                            value={providerDraft.base_url}
                            onChange={(e) =>
                              setProviderDraft({ ...providerDraft, base_url: e.target.value })
                            }
                            placeholder="Base URL"
                          />
                          <select
                            className={inputCls}
                            value={providerDraft.type}
                            onChange={(e) => setProviderDraft({ ...providerDraft, type: e.target.value })}
                          >
                            {PROVIDER_TYPE_OPTIONS.map((option) => (
                              <option key={option.value} value={option.value}>
                                {option.label}
                              </option>
                            ))}
                          </select>
                          <div className="flex gap-2">
                            <Button size="sm" disabled={providerBusy[p.id]} onClick={() => void saveProviderDetails(p)}>
                              <Save className="size-3.5" />
                              Guardar
                            </Button>
                            <Button size="sm" variant="outline" onClick={() => setEditingProviderId(null)}>
                              Cancelar
                            </Button>
                          </div>
                        </div>
                      ) : (
                        <>
                          <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
                            <label className="flex flex-1 flex-col gap-1">
                              <span className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                                API key {p.api_key_masked ? `(en uso: ${p.api_key_masked})` : "(sin clave)"}
                              </span>
                              <input
                                type="password"
                                className={inputCls}
                                placeholder={
                                  p.api_key_masked
                                    ? "Nueva clave (vacío = mantener)"
                                    : preset && !preset.requiresKey
                                      ? "No requerida"
                                      : "sk-…"
                                }
                                value={providerKeys[p.id] ?? ""}
                                onChange={(e) => setProviderKeys((k) => ({ ...k, [p.id]: e.target.value }))}
                              />
                            </label>
                            <Button size="sm" disabled={providerBusy[p.id]} onClick={() => saveProviderKey(p)}>
                              Guardar clave
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              disabled={providerBusy[p.id]}
                              onClick={() => testProvider(p)}
                            >
                              Probar
                            </Button>
                          </div>
                          <div className="flex flex-wrap gap-1.5">
                            <Button
                              size="xs"
                              variant="outline"
                              disabled={importBusy[p.id]}
                              onClick={() => void discoverModels(p)}
                            >
                              <RefreshCw className="size-3" />
                              Detectar modelos
                            </Button>
                            <Button size="xs" variant="ghost" onClick={() => startEditProvider(p)}>
                              <Pencil className="size-3" />
                              Editar
                            </Button>
                          </div>
                        </>
                      )}

                      {discovery && (
                        <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                          <div className="flex items-center justify-between gap-2">
                            <p className="text-xs text-muted-foreground">{discovery.message}</p>
                            {discovery.ok && discovery.models.length > 0 && (
                              <Button size="xs" disabled={importBusy[p.id]} onClick={() => void importDiscovered(p)}>
                                Importar todos
                              </Button>
                            )}
                          </div>
                          {discovery.models.length > 0 && (
                            <div className="mt-2 flex max-h-28 flex-wrap gap-1 overflow-y-auto">
                              {discovery.models.slice(0, 24).map((model) => (
                                <span
                                  key={model.id}
                                  className="rounded-full border border-slate-200 bg-white px-2 py-0.5 font-mono text-[10px] text-muted-foreground"
                                >
                                  {model.id}
                                </span>
                              ))}
                              {discovery.models.length > 24 && (
                                <span className="text-[10px] text-muted-foreground">
                                  +{discovery.models.length - 24}
                                </span>
                              )}
                            </div>
                          )}
                        </div>
                      )}

                      {result && (
                        <p className={`text-xs ${resultOk ? "text-emerald-600" : "text-muted-foreground"}`}>
                          {result}
                        </p>
                      )}
                    </div>
                  </div>
                );
              })
            ) : (
              <p className="rounded-xl border border-dashed border-border bg-muted/20 p-6 text-center text-sm text-muted-foreground">
                Sin proveedores todavía. Buscá uno en el catálogo para conectarlo.
              </p>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
