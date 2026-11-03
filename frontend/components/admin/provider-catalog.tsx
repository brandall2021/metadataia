"use client";

import { useMemo, useState } from "react";
import { Check, Search } from "lucide-react";

import {
  PROVIDER_CATEGORIES,
  providerTypeLabel,
  type ProviderCategory,
  type ProviderPreset,
} from "@/lib/ai-providers";

const chipCls =
  "rounded-full border px-2.5 py-1 text-[11px] font-medium transition-colors";

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
  const [category, setCategory] = useState<ProviderCategory | "all">("all");

  const filtered = useMemo(() => {
    const term = query.trim().toLowerCase();
    return presets.filter((preset) => {
      if (category !== "all" && preset.category !== category) return false;
      if (!term) return true;
      return (
        preset.name.toLowerCase().includes(term) ||
        preset.code.toLowerCase().includes(term) ||
        preset.description.toLowerCase().includes(term) ||
        providerTypeLabel(preset.type).toLowerCase().includes(term)
      );
    });
  }, [presets, query, category]);

  return (
    <div className="space-y-3">
      <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
        <div className="relative w-full lg:max-w-xs">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <input
            className="w-full rounded-xl border border-border bg-muted/30 py-2 pl-9 pr-3 text-sm text-foreground placeholder:text-muted-foreground/60 outline-none transition-colors focus:border-ring focus:bg-muted/50 focus:ring-2 focus:ring-ring/30"
            placeholder="Buscar proveedor (OpenAI, Gemini, Groq…)"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>
        <div className="flex flex-wrap gap-1.5">
          {PROVIDER_CATEGORIES.map((item) => (
            <button
              key={item.value}
              type="button"
              onClick={() => setCategory(item.value)}
              className={`${chipCls} ${
                category === item.value
                  ? "border-primary/30 bg-primary/10 text-primary"
                  : "border-border bg-background text-muted-foreground hover:bg-muted"
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
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
              <p className="mt-auto pt-2 text-[10px] uppercase tracking-[0.16em] text-muted-foreground/80">
                {preset.models.length > 0
                  ? `${preset.models.length} modelos sugeridos`
                  : "Carga manual de modelos"}
              </p>
            </button>
          );
        })}
      </div>

      {filtered.length === 0 && (
        <p className="rounded-xl border border-dashed border-border bg-muted/20 p-6 text-center text-sm text-muted-foreground">
          No hay proveedores que coincidan con “{query}”. Podés crear uno compatible OpenAI desde el formulario.
        </p>
      )}
    </div>
  );
}
