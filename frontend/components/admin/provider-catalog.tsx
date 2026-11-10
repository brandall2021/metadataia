"use client";

import { useMemo, useState } from "react";
import { Check, Search } from "lucide-react";

import { providerTypeLabel, type ProviderPreset } from "@/lib/ai-providers";

// Proveedores que se muestran por defecto; el resto aparece al buscar.
const DEFAULT_PRESET_CODES = new Set(["openai", "anthropic", "google", "ollama", "openrouter"]);

export function ProviderCatalog({
  presets,
  connectedCodes,
  selectedCode,
  onSelect,
}: {
  presets: ProviderPreset[];
  connectedCodes: Set<string>;
  selectedCode: string | null;
  onSelect: (preset: ProviderPreset) => void;
}) {
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const term = query.trim().toLowerCase();
    return presets.filter((preset) => {
      if (!term) return DEFAULT_PRESET_CODES.has(preset.code);
      return (
        preset.name.toLowerCase().includes(term) ||
        preset.code.toLowerCase().includes(term) ||
        preset.description.toLowerCase().includes(term) ||
        providerTypeLabel(preset.type).toLowerCase().includes(term)
      );
    });
  }, [presets, query]);

  return (
    <div className="space-y-3">
      <div className="relative w-full lg:max-w-xs">
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <input
          className="w-full rounded-xl border border-border bg-muted/30 py-2 pl-9 pr-3 text-sm text-foreground placeholder:text-muted-foreground/60 outline-none transition-colors focus:border-ring focus:bg-muted/50 focus:ring-2 focus:ring-ring/30"
          placeholder="Buscar entre 25+ proveedores (Gemini, Groq, DeepSeek…)"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
      </div>

      <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
        {filtered.map((preset) => {
          const connected = connectedCodes.has(preset.code);
          const selected = selectedCode === preset.code;
          return (
            <button
              key={preset.code}
              type="button"
              onClick={() => onSelect(preset)}
              className={`flex h-full flex-col rounded-2xl border p-3 text-left shadow-sm transition-colors ${
                selected
                  ? "border-primary/40 bg-primary/5 ring-1 ring-primary/20"
                  : "border-slate-200 bg-white hover:border-primary/25 hover:bg-slate-50"
              }`}
            >
              <div className="flex w-full items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-foreground">{preset.name}</p>
                  <p className="mt-0.5 text-[11px] text-muted-foreground">{providerTypeLabel(preset.type)}</p>
                </div>
                {connected ? (
                  <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-medium text-emerald-600">
                    <Check className="size-3" />
                    Conectado
                  </span>
                ) : (
                  <span className="shrink-0 rounded-full bg-muted px-2 py-0.5 text-[10px] text-muted-foreground">
                    {preset.requiresKey ? "API key" : "Sin key"}
                  </span>
                )}
              </div>
              <p className="mt-2 line-clamp-2 text-xs leading-5 text-muted-foreground">{preset.description}</p>
            </button>
          );
        })}
      </div>

      {filtered.length === 0 && (
        <p className="rounded-xl border border-dashed border-border bg-muted/20 p-6 text-center text-sm text-muted-foreground">
          No hay proveedores que coincidan con “{query}”. Podés crear uno compatible OpenAI con “Proveedor personalizado”.
        </p>
      )}
    </div>
  );
}
