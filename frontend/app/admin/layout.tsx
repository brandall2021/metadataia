"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { LogOut } from "lucide-react";

import { Button } from "@/components/ui/button";
import { getToken, setToken } from "@/lib/api";

const NAV = [
  { href: "/admin", label: "Inicio" },
  { href: "/admin/dashboard", label: "Dashboard" },
  { href: "/admin/metadata", label: "Metadatos" },
  { href: "/admin/ai", label: "Agentes IA" },
  { href: "/admin/repositories", label: "Repositorios" },
  { href: "/admin/audit", label: "Auditoría" },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    setReady(true);
  }, [router]);

  if (!ready) return null;

  return (
    <div className="min-h-full bg-gradient-to-b from-background via-background to-muted/30">
      <header className="sticky top-0 z-30 border-b border-border/70 bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/70">
        <div className="mx-auto flex w-full max-w-7xl items-center justify-between gap-4 px-4 py-3 lg:px-8">
          <div className="flex items-center gap-6">
            <div>
              <p className="text-[11px] uppercase tracking-[0.28em] text-muted-foreground">
                MetadataIA
              </p>
              <span className="block text-sm font-semibold">Administración</span>
            </div>
            <nav className="flex flex-wrap items-center gap-2">
             {NAV.map((item) => (
               <Link
                 key={item.href}
                 href={item.href}
                 className={
                    pathname === item.href
                    ? "rounded-full border border-primary/20 bg-primary/10 px-3 py-1.5 text-sm font-medium text-primary"
                    : "rounded-full px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-muted/70 hover:text-foreground"
                 }
               >
                 {item.label}
               </Link>
             ))}
            </nav>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setToken(null);
              router.replace("/login");
            }}
            className="gap-2"
          >
            <LogOut className="size-4" />
            Salir
          </Button>
        </div>
      </header>
      <main className="mx-auto w-full max-w-7xl px-4 py-6 lg:px-8 lg:py-8">{children}</main>
    </div>
  );
}
