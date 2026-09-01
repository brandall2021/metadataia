"use client";

import { FormEvent, useEffect, useMemo, useState, type ReactNode } from "react";
import {
  ArrowRight,
  CheckCircle2,
  Clock3,
  Database,
  Download,
  FileText,
  Loader2,
  RefreshCw,
  ScanSearch,
  Sparkles,
  UploadCloud,
  Wrench,
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
  const meta = documentHelpers.documentStatusMeta(status);
  return meta.tone;
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

  const selectedDoc = view?.detail ?? null;
  const meta = selectedDoc ? documentHelpers.documentStatusMeta(selectedDoc.status) : null;
  const busyJob = selectedDoc?.jobs.find((job) => ["PENDING", "RUNNING"].includes(job.status));
  const activeDocs = documents.filter((doc) => ["PROCESSING", "OCR_COMPLETED", "METADATA_EXTRACTED"].includes(doc.status)).length;

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
      const [detail, metadata, validation, depositions] = await Promise.all([
        apiFetch<DocumentDetail>(`/api/documents/${id}`),
        apiFetch<MetadataCollection>(`/api/documents/${id}/metadata`),
        apiFetch<ValidationCollection>(`/api/documents/${id}/validation`),
        apiFetch<Deposition[]>(`/api/documents/${id}/depositions`),
      ]);
      setView({ detail, metadata, validation, depositions });
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al cargar el documento");
      setView(null);
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
    if (!selectedId || !busyJob) return;
    const timer = window.setInterval(() => void loadDetail(selectedId), 5000);
    return () => window.clearInterval(timer);
  }, [selectedId, busyJob?.id, busyJob?.status]);

  async function uploadDocument(e: FormEvent) {
    e.preventDefault();
    if (!uploadFile) {
      setError("Elegí un PDF antes de cargar");
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

  async function requestAction(action: "ocr" | "extract" | "normalize" | "validate" | "deposit") {
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

  const canRequestOcr = documentHelpers.documentCanRequestOcr(selectedDoc);
  const canRequestExtraction = documentHelpers.documentCanRequestExtraction(selectedDoc);
  const canRequestNormalization = documentHelpers.documentCanRequestNormalization(view?.metadata);
  const canRequestValidation = documentHelpers.documentCanRequestValidation(view?.metadata);
  const canRequestDeposit = documentHelpers.documentCanRequestDeposit(view?.validation);

  const selectedIndex = useMemo(() => documents.findIndex((doc) => doc.id === selectedId), [documents, selectedId]);

  return (
    <div className="space-y-6">
      <section className="rounded-3xl border border-border/70 bg-gradient-to-br from-primary/[0.08] via-background to-muted/40 p-6 shadow-sm">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-2xl space-y-3">
            <span className="inline-flex items-center gap-2 rounded-full border border-primary/15 bg-primary/10 px-3 py-1 text-[11px] uppercase tracking-[0.22em] text-primary">
              <Sparkles className="size-3.5" />
              Flujo de documentos
            </span>
            <div className="space-y-2">
              <h1 className="text-3xl font-semibold tracking-tight">Documentos</h1>
              <p className="max-w-2xl text-sm leading-6 text-muted-foreground">
                Carga, análisis, OCR y extracción de metadatos. Desde acá se sube el PDF,
                se sigue el estado y se dispara cada etapa del pipeline.
              </p>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3 sm:min-w-[360px] lg:w-[420px]">
            <Stat label="Cargados" value={`${documents.length}`} icon={Database} />
            <Stat label="En flujo" value={`${activeDocs}`} icon={Loader2} />
            <Stat label="Selección" value={selectedDoc ? `#${selectedIndex + 1}` : "—"} icon={FileText} />
            <Stat label="Tipos" value={`${docTypes.length}`} icon={CheckCircle2} />
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
          <Section title="Cargar PDF" description="Sube un PDF y opcionalmente asígnale un tipo documental.">
            <form onSubmit={uploadDocument} className="space-y-4 p-4">
              <label className="block">
                <span className="mb-1 block text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                  Archivo PDF
                </span>
                <input
                  type="file"
                  accept="application/pdf"
                  className={inputCls}
                  onChange={(e) => setUploadFile(e.target.files?.[0] ?? null)}
                />
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
                    No hay acceso a tipos documentales o todavía no se cargaron.
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
                        <span className="truncate font-medium">
                          {doc.original_filename ?? doc.sha256 ?? doc.id}
                        </span>
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

        <div className="space-y-6">
          <Section
            title={selectedDoc ? selectedDoc.original_filename ?? selectedDoc.sha256 ?? selectedDoc.id : "Detalle"}
            description={selectedDoc ? "Estado, acciones y trazabilidad del documento seleccionado." : "Elegí un documento para ver el detalle."}
          >
            {selectedDoc && view && meta ? (
              <div className="space-y-6 p-4">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                  <div className="space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge tone={meta.tone}>{meta.label}</Badge>
                      {busyJob && <Badge tone="slate">Job {busyJob.status.toLowerCase()}</Badge>}
                    </div>
                    <p className="max-w-2xl text-sm text-muted-foreground">{meta.description}</p>
                    <dl className="grid gap-3 text-sm md:grid-cols-2 lg:grid-cols-3">
                      <div className="rounded-2xl bg-muted/30 px-3 py-2">
                        <dt className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Archivo</dt>
                        <dd className="mt-1 font-medium">{selectedDoc.original_filename ?? "—"}</dd>
                      </div>
                      <div className="rounded-2xl bg-muted/30 px-3 py-2">
                        <dt className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Peso</dt>
                        <dd className="mt-1 font-medium">{formatBytes(selectedDoc.file_size)}</dd>
                      </div>
                      <div className="rounded-2xl bg-muted/30 px-3 py-2">
                        <dt className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Páginas</dt>
                        <dd className="mt-1 font-medium">{selectedDoc.page_count ?? 0}</dd>
                      </div>
                      <div className="rounded-2xl bg-muted/30 px-3 py-2">
                        <dt className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Texto extraído</dt>
                        <dd className="mt-1 font-medium">{view.detail.analysis.total_text_length.toLocaleString("es-AR")} caracteres</dd>
                      </div>
                      <div className="rounded-2xl bg-muted/30 px-3 py-2">
                        <dt className="text-xs uppercase tracking-[0.18em] text-muted-foreground">OCR</dt>
                        <dd className="mt-1 font-medium">{selectedDoc.needs_ocr ? "Requerido" : "No requerido"}</dd>
                      </div>
                      <div className="rounded-2xl bg-muted/30 px-3 py-2">
                        <dt className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Creado</dt>
                        <dd className="mt-1 font-medium">{formatDate(selectedDoc.created_at)}</dd>
                      </div>
                    </dl>
                  </div>

                  <div className="flex flex-wrap gap-2 lg:justify-end">
                    <Button variant="outline" size="sm" onClick={() => void loadDetail(selectedDoc.id)} className="gap-2">
                      <RefreshCw className="size-4" />
                      Refrescar
                    </Button>
                    <Button variant="outline" size="sm" className="gap-2" onClick={() => void downloadDocument()}>
                      <Download className="size-4" />
                      Descargar
                    </Button>
                    <Button variant="outline" size="sm" disabled={!canRequestOcr} onClick={() => void requestAction("ocr")} className="gap-2">
                      <ScanSearch className="size-4" />
                      OCR
                    </Button>
                    <Button variant="outline" size="sm" disabled={!canRequestExtraction} onClick={() => void requestAction("extract")} className="gap-2">
                      <Sparkles className="size-4" />
                      Extraer
                    </Button>
                    <Button variant="outline" size="sm" disabled={!canRequestNormalization} onClick={() => void requestAction("normalize")} className="gap-2">
                      <Wrench className="size-4" />
                      Normalizar
                    </Button>
                    <Button variant="outline" size="sm" disabled={!canRequestValidation} onClick={() => void requestAction("validate")} className="gap-2">
                      <CheckCircle2 className="size-4" />
                      Validar
                    </Button>
                    <Button variant="outline" size="sm" disabled={!canRequestDeposit} onClick={() => void requestAction("deposit")} className="gap-2">
                      <Clock3 className="size-4" />
                      Depositar
                    </Button>
                  </div>
                </div>

                <div className="grid gap-4 md:grid-cols-3">
                  <div className="rounded-2xl border border-border/70 bg-muted/20 p-4">
                    <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Análisis</p>
                    <ul className="mt-3 space-y-2 text-sm">
                      <li>Texto total: {view.detail.analysis.total_text_length.toLocaleString("es-AR")}</li>
                      <li>Necesita OCR: {view.detail.analysis.needs_ocr ? "sí" : "no"}</li>
                      <li>Estado interno: {view.detail.analysis.status}</li>
                    </ul>
                  </div>
                  <div className="rounded-2xl border border-border/70 bg-muted/20 p-4">
                    <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Jobs</p>
                    <ul className="mt-3 space-y-2 text-sm">
                      {view.detail.jobs.slice(0, 3).map((job) => (
                        <li key={job.id} className="flex items-center justify-between gap-2">
                          <span>{job.job_type}</span>
                          <Badge tone={statusTone(job.status)}>{job.status}</Badge>
                        </li>
                      ))}
                      {view.detail.jobs.length === 0 && <li className="text-muted-foreground">Sin jobs.</li>}
                    </ul>
                  </div>
                  <div className="rounded-2xl border border-border/70 bg-muted/20 p-4">
                    <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Trazabilidad</p>
                    <ul className="mt-3 space-y-2 text-sm">
                      <li>Metadatos: {view.metadata.records.length}</li>
                      <li>Validaciones: {view.validation.results.length}</li>
                      <li>Depósitos: {view.depositions.length}</li>
                    </ul>
                  </div>
                </div>

                <div className="grid gap-4 lg:grid-cols-2">
                  <div className="rounded-2xl border border-border/70 bg-muted/10 p-4">
                    <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Páginas</p>
                    <div className="mt-3 space-y-3">
                      {view.detail.pages.slice(0, 6).map((page) => (
                        <div key={page.id} className="rounded-2xl border border-border/60 bg-background p-3">
                          <div className="flex items-center justify-between gap-2 text-sm">
                            <span className="font-medium">Página {page.page_number}</span>
                            <span className="text-xs text-muted-foreground">{page.ocr_used ? "OCR" : "Texto original"}</span>
                          </div>
                          <p className="mt-2 text-xs text-muted-foreground line-clamp-3">{page.text || "Sin texto"}</p>
                        </div>
                      ))}
                      {view.detail.pages.length === 0 && <p className="text-sm text-muted-foreground">Sin páginas cargadas.</p>}
                    </div>
                  </div>

                  <div className="space-y-4">
                    <div className="rounded-2xl border border-border/70 bg-muted/10 p-4">
                      <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Metadatos extraídos</p>
                      <div className="mt-3 space-y-2">
                        {view.metadata.records.slice(0, 8).map((record) => (
                          <div key={record.id} className="rounded-2xl border border-border/60 bg-background p-3">
                            <div className="flex items-center justify-between gap-2">
                              <span className="text-sm font-medium">{record.display_name}</span>
                              <Badge tone={record.validated ? "green" : record.normalized ? "emerald" : "slate"}>
                                {record.validated ? "Validado" : record.normalized ? "Normalizado" : "Pendiente"}
                              </Badge>
                            </div>
                            <p className="mt-1 text-sm text-foreground">{record.value ?? "—"}</p>
                            <p className="mt-1 text-xs text-muted-foreground">
                              {record.source ?? "IA"} · pág. {record.source_page ?? "—"} · conf. {record.confidence ?? "—"}
                            </p>
                          </div>
                        ))}
                        {view.metadata.records.length === 0 && <p className="text-sm text-muted-foreground">Sin metadatos aún.</p>}
                      </div>
                    </div>

                    <div className="rounded-2xl border border-border/70 bg-muted/10 p-4">
                      <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Validaciones y depósitos</p>
                      <div className="mt-3 space-y-2">
                        {view.validation.results.slice(0, 4).map((result) => (
                          <div key={result.id} className="rounded-2xl border border-border/60 bg-background p-3 text-sm">
                            <div className="flex items-center justify-between gap-2">
                              <span className="font-medium">{result.validator_type}</span>
                              <Badge tone={statusTone(result.status)}>{result.status}</Badge>
                            </div>
                            <p className="mt-1 text-xs text-muted-foreground">{formatDate(result.created_at)}</p>
                          </div>
                        ))}
                        {view.validation.results.length === 0 && <p className="text-sm text-muted-foreground">Sin validaciones.</p>}
                        {view.depositions.slice(0, 4).map((deposition) => (
                          <div key={deposition.id} className="rounded-2xl border border-border/60 bg-background p-3 text-sm">
                            <div className="flex items-center justify-between gap-2">
                              <span className="font-medium">Depósito</span>
                              <Badge tone={statusTone(deposition.status)}>{deposition.status}</Badge>
                            </div>
                            <p className="mt-1 text-xs text-muted-foreground">{deposition.handle ?? deposition.external_item_id ?? "Sin handle"}</p>
                          </div>
                        ))}
                        {view.depositions.length === 0 && <p className="text-sm text-muted-foreground">Sin depósitos.</p>}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ) : loadingDetail ? (
              <div className="flex min-h-[360px] items-center justify-center p-8 text-sm text-muted-foreground">
                Cargando detalle…
              </div>
            ) : (
              <div className="flex min-h-[360px] items-center justify-center p-8 text-center text-sm text-muted-foreground">
                Seleccioná un documento para ver el flujo completo.
              </div>
            )}
          </Section>
        </div>
      </div>
    </div>
  );
}
