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
        <h1 className="text-2xl font-bold tracking-tight">Repositorios</h1>
        <p className="text-sm text-muted-foreground">
          Configuración de repositorios DSpace (URL, autenticación), sincronización
          de comunidades/colecciones y asociación de tipos documentales.
        </p>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Nuevo repositorio</CardTitle>
            <CardDescription>
              La credencial se cifra y solo se muestra enmascarada.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleCreate} className="flex flex-col gap-3 text-sm">
              <label className="flex flex-col gap-1">
                Nombre
                <input
                  className="rounded-lg border border-border bg-background px-3 py-2"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="SEDICI"
                  required
                />
              </label>
              <label className="flex flex-col gap-1">
                Código
                <input
                  className="rounded-lg border border-border bg-background px-3 py-2"
                  value={form.code}
                  onChange={(e) => setForm({ ...form, code: e.target.value })}
                  placeholder="sedici"
                  required
                />
              </label>
              <label className="flex flex-col gap-1">
                URL pública
                <input
                  className="rounded-lg border border-border bg-background px-3 py-2"
                  value={form.base_url}
                  onChange={(e) => setForm({ ...form, base_url: e.target.value })}
                  placeholder="https://repo.example.gob.ar"
                />
              </label>
              <label className="flex flex-col gap-1">
                URL de API
                <input
                  className="rounded-lg border border-border bg-background px-3 py-2"
                  value={form.api_url}
                  onChange={(e) => setForm({ ...form, api_url: e.target.value })}
                  placeholder="https://repo.example.gob.ar/server/api"
                />
              </label>
              <label className="flex flex-col gap-1">
                Tipo de autenticación
                <select
                  className="rounded-lg border border-border bg-background px-3 py-2"
                  value={form.authentication_type}
                  onChange={(e) => setForm({ ...form, authentication_type: e.target.value })}
                >
                  <option value="">Seleccionar…</option>
                  <option value="basic">Basic</option>
                  <option value="token">Token</option>
                </select>
              </label>
              <label className="flex flex-col gap-1">
                Usuario
                <input
                  className="rounded-lg border border-border bg-background px-3 py-2"
                  value={form.username}
                  onChange={(e) => setForm({ ...form, username: e.target.value })}
                  placeholder="usuario"
                />
              </label>
              <label className="flex flex-col gap-1">
                Credencial
                <input
                  type="password"
                  className="rounded-lg border border-border bg-background px-3 py-2"
                  value={form.credential}
                  onChange={(e) => setForm({ ...form, credential: e.target.value })}
                  placeholder="password / token"
                />
              </label>
              <Button type="submit" disabled={saving}>
                {saving ? "Creando…" : "Crear repositorio"}
              </Button>
            </form>
          </CardContent>
        </Card>

        <div className="lg:col-span-2 space-y-4">
          {repos.map((repo) => {
            const open = expanded === repo.id;
            return (
              <div key={repo.id} className="overflow-hidden rounded-xl ring-1 ring-foreground/10">
                <div className="flex items-center justify-between gap-3 px-4 py-3">
                  <button
                    className="flex flex-1 items-center gap-3 text-left"
                    onClick={() => toggleExpand(repo.id)}
                  >
                    <div className="flex-1">
                      <div className="font-medium">{repo.name}</div>
                      <div className="text-xs text-muted-foreground">
                        {repo.code}
                        {repo.base_url ? ` · ${repo.base_url}` : ""}
                        {repo.username ? ` · ${repo.username}` : ""}
                      </div>
                    </div>
                    <span
                      className={
                        repo.active
                          ? "rounded-full bg-emerald-500/15 px-2 py-0.5 text-xs text-emerald-600"
                          : "rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground"
                      }
                    >
                      {repo.active ? "Activo" : "Inactivo"}
                    </span>
                  </button>
                  <div className="flex items-center gap-2">
                    {repo.active && (
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={busy === `sync:${repo.id}`}
                        onClick={() => sync(repo)}
                      >
                        {busy === `sync:${repo.id}` ? "Sincronizando…" : "Sincronizar"}
                      </Button>
                    )}
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => toggleRepo(repo, !repo.active)}
                    >
                      {repo.active ? "Desactivar" : "Activar"}
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => deleteRepo(repo)}>
                      Eliminar
                    </Button>
                  </div>
                </div>

                {open && (
                  <div className="border-t">
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead className="bg-muted/50 text-left text-xs text-muted-foreground">
                          <tr>
                            <th className="px-3 py-2">Colección</th>
                            <th className="px-3 py-2">Handle</th>
                            <th className="px-3 py-2">Tipo documental</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(cols[repo.id] ?? []).map((c) => (
                            <tr key={c.id} className="border-t">
                              <td className="px-3 py-2">
                                {c.name ?? c.external_id ?? "—"}
                              </td>
                              <td className="px-3 py-2 font-mono text-xs">
                                {c.handle ?? "—"}
                              </td>
                              <td className="px-3 py-2">
                                <select
                                  className="rounded-lg border border-border bg-background px-2 py-1 text-sm"
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
                                className="px-3 py-6 text-center text-muted-foreground"
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
            <div className="rounded-xl ring-1 ring-foreground/10 p-8 text-center text-muted-foreground">
              Sin repositorios todavía. Cree el primero con el formulario.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
