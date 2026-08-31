"use client";

import { FormEvent, useEffect, useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  Database,
  Plus,
  Power,
  RefreshCw,
  Trash2,
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

type Repository = {
  id: string;
  name: string;
  code: string;
  base_url: string | null;
  api_url: string | null;
  authentication_type: string | null;
  username: string | null;
  credential: string | null;
  active: boolean;
};
type Collection = {
  id: string;
  repository_id: string;
  external_id: string | null;
  name: string | null;
  handle: string | null;
  document_type_id: string | null;
  document_type_code: string | null;
  active: boolean;
};
type DocType = { id: string; name: string; code: string };
type SyncOut = { repository_id: string; communities: number; collections: number };

const inputCls =
  "w-full rounded-lg border border-border bg-muted/30 px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground/60 outline-none transition-colors focus:border-ring focus:bg-muted/50 focus:ring-2 focus:ring-ring/30";

function StatusBadge({ active }: { active: boolean }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium ${
        active
          ? "bg-emerald-500/15 text-emerald-500"
          : "bg-muted text-muted-foreground"
      }`}
    >
      <span className={`size-1.5 rounded-full ${active ? "bg-emerald-500" : "bg-muted-foreground/60"}`} />
      {active ? "Activo" : "Inactivo"}
    </span>
  );
}

export default function RepositoriesPage() {
  const [repos, setRepos] = useState<Repository[]>([]);
  const [cols, setCols] = useState<Record<string, Collection[]>>({});
  const [docTypes, setDocTypes] = useState<DocType[]>([]);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    name: "",
    code: "",
    base_url: "",
    api_url: "",
    authentication_type: "",
    username: "",
    credential: "",
  });

  async function loadCollections(repoId: string) {
    try {
      const c = await apiFetch<Collection[]>(`/api/admin/repositories/${repoId}/collections`);
      setCols((prev) => ({ ...prev, [repoId]: c }));
    } catch {
      setCols((prev) => ({ ...prev, [repoId]: [] }));
    }
  }

  async function load() {
    try {
      const [r, d] = await Promise.all([
        apiFetch<Repository[]>("/api/admin/repositories"),
        apiFetch<DocType[]>("/api/admin/document-types"),
      ]);
      setRepos(r);
      setDocTypes(d);
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
      await apiFetch<Repository>("/api/admin/repositories", {
        method: "POST",
        body: JSON.stringify({
          name: form.name.trim(),
          code: form.code.trim(),
          base_url: form.base_url.trim() || null,
          api_url: form.api_url.trim() || null,
          authentication_type: form.authentication_type.trim() || null,
          username: form.username.trim() || null,
          credential: form.credential || null,
        }),
      });
      setForm({
        name: "",
        code: "",
        base_url: "",
        api_url: "",
        authentication_type: "",
        username: "",
        credential: "",
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al crear el repositorio");
    } finally {
      setSaving(false);
    }
  }

  async function toggleRepo(repo: Repository, active: boolean) {
    setError(null);
    try {
      await apiFetch<Repository>(`/api/admin/repositories/${repo.id}`, {
        method: "PUT",
        body: JSON.stringify({ active }),
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al actualizar");
    }
  }

  async function deleteRepo(repo: Repository) {
    if (!window.confirm(`¿Eliminar el repositorio "${repo.name}"?`)) return;
    setError(null);
    try {
      await apiFetch<void>(`/api/admin/repositories/${repo.id}`, { method: "DELETE" });
      await load();
      setCols((prev) => {
        const next = { ...prev };
        delete next[repo.id];
        return next;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al eliminar");
    }
  }

  async function sync(repo: Repository) {
    setBusy(`sync:${repo.id}`);
    setError(null);
    try {
      const res = await apiFetch<SyncOut>(
        `/api/admin/repositories/${repo.id}/collections/sync`,
        { method: "POST" },
      );
      await loadCollections(repo.id);
      setError(
        `Sincronizados ${res.communities} comunidades y ${res.collections} colecciones.`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al sincronizar");
    } finally {
      setBusy(null);
    }
  }

  async function setCollectionType(col: Collection, document_type_id: string) {
    setBusy(`col:${col.id}`);
    setError(null);
    try {
      await apiFetch<Collection>(
        `/api/admin/repositories/${col.repository_id}/collections/${col.id}`,
        { method: "PUT", body: JSON.stringify({ document_type_id: document_type_id || null }) },
      );
      await loadCollections(col.repository_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al asociar tipo");
    } finally {
      setBusy(null);
    }
  }

  function toggleExpand(repoId: string) {
    setExpanded((prev) => {
      const next = prev === repoId ? null : repoId;
      if (next && !cols[next]) loadCollections(next);
      return next;
    });
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-bold tracking-tight">
          <Database className="size-6 text-primary" />
          Repositorios
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Configuración de repositorios DSpace (URL, autenticación), sincronización
          de comunidades/colecciones y asociación de tipos documentales.
        </p>
      </div>

      {error && (
        <p
          className={`rounded-lg border px-3 py-2 text-sm ${
            error.startsWith("Sincronizados")
              ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-500"
              : "border-destructive/30 bg-destructive/10 text-destructive"
          }`}
        >
          {error}
        </p>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="h-fit">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Plus className="size-4" />
              Nuevo repositorio
            </CardTitle>
            <CardDescription>
              La credencial se cifra y solo se muestra enmascarada.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleCreate} className="flex flex-col gap-3 text-sm">
              <label className="flex flex-col gap-1.5">
                <span className="text-xs font-medium text-muted-foreground">Nombre</span>
                <input
                  className={inputCls}
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="SEDICI"
                  required
                />
              </label>
              <label className="flex flex-col gap-1.5">
                <span className="text-xs font-medium text-muted-foreground">Código</span>
                <input
                  className={inputCls}
                  value={form.code}
                  onChange={(e) => setForm({ ...form, code: e.target.value })}
                  placeholder="sedici"
                  required
                />
              </label>
              <label className="flex flex-col gap-1.5">
                <span className="text-xs font-medium text-muted-foreground">URL pública</span>
                <input
                  className={inputCls}
                  value={form.base_url}
                  onChange={(e) => setForm({ ...form, base_url: e.target.value })}
                  placeholder="https://repo.example.gob.ar"
                />
              </label>
              <label className="flex flex-col gap-1.5">
                <span className="text-xs font-medium text-muted-foreground">URL de API</span>
                <input
                  className={inputCls}
                  value={form.api_url}
                  onChange={(e) => setForm({ ...form, api_url: e.target.value })}
                  placeholder="https://repo.example.gob.ar/server/api"
                />
              </label>
              <label className="flex flex-col gap-1.5">
                <span className="text-xs font-medium text-muted-foreground">Tipo de autenticación</span>
                <select
                  className={inputCls}
                  value={form.authentication_type}
                  onChange={(e) => setForm({ ...form, authentication_type: e.target.value })}
                >
                  <option value="">Seleccionar…</option>
                  <option value="basic">Basic</option>
                  <option value="token">Token</option>
                </select>
              </label>
              <div className="grid grid-cols-2 gap-3">
                <label className="flex flex-col gap-1.5">
                  <span className="text-xs font-medium text-muted-foreground">Usuario</span>
                  <input
                    className={inputCls}
                    value={form.username}
                    onChange={(e) => setForm({ ...form, username: e.target.value })}
                    placeholder="usuario"
                  />
                </label>
                <label className="flex flex-col gap-1.5">
                  <span className="text-xs font-medium text-muted-foreground">Credencial</span>
                  <input
                    type="password"
                    className={inputCls}
                    value={form.credential}
                    onChange={(e) => setForm({ ...form, credential: e.target.value })}
                    placeholder="password"
                  />
                </label>
              </div>
              <Button type="submit" disabled={saving} className="mt-1">
                {saving ? "Creando…" : "Crear repositorio"}
              </Button>
            </form>
          </CardContent>
        </Card>

        <div className="lg:col-span-2 space-y-3">
          {repos.map((repo) => {
            const open = expanded === repo.id;
            return (
              <div
                key={repo.id}
                className="overflow-hidden rounded-xl ring-1 ring-foreground/10 transition-colors"
              >
                <div className="flex items-center gap-3 px-4 py-3">
                  <button
                    className="flex flex-1 items-center gap-3 rounded-lg p-1 text-left transition-colors hover:bg-muted/40"
                    onClick={() => toggleExpand(repo.id)}
                  >
                    {open ? (
                      <ChevronDown className="size-4 shrink-0 text-muted-foreground" />
                    ) : (
                      <ChevronRight className="size-4 shrink-0 text-muted-foreground" />
                    )}
                    <div className="flex-1">
                      <div className="flex items-center gap-2 font-medium">
                        {repo.name}
                        <StatusBadge active={repo.active} />
                      </div>
                      <div className="mt-0.5 text-xs text-muted-foreground">
                        {repo.code}
                        {repo.base_url ? ` · ${repo.base_url}` : ""}
                        {repo.username ? ` · ${repo.username}` : ""}
                      </div>
                    </div>
                  </button>
                  <div className="flex shrink-0 items-center gap-1">
                    {repo.active && (
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={busy === `sync:${repo.id}`}
                        onClick={() => sync(repo)}
                      >
                        <RefreshCw
                          className={busy === `sync:${repo.id}` ? "animate-spin" : ""}
                        />
                        {busy === `sync:${repo.id}` ? "Sincronizando" : "Sincronizar"}
                      </Button>
                    )}
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      title={repo.active ? "Desactivar" : "Activar"}
                      onClick={() => toggleRepo(repo, !repo.active)}
                    >
                      <Power />
                    </Button>
                    <Button
                      variant="destructive"
                      size="icon-sm"
                      title="Eliminar"
                      onClick={() => deleteRepo(repo)}
                    >
                      <Trash2 />
                    </Button>
                  </div>
                </div>

                {open && (
                  <div className="border-t">
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead className="bg-muted/50 text-left text-xs text-muted-foreground">
                          <tr>
                            <th className="px-4 py-3 font-medium">Colección</th>
                            <th className="px-4 py-3 font-medium">Handle</th>
                            <th className="px-4 py-3 font-medium">Tipo documental</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(cols[repo.id] ?? []).map((c) => (
                            <tr key={c.id} className="border-t transition-colors hover:bg-muted/30">
                              <td className="px-4 py-2.5">
                                {c.name ?? c.external_id ?? "—"}
                              </td>
                              <td className="px-4 py-2.5 font-mono text-xs text-muted-foreground">
                                {c.handle ?? "—"}
                              </td>
                              <td className="px-4 py-2.5">
                                <select
                                  className="rounded-lg border border-border bg-muted/30 px-2 py-1 text-sm outline-none transition-colors focus:border-ring focus:ring-2 focus:ring-ring/30"
                                  value={c.document_type_id ?? ""}
                                  disabled={busy === `col:${c.id}`}
                                  onChange={(e) => setCollectionType(c, e.target.value)}
                                >
                                  <option value="">—</option>
                                  {docTypes.map((d) => (
                                    <option key={d.id} value={d.id}>
                                      {d.name} ({d.code})
                                    </option>
                                  ))}
                                </select>
                              </td>
                            </tr>
                          ))}
                          {(cols[repo.id] ?? []).length === 0 && (
                            <tr>
                              <td
                                colSpan={3}
                                className="px-4 py-6 text-center text-muted-foreground"
                              >
                                Sin colecciones. Pulse «Sincronizar» para traerlas de DSpace.
                              </td>
                            </tr>
                          )}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
          {repos.length === 0 && (
            <div className="rounded-xl ring-1 ring-foreground/10 p-10 text-center">
              <Database className="mx-auto mb-2 size-8 opacity-40" />
              <p className="text-sm text-muted-foreground">
                Sin repositorios todavía. Cree el primero con el formulario.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
