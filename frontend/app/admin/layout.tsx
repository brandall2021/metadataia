"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { getToken, setToken } from "@/lib/api";

const NAV = [
  { href: "/admin", label: "Inicio" },
  { href: "/admin/dashboard", label: "Dashboard" },
  { href: "/admin/metadata", label: "Metadatos" },
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
    <div className="flex min-h-full flex-col">
      <header className="flex items-center justify-between border-b px-6 py-3">
        <div className="flex items-center gap-6">
          <span className="font-semibold">METADATAIA · Administración</span>
          <nav className="flex items-center gap-2">
            {NAV.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={
                  pathname === item.href
                    ? "text-sm font-medium text-primary"
                    : "text-sm text-muted-foreground hover:text-foreground"
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
        >
          Salir
        </Button>
      </header>
      <main className="flex-1 p-6">{children}</main>
    </div>
  );
}