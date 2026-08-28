"use client";

import { FormEvent, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { apiFetch } from "@/lib/api";

type Schema = {
  id: string;
  name: string;
  code: string;
};

type Field = {
  id: string;
  schema_code: string;
  element: string;
  qualifier: string | null;
  display_name: string | null;
  data_type: string;
  required: boolean;
  repeatable: boolean;
  ai_extractable: boolean;
  active: boolean;
};

export default function MetadataPage() {
  const [schemas, setSchemas] = useState<Schema[]>([]);
  const [fields, setFields] = useState<Field[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    schema_id: "",
    element: "",
    qualifier: "",
    display_name: "",
    required: false,
    repeatable: false,
    ai_extractable: true,
  });

  async function load() {
    try {
      const [s, f] = await Promise.all([
        apiFetch<Schema[]>("/api/admin/metadata/schemas"),
        apiFetch<Field[]>("/api/admin/metadata/fields"),
      ]);
      setSchemas(s);
      setFields(f);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al cargar datos");
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await apiFetch<Field>("/api/admin/metadata/fields", {
        method: "POST",
        body: JSON.stringify({
          schema_id: form.schema_id,
          element: form.element.trim(),
          qualifier: form.qualifier.trim() || null,
          display_name: form.display_name.trim() || null,
          required: form.required,
          repeatable: form.repeatable,
          ai_extractable: form.ai_extractable,
        }),
      });
      setForm({
        schema_id: form.schema_id,
        element: "",
        qualifier: "",
        display_name: "",
        required: false,
        repeatable: false,
        ai_extractable: true,
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al crear el campo");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Metadatos</h1>
        <p className="text-sm text-muted-foreground">
          Campos de metadatos. Un campo creado aparece aquí y en los
          formularios de documentos automáticamente, sin modificar código.
        </p>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Nuevo campo</CardTitle>
            <CardDescription>
              El formulario de carga lo construirá dinámicamente según estos
              atributos.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleCreate} className="flex flex-col gap-3 text-sm">
              <label className="flex flex-col gap-1">
                Esquema
                <select
                  className="rounded-lg border border-border bg-background px-3 py-2"
                  value={form.schema_id}
                  onChange={(e) => setForm({ ...form, schema_id: e.target.value })}
                  required
                >
                  <option value="" disabled>
                    Seleccionar…
                  </option>
                  {schemas.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name} ({s.code})
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex flex-col gap-1">
                Elemento (Dublin Core)
                <input
                  className="rounded-lg border border-border bg-background px-3 py-2"
                  value={form.element}
                  onChange={(e) => setForm({ ...form, element: e.target.value })}
                  placeholder="title"
                  required
                />
              </label>
              <label className="flex flex-col gap-1">
                Qualifier
                <input
                  className="rounded-lg border border-border bg-background px-3 py-2"
                  value={form.qualifier}
                  onChange={(e) => setForm({ ...form, qualifier: e.target.value })}
                  placeholder="alternative"
                />
              </label>
              <label className="flex flex-col gap-1">
                Etiqueta visible
                <input
                  className="rounded-lg border border-border bg-background px-3 py-2"
                  value={form.display_name}
                  onChange={(e) => setForm({ ...form, display_name: e.target.value })}
                  placeholder="Título alternativo"
                />
              </label>
              <div className="flex flex-col gap-1 pt-1">
                {(
                  [
                    ["required", "Obligatorio"],
                    ["repeatable", "Repetible"],
                    ["ai_extractable", "Extraíble por IA"],
                  ] as const
                ).map(([key, label]) => (
                  <label key={key} className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={form[key]}
                      onChange={(e) => setForm({ ...form, [key]: e.target.checked })}
                    />
                    {label}
                  </label>
                ))}
              </div>
              <Button type="submit" disabled={saving || !form.schema_id}>
                {saving ? "Creando…" : "Crear campo"}
              </Button>
            </form>
          </CardContent>
        </Card>

        <div className="lg:col-span-2 overflow-hidden rounded-xl ring-1 ring-foreground/10">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 text-left text-xs text-muted-foreground">
              <tr>
                <th className="px-3 py-2">Etiqueta</th>
                <th className="px-3 py-2">Elemento</th>
                <th className="px-3 py-2">Qualifier</th>
                <th className="px-3 py-2">Esquema</th>
                <th className="px-3 py-2">Tipo</th>
                <th className="px-3 py-2">Requisitos</th>
              </tr>
            </thead>
            <tbody>
              {fields.map((f) => (
                <tr key={f.id} className="border-t">
                  <td className="px-3 py-2">{f.display_name ?? f.element}</td>
                  <td className="px-3 py-2 font-mono text-xs">{f.element}</td>
                  <td className="px-3 py-2 font-mono text-xs">{f.qualifier ?? "—"}</td>
                  <td className="px-3 py-2">{f.schema_code}</td>
                  <td className="px-3 py-2">{f.data_type}</td>
                  <td className="px-3 py-2 text-xs text-muted-foreground">
                    {[f.required && "oblig.", f.repeatable && "repetible", f.ai_extractable && "IA"]
                      .filter(Boolean)
                      .join(" · ") || "—"}
                  </td>
                </tr>
              ))}
              {fields.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-3 py-8 text-center text-muted-foreground">
                    Sin campos todavía. Cree el primero con el formulario.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}