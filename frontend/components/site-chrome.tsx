"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useMemo, type ReactNode } from "react";
import { BookText, LayoutDashboard, Layers3, ListChecks, Settings2, Sparkles, Home, FileText } from "lucide-react";

import { cn } from "@/lib/utils";

type NavItem = { href: string; label: string; icon: typeof Home };

const DEFAULT_NAV: NavItem[] = [
  { href: "/", label: "Inicio", icon: Home },
  { href: "/documents", label: "Documentos", icon: FileText },
  { href: "/review", label: "Revisión", icon: ListChecks },
  { href: "/admin", label: "Administración", icon: LayoutDashboard },
];

const ADMIN_NAV: NavItem[] = [
  { href: "/admin", label: "Inicio", icon: Home },
  { href: "/admin/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/admin/metadata", label: "Metadatos", icon: BookText },
  { href: "/admin/document-types", label: "Tipos", icon: Layers3 },
  { href: "/admin/ai", label: "IA", icon: Sparkles },
  { href: "/admin/config", label: "Config", icon: Settings2 },
];

function isActive(pathname: string, href: string): boolean {
  return href === "/" ? pathname === href : pathname.startsWith(href);
}

export function SiteChrome({ children }: { children: ReactNode }) {
  const pathname = usePathname();

  const nav = useMemo(() => {
    if (pathname.startsWith("/admin")) return ADMIN_NAV;
    return DEFAULT_NAV;
  }, [pathname]);

  if (pathname.startsWith("/login")) return <>{children}</>;

  return (
    <div className="min-h-dvh bg-[radial-gradient(circle_at_top,_rgba(79,70,229,0.12),_transparent_32%),linear-gradient(180deg,#f8fafc_0%,#f5f7ff_48%,#eef2ff_100%)] text-slate-900">
      <div className="sticky top-0 z-40 border-b border-slate-200/80 bg-white/80 backdrop-blur-xl">
        <div className="mx-auto flex w-full max-w-[1600px] items-center gap-4 px-4 py-3 sm:px-6 lg:px-8">
          <div className="flex items-center gap-3 rounded-full border border-indigo-200/80 bg-indigo-50/70 px-3 py-1.5 shadow-sm">
            <span className="flex size-7 items-center justify-center rounded-full bg-[#4F46E5] text-xs font-semibold text-white">M</span>
            <div className="min-w-0">
              <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-indigo-500">MetadataIA</p>
              <p className="text-sm font-medium text-slate-900">Centro de trabajo</p>
            </div>
          </div>

          <nav className="flex flex-1 items-center gap-2 overflow-x-auto">
            {nav.map((item) => {
              const Icon = item.icon;
              const active = isActive(pathname, item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "inline-flex items-center gap-2 rounded-full border px-3 py-2 text-sm font-medium transition-all",
                    active
                      ? "border-indigo-200 bg-indigo-600 text-white shadow-[0_18px_36px_-24px_rgba(79,70,229,0.7)]"
                      : "border-slate-200 bg-white text-slate-600 hover:border-indigo-200 hover:bg-indigo-50 hover:text-indigo-700",
                  )}
                >
                  <Icon className="size-4" />
                  {item.label}
                </Link>
              );
            })}
          </nav>

          <div className="hidden items-center gap-2 lg:flex">
            <span className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700">Activo</span>
          </div>
        </div>
      </div>

      {children}
    </div>
  );
}
