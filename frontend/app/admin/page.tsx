"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  Bot,
  CheckCircle2,
  Clock3,
  Database,
  FileSliders,
  Gauge,
  RefreshCw,
  Server,
  ShieldCheck,
  Sparkles,
  Settings2,
  Users,
  type LucideIcon,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { apiFetch } from "@/lib/api";
import { cn } from "@/lib/utils";

type DashboardOut = {
  documentos: {
    total: number;
    procesados: number;
    pendientes_revision: number;
    aprobados: number;
    rechazados: number;
    depositados: number;
    por_estado: Record<string, number>;
  };
  procesamiento: {
    ocr_ejecutados: number;
    extracciones_ia: number;
    normalizaciones: number;
    validaciones: number;
    tiempo_promedio_ms: number | null;
    tiempo_promedio_por_tipo: Record<string, number>;
    errores: number;
    errores_por_tipo: Record<string, number>;
    jobs_por_estado: Record<string, number>;
  };
  ia: {
    ejecuciones: number;
    ok: number;
    errores: number;
    tokens_promedio: { input: number | null; output: number | null };
    tiempo_promedio_ms: number | null;
    errores_por_agente: { agente: string | null; ejecuciones: number; errores: number }[];
    errores_por_modelo: { modelo: string | null; ejecuciones: number; errores: number }[];
  };
  depositos: { total: number; completados: number; fallidos: number; pendientes: number };
  tendencia_7d: { fecha: string; documentos: number }[];
  usuarios: number;
  repositorios: number;
};

type AgentOut = { id: string; name: string; code: string; active: boolean };
type RepositoryOut = { id: string; name: string; code: string; active: boolean };
type SchemaOut = { id: string; name: string; code: string; active: boolean; field_count: number };
type AuditOut = {
  id: string;
  user_id: string | null;
  username: string | null;
  action: string;
  entity_type: string | null;
  entity_id: string | null;
  old_value: Record<string, unknown> | null;
  new_value: Record<string, unknown> | null;
  ip_address: string | null;
  user_agent: string | null;
  created_at: string;
};
type AuditCollectionOut = { items: AuditOut[]; total: number; limit: number; offset: number };

type LoadingState = {
  dashboard: boolean;
  agents: boolean;
  repos: boolean;
  schemas: boolean;
  audit: boolean;
};

const MODULES = [
  {
    href: "/admin/metadata",
    title: "Metadatos",
    icon: Database,
    description: "Administrá esquemas, campos, vocabularios y tipos documentales.",
    cta: "Ver metadatos",
    tone: "indigo",
  },
  {
    href: "/admin/dashboard",
    title: "Dashboard",
    icon: Gauge,
    description: "Visualizá estadísticas, procesamiento y rendimiento del sistema.",
    cta: "Ver dashboard",
    tone: "slate",
  },
  {
    href: "/admin/ai",
    title: "Agentes IA",
    icon: Bot,
    description: "Configurá agentes de extracción, modelos y prompts versionados.",
    cta: "Ver agentes",
    tone: "sky",
  },
  {
    href: "/admin/repositories",
    title: "Repositorios",
    icon: Server,
    description: "Conectá y sincronizá repositorios DSpace y otras fuentes documentales.",
    cta: "Ver repositorios",
    tone: "emerald",
  },
  {
    href: "/admin/audit",
    title: "Auditoría",
    icon: ShieldCheck,
    description: "Consultá todas las operaciones realizadas en el sistema.",
    cta: "Ver auditoría",
    tone: "rose",
  },
  {
    href: "/admin/config",
    title: "Configuración",
    icon: Settings2,
    description: "Administrá preferencias, permisos, integraciones y parámetros globales.",
    cta: "Abrir configuración",
    tone: "slate",
  },
] as const;

function fmt(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return n.toLocaleString("es-AR");
}

function pct(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return `${n > 0 ? "+" : ""}${n.toFixed(1)}%`;
}

function toDate(value: string): string {
  return new Date(value).toLocaleString("es-AR", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function trendIcon(value: number): LucideIcon {
  if (value > 0) return ArrowUpRight;
  if (value < 0) return ArrowDownRight;
  return CheckCircle2;
}

function activityIcon(action: string): LucideIcon {
  const text = action.toLowerCase();
  if (text.includes("sync") || text.includes("repository")) return RefreshCw;
  if (text.includes("ai") || text.includes("extraction")) return Sparkles;
  if (text.includes("document") || text.includes("type") || text.includes("metadata")) return FileSliders;
  if (text.includes("config") || text.includes("setting")) return Settings2;
  if (text.includes("user") || text.includes("role")) return Users;
  if (text.includes("error") || text.includes("failed")) return AlertTriangle;
  return Clock3;
}

function describeAction(action: string, entityType: string | null): string {
  const text = action.toLowerCase();
  if (text.includes("document") && text.includes("type") && (text.includes("create") || text.includes("add"))) {
    return "Usuario creó un nuevo tipo documental.";
  }
  if (text.includes("extraction") && (text.includes("complete") || text.includes("finish") || text.includes("ok"))) {
    return "Agente IA finalizó una extracción.";
  }
  if (text.includes("repository") && text.includes("sync")) {
    return "Repositorio DSpace sincronizado.";
  }
  if (text.includes("config") || text.includes("setting")) {
    return "Se actualizó la configuración del sistema.";
  }
  if (text.includes("deposit") && (text.includes("complete") || text.includes("success"))) {
    return "Depósito completado correctamente.";
  }
  if (text.includes("error") || text.includes("failed")) {
    return "Se registró un error en el sistema.";
  }
  if (entityType) {
    return `${action} en ${entityType}`;
  }
  return action.replaceAll(".", " ");
}

function SkeletonCard() {
  return <div className="h-32 animate-pulse rounded-2xl border border-slate-200 bg-white shadow-sm" />;
}

function MetricCard({
  label,
  value,
  delta,
  helper,
  icon: Icon,
  tone,
}: {
  label: string;
  value: string;
  delta: string;
  helper: string;
  icon: LucideIcon;
  tone: "indigo" | "sky" | "emerald" | "rose" | "slate";
}) {
  const toneClasses = {
    indigo: "bg-indigo-50 text-indigo-600",
    sky: "bg-sky-50 text-sky-600",
    emerald: "bg-emerald-50 text-emerald-600",
    rose: "bg-rose-50 text-rose-600",
    slate: "bg-slate-100 text-slate-600",
  }[tone];
  const Trend = trendIcon(delta.startsWith("-") ? -1 : delta.startsWith("+") ? 1 : 0);
  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-4 shadow-[0_14px_30px_-24px_rgba(15,23,42,0.32)] transition-all duration-200 hover:-translate-y-0.5 hover:shadow-[0_18px_36px_-24px_rgba(15,23,42,0.4)]">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-slate-500">{label}</p>
          <div className="mt-3 flex items-end gap-3">
            <p className="text-3xl font-semibold tracking-tight text-slate-950">{value}</p>
            <span className={cn("inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium", toneClasses)}>
              <Trend className="size-3.5" />
              {delta}
            </span>
          </div>
        </div>
        <div className={cn("flex size-11 items-center justify-center rounded-2xl", toneClasses)}>
          <Icon className="size-5" />
        </div>
      </div>
      <p className="mt-3 text-sm text-slate-500">{helper}</p>
    </article>
  );
}

function ModuleCard({
  href,
  title,
  icon: Icon,
  description,
  cta,
  indicator,
  tone,
}: {
  href: string;
  title: string;
  icon: LucideIcon;
  description: string;
  cta: string;
  indicator?: string;
  tone: "indigo" | "sky" | "emerald" | "rose" | "slate";
}) {
  const toneClasses = {
    indigo: "bg-indigo-50 text-indigo-600 ring-indigo-100",
    sky: "bg-sky-50 text-sky-600 ring-sky-100",
    emerald: "bg-emerald-50 text-emerald-600 ring-emerald-100",
    rose: "bg-rose-50 text-rose-600 ring-rose-100",
    slate: "bg-slate-100 text-slate-600 ring-slate-200",
  }[tone];

  return (
    <Link
      href={href}
      className="group block h-full rounded-[1.25rem] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-300 focus-visible:ring-offset-2 focus-visible:ring-offset-[#F8FAFC]"
    >
      <article className="flex h-full flex-col rounded-[1.25rem] border border-slate-200 bg-white p-5 shadow-[0_14px_30px_-24px_rgba(15,23,42,0.32)] transition-all duration-200 hover:-translate-y-0.5 hover:border-slate-300 hover:shadow-[0_22px_44px_-28px_rgba(15,23,42,0.42)]">
        <div className="flex items-start justify-between gap-4">
          <div className={cn("flex size-12 items-center justify-center rounded-2xl ring-1", toneClasses)}>
            <Icon className="size-5" />
          </div>
          <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-medium text-slate-600 transition-colors group-hover:bg-slate-200">
            {indicator ?? "Acceso directo"}
          </span>
        </div>
        <div className="mt-4 space-y-2">
          <h2 className="text-lg font-semibold tracking-tight text-slate-950">{title}</h2>
          <p className="text-sm leading-6 text-slate-500">{description}</p>
        </div>
        <div className="mt-6 flex items-center gap-2 text-sm font-medium text-[#4F46E5]">
          <span>{cta}</span>
          <ArrowUpRight className="size-4 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
        </div>
      </article>
    </Link>
  );
}

function ActivityItem({ item }: { item: AuditOut }) {
  const Icon = activityIcon(item.action);
  return (
    <li className="flex gap-3 rounded-2xl border border-slate-200 bg-slate-50/80 p-4 transition-colors hover:bg-slate-50">
      <div className="mt-0.5 flex size-10 shrink-0 items-center justify-center rounded-2xl bg-white text-[#4F46E5] ring-1 ring-slate-200">
        <Icon className="size-4" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <p className="font-medium text-slate-950">{describeAction(item.action, item.entity_type)}</p>
          <span className="rounded-full bg-indigo-50 px-2 py-1 text-[11px] font-medium text-indigo-600">{item.action}</span>
        </div>
        <p className="mt-1 text-sm text-slate-500">
          {item.username ?? "Sistema"} · {toDate(item.created_at)}
        </p>
      </div>
    </li>
  );
}

export default function AdminHome() {
  const [dashboard, setDashboard] = useState<DashboardOut | null>(null);
  const [agents, setAgents] = useState<AgentOut[]>([]);
  const [repos, setRepos] = useState<RepositoryOut[]>([]);
  const [schemas, setSchemas] = useState<SchemaOut[]>([]);
  const [audit, setAudit] = useState<AuditCollectionOut | null>(null);
  const [loading, setLoading] = useState<LoadingState>({
    dashboard: true,
    agents: true,
    repos: true,
    schemas: true,
    audit: true,
  });
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setError(null);
    setLoading({ dashboard: true, agents: true, repos: true, schemas: true, audit: true });
    try {
      const since = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();
      const [dash, agentList, repoList, schemaList, auditList] = await Promise.all([
        apiFetch<DashboardOut>("/api/admin/dashboard"),
        apiFetch<AgentOut[]>("/api/admin/ai/agents"),
        apiFetch<RepositoryOut[]>("/api/admin/repositories"),
        apiFetch<SchemaOut[]>("/api/admin/metadata/schemas"),
        apiFetch<AuditCollectionOut>(`/api/admin/audit?limit=8&from_date=${encodeURIComponent(since)}`),
      ]);
      setDashboard(dash);
      setAgents(agentList);
      setRepos(repoList);
      setSchemas(schemaList);
      setAudit(auditList);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al cargar la administración");
    } finally {
      setLoading({ dashboard: false, agents: false, repos: false, schemas: false, audit: false });
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const activeSchemas = useMemo(() => schemas.filter((schema) => schema.active), [schemas]);
  const activeAgents = useMemo(() => agents.filter((agent) => agent.active), [agents]);
  const activeRepos = useMemo(() => repos.filter((repo) => repo.active), [repos]);
  const recentErrors = useMemo(() => {
    const logs = audit?.items ?? [];
    return logs.filter((item) => /error|failed|reject/i.test(item.action)).length;
  }, [audit]);
  const latestActivity = audit?.items ?? [];
  const lastTrend = dashboard?.tendencia_7d ?? [];

  const docsTrend = useMemo(() => {
    if (lastTrend.length < 2) return 0;
    const last = lastTrend[lastTrend.length - 1]?.documentos ?? 0;
    const prev = lastTrend[lastTrend.length - 2]?.documentos ?? 0;
    if (!prev) return last ? 100 : 0;
    return ((last - prev) / prev) * 100;
  }, [lastTrend]);

  const activeAgentsShare = agents.length ? (activeAgents.length / agents.length) * 100 : 0;
  const activeReposShare = repos.length ? (activeRepos.length / repos.length) * 100 : 0;
  const recentErrorsShare = latestActivity.length ? (recentErrors / latestActivity.length) * 100 : 0;

  return (
    <div className="space-y-6">
      <section className="rounded-[1.75rem] border border-slate-200 bg-white p-6 shadow-[0_20px_50px_-34px_rgba(15,23,42,0.36)]">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-2xl space-y-3">
            <span className="inline-flex items-center gap-2 rounded-full border border-indigo-100 bg-indigo-50 px-3 py-1 text-[11px] font-medium uppercase tracking-[0.22em] text-[#4F46E5]">
              <Gauge className="size-3.5" />
              Administración
            </span>
            <div className="space-y-2">
              <h1 className="text-3xl font-semibold tracking-tight text-slate-950 sm:text-4xl">Administración</h1>
              <p className="max-w-xl text-sm leading-6 text-slate-500">
                Gestioná metadatos, agentes, repositorios y configuraciones del sistema.
              </p>
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 xl:min-w-[400px] xl:grid-cols-2">
            <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
              <p className="text-[11px] uppercase tracking-[0.22em] text-slate-500">Base activa</p>
              <p className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">{fmt(dashboard?.documentos.total ?? 0)}</p>
              <p className="mt-1 text-sm text-slate-500">Documentos en el sistema</p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
              <p className="text-[11px] uppercase tracking-[0.22em] text-slate-500">Estado actual</p>
              <p className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">{fmt(dashboard?.depositos.completados ?? 0)}</p>
              <p className="mt-1 text-sm text-slate-500">Depósitos completados</p>
            </div>
          </div>
        </div>
      </section>

      {error && (
        <div className="flex items-center justify-between gap-4 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          <p>{error}</p>
          <Button variant="outline" size="sm" onClick={() => void load()} className="border-rose-200 bg-white text-rose-700 hover:bg-rose-50">
            Reintentar
          </Button>
        </div>
      )}

      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {loading.dashboard || loading.agents || loading.repos || loading.schemas || loading.audit ? (
          <>
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
          </>
        ) : (
          <>
            <MetricCard
              label="Documentos procesados"
              value={fmt(dashboard?.documentos.procesados ?? 0)}
              delta={pct(docsTrend)}
              helper="Variación frente al día anterior en la tendencia de 7 días."
              icon={FileSliders}
              tone="indigo"
            />
            <MetricCard
              label="Agentes IA activos"
              value={fmt(activeAgents.length)}
              delta={pct(activeAgentsShare)}
              helper={`${fmt(activeAgents.length)} activos de ${fmt(agents.length)} agentes registrados.`}
              icon={Bot}
              tone="sky"
            />
            <MetricCard
              label="Repositorios conectados"
              value={fmt(activeRepos.length)}
              delta={pct(activeReposShare)}
              helper={`${fmt(activeRepos.length)} conectados de ${fmt(repos.length)} repositorios.`}
              icon={Server}
              tone="emerald"
            />
            <MetricCard
              label="Errores recientes"
              value={fmt(recentErrors)}
              delta={recentErrors > 0 ? `-${recentErrorsShare.toFixed(1)}%` : "0.0%"}
              helper="Eventos con estado de error o fallo en las últimas 24 horas."
              icon={AlertTriangle}
              tone="rose"
            />
          </>
        )}
      </section>

      <section className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1.45fr)_minmax(340px,0.85fr)]">
        <div className="space-y-4">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {MODULES.map((module) => (
              <ModuleCard
                key={module.href}
                href={module.href}
                title={module.title}
                icon={module.icon}
                description={module.description}
                cta={module.cta}
                tone={module.tone}
                indicator={
                  module.href === "/admin/metadata"
                    ? `${fmt(activeSchemas.length)} esquemas activos`
                    : module.href === "/admin/dashboard"
                      ? "Actividad actualizada"
                      : module.href === "/admin/ai"
                        ? `${fmt(activeAgents.length)} agentes activos`
                        : module.href === "/admin/repositories"
                          ? `${fmt(activeRepos.length)} repositorios conectados`
                          : module.href === "/admin/audit"
                            ? `${fmt(recentErrors)} eventos con error`
                            : "Preferencias globales"
                }
              />
            ))}
          </div>
        </div>

        <aside className="rounded-[1.5rem] border border-slate-200 bg-white p-5 shadow-[0_14px_30px_-24px_rgba(15,23,42,0.32)]">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-500">Actividad reciente</p>
              <h2 className="mt-2 text-lg font-semibold tracking-tight text-slate-950">Movimientos del sistema</h2>
            </div>
            <div className="flex size-10 items-center justify-center rounded-2xl bg-slate-100 text-slate-600">
              <Clock3 className="size-4" />
            </div>
          </div>

          <div className="mt-4">
            {loading.audit ? (
              <div className="space-y-3">
                <SkeletonCard />
                <SkeletonCard />
                <SkeletonCard />
              </div>
            ) : latestActivity.length > 0 ? (
              <ul className="space-y-3">
                {latestActivity.map((item) => (
                  <ActivityItem key={item.id} item={item} />
                ))}
              </ul>
            ) : (
              <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-4 py-6 text-sm text-slate-500">
                Todavía no hay actividad reciente para mostrar.
              </div>
            )}
          </div>

          <div className="mt-5 rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
            <p className="font-medium text-slate-900">Estado del sistema</p>
            <p className="mt-1 leading-6">
              {dashboard?.procesamiento.errores ?? 0} errores de procesamiento, {dashboard?.ia.errores ?? 0} errores de IA y {dashboard?.depositos.fallidos ?? 0} depósitos fallidos.
            </p>
          </div>
        </aside>
      </section>
    </div>
  );
}
