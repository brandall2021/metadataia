"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Bot, Cpu, KeyRound, type LucideIcon } from "lucide-react";

const TABS: { href: string; label: string; icon: LucideIcon; exact?: boolean }[] = [
  { href: "/admin/ai", label: "Agentes", icon: Bot, exact: true },
  { href: "/admin/ai/modelos", label: "Modelos", icon: Cpu },
  { href: "/admin/ai/proveedores", label: "Proveedores", icon: KeyRound },
];

export default function AILayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight text-slate-950">Agentes IA</h1>
          <p className="text-sm text-slate-500">
            Proveedores → modelos → agentes: cada cosa en su propia pestaña.
          </p>
        </div>
        <nav className="flex gap-1 rounded-2xl border border-slate-200 bg-white p-1 shadow-sm">
          {TABS.map((tab) => {
            const active = tab.exact ? pathname === tab.href : pathname.startsWith(tab.href);
            const Icon = tab.icon;
            return (
              <Link
                key={tab.href}
                href={tab.href}
                className={`inline-flex items-center gap-2 rounded-xl px-3 py-1.5 text-sm font-medium transition-colors ${
                  active
                    ? "bg-primary text-primary-foreground shadow-sm"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground"
                }`}
              >
                <Icon className="size-4" />
                {tab.label}
              </Link>
            );
          })}
        </nav>
      </header>
      {children}
    </div>
  );
}
