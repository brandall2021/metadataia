"use client";

// Tipos y piezas compartidas por las páginas de /admin/ai
// (Agentes, Modelos, Proveedores).

export type Model = {
  id: string;
  provider_id: string;
  provider_name: string;
  name: string;
  model_identifier: string;
  context_window: number | null;
  supports_json: boolean;
  supports_vision: boolean;
  temperature_default: number | null;
  max_tokens_default: number | null;
  active: boolean;
  configuration_json: Record<string, unknown> | null;
};

export type AgentVersion = {
  id: string;
  version_number: number;
  model_id: string;
  model_name: string;
  model_identifier: string;
  system_prompt: string | null;
  extraction_prompt: string | null;
  temperature: number | null;
  max_tokens: number | null;
  output_schema_json: Record<string, unknown> | null;
  configuration_json: Record<string, unknown> | null;
  active: boolean;
  created_at: string;
};

export type Agent = {
  id: string;
  name: string;
  code: string;
  description: string | null;
  document_type_id: string | null;
  active: boolean;
  current_version: AgentVersion | null;
};

export type DocType = { id: string; name: string; code: string };

export type Provider = {
  id: string;
  name: string;
  code: string;
  type: string;
  base_url: string | null;
  active: boolean;
  api_key_masked: string;
  configuration_json: Record<string, unknown> | null;
};

export type DiscoveredModel = { id: string; owned_by?: string | null; created?: number | null };
export type Discovery = {
  ok: boolean;
  message: string;
  models: DiscoveredModel[];
  detail?: string | null;
};
export type ImportResult = { created: Model[]; skipped: string[] };

export const inputCls =
  "w-full rounded-xl border border-border bg-muted/30 px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground/60 outline-none transition-colors focus:border-ring focus:bg-muted/50 focus:ring-2 focus:ring-ring/30";

export function StatusBadge({ active, onClick }: { active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      title={active ? "Desactivar" : "Activar"}
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium transition-colors ${
        active
          ? "bg-emerald-500/15 text-emerald-500 hover:bg-emerald-500/25"
          : "bg-muted text-muted-foreground hover:bg-muted/70"
      }`}
    >
      <span className={`size-1.5 rounded-full ${active ? "bg-emerald-500" : "bg-muted-foreground/60"}`} />
      {active ? "Activo" : "Inactivo"}
    </button>
  );
}

export function ErrorBanner({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <p className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
      {message}
    </p>
  );
}
