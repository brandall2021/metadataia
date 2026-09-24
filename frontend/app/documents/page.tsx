"use client";

import { FormEvent, useEffect, useMemo, useState, type ReactNode } from "react";
import {
  ArrowRight,
  CheckCircle2,
  Clock3,
  Database,
  Download,
  FileText,
  History,
  Layers3,
  Loader2,
  RefreshCw,
  ScanSearch,
  Sparkles,
  UploadCloud,
  Wrench,
  Trash2,
  type LucideIcon,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { apiFetch, apiFetchBlob, API_URL, getToken } from "@/lib/api";
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

type DocumentDetail = DocumentListItem & {
  document_type_id: string | null;
  pages: DocumentPage[];
  analysis: { total_text_length: number; needs_ocr: boolean; status: string };
  jobs: Job[];
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

type DocType = { id: string; name: string; code: string };

type ViewData = {
  detail: DocumentDetail;
  metadata: MetadataCollection;
  validation: ValidationCollection;
  depositions: Deposition[];
};

type TabKey = "overview" | "metadata" | "validation" | "history";
type ActionKey = "ocr" | "extract" | "normalize" | "validate" | "deposit";

const inputCls =
  "w-full rounded-xl border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground/60 outline-none transition-colors focus:border-ring focus:ring-2 focus:ring-ring/30";

function formatBytes(value: number | null): string {
  if (value === null) return "—";
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${Math.round(value / 1024)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(value: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleString("es-AR", {
    dateStyle: "short",
    timeStyle: "short",
  });
}

function statusTone(status: string): string {
  return documentHelpers.documentStatusMeta(status).tone;
}

function StatCard({ label, value, hint, icon: Icon }: { label: string; value: string; hint?: string; icon: LucideIcon }) {
  return (
    <div className="rounded-2xl border border-border/70 bg-background/90 p-4 shadow-sm">
      <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.22em] text-muted-foreground">
        <Icon className="size-3.5" />
        {label}
      </div>
      <div className="mt-3 text-2xl font-semibold tracking-tight tabular-nums">{value}</div>
      {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
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

function Section({ title, description, children, actions }: { title: string; description?: string; children: ReactNode; actions?: ReactNode }) {
  return (
    <Card className="border-border/70 shadow-sm">
      <CardHeader className="space-y-2 border-b border-border/60 bg-muted/20">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="space-y-1">
            <CardTitle className="text-lg">{title}</CardTitle>
            {description && <CardDescription>{description}</CardDescription>}
          </div>
          {actions}
        </div>
      </CardHeader>
      <CardContent className="p-0">{children}</CardContent>
    </Card>
  );
}

function EmptyState({ icon: Icon, title, description }: { icon: LucideIcon; title: string; description: string }) {
  return (
    <div className="flex min-h-[320px] flex-col items-center justify-center rounded-3xl border border-dashed border-border/70 bg-muted/20 px-6 py-12 text-center">
      <div className="flex size-12 items-center justify-center rounded-2xl bg-background shadow-sm">
        <Icon className="size-5 text-muted-foreground" />
      </div>
      <h3 className="mt-4 text-base font-semibold">{title}</h3>
      <p className="mt-2 max-w-sm text-sm leading-6 text-muted-foreground">{description}</p>
    </div>
  );
}

function TabButton({ active, children, onClick }: { active: boolean; children: ReactNode; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`rounded-full px-3 py-2 text-sm font-medium transition-colors ${
        active ? "bg-foreground text-background" : "bg-muted/70 text-muted-foreground hover:bg-muted hover:text-foreground"
      }`}
    >
      {children}
    </button>
  );
}

function DetailField({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="rounded-2xl border border-border/60 bg-background px-3 py-2.5">
      <div className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">{label}</div>
      <div className="mt-1 text-sm font-medium text-foreground">{value}</div>
    </div>
  );
}

function SummaryRow({ label, value, meta }: { label: string; value: ReactNode; meta?: ReactNode }) {
  return (
    <div className="rounded-2xl border border-border/60 bg-background px-3 py-2.5">
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-medium">{label}</span>
        {meta}
      </div>
      <div className="mt-1 text-sm text-muted-foreground">{value}</div>
    </div>
  );
}

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<DocumentListItem[]>([]);
  const [docTypes, setDocTypes] = useState<DocType[]>([]);
  const [view, setView] = useState<ViewData | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loadingDocs, setLoadingDocs] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadDocumentType, setUploadDocumentType] = useState("");
  const [activeTab, setActiveTab] = useState<TabKey>("overview");

  const docTypeMap = useMemo(() => new Map(docTypes.map((type) => [type.id, type])), [docTypes]);
  const selectedDoc = view?.detail ?? null;
  const meta = selectedDoc ? documentHelpers.documentStatusMeta(selectedDoc.status) : null;
  const busyJob = selectedDoc?.jobs.find((job) => ["PENDING", "RUNNING"].includes(job.status));
  const activeDocs = documents.filter((doc) => ["PROCESSING", "OCR_COMPLETED", "METADATA_EXTRACTED"].includes(doc.status)).length;
  const approvedDocs = documents.filter((doc) => doc.status === "APPROVED").length;
  const depositedDocs = documents.filter((doc) => doc.status === "DEPOSITED").length;

  const selectedDocumentType = selectedDoc?.document_type_id ? docTypeMap.get(selectedDoc.document_type_id) ?? null : null;
  const selectedIndex = useMemo(() => documents.findIndex((doc) => doc.id === selectedId), [documents, selectedId]);

  async function loadDocuments() {
    try {
      setLoadingDocs(true);
      const [docs, types] = await Promise.all([
        apiFetch<DocumentListItem[]>("/api/documents"),
        apiFetch<DocType[]>("/api/admin/document-types").catch(() => []),
      ]);
      setDocuments(docs);
      setDocTypes(types);
      setError(null);
      setSelectedId((current) => (current && docs.some((doc) => doc.id === current) ? current : docs[0]?.id ?? null));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al cargar documentos");
    } finally {
      setLoadingDocs(false);
    }
  }

  async function loadDetail(id: string) {
    setLoadingDetail(true);
    setView(null);
    try {
      const [detail, metadata, validation, depositions] = await Promise.all([
        apiFetch<DocumentDetail>(`/api/documents/${id}`),
        apiFetch<MetadataCollection>(`/api/documents/${id}/metadata`),
        apiFetch<ValidationCollection>(`/api/documents/${id}/validation`),
        apiFetch<Deposition[]>(`/api/documents/${id}/depositions`),
      ]);
      setView({ detail, metadata, validation, depositions });
      setError(null);
      setActiveTab("overview");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al cargar el documento");
    } finally {
      setLoadingDetail(false);
    }
  }

  useEffect(() => {
    void loadDocuments();
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    void loadDetail(selectedId);
  }, [selectedId]);

  useEffect(() => {
    if (!selectedId || !busyJob) return;
    const timer = window.setInterval(() => void loadDetail(selectedId), 5000);
    return () => window.clearInterval(timer);
  }, [selectedId, busyJob?.id, busyJob?.status]);

  async function uploadDocument(e: FormEvent) {
    e.preventDefault();
    if (!uploadFile) {
      setError("Elegí un PDF antes de cargarlo");
      return;
    }
    setUploading(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append("file", uploadFile);
      if (uploadDocumentType) formData.append("document_type_id", uploadDocumentType);

      const token = getToken();
      const res = await fetch(`${API_URL}/api/documents`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
        body: formData,
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail ?? `Error ${res.status}`);
      }
      const created = (await res.json()) as DocumentDetail;
      setUploadFile(null);
      setUploadDocumentType("");
      await loadDocuments();
      setSelectedId(created.id);
      await loadDetail(created.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al cargar el PDF");
    } finally {
      setUploading(false);
    }
  }

  async function requestAction(action: ActionKey) {
    if (!selectedId) return;
    setError(null);
    try {
      await apiFetch(`/api/documents/${selectedId}/${action}`, { method: "POST" });
      await loadDocuments();
      await loadDetail(selectedId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo ejecutar la acción");
    }
  }

  async function downloadDocument() {
    if (!selectedDoc) return;
    setError(null);
    try {
      const { blob, filename } = await apiFetchBlob(`/api/documents/${selectedDoc.id}/download`);
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filename ?? selectedDoc.original_filename ?? `${selectedDoc.id}.pdf`;
      anchor.rel = "noreferrer";
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo descargar el documento");
    }
  }

  async function deleteDocument() {
    if (!selectedDoc) return;
    if (!window.confirm("¿Borrar este documento? Esta acción no se puede deshacer.")) return;
    setError(null);
    try {
      await apiFetch(`/api/documents/${selectedDoc.id}`, { method: "DELETE" });
      setView(null);
      setSelectedId((current) => {
        const nextDocuments = documents.filter((doc) => doc.id !== selectedDoc.id);
        return current === selectedDoc.id ? nextDocuments[0]?.id ?? null : current;
      });
      await loadDocuments();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo borrar el documento");
    }
  }

  const canRequestOcr = documentHelpers.documentCanRequestOcr(selectedDoc);
  const canRequestExtraction = documentHelpers.documentCanRequestExtraction(selectedDoc);
  const canRequestNormalization = documentHelpers.documentCanRequestNormalization(view?.metadata);
  const canRequestValidation = documentHelpers.documentCanRequestValidation(view?.metadata);
  const canRequestDeposit = documentHelpers.documentCanRequestDeposit(view?.validation);

  const actionButtons = [
    {
      key: "ocr" as const,
      label: "Solicitar OCR",
      hint: "Cuando el PDF no trae texto.",
      icon: ScanSearch,
      can: canRequestOcr,
    },
    {
      key: "extract" as const,
      label: "Extraer metadatos",
      hint: "Lanza el análisis IA sobre texto disponible.",
      icon: Sparkles,
      can: canRequestExtraction,
    },
    {
      key: "normalize" as const,
      label: "Normalizar",
      hint: "Ajusta valores al formato esperado.",
      icon: Wrench,
      can: canRequestNormalization,
    },
    {
      key: "validate" as const,
      label: "Validar",
      hint: "Ejecuta las reglas de consistencia.",
      icon: CheckCircle2,
      can: canRequestValidation,
    },
    {
      key: "deposit" as const,
      label: "Depositar",
      hint: "Envía el documento al repositorio.",
      icon: Clock3,
      can: canRequestDeposit,
    },
  ];

  return (
    <div className="space-y-6 pb-4">
      <section className="rounded-2xl border border-border/70 bg-background/90 p-4 shadow-sm backdrop-blur xl:p-5">
        <div className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr] xl:items-center">
          <div className="max-w-2xl space-y-3">
            <span className="inline-flex items-center gap-2 rounded-full border border-primary/15 bg-primary/10 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.24em] text-primary">
              <Layers3 className="size-3.5" />
              Workspace de documentos
            </span>
            <div className="space-y-2">
              <p className="text-xs text-muted-foreground">Inicio / Documentos</p>
              <h1 className="text-2xl font-semibold tracking-tight xl:text-[2.1rem]">Documentos</h1>
              <p className="max-w-2xl text-sm leading-6 text-muted-foreground text-balance">
                Carga, análisis, OCR, extracción y depósito en un solo lugar. Seleccioná un PDF y seguí el flujo completo sin salir de esta pantalla.
              </p>
            </div>
          </div>
          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
            <div className="rounded-2xl border border-border/70 bg-slate-50 p-3 shadow-sm">
              <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">Documentos</p>
              <p className="mt-1 text-xl font-semibold tabular-nums text-slate-900">{documents.length}</p>
            </div>
            <div className="rounded-2xl border border-border/70 bg-indigo-50 p-3 shadow-sm">
              <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">Activos</p>
              <p className="mt-1 text-xl font-semibold tabular-nums text-indigo-700">{activeDocs}</p>
            </div>
            <div className="rounded-2xl border border-border/70 bg-emerald-50 p-3 shadow-sm">
              <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">Aprobados</p>
              <p className="mt-1 text-xl font-semibold tabular-nums text-emerald-700">{approvedDocs}</p>
            </div>
            <div className="rounded-2xl border border-border/70 bg-sky-50 p-3 shadow-sm">
              <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">Depositados</p>
              <p className="mt-1 text-xl font-semibold tabular-nums text-sky-700">{depositedDocs}</p>
            </div>
          </div>
        </div>
      </section>

      {error && (
        <p className="rounded-xl border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </p>
      )}

      <div className="grid gap-6 xl:grid-cols-[minmax(360px,0.95fr)_1.05fr]">
        <div className="space-y-6">
          <Section title="Cargar PDF" description="Subí un archivo y, si querés, asignale un tipo documental.">
            <form onSubmit={uploadDocument} className="space-y-4 p-4">
              <label className="block rounded-3xl border border-dashed border-border/70 bg-muted/20 p-4 transition-colors hover:bg-muted/30">
                <span className="mb-2 flex items-center gap-2 text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                  <UploadCloud className="size-3.5" />
                  Archivo PDF
                </span>
                <input
                  type="file"
                  accept="application/pdf"
                  className={inputCls}
                  onChange={(e) => setUploadFile(e.target.files?.[0] ?? null)}
                />
                <p className="mt-2 text-xs text-muted-foreground">
                  {uploadFile ? `${uploadFile.name} · ${formatBytes(uploadFile.size)}` : "Arrastrá o seleccioná un archivo para comenzar."}
                </p>
              </label>

              <label className="block">
                <span className="mb-1 block text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                  Tipo documental
                </span>
                <select
                  className={inputCls}
                  value={uploadDocumentType}
                  onChange={(e) => setUploadDocumentType(e.target.value)}
                >
                  <option value="">Sin asociar</option>
                  {docTypes.map((type) => (
                    <option key={type.id} value={type.id}>
                      {type.name} ({type.code})
                    </option>
                  ))}
                </select>
                {docTypes.length === 0 && (
                  <p className="mt-2 text-xs text-muted-foreground">
                    No pudimos cargar la lista de tipos documentales.
                  </p>
                )}
              </label>

              <Button type="submit" disabled={uploading} className="w-full gap-2">
                {uploading ? <Loader2 className="size-4 animate-spin" /> : <UploadCloud className="size-4" />}
                {uploading ? "Cargando…" : "Subir PDF"}
              </Button>
            </form>
          </Section>

          <Section
            title="Documentos"
            description={loadingDocs ? "Cargando lista…" : `${documents.length} documentos disponibles`}
          >
            <div className="max-h-[720px] divide-y overflow-auto">
              {documents.map((doc) => {
                const metaDoc = documentHelpers.documentStatusMeta(doc.status);
                const selected = doc.id === selectedId;
                return (
                  <button
                    key={doc.id}
                    type="button"
                    className={`flex w-full items-start gap-3 px-4 py-3 text-left transition-colors ${
                      selected ? "bg-primary/5" : "hover:bg-muted/30"
                    }`}
                    onClick={() => setSelectedId(doc.id)}
                  >
                    <div className="mt-0.5 rounded-xl border border-border/70 bg-background p-2">
                      <FileText className="size-4 text-muted-foreground" />
                    </div>
                    <div className="min-w-0 flex-1 space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="truncate font-medium">{doc.original_filename ?? doc.sha256 ?? doc.id}</span>
                        <Badge tone={metaDoc.tone}>{metaDoc.label}</Badge>
                      </div>
                      <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                        <span>{formatBytes(doc.file_size)}</span>
                        <span>·</span>
                        <span>{doc.page_count ?? 0} págs.</span>
                        <span>·</span>
                        <span>{doc.needs_ocr ? "Necesita OCR" : "Tiene texto"}</span>
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

        <div className="space-y-6 xl:sticky xl:top-6 xl:self-start">
          <Section
            title={selectedDoc ? selectedDoc.original_filename ?? selectedDoc.sha256 ?? selectedDoc.id : "Detalle"}
            description={selectedDoc ? "Estado, acciones y trazabilidad del documento seleccionado." : "Elegí un documento para ver el flujo completo."}
            actions={
              selectedDoc ? (
                <div className="flex flex-wrap gap-2">
                  <Button variant="outline" size="sm" onClick={() => void loadDetail(selectedDoc.id)} className="gap-2">
                    <RefreshCw className="size-4" />
                    Refrescar
                  </Button>
                  <Button variant="outline" size="sm" className="gap-2" onClick={() => void downloadDocument()}>
                    <Download className="size-4" />
                    Descargar
                  </Button>
                  <Button variant="outline" size="sm" className="gap-2 border-red-200 text-red-700 hover:bg-red-50" onClick={() => void deleteDocument()}>
                    <Trash2 className="size-4" />
                    Borrar
                  </Button>
                </div>
              ) : null
            }
          >
            {selectedDoc && view && meta ? (
              <div className="space-y-6 p-4">
                <div className="flex flex-col gap-4 rounded-3xl border border-border/60 bg-muted/10 p-4 lg:flex-row lg:items-start lg:justify-between">
                  <div className="space-y-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge tone={meta.tone}>{meta.label}</Badge>
                      {busyJob && <Badge tone="slate">Job {busyJob.status.toLowerCase()}</Badge>}
                      {selectedDocumentType && <Badge tone="primary">{selectedDocumentType.code}</Badge>}
                    </div>
                    <p className="max-w-2xl text-sm leading-6 text-muted-foreground">{meta.description}</p>
                    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                      <DetailField label="Archivo" value={selectedDoc.original_filename ?? "—"} />
                      <DetailField label="Tipo documental" value={selectedDocumentType ? selectedDocumentType.name : "Sin asociar"} />
                      <DetailField label="Peso" value={formatBytes(selectedDoc.file_size)} />
                      <DetailField label="Páginas" value={selectedDoc.page_count ?? 0} />
                      <DetailField label="Texto total" value={`${view.detail.analysis.total_text_length.toLocaleString("es-AR")} caracteres`} />
                      <DetailField label="Creado" value={formatDate(selectedDoc.created_at)} />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-2 lg:min-w-[320px]">
                    {actionButtons.map((action) => {
                      const Icon = action.icon;
                      return (
                        <button
                          key={action.key}
                          type="button"
                          disabled={!action.can}
                          onClick={() => void requestAction(action.key)}
                          className={`rounded-2xl border px-3 py-3 text-left transition-all ${
                            action.can
                              ? "border-border/70 bg-background hover:-translate-y-0.5 hover:border-primary/35 hover:shadow-sm"
                              : "border-border/50 bg-muted/30 text-muted-foreground"
                          }`}
                        >
                          <div className="flex items-start justify-between gap-3">
                            <Icon className="size-4 shrink-0" />
                            <span className="text-[11px] uppercase tracking-[0.18em]">{action.can ? "listo" : "bloqueado"}</span>
                          </div>
                          <div className="mt-3 text-sm font-medium">{action.label}</div>
                          <div className="mt-1 text-xs leading-5 text-muted-foreground">{action.hint}</div>
                        </button>
                      );
                    })}
                  </div>
                </div>

                <div className="flex flex-wrap gap-2 border-b border-border/60 pb-4">
                  <TabButton active={activeTab === "overview"} onClick={() => setActiveTab("overview")}>
                    Resumen
                  </TabButton>
                  <TabButton active={activeTab === "metadata"} onClick={() => setActiveTab("metadata")}>
                    Metadatos
                  </TabButton>
                  <TabButton active={activeTab === "validation"} onClick={() => setActiveTab("validation")}>
                    Validación
                  </TabButton>
                  <TabButton active={activeTab === "history"} onClick={() => setActiveTab("history")}>
                    Historial
                  </TabButton>
                </div>

                {activeTab === "overview" && (
                  <div className="space-y-4">
                    <div className="grid gap-4 md:grid-cols-3">
                      <SummaryRow label="Análisis" value={view.detail.analysis.status} meta={<Badge tone={statusTone(view.detail.analysis.status)}>{view.detail.analysis.status}</Badge>} />
                      <SummaryRow label="OCR" value={view.detail.analysis.needs_ocr ? "Requerido" : "No requerido"} />
                      <SummaryRow label="Jobs activos" value={busyJob ? `${busyJob.job_type} · ${busyJob.status}` : "Sin jobs activos"} />
                    </div>

                    <div className="grid gap-4 lg:grid-cols-[1.08fr_0.92fr]">
                      <div className="rounded-2xl border border-border/70 bg-muted/10 p-4">
                        <div className="flex items-center justify-between gap-2">
                          <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Páginas</p>
                          <span className="text-xs text-muted-foreground">{view.detail.pages.length} páginas</span>
                        </div>
                        <div className="mt-3 space-y-3">
                          {view.detail.pages.slice(0, 6).map((page) => (
                            <div key={page.id} className="rounded-2xl border border-border/60 bg-background p-3">
                              <div className="flex items-center justify-between gap-2 text-sm">
                                <span className="font-medium">Página {page.page_number}</span>
                                <span className="text-xs text-muted-foreground">{page.ocr_used ? "OCR" : "Texto original"}</span>
                              </div>
                              <p className="mt-2 line-clamp-3 text-xs leading-5 text-muted-foreground">{page.text || "Sin texto"}</p>
                            </div>
                          ))}
                          {view.detail.pages.length === 0 && <p className="text-sm text-muted-foreground">Sin páginas cargadas.</p>}
                        </div>
                      </div>

                      <div className="space-y-4">
                        <div className="rounded-2xl border border-border/70 bg-muted/10 p-4">
                          <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Estado del flujo</p>
                          <div className="mt-3 space-y-2 text-sm">
                            <div className="flex items-center justify-between gap-2">
                              <span>Metadatos extraídos</span>
                              <span className="font-medium">{view.metadata.records.length}</span>
                            </div>
                            <div className="flex items-center justify-between gap-2">
                              <span>Validaciones</span>
                              <span className="font-medium">{view.validation.results.length}</span>
                            </div>
                            <div className="flex items-center justify-between gap-2">
                              <span>Depósitos</span>
                              <span className="font-medium">{view.depositions.length}</span>
                            </div>
                          </div>
                        </div>

                        <div className="rounded-2xl border border-border/70 bg-muted/10 p-4">
                          <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Última actividad</p>
                          <div className="mt-3 space-y-3 text-sm">
                            {view.detail.jobs.slice(0, 3).map((job) => (
                              <div key={job.id} className="rounded-2xl border border-border/60 bg-background p-3">
                                <div className="flex items-center justify-between gap-2">
                                  <span className="font-medium">{job.job_type}</span>
                                  <Badge tone={statusTone(job.status)}>{job.status}</Badge>
                                </div>
                                <p className="mt-1 text-xs text-muted-foreground">{formatDate(job.started_at)} · {job.progress ?? 0}%</p>
                              </div>
                            ))}
                            {view.detail.jobs.length === 0 && <p className="text-sm text-muted-foreground">Sin jobs registrados.</p>}
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {activeTab === "metadata" && (
                  <div className="space-y-4">
                    <div className="grid gap-4 md:grid-cols-3">
                      <SummaryRow label="Registros" value={view.metadata.records.length} />
                      <SummaryRow label="Runs" value={view.metadata.runs.length} />
                      <SummaryRow label="Documento" value={view.metadata.document_status} meta={<Badge tone={statusTone(view.metadata.document_status)}>{view.metadata.document_status}</Badge>} />
                    </div>

                    <div className="rounded-2xl border border-border/70 bg-muted/10 p-4">
                      <div className="flex items-center justify-between gap-2">
                        <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Metadatos extraídos</p>
                        <span className="text-xs text-muted-foreground">{view.metadata.records.filter((record) => record.validated).length} validados</span>
                      </div>
                      <div className="mt-3 space-y-2">
                        {view.metadata.records.slice(0, 12).map((record) => (
                          <div key={record.id} className="rounded-2xl border border-border/60 bg-background p-3">
                            <div className="flex items-center justify-between gap-2">
                              <span className="text-sm font-medium">{record.display_name}</span>
                              <div className="flex flex-wrap gap-2">
                                <Badge tone={record.validated ? "green" : record.normalized ? "emerald" : "slate"}>
                                  {record.validated ? "Validado" : record.normalized ? "Normalizado" : "Pendiente"}
                                </Badge>
                                {record.manually_modified && <Badge tone="amber">Editado</Badge>}
                              </div>
                            </div>
                            <p className="mt-1 text-sm text-foreground">{record.value ?? "—"}</p>
                            <p className="mt-1 text-xs text-muted-foreground">
                              {record.source ?? "IA"} · pág. {record.source_page ?? "—"} · conf. {record.confidence ?? "—"}
                            </p>
                          </div>
                        ))}
                        {view.metadata.records.length === 0 && <EmptyState icon={FileText} title="Sin metadatos" description="Todavía no hay extracción para este documento." />}
                      </div>
                    </div>

                    <div className="rounded-2xl border border-border/70 bg-muted/10 p-4">
                      <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Runs</p>
                      <div className="mt-3 space-y-2">
                        {view.metadata.runs.slice(0, 6).map((run) => (
                          <div key={run.id} className="rounded-2xl border border-border/60 bg-background p-3">
                            <div className="flex items-center justify-between gap-2">
                              <span className="text-sm font-medium">{run.model_id ?? run.agent_id ?? "Run"}</span>
                              <Badge tone={statusTone(run.status)}>{run.status}</Badge>
                            </div>
                            <div className="mt-1 flex flex-wrap gap-2 text-xs text-muted-foreground">
                              <span>{formatDate(run.started_at)}</span>
                              <span>·</span>
                              <span>{run.input_tokens ?? 0} in</span>
                              <span>·</span>
                              <span>{run.output_tokens ?? 0} out</span>
                            </div>
                          </div>
                        ))}
                        {view.metadata.runs.length === 0 && <p className="text-sm text-muted-foreground">Sin runs registrados.</p>}
                      </div>
                    </div>
                  </div>
                )}

                {activeTab === "validation" && (
                  <div className="space-y-4">
                    <div className="grid gap-4 md:grid-cols-3">
                      <SummaryRow label="Resultados" value={view.validation.results.length} />
                      <SummaryRow label="Documento" value={view.validation.document_status} meta={<Badge tone={statusTone(view.validation.document_status)}>{view.validation.document_status}</Badge>} />
                      <SummaryRow label="Listo para depósito" value={canRequestDeposit ? "Sí" : "No"} />
                    </div>

                    <div className="rounded-2xl border border-border/70 bg-muted/10 p-4">
                      <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Validaciones</p>
                      <div className="mt-3 space-y-2">
                        {view.validation.results.map((result) => (
                          <div key={result.id} className="rounded-2xl border border-border/60 bg-background p-3">
                            <div className="flex items-center justify-between gap-2">
                              <span className="text-sm font-medium">{result.validator_type}</span>
                              <Badge tone={statusTone(result.status)}>{result.status}</Badge>
                            </div>
                            <p className="mt-1 text-xs text-muted-foreground">{formatDate(result.created_at)}</p>
                            {Array.isArray(result.errors_json) && result.errors_json.length > 0 && (
                              <p className="mt-2 text-xs text-destructive">Errores: {result.errors_json.length}</p>
                            )}
                            {Array.isArray(result.warnings_json) && result.warnings_json.length > 0 && (
                              <p className="mt-1 text-xs text-amber-600 dark:text-amber-300">Advertencias: {result.warnings_json.length}</p>
                            )}
                          </div>
                        ))}
                        {view.validation.results.length === 0 && <EmptyState icon={CheckCircle2} title="Sin validaciones" description="Todavía no se ejecutó ninguna validación sobre este documento." />}
                      </div>
                    </div>
                  </div>
                )}

                {activeTab === "history" && (
                  <div className="space-y-4">
                    <div className="grid gap-4 md:grid-cols-3">
                      <SummaryRow label="Jobs" value={view.detail.jobs.length} />
                      <SummaryRow label="Depósitos" value={view.depositions.length} />
                      <SummaryRow label="Estado" value={view.detail.status} meta={<Badge tone={meta.tone}>{meta.label}</Badge>} />
                    </div>

                    <div className="rounded-2xl border border-border/70 bg-muted/10 p-4">
                      <div className="flex items-center justify-between gap-2">
                        <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Jobs y depósitos</p>
                        <History className="size-4 text-muted-foreground" />
                      </div>
                      <div className="mt-3 space-y-2">
                        {view.detail.jobs.slice(0, 6).map((job) => (
                          <div key={job.id} className="rounded-2xl border border-border/60 bg-background p-3">
                            <div className="flex items-center justify-between gap-2">
                              <span className="text-sm font-medium">{job.job_type}</span>
                              <Badge tone={statusTone(job.status)}>{job.status}</Badge>
                            </div>
                            <div className="mt-1 flex flex-wrap gap-2 text-xs text-muted-foreground">
                              <span>{formatDate(job.started_at)}</span>
                              <span>·</span>
                              <span>Progreso {job.progress ?? 0}%</span>
                            </div>
                            {job.error_message && <p className="mt-2 text-xs text-destructive">{job.error_message}</p>}
                          </div>
                        ))}
                        {view.detail.jobs.length === 0 && <p className="text-sm text-muted-foreground">Sin jobs registrados.</p>}
                      </div>
                    </div>

                    <div className="rounded-2xl border border-border/70 bg-muted/10 p-4">
                      <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Depósitos</p>
                      <div className="mt-3 space-y-2">
                        {view.depositions.map((deposition) => (
                          <div key={deposition.id} className="rounded-2xl border border-border/60 bg-background p-3">
                            <div className="flex items-center justify-between gap-2">
                              <span className="text-sm font-medium">{deposition.handle ?? deposition.external_item_id ?? deposition.id}</span>
                              <Badge tone={statusTone(deposition.status)}>{deposition.status}</Badge>
                            </div>
                            <p className="mt-1 text-xs text-muted-foreground">
                              {formatDate(deposition.started_at)} · {formatDate(deposition.finished_at)}
                            </p>
                            {deposition.error_message && <p className="mt-2 text-xs text-destructive">{deposition.error_message}</p>}
                          </div>
                        ))}
                        {view.depositions.length === 0 && <p className="text-sm text-muted-foreground">Sin depósitos todavía.</p>}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ) : loadingDetail ? (
              <div className="space-y-4 p-4">
                <div className="grid gap-4 md:grid-cols-3">
                  <div className="h-20 animate-pulse rounded-2xl bg-muted/40" />
                  <div className="h-20 animate-pulse rounded-2xl bg-muted/40" />
                  <div className="h-20 animate-pulse rounded-2xl bg-muted/40" />
                </div>
                <div className="h-[420px] animate-pulse rounded-3xl bg-muted/40" />
              </div>
            ) : (
              <div className="p-4">
                <EmptyState
                  icon={FileText}
                  title="Seleccioná un documento"
                  description="Elegí un PDF en la lista para ver el detalle, los metadatos, la validación y la trazabilidad."
                />
              </div>
            )}
          </Section>

          <div className="grid gap-3 md:grid-cols-3">
            <StatCard label="Selección" value={selectedDoc ? `#${selectedIndex + 1}` : "—"} hint="Documento activo" icon={FileText} />
            <StatCard label="Texto" value={selectedDoc ? `${selectedDoc.analysis.total_text_length.toLocaleString("es-AR")}` : "—"} hint="Carácteres extraídos" icon={Sparkles} />
            <StatCard label="Jobs" value={selectedDoc ? `${selectedDoc.jobs.length}` : "—"} hint="Trazabilidad disponible" icon={History} />
          </div>
        </div>
      </div>
    </div>
  );
}
