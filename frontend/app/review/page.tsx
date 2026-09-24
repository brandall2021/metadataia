"use client";

import { FormEvent, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import {
  ArrowRight,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Check,
  Download,
  Edit3,
  Eye,
  FileText,
  Fullscreen,
  History,
  Loader2,
  PenLine,
  Printer,
  Plus,
  Search,
  ShieldCheck,
  Sparkles,
  X,
  ZoomIn,
  ZoomOut,
  type LucideIcon,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { apiFetch, apiFetchBlob } from "@/lib/api";
import * as documentHelpers from "@/lib/documents";

type DocumentListItem = {
  id: string;
  original_filename: string | null;
  mime_type: string | null;
  file_size: number | null;
  sha256: string | null;
  page_count: number | null;
  document_type_id: string | null;
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

type DocTypeListItem = { id: string; name: string; code: string };

type ReviewDetail = {
  detail: DocumentListItem & { pages: DocumentPage[]; analysis: { total_text_length: number; needs_ocr: boolean; status: string }; jobs: Job[] };
  metadata: MetadataCollection;
  validation: ValidationCollection;
  depositions: Deposition[];
  docType: DocTypeDetail | null;
};

type PaneKey = "documents" | "pdf" | "review";
type ToastState = { tone: "success" | "error" | "info"; message: string } | null;

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
  return new Date(value).toLocaleString("es-AR", { dateStyle: "short", timeStyle: "short" });
}

function formatStatusTone(status: string): string {
  return documentHelpers.documentStatusMeta(status).tone;
}

function Stat({ label, value, icon: Icon, hint }: { label: string; value: string; icon: LucideIcon; hint?: string }) {
  return (
    <div className="rounded-2xl border border-border/70 bg-background px-4 py-3 shadow-sm">
      <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.22em] text-muted-foreground">
        <Icon className="size-3.5" />
        {label}
      </div>
      <div className="mt-2 text-2xl font-semibold tracking-tight tabular-nums">{value}</div>
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

function TabButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`rounded-full px-3 py-2 text-sm font-medium transition-colors ${active ? "bg-foreground text-background" : "bg-muted/70 text-muted-foreground hover:bg-muted hover:text-foreground"}`}
    >
      {children}
    </button>
  );
}

function EmptyState({ icon: Icon, title, description }: { icon: LucideIcon; title: string; description: string }) {
  return (
    <div className="flex min-h-[280px] flex-col items-center justify-center rounded-3xl border border-dashed border-border/70 bg-muted/20 px-6 py-12 text-center">
      <div className="flex size-12 items-center justify-center rounded-2xl bg-background shadow-sm">
        <Icon className="size-5 text-muted-foreground" />
      </div>
      <h3 className="mt-4 text-base font-semibold">{title}</h3>
      <p className="mt-2 max-w-sm text-sm leading-6 text-muted-foreground">{description}</p>
    </div>
  );
}

function FieldStatus({ record }: { record: MetadataRecord }) {
  if (record.validated) return <Badge tone="green">Validado</Badge>;
  if (record.manually_modified) return <Badge tone="violet">Corregido</Badge>;
  if ((record.confidence ?? 0) < 0.9) return <Badge tone="amber">Pendiente</Badge>;
  return <Badge tone="slate">Auto</Badge>;
}

export default function ReviewPage() {
  const [documents, setDocuments] = useState<DocumentListItem[]>([]);
  const [docTypes, setDocTypes] = useState<DocTypeListItem[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [review, setReview] = useState<ReviewDetail | null>(null);
  const [loadingDocs, setLoadingDocs] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [saving, setSaving] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<ToastState>(null);
  const [newRecord, setNewRecord] = useState({ field_id: "", value: "", confidence: "0.8" });
  const [updateDrafts, setUpdateDrafts] = useState<Record<string, string>>({});
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [selectedRecordId, setSelectedRecordId] = useState<string | null>(null);
  const [activePane, setActivePane] = useState<PaneKey>("documents");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");
  const [sortBy, setSortBy] = useState("recent");
  const [currentPage, setCurrentPage] = useState(1);
  const [zoom, setZoom] = useState(100);
  const pdfFrameRef = useRef<HTMLIFrameElement | null>(null);

  const selectedDoc = review?.detail ?? null;
  const meta = selectedDoc ? documentHelpers.documentStatusMeta(selectedDoc.status) : null;
  const selectedDocType = useMemo(() => docTypes.find((type) => type.id === selectedDoc?.document_type_id) ?? null, [docTypes, selectedDoc?.document_type_id]);
  const fieldOptions = review?.docType?.fields ?? [];
  const existingRecordIds = new Set(review?.metadata.records.map((r) => r.metadata_field_id) ?? []);
  const missingFields = fieldOptions.filter((field) => !existingRecordIds.has(field.id));
  const totalRecords = review?.metadata.records.length ?? 0;
  const validatedRecords = review?.metadata.records.filter((r) => r.validated).length ?? 0;
  const pendingRecords = Math.max(0, totalRecords - validatedRecords);
  const pendingDocs = documents.filter((doc) => doc.status === "NEEDS_REVIEW").length;
  const averageConfidence = totalRecords > 0 ? Math.round((review!.metadata.records.reduce((sum, record) => sum + (record.confidence ?? 0), 0) / totalRecords) * 100) : 0;
  const selectedRecord = review?.metadata.records.find((record) => record.id === selectedRecordId) ?? null;
  const reviewProgress = totalRecords > 0 ? Math.round((validatedRecords / totalRecords) * 100) : 0;
  const criticalMissing = missingFields.filter((field) => field.required).length;
  const approveDisabled = criticalMissing > 0 || totalRecords === 0;
  const depositDisabled = selectedDoc?.status !== "APPROVED" || criticalMissing > 0;

  const typeMap = useMemo(() => new Map(docTypes.map((type) => [type.id, type])), [docTypes]);

  const filteredDocuments = useMemo(() => {
    const normalized = search.trim().toLowerCase();
    const list = documents.filter((doc) => {
      const matchesSearch = !normalized || [doc.original_filename, doc.sha256, doc.status, typeMap.get(doc.document_type_id ?? "")?.name, typeMap.get(doc.document_type_id ?? "")?.code]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(normalized));
      const matchesStatus = statusFilter === "all" || doc.status === statusFilter;
      const matchesType = typeFilter === "all" || doc.document_type_id === typeFilter;
      return matchesSearch && matchesStatus && matchesType;
    });
    return list.sort((a, b) => {
      if (sortBy === "oldest") return +new Date(a.created_at) - +new Date(b.created_at);
      if (sortBy === "name") return (a.original_filename ?? "").localeCompare(b.original_filename ?? "");
      return +new Date(b.created_at) - +new Date(a.created_at);
    });
  }, [documents, search, statusFilter, typeFilter, sortBy, typeMap]);

  const pdfViewerSrc = useMemo(() => {
    if (!pdfUrl) return null;
    const page = Math.max(1, currentPage);
    return `${pdfUrl}#page=${page}&zoom=${zoom}`;
  }, [currentPage, pdfUrl, zoom]);

  function pushToast(tone: NonNullable<ToastState>["tone"], message: string) {
    setToast({ tone, message });
    window.setTimeout(() => setToast((current) => (current?.message === message ? null : current)), 2400);
  }

  async function loadDocuments() {
    try {
      setLoadingDocs(true);
      const [docs, types] = await Promise.all([
        apiFetch<DocumentListItem[]>("/api/documents"),
        apiFetch<DocTypeListItem[]>("/api/admin/document-types").catch(() => []),
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
    try {
      const detail = await apiFetch<ReviewDetail["detail"]>(`/api/documents/${id}`);
      const [metadata, validation, depositions, docType] = await Promise.all([
        apiFetch<MetadataCollection>(`/api/documents/${id}/metadata`),
        apiFetch<ValidationCollection>(`/api/documents/${id}/validation`),
        apiFetch<Deposition[]>(`/api/documents/${id}/depositions`),
        detail.document_type_id ? apiFetch<DocTypeDetail>(`/api/admin/document-types/${detail.document_type_id}`).catch(() => null) : Promise.resolve(null),
      ]);
      setReview({ detail, metadata, validation, depositions, docType });
      setUpdateDrafts((prev) => {
        const next: Record<string, string> = {};
        for (const record of metadata.records) next[record.id] = prev[record.id] ?? record.value ?? "";
        return next;
      });
      setNewRecord({ field_id: "", value: "", confidence: "0.8" });
      setSelectedRecordId((current) => metadata.records.some((record) => record.id === current) ? current : metadata.records[0]?.id ?? null);
      setCurrentPage(metadata.records.find((record) => record.id === selectedRecordId)?.source_page ?? detail.pages[0]?.page_number ?? 1);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al cargar la revisión");
      setReview(null);
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
    if (!selectedDoc) {
      setPdfUrl(null);
      return;
    }
    let active = true;
    let current: string | null = null;
    apiFetchBlob(`/api/documents/${selectedDoc.id}/download`)
      .then(({ blob }) => {
        if (!active) return;
        current = URL.createObjectURL(blob);
        setPdfUrl((prev) => {
          if (prev) URL.revokeObjectURL(prev);
          return current;
        });
      })
      .catch(() => {
        if (active) setPdfUrl(null);
      });
    return () => {
      active = false;
      if (current) URL.revokeObjectURL(current);
    };
  }, [selectedDoc?.id]);

  useEffect(() => {
    if (!selectedId || !review) return;
    const timer = window.setInterval(() => void loadDetail(selectedId), 5000);
    return () => window.clearInterval(timer);
  }, [selectedId, review?.detail.status, review?.metadata.records.length]);

  useEffect(() => {
    if (!selectedRecord) return;
    if (selectedRecord.source_page) setCurrentPage(selectedRecord.source_page);
    if (window.innerWidth < 1024) setActivePane("pdf");
  }, [selectedRecordId]);

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
      pushToast("success", "Campo guardado");
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo guardar el campo");
      pushToast("error", "No se pudo guardar el campo");
    } finally {
      setSaving(null);
    }
  }

  async function saveAllChanges() {
    if (!selectedId || !review) return;
    const changed = review.metadata.records.filter((record) => (updateDrafts[record.id] ?? "") !== (record.value ?? ""));
    if (changed.length === 0) {
      pushToast("info", "No hay cambios para guardar");
      return;
    }
    setSaving("bulk");
    setError(null);
    try {
      for (const record of changed) {
        await apiFetch(`/api/documents/${selectedId}/records/${record.id}`, {
          method: "PUT",
          body: JSON.stringify({ value: updateDrafts[record.id] ?? "" }),
        });
      }
      await loadDetail(selectedId);
      pushToast("success", "Cambios guardados");
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudieron guardar los cambios");
      pushToast("error", "No se pudieron guardar los cambios");
    } finally {
      setSaving(null);
    }
  }

  async function validateRecord(recordId: string) {
    if (!selectedId) return;
    setSaving(recordId);
    setError(null);
    try {
      await apiFetch(`/api/documents/${selectedId}/records/${recordId}/validate`, { method: "POST" });
      await loadDetail(selectedId);
      pushToast("success", "Campo validado");
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo validar el campo");
      pushToast("error", "No se pudo validar el campo");
    } finally {
      setSaving(null);
    }
  }

  async function markIncorrect(recordId: string) {
    if (!selectedId) return;
    setSaving(recordId);
    setError(null);
    try {
      await apiFetch(`/api/documents/${selectedId}/records/${recordId}/invalidate`, { method: "POST" });
      await loadDetail(selectedId);
      pushToast("success", "Campo marcado como incorrecto");
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo marcar el campo");
      pushToast("error", "No se pudo marcar el campo");
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
      pushToast("success", "Campo eliminado");
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo eliminar el campo");
      pushToast("error", "No se pudo eliminar el campo");
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
      pushToast("success", "Campo creado");
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo crear el campo");
      pushToast("error", "No se pudo crear el campo");
    } finally {
      setSaving(null);
    }
  }

  async function reviewAction(action: "approve" | "reject" | "deposit") {
    if (!selectedId) return;
    if (action !== "approve" && !window.confirm(action === "reject" ? "¿Rechazar este documento?" : "¿Depositar este documento?")) return;
    setSaving(action);
    setError(null);
    try {
      const path = action === "deposit" ? `/api/documents/${selectedId}/deposit` : `/api/documents/${selectedId}/${action}`;
      await apiFetch(path, { method: "POST" });
      await loadDocuments();
      await loadDetail(selectedId);
      pushToast("success", action === "approve" ? "Documento aprobado" : action === "reject" ? "Documento rechazado" : "Depósito encolado");
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo completar la revisión");
      pushToast("error", "No se pudo completar la revisión");
    } finally {
      setSaving(null);
    }
  }

  async function downloadDocument() {
    if (!selectedDoc) return;
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
  }

  const pdfPageCount = selectedDoc?.page_count ?? selectedDoc?.pages.length ?? 0;
  const availableFieldOptions = review?.docType?.fields ?? [];

  return (
    <div className="space-y-6 pb-28">
      <section className="rounded-2xl border border-border/70 bg-background/90 p-4 shadow-sm backdrop-blur xl:p-5">
        <div className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr] xl:items-center">
          <div className="space-y-3">
            <span className="inline-flex items-center gap-2 rounded-full border border-primary/15 bg-primary/10 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.24em] text-primary">
              <Edit3 className="size-3.5" />
              Revisión humana
            </span>
            <div className="space-y-1.5">
              <p className="text-xs text-muted-foreground">Inicio / Revisión humana</p>
              <h1 className="text-2xl font-semibold tracking-tight xl:text-[2.1rem]">Revisión</h1>
              <p className="max-w-2xl text-sm leading-6 text-muted-foreground">
                Validá los campos extraídos, corregí valores y aprobá documentos.
              </p>
            </div>
          </div>
          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
            <div className="rounded-2xl border border-border/70 bg-slate-50 p-3 shadow-sm">
              <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">Pendientes</p>
              <p className="mt-1 text-xl font-semibold tabular-nums text-slate-900">{pendingDocs}</p>
            </div>
            <div className="rounded-2xl border border-border/70 bg-indigo-50 p-3 shadow-sm">
              <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">Registros</p>
              <p className="mt-1 text-xl font-semibold tabular-nums text-indigo-700">{totalRecords}</p>
            </div>
            <div className="rounded-2xl border border-border/70 bg-emerald-50 p-3 shadow-sm">
              <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">Validados</p>
              <p className="mt-1 text-xl font-semibold tabular-nums text-emerald-700">{validatedRecords}</p>
            </div>
            <div className="rounded-2xl border border-border/70 bg-amber-50 p-3 shadow-sm">
              <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">Campos faltantes</p>
              <p className="mt-1 text-xl font-semibold tabular-nums text-amber-700">{missingFields.length}</p>
            </div>
          </div>
        </div>
      </section>

      {error && <p className="rounded-xl border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}

      {selectedDoc && review && (
        <div className="sticky top-4 z-10 hidden rounded-2xl border border-border/70 bg-background/95 p-2.5 shadow-sm backdrop-blur lg:block">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="min-w-0 space-y-1">
              <p className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">Documento seleccionado</p>
              <p className="truncate text-sm font-medium">{selectedDoc.original_filename ?? selectedDoc.sha256 ?? selectedDoc.id}</p>
              <p className="text-xs text-muted-foreground">{meta?.label ?? selectedDoc.status} · Progreso {reviewProgress}% · Página {currentPage} de {pdfPageCount || currentPage}</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" size="sm" onClick={() => void reviewAction("reject")} disabled={saving === "reject"} className="gap-2 border-red-200 text-red-700 hover:bg-red-50">
                {saving === "reject" ? <Loader2 className="size-4 animate-spin" /> : <X className="size-4" />}
                Rechazar
              </Button>
              <Button variant="outline" size="sm" onClick={() => void reviewAction("approve")} disabled={approveDisabled || saving === "approve"} className="gap-2 border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100 dark:border-emerald-900/40 dark:bg-emerald-950/40 dark:text-emerald-300">
                {saving === "approve" ? <Loader2 className="size-4 animate-spin" /> : <ShieldCheck className="size-4" />}
                Aprobar
              </Button>
              <Button variant="outline" size="sm" onClick={() => void saveAllChanges()} disabled={saving === "bulk"} className="gap-2">
                {saving === "bulk" ? <Loader2 className="size-4 animate-spin" /> : <PenLine className="size-4" />}
                Guardar cambios
              </Button>
              <Button variant="outline" size="sm" onClick={() => void reviewAction("deposit")} disabled={depositDisabled || saving === "deposit"} className="gap-2">
                {saving === "deposit" ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
                Depositar
              </Button>
            </div>
          </div>
        </div>
      )}

      <div className="flex flex-wrap gap-2 lg:hidden">
        <TabButton active={activePane === "documents"} onClick={() => setActivePane("documents")}>Documentos</TabButton>
        <TabButton active={activePane === "pdf"} onClick={() => setActivePane("pdf")}>PDF</TabButton>
        <TabButton active={activePane === "review"} onClick={() => setActivePane("review")}>Revisión</TabButton>
      </div>

      <div className="hidden gap-6 lg:grid xl:grid-cols-[24%_46%_30%]">
        <aside className="space-y-4 xl:sticky xl:top-6 xl:max-h-[calc(100dvh-9rem)] xl:overflow-hidden">
          <Section
            title="Documentos para revisar"
            description={`${filteredDocuments.length} resultados`}
            actions={<Badge tone="slate">{loadingDocs ? "Cargando" : `${documents.length} totales`}</Badge>}
          >
            <div className="space-y-3 p-4">
              <div className="grid gap-2">
                <div className="relative">
                  <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                  <input className={`${inputCls} pl-9`} placeholder="Buscar documento" value={search} onChange={(e) => setSearch(e.target.value)} />
                </div>
                <div className="grid gap-2 sm:grid-cols-3">
                  <select className={inputCls} value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
                    <option value="all">Todos los estados</option>
                    <option value="NEEDS_REVIEW">Pendiente</option>
                    <option value="APPROVED">Aprobado</option>
                    <option value="REJECTED">Rechazado</option>
                    <option value="NEEDS_REVIEW">En revisión</option>
                  </select>
                  <select className={inputCls} value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
                    <option value="all">Todos los tipos</option>
                    {docTypes.map((type) => (
                      <option key={type.id} value={type.id}>{type.name}</option>
                    ))}
                  </select>
                  <select className={inputCls} value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
                    <option value="recent">Más recientes</option>
                    <option value="oldest">Más antiguos</option>
                    <option value="name">Nombre</option>
                  </select>
                </div>
              </div>

              <div className="max-h-[calc(100dvh-20rem)] overflow-auto pr-1">
                <div className="space-y-2">
                  {filteredDocuments.map((doc) => {
                    const statusMeta = documentHelpers.documentStatusMeta(doc.status);
                    const selected = doc.id === selectedId;
                    const type = doc.document_type_id ? typeMap.get(doc.document_type_id) : null;
                    return (
                      <button
                        key={doc.id}
                        type="button"
                        className={`flex w-full items-start gap-3 rounded-2xl border px-3 py-3 text-left transition-all ${selected ? "border-primary/40 bg-primary/5 shadow-sm" : "border-border/70 bg-background hover:bg-muted/20"}`}
                        onClick={() => setSelectedId(doc.id)}
                      >
                        <div className={`mt-0.5 rounded-xl border p-2 ${selected ? "border-primary/20 bg-primary/10" : "border-border/70 bg-background"}`}>
                          <FileText className={`size-4 ${selected ? "text-primary" : "text-muted-foreground"}`} />
                        </div>
                        <div className="min-w-0 flex-1 space-y-1">
                          <div className="flex items-center gap-2">
                            <span className="truncate text-sm font-medium">{doc.original_filename ?? doc.sha256 ?? doc.id}</span>
                            <Badge tone={statusMeta.tone}>{statusMeta.label}</Badge>
                          </div>
                          <p className="text-xs text-muted-foreground">{type?.name ?? "Sin tipo"}</p>
                          <p className="text-xs text-muted-foreground">
                            {doc.page_count ?? 0} páginas · {formatDate(doc.created_at)}
                          </p>
                        </div>
                        {selected && <ArrowRight className="mt-1 size-4 shrink-0 text-primary" />}
                      </button>
                    );
                  })}
                  {filteredDocuments.length === 0 && <EmptyState icon={FileText} title="Sin resultados" description="Probá con otro filtro o buscá un documento distinto." />}
                </div>
              </div>
            </div>
          </Section>
        </aside>

        <main className="space-y-4 xl:sticky xl:top-6 xl:max-h-[calc(100dvh-9rem)] xl:overflow-hidden">
          <Section
            title="Documento original"
            description={selectedDoc ? selectedDoc.original_filename ?? selectedDoc.sha256 ?? selectedDoc.id : "Elegí un documento para ver el PDF"}
            actions={
              selectedDoc ? (
                <div className="flex flex-wrap gap-2">
                  <Button variant="outline" size="sm" onClick={() => setZoom((current) => Math.max(50, current - 10))} className="gap-2"><ZoomOut className="size-4" />Alejar</Button>
                  <Button variant="outline" size="sm" onClick={() => setZoom((current) => Math.min(180, current + 10))} className="gap-2"><ZoomIn className="size-4" />Acercar</Button>
                  <Button variant="outline" size="sm" onClick={() => setCurrentPage((current) => Math.max(1, current - 1))} className="gap-2"><ChevronLeft className="size-4" />Anterior</Button>
                  <Button variant="outline" size="sm" onClick={() => setCurrentPage((current) => Math.min(pdfPageCount || current, current + 1))} className="gap-2"><ChevronRight className="size-4" />Siguiente</Button>
                  <Button variant="outline" size="sm" onClick={() => void downloadDocument()} className="gap-2"><Download className="size-4" />Descargar</Button>
                  <Button variant="outline" size="sm" onClick={() => window.print()} className="gap-2"><Printer className="size-4" />Imprimir</Button>
                  <Button variant="outline" size="sm" onClick={() => pdfFrameRef.current?.requestFullscreen?.()} className="gap-2"><Fullscreen className="size-4" />Pantalla completa</Button>
                </div>
              ) : null
            }
          >
            <div className="space-y-0 p-4">
              {selectedDoc ? (
                <div className="space-y-4">
                  <div className="grid gap-3 rounded-2xl border border-border/70 bg-muted/10 p-4 md:grid-cols-4">
                    <Stat label="Archivo" value={selectedDoc.original_filename ?? "—"} icon={FileText} />
                    <Stat label="Páginas" value={`${pdfPageCount}`} icon={History} />
                    <Stat label="Estado" value={meta?.label ?? selectedDoc.status} icon={ShieldCheck} />
                    <Stat label="Página actual" value={`Página ${currentPage} de ${pdfPageCount || currentPage}`} icon={Eye} />
                  </div>

                  <div className="overflow-hidden rounded-3xl border border-border/70 bg-[#27272A] shadow-inner">
                    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 px-4 py-3 text-sm text-white/90">
                      <div className="min-w-0">
                        <p className="truncate font-medium text-white">{selectedDoc.original_filename ?? selectedDoc.sha256 ?? selectedDoc.id}</p>
                        <p className="text-xs text-white/60">Página {currentPage} de {pdfPageCount || currentPage}</p>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <Button variant="outline" size="sm" className="border-white/15 bg-white/5 text-white hover:bg-white/10" onClick={() => setCurrentPage(1)}>Ajustar al ancho</Button>
                      </div>
                    </div>
                    <div className="h-[min(72vh,860px)] overflow-auto bg-[#27272A] p-4">
                      {pdfViewerSrc ? (
                        <iframe
                          ref={pdfFrameRef}
                          title="Vista previa PDF"
                          src={pdfViewerSrc}
                          className="h-full min-h-[640px] w-full rounded-2xl bg-white"
                        />
                      ) : (
                        <div className="flex h-[640px] items-center justify-center rounded-2xl border border-white/10 bg-white/5 text-sm text-white/70">
                          Cargando PDF…
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="grid gap-4 lg:grid-cols-2">
                    <div className="rounded-2xl border border-border/70 bg-muted/10 p-4 shadow-sm">
                      <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Evidencia seleccionada</p>
                      {selectedRecord ? (
                        <div className="mt-3 space-y-3 rounded-2xl border border-primary/20 bg-primary/5 p-4">
                          <div className="flex flex-wrap items-center gap-2">
                            <Badge tone={selectedRecord.validated ? "green" : selectedRecord.manually_modified ? "violet" : "amber"}>
                              {selectedRecord.validated ? "Validado" : selectedRecord.manually_modified ? "Modificado manualmente" : "Pendiente"}
                            </Badge>
                            {selectedRecord.confidence !== null && selectedRecord.confidence < 0.9 && <Badge tone="amber">Confianza baja</Badge>}
                          </div>
                          <p className="text-sm font-medium">{selectedRecord.display_name}</p>
                          <p className="rounded-xl bg-background px-3 py-2 text-sm text-foreground">{selectedRecord.source_text || "Sin evidencia disponible"}</p>
                          <p className="text-xs text-muted-foreground">Página {selectedRecord.source_page ?? "—"} · {selectedRecord.source ?? "IA"}</p>
                        </div>
                      ) : (
                        <EmptyState icon={Eye} title="Seleccioná un campo" description="Al tocar un campo verás aquí la evidencia asociada." />
                      )}
                    </div>

                    <div className="rounded-2xl border border-border/70 bg-muted/10 p-4 shadow-sm">
                      <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Estado y navegación</p>
                      <div className="mt-3 space-y-3 text-sm">
                        <div className="rounded-2xl border border-border/60 bg-background p-3">
                          <div className="flex items-center justify-between gap-2">
                            <span className="font-medium">Progreso de revisión</span>
                            <span className="text-muted-foreground">{validatedRecords} de {totalRecords} campos validados</span>
                          </div>
                          <div className="mt-3 h-2 overflow-hidden rounded-full bg-muted">
                            <div className="h-full rounded-full bg-emerald-500" style={{ width: `${reviewProgress}%` }} />
                          </div>
                          <p className="mt-2 text-xs text-muted-foreground">Confianza media: {averageConfidence}%</p>
                        </div>
                        <div className="rounded-2xl border border-border/60 bg-background p-3">
                          <div className="flex items-center justify-between gap-2 text-xs uppercase tracking-[0.18em] text-muted-foreground">
                            <span>Documento</span>
                            <span>{selectedDocType?.code ?? selectedDoc.status}</span>
                          </div>
                          <p className="mt-2 text-sm font-medium">{selectedDoc.original_filename ?? selectedDoc.sha256 ?? selectedDoc.id}</p>
                          <p className="mt-1 text-xs text-muted-foreground">{selectedDoc.page_count ?? 0} páginas · {formatDate(selectedDoc.created_at)}</p>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              ) : loadingDetail ? (
                <div className="flex min-h-[700px] items-center justify-center p-8 text-sm text-muted-foreground">Cargando revisión…</div>
              ) : (
                <EmptyState icon={FileText} title="Seleccioná un documento" description="Elegí un documento para ver el PDF, la evidencia y los estados de validación." />
              )}
            </div>
          </Section>
        </main>

        <aside className="space-y-4 xl:sticky xl:top-6 xl:max-h-[calc(100dvh-9rem)] xl:overflow-hidden">
          <Section
            title="Revisión"
            description={selectedDoc ? `${totalRecords} registros · ${criticalMissing} faltantes críticos` : "Sin documento seleccionado"}
            actions={selectedDoc ? <Badge tone={meta?.tone ?? "slate"}>{meta?.label ?? selectedDoc.status}</Badge> : null}
          >
            {selectedDoc && review && meta ? (
              <div className="space-y-4 p-4">
                <div className="space-y-3 rounded-2xl border border-border/60 bg-background p-4">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Progreso</p>
                    <span className="text-xs text-muted-foreground">{validatedRecords} de {totalRecords} campos validados</span>
                  </div>
                  <div className="h-3 overflow-hidden rounded-full bg-muted">
                    <div className="h-full bg-slate-300" style={{ width: `${Math.max(0, 100 - reviewProgress)}%` }} />
                    <div className="-mt-3 h-3 bg-indigo-500" style={{ width: `${reviewProgress}%` }} />
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground sm:grid-cols-4">
                    <span>Pendiente: {pendingRecords}</span>
                    <span>En revisión: {Math.max(0, totalRecords - validatedRecords - criticalMissing)}</span>
                    <span>Validado: {validatedRecords}</span>
                    <span>Error: {criticalMissing}</span>
                  </div>
                  <p className="text-sm text-muted-foreground">Confianza media: {averageConfidence}%</p>
                </div>

                <div className="space-y-3 rounded-2xl border border-border/60 bg-background p-4">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Campos extraídos</p>
                    <Badge tone="slate">{review.metadata.records.length}</Badge>
                  </div>
                  <div className="space-y-3 max-h-[30vh] overflow-auto pr-1">
                    {review.metadata.records.map((record) => {
                      const selected = record.id === selectedRecordId;
                      return (
                        <button
                          key={record.id}
                          type="button"
                          onClick={() => {
                            setSelectedRecordId(record.id);
                            setActivePane("pdf");
                          }}
                          className={`w-full rounded-2xl border px-3 py-3 text-left transition-all ${selected ? "border-primary/40 bg-primary/5 shadow-sm" : "border-border/60 bg-muted/10 hover:bg-muted/20"}`}
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0 space-y-1">
                              <div className="flex flex-wrap items-center gap-2">
                                <span className="truncate text-sm font-medium">{record.display_name}</span>
                                <FieldStatus record={record} />
                              </div>
                              <p className="text-xs text-muted-foreground">{record.value || "Sin valor"}</p>
                              <p className="text-xs text-muted-foreground">Página {record.source_page ?? "—"} · {record.source ?? "IA"}</p>
                            </div>
                            <div className="flex shrink-0 flex-col items-end gap-1 text-xs text-muted-foreground">
                              <span>{Math.round((record.confidence ?? 0) * 100)}%</span>
                              {record.manually_modified && <Badge tone="violet">Modificado manualmente</Badge>}
                            </div>
                          </div>
                          {record.confidence !== null && record.confidence < 0.9 && <p className="mt-2 text-xs text-amber-600 dark:text-amber-300">Confianza menor a 90%</p>}
                        </button>
                      );
                    })}
                    {review.metadata.records.length === 0 && <EmptyState icon={FileText} title="Sin campos" description="Todavía no hay metadatos extraídos para revisar." />}
                  </div>
                </div>

                <div className="grid gap-3 rounded-2xl border border-border/60 bg-muted/10 p-4">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Validación</p>
                    <Badge tone={review.validation.results.length > 0 ? "green" : "slate"}>{review.validation.results.length}</Badge>
                  </div>
                  <div className="space-y-2 text-sm">
                    <StatusRow label="Metadata" value={validatedRecords > 0 ? "Completado" : "Pendiente"} tone={validatedRecords > 0 ? "green" : "slate"} />
                    <StatusRow label="SNRD" value={review.validation.results.some((result) => /snrd/i.test(result.validator_type)) ? "Completado" : "Pendiente"} tone={review.validation.results.some((result) => /snrd/i.test(result.validator_type)) ? "green" : "slate"} />
                    <StatusRow label="Esquema" value={review.validation.results.some((result) => /schema/i.test(result.validator_type)) ? "Completado" : "Pendiente"} tone={review.validation.results.some((result) => /schema/i.test(result.validator_type)) ? "green" : "slate"} />
                    <StatusRow label="Reglas documentales" value={review.validation.results.length > 0 ? "Completado" : "Pendiente"} tone={review.validation.results.length > 0 ? "green" : "slate"} />
                  </div>
                  <div className="rounded-2xl border border-border/60 bg-background p-3 text-sm">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium">Depósito</span>
                      <Badge tone={selectedDoc.status === "APPROVED" ? "green" : "amber"}>{selectedDoc.status}</Badge>
                    </div>
                    <p className="mt-2 text-xs text-muted-foreground">Último intento: {review.depositions[0] ? formatDate(review.depositions[0].started_at) : "—"}</p>
                    <p className="mt-1 text-xs text-muted-foreground line-clamp-2">{review.depositions[0]?.error_message ?? "Sin errores registrados"}</p>
                    <Button variant="outline" size="sm" className="mt-3 w-full gap-2" disabled={depositDisabled} onClick={() => void reviewAction("deposit")}>Reintentar depósito</Button>
                  </div>
                </div>

                <div className="space-y-3 rounded-2xl border border-border/60 bg-background p-4">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Crear metadato</p>
                    <Badge tone="slate">{availableFieldOptions.length}</Badge>
                  </div>
                  <form onSubmit={createRecord} className="space-y-3">
                    <select className={inputCls} value={newRecord.field_id} onChange={(e) => setNewRecord({ ...newRecord, field_id: e.target.value })} required>
                      <option value="">Seleccionar campo faltante</option>
                      {missingFields.map((field) => (
                        <option key={field.id} value={field.id}>
                          {field.display_name ?? `${field.element}${field.qualifier ? `.${field.qualifier}` : ""}`}{field.required ? " (requerido)" : ""}
                        </option>
                      ))}
                    </select>
                    <textarea className={`${inputCls} min-h-24 resize-y`} value={newRecord.value} onChange={(e) => setNewRecord({ ...newRecord, value: e.target.value })} placeholder="Valor corregido o faltante" required />
                    <input type="number" step="0.05" min="0" max="1" className={inputCls} value={newRecord.confidence} onChange={(e) => setNewRecord({ ...newRecord, confidence: e.target.value })} />
                    <Button type="submit" disabled={saving === "create" || !newRecord.field_id} className="w-full gap-2">
                      {saving === "create" ? <Loader2 className="size-4 animate-spin" /> : <Plus className="size-4" />}
                      Crear registro
                    </Button>
                  </form>
                </div>

                <div className="space-y-3 rounded-2xl border border-border/60 bg-background p-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Detalle del documento</p>
                  <div className="grid gap-2 text-sm">
                    <InfoRow label="Archivo" value={selectedDoc.original_filename ?? "—"} />
                    <InfoRow label="Tipo" value={selectedDocType?.name ?? "Sin tipo"} />
                    <InfoRow label="Páginas" value={`${selectedDoc.page_count ?? 0}`} />
                    <InfoRow label="Creado" value={formatDate(selectedDoc.created_at)} />
                  </div>
                </div>
              </div>
            ) : loadingDetail ? (
              <div className="flex min-h-[720px] items-center justify-center p-8 text-sm text-muted-foreground">Cargando revisión…</div>
            ) : (
              <EmptyState icon={FileText} title="Seleccioná un documento" description="Elegí un documento para revisar sus metadatos, evidencia y estado de depósito." />
            )}
          </Section>
        </aside>
      </div>

      <div className="space-y-6 lg:hidden">
        {activePane === "documents" && (
          <Section title="Documentos para revisar" description={`${filteredDocuments.length} resultados`}>
            <div className="space-y-3 p-4">
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                <input className={`${inputCls} pl-9`} placeholder="Buscar documento" value={search} onChange={(e) => setSearch(e.target.value)} />
              </div>
              <div className="grid gap-2 sm:grid-cols-3">
                <select className={inputCls} value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
                  <option value="all">Todos los estados</option>
                  <option value="NEEDS_REVIEW">Pendiente</option>
                  <option value="APPROVED">Aprobado</option>
                  <option value="REJECTED">Rechazado</option>
                </select>
                <select className={inputCls} value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
                  <option value="all">Todos los tipos</option>
                  {docTypes.map((type) => <option key={type.id} value={type.id}>{type.name}</option>)}
                </select>
                <select className={inputCls} value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
                  <option value="recent">Más recientes</option>
                  <option value="oldest">Más antiguos</option>
                  <option value="name">Nombre</option>
                </select>
              </div>
              <div className="space-y-2">
                {filteredDocuments.map((doc) => {
                  const statusMeta = documentHelpers.documentStatusMeta(doc.status);
                  const selected = doc.id === selectedId;
                  const type = doc.document_type_id ? typeMap.get(doc.document_type_id) : null;
                  return (
                    <button key={doc.id} type="button" className={`flex w-full items-start gap-3 rounded-2xl border px-3 py-3 text-left ${selected ? "border-primary/40 bg-primary/5" : "border-border/70 bg-background"}`} onClick={() => setSelectedId(doc.id)}>
                      <div className="rounded-xl border border-border/70 bg-background p-2"><FileText className="size-4 text-muted-foreground" /></div>
                      <div className="min-w-0 flex-1 space-y-1">
                        <div className="flex items-center gap-2"><span className="truncate text-sm font-medium">{doc.original_filename ?? doc.sha256 ?? doc.id}</span><Badge tone={statusMeta.tone}>{statusMeta.label}</Badge></div>
                        <p className="text-xs text-muted-foreground">{type?.name ?? "Sin tipo"}</p>
                        <p className="text-xs text-muted-foreground">{doc.page_count ?? 0} páginas · {formatDate(doc.created_at)}</p>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          </Section>
        )}

        {activePane === "pdf" && (
          <Section title="Documento original" description={selectedDoc ? selectedDoc.original_filename ?? selectedDoc.sha256 ?? selectedDoc.id : "Sin selección"}>
            {selectedDoc ? (
              <div className="space-y-4 p-4">
                <div className="flex flex-wrap gap-2">
                  <Button variant="outline" size="sm" onClick={() => setZoom((current) => Math.max(50, current - 10))}><ZoomOut className="size-4" /></Button>
                  <Button variant="outline" size="sm" onClick={() => setZoom((current) => Math.min(180, current + 10))}><ZoomIn className="size-4" /></Button>
                  <Button variant="outline" size="sm" onClick={() => setCurrentPage((current) => Math.max(1, current - 1))}><ChevronLeft className="size-4" /></Button>
                  <Button variant="outline" size="sm" onClick={() => setCurrentPage((current) => Math.min(pdfPageCount || current, current + 1))}><ChevronRight className="size-4" /></Button>
                </div>
                <div className="overflow-hidden rounded-3xl border border-border/70 bg-[#27272A]">
                  <div className="px-4 py-3 text-sm text-white/90">Página {currentPage} de {pdfPageCount || currentPage}</div>
                  <div className="h-[72vh] bg-[#27272A] p-3">{pdfViewerSrc ? <iframe ref={pdfFrameRef} title="Vista previa PDF" src={pdfViewerSrc} className="h-full w-full rounded-2xl bg-white" /> : <div className="flex h-full items-center justify-center text-white/70">Cargando PDF…</div>}</div>
                </div>
              </div>
            ) : <div className="p-4"><EmptyState icon={FileText} title="Seleccioná un documento" description="Elegí un documento para ver el PDF." /></div>}
          </Section>
        )}

        {activePane === "review" && (
          <Section title="Revisión" description={selectedDoc ? `${totalRecords} registros · ${criticalMissing} faltantes críticos` : "Sin documento"}>
            {selectedDoc && review && meta ? (
              <div className="space-y-4 p-4">
                <div className="rounded-2xl border border-border/60 bg-background p-4">
                  <div className="flex items-center justify-between gap-2"><span className="text-sm font-medium">Progreso de revisión</span><span className="text-xs text-muted-foreground">{validatedRecords} de {totalRecords} campos validados</span></div>
                  <div className="mt-3 h-3 overflow-hidden rounded-full bg-muted"><div className="h-full bg-indigo-500" style={{ width: `${reviewProgress}%` }} /></div>
                  <p className="mt-2 text-xs text-muted-foreground">Confianza media: {averageConfidence}%</p>
                </div>

                <div className="space-y-3">
                  {review.metadata.records.map((record) => {
                    const selected = record.id === selectedRecordId;
                    return (
                      <button key={record.id} type="button" onClick={() => { setSelectedRecordId(record.id); setActivePane("pdf"); }} className={`w-full rounded-2xl border px-3 py-3 text-left ${selected ? "border-primary/40 bg-primary/5" : "border-border/60 bg-background"}`}>
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0 space-y-1">
                            <div className="flex flex-wrap items-center gap-2"><span className="truncate text-sm font-medium">{record.display_name}</span><FieldStatus record={record} /></div>
                            <p className="text-xs text-muted-foreground">{record.value || "Sin valor"}</p>
                            <p className="text-xs text-muted-foreground">Página {record.source_page ?? "—"} · {record.source ?? "IA"}</p>
                          </div>
                          <div className="flex flex-col items-end gap-1">
                            <span className="text-xs text-muted-foreground">{Math.round((record.confidence ?? 0) * 100)}%</span>
                            {record.manually_modified && <Badge tone="violet">Modificado manualmente</Badge>}
                          </div>
                        </div>
                        <div className="mt-3 flex flex-wrap gap-2">
                          <Button type="button" variant="outline" size="sm" onClick={(e) => { e.stopPropagation(); void saveRecord(record.id); }} disabled={saving === record.id} className="gap-2"><PenLine className="size-4" />Guardar</Button>
                          <Button type="button" variant="outline" size="sm" onClick={(e) => { e.stopPropagation(); void validateRecord(record.id); }} disabled={saving === record.id} className="gap-2"><Check className="size-4" />Validar</Button>
                          <Button type="button" variant="outline" size="sm" onClick={(e) => { e.stopPropagation(); void markIncorrect(record.id); }} disabled={saving === record.id} className="gap-2 text-destructive"><X className="size-4" />Incorrecto</Button>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            ) : <div className="p-4"><EmptyState icon={FileText} title="Seleccioná un documento" description="Elegí un documento para revisar sus campos." /></div>}
          </Section>
        )}
      </div>

      {selectedDoc && review && (
        <div className="fixed inset-x-0 bottom-0 z-20 border-t border-border/70 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80">
          <div className="mx-auto flex max-w-7xl flex-col gap-3 px-4 py-3 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
              <span className="font-medium text-foreground">{review.metadata.records.length} campos totales</span>
              <span>· {validatedRecords} validados</span>
              <span>· {criticalMissing} pendientes críticos</span>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" size="sm" onClick={() => void saveAllChanges()} disabled={saving === "bulk"} className="gap-2">{saving === "bulk" ? <Loader2 className="size-4 animate-spin" /> : <PenLine className="size-4" />}Guardar revisión</Button>
              <Button variant="outline" size="sm" onClick={() => void reviewAction("approve")} disabled={approveDisabled || saving === "approve"} className="gap-2 border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100 dark:border-emerald-900/40 dark:bg-emerald-950/40 dark:text-emerald-300">{saving === "approve" ? <Loader2 className="size-4 animate-spin" /> : <ShieldCheck className="size-4" />}Aprobar documento</Button>
            </div>
          </div>
        </div>
      )}

      {toast && (
        <div className={`fixed right-4 top-4 z-30 rounded-2xl border px-4 py-3 shadow-lg ${toast.tone === "success" ? "border-emerald-200 bg-emerald-50 text-emerald-800" : toast.tone === "error" ? "border-red-200 bg-red-50 text-red-800" : "border-border bg-background text-foreground"}`}>
          {toast.message}
        </div>
      )}
    </div>
  );
}

function StatusRow({ label, value, tone }: { label: string; value: string; tone: string }) {
  return (
    <div className="flex items-center justify-between gap-2 rounded-2xl border border-border/60 bg-background px-3 py-2">
      <span className="text-sm font-medium">{label}</span>
      <Badge tone={tone}>{value}</Badge>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-2 rounded-2xl border border-border/60 bg-background px-3 py-2">
      <span className="text-sm font-medium">{label}</span>
      <span className="text-sm text-muted-foreground">{value}</span>
    </div>
  );
}
