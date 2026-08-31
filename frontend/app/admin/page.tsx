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
        <Card>
          <CardHeader>
            <CardTitle>Auditoría</CardTitle>
            <CardDescription>
              Registro de todas las operaciones: logins, subidas, extracción IA,
              cambios humanos, aprobaciones y depósitos.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Link href="/admin/audit">
              <Button variant="outline">Ir a Auditoría</Button>
            </Link>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Dashboard</CardTitle>
            <CardDescription>
              Estadísticas del sistema: documentos por estado, procesamiento IA,
              errores por agente y modelo, depósitos y tendencia diaria.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Link href="/admin/dashboard">
              <Button variant="outline">Ver Dashboard</Button>
            </Link>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Agentes IA</CardTitle>
            <CardDescription>
              Agentes de extracción de metadatos, cada uno ligado a un modelo y
              un tipo documental con prompts y versionado.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Link href="/admin/ai">
              <Button variant="outline">Ir a Agentes IA</Button>
            </Link>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Repositorios</CardTitle>
            <CardDescription>
              Repositorios DSpace: URL, autenticación, sincronización de
              comunidades/colecciones y asociación de tipos documentales.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Link href="/admin/repositories">
              <Button variant="outline">Ir a Repositorios</Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}