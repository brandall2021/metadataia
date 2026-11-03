"use client";

import { FormEvent, useEffect, useMemo, useState, type ReactNode } from "react";
import {
  ArrowDown,
  ArrowUp,
  BadgeCheck,
  BookMarked,
  ChevronRight,
  Database,
  FileText,
  Layers3,
  Loader2,
  Pencil,
  Plus,
  RotateCcw,
  Search,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { apiFetch } from "@/lib/api";

type Schema = {
  id: string;
  name: string;
  code: string;
  namespace: string | null;
  description: string | null;
  active: boolean;
  version: number;
  field_count: number;
};

type Vocabulary = {
  id: string;
  name: string;
  code: string;
};

type Field = {
  id: string;
  schema_id: string;
  schema_name: string;
  schema_code: string;
  element: string;
  qualifier: string | null;
  display_name: string | null;
  description: string | null;
  data_type: string;
  required: boolean;
  repeatable: boolean;
  editable: boolean;
  ai_extractable: boolean;
  validation_type: string | null;
  normalization_type: string | null;
  vocabulary_id: string | null;
  vocabulary_code: string | null;
  order_index: number | null;
  active: boolean;
};

type FieldDraft = {
  id: string | null;
  schema_id: string;
  element: string;
  qualifier: string;
  display_name: string;
  description: string;
  data_type: string;
  required: boolean;
  repeatable: boolean;
  editable: boolean;
  ai_extractable: boolean;
  validation_type: string;
  vocabulary_id: string;
  order_index: number;
  active: boolean;
};

type SchemaDraft = {
  id: string | null;
  name: string;
  code: string;
  namespace: string;
  description: string;
  active: boolean;
};

type FilterKey = "all" | "required" | "ai" | "vocabulary" | "inactive";

const DATA_TYPES = ["text", "textarea", "date", "url", "identifier"];
const VALIDATIONS = [
  { value: "", label: "Automática (según tipo)" },
  { value: "date", label: "Fecha ISO 8601" },
  { value: "url", label: "URL" },
  { value: "email", label: "Correo" },
  { value: "doi", label: "DOI" },
  { value: "orcid", label: "ORCID" },
  { value: "isbn", label: "ISBN" },
  { value: "issn", label: "ISSN" },
  { value: "integer", label: "Entero" },
];

const DC_ELEMENTS = [
  "title",
  "creator",
  "contributor",
  "date",
  "type",
  "language",
  "publisher",
  "description",
  "subject",
  "identifier",
  "relation",
  "format",
  "rights",
  "source",
  "coverage",
];

const QUALIFIER_SUGGESTIONS = [
  "alternative",
  "advisor",
  "issued",
  "subtype",
  "iso",
  "abstract",
  "sponsorship",
  "other",
  "citation",
  "uri",
  "ispartofseries",
  "license",
];

const LABEL_SUGGESTIONS: Record<string, string> = {
  title: "Título",
  "title.alternative": "Título alternativo",
  creator: "Autor",
  "contributor.advisor": "Director / tutor",
  contributor: "Colaborador",
  "date.issued": "Fecha de publicación",
  type: "Tipo de recurso",
  "type.subtype": "Subtipo documental",
  "language.iso": "Idioma",
  publisher: "Editorial / institución",
  "description.abstract": "Resumen",
  "description.sponsorship": "Financiamiento",
  subject: "Palabras clave / materias",
  "subject.other": "Grado / nota de título",
  "identifier.citation": "Cita bibliográfica",
  "identifier.uri": "URI del recurso",
  "relation.ispartofseries": "Serie / colección",
  format: "Formato",
  rights: "Derechos de uso",
  "rights.license": "Licencia",
  "rights.uri": "URI de licencia",
};

const GROUPS = ["Identificación", "Autoría", "Publicación", "Contenido", "Derechos", "Otros"] as const;
type Group = (typeof GROUPS)[number];

const GROUP_BY_ELEMENT: Record<string, Group> = {
  title: "Identificación",
  identifier: "Identificación",
  relation: "Identificación",
  creator: "Autoría",
  contributor: "Autoría",
  date: "Publicación",
  publisher: "Publicación",
  type: "Publicación",
  language: "Publicación",
  format: "Publicación",
  description: "Contenido",
  subject: "Contenido",
  rights: "Derechos",
};

const FILTERS: { key: FilterKey; label: string }[] = [
  { key: "all", label: "Todos" },
  { key: "required", label: "Obligatorios" },
  { key: "ai", label: "Extraíbles por IA" },
  { key: "vocabulary", label: "Con vocabulario" },
  { key: "inactive", label: "Inactivos" },
];

const inputCls =
  "w-full rounded-xl border border-border bg-muted/30 px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground/60 outline-none transition-colors focus:border-ring focus:bg-muted/50 focus:ring-2 focus:ring-ring/30";
const textareaCls = `${inputCls} min-h-[92px] resize-y`;

const TONES: Record<string, string> = {
  slate: "border-slate-200 bg-slate-50 text-slate-600",
  indigo: "border-indigo-100 bg-indigo-50 text-indigo-700",
  emerald: "border-emerald-100 bg-emerald-50 text-emerald-700",
  amber: "border-amber-100 bg-amber-50 text-amber-700",
  rose: "border-rose-100 bg-rose-50 text-rose-700",
  sky: "border-sky-100 bg-sky-50 text-sky-700",
};

function fieldKey(element: string, qualifier: string | null | undefined) {
  return qualifier ? `${element}.${qualifier}` : element;
}

function dspaceKey(element: string, qualifier: string | null | undefined) {
  return `dc.${fieldKey(element, qualifier)}`;
}

function suggestionFor(element: string, qualifier: string) {
  return LABEL_SUGGESTIONS[fieldKey(element.trim(), qualifier.trim() || null)] ?? "";
}

function groupFor(element: string): Group {
  return GROUP_BY_ELEMENT[element] ?? "Otros";
}

function MiniStat({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 shadow-sm">
      <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.22em] text-slate-500">
        {icon}
        {label}
      </div>
      <div className="mt-2 text-xl font-semibold tracking-tight">{value}</div>
    </div>
  );
}

function Badge({ children, tone = "slate" }: { children: ReactNode; tone?: keyof typeof TONES }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium ${TONES[tone]}`}
    >
      {children}
    </span>
  );
}

function Modal({
  title,
  subtitle,
  onClose,
  children,
  footer,
}: {
  title: string;
  subtitle: string;
  onClose: () => void;
  children: ReactNode;
  footer: ReactNode;
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-950/40 p-4 backdrop-blur-sm sm:p-8"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="my-auto w-full max-w-2xl overflow-hidden rounded-[1.5rem] border border-slate-200 bg-white shadow-2xl"
      >
        <div className="flex items-start justify-between gap-4 border-b border-slate-200 px-6 py-5">
          <div>
            <h2 className="text-lg font-semibold tracking-tight text-slate-950">{title}</h2>
            <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p>
          </div>
          <Button variant="ghost" size="icon-sm" onClick={onClose} aria-label="Cerrar">
            <X />
          </Button>
        </div>
        <div className="max-h-[70vh] space-y-4 overflow-y-auto px-6 py-5">{children}</div>
        <div className="flex items-center justify-end gap-2 border-t border-slate-200 bg-slate-50/70 px-6 py-4">
          {footer}
        </div>
      </div>
    </div>
  );
}

export default function MetadataPage() {
  const [schemas, setSchemas] = useState<Schema[]>([]);
  const [fields, setFields] = useState<Field[]>([]);
  const [vocabularies, setVocabularies] = useState<Vocabulary[]>([]);
  const [selectedSchemaId, setSelectedSchemaId] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<FilterKey>("all");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [fieldDraft, setFieldDraft] = useState<FieldDraft | null>(null);
  const [fieldSaving, setFieldSaving] = useState(false);
  const [fieldError, setFieldError] = useState<string | null>(null);

  const [schemaDraft, setSchemaDraft] = useState<SchemaDraft | null>(null);
  const [schemaSaving, setSchemaSaving] = useState(false);
  const [schemaError, setSchemaError] = useState<string | null>(null);

  async function load(preferredSchemaId?: string | null) {
    try {
      const [schemaData, fieldData] = await Promise.all([
        apiFetch<Schema[]>("/api/admin/metadata/schemas"),
        apiFetch<Field[]>("/api/admin/metadata/fields"),
      ]);
      const vocabularyData = await apiFetch<Vocabulary[]>("/api/admin/vocabularies").catch(() => []);
      setSchemas(schemaData);
      setFields(fieldData);
      setVocabularies(vocabularyData);
      setSelectedSchemaId((current) => {
        if (preferredSchemaId && schemaData.some((s) => s.id === preferredSchemaId)) return preferredSchemaId;
        if (current && schemaData.some((s) => s.id === current)) return current;
        return schemaData[0]?.id ?? null;
      });
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudieron cargar los metadatos");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const [schemaData, fieldData] = await Promise.all([
          apiFetch<Schema[]>("/api/admin/metadata/schemas"),
          apiFetch<Field[]>("/api/admin/metadata/fields"),
        ]);
        const vocabularyData = await apiFetch<Vocabulary[]>("/api/admin/vocabularies").catch(() => []);
        if (!active) return;
        setSchemas(schemaData);
        setFields(fieldData);
        setVocabularies(vocabularyData);
        setSelectedSchemaId(schemaData[0]?.id ?? null);
        setError(null);
      } catch (err) {
        if (active) setError(err instanceof Error ? err.message : "No se pudieron cargar los metadatos");
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!fieldDraft && !schemaDraft) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      setFieldDraft(null);
      setSchemaDraft(null);
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [fieldDraft, schemaDraft]);

  const selectedSchema = useMemo(
    () => schemas.find((s) => s.id === selectedSchemaId) ?? null,
    [schemas, selectedSchemaId],
  );

  const schemaFields = useMemo(
    () => fields.filter((f) => f.schema_id === selectedSchemaId),
    [fields, selectedSchemaId],
  );

  const orderedFields = useMemo(
    () =>
      [...schemaFields].sort(
        (a, b) =>
          (a.order_index ?? 0) - (b.order_index ?? 0) ||
          (a.display_name ?? a.element).localeCompare(b.display_name ?? b.element),
      ),
    [schemaFields],
  );

  const searchedFields = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (!term) return orderedFields;
    return orderedFields.filter((f) =>
      [f.display_name, f.element, f.qualifier, f.description, f.vocabulary_code]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(term)),
    );
  }, [orderedFields, search]);

  const filterCounts = useMemo(
    () => ({
      all: searchedFields.length,
      required: searchedFields.filter((f) => f.required).length,
      ai: searchedFields.filter((f) => f.ai_extractable).length,
      vocabulary: searchedFields.filter((f) => f.vocabulary_id).length,
      inactive: searchedFields.filter((f) => !f.active).length,
    }),
    [searchedFields],
  );

  const visibleFields = useMemo(() => {
    if (filter === "required") return searchedFields.filter((f) => f.required);
    if (filter === "ai") return searchedFields.filter((f) => f.ai_extractable);
    if (filter === "vocabulary") return searchedFields.filter((f) => f.vocabulary_id);
    if (filter === "inactive") return searchedFields.filter((f) => !f.active);
    return searchedFields;
  }, [searchedFields, filter]);

  const groupedFields = useMemo(() => {
    const buckets = new Map<Group, Field[]>(GROUPS.map((group) => [group, []]));
    for (const field of visibleFields) {
      buckets.get(groupFor(field.element))?.push(field);
    }
    return GROUPS.map((group) => ({ group, items: buckets.get(group) ?? [] })).filter((entry) => entry.items.length > 0);
  }, [visibleFields]);

  const activeFields = fields.filter((f) => f.active).length;
  const requiredFields = fields.filter((f) => f.required && f.active).length;
  const aiFields = fields.filter((f) => f.ai_extractable && f.active).length;
  const riduntSchema = schemas.find((s) => s.code === "snrd-dc") ?? null;

  async function applyRiduntProfile() {
    setBusy("ridunt");
    setError(null);
    setNotice(null);
    try {
      const schema = await apiFetch<Schema>("/api/admin/metadata/ridunt-profile", { method: "POST" });
      setSelectedSchemaId(schema.id);
      await load(schema.id);
      setNotice(
        `Perfil RIDUNT aplicado: ${schema.field_count} campos en el esquema "${schema.name}". Ya alimentan el formulario de carga.`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo aplicar el perfil RIDUNT");
    } finally {
      setBusy(null);
    }
  }

  function openCreateField() {
    if (!selectedSchema) return;
    setFieldError(null);
    setFieldDraft({
      id: null,
      schema_id: selectedSchema.id,
      element: "",
      qualifier: "",
      display_name: "",
      description: "",
      data_type: "text",
      required: false,
      repeatable: false,
      editable: true,
      ai_extractable: true,
      validation_type: "",
      vocabulary_id: "",
      order_index: orderedFields.length,
      active: true,
    });
  }

  function openEditField(field: Field) {
    setFieldError(null);
    setFieldDraft({
      id: field.id,
      schema_id: field.schema_id,
      element: field.element,
      qualifier: field.qualifier ?? "",
      display_name: field.display_name ?? "",
      description: field.description ?? "",
      data_type: field.data_type,
      required: field.required,
      repeatable: field.repeatable,
      editable: field.editable,
      ai_extractable: field.ai_extractable,
      validation_type: field.validation_type ?? "",
      vocabulary_id: field.vocabulary_id ?? "",
      order_index: field.order_index ?? 0,
      active: field.active,
    });
  }

  function patchFieldDraft(patch: Partial<FieldDraft>, suggestLabel = false) {
    setFieldDraft((prev) => {
      if (!prev) return prev;
      const next = { ...prev, ...patch };
      if (suggestLabel && !prev.display_name.trim()) {
        const suggestion = suggestionFor(next.element, next.qualifier);
        if (suggestion) next.display_name = suggestion;
      }
      return next;
    });
  }

  async function saveField(event: FormEvent) {
    event.preventDefault();
    if (!fieldDraft) return;
    const element = fieldDraft.element.trim().toLowerCase();
    if (!element) {
      setFieldError("El elemento de Dublin Core es obligatorio.");
      return;
    }
    const qualifier = fieldDraft.qualifier.trim().toLowerCase() || null;
    const duplicate = fields.find(
      (f) =>
        f.schema_id === fieldDraft.schema_id &&
        f.element === element &&
        (f.qualifier ?? null) === qualifier &&
        f.id !== fieldDraft.id,
    );
    if (duplicate) {
      setFieldError(`Ya existe el campo ${dspaceKey(element, qualifier)} en este esquema.`);
      return;
    }

    setFieldSaving(true);
    setFieldError(null);
    try {
      const payload = {
        element,
        qualifier,
        display_name: fieldDraft.display_name.trim() || null,
        description: fieldDraft.description.trim() || null,
        data_type: fieldDraft.data_type,
        required: fieldDraft.required,
        repeatable: fieldDraft.repeatable,
        editable: fieldDraft.editable,
        ai_extractable: fieldDraft.ai_extractable,
        validation_type: fieldDraft.validation_type || null,
        vocabulary_id: fieldDraft.vocabulary_id || null,
        order_index: fieldDraft.order_index,
        active: fieldDraft.active,
      };
      if (fieldDraft.id) {
        await apiFetch(`/api/admin/metadata/fields/${fieldDraft.id}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
      } else {
        await apiFetch<Field>("/api/admin/metadata/fields", {
          method: "POST",
          body: JSON.stringify({ ...payload, schema_id: fieldDraft.schema_id }),
        });
      }
      const schemaId = fieldDraft.schema_id;
      const edited = Boolean(fieldDraft.id);
      setFieldDraft(null);
      await load(schemaId);
      setNotice(
        edited
          ? "Campo actualizado. El formulario de carga toma el cambio automáticamente."
          : "Campo creado. Ya aparece en el formulario de carga, sin modificar código.",
      );
    } catch (err) {
      setFieldError(err instanceof Error ? err.message : "No se pudo guardar el campo");
    } finally {
      setFieldSaving(false);
    }
  }

  async function toggleField(field: Field) {
    setBusy(field.id);
    setError(null);
    try {
      await apiFetch(`/api/admin/metadata/fields/${field.id}`, {
        method: "PUT",
        body: JSON.stringify({ active: !field.active }),
      });
      await load(field.schema_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo cambiar el estado del campo");
    } finally {
      setBusy(null);
    }
  }

  async function deleteField(field: Field) {
    if (!window.confirm(`¿Eliminar el campo "${field.display_name ?? dspaceKey(field.element, field.qualifier)}"?`)) {
      return;
    }
    setBusy(field.id);
    setError(null);
    try {
      await apiFetch(`/api/admin/metadata/fields/${field.id}`, { method: "DELETE" });
      await load(field.schema_id);
      setNotice("Campo eliminado del esquema.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo eliminar el campo");
    } finally {
      setBusy(null);
    }
  }

  async function moveField(field: Field, direction: -1 | 1) {
    const index = orderedFields.findIndex((f) => f.id === field.id);
    const target = orderedFields[index + direction];
    if (index < 0 || !target) return;
    setBusy(field.id);
    setError(null);
    try {
      await Promise.all([
        apiFetch(`/api/admin/metadata/fields/${field.id}`, {
          method: "PUT",
          body: JSON.stringify({ order_index: index + direction }),
        }),
        apiFetch(`/api/admin/metadata/fields/${target.id}`, {
          method: "PUT",
          body: JSON.stringify({ order_index: index }),
        }),
      ]);
      await load(field.schema_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo reordenar el campo");
    } finally {
      setBusy(null);
    }
  }

  function openCreateSchema() {
    setSchemaError(null);
    setSchemaDraft({ id: null, name: "", code: "", namespace: "", description: "", active: true });
  }

  function openEditSchema() {
    if (!selectedSchema) return;
    setSchemaError(null);
    setSchemaDraft({
      id: selectedSchema.id,
      name: selectedSchema.name,
      code: selectedSchema.code,
      namespace: selectedSchema.namespace ?? "",
      description: selectedSchema.description ?? "",
      active: selectedSchema.active,
    });
  }

  async function saveSchema(event: FormEvent) {
    event.preventDefault();
    if (!schemaDraft) return;
    const name = schemaDraft.name.trim();
    if (!name) {
      setSchemaError("El nombre del esquema es obligatorio.");
      return;
    }
    if (!schemaDraft.id && !schemaDraft.code.trim()) {
      setSchemaError("El código del esquema es obligatorio.");
      return;
    }
    setSchemaSaving(true);
    setSchemaError(null);
    try {
      let saved: Schema;
      if (schemaDraft.id) {
        saved = await apiFetch<Schema>(`/api/admin/metadata/schemas/${schemaDraft.id}`, {
          method: "PUT",
          body: JSON.stringify({
            name,
            namespace: schemaDraft.namespace.trim() || null,
            description: schemaDraft.description.trim() || null,
            active: schemaDraft.active,
          }),
        });
      } else {
        saved = await apiFetch<Schema>("/api/admin/metadata/schemas", {
          method: "POST",
          body: JSON.stringify({
            name,
            code: schemaDraft.code.trim(),
            namespace: schemaDraft.namespace.trim() || null,
            description: schemaDraft.description.trim() || null,
            active: schemaDraft.active,
          }),
        });
      }
      const edited = Boolean(schemaDraft.id);
      setSchemaDraft(null);
      await load(saved.id);
      setNotice(edited ? "Esquema actualizado." : "Esquema creado. Ahora agregá sus campos.");
    } catch (err) {
      setSchemaError(err instanceof Error ? err.message : "No se pudo guardar el esquema");
    } finally {
      setSchemaSaving(false);
    }
  }

  async function deleteSchema(schema: Schema) {
    const count = fields.filter((f) => f.schema_id === schema.id).length;
    const extra = count ? ` y sus ${count} campos` : "";
    if (!window.confirm(`¿Eliminar el esquema "${schema.name}"${extra}? Esta acción no se puede deshacer.`)) {
      return;
    }
    setBusy(schema.id);
    setError(null);
    try {
      await apiFetch(`/api/admin/metadata/schemas/${schema.id}`, { method: "DELETE" });
      await load(null);
      setNotice("Esquema eliminado.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo eliminar el esquema");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-6">
      <section className="rounded-[1.75rem] border border-slate-200 bg-white p-6 shadow-[0_20px_50px_-34px_rgba(15,23,42,0.36)]">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="space-y-3">
            <span className="inline-flex items-center gap-2 rounded-full border border-indigo-100 bg-indigo-50 px-3 py-1 text-[11px] font-medium uppercase tracking-[0.22em] text-[#4F46E5]">
              <BookMarked className="size-3.5" />
              Catálogo de metadatos
            </span>
            <div className="space-y-2">
              <h1 className="text-3xl font-semibold tracking-tight text-slate-950 sm:text-4xl">Metadatos</h1>
              <p className="max-w-2xl text-sm leading-6 text-slate-500">
                Definí los campos que publica RIDUNT en sus fichas. Todo campo activo aparece automáticamente en el
                formulario de carga, sin modificar código.
              </p>
            </div>
            <div className="flex flex-wrap gap-2 text-xs text-slate-500">
              <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 shadow-sm">Esquemas</span>
              <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 shadow-sm">Campos</span>
              <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 shadow-sm">Perfil RIDUNT</span>
              <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 shadow-sm">Carga dinámica</span>
            </div>
          </div>

          <div className="grid gap-3 sm:min-w-[380px] lg:w-[440px]">
            <div className="grid grid-cols-2 gap-3">
              <MiniStat icon={<Database className="size-3.5" />} label="Esquemas" value={String(schemas.length)} />
              <MiniStat icon={<FileText className="size-3.5" />} label="Campos activos" value={String(activeFields)} />
              <MiniStat icon={<BadgeCheck className="size-3.5" />} label="Obligatorios" value={String(requiredFields)} />
              <MiniStat icon={<Sparkles className="size-3.5" />} label="Con IA" value={String(aiFields)} />
            </div>
          </div>
        </div>
      </section>

      {error && (
        <div className="flex items-start justify-between gap-4 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
          <span>{error}</span>
          <button type="button" onClick={() => setError(null)} aria-label="Cerrar aviso" className="shrink-0">
            <X className="size-4" />
          </button>
        </div>
      )}
      {notice && (
        <div className="flex items-start justify-between gap-4 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          <span>{notice}</span>
          <button type="button" onClick={() => setNotice(null)} aria-label="Cerrar aviso" className="shrink-0">
            <X className="size-4" />
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[320px_minmax(0,1fr)]">
        <div className="space-y-4 xl:sticky xl:top-6 xl:self-start">
          <div className="overflow-hidden rounded-[1.5rem] border border-slate-200 bg-white shadow-sm">
            <div className="flex items-center justify-between gap-3 border-b border-slate-200 bg-slate-50/80 px-4 py-3">
              <div>
                <p className="text-sm font-semibold text-slate-900">Esquemas</p>
                <p className="text-[11px] text-slate-500">Elegí el perfil a editar</p>
              </div>
              <Button variant="outline" size="sm" onClick={openCreateSchema}>
                <Plus />
                Nuevo
              </Button>
            </div>
            <div className="space-y-1.5 p-2">
              {schemas.map((schema) => {
                const selected = schema.id === selectedSchemaId;
                return (
                  <button
                    key={schema.id}
                    type="button"
                    onClick={() => {
                      setSelectedSchemaId(schema.id);
                      setSearch("");
                      setFilter("all");
                    }}
                    className={`flex w-full items-center justify-between gap-3 rounded-xl border px-3 py-2.5 text-left transition-colors ${
                      selected
                        ? "border-indigo-200 bg-indigo-50/70"
                        : "border-transparent bg-transparent hover:border-slate-200 hover:bg-slate-50"
                    }`}
                  >
                    <span className="min-w-0">
                      <span
                        className={`block truncate text-sm font-medium ${
                          selected ? "text-indigo-900" : "text-slate-800"
                        }`}
                      >
                        {schema.name}
                      </span>
                      <span className="mt-0.5 block truncate font-mono text-[11px] text-slate-500">{schema.code}</span>
                    </span>
                    <span className="flex shrink-0 items-center gap-2">
                      {!schema.active && <Badge tone="rose">Inactivo</Badge>}
                      <span className="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[11px] text-slate-500">
                        {schema.field_count}
                      </span>
                      <ChevronRight className={`size-4 ${selected ? "text-indigo-500" : "text-slate-300"}`} />
                    </span>
                  </button>
                );
              })}
              {schemas.length === 0 && !loading && (
                <p className="px-3 py-6 text-center text-xs text-slate-500">
                  Todavía no hay esquemas. Aplicá el perfil RIDUNT o creá uno.
                </p>
              )}
            </div>
          </div>

          <div className="rounded-[1.5rem] border border-indigo-100 bg-gradient-to-br from-indigo-50 via-white to-white p-5 shadow-sm">
            <div className="flex items-start justify-between gap-3">
              <div className="inline-flex items-center gap-2 rounded-full border border-indigo-100 bg-white px-2.5 py-1 text-[10px] font-medium uppercase tracking-[0.2em] text-indigo-600">
                <Sparkles className="size-3" />
                Perfil RIDUNT
              </div>
              {riduntSchema && <Badge tone="emerald">Aplicado</Badge>}
            </div>
            <p className="mt-3 text-sm font-semibold text-slate-900">Perfil RIDUNT / SNRD</p>
            <p className="mt-1 text-xs leading-5 text-slate-500">
              Carga los 21 campos de las fichas de RIDUNT (autor, director, resumen, licencia y más) con sus tipos,
              validaciones y vocabularios.
            </p>
            <ul className="mt-3 space-y-1 text-[11px] text-slate-500">
              <li>· Se asigna a los tipos documentales sin selección propia.</li>
              <li>· No elimina otros esquemas ni campos.</li>
              <li>· Es idempotente: se puede volver a aplicar.</li>
              <li>· Desactiva los campos genéricos heredados.</li>
            </ul>
            <Button className="mt-4 w-full" onClick={applyRiduntProfile} disabled={busy !== null}>
              {busy === "ridunt" ? <Loader2 className="animate-spin" /> : <RotateCcw />}
              {riduntSchema ? "Actualizar perfil" : "Aplicar perfil"}
            </Button>
            <p className="mt-2 text-[11px] text-slate-400">
              {riduntSchema ? `${riduntSchema.field_count} campos en el esquema` : "Recomendado para empezar"}
            </p>
          </div>
        </div>

        <div className="min-w-0 space-y-4">
          {!selectedSchema && (
            <div className="rounded-[1.5rem] border border-dashed border-slate-300 bg-white px-6 py-16 text-center shadow-sm">
              <div className="mx-auto flex size-12 items-center justify-center rounded-2xl border border-slate-200 bg-slate-50">
                <Layers3 className="size-5 text-slate-400" />
              </div>
              <h2 className="mt-4 text-base font-semibold text-slate-900">Elegí un esquema para empezar</h2>
              <p className="mx-auto mt-1 max-w-md text-sm text-slate-500">
                Si es la primera vez, aplicá el perfil RIDUNT y sus 21 campos quedan listos para editar.
              </p>
              <div className="mt-5 flex flex-wrap justify-center gap-2">
                <Button onClick={applyRiduntProfile} disabled={busy !== null}>
                  {busy === "ridunt" ? <Loader2 className="animate-spin" /> : <Sparkles />}
                  Aplicar perfil RIDUNT
                </Button>
                <Button variant="outline" onClick={openCreateSchema}>
                  <Plus />
                  Crear esquema
                </Button>
              </div>
            </div>
          )}

          {selectedSchema && (
            <>
              <section className="rounded-[1.5rem] border border-slate-200 bg-white p-6 shadow-sm">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                  <div className="min-w-0 space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <h2 className="text-xl font-semibold tracking-tight text-slate-950">{selectedSchema.name}</h2>
                      <Badge tone="indigo">{selectedSchema.code}</Badge>
                      {selectedSchema.namespace && <Badge tone="slate">ns: {selectedSchema.namespace}</Badge>}
                      {selectedSchema.active ? <Badge tone="emerald">Activo</Badge> : <Badge tone="rose">Inactivo</Badge>}
                    </div>
                    <p className="max-w-2xl text-sm leading-6 text-slate-500">
                      {selectedSchema.description ??
                        "Sin descripción. Editá el esquema para agregar contexto institucional."}
                    </p>
                    <p className="text-xs text-slate-400">
                      {orderedFields.length} campos · {orderedFields.filter((f) => f.active).length} activos · versión{" "}
                      {selectedSchema.version}
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Button variant="outline" size="sm" onClick={openEditSchema}>
                      <Pencil />
                      Editar esquema
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      className="text-rose-700"
                      onClick={() => deleteSchema(selectedSchema)}
                      disabled={busy === selectedSchema.id}
                    >
                      {busy === selectedSchema.id ? <Loader2 className="animate-spin" /> : <Trash2 />}
                      Eliminar
                    </Button>
                    <Button size="sm" onClick={openCreateField}>
                      <Plus />
                      Nuevo campo
                    </Button>
                  </div>
                </div>
              </section>

              <section className="overflow-hidden rounded-[1.5rem] border border-slate-200 bg-white shadow-sm">
                <div className="flex flex-col gap-3 border-b border-slate-200 bg-slate-50/80 px-4 py-3 lg:flex-row lg:items-center lg:justify-between">
                  <div className="relative w-full lg:max-w-sm">
                    <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400" />
                    <input
                      className={`${inputCls} bg-white pl-9`}
                      placeholder="Buscar por etiqueta, clave o descripción…"
                      value={search}
                      onChange={(event) => setSearch(event.target.value)}
                    />
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {FILTERS.map((item) => (
                      <button
                        key={item.key}
                        type="button"
                        onClick={() => setFilter(item.key)}
                        className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                          filter === item.key
                            ? "border-indigo-200 bg-indigo-50 text-indigo-700"
                            : "border-slate-200 bg-white text-slate-500 hover:bg-slate-50"
                        }`}
                      >
                        {item.label}
                        <span className="rounded-full bg-white/70 px-1.5 text-[10px] text-slate-500">
                          {filterCounts[item.key]}
                        </span>
                      </button>
                    ))}
                  </div>
                </div>

                <div className="space-y-6 p-4">
                  {loading && (
                    <div className="flex items-center justify-center gap-2 py-16 text-sm text-slate-500">
                      <Loader2 className="size-4 animate-spin" />
                      Cargando campos…
                    </div>
                  )}

                  {!loading && groupedFields.length === 0 && (
                    <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50/60 px-6 py-14 text-center">
                      <p className="text-sm font-medium text-slate-700">
                        {orderedFields.length === 0
                          ? "Este esquema todavía no tiene campos"
                          : "No hay campos que coincidan"}
                      </p>
                      <p className="mt-1 text-xs text-slate-500">
                        {orderedFields.length === 0
                          ? "Creá el primero y aparecerá en el formulario de carga."
                          : "Probá con otra búsqueda o quitá los filtros."}
                      </p>
                      <div className="mt-4 flex flex-wrap justify-center gap-2">
                        {orderedFields.length === 0 ? (
                          <Button size="sm" onClick={openCreateField}>
                            <Plus />
                            Nuevo campo
                          </Button>
                        ) : (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => {
                              setSearch("");
                              setFilter("all");
                            }}
                          >
                            Limpiar filtros
                          </Button>
                        )}
                      </div>
                    </div>
                  )}

                  {!loading &&
                    groupedFields.map(({ group, items }) => (
                      <div key={group} className="space-y-2">
                        <div className="flex items-center gap-2 px-1">
                          <h3 className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">{group}</h3>
                          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] text-slate-500">
                            {items.length}
                          </span>
                        </div>

                        {items.map((field) => {
                          const position = orderedFields.findIndex((f) => f.id === field.id);
                          const isBusy = busy === field.id;
                          return (
                            <div
                              key={field.id}
                              className={`rounded-2xl border p-4 shadow-sm transition-colors ${
                                field.active ? "border-slate-200 bg-white" : "border-dashed border-slate-300 bg-slate-50/70"
                              }`}
                            >
                              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                                <div className="flex min-w-0 gap-3">
                                  <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-xl border border-slate-200 bg-slate-50 text-xs font-semibold text-slate-500">
                                    {position + 1}
                                  </span>
                                  <div className="min-w-0 space-y-1.5">
                                    <div className="flex flex-wrap items-center gap-2">
                                      <p
                                        className={`text-sm font-semibold ${
                                          field.active ? "text-slate-900" : "text-slate-500"
                                        }`}
                                      >
                                        {field.display_name ?? field.element}
                                      </p>
                                      {!field.active && <Badge tone="rose">Inactivo</Badge>}
                                    </div>
                                    <p className="font-mono text-[11px] text-slate-500">
                                      {dspaceKey(field.element, field.qualifier)}
                                    </p>
                                    {field.description && (
                                      <p className="max-w-xl text-xs leading-5 text-slate-500">{field.description}</p>
                                    )}
                                    <div className="flex flex-wrap gap-1.5 pt-0.5">
                                      {field.required && <Badge tone="rose">Obligatorio</Badge>}
                                      {field.repeatable && <Badge tone="sky">Repetible</Badge>}
                                      {field.ai_extractable ? (
                                        <Badge tone="indigo">IA</Badge>
                                      ) : (
                                        <Badge tone="slate">Sin IA</Badge>
                                      )}
                                      {field.validation_type === "date" && <Badge tone="amber">Fecha ISO</Badge>}
                                      {field.vocabulary_code && (
                                        <Badge tone="emerald">Vocabulario: {field.vocabulary_code}</Badge>
                                      )}
                                      <Badge tone="slate">{field.data_type}</Badge>
                                    </div>
                                  </div>
                                </div>

                                <div className="flex shrink-0 items-center gap-1 sm:pl-4">
                                  {isBusy ? (
                                    <span className="flex size-24 items-center justify-center text-slate-400">
                                      <Loader2 className="size-4 animate-spin" />
                                    </span>
                                  ) : (
                                    <>
                                      <Button
                                        variant="ghost"
                                        size="icon-sm"
                                        title="Subir"
                                        aria-label="Subir"
                                        disabled={position <= 0}
                                        onClick={() => moveField(field, -1)}
                                      >
                                        <ArrowUp />
                                      </Button>
                                      <Button
                                        variant="ghost"
                                        size="icon-sm"
                                        title="Bajar"
                                        aria-label="Bajar"
                                        disabled={position >= orderedFields.length - 1}
                                        onClick={() => moveField(field, 1)}
                                      >
                                        <ArrowDown />
                                      </Button>
                                      <Button
                                        variant="ghost"
                                        size="icon-sm"
                                        title="Editar"
                                        aria-label="Editar"
                                        onClick={() => openEditField(field)}
                                      >
                                        <Pencil />
                                      </Button>
                                      <Button
                                        variant="ghost"
                                        size="icon-sm"
                                        title={field.active ? "Desactivar" : "Activar"}
                                        aria-label={field.active ? "Desactivar" : "Activar"}
                                        onClick={() => toggleField(field)}
                                      >
                                        <BadgeCheck />
                                      </Button>
                                      <Button
                                        variant="ghost"
                                        size="icon-sm"
                                        title="Eliminar"
                                        aria-label="Eliminar"
                                        className="text-rose-600"
                                        onClick={() => deleteField(field)}
                                      >
                                        <Trash2 />
                                      </Button>
                                    </>
                                  )}
                                </div>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    ))}
                </div>
              </section>
            </>
          )}
        </div>
      </div>

      {fieldDraft && (
        <Modal
          title={fieldDraft.id ? "Editar campo" : "Nuevo campo"}
          subtitle={
            selectedSchema
              ? `Esquema ${selectedSchema.name} · clave ${dspaceKey(
                  fieldDraft.element || "elemento",
                  fieldDraft.qualifier.trim() || null,
                )}`
              : "Definición del campo"
          }
          onClose={() => setFieldDraft(null)}
          footer={
            <>
              <Button variant="outline" onClick={() => setFieldDraft(null)} disabled={fieldSaving}>
                Cancelar
              </Button>
              <Button form="field-form" type="submit" disabled={fieldSaving}>
                {fieldSaving ? <Loader2 className="animate-spin" /> : <Pencil />}
                {fieldSaving ? "Guardando…" : "Guardar campo"}
              </Button>
            </>
          }
        >
          <form id="field-form" onSubmit={saveField} className="space-y-4">
            {fieldError && (
              <p className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">{fieldError}</p>
            )}

            <div className="grid gap-3 sm:grid-cols-2">
              <label className="flex flex-col gap-1 text-xs font-medium text-slate-600">
                Elemento (Dublin Core)
                <input
                  className={inputCls}
                  list="dc-elements"
                  value={fieldDraft.element}
                  onChange={(event) => patchFieldDraft({ element: event.target.value }, !fieldDraft.id)}
                  placeholder="title"
                  required
                />
                <datalist id="dc-elements">
                  {DC_ELEMENTS.map((element) => (
                    <option key={element} value={element} />
                  ))}
                </datalist>
              </label>
              <label className="flex flex-col gap-1 text-xs font-medium text-slate-600">
                Qualifier <span className="font-normal text-slate-400">(opcional)</span>
                <input
                  className={inputCls}
                  list="dc-qualifiers"
                  value={fieldDraft.qualifier}
                  onChange={(event) => patchFieldDraft({ qualifier: event.target.value }, !fieldDraft.id)}
                  placeholder="alternative"
                />
                <datalist id="dc-qualifiers">
                  {QUALIFIER_SUGGESTIONS.map((qualifier) => (
                    <option key={qualifier} value={qualifier} />
                  ))}
                </datalist>
              </label>
            </div>

            <label className="flex flex-col gap-1 text-xs font-medium text-slate-600">
              Etiqueta visible
              <input
                className={inputCls}
                value={fieldDraft.display_name}
                onChange={(event) => patchFieldDraft({ display_name: event.target.value })}
                placeholder="Título alternativo"
              />
            </label>

            <label className="flex flex-col gap-1 text-xs font-medium text-slate-600">
              Descripción / ayuda para el catalogador
              <textarea
                className={textareaCls}
                value={fieldDraft.description}
                onChange={(event) => patchFieldDraft({ description: event.target.value })}
                placeholder="Explique qué debe cargarse en este campo y con qué formato."
              />
            </label>

            <div className="grid gap-3 sm:grid-cols-3">
              <label className="flex flex-col gap-1 text-xs font-medium text-slate-600">
                Tipo de dato
                <select
                  className={inputCls}
                  value={fieldDraft.data_type}
                  onChange={(event) => patchFieldDraft({ data_type: event.target.value })}
                >
                  {DATA_TYPES.map((type) => (
                    <option key={type} value={type}>
                      {type}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex flex-col gap-1 text-xs font-medium text-slate-600">
                Validación
                <select
                  className={inputCls}
                  value={fieldDraft.validation_type}
                  onChange={(event) => patchFieldDraft({ validation_type: event.target.value })}
                >
                  {VALIDATIONS.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex flex-col gap-1 text-xs font-medium text-slate-600">
                Vocabulario
                <select
                  className={inputCls}
                  value={fieldDraft.vocabulary_id}
                  onChange={(event) => patchFieldDraft({ vocabulary_id: event.target.value })}
                >
                  <option value="">Sin vocabulario</option>
                  {vocabularies.map((vocabulary) => (
                    <option key={vocabulary.id} value={vocabulary.id}>
                      {vocabulary.name}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <div className="grid gap-2 rounded-2xl border border-slate-200 bg-slate-50/70 p-3 sm:grid-cols-2">
              {(
                [
                  ["required", "Obligatorio", "Exige un valor para validar el documento."],
                  ["repeatable", "Repetible", "Admite varios valores por campo."],
                  ["ai_extractable", "Extraíble por IA", "La IA puede proponer el valor desde el PDF."],
                  ["editable", "Editable", "El catalogador puede corregir el valor."],
                  ["active", "Activo", "Aparece en el formulario de carga."],
                ] as const
              ).map(([key, label, hint]) => (
                <label key={key} className="flex items-start gap-2 rounded-xl bg-white/70 px-2.5 py-2">
                  <input
                    type="checkbox"
                    className="mt-0.5"
                    checked={fieldDraft[key]}
                    onChange={(event) => patchFieldDraft({ [key]: event.target.checked })}
                  />
                  <span>
                    <span className="block text-xs font-medium text-slate-700">{label}</span>
                    <span className="block text-[11px] leading-4 text-slate-400">{hint}</span>
                  </span>
                </label>
              ))}
            </div>
          </form>
        </Modal>
      )}

      {schemaDraft && (
        <Modal
          title={schemaDraft.id ? "Editar esquema" : "Nuevo esquema"}
          subtitle="Los esquemas agrupan campos y definen el namespace de las claves."
          onClose={() => setSchemaDraft(null)}
          footer={
            <>
              <Button variant="outline" onClick={() => setSchemaDraft(null)} disabled={schemaSaving}>
                Cancelar
              </Button>
              <Button form="schema-form" type="submit" disabled={schemaSaving}>
                {schemaSaving ? <Loader2 className="animate-spin" /> : <Pencil />}
                {schemaSaving ? "Guardando…" : "Guardar esquema"}
              </Button>
            </>
          }
        >
          <form id="schema-form" onSubmit={saveSchema} className="space-y-4">
            {schemaError && (
              <p className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">{schemaError}</p>
            )}
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="flex flex-col gap-1 text-xs font-medium text-slate-600">
                Nombre
                <input
                  className={inputCls}
                  value={schemaDraft.name}
                  onChange={(event) => setSchemaDraft({ ...schemaDraft, name: event.target.value })}
                  placeholder="RIDUNT / SNRD"
                  required
                />
              </label>
              <label className="flex flex-col gap-1 text-xs font-medium text-slate-600">
                Código
                <input
                  className={`${inputCls} font-mono ${schemaDraft.id ? "opacity-60" : ""}`}
                  value={schemaDraft.code}
                  onChange={(event) => setSchemaDraft({ ...schemaDraft, code: event.target.value })}
                  placeholder="snrd-dc"
                  disabled={Boolean(schemaDraft.id)}
                  required={!schemaDraft.id}
                />
              </label>
            </div>
            <label className="flex flex-col gap-1 text-xs font-medium text-slate-600">
              Namespace
              <input
                className={inputCls}
                value={schemaDraft.namespace}
                onChange={(event) => setSchemaDraft({ ...schemaDraft, namespace: event.target.value })}
                placeholder="dc"
              />
            </label>
            <label className="flex flex-col gap-1 text-xs font-medium text-slate-600">
              Descripción
              <textarea
                className={textareaCls}
                value={schemaDraft.description}
                onChange={(event) => setSchemaDraft({ ...schemaDraft, description: event.target.value })}
                placeholder="Perfil institucional basado en Dublin Core y SNRD."
              />
            </label>
            <label className="flex items-center gap-2 text-xs font-medium text-slate-700">
              <input
                type="checkbox"
                checked={schemaDraft.active}
                onChange={(event) => setSchemaDraft({ ...schemaDraft, active: event.target.checked })}
              />
              Esquema activo
            </label>
            {schemaDraft.id && (
              <p className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-[11px] text-slate-500">
                El código no se puede cambiar una vez creado porque las claves ya publicadas dependen de él.
              </p>
            )}
          </form>
        </Modal>
      )}
    </div>
  );
}
