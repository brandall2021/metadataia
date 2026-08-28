"use client";

import Link from "next/link";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export default function AdminHome() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold tracking-tight">Administración</h1>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-4xl">
        <Card>
          <CardHeader>
            <CardTitle>Metadatos</CardTitle>
            <CardDescription>
              Esquemas, campos, vocabularios y tipos documentales. Los campos
              creados aparecen automáticamente en los formularios.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Link href="/admin/metadata">
              <Button variant="outline">Ir a Metadatos</Button>
            </Link>
          </CardContent>
        </Card>
        {["Agentes IA", "Repositorios"].map((title) => (
          <Card key={title}>
            <CardHeader>
              <CardTitle>{title}</CardTitle>
              <CardDescription>Disponible en próximas fases.</CardDescription>
            </CardHeader>
            <CardContent>
              <Button variant="outline" disabled>
                En construcción
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}