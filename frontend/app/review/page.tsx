"use client";

import { FormEvent, useEffect, useMemo, useState, type ReactNode } from "react";
import {
  ArrowRight,
  CheckCircle2,
  Edit3,
  FileText,
  Loader2,
  MessageSquareQuote,
  PenLine,
  Plus,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  ThumbsDown,
  Trash2,
  type LucideIcon,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { apiFetch } from "@/lib/api";
import * as documentHelpers from "@/lib/documents";

type DocumentListItem = {
  id: string;
  original_filename: string | null;
  mime_type: string | null;
  file_size: number | null;
  sha256: string | null;
  page_count: number | null;
  needs_ocr: boolean;
  status: string;
  created_at: string;
};

type DocumentPage = {
  id: string;
  page_number: number;
  text: string | null;
  text_length: number | null;
  ocr_used: boolean;
};

type Job = {
  id: string;
  job_type: string;
  status: string;
  progress: number | null;
  started_at: string | null;
  finished_at: string | null;
  error_message: string | null;
  metadata_json: Record<string, unknown>;
};

type MetadataRecord = {
  id: string;
  metadata_field_id: string;
  field: string;
  display_name: string;
  value: string | null;
  language: string | null;
  confidence: number | null;
  source: string | null;
  source_page: number | null;
  source_text: string | null;
  extraction_run_id: string | null;
  normalized: boolean;
  validated: boolean;
  manually_modified: boolean;
};

type MetadataRun = {
  id: string;
  agent_id: string | null;
  agent_version_id: string | null;
  model_id: string | null;
  prompt_hash: string | null;
  started_at: string | null;
  finished_at: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  status: string;
  raw_response_storage_path: string | null;
  error_message: string | null;
  summary: Record<string, unknown>;
};

type MetadataCollection = {
  document_id: string;
  document_status: string;
  runs: MetadataRun[];
  records: MetadataRecord[];
};

type ValidationResult = {
  id: string;
  validator_type: string;
  status: string;
  errors_json: unknown[] | null;
  warnings_json: unknown[] | null;
  created_at: string | null;
};

type ValidationCollection = {
  document_id: string;
  document_status: string;
  results: ValidationResult[];
};

type Deposition = {
  id: string;
  document_id: string;
  repository_id: string | null;
  collection_id: string | null;
  external_item_id: string | null;
  handle: string | null;
  status: string;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
};

type DocTypeField = {
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

type DocTypeDetail = {
  id: string;
  name: string;
  code: string;
  description: string | null;
  default_agent_id: string | null;
  default_agent_code: string | null;
  default_agent_name: string | null;
  active: boolean;
  created_at: string;
  updated_at: string;
  fields: DocTypeField[];
};

type ReviewDetail = {
  detail: DocumentListItem & { document_type_id: string | null; pages: DocumentPage[]; analysis: { total_text_length: number; needs_ocr: boolean; status: string }; jobs: Job[] };
  metadata: MetadataCollection;
  validation: ValidationCollection;
  depositions: Deposition[];
  docType: DocTypeDetail | null;
};

const inputCls =
  "w-full rounded-xl border border-border bg-muted/30 px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground/60 outline-none transition-colors focus:border-ring focus:bg-muted/50 focus:ring-2 focus:ring-ring/30";

function Stat({ label, value, icon: Icon }: { label: string; value: string; icon: LucideIcon }) {
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

function Badge({ tone, children }: { tone: string; children: ReactNode }) {
  const styles: Record<string, string> = {
    amber: "bg-amber-500/15 text-amber-700 dark:text-amber-300",
    blue: "bg-blue-500/15 text-blue-700 dark:text-blue-300",
    cyan: "bg-cyan-500/15 text-cyan-700 dark:text-cyan-300",
    violet: "bg-violet-500/15 text-violet-700 dark:text-violet-300",
    emerald: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300",
    green: "bg-green-500/15 text-green-700 dark:text-green-300",
    primary: "bg-primary/15 text-primary",
    rose: "bg-rose-500/15 text-rose-700 dark:text-rose-300",
    slate: "bg-muted text-muted-foreground",
  };
  return <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium ${styles[tone] ?? styles.slate}`}>{children}</span>;
}

function Section({ title, description, children }: { title: string; description?: string; children: ReactNode }) {
  return (
    <Card className="border-border/70 shadow-sm">
      <CardHeader className="space-y-2 border-b border-border/60 bg-muted/20">
        <CardTitle className="text-lg">{title}</CardTitle>
        {description && <CardDescription>{description}</CardDescription>}
      </CardHeader>
      <CardContent className="p-0">{children}</CardContent>
    </Card>
  );
}

function formatDate(value: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleString("es-AR", { dateStyle: "short", timeStyle: "short" });
}

function formatStatusTone(status: string): string {
  return documentHelpers.documentStatusMeta(status).tone;
}

export default function ReviewPage() {
  const [documents, setDocuments] = useState<DocumentListItem[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [review, setReview] = useState<ReviewDetail | null>(null);
  const [loadingDocs, setLoadingDocs] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [saving, setSaving] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [newRecord, setNewRecord] = useState({ field_id: "", value: "", confidence: "0.8" });
  const [updateDrafts, setUpdateDrafts] = useState<Record<string, string>>({});

  const selectedDoc = review?.detail ?? null;
  const meta = selectedDoc ? documentHelpers.documentStatusMeta(selectedDoc.status) : null;
  const fieldOptions = review?.docType?.fields ?? [];
  const existingRecordIds = new Set(review?.metadata.records.map((r) => r.metadata_field_id) ?? []);
  const missingFields = fieldOptions.filter((field) => !existingRecordIds.has(field.id));
  const pendingDocs = documents.filter((doc) => doc.status === "NEEDS_REVIEW").length;

  async function loadDocuments() {
    try {
      setLoadingDocs(true);
      const docs = await apiFetch<DocumentListItem[]>("/api/documents");
      setDocuments(docs);
      setError(null);
      if (!selectedId && docs[0]) setSelectedId(docs[0].id);
      if (selectedId && !docs.some((doc) => doc.id === selectedId) && docs[0]) setSelectedId(docs[0].id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al cargar documentos");
    } finally {
      setLoadingDocs(false);
    }
  }

  async function loadDetail(id: string) {
    setLoadingDetail(true);
    try {
      const detail = await apiFetch<ReviewDetail["detail"]>(`/api/documents/${id}`);
      const [metadata, validation, depositions, docType] = await Promise.all([
        apiFetch<MetadataCollection>(`/api/documents/${id}/metadata`),
        apiFetch<ValidationCollection>(`/api/documents/${id}/validation`),
        apiFetch<Deposition[]>(`/api/documents/${id}/depositions`),
        detail.document_type_id
          ? apiFetch<DocTypeDetail>(`/api/admin/document-types/${detail.document_type_id}`).catch(() => null)
          : Promise.resolve(null),
      ]);
      setReview({ detail, metadata, validation, depositions, docType });
      setUpdateDrafts((prev) => {
        const next: Record<string, string> = {};
        for (const record of metadata.records) next[record.id] = prev[record.id] ?? record.value ?? "";
        return next;
      });
      setNewRecord({ field_id: "", value: "", confidence: "0.8" });
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al cargar la revisión");
      setReview(null);
    } finally {
      setLoadingDetail(false);
    }
  }

  useEffect(() => {
    loadDocuments();
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    void loadDetail(selectedId);
  }, [selectedId]);

  useEffect(() => {
    if (!selectedId || !review) return;
    const timer = window.setInterval(() => void loadDetail(selectedId), 5000);
    return () => window.clearInterval(timer);
  }, [selectedId, review?.detail.status, review?.metadata.records.length]);

  async function saveRecord(recordId: string) {
    if (!selectedId) return;
    setSaving(recordId);
    setError(null);
    try {
      await apiFetch(`/api/documents/${selectedId}/records/${recordId}`, {
        method: "PUT",
        body: JSON.stringify({ value: updateDrafts[recordId] ?? "" }),
      });
      await loadDetail(selectedId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo guardar el campo");
    } finally {
      setSaving(null);
    }
  }

  async function deleteRecord(recordId: string) {
    if (!selectedId) return;
    if (!window.confirm("¿Eliminar este metadato?")) return;
    setSaving(recordId);
    setError(null);
    try {
      await apiFetch(`/api/documents/${selectedId}/records/${recordId}`, { method: "DELETE" });
      await loadDetail(selectedId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo eliminar el campo");
    } finally {
      setSaving(null);
    }
  }

  async function createRecord(e: FormEvent) {
    e.preventDefault();
    if (!selectedId) return;
    setSaving("create");
    setError(null);
    try {
      await apiFetch(`/api/documents/${selectedId}/records`, {
        method: "POST",
        body: JSON.stringify({
          field_id: newRecord.field_id,
          value: newRecord.value,
          confidence: newRecord.confidence ? Number(newRecord.confidence) : null,
        }),
      });
      await loadDetail(selectedId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo crear el campo");
    } finally {
      setSaving(null);
    }
  }

  async function reviewAction(action: "approve" | "reject") {
    if (!selectedId) return;
    setSaving(action);
    setError(null);
    try {
      await apiFetch(`/api/documents/${selectedId}/${action}`, { method: "POST" });
      await loadDocuments();
      await loadDetail(selectedId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo completar la revisión");
    } finally {
      setSaving(null);
    }
  }

  const totalRecords = review?.metadata.records.length ?? 0;
  const validatedRecords = review?.metadata.records.filter((r) => r.validated).length ?? 0;

  return (
    <div className="space-y-6">
      <section className="rounded-3xl border border-border/70 bg-gradient-to-br from-primary/[0.08] via-background to-muted/40 p-6 shadow-sm">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-2xl space-y-3">
            <span className="inline-flex items-center gap-2 rounded-full border border-primary/15 bg-primary/10 px-3 py-1 text-[11px] uppercase tracking-[0.22em] text-primary">
              <Edit3 className="size-3.5" />
              Revisión humana
            </span>
            <div className="space-y-2">
              <h1 className="text-3xl font-semibold tracking-tight">Revisión</h1>
              <p className="max-w-2xl text-sm leading-6 text-muted-foreground">
                Formulario dinámico, evidencia y confianza por campo. Corregí valores,
                completá faltantes y aprobá el documento cuando la validación esté lista.
              </p>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3 sm:min-w-[360px] lg:w-[420px]">
            <Stat label="Pendientes" value={`${pendingDocs}`} icon={FileText} />
            <Stat label="Registros" value={`${totalRecords}`} icon={MessageSquareQuote} />
            <Stat label="Validados" value={`${validatedRecords}`} icon={CheckCircle2} />
            <Stat label="Campos faltantes" value={`${missingFields.length}`} icon={Plus} />
          </div>
        </div>
      </section>

      {error && (
        <p className="rounded-xl border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </p>
      )}

      <div className="grid gap-6 xl:grid-cols-[minmax(360px,0.92fr)_1.08fr]">
        <div className="space-y-6">
          <Section title="Documentos" description={loadingDocs ? "Cargando lista…" : `${documents.length} documentos disponibles`}>
            <div className="max-h-[720px] divide-y overflow-auto">
              {documents.map((doc) => {
                const statusMeta = documentHelpers.documentStatusMeta(doc.status);
                const selected = doc.id === selectedId;
                return (
                  <button
                    key={doc.id}
                    className={`flex w-full items-start gap-3 px-4 py-3 text-left transition-colors ${selected ? "bg-primary/5" : "hover:bg-muted/30"}`}
                    onClick={() => setSelectedId(doc.id)}
                  >
                    <div className="mt-0.5 rounded-xl border border-border/70 bg-background p-2">
                      <ShieldCheck className="size-4 text-muted-foreground" />
                    </div>
                    <div className="min-w-0 flex-1 space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="truncate font-medium">{doc.original_filename ?? doc.sha256 ?? doc.id}</span>
                        <Badge tone={statusMeta.tone}>{statusMeta.label}</Badge>
                      </div>
                      <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                        <span>{doc.needs_ocr ? "Necesita OCR" : "Tiene texto"}</span>
                        <span>·</span>
                        <span>{doc.page_count ?? 0} págs.</span>
                        <span>·</span>
                        <span>{new Date(doc.created_at).toLocaleDateString("es-AR")}</span>
                      </div>
                    </div>
                    {selected && <ArrowRight className="mt-1 size-4 shrink-0 text-primary" />}
                  </button>
                );
              })}
              {documents.length === 0 && (
                <div className="px-4 py-16 text-center text-sm text-muted-foreground">
                  <FileText className="mx-auto mb-3 size-10 opacity-35" />
                  Todavía no hay documentos cargados.
                </div>
              )}
            </div>
          </Section>
        </div>

        <div className="space-y-6">
          <Section
            title={selectedDoc ? selectedDoc.original_filename ?? selectedDoc.sha256 ?? selectedDoc.id : "Detalle"}
            description={selectedDoc ? "Editar, crear faltantes y cerrar la revisión." : "Elegí un documento para ver el detalle."}
          >
            {selectedDoc && review && meta ? (
              <div className="space-y-6 p-4">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                  <div className="space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge tone={meta.tone}>{meta.label}</Badge>
                      {review.docType && <Badge tone="slate">{review.docType.code}</Badge>}
                    </div>
                    <p className="max-w-2xl text-sm text-muted-foreground">{meta.description}</p>
                    <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
                      <div className="rounded-2xl bg-muted/30 px-3 py-2">
                        <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Documento</p>
                        <p className="mt-1 text-sm font-medium">{selectedDoc.original_filename ?? "—"}</p>
                      </div>
                      <div className="rounded-2xl bg-muted/30 px-3 py-2">
                        <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Estado</p>
                        <p className="mt-1 text-sm font-medium">{selectedDoc.status}</p>
                      </div>
                      <div className="rounded-2xl bg-muted/30 px-3 py-2">
                        <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Confianza media</p>
                        <p className="mt-1 text-sm font-medium">
                          {totalRecords > 0
                            ? `${Math.round(((review.metadata.records.reduce((sum, r) => sum + (r.confidence ?? 0), 0) / totalRecords) || 0) * 100)}%`
                            : "—"}
                        </p>
                      </div>
                    </div>
                  </div>

                  <div className="flex flex-wrap gap-2 lg:justify-end">
                    <Button variant="outline" size="sm" onClick={() => void loadDetail(selectedDoc.id)} className="gap-2">
                      <RefreshCw className="size-4" />
                      Refrescar
                    </Button>
                    <Button variant="outline" size="sm" disabled={saving === "reject"} onClick={() => void reviewAction("reject")} className="gap-2">
                      {saving === "reject" ? <Loader2 className="size-4 animate-spin" /> : <ThumbsDown className="size-4" />}
                      Rechazar
                    </Button>
                    <Button variant="outline" size="sm" disabled={saving === "approve"} onClick={() => void reviewAction("approve")} className="gap-2">
                      {saving === "approve" ? <Loader2 className="size-4 animate-spin" /> : <ShieldCheck className="size-4" />}
                      Aprobar
                    </Button>
                  </div>
                </div>

                <div className="grid gap-4 md:grid-cols-3">
                  <div className="rounded-2xl border border-border/70 bg-muted/20 p-4">
                    <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Evidencia</p>
                    <ul className="mt-3 space-y-2 text-sm">
                      {review.metadata.records.slice(0, 4).map((record) => (
                        <li key={record.id} className="rounded-2xl border border-border/60 bg-background p-3">
                          <div className="flex items-center justify-between gap-2">
                            <span className="font-medium">{record.display_name}</span>
                            <Badge tone={record.validated ? "green" : record.normalized ? "emerald" : "slate"}>
                              {Math.round((record.confidence ?? 0) * 100)}%
                            </Badge>
                          </div>
                          <p className="mt-2 text-xs text-muted-foreground">
                            pág. {record.source_page ?? "—"} · {record.source ?? "IA"}
                          </p>
                          <p className="mt-2 text-xs text-muted-foreground line-clamp-3">
                            {record.source_text || "Sin evidencia"}
                          </p>
                        </li>
                      ))}
                      {review.metadata.records.length === 0 && <li className="text-muted-foreground">Sin registros todavía.</li>}
                    </ul>
                  </div>

                  <div className="rounded-2xl border border-border/70 bg-muted/20 p-4">
                    <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Validación</p>
                    <ul className="mt-3 space-y-2 text-sm">
                      {review.validation.results.slice(0, 4).map((result) => (
                        <li key={result.id} className="flex items-center justify-between gap-2 rounded-2xl border border-border/60 bg-background px-3 py-2">
                          <span>{result.validator_type}</span>
                          <Badge tone={formatStatusTone(result.status)}>{result.status}</Badge>
                        </li>
                      ))}
                      {review.validation.results.length === 0 && <li className="text-muted-foreground">Sin validaciones.</li>}
                    </ul>
                  </div>

                  <div className="rounded-2xl border border-border/70 bg-muted/20 p-4">
                    <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Depósito</p>
                    <ul className="mt-3 space-y-2 text-sm">
                      {review.depositions.slice(0, 4).map((deposition) => (
                        <li key={deposition.id} className="flex items-center justify-between gap-2 rounded-2xl border border-border/60 bg-background px-3 py-2">
                          <span>{deposition.handle ?? deposition.external_item_id ?? "Depósito"}</span>
                          <Badge tone={formatStatusTone(deposition.status)}>{deposition.status}</Badge>
                        </li>
                      ))}
                      {review.depositions.length === 0 && <li className="text-muted-foreground">Sin depósitos.</li>}
                    </ul>
                  </div>
                </div>

                <div className="grid gap-4 lg:grid-cols-2">
                  <div className="rounded-2xl border border-border/70 bg-muted/10 p-4">
                    <div className="flex items-center justify-between gap-2">
                      <div>
                        <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Formulario dinámico</p>
                        <p className="mt-1 text-sm text-muted-foreground">Campos del tipo documental {review.docType ? `(${review.docType.fields.length})` : ""}</p>
                      </div>
                      <Badge tone="primary">{review.docType ? review.docType.name : "Sin tipo"}</Badge>
                    </div>

                    <form onSubmit={createRecord} className="mt-4 space-y-3">
                      <label className="block">
                        <span className="mb-1 block text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                          Campo faltante
                        </span>
                        <select
                          className={inputCls}
                          value={newRecord.field_id}
                          onChange={(e) => setNewRecord({ ...newRecord, field_id: e.target.value })}
                          required
                        >
                          <option value="">Seleccionar…</option>
                          {missingFields.map((field) => (
                            <option key={field.id} value={field.id}>
                              {field.display_name ?? `${field.element}${field.qualifier ? `.${field.qualifier}` : ""}`}
                              {field.required ? " (requerido)" : ""}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label className="block">
                        <span className="mb-1 block text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                          Valor
                        </span>
                        <textarea
                          className={`${inputCls} min-h-24 resize-y`}
                          value={newRecord.value}
                          onChange={(e) => setNewRecord({ ...newRecord, value: e.target.value })}
                          placeholder="Valor normalizado o corregido"
                          required
                        />
                      </label>
                      <label className="block">
                        <span className="mb-1 block text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                          Confianza
                        </span>
                        <input
                          type="number"
                          step="0.05"
                          min="0"
                          max="1"
                          className={inputCls}
                          value={newRecord.confidence}
                          onChange={(e) => setNewRecord({ ...newRecord, confidence: e.target.value })}
                        />
                      </label>
                      <Button type="submit" disabled={saving === "create" || !newRecord.field_id} className="gap-2">
                        {saving === "create" ? <Loader2 className="size-4 animate-spin" /> : <Plus className="size-4" />}
                        Crear registro
                      </Button>
                    </form>
                  </div>

                  <div className="rounded-2xl border border-border/70 bg-muted/10 p-4">
                    <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Campos existentes</p>
                    <div className="mt-4 space-y-3">
                      {review.metadata.records.map((record) => (
                        <div key={record.id} className="rounded-2xl border border-border/60 bg-background p-4">
                          <div className="flex items-center justify-between gap-2">
                            <div>
                              <p className="text-sm font-medium">{record.display_name}</p>
                              <p className="text-xs text-muted-foreground">{record.field}</p>
                            </div>
                              <div className="flex items-center gap-2">
                              <Badge tone={record.manually_modified ? "violet" : record.validated ? "green" : "slate"}>
                                {record.manually_modified ? "Manual" : record.validated ? "Validado" : "Auto"}
                              </Badge>
                              <Button variant="ghost" size="icon-sm" onClick={() => void deleteRecord(record.id)} title="Eliminar">
                                <Trash2 />
                              </Button>
                            </div>
                          </div>
                          <div className="mt-3 space-y-2">
                            <label className="block">
                              <span className="mb-1 block text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                                Valor
                              </span>
                              <textarea
                                className={`${inputCls} min-h-20 resize-y`}
                                value={updateDrafts[record.id] ?? ""}
                                onChange={(e) => setUpdateDrafts({ ...updateDrafts, [record.id]: e.target.value })}
                              />
                            </label>
                            <div className="grid gap-2 text-xs text-muted-foreground md:grid-cols-3">
                              <div>Evidencia pág. {record.source_page ?? "—"}</div>
                              <div>Confianza {Math.round((record.confidence ?? 0) * 100)}%</div>
                              <div>{record.normalized ? "Normalizado" : "Sin normalizar"}</div>
                            </div>
                            <p className="text-xs text-muted-foreground line-clamp-3">{record.source_text || "Sin evidencia"}</p>
                            <Button variant="outline" size="sm" disabled={saving === record.id} onClick={() => void saveRecord(record.id)} className="gap-2">
                              {saving === record.id ? <Loader2 className="size-4 animate-spin" /> : <PenLine className="size-4" />}
                              Guardar cambio
                            </Button>
                          </div>
                        </div>
                      ))}
                      {review.metadata.records.length === 0 && (
                        <div className="rounded-2xl border border-dashed border-border/70 bg-background p-6 text-sm text-muted-foreground">
                          Todavía no hay registros para revisar.
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ) : loadingDetail ? (
              <div className="flex min-h-[360px] items-center justify-center p-8 text-sm text-muted-foreground">
                Cargando revisión…
              </div>
            ) : (
              <div className="flex min-h-[360px] items-center justify-center p-8 text-center text-sm text-muted-foreground">
                Seleccioná un documento para revisar sus metadatos.
              </div>
            )}
          </Section>
        </div>
      </div>
    </div>
  );
}
