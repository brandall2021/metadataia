# METADATAIA

Plataforma **configurable** de catalogación asistida por inteligencia artificial: carga de PDF, OCR, extracción de metadatos con agentes de IA, normalización, validación (SNRD), revisión humana y depósito en **DSpace 9**.

Todo se administra desde el panel y se persiste en base de datos — **no se hardcodea**: proveedores y modelos de IA, agentes (prompts), esquemas y campos de metadatos, vocabularios, tipos documentales y repositorios DSpace.

- **Backend**: FastAPI (Python 3.12) + PostgreSQL + Redis + Celery + MinIO
- **Frontend**: Next.js 16 (App Router) + TypeScript + shadcn/ui
- **Especificación técnica**: [`docs/SPECIFICATION.md`](docs/SPECIFICATION.md) (18 fases, criterios de aceptación por fase)

| | |
|---|---|
| Repositorio | https://github.com/brandall2021/metadataia |
| Documentación | `docs/` (SPECIFICATION, ARCHITECTURE, y por dominio) |
| Estado | FASE 8 en curso · ✅ F1–F7 completadas |

---

## 1. Flujo del sistema

```
PDF ──> Análisis (motor PDF) ──> OCR (OCRmyPDF/Tesseract) ──> Texto por página
                                                    │
                                                    ▼
                                    Agente IA (selección automática por tipo documental)
                                                    │
                     JSON Schema + confidence + evidencia (cita página/coordenadas)
                                                    ▼
                              Normalización (vocabularios, fechas, idioma, derechos)
                                                    ▼
                              Validación SNRD (reglas, errores, warnings)
                                                    ▼
                              Revisión humana (formulario dinámico, edición, aprobación)
                                                    ▼
                              Depósito DSpace 9 (workspace → collection, metadata + bitstream)
```

---

## 2. Estado del proyecto

Plan de 18 fases (spec §41). Avance incremental con criterio de aceptación por fase.

| Fase | Descripción | Estado |
|------|-------------|--------|
| 1 | Inicialización (repo, estructura, Docker Compose, .env) | ✅ |
| 2 | Base de datos (modelos, migraciones, seeds) | ✅ |
| 3 | Autenticación (login, JWT, RBAC, usuarios, roles, permisos) | ✅ |
| 4 | Administración IA (proveedores, modelos, prueba de conexión) | ✅ |
| 5 | Agentes IA (CRUD, prompts con variables, versiones, clonar, probar) | ✅ |
| 6 | Metadatos (esquemas, campos, vocabularios, tipos documentales) | ✅ |
| 7 | PDF (upload, SHA256, análisis, almacenamiento) | ✅ |
| 8 | OCR (detección de texto, OCRmyPDF, Tesseract, extracción por página) | 🔨 En curso |
| 9 | IA (selección de agente, prompt, JSON Schema, extracción, confidence, evidencia) | ⏳ |
| 10 | Normalización (vocabularios, fechas, idioma, tipos, derechos, identificadores) | ⏳ |
| 11 | Validación (reglas, errores, warnings, SNRD) | ⏳ |
| 12 | Revisión humana (visor, formulario dinámico, edición, evidencia, aprobación) | ⏳ |
| 13 | DSpace (configuración, auth, comunidades, colecciones, workspace, submission) | ⏳ |
| 14 | Auditoría (logs, historial, extracción IA, cambios humanos, depósitos) | ⏳ |
| 15 | Dashboard (estadísticas) | ⏳ |
| 16 | Tests (unit, integration, API, OCR, AI mock, DSpace mock, e2e) | ⏳ |
| 17 | Seguridad (auditoría de auth, permisos, archivos, infra) | ⏳ |
| 18 | Producción (docs, Dockerfiles prod, deploy) | ⏳ |

---

## 3. Características implementadas

### Autenticación y permisos (FASE 3)
- Login con JWT stateless (`POST /api/auth/login`), refresh y logout.
- RBAC: roles → permisos; los endpoints validan permisos con `require_permission`.
- Usuarios: CRUD (solo admin), roles y permisos administrables por API.
- Claves de secret cifradas en reposo con **Fernet** (clave derivada de `APP_SECRET_KEY`) y expuestas solo como `****últimos4`.

### Administración de IA (FASE 4-5)
- **Proveedores** (OpenAI, OpenAI-compatible, Ollama, Anthropic) con URL base por defecto, prueba de conexión (`GET /models`), API key cifrada.
- **Modelos** por proveedor (contexto, soporte JSON/visión, temperatura/máx. tokens) y prueba de inferencia (`chat/completions` o `/v1/messages`).
- **Agentes**: CRUD, activar/desactivar, **versionado automático** (cada cambio de modelo/prompt genera una versión nueva), **clonar**, historial de versiones y **probar agente** (envía su prompt real con variables de ejemplo).
- Plantilla de prompt segura (spec §10): las variables `{{variable}}` definidas se rellenan; las desconocidas quedan intactas; el contenido del documento **nunca** entra al *system prompt*.

### Metadatos (FASE 6)
- **Esquemas** (p. ej. SNRD Dublin Core) con namespace.
- **Campos** con todos los atributos de la spec §11: elemento, qualifier, etiqueta, tipo, obligatorio*, repetible, editable, extraíble por IA, regla de validación, vocabulario, orden.
- **Vocabularios**: CRUD, valores, **sinónimos**, activar/desactivar, **importación CSV** idempotente y endpoint de normalización (minúsculas + sin acentos, incluye sinónimos).
- **Tipos documentales** (Tesis, Artículo, Resolución…) con **agente IA por defecto** y **asociación de campos** (orden, `required_override`).
- **Frontend dinámico**: el formulario de carga se construye desde la configuración; un campo nuevo aparece automáticamente sin tocar código.

### Motor de PDF (FASE 7)
- `POST /api/documents`: validación de extensión, MIME, PDF válido, tamaño máximo configurable, **SHA256**, deduplicación (409), almacenamiento del **original sin modificar** (MinIO S3 o filesystem), conteo de páginas y análisis de texto por página.
- Detección de **necesidad de OCR**: un PDF escaneado (sin texto) queda marcado `needs_ocr=true` para la FASE 8.
- Listado, detalle (páginas + análisis), **descarga del original** (verificación por SHA256) y borrado (documento + objeto de almacenamiento).

### Frontend de administración
- `/login`: autenticación.
- `/admin`: navegación con guard de sesión.
- `/admin/metadata`: lista de campos y formulario de creación dinámico.

---

## 4. Arquitectura

```
                        ┌──────────────────────────────────────────┐
  Navegador ──────>     │  frontend (Next.js 16)  :3000           │
                        └──────────────────────────────────────────┘
                                   │  REST (JSON + JWT)
                                   ▼
                        ┌──────────────────────────────────────────┐
                        │  api (FastAPI)          :8000            │
                        │  /api/auth /api/users /api/admin/*       │
                        │  /api/documents /api/review /api/dspace  │
                        └───────┬──────────────┬─────────────┬─────┘
                                │              │             │
                          PostgreSQL      Redis       MinIO (PDFs)
                          (datos)         (celery)      (almacenamiento)
                                │
                        ┌───────┴──────────────┐
                        │ worker (Celery)      │
                        │  OCR / IA / DSpace   │
                        └──────────────────────┘
```

Servicios (Docker Compose): `frontend`, `api`, `worker`, `postgres`, `redis`, `minio`.

### Entidades principales (FASE 2)
`users`, `roles`, `permissions`, `role_permissions`, `user_roles` · `ai_providers`, `ai_models`, `ai_agents`, `ai_agent_versions` · `metadata_schemas`, `metadata_fields`, `vocabularies`, `vocabulary_values`, `document_types`, `document_type_metadata_fields` · `documents`, `document_pages`, `extraction_runs`, `metadata_records`, `validation_results`, `processing_jobs` · `repositories`, `repository_collections`, `depositions`, `audit_logs`.

Diagrama y decisiones: [`ARCHITECTURE.md`](ARCHITECTURE.md).

---

## 5. Estructura del repositorio

```
.
├── backend/
│   ├── app/
│   │   ├── auth/            # login, JWT, refresh, me
│   │   ├── users/           # usuarios, roles, permisos (admin)
│   │   ├── ai/              # proveedores, modelos, agentes (admin) + propagación IA (F9)
│   │   ├── metadata/        # esquemas, campos, vocabularios, tipos documentales (admin)
│   │   ├── core/            # security (bcrypt/JWT/Fernet), dependencies (RBAC), config
│   │   ├── models/          # SQLAlchemy (migrados con Alembic)
│   │   ├── seed.py          # datos iniciales idempotentes
│   │   └── main.py          # factory de la app (monta routers /health /api)
│   ├── alembic/             # migraciones
│   └── tests/               # pytest (TestsClient)
├── frontend/
│   ├── app/                 # Next.js App Router (login, admin, admin/metadata)
│   │   ├── login/
│   │   └── admin/
│   ├── components/ui/       # shadcn/ui
│   └── lib/api.ts           # cliente REST con token
├── docs/                    # SPECIFICATION y documentación por dominio
├── scripts/                 # utilidades (patch-firewall.sh)
├── Makefile                 # atajos de desarrollo
├── docker-compose.yml
└── .env.example
```

---

## 6. Requisitos

- Docker ≥ 24 y Docker Compose v2
- ~2 GB de espacio libre para imágenes
- (Producción) Acceso a un DSpace 9 y a al menos un proveedor de IA con API key

---

## 7. Puesta en marcha (desarrollo)

```bash
cp .env.example .env          # ajustar credenciales (claves JWT/secret ≥ 32 caracteres)
make dev-up                   # construye y levanta todos los servicios
make migrate                  # aplica migraciones (alembic upgrade head)
make seed                     # carga datos iniciales (usuarios/roles/permisos)
make test                     # 80 tests del backend
```

| Servicio | URL |
|----------|-----|
| API + docs Swagger | http://localhost:8000 |
| Frontend | http://localhost:3000 |
| MinIO consola | http://localhost:9001 |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |

Estado de salud: `GET /health` → `{"status":"ok","database":"ok"}`

### Primeros pasos en el navegador

1. Ir a http://localhost:3000 → **Administración** → login con `admin / metadataia123`.
2. **Metadatos**: crear un esquema y un campo → aparece automáticamente en el listado.
3. Crear tarjetas de IA: **proveedor → modelo → agente** (endpoints en Swagger).

---

## 8. Usuarios seed

| Usuario | Password | Rol |
|---------|----------|-----|
| `admin` | `metadataia123` | ADMIN |
| `catalogador` | `metadataia123` | CATALOGADOR |
| `revisor` | `metadataia123` | REVISOR |

> Cambiar las contraseñas fuera de desarrollo.

---

## 9. API (resumen)

Docs interactivos: Swagger en `http://localhost:8000/docs`.

| Grupo | Endpoints clave |
|-------|-----------------|
| Auth | `POST /api/auth/login` · `POST /api/auth/refresh` · `POST /api/auth/logout` · `GET /api/auth/me` |
| Usuarios | `GET/POST /api/users` · `PUT/DELETE /api/users/{id}` · `GET /api/roles` · `PUT /api/roles/{id}/permissions` |
| IA (admin) | `GET/POST /api/admin/ai/providers` · `PUT/DELETE /{id}` · `POST …/{id}/test` · `GET/POST /api/admin/ai/models` · `PUT/DELETE /{id}` · `POST …/{id}/test` · `GET/POST …/agents` · `PUT/DELETE …/{id}` · `GET/POST …/{id}/versions` · `POST …/{id}/clone` · `POST …/{id}/test` |
| Metadatos (admin) | `GET/POST /api/admin/metadata/schemas` · `PUT/DELETE …/{id}` · `GET/POST /api/admin/metadata/fields` · `PUT/DELETE …/{id}` · `GET/POST /api/admin/vocabularies` · `PUT/DELETE …/{id}` · `GET/POST …/{id}/values` · `POST …/{id}/import` (CSV) · `POST …/{id}/normalize` · `GET/POST /api/admin/document-types` · `PUT/DELETE …/{id}` · `GET/PUT …/{id}/fields` |
| Sistemas | `GET /health` |

- Verbos: create `201`, delete `204`, errores `401/403/404/409/422`.
- Toda ruta `/api/admin/*` requiere JWT + permiso correspondiente (`admin.ai.*.manage`, `admin.metadata.manage`, `admin.vocabularies.manage`, `admin.document_types.manage`, …).

---

## 10. Seguridad

- Contraseñas con **bcrypt**; JWT firmado con `JWT_SECRET` (≥ 32 caracteres).
- **RBAC**: roles → permisos; los endpoints se protegen con `require_permission`.
- API keys de proveedores cifradas con **Fernet** (derivado de `APP_SECRET_KEY`) y nunca devueltas en claro.
- FKs circulares resueltas con `use_alter`; borrado en cascada a nivel BD con `passive_deletes` (evita que el ORM anule FKs NOT NULL).
- `.env` no se versiona; solo `.env.example`.

---

## 11. Variables de entorno

Ver `.env.example`. Principales:

| Variable | Descripción |
|----------|-------------|
| `APP_ENV` / `APP_SECRET_KEY` | Entorno y clave maestra (deriva la clave Fernet ≥ 32 chars) |
| `DATABASE_URL` / `REDIS_URL` | Conexiones Postgres/Redis |
| `MINIO_*` | Almacenamiento (endpoint, bucket, credenciales) |
| `JWT_SECRET`, `JWT_ALGORITHM`, `JWT_EXPIRE_MINUTES` | Tokens de acceso |
| `CORS_ORIGINS` | Orígenes permitidos |
| `OCR_LANGUAGES`, `AUTO_OCR`, `AUTO_AI` | Comportamiento del pipeline (F8-F9) |
| `AI_TIMEOUT_SECONDS`, `DSPACE_TIMEOUT_SECONDS` | Timeouts de integraciones |

---

## 12. Tests

```bash
make test                    # dentro del contenedor api (instala editable si falta)
docker compose exec api pytest tests/test_ai_agents.py -q   # un grupo
```

Estado actual: **80 tests en verde** (smoke, auth, users, ai_admin, agents, metadata). Los endpoints externos (IA, DSpace) se simulan con `httpx.MockTransport`.

---

## 13. Roadmap

- **En curso**: FASE 7 — Motor PDF (upload, SHA256, análisis, almacenamiento en MinIO).
- **Siguientes**: OCR (8) → extracción IA (9) → normalización (10) → validación SNRD (11) → revisión humana (12) → DSpace (13) → auditoría (14) → dashboard (15) → tests e2e (16) → seguridad (17) → producción (18).

---

## 14. Despliegue

- Repositorio alojado en **GitHub** (privado).
- Puesta en producción prevista con **Dokploy** (Compose de producción, volúmenes nombrados, migración en el arranque y `docker-compose.prod.yml`).
- Documentación de despliegue se completa en FASE 18 (`docs/DEPLOYMENT.md`).

---

## 15. Comandos útiles

```bash
make dev-up    # levantar todos los servicios
make build     # reconstruir imágenes
make migrate   # alembic upgrade head
make seed      # datos iniciales
make test      # tests del backend
make logs      # logs en vivo
make ps        # estado de servicios
```

Nueva migración:

```bash
docker compose run --rm api alembic revision --autogenerate -m "nombre"
```

---

## 16. Notas de este entorno (host CentOS 7 / kernel 3.10)

1. **Firewall del hosting**: las reglas anti-bogon DROPean el tráfico hacia rangos privados e impiden que el host alcance los contenedores. Aplicar una vez (persiste con `iptables-save`):

   ```bash
   ./scripts/patch-firewall.sh
   ```

2. **PostgreSQL + seccomp**: el perfil seccomp por defecto rompe Postgres en este kernel. El servicio `postgres` usa `seccomp:unconfined` (solo desarrollo).

3. **Espacio en disco**: los volúmenes/rebuilds consumen rápido `/var`. Monitorear con `df -h /var` y limpiar con `docker image prune -f`.

4. **Frontend**: compila solo dentro del contenedor (node:20-alpine); las bindings nativas de Next requieren glibc ≥ 2.27 y el host tiene 2.17.

---

## 17. Documentación

| Doc | Contenido |
|-----|-----------|
| `docs/SPECIFICATION.md` | Especificación funcional completa (14 secciones de funcionalidad + 18 fases) |
| `docs/ARCHITECTURE.md` | Arquitectura y decisiones técnicas |
| `docs/DATABASE.md` *(F2)* | Modelo de datos y relaciones |
| `docs/AI.md`, `docs/AI_AGENTS.md` *(F4-F5)* | Proveedores/modelos y agentes |
| `docs/METADATA.md` *(F6)* | Esquemas, campos, vocabularios, tipos |
| `docs/SNRD.md`, `docs/OCR.md`, `docs/DSPACE.md` *(F10-F13)* | Por dominio |
| `docs/SECURITY.md`, `docs/DEPLOYMENT.md`, `docs/TESTING.md`, `docs/TROUBLESHOOTING.md` | Completadas por fase |

---

## 18. Licencia

Uso interno / institucional. Los derechos de la especificación y del código pertenecen a la institución propietaria del proyecto.