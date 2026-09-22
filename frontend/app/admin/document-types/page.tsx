"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { CheckSquare, Layers3, Plus, Save, ShieldCheck, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { apiFetch } from "@/lib/api";

type Agent = { id: string; name: string; code: string };
type Field = {
  id: string;
  schema_code: string;
  element: string;
  qualifier: string | null;
  display_name: string | null;
  active: boolean;
};
type DocumentTypeField = {
  id: string;
  schema_id: string;
  schema_code: string;
  element: string;
  qualifier: string | null;
  display_name: string | null;
  data_type: string;
  required: boolean;
  repeatable: boolean;
  ai_extractable: boolean;
  vocabulary_id: string | null;
  vocabulary_code: string | null;
  required_override: boolean | null;
  order_index: number | null;
  extraction_instruction: string | null;
};
type DocumentType = {
  id: string;
  name: string;
  code: string;
  description: string | null;
  default_agent_id: string | null;
  default_agent_code: string | null;
  default_agent_name: string | null;
  active: boolean;
  ocr_languages: string | null;
  created_at: string;
  updated_at: string;
  fields: DocumentTypeField[];
};

const inputCls =
  "w-full rounded-xl border border-border bg-muted/30 px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground/60 outline-none transition-colors focus:border-ring focus:bg-muted/50 focus:ring-2 focus:ring-ring/30";

const emptyForm = {
  name: "",
  code: "",
  description: "",
  default_agent_id: "",
  active: true,
  ocr_languages: "spa+eng",
};

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-border/70 bg-background/75 px-4 py-3 shadow-sm">
      <div className="text-[11px] uppercase tracking-[0.22em] text-muted-foreground">{label}</div>
      <div className="mt-2 text-xl font-semibold tracking-tight">{value}</div>
    </div>
  );
}

export default function DocumentTypesPage() {
  const [types, setTypes] = useState<DocumentType[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedType, setSelectedType] = useState<DocumentType | null>(null);
  const [fields, setFields] = useState<Field[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [form, setForm] = useState(emptyForm);
  const [fieldSelection, setFieldSelection] = useState<Record<string, { required_override: boolean; order_index: number }>>({});
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [savingFields, setSavingFields] = useState(false);

  async function load(initialSelectedId?: string | null) {
    try {
      const [typesData, fieldsData, agentsData] = await Promise.all([
        apiFetch<DocumentType[]>("/api/admin/document-types"),
        apiFetch<Field[]>("/api/admin/metadata/fields"),
        apiFetch<Agent[]>("/api/admin/ai/agents"),
      ]);
      setTypes(typesData);
      setFields(fieldsData);
      setAgents(agentsData);
      setError(null);
      const nextSelected = initialSelectedId ?? selectedId ?? typesData[0]?.id ?? null;
      setSelectedId(nextSelected);
      if (nextSelected) {
        await loadDetail(nextSelected);
      } else {
        setSelectedType(null);
        setFieldSelection({});
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al cargar tipos documentales");
    }
  }

  async function loadDetail(id: string) {
    const detail = await apiFetch<DocumentType>(`/api/admin/document-types/${id}`);
    setSelectedType(detail);
    setForm({
      name: detail.name,
      code: detail.code,
      description: detail.description ?? "",
      default_agent_id: detail.default_agent_id ?? "",
      active: detail.active,
      ocr_languages: detail.ocr_languages ?? "",
    });
    const next: Record<string, { required_override: boolean; order_index: number }> = {};
    detail.fields.forEach((field, index) => {
      next[field.id] = { required_override: field.required_override ?? field.required, order_index: field.order_index ?? index };
    });
    setFieldSelection(next);
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function startNew() {
    setSelectedId(null);
    setSelectedType(null);
    setForm(emptyForm);
    setFieldSelection({});
  }

  function selectType(type: DocumentType) {
    setSelectedId(type.id);
    void loadDetail(type.id).catch((err) => setError(err instanceof Error ? err.message : "Error al cargar detalle"));
  }

  async function saveType(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const payload = {
        name: form.name.trim(),
        code: form.code.trim(),
        description: form.description.trim() || null,
        default_agent_id: form.default_agent_id || null,
        active: form.active,
        ocr_languages: form.ocr_languages.trim() || null,
      };
      if (selectedType) {
        await apiFetch(`/api/admin/document-types/${selectedType.id}`, { method: "PUT", body: JSON.stringify(payload) });
        await load(selectedType.id);
      } else {
        const created = await apiFetch<DocumentType>("/api/admin/document-types", { method: "POST", body: JSON.stringify(payload) });
        await load(created.id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo guardar el tipo documental");
    } finally {
      setSaving(false);
    }
  }

  async function deleteType() {
    if (!selectedType) return;
    if (!window.confirm(`¿Eliminar el tipo documental "${selectedType.name}"?`)) return;
    setError(null);
    try {
      await apiFetch(`/api/admin/document-types/${selectedType.id}`, { method: "DELETE" });
      startNew();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo eliminar el tipo documental");
    }
  }

  function toggleField(fieldId: string) {
    setFieldSelection((prev) => {
      const next = { ...prev };
      if (next[fieldId]) delete next[fieldId];
      else next[fieldId] = { required_override: false, order_index: Object.keys(next).length };
      return next;
    });
  }

  function setRequiredOverride(fieldId: string, required_override: boolean) {
    setFieldSelection((prev) => ({
      ...prev,
      [fieldId]: { ...(prev[fieldId] ?? { required_override: false, order_index: Object.keys(prev).length }), required_override },
    }));
  }

  async function saveFields() {
    if (!selectedType) return;
    setSavingFields(true);
    setError(null);
    try {
      const payload = {
        fields: Object.entries(fieldSelection)
          .sort((a, b) => a[1].order_index - b[1].order_index)
          .map(([field_id, data], index) => ({ field_id, required_override: data.required_override, order_index: index })),
      };
      await apiFetch(`/api/admin/document-types/${selectedType.id}/fields`, { method: "PUT", body: JSON.stringify(payload) });
      await load(selectedType.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudieron guardar los campos");
    } finally {
      setSavingFields(false);
    }
  }

  const selectedFields = selectedType?.fields.length ?? 0;

  const fieldOptions = useMemo(() => fields.filter((field) => field.active), [fields]);

  return (
    <div className="space-y-6">
      <section className="rounded-3xl border border-border/70 bg-gradient-to-br from-primary/[0.08] via-background to-muted/40 p-6 shadow-sm">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="space-y-2">
            <span className="inline-flex items-center gap-2 rounded-full border border-primary/15 bg-primary/10 px-3 py-1 text-[11px] uppercase tracking-[0.22em] text-primary">
              <Layers3 className="size-3.5" />
              Tipos documentales
            </span>
            <h1 className="text-3xl font-semibold tracking-tight">Tipos documentales</h1>
            <p className="max-w-2xl text-sm leading-6 text-muted-foreground">
              Armá perfiles documentales y asignales campos, agente IA y idiomas OCR desde una sola pantalla.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-3 sm:min-w-[360px] lg:w-[420px]">
            <MiniStat label="Tipos" value={String(types.length)} />
            <MiniStat label="Campos" value={String(selectedFields)} />
          </div>
        </div>
      </section>

      {error && <p className="rounded-xl border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}

      <div className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
        <Card className="border-border/70 shadow-sm">
          <CardHeader className="border-b border-border/60 bg-muted/20">
            <CardTitle className="flex items-center gap-2 text-lg">
              <Plus className="size-4" />
              {selectedType ? "Editar tipo" : "Nuevo tipo"}
            </CardTitle>
            <CardDescription>Definí el perfil documental y el agente por defecto.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 p-4">
            <form onSubmit={saveType} className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <label className="space-y-1 text-sm">
                  <span>Nombre</span>
                  <input className={inputCls} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
                </label>
                <label className="space-y-1 text-sm">
                  <span>Código</span>
                  <input className={inputCls} value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} required />
                </label>
                <label className="space-y-1 text-sm sm:col-span-2">
                  <span>Descripción</span>
                  <textarea className={`${inputCls} min-h-24 resize-y`} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
                </label>
                <label className="space-y-1 text-sm">
                  <span>Agente IA</span>
                  <select className={inputCls} value={form.default_agent_id} onChange={(e) => setForm({ ...form, default_agent_id: e.target.value })}>
                    <option value="">Sin agente</option>
                    {agents.map((agent) => (
                      <option key={agent.id} value={agent.id}>
                        {agent.name} ({agent.code})
                      </option>
                    ))}
                  </select>
                </label>
                <label className="space-y-1 text-sm">
                  <span>Estado</span>
                  <select className={inputCls} value={form.active ? "true" : "false"} onChange={(e) => setForm({ ...form, active: e.target.value === "true" })}>
                    <option value="true">Activo</option>
                    <option value="false">Inactivo</option>
                  </select>
                </label>
                <label className="space-y-1 text-sm sm:col-span-2">
                  <span>Idiomas OCR</span>
                  <input className={inputCls} value={form.ocr_languages} onChange={(e) => setForm({ ...form, ocr_languages: e.target.value })} placeholder="spa+eng" />
                </label>
              </div>

              <div className="flex flex-wrap gap-2">
                <Button type="submit" className="gap-2" disabled={saving}>
                  {saving ? <span>Guardando…</span> : <><Save className="size-4" /> Guardar tipo</>}
                </Button>
                <Button type="button" variant="outline" onClick={startNew}>Nuevo</Button>
                {selectedType && (
                  <Button type="button" variant="outline" className="gap-2" onClick={() => void deleteType()}>
                    <Trash2 className="size-4" />
                    Eliminar
                  </Button>
                )}
              </div>
            </form>
          </CardContent>
        </Card>

        <Card className="border-border/70 shadow-sm">
          <CardHeader className="border-b border-border/60 bg-muted/20">
            <CardTitle>Listado</CardTitle>
            <CardDescription>Elegí un tipo para editarlo y asignar sus campos.</CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            <div className="divide-y divide-border/60">
              {types.map((type) => (
                <button key={type.id} type="button" onClick={() => selectType(type)} className={`w-full px-4 py-4 text-left transition-colors ${selectedId === type.id ? "bg-primary/5" : "hover:bg-muted/30"}`}>
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <p className="font-medium">{type.name}</p>
                      <p className="mt-1 text-xs uppercase tracking-[0.18em] text-muted-foreground font-mono">{type.code}</p>
                      <p className="mt-2 text-sm text-muted-foreground line-clamp-2">{type.description ?? "Sin descripción"}</p>
                    </div>
                    <div className="text-right text-xs text-muted-foreground">
                      <p>{type.default_agent_name ?? "Sin agente"}</p>
                      <p>{type.active ? "Activo" : "Inactivo"}</p>
                    </div>
                  </div>
                </button>
              ))}
              {types.length === 0 && <div className="p-6 text-sm text-muted-foreground">Sin tipos documentales todavía.</div>}
            </div>
          </CardContent>
        </Card>
      </div>

      <Card className="border-border/70 shadow-sm">
        <CardHeader className="border-b border-border/60 bg-muted/20">
          <CardTitle className="flex items-center gap-2 text-lg">
            <ShieldCheck className="size-4" />
            Campos del tipo
          </CardTitle>
          <CardDescription>{selectedType ? `${selectedType.name} (${selectedType.fields.length} campos)` : "Seleccioná un tipo para editar sus campos."}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4 p-4">
          {selectedType ? (
            <>
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {fieldOptions.map((field) => {
                  const selected = Boolean(fieldSelection[field.id]);
                  const data = fieldSelection[field.id] ?? { required_override: false, order_index: 0 };
                  return (
                    <label key={field.id} className={`rounded-2xl border px-4 py-3 text-sm ${selected ? "border-primary/40 bg-primary/5" : "border-border/60 bg-background"}`}>
                      <div className="flex items-start gap-2">
                        <input type="checkbox" className="mt-1" checked={selected} onChange={() => toggleField(field.id)} />
                        <div className="min-w-0 flex-1">
                          <p className="font-medium">{field.display_name ?? field.element}</p>
                          <p className="text-xs text-muted-foreground">{field.schema_code} · {field.element}{field.qualifier ? `.${field.qualifier}` : ""}</p>
                          {selected && (
                            <div className="mt-3 flex items-center gap-2">
                              <input type="checkbox" checked={data.required_override} onChange={(e) => setRequiredOverride(field.id, e.target.checked)} />
                              <span className="text-xs text-muted-foreground">Forzar requerido</span>
                            </div>
                          )}
                        </div>
                      </div>
                    </label>
                  );
                })}
              </div>
              <div className="flex flex-wrap gap-2">
                <Button type="button" className="gap-2" disabled={savingFields} onClick={() => void saveFields()}>
                  <Save className="size-4" />
                  {savingFields ? "Guardando…" : "Guardar campos"}
                </Button>
              </div>
            </>
          ) : (
            <div className="rounded-2xl border border-dashed border-border/70 bg-background p-6 text-sm text-muted-foreground">
              No hay tipo seleccionado.
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
