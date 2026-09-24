"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  Bell,
  BookText,
  ChevronDown,
  ClipboardList,
  Database,
  FileSliders,
  Gauge,
  Home,
  Layers3,
  LogOut,
  Menu,
  PanelLeftClose,
  Settings2,
  ShieldCheck,
  Sparkles,
  Users,
  Workflow,
  Bot,
  Search,
  Server,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { getToken, setToken } from "@/lib/api";

type NavItem = {
  href: string;
  label: string;
  icon: typeof Home;
};

type NavGroup = {
  label: string;
  items: NavItem[];
};

const NAV_GROUPS: NavGroup[] = [
  {
    label: "Principal",
    items: [
      { href: "/admin", label: "Inicio", icon: Home },
      { href: "/admin/dashboard", label: "Dashboard", icon: Gauge },
    ],
  },
  {
    label: "Gestión",
    items: [
      { href: "/admin/metadata", label: "Metadatos", icon: Database },
      { href: "/admin/vocabularies", label: "Vocabularios", icon: BookText },
      { href: "/admin/document-types", label: "Tipos documentales", icon: Layers3 },
      { href: "/admin/repositories", label: "Repositorios", icon: Server },
    ],
  },
  {
    label: "Automatización",
    items: [{ href: "/admin/ai", label: "Agentes IA", icon: Bot }],
  },
  {
    label: "Administración",
    items: [
      { href: "/admin/users", label: "Usuarios", icon: Users },
      { href: "/admin/config", label: "Configuración", icon: Settings2 },
      { href: "/admin/audit", label: "Auditoría", icon: ShieldCheck },
    ],
  },
];

const QUICK_ACTIONS = [
  { href: "/admin/metadata", label: "Crear metadato", icon: FileSliders },
  { href: "/admin/ai", label: "Crear agente IA", icon: Sparkles },
  { href: "/admin/repositories", label: "Agregar repositorio", icon: Workflow },
  { href: "/admin/audit", label: "Ver auditoría", icon: ClipboardList },
];

function isActive(pathname: string, href: string): boolean {
  return href === "/admin" ? pathname === href : pathname.startsWith(href);
}

function prettyBreadcrumb(pathname: string): string[] {
  const item = NAV_GROUPS.flatMap((group) => group.items).find((nav) => isActive(pathname, nav.href));
  if (!item) return ["Inicio", "Administración"];
  if (item.href === "/admin") return ["Inicio", "Administración"];
  return ["Inicio", "Administración", item.label];
}

export function AdminShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [actionsOpen, setActionsOpen] = useState(false);
  const [userOpen, setUserOpen] = useState(false);
  const actionsRef = useRef<HTMLDivElement | null>(null);
  const userRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const onPointerDown = (event: MouseEvent) => {
      const target = event.target as Node;
      if (actionsRef.current && !actionsRef.current.contains(target)) setActionsOpen(false);
      if (userRef.current && !userRef.current.contains(target)) setUserOpen(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setMobileOpen(false);
        setActionsOpen(false);
        setUserOpen(false);
      }
    };

    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, []);

  useEffect(() => {
    setMobileOpen(false);
    setActionsOpen(false);
    setUserOpen(false);
  }, [pathname]);

  const breadcrumb = useMemo(() => prettyBreadcrumb(pathname), [pathname]);

  function signOut() {
    setToken(null);
    router.replace("/login");
  }

  return (
    <div className="min-h-dvh bg-[#F8FAFC] text-slate-900">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[100] focus:rounded-full focus:bg-white focus:px-4 focus:py-2 focus:text-sm focus:shadow-lg"
      >
        Ir al contenido
      </a>

      <aside className="hidden lg:fixed lg:inset-y-0 lg:left-0 lg:z-40 lg:flex lg:w-60 lg:flex-col lg:border-r lg:border-slate-800/60 lg:bg-[#0F172A] lg:text-slate-100">
        <div className="flex h-full flex-col px-4 py-5">
          <div className="rounded-2xl border border-white/10 bg-white/5 p-4 shadow-[0_20px_40px_-28px_rgba(15,23,42,0.7)]">
            <p className="text-[10px] font-semibold uppercase tracking-[0.32em] text-slate-400">METADATAIA</p>
            <div className="mt-1 flex items-center justify-between gap-3">
              <span className="text-lg font-semibold tracking-tight text-white">Administración</span>
              <span className="rounded-full bg-indigo-500/15 px-2 py-1 text-[11px] font-medium text-indigo-200">SaaS</span>
            </div>
          </div>

          <nav className="mt-6 flex-1 space-y-5 overflow-y-auto pr-1 text-sm">
            {NAV_GROUPS.map((group) => (
              <div key={group.label} className="space-y-2">
                <p className="px-2 text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">{group.label}</p>
                <div className="space-y-1">
                  {group.items.map((item) => {
                    const active = isActive(pathname, item.href);
                    const Icon = item.icon;
                    return (
                      <Link
                        key={item.href}
                        href={item.href}
                        aria-current={active ? "page" : undefined}
                        className={cn(
                          "group relative flex items-center gap-3 rounded-2xl px-3 py-2.5 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400/60",
                          active
                            ? "bg-[#4F46E5] text-white shadow-[0_18px_35px_-24px_rgba(79,70,229,0.85)]"
                            : "text-slate-300 hover:bg-white/10 hover:text-white",
                        )}
                      >
                        {active && <span className="absolute left-0 top-2 bottom-2 w-1 rounded-r-full bg-sky-400" />}
                        <Icon className="size-4 shrink-0" />
                        <span className="font-medium">{item.label}</span>
                      </Link>
                    );
                  })}
                </div>
              </div>
            ))}
          </nav>

          <div className="mt-4 rounded-2xl border border-white/10 bg-white/5 p-3 text-xs text-slate-400">
            <p className="font-medium text-slate-200">Accesos</p>
            <p className="mt-1 leading-5">Atajos para gestión, monitoreo y mantenimiento del sistema.</p>
          </div>
        </div>
      </aside>

      {mobileOpen && (
        <div className="fixed inset-0 z-40 bg-slate-950/40 backdrop-blur-[1px] lg:hidden" onClick={() => setMobileOpen(false)} />
      )}

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-80 max-w-[90vw] flex-col border-r border-slate-800/20 bg-[#0F172A] text-slate-100 shadow-2xl transition-transform duration-300 lg:hidden",
          mobileOpen ? "translate-x-0" : "-translate-x-full",
        )}
        aria-hidden={!mobileOpen}
      >
        <div className="flex items-center justify-between border-b border-white/10 px-4 py-4">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.32em] text-slate-400">METADATAIA</p>
            <p className="text-base font-semibold text-white">Administración</p>
          </div>
          <Button variant="outline" size="icon-sm" onClick={() => setMobileOpen(false)} className="border-white/10 bg-white/5 text-white hover:bg-white/10">
            <PanelLeftClose className="size-4" />
          </Button>
        </div>
        <nav className="flex-1 space-y-5 overflow-y-auto p-4 text-sm">
          {NAV_GROUPS.map((group) => (
            <div key={group.label} className="space-y-2">
              <p className="px-2 text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">{group.label}</p>
              <div className="space-y-1">
                {group.items.map((item) => {
                  const active = isActive(pathname, item.href);
                  const Icon = item.icon;
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      onClick={() => setMobileOpen(false)}
                      className={cn(
                        "relative flex items-center gap-3 rounded-2xl px-3 py-2.5 text-sm transition-colors",
                        active ? "bg-[#4F46E5] text-white" : "text-slate-300 hover:bg-white/10 hover:text-white",
                      )}
                    >
                      {active && <span className="absolute left-0 top-2 bottom-2 w-1 rounded-r-full bg-sky-400" />}
                      <Icon className="size-4 shrink-0" />
                      <span className="font-medium">{item.label}</span>
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>
      </aside>

      <div className="min-h-dvh lg:pl-60">
        <header className="sticky top-0 z-30 border-b border-slate-200/80 bg-white/90 backdrop-blur">
          <div className="mx-auto flex w-full max-w-[1600px] items-center gap-3 px-4 py-3 sm:px-6 lg:px-8">
            <Button
              variant="outline"
              size="icon-sm"
              className="lg:hidden"
              onClick={() => setMobileOpen(true)}
              aria-label="Abrir navegación"
            >
              <Menu className="size-4" />
            </Button>

            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2 text-sm text-slate-500">
                {breadcrumb.map((item, index) => (
                  <span key={`${item}-${index}`} className="flex items-center gap-2">
                    {index > 0 && <span className="text-slate-300">/</span>}
                    <span className={cn(index === breadcrumb.length - 1 ? "text-slate-900" : "text-slate-500")}>{item}</span>
                  </span>
                ))}
              </div>
            </div>

            <label className="hidden min-w-0 max-w-md flex-1 items-center gap-2 rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-500 shadow-sm focus-within:border-indigo-300 focus-within:ring-2 focus-within:ring-indigo-200 md:flex">
              <Search className="size-4 shrink-0 text-slate-400" />
              <input
                type="search"
                placeholder="Buscar en MetadataIA..."
                className="w-full bg-transparent outline-none placeholder:text-slate-400"
              />
            </label>

            <div className="flex items-center gap-2">
              <div ref={actionsRef} className="relative">
                <Button variant="default" size="sm" onClick={() => setActionsOpen((value) => !value)} className="gap-2 rounded-full px-4">
                  <span>+ Nueva acción</span>
                  <ChevronDown className="size-4" />
                </Button>
                {actionsOpen && (
                  <div className="absolute right-0 top-full z-40 mt-2 w-64 overflow-hidden rounded-2xl border border-slate-200 bg-white p-2 shadow-xl">
                    {QUICK_ACTIONS.map((item) => {
                      const Icon = item.icon;
                      return (
                        <Link
                          key={item.href}
                          href={item.href}
                          className="flex items-start gap-3 rounded-xl px-3 py-2.5 text-sm text-slate-700 transition-colors hover:bg-slate-50 hover:text-slate-950"
                        >
                          <Icon className="mt-0.5 size-4 text-indigo-600" />
                          <span>{item.label}</span>
                        </Link>
                      );
                    })}
                  </div>
                )}
              </div>

              <Button variant="outline" size="icon-sm" className="hidden sm:inline-flex">
                <Bell className="size-4" />
              </Button>

              <div ref={userRef} className="relative">
                <Button variant="outline" size="sm" onClick={() => setUserOpen((value) => !value)} className="gap-2 rounded-full px-3">
                  <span className="flex size-7 items-center justify-center rounded-full bg-slate-900 text-xs font-semibold text-white">MD</span>
                  <span className="hidden sm:inline">Administrador</span>
                  <ChevronDown className="size-4" />
                </Button>
                {userOpen && (
                  <div className="absolute right-0 top-full z-40 mt-2 w-56 overflow-hidden rounded-2xl border border-slate-200 bg-white p-2 shadow-xl">
                    <div className="px-3 py-2 text-xs text-slate-500">
                      Sesión activa
                      <div className="mt-1 text-sm font-medium text-slate-900">Administrador</div>
                    </div>
                    <button
                      type="button"
                      onClick={signOut}
                      className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-slate-700 transition-colors hover:bg-slate-50 hover:text-slate-950"
                    >
                      <LogOut className="size-4 text-slate-500" />
                      Cerrar sesión
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        </header>

        <main id="main-content" className="mx-auto w-full max-w-[1600px] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          {children}
        </main>
      </div>
    </div>
  );
}
