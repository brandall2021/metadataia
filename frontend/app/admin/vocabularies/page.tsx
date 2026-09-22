"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { CheckCircle2, FileUp, Languages, Plus, RefreshCw, Save, Search, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { apiFetch, API_URL, getToken, setToken } from "@/lib/api";

type Vocabulary = {
  id: string;
  name: string;
  code: string;
  description: string | null;
  source: string | null;
  active: boolean;
  value_count: number;
};

type VocabularyValue = {
  id: string;
  vocabulary_id: string;
  code: string;
  label: string;
  normalized_value: string | null;
  synonyms: string[];
  active: boolean;
};

type NormalizeResult = {
  found: boolean;
  code: string | null;
  label: string | null;
  normalized_value: string | null;
};

const inputCls =
  "w-full rounded-xl border border-border bg-muted/30 px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground/60 outline-none transition-colors focus:border-ring focus:bg-muted/50 focus:ring-2 focus:ring-ring/30";

const emptyVocabForm = { name: "", code: "", description: "", source: "", active: true };
const emptyValueForm = { code: "", label: "", normalized_value: "", synonyms: "", active: true };

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-border/70 bg-background/75 px-4 py-3 shadow-sm">
      <div className="text-[11px] uppercase tracking-[0.22em] text-muted-foreground">{label}</div>
      <div className="mt-2 text-xl font-semibold tracking-tight">{value}</div>
    </div>
  );
}

function authHeaders(): HeadersInit {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function parseSynonyms(raw: string): string[] {
  return raw
    .split(/[\n,|]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export default function VocabulariesPage() {
  const [vocabularies, setVocabularies] = useState<Vocabulary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [values, setValues] = useState<VocabularyValue[]>([]);
  const [vocabForm, setVocabForm] = useState(emptyVocabForm);
  const [valueForm, setValueForm] = useState(emptyValueForm);
  const [valueDrafts, setValueDrafts] = useState<Record<string, typeof emptyValueForm>>({});
  const [normalizeInput, setNormalizeInput] = useState("");
  const [normalizeResult, setNormalizeResult] = useState<NormalizeResult | null>(null);
  const [importFile, setImportFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [savingVocab, setSavingVocab] = useState(false);
  const [savingValue, setSavingValue] = useState(false);
  const [savingDraft, setSavingDraft] = useState<string | null>(null);

  const selectedVocabulary = useMemo(
    () => vocabularies.find((item) => item.id === selectedId) ?? null,
    [vocabularies, selectedId],
  );

  async function loadVocabularies() {
    const list = await apiFetch<Vocabulary[]>("/api/admin/vocabularies");
    setVocabularies(list);
    if (selectedId && !list.some((item) => item.id === selectedId)) {
      setSelectedId(list[0]?.id ?? null);
    }
  }

  async function loadValues(vocabId: string) {
    const list = await apiFetch<VocabularyValue[]>(`/api/admin/vocabularies/${vocabId}/values`);
    setValues(list);
    setValueDrafts(
      Object.fromEntries(
        list.map((item) => [item.id, { code: item.code, label: item.label, normalized_value: item.normalized_value ?? "", synonyms: item.synonyms.join("\n"), active: item.active }]),
      ),
    );
  }

  async function load(initialSelectedId?: string | null) {
    try {
      const list = await apiFetch<Vocabulary[]>("/api/admin/vocabularies");
      setVocabularies(list);
      const nextSelected = initialSelectedId ?? selectedId ?? list[0]?.id ?? null;
      setSelectedId(nextSelected);
      if (nextSelected) {
        await loadValues(nextSelected);
      } else {
        setValues([]);
        setValueDrafts({});
      }
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al cargar vocabularios");
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleSaveVocabulary(e: FormEvent) {
    e.preventDefault();
    setSavingVocab(true);
    setError(null);
    try {
      const payload = {
        name: vocabForm.name.trim(),
        code: vocabForm.code.trim(),
        description: vocabForm.description.trim() || null,
        source: vocabForm.source.trim() || null,
        active: vocabForm.active,
      };
      if (selectedVocabulary) {
        await apiFetch(`/api/admin/vocabularies/${selectedVocabulary.id}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
        await load(selectedVocabulary.id);
      } else {
        const created = await apiFetch<Vocabulary>("/api/admin/vocabularies", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        setSelectedId(created.id);
        setVocabForm(emptyVocabForm);
        await load(created.id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo guardar el vocabulario");
    } finally {
      setSavingVocab(false);
    }
  }

  async function deleteVocabulary() {
    if (!selectedVocabulary) return;
    if (!window.confirm(`¿Eliminar el vocabulario "${selectedVocabulary.name}"?`)) return;
    setError(null);
    try {
      await apiFetch(`/api/admin/vocabularies/${selectedVocabulary.id}`, { method: "DELETE" });
      setSelectedId(null);
      setVocabForm(emptyVocabForm);
      await load(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo eliminar el vocabulario");
    }
  }

  function selectVocabulary(vocab: Vocabulary) {
    setSelectedId(vocab.id);
    setVocabForm({
      name: vocab.name,
      code: vocab.code,
      description: vocab.description ?? "",
      source: vocab.source ?? "",
      active: vocab.active,
    });
    void loadValues(vocab.id).catch((err) => setError(err instanceof Error ? err.message : "Error al cargar valores"));
  }

  async function saveValue(valueId?: string) {
    if (!selectedVocabulary) return;
    setSavingValue(true);
    setError(null);
    try {
      const source = valueId ? valueDrafts[valueId] : valueForm;
      const payload = {
        code: source.code.trim(),
        label: source.label.trim(),
        normalized_value: source.normalized_value.trim() || null,
        synonyms: parseSynonyms(source.synonyms),
        active: source.active,
      };
      if (valueId) {
        await apiFetch(`/api/admin/vocabularies/${selectedVocabulary.id}/values/${valueId}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
      } else {
        await apiFetch(`/api/admin/vocabularies/${selectedVocabulary.id}/values`, {
          method: "POST",
          body: JSON.stringify(payload),
        });
        setValueForm(emptyValueForm);
      }
      await loadValues(selectedVocabulary.id);
      await loadVocabularies();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo guardar el valor");
    } finally {
      setSavingValue(false);
    }
  }

  async function deleteValue(valueId: string) {
    if (!selectedVocabulary) return;
    if (!window.confirm("¿Eliminar el valor?") ) return;
    setSavingDraft(valueId);
    setError(null);
    try {
      await apiFetch(`/api/admin/vocabularies/${selectedVocabulary.id}/values/${valueId}`, { method: "DELETE" });
      await loadValues(selectedVocabulary.id);
      await loadVocabularies();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo eliminar el valor");
    } finally {
      setSavingDraft(null);
    }
  }

  async function importCsv() {
    if (!selectedVocabulary || !importFile) return;
    setSavingVocab(true);
    setError(null);
    try {
      const body = new FormData();
      body.append("file", importFile);
      const res = await fetch(`${API_URL}/api/admin/vocabularies/${selectedVocabulary.id}/import`, {
        method: "POST",
        headers: authHeaders(),
        body,
      });
      if (res.status === 401) {
        setToken(null);
        if (typeof window !== "undefined") window.location.href = "/login";
        throw new Error("Sesión expirada");
      }
      if (!res.ok) {
        const payload = await res.json().catch(() => ({}));
        throw new Error(payload.detail ?? `Error ${res.status}`);
      }
      await loadValues(selectedVocabulary.id);
      await loadVocabularies();
      setImportFile(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo importar el CSV");
    } finally {
      setSavingVocab(false);
    }
  }

  async function normalizeValue() {
    if (!selectedVocabulary || !normalizeInput.trim()) return;
    setError(null);
    try {
      const result = await apiFetch<NormalizeResult>(`/api/admin/vocabularies/${selectedVocabulary.id}/normalize`, {
        method: "POST",
        body: JSON.stringify({ value: normalizeInput }),
      });
      setNormalizeResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo normalizar");
    }
  }

  const selectedCount = selectedVocabulary?.value_count ?? 0;

  return (
    <div className="space-y-6">
      <section className="rounded-3xl border border-border/70 bg-gradient-to-br from-primary/[0.08] via-background to-muted/40 p-6 shadow-sm">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="space-y-2">
            <span className="inline-flex items-center gap-2 rounded-full border border-primary/15 bg-primary/10 px-3 py-1 text-[11px] uppercase tracking-[0.22em] text-primary">
              <Languages className="size-3.5" />
              Vocabularios
            </span>
            <h1 className="text-3xl font-semibold tracking-tight">Vocabularios</h1>
            <p className="max-w-2xl text-sm leading-6 text-muted-foreground">
              Cargá valores controlados, importá CSV y probá la normalización desde la misma pantalla.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-3 sm:min-w-[360px] lg:w-[420px]">
            <MiniStat label="Vocabularios" value={String(vocabularies.length)} />
            <MiniStat label="Valores" value={String(selectedCount)} />
          </div>
        </div>
      </section>

      {error && <p className="rounded-xl border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}

      <div className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
        <Card className="border-border/70 shadow-sm">
          <CardHeader className="border-b border-border/60 bg-muted/20">
            <CardTitle className="flex items-center gap-2 text-lg">
              <Plus className="size-4" />
              {selectedVocabulary ? "Editar vocabulario" : "Nuevo vocabulario"}
            </CardTitle>
            <CardDescription>Creá o actualizá el vocabulario seleccionado.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 p-4">
            <form onSubmit={handleSaveVocabulary} className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <label className="space-y-1 text-sm">
                  <span>Nombre</span>
                  <input className={inputCls} value={vocabForm.name} onChange={(e) => setVocabForm({ ...vocabForm, name: e.target.value })} required />
                </label>
                <label className="space-y-1 text-sm">
                  <span>Código</span>
                  <input className={inputCls} value={vocabForm.code} onChange={(e) => setVocabForm({ ...vocabForm, code: e.target.value })} required />
                </label>
                <label className="space-y-1 text-sm sm:col-span-2">
                  <span>Descripción</span>
                  <textarea className={`${inputCls} min-h-24 resize-y`} value={vocabForm.description} onChange={(e) => setVocabForm({ ...vocabForm, description: e.target.value })} />
                </label>
                <label className="space-y-1 text-sm">
                  <span>Origen</span>
                  <input className={inputCls} value={vocabForm.source} onChange={(e) => setVocabForm({ ...vocabForm, source: e.target.value })} />
                </label>
                <label className="space-y-1 text-sm">
                  <span>Estado</span>
                  <select className={inputCls} value={vocabForm.active ? "true" : "false"} onChange={(e) => setVocabForm({ ...vocabForm, active: e.target.value === "true" })}>
                    <option value="true">Activo</option>
                    <option value="false">Inactivo</option>
                  </select>
                </label>
              </div>

              <div className="flex flex-wrap gap-2">
                <Button type="submit" className="gap-2" disabled={savingVocab}>
                  {savingVocab ? <span>Guardando…</span> : <><Save className="size-4" /> Guardar vocabulario</>}
                </Button>
                <Button type="button" variant="outline" onClick={() => { setSelectedId(null); setVocabForm(emptyVocabForm); setValues([]); setValueDrafts({}); }}>
                  Nuevo
                </Button>
                {selectedVocabulary && (
                  <Button type="button" variant="outline" className="gap-2" onClick={() => void deleteVocabulary()}>
                    <Trash2 className="size-4" />
                    Eliminar
                  </Button>
                )}
              </div>
            </form>

            <div className="rounded-2xl border border-dashed border-border/70 bg-background p-4">
              <p className="text-sm font-medium">Importar CSV</p>
              <p className="mt-1 text-xs text-muted-foreground">Formato: code,label,synonyms. Los sinónimos se separan con `|`.</p>
              <div className="mt-3 flex flex-col gap-3 sm:flex-row">
                <input className={inputCls} type="file" accept=".csv,text/csv" onChange={(e) => setImportFile(e.target.files?.[0] ?? null)} />
                <Button type="button" className="gap-2" variant="outline" disabled={!selectedVocabulary || !importFile || savingVocab} onClick={() => void importCsv()}>
                  <FileUp className="size-4" />
                  Importar
                </Button>
              </div>
            </div>

            <div className="rounded-2xl border border-dashed border-border/70 bg-background p-4">
              <p className="text-sm font-medium">Probar normalización</p>
              <div className="mt-3 flex flex-col gap-3 sm:flex-row">
                <input className={inputCls} value={normalizeInput} onChange={(e) => setNormalizeInput(e.target.value)} placeholder="Texto a normalizar" />
                <Button type="button" className="gap-2" variant="outline" disabled={!selectedVocabulary || !normalizeInput.trim()} onClick={() => void normalizeValue()}>
                  <Search className="size-4" />
                  Probar
                </Button>
              </div>
              {normalizeResult && (
                <div className="mt-3 rounded-xl bg-muted/30 p-3 text-sm">
                  {normalizeResult.found ? (
                    <p className="flex items-center gap-2 text-emerald-600"><CheckCircle2 className="size-4" /> Coincide con <strong>{normalizeResult.code}</strong> · {normalizeResult.label}</p>
                  ) : (
                    <p className="text-muted-foreground">Sin coincidencia, normalizado a <span className="font-mono">{normalizeResult.normalized_value}</span></p>
                  )}
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card className="border-border/70 shadow-sm">
            <CardHeader className="border-b border-border/60 bg-muted/20">
              <CardTitle>Lista</CardTitle>
              <CardDescription>Seleccioná un vocabulario para editarlo.</CardDescription>
            </CardHeader>
            <CardContent className="p-0">
              <div className="divide-y divide-border/60">
                {vocabularies.map((vocab) => (
                  <button key={vocab.id} type="button" onClick={() => selectVocabulary(vocab)} className={`w-full px-4 py-4 text-left transition-colors ${selectedId === vocab.id ? "bg-primary/5" : "hover:bg-muted/30"}`}>
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <p className="font-medium">{vocab.name}</p>
                        <p className="mt-1 text-xs uppercase tracking-[0.18em] text-muted-foreground font-mono">{vocab.code}</p>
                        <p className="mt-2 text-sm text-muted-foreground line-clamp-2">{vocab.description ?? "Sin descripción"}</p>
                      </div>
                      <div className="text-right text-xs text-muted-foreground">
                        <p>{vocab.value_count} valores</p>
                        <p>{vocab.active ? "Activo" : "Inactivo"}</p>
                      </div>
                    </div>
                  </button>
                ))}
                {vocabularies.length === 0 && <div className="p-6 text-sm text-muted-foreground">Sin vocabularios todavía.</div>}
              </div>
            </CardContent>
          </Card>

          <Card className="border-border/70 shadow-sm">
            <CardHeader className="border-b border-border/60 bg-muted/20">
              <CardTitle>Valores</CardTitle>
              <CardDescription>{selectedVocabulary ? `${selectedVocabulary.name} (${values.length} valores)` : "Seleccioná un vocabulario para ver sus valores."}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 p-4">
              {selectedVocabulary && (
                <form onSubmit={(e) => { e.preventDefault(); void saveValue(); }} className="grid gap-3 rounded-2xl border border-border/60 bg-background p-4">
                  <div className="grid gap-3 sm:grid-cols-2">
                    <input className={inputCls} placeholder="Código" value={valueForm.code} onChange={(e) => setValueForm({ ...valueForm, code: e.target.value })} required />
                    <input className={inputCls} placeholder="Etiqueta" value={valueForm.label} onChange={(e) => setValueForm({ ...valueForm, label: e.target.value })} required />
                    <input className={inputCls} placeholder="Normalizado" value={valueForm.normalized_value} onChange={(e) => setValueForm({ ...valueForm, normalized_value: e.target.value })} />
                    <select className={inputCls} value={valueForm.active ? "true" : "false"} onChange={(e) => setValueForm({ ...valueForm, active: e.target.value === "true" })}>
                      <option value="true">Activo</option>
                      <option value="false">Inactivo</option>
                    </select>
                  </div>
                  <textarea className={`${inputCls} min-h-20 resize-y`} placeholder="Sinónimos separados por coma, barra vertical o salto de línea" value={valueForm.synonyms} onChange={(e) => setValueForm({ ...valueForm, synonyms: e.target.value })} />
                  <Button type="submit" className="gap-2" disabled={savingValue}>
                    <Plus className="size-4" />
                    {savingValue ? "Guardando…" : "Agregar valor"}
                  </Button>
                </form>
              )}

              <div className="space-y-3">
                {values.map((value) => {
                  const draft = valueDrafts[value.id] ?? { code: value.code, label: value.label, normalized_value: value.normalized_value ?? "", synonyms: value.synonyms.join("\n"), active: value.active };
                  return (
                    <div key={value.id} className="rounded-2xl border border-border/60 bg-background p-4">
                      <div className="grid gap-3 sm:grid-cols-2">
                        <input className={inputCls} value={draft.code} onChange={(e) => setValueDrafts((prev) => ({ ...prev, [value.id]: { ...draft, code: e.target.value } }))} />
                        <input className={inputCls} value={draft.label} onChange={(e) => setValueDrafts((prev) => ({ ...prev, [value.id]: { ...draft, label: e.target.value } }))} />
                        <input className={inputCls} value={draft.normalized_value} onChange={(e) => setValueDrafts((prev) => ({ ...prev, [value.id]: { ...draft, normalized_value: e.target.value } }))} />
                        <select className={inputCls} value={draft.active ? "true" : "false"} onChange={(e) => setValueDrafts((prev) => ({ ...prev, [value.id]: { ...draft, active: e.target.value === "true" } }))}>
                          <option value="true">Activo</option>
                          <option value="false">Inactivo</option>
                        </select>
                      </div>
                      <textarea className={`${inputCls} mt-3 min-h-20 resize-y`} value={draft.synonyms} onChange={(e) => setValueDrafts((prev) => ({ ...prev, [value.id]: { ...draft, synonyms: e.target.value } }))} />
                      <div className="mt-3 flex flex-wrap gap-2">
                        <Button type="button" variant="outline" className="gap-2" disabled={savingDraft === value.id} onClick={() => void saveValue(value.id)}>
                          <Save className="size-4" />
                          Guardar
                        </Button>
                        <Button type="button" variant="outline" className="gap-2" disabled={savingDraft === value.id} onClick={() => void deleteValue(value.id)}>
                          <Trash2 className="size-4" />
                          Eliminar
                        </Button>
                        <span className="text-xs text-muted-foreground self-center">{value.active ? "Activo" : "Inactivo"}</span>
                      </div>
                    </div>
                  );
                })}
                {selectedVocabulary && values.length === 0 && <div className="rounded-2xl border border-dashed border-border/70 bg-background p-6 text-sm text-muted-foreground">Sin valores todavía.</div>}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
