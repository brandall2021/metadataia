import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export default function Home() {
  return (
    <main className="flex-1 flex flex-col items-center justify-center gap-10 p-8">
      <div className="max-w-2xl text-center space-y-4">
        <h1 className="text-4xl font-bold tracking-tight">METADATAIA</h1>
        <p className="text-lg text-muted-foreground">
          Plataforma configurable de catalogación asistida por inteligencia
          artificial. PDF → OCR → Extracción → Normalización → Validación SNRD →
          Revisión humana → DSpace 9.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 w-full max-w-4xl">
        {[
          {
            title: "Documentos",
            description: "Carga, análisis, OCR y extracción de metadatos.",
          },
          {
            title: "Revisión",
            description: "Formulario dinámico, evidencia y confianza por campo.",
          },
          {
            title: "Administración",
            description: "Proveedores IA, agentes, metadatos y repositorios.",
          },
        ].map((item) => (
          <Card key={item.title}>
            <CardHeader>
              <CardTitle>{item.title}</CardTitle>
              <CardDescription>{item.description}</CardDescription>
            </CardHeader>
            <CardContent>
              {item.title === "Administración" ? (
                <a href="/admin">
                  <Button variant="outline">Abrir</Button>
                </a>
              ) : (
                <Button variant="outline" disabled>
                  En construcción
                </Button>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      <p className="text-sm text-muted-foreground">
        Esqueleto FASE 1-2 · Backend FastAPI + PostgreSQL + Redis + MinIO +
        Celery · Frontend Next.js
      </p>
    </main>
  );
}