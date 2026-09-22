"use client";

import { FormEvent, useEffect, useState } from "react";
import { KeyRound, PencilLine, Save, Shield, Trash2, UserPlus, Users, type LucideIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { apiFetch } from "@/lib/api";

type UserOut = {
  id: string;
  username: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  active: boolean;
  created_at: string;
  updated_at: string;
  roles: string[];
};

type RoleOut = {
  id: string;
  name: string;
  description: string | null;
  permissions: string[];
};

type PermissionOut = {
  code: string;
  description: string;
};

const inputCls =
  "w-full rounded-xl border border-border bg-muted/30 px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground/60 outline-none transition-colors focus:border-ring focus:bg-muted/50 focus:ring-2 focus:ring-ring/30";

function MiniStat({ label, value, icon: Icon }: { label: string; value: string; icon: LucideIcon }) {
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

type UserForm = {
  username: string;
  email: string;
  password: string;
  first_name: string;
  last_name: string;
  active: boolean;
  role_codes: string[];
};

type RoleDraft = {
  description: string;
  permission_codes: string[];
};

const emptyUserForm: UserForm = {
  username: "",
  email: "",
  password: "",
  first_name: "",
  last_name: "",
  active: true,
  role_codes: [],
};

function toMaybe(value: string): string | null {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function formatDate(value: string): string {
  return new Date(value).toLocaleString("es-AR");
}

function roleDraftsFromRoles(roles: RoleOut[]): Record<string, RoleDraft> {
  return Object.fromEntries(
    roles.map((role) => [
      role.id,
      {
        description: role.description ?? "",
        permission_codes: [...role.permissions],
      },
    ]),
  );
}

export default function AdminUsersPage() {
  const [users, setUsers] = useState<UserOut[]>([]);
  const [roles, setRoles] = useState<RoleOut[]>([]);
  const [permissions, setPermissions] = useState<PermissionOut[]>([]);
  const [userForm, setUserForm] = useState<UserForm>(emptyUserForm);
  const [editingUserId, setEditingUserId] = useState<string | null>(null);
  const [roleDrafts, setRoleDrafts] = useState<Record<string, RoleDraft>>({});
  const [error, setError] = useState<string | null>(null);
  const [savingUser, setSavingUser] = useState(false);
  const [savingRole, setSavingRole] = useState<string | null>(null);
  const [deletingUser, setDeletingUser] = useState<string | null>(null);

  async function load() {
    try {
      const [usersData, rolesData, permissionsData] = await Promise.all([
        apiFetch<UserOut[]>("/api/users"),
        apiFetch<RoleOut[]>("/api/roles"),
        apiFetch<PermissionOut[]>("/api/permissions"),
      ]);
      setUsers(usersData);
      setRoles(rolesData);
      setPermissions(permissionsData);
      setRoleDrafts((prev) => {
        const next = roleDraftsFromRoles(rolesData);
        for (const [roleId, draft] of Object.entries(prev)) {
          if (next[roleId]) next[roleId] = { ...next[roleId], ...draft };
        }
        return next;
      });
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al cargar usuarios y roles");
    }
  }

  useEffect(() => {
    load();
  }, []);

  function startCreate() {
    setEditingUserId(null);
    setUserForm(emptyUserForm);
  }

  function startEdit(user: UserOut) {
    setEditingUserId(user.id);
    setUserForm({
      username: user.username,
      email: user.email,
      password: "",
      first_name: user.first_name ?? "",
      last_name: user.last_name ?? "",
      active: user.active,
      role_codes: [...user.roles],
    });
  }

  function toggleUserRole(code: string) {
    setUserForm((prev) => {
      const exists = prev.role_codes.includes(code);
      return { ...prev, role_codes: exists ? prev.role_codes.filter((item) => item !== code) : [...prev.role_codes, code] };
    });
  }

  async function saveUser(e: FormEvent) {
    e.preventDefault();
    setSavingUser(true);
    setError(null);
    try {
      const payload: Record<string, unknown> = {
        email: userForm.email.trim(),
        first_name: toMaybe(userForm.first_name),
        last_name: toMaybe(userForm.last_name),
        active: userForm.active,
        role_codes: userForm.role_codes,
      };
      if (!editingUserId) {
        payload.username = userForm.username.trim();
        payload.password = userForm.password;
      } else if (userForm.password.trim()) {
        payload.password = userForm.password;
      }
      const method = editingUserId ? "PUT" : "POST";
      const path = editingUserId ? `/api/users/${editingUserId}` : "/api/users";
      await apiFetch(path, { method, body: JSON.stringify(payload) });
      await load();
      startCreate();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo guardar el usuario");
    } finally {
      setSavingUser(false);
    }
  }

  async function deleteUser(user: UserOut) {
    if (!window.confirm(`¿Eliminar a ${user.username}?`)) return;
    setDeletingUser(user.id);
    setError(null);
    try {
      await apiFetch(`/api/users/${user.id}`, { method: "DELETE" });
      if (editingUserId === user.id) startCreate();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo eliminar el usuario");
    } finally {
      setDeletingUser(null);
    }
  }

  async function saveRole(role: RoleOut) {
    const draft = roleDrafts[role.id];
    if (!draft) return;
    setSavingRole(role.id);
    setError(null);
    try {
      await apiFetch(`/api/roles/${role.id}`, {
        method: "PUT",
        body: JSON.stringify({ description: toMaybe(draft.description) }),
      });
      await apiFetch(`/api/roles/${role.id}/permissions`, {
        method: "PUT",
        body: JSON.stringify({ permission_codes: draft.permission_codes }),
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo guardar el rol");
    } finally {
      setSavingRole(null);
    }
  }

  function toggleRolePermission(roleId: string, code: string) {
    setRoleDrafts((prev) => {
      const current = prev[roleId] ?? { description: "", permission_codes: [] };
      const exists = current.permission_codes.includes(code);
      return {
        ...prev,
        [roleId]: {
          ...current,
          permission_codes: exists
            ? current.permission_codes.filter((item) => item !== code)
            : [...current.permission_codes, code],
        },
      };
    });
  }

  const userCount = users.length;
  const activeCount = users.filter((user) => user.active).length;
  const roleCount = roles.length;

  return (
    <div className="space-y-6">
      <section className="rounded-3xl border border-border/70 bg-gradient-to-br from-primary/[0.08] via-background to-muted/40 p-6 shadow-sm">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="space-y-2">
            <span className="inline-flex items-center gap-2 rounded-full border border-primary/15 bg-primary/10 px-3 py-1 text-[11px] uppercase tracking-[0.22em] text-primary">
              <Shield className="size-3.5" />
              RBAC
            </span>
            <h1 className="text-3xl font-semibold tracking-tight">Usuarios y roles</h1>
            <p className="max-w-2xl text-sm leading-6 text-muted-foreground">
              Administrá cuentas, roles y permisos sin tocar la base de datos a mano.
            </p>
          </div>
          <div className="grid grid-cols-3 gap-3 sm:min-w-[360px] lg:w-[420px]">
            <MiniStat label="Usuarios" value={String(userCount)} icon={Users} />
            <MiniStat label="Activos" value={String(activeCount)} icon={UserPlus} />
            <MiniStat label="Roles" value={String(roleCount)} icon={KeyRound} />
          </div>
        </div>
      </section>

      {error && <p className="rounded-xl border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}

      <div className="grid gap-6 xl:grid-cols-[1fr_1.2fr]">
        <Card className="border-border/70 shadow-sm">
          <CardHeader className="border-b border-border/60 bg-muted/20">
            <CardTitle className="flex items-center gap-2 text-lg">
              <UserPlus className="size-4" />
              {editingUserId ? "Editar usuario" : "Nuevo usuario"}
            </CardTitle>
            <CardDescription>Usuarios del sistema y sus roles de acceso.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 p-4">
            <form onSubmit={saveUser} className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <label className="space-y-1 text-sm">
                  <span>Usuario</span>
                  <input
                    className={inputCls}
                    value={userForm.username}
                    onChange={(e) => setUserForm({ ...userForm, username: e.target.value })}
                    disabled={Boolean(editingUserId)}
                    required
                  />
                </label>
                <label className="space-y-1 text-sm">
                  <span>Email</span>
                  <input
                    className={inputCls}
                    type="email"
                    value={userForm.email}
                    onChange={(e) => setUserForm({ ...userForm, email: e.target.value })}
                    required
                  />
                </label>
                <label className="space-y-1 text-sm">
                  <span>{editingUserId ? "Nueva contraseña" : "Contraseña"}</span>
                  <input
                    className={inputCls}
                    type="password"
                    value={userForm.password}
                    onChange={(e) => setUserForm({ ...userForm, password: e.target.value })}
                    required={!editingUserId}
                  />
                </label>
                <label className="space-y-1 text-sm">
                  <span>Estado</span>
                  <select
                    className={inputCls}
                    value={userForm.active ? "true" : "false"}
                    onChange={(e) => setUserForm({ ...userForm, active: e.target.value === "true" })}
                  >
                    <option value="true">Activo</option>
                    <option value="false">Inactivo</option>
                  </select>
                </label>
                <label className="space-y-1 text-sm">
                  <span>Nombre</span>
                  <input
                    className={inputCls}
                    value={userForm.first_name}
                    onChange={(e) => setUserForm({ ...userForm, first_name: e.target.value })}
                  />
                </label>
                <label className="space-y-1 text-sm">
                  <span>Apellido</span>
                  <input
                    className={inputCls}
                    value={userForm.last_name}
                    onChange={(e) => setUserForm({ ...userForm, last_name: e.target.value })}
                  />
                </label>
              </div>

              <div className="space-y-2">
                <p className="text-sm font-medium">Roles</p>
                <div className="grid gap-2 sm:grid-cols-2">
                  {roles.map((role) => {
                    const checked = userForm.role_codes.includes(role.name);
                    return (
                      <label key={role.id} className="flex items-center gap-2 rounded-2xl border border-border/60 bg-muted/20 px-3 py-2 text-sm">
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => toggleUserRole(role.name)}
                        />
                        <span className="font-medium">{role.name}</span>
                        <span className="text-xs text-muted-foreground">{role.description ?? "Sin descripción"}</span>
                      </label>
                    );
                  })}
                </div>
              </div>

              <div className="flex flex-wrap gap-2">
                <Button type="submit" className="gap-2" disabled={savingUser}>
                  {savingUser ? <span>Guardando…</span> : <><Save className="size-4" /> Guardar usuario</>}
                </Button>
                <Button type="button" variant="outline" onClick={startCreate}>
                  Limpiar
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>

        <Card className="border-border/70 shadow-sm">
          <CardHeader className="border-b border-border/60 bg-muted/20">
            <CardTitle className="flex items-center gap-2 text-lg">
              <PencilLine className="size-4" />
              Usuarios
            </CardTitle>
            <CardDescription>Editar, activar o eliminar cuentas del sistema.</CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            <div className="divide-y divide-border/60">
              {users.map((user) => (
                <div key={user.id} className="grid gap-4 p-4 xl:grid-cols-[1.2fr_0.8fr_auto] xl:items-start">
                  <div>
                    <p className="font-medium">{user.username}</p>
                    <p className="text-sm text-muted-foreground">{user.email}</p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {user.first_name || user.last_name ? `${user.first_name ?? ""} ${user.last_name ?? ""}`.trim() : "Sin nombre"}
                    </p>
                  </div>
                  <div className="space-y-2 text-sm">
                    <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Roles</p>
                    <div className="flex flex-wrap gap-2">
                      {user.roles.length > 0 ? user.roles.map((role) => (
                        <span key={role} className="rounded-full bg-muted px-2.5 py-1 text-xs">{role}</span>
                      )) : <span className="text-muted-foreground">Sin roles</span>}
                    </div>
                    <p className="text-xs text-muted-foreground">
                      {user.active ? "Activo" : "Inactivo"} · {formatDate(user.updated_at)}
                    </p>
                  </div>
                  <div className="flex gap-2 xl:flex-col">
                    <Button variant="outline" size="sm" className="gap-2" onClick={() => startEdit(user)}>
                      <PencilLine className="size-4" />
                      Editar
                    </Button>
                    <Button variant="outline" size="sm" className="gap-2" disabled={deletingUser === user.id} onClick={() => void deleteUser(user)}>
                      <Trash2 className="size-4" />
                      {deletingUser === user.id ? "Eliminando…" : "Eliminar"}
                    </Button>
                  </div>
                </div>
              ))}
              {users.length === 0 && <div className="p-6 text-sm text-muted-foreground">Sin usuarios.</div>}
            </div>
          </CardContent>
        </Card>
      </div>

      <Card className="border-border/70 shadow-sm">
        <CardHeader className="border-b border-border/60 bg-muted/20">
          <CardTitle className="flex items-center gap-2 text-lg">
            <KeyRound className="size-4" />
            Roles y permisos
          </CardTitle>
          <CardDescription>Editar descripción y permisos efectivos de cada rol.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4 p-4">
          <div className="grid gap-4 xl:grid-cols-3">
            {roles.map((role) => {
              const draft = roleDrafts[role.id] ?? { description: role.description ?? "", permission_codes: [...role.permissions] };
              return (
                <div key={role.id} className="rounded-2xl border border-border/60 bg-background p-4">
                  <div className="space-y-3">
                    <div>
                      <p className="font-medium">{role.name}</p>
                      <p className="text-xs text-muted-foreground">{role.permissions.length} permisos</p>
                    </div>
                    <label className="block space-y-1 text-sm">
                      <span>Descripción</span>
                    <textarea
                      className={`${inputCls} min-h-20 resize-y`}
                      value={draft.description}
                      onChange={(e) =>
                        setRoleDrafts((prev) => ({
                          ...prev,
                          [role.id]: { ...(prev[role.id] ?? draft), description: e.target.value },
                        }))
                      }
                    />
                    </label>
                    <div className="space-y-2">
                      <p className="text-sm font-medium">Permisos</p>
                      <div className="max-h-64 space-y-2 overflow-auto rounded-2xl border border-border/50 bg-muted/10 p-3">
                        {permissions.map((permission) => {
                          const checked = draft.permission_codes.includes(permission.code);
                          return (
                            <label key={permission.code} className="flex items-start gap-2 rounded-xl px-2 py-1.5 text-sm hover:bg-background/70">
                              <input
                                type="checkbox"
                                className="mt-1"
                                checked={checked}
                                onChange={() => toggleRolePermission(role.id, permission.code)}
                              />
                              <span>
                                <span className="font-medium">{permission.code}</span>
                                <span className="ml-2 text-xs text-muted-foreground">{permission.description}</span>
                              </span>
                            </label>
                          );
                        })}
                      </div>
                    </div>
                    <Button variant="outline" size="sm" className="gap-2" disabled={savingRole === role.id} onClick={() => void saveRole(role)}>
                      {savingRole === role.id ? <span>Guardando…</span> : <><Save className="size-4" /> Guardar rol</>}
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
