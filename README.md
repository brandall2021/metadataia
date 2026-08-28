# METADATAIA

Sistema de extracción, normalización, validación y depósito de metadatos desde documentos PDF mediante OCR + Agentes de IA + SNRD + DSpace 9.

Plataforma **genérica y configurable**: proveedor de IA, modelo, prompt, campos de metadatos, tipos documentales, vocabularios, reglas de validación y colecciones DSpace se administran desde el panel — no se hardcodean.

Especificación técnica completa: [`docs/SPECIFICATION.md`](docs/SPECIFICATION.md).

## Estado del proyecto

Fases del plan (spec §41):

| Fase | Descripción | Estado |
|------|-------------|--------|
| 1 | Inicialización (repo, estructura, Docker Compose, .env) | ✅ |
| 2 | Base de datos (modelos, migraciones, seeds) | ✅ |
| 3 | Autenticación (login, JWT, RBAC, usuarios, roles, permisos) | ✅ |
| 4 | Administración IA (proveedores, modelos, prueba de conexión) | ✅ |
| 5 | Agentes IA (CRUD, prompts variables, versiones, clonar, probar) | ✅ |
| 6–18 | Metadatos, PDF, OCR, revisión, DSpace, auditoría, tests, seguridad, producción | Pendiente (incremental) |

## Requisitos

- Docker 24+ y Docker Compose v2
- Espacio en disco suficiente para las imágenes (≈2 GB)

## Puesta en marcha (desarrollo)

```bash
cp .env.example .env            # ajustar credenciales de desarrollo
make dev-up                      # construye y levanta todos los servicios
make migrate                     # aplica migraciones (alembic upgrade head)
make seed                        # carga usuarios/roles/permisos iniciales
make test                        # ejecuta los tests del backend
```

Servicios:

| Servicio | URL |
|----------|-----|
| API (FastAPI) + docs Swagger | http://localhost:8000 |
| Frontend (Next.js) | http://localhost:3000 |
| MinIO consola | http://localhost:9001 |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |

Estado de salud: `GET /health` → `{"status":"ok","database":"ok"}`

## Usuarios seed

| Usuario | Password | Rol |
|---------|----------|-----|
| `admin` | `metadataia123` | ADMIN |
| `catalogador` | `metadataia123` | CATALOGADOR |
| `revisor` | `metadataia123` | REVISOR |

> Cambiar las contraseñas fuera de desarrollo.

## Estructura

```
backend/          API FastAPI + worker Celery (Python 3.12)
  app/            paquetes por dominio (auth, ai, metadata, pdf, ocr, ...)
  alembic/        migraciones de base de datos
  tests/          pruebas pytest
frontend/         Next.js 16 + TypeScript + shadcn/ui
docs/             especificación y documentación
scripts/          utilidades (patch-firewall.sh)
docker-compose.yml  PostgreSQL, Redis, MinIO, API, worker, frontend
```

## Comandos útiles

```bash
make dev-down     # detener servicios
make logs         # seguir logs
make build        # reconstruir imágenes
docker compose run --rm api alembic revision --autogenerate -m "cambio"  # nueva migración
```

## Notas de este entorno (host CentOS 7 / kernel 3.10)

1. **Firewall del hosting**: las reglas anti-bogon del host DROPean el tráfico hacia/desde rangos privados, lo que impide que el host alcance los contenedores. Aplicar una vez (persiste con `iptables-save`):

   ```bash
   ./scripts/patch-firewall.sh
   ```

2. **PostgreSQL + seccomp**: el perfil seccomp por defecto de Docker rompe Postgres en este kernel (`Operation not permitted` al escribir `postmaster.pid`). El servicio `postgres` en `docker-compose.yml` usa `seccomp:unconfined` (solo entorno de desarrollo).

3. **Espacio en disco**: los volúmenes y los rebuilds de imágenes consumen rápidamente `/var`. Monitorear con `df -h /var` y limpiar con `docker image prune -f`.

## Siguiente fase

FASE 3 — Autenticación: login, JWT, usuarios, roles y permisos (criterio: solo se accede a funciones autorizadas).

Documentación de referencia (spec §46) se completa por fase: ARCHITECTURE, DATABASE, API, AI, AI_AGENTS, METADATA, SNRD, OCR, DSPACE, SECURITY, DEPLOYMENT, TESTING, TROUBLESHOOTING.