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
| Estado | ✅ F1–F18 completadas (incluye despliegue producción + guía Dokploy) |

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
| 8 | OCR (detección de texto, OCRmyPDF, Tesseract, extracción por página) | ✅ |
| 9 | Extracción de metadatos con IA (extracción de campos, OCR + IA) | ✅ |
| 9 | IA (selección de agente, prompt, JSON Schema, extracción, confidence, evidencia) | ⏳ |
| 10 | Normalización (vocabularios, fechas, idioma, tipos, derechos, identificadores) | ✅ |
| 11 | Validación (reglas, errores, warnings, SNRD) | ✅ |
| 12 | Revisión humana (visor, formulario dinámico, edición, evidencia, aprobación) | ✅ |
| 13 | DSpace (configuración, auth, comunidades, colecciones, workspace, submission) | ✅ |
| 14 | Auditoría (logs, historial, extracción IA, cambios humanos, depósitos) | ✅ |
| 15 | Dashboard (estadísticas) | ✅ |
| 16 | Tests (unit, integration, API, OCR, AI mock, DSpace mock, e2e) | ✅ |
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

### OCR de documentos escaneados (FASE 8)
- Pipeline Celery: `run_ocr` ejecuta **OCRmyPDF + Tesseract** (`spa+eng+por` configurable) sobre el original sin modificarlo y genera un **PDF buscable** (`ocr/{sha256}.pdf` en MinIO/S3).
- **Auto-encolado**: `AUTO_OCR=true` encola OCR automáticamente al subir un PDF detectado como escaneado; también se puede solicitar bajo demanda con `POST /api/documents/{id}/ocr`.
- **Registro completo** por job (`ProcessingJob`): herramienta, versión, idiomas, tiempo de ejecución, páginas procesadas y errores (`metadata_json`), con estados `PENDING → RUNNING → COMPLETED|ERROR`.
- Extracción del texto **página por página** del PDF buscable, actualizando `document_pages.text`, `text_length` y `ocr_used`; el documento pasa a estado `OCR_COMPLETED`.
- Detalle del documento incluye el histórico de jobs (`/api/documents/{id}`).

### Extracción de metadatos con IA (FASE 9)
- **Selección automática de agente**: agente por defecto del tipo documental → agente específico del tipo → agente genérico activo (`AIAgent.active` + `current_version`).
- **Pipeline Celery**: `extract_metadata` construye el prompt (system + instrucciones con variables de contexto) a partir del texto por página, llama al modelo (**OpenAI-compatible** o **Anthropic**, `response_format` JSON si el modelo lo soporta), **valida la salida contra el JSON Schema** del agente y mapea cada campo a `MetadataRecord` con `value`, `confidence` y **evidencia** (`source_page`, `source_text`).
- Nuevos endpoints: `POST /api/documents/{id}/extract` (202, encola) y `GET /api/documents/{id}/metadata` (runs + registros); `ExtractionRun` guarda tokens, tiempos, hash del prompt y la **respuesta cruda** (`raw/{run_id}.json` en MinIO) para auditoría.
- **Auto-encolado**: `AUTO_AI=true` encola extracción automáticamente al subir un documento con texto (`POST /api/documents` acepta `document_type_id` como form) o tras el OCR.
- La tarea **adopta el job `PENDING`** creado por el encolador (un único job por extracción).

### Normalización de metadatos (FASE 10)
- **Reglas deterministas, independientes del LLM**: los valores extraídos por IA se convierten al formato configurado con `MetadataNormalizer` (`backend/app/normalization/engine.py`): vocabularios con sinónimos (p. ej. `Spanish`/`Castellano` → `spa`), fechas a ISO (`10/05/2023` → `2023-05-10`, `10 de mayo de 2023`, `May 10, 2023`, `2023-05`, `2023`), DOI (`10.xxxx/yyyy`), ORCID (`0000-0000-0000-0000`), nombres (`APELLIDO, Nombre`), espacios y mayúsculas.
- **Configuración por campo**: `normalization_type` en `MetadataField` (columna nueva con migración) o inferido del `data_type`/elemento (`date`, `identifier`, `creator`, `language`...); un `vocabulary_id` hace que el valor se mapee a `code` canónico.
- **Pipeline**: `POST /api/documents/{id}/normalize` (202, encola job `NORMALIZATION`); la tarea **adopta el job `PENDING`**, deja intacto todo valor no convertible (`normalized=False`) y marca el documento como `NORMALIZED`.
- **Auto-normalización**: `AUTO_NORMALIZE=true` (por defecto) encadena `normalize_metadata` al final de `extract_metadata`, por lo que subir + cargar genera `UPLOADED → … → METADATA_EXTRACTED → NORMALIZED`.

### Validación de metadatos (FASE 11)
- **Motor determinista** (`backend/app/validation/engine.py`): reglas por campo según `MetadataField` — obligatorios (incluye campos obligatorios del tipo documental **sin registro extraído**), formatos (`email`, `url`, `date`/ISO, `integer`, `float`, `doi`, `orcid`, `isbn`, `issn`, `identifier`, `regex:patrón`), longitudes (`min_length:N`, `max_length:N`) y vocabularios; genera **errores** (registros inválidos) y **warnings** (p. ej. confianza baja < 0.6).
- **Validador SNRD** (`backend/app/snrd/validator.py`), módulo aparte de DSpace: verifica el perfil de interoperabilidad (elementos obligatorios `title`/`date`, fechas ISO, idioma recomendado).
- **Pipeline**: `POST /api/documents/{id}/validate` (202, encola job `VALIDATION`); la tarea adopta el job `PENDING`, registra un `ValidationResult` por validador (`METADATA`, `SNRD`) con `errors_json`/`warnings_json` y deja el documento en `VALIDATED` (sin errores) o `VALIDATION_FAILED`. `GET /api/documents/{id}/validation` muestra los resultados.
- **Auto-validación**: `AUTO_VALIDATE=true` (por defecto) encadena `validate_metadata` tras normalizar; flujo completo `UPLOADED → … → NORMALIZED → VALIDATED`.

### Revisión humana (FASE 12)
- **Edición de metadatos** (`backend/app/review/router.py`): `PUT /api/documents/{id}/records/{record_id}` corrige un valor (marca `manually_modified=True`, invalida la validación y pone el documento en `NEEDS_REVIEW`); `POST /api/documents/{id}/records` crea un registro faltante (fuente `MANUAL`, validando que el campo pertenezca al tipo documental y no tenga valor); `DELETE /api/documents/{id}/records/{record_id}` elimina registros erróneos. El visor usa `GET /api/documents/{id}/download` + records con evidencia (`confidence`, `source_page`, `source_text`).
- **Aprobación y rechazo**: `POST /api/documents/{id}/approve` **revalida** primero y solo aprueba si no hay errores (`VALIDATION_FAILED` bloquea la aprobación); `POST /api/documents/{id}/reject` marca `REJECTED`. Un documento `APPROVED` no se puede editar ni rechazar.
- **Permisos RBAC**: editar/rechazar requieren `document.review` (CATALOGADOR, REVISOR); aprobar requiere `document.approve` (REVISOR queda bloqueado con 403).

### Integración con DSpace (FASE 13)
- **Configuración de repositorios** (`backend/app/repositories/router.py`): CRUD en `/api/admin/repositories` (nombre, código, URL de la API REST, protocolo, usuario y credencial — la credencial se guarda enmascarada; al crear se necesita `admin.repositories.manage`, solo ADMIN). `POST /api/admin/repositories/{id}/collections/sync` autentica contra DSpace, lista comunidades y colecciones (UUID, nombre, handle) y las sincroniza (upsert por `external_id`, inactiva huérfanas sin tipo documental). `PUT /api/admin/repositories/{id}/collections/{c_id}` asocia un tipo documental a una colección.
- **Conector REST** (`backend/app/dspace/connector.py`): `Dspace9Connector` con el contrato de la API de submission de DSpace 7/8/9 — `authenticate()` (login por formulario → token), `get_communities`, `get_collections`, `get_collection`, `create_workspace_item` (`POST /submission/workspaceitems?parent=`), `add_metadata` (JSON-Patch sobre `/sections/traditionalpageone/dc.*`), `upload_bitstream` (multipart), `get_workspace_item`, `submit_workspace_item` (`POST /workflow/workflowitems` con `text/uri-list`) y `get_item`. El frontend nunca habla con DSpace: todo ocurre desde el backend.
- **Export SNRD-DC** (`backend/app/snrd/export.py`): `GET /api/documents/{id}/snrd` devuelve el perfil SNRD en Dublin Core (`dc.contributor.author`, `dc.date.issued`, `dc.language.iso`, `dc.identifier.other` = sha256...).
- **Depósito** (`backend/app/deposit/router.py` + `backend/app/jobs/tasks.py`): `POST /api/documents/{id}/deposit` (202) solo si el documento está `APPROVED` y hay repositorio + colección activa con tipo asociado (si ya fue depositado o no está aprobado responde 409). La tarea `deposit_document` adopta el job `DEPOSIT`: validación final, crea el workspace item, agrega metadata SNRD-DC, sube el PDF, hace submit y registra una `Deposition` `COMPLETED` (item UUID + handle) dejando el documento `DEPOSITED`. Un fallo revierte a `APPROVED` con el error visible para reintentar; un depósito ya completado no se duplica.

### Auditoría (FASE 14)
- **Registro central** (`backend/app/audit/service.py` + tabla `audit_logs`): toda operación relevante queda anotada con usuario (o `sistema` para tareas async), acción, entidad (tipo + id), valores **anterior/nuevo**, IP (honra `X-Forwarded-For` para proxies) y user-agent — sin guardar información sensible (las credenciales de repositorios nunca entran al log).
- **Acciones auditadas**: `auth.login`, `document.upload`, `document.delete`, `ocr.request`/`ocr.completed`, `ai.extraction` (agente, modelo, proveedor, prompt hash, cantidad de registros, tokens de entrada/salida y duración) y `ai.extraction.failed`, `metadata.normalize`, `document.validate`, `record.create`/`update`/`delete` (campo y valor anterior), `document.approve`/`reject` (una aprobación repetida no duplica), `deposit.request`/`completed`/`failed`, `repository.create`/`update`/`delete`/`sync` y `collection.update`/`delete`.
- **Consulta** (`backend/app/audit/router.py`): `GET /api/admin/audit` (solo ADMIN, permiso `audit.view`) con filtros `action`, `entity_type`, `entity_id`, `user_id`, `from_date`, `to_date` y paginación; `GET /api/documents/{id}/history` (con permiso `document.view`) combina auditoría + jobs del pipeline + deposiciones del documento en una línea de tiempo única.
- **Frontend**: `/admin/audit` — tabla de registros con filtros por acción/entidad, paginación y detalle de valores anterior/nuevo.

### Dashboard (FASE 15)
- **Estadísticas agregadas** (`backend/app/dashboard/router.py` + `schemas.py`): `GET /api/admin/dashboard` (permiso `dashboard.view`, ya asignado a ADMIN, CATALOGADOR y REVISOR) consolida el estado completo del sistema en un solo payload:
  - **Documentos**: total, procesados, en revisión, aprobados, rechazados, depositados y conteo por estado.
  - **Procesamiento**: OCR, extracciones IA, normalizaciones y validaciones ejecutadas; tiempos promedio (ms) globales y por tipo de job; errores por tipo; jobs por estado.
  - **Extracción IA**: ejecuciones, exitosas y errores; tokens promedio entrada/salida; tiempo promedio; errores por agente y por modelo.
  - **Depósitos**: total, completados, fallidos y pendientes.
  - **Extras**: tendencia de documentos por día (últimos 7 días), total de usuarios y repositorios.
- **Frontend**: `/admin/dashboard` — tarjetas de métricas, tablas de errores por agente/modelo, tiempos por tipo de job y gráfico de barras de tendencia diaria.

### Tests e2e (FASE 16)
- **Suite e2e hermética** (`backend/tests/test_e2e.py`): a diferencia del resto de la suite (mocks en proceso), arranca `scripts/mock_ai_server.py` y `scripts/mock_dspace_server.py` como subprocesos en puertos libres y ejecuta el pipeline por **HTTP real** — extracción IA (conector `/v1/chat/completions` real con tokens verificables 123/45) y depósito DSpace (`Dspace9Connector` real sin `MockTransport`): repo → sync colecciones → asociar tipo → subir → extraer → normalizar → validar → edición humana → aprobar → depositar `DEPOSITED` (item + handle) → deduplicación NOOP → auditoría → historia unificada → dashboard.
- **Permisos y estados**: 401 sin token, 403 para el revisor (auditoría/repos) con `dashboard.view` permitido, 409 al depositar sin aprobar, deposit task ERROR.
- **OCR real**: PDF escaneado en blanco → detección `needs_ocr` → `run_ocr` con Tesseract real (`--skip-text`) → job y páginas marcadas + auditoría `ocr.completed` (skip si no hay herramientas).
- Los mock servers aceptan el puerto como argumento opcional (default 9999/9998); el contenedor api monta `scripts/` para poder ejecutarlos.

### Seguridad (FASE 17)
- **Revocación de sesiones** (`backend/app/auth/session.py` + tabla `revoked_tokens` + `users.token_version`): los JWT llevan `jti` y `version`; `POST /api/auth/logout` registra el `jti` en la lista de revocados y todo endpoint autenticado lo rechaza (401). Un cambio de password o la desactivación de un usuario incrementa su `token_version`, invalidando todos los tokens emitidos con anterioridad. `POST /api/auth/refresh` ahora exige usuario autenticado, activo y no revocado.
- **Cabeceras de seguridad**: middleware que agrega `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY` y `Referrer-Policy: same-origin` a todas las respuestas.
- **Guarda de producción**: con `APP_ENV=production` el arranque falla si se conservan `JWT_SECRET`/`APP_SECRET_KEY` de desarrollo o el CORS por defecto (no se puede desplegar con credenciales conocidas).
- **Subida de archivos**: el upload lee con límite explícito (413 si excede el máximo, sin cargar el archivo completo en memoria) y el nombre original se sanea (se eliminan `\r`, `\n`, comillas y caracteres de control) antes de usarse en `Content-Disposition` (evita inyección de cabeceras en la descarga).
- **Auto-bloqueo de administradores**: un admin no puede desactivarse, eliminarse ni quitarse el rol `ADMIN` a sí mismo.
- **Aislamiento de prompts**: el texto del documento solo ocupa el placeholder `{{document_text}}` del prompt de usuario; el prompt de sistema es fijo (verificado con test) y no puede ser reescrito por el contenido del PDF.
- **Auditado sin cambios**: CORS configurado, MIME/extension y contenido real del PDF validados, claves de storage derivadas de SHA-256 (sin path traversal), API keys de proveedores e IA y credenciales de repositorios siempre enmascaradas/cifradas (Fernet), auditoría sin secretos, errores 500 sin detalles internos. En producción el TLS lo aporta el proxy de Dokploy (FASE 18).

### Producción (FASE 18)
- **Compose de producción** (`docker-compose.prod.yml`, proyecto `metadato-prod`): postgres, redis, minio, api, worker (Celery), frontend (Next build + start) y un contenedor **`migrate` one-shot** (`alembic upgrade head`) que corre en el arranque. Secretos obligatorios vía `environment` con `${VAR:?Defina …}`: sin `.env` completo el stack **no arranca**. Puertos por defecto sin conflicto con dev: `POSTGRES_PORT=5433`, `REDIS_PORT=6380`, `MINIO_PORT=9002`, `MINIO_CONSOLE_PORT=9003`, `API_PORT=8001`, `FRONTEND_PORT=3001` (todos override por env).
- **Entrada única por dominio**: el navegador solo ve `https://MI.DOMINIO.GOB.AR` (frontend `:3000`). El frontend reescribe `/api/*` → `http://api:8000/api/*` (`next.config.ts` con `API_INTERNAL_URL` horneada en build via `frontend/Dockerfile.prod`), así la API no necesita puerto público, CORS ni subdominio adicional; solo el puerto 3000 se publica en Dokploy.
- **Guarda de producción activa**: `APP_ENV=production` + `seccomp:unconfined` activo para postgres (requerido en kernel < 4.8, inofensivo en kernels modernos).
- **Bootstrap**: tras el primer despliegue, desde la terminal del contenedor `api` en Dokploy: `python -m app.seed` (crea roles/permisos y el usuario `admin`, idempotente).
- **Operación**: `make prod-config|prod-up|prod-down|prod-logs|prod-seed|prod-backup`; `deploy/backup.sh` (pg_dump + tar de MinIO, conserva 7).
- **Guía paso a paso en Dokploy**: ver `docs/DEPLOYMENT.md` (proyecto → servicio Docker Compose apuntando a `docker-compose.prod.yml` desde el repo → variables de entorno desde `.env.prod.example` → deploy → dominios: contenedor `frontend`, puerto 3000, HTTPS Let's Encrypt).

### Frontend de administración
- `/login`: autenticación.
- `/admin`: navegación con guard de sesión.
- `/admin/dashboard`: dashboard de estadísticas del sistema.
- `/admin/metadata`: lista de campos y formulario de creación dinámico.
- `/admin/ai`: agentes de extracción IA (alta con modelo/tipo documental/prompts, activar/desactivar, eliminar).
- `/admin/repositories`: repositorios DSpace (alta con URL/autenticación/credencial cifrada, sincronización de comunidades/colecciones y asociación de tipos documentales).
- `/admin/audit`: consulta de auditoría con filtros y paginación.

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
                        │  /api/documents /api/review /api/admin/repositories /api/deposit │
                        │  /api/admin/audit /api/documents/{id}/history │
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
│   │   ├── ai/               # proveedores, modelos, agentes (admin) + propagación IA (F9)
│   │   ├── metadata/         # esquemas, campos, vocabularios, tipos documentales (admin)
│   │   ├── pdf/              # motor PDF: upload, análisis, dedup, descarga (F7)
│   │   ├── ocr/              # motor OCR: OCRmyPDF+Tesseract, extracción por página (F8)
│   │   ├── extraction/       # extracción IA: selección de agente, prompt, validación, records (F9)
│   │   ├── jobs/             # Celery (celery_app + tareas: run_ocr, extract_metadata)
│   │   ├── core/            # security (bcrypt/JWT/Fernet), dependencies (RBAC), config, storage (S3/filesystem)
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
├── scripts/                 # utilidades (patch-firewall.sh, mock_ai_server.py)
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
make test                     # 201 tests del backend
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

Estado actual: **201 tests en verde** (smoke, auth, users, ai_admin, agents, metadata, pdf, ocr, extraction, normalization, validation, review, dspace, audit, dashboard, security, e2e). Los endpoints externos (IA, DSpace) se simulan con `httpx.MockTransport`; el motor OCR se prueba con mocks deterministas y en vivo contra Tesseract real. La suite **e2e** (`backend/tests/test_e2e.py`) arranca los mock servers reales como subprocesos en puertos libres y ejecuta el pipeline completo por HTTP real (extracción IA y depósito DSpace sin monkeypatch); `scripts/mock_ai_server.py` y `scripts/mock_dspace_server.py` aceptan el puerto como argumento opcional y también permiten probar de extremo a extremo desde Docker. La suite **security** (`backend/tests/test_security.py`, 14 tests) cubre revocación de tokens (logout, refresh, cambio de password, desactivación), cabeceras de seguridad, guarda de producción, sanitizado de nombres de archivo, límite de upload y auto-bloqueo de administradores.

---

## 13. Roadmap

- **Completadas**: F1–F18 — autenticación, usuarios, IA, metadatos, PDF, OCR, extracción, normalización, validación, revisión, DSpace, auditoría, dashboard, tests e2e, seguridad y **producción/Dokploy**.
- **Siguientes**: despliegue en el servidor destino, ajuste fino operativo (monitoreo, rate limiting) y ampliación de la cobertura de tests del frontend.

---

## 14. Despliegue

- Repositorio alojado en **GitHub** (privado): `https://github.com/brandall2021/metadataia`.
- Producción con **Dokploy**: `docker-compose.prod.yml` (proyecto `metadato-prod`, volúmenes nombrados, migración en el arranque, secretos obligatorios).
- **Guía completa paso a paso (Dokploy, variables, bootstrap, backups, troubleshooting, firewall del host)**: `docs/DEPLOYMENT.md`.
- Plantilla de variables: `.env.prod.example` (secretos con `openssl rand -base64 48`).
- Ruta alternativa documentada (subdominio `api.MI.DOMINIO` con CORS) si se prefiere exponer la API por separado.

---

## 15. Comandos útiles

```bash
make dev-up    # levantar todos los servicios
make build     # reconstruir imágenes
make migrate   # alembic upgrade head
make seed      # datos iniciales
make test      # tests del backend (201 en verde)
make logs      # logs en vivo
make ps        # estado de servicios

# Producción (FASE 18)
make prod-config   # valida docker-compose.prod.yml con tu .env
make prod-up       # build + arranque del stack prod (migración incluida)
make prod-logs     # logs del stack prod
make prod-seed     # bootstrap admin/roles (una vez, post-deploy)
make prod-backup   # pg_dump + tar de MinIO en ./backups/
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