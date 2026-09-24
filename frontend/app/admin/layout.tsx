"use client";

import { useEffect, useState } from "react";

import { AdminShell } from "@/components/admin-shell";
import { getToken } from "@/lib/api";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!getToken()) {
      globalThis.location.replace("/login");
      return;
    }
    setReady(true);
  }, []);

  if (!ready) return null;

  return <AdminShell>{children}</AdminShell>;
}
