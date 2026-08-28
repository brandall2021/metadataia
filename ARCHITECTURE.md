# METADATAIA — Arquitectura

## Principio arquitectónico fundamental (spec §4)

Separación estricta de responsabilidades. La IA **nunca** escribe directamente en DSpace.

```
PDF
 -> Analyzer
 -> OCR si corresponde
 -> Text Extraction
 -> AI Extraction
 -> Metadata Normalizer
 -> Metadata Validator
 -> Human Review (SNRD Validator)
 -> DSpace Connector
```

## Componentes

```
Frontend (Next.js)
    |
    v
FastAPI
    |
    +------------------+
    |                  |
    v                  v
PostgreSQL           Redis
                       |
                       v
                    Celery
                       |
             +---------+----------+
             |         |          |
             v         v          v
            OCR       IA      Validation
             |
             v
          Storage (MinIO S3)
             |
             v
       DSpace Connector
             |
             v
          DSpace 9
```

## Backend (`backend/app/`)

Paquetes por dominio, espejando la spec §5:

| Paquete | Responsabilidad (fase) |
|---------|-------------------------|
| `core/` | Configuración (pydantic-settings), sesión SQLAlchemy, seguridad (bcrypt/JWT/Fernet) y dependencias RBAC (F3) |
| `auth/` | Login, refresh, logout, /me (F3) ✅ |
| `users/` | Usuarios, roles, permisos (F3) ✅ |
| `documents/` | Ciclo de vida de documentos (F7+) |
| `pdf/` | Motor PDF: validación, SHA256, análisis (F7) |
| `ocr/` | OCRmyPDF + Tesseract (F8) |
| `extraction/` | Extracción de texto página por página (F8) |
| `ai/` | Proveedores y modelos + prueba de conexión (F4 ✅); agentes, prompts con variables, versiones (F5 ✅); extracción estructurada (F9) |
| `metadata/` | Esquemas, campos, vocabularios (+CSV, sinónimos, normalización) y tipos documentales (F6 ✅; F10 normalizador, F11 reglas) |
| `pdf/` | Motor de PDF: upload, SHA256, validación, análisis de texto y necesidad de OCR (F7 ✅); OCR y extracción de texto (F8) |
| `core/storage.py` | Almacenamiento de objetos S3/MinIO o filesystem (`STORAGE_BACKEND`); originales intactos bajo `documents/{sha256}.pdf` (F7) |
| `metadata/` | Esquemas, campos, vocabularios, normalización (F6, F10) |
| `validation/` | Reglas de validación, errores y warnings (F11) |
| `snrd/` | Validación de interoperabilidad SNRD (F11) |
| `dspace/` | Conector DSpace 9 (F13) |
| `workflows/` | Máquina de estados del documento (F7+) |
| `audit/` | Logs de auditoría (F14) |
| `repositories/` | Registro de repositorios y colecciones (F13) |
| `administration/` | CRUDs del panel de administración (F4-6, F13) |
| `jobs/` | Tareas Celery asíncronas (F7+) |
| `models/` | Modelos ORM de todas las tablas (F2) |

## Abstracciones (spec §44)

Interfaces que permiten cambiar tecnologías sin reescribir la aplicación:

```
AIProvider.generate_structured_output()
RepositoryConnector.create_item() / upload_file() / add_metadata() / submit()
OCRProvider
MetadataNormalizer
MetadataValidator
```

## Base de datos

25 tablas (spec §6). Ver `backend/alembic/` y `backend/app/models/`.
Migraciones con Alembic; la BD inicial se crea con:

```bash
make migrate
```

## Procesamiento asíncrono

Celery + Redis. Tareas definidas (placeholders en `app/jobs/tasks.py`):
`analyze_document`, `run_ocr`, `extract_text`, `extract_metadata`,
`normalize_metadata`, `validate_metadata`, `deposit_dspace`.

## Estado del documento (spec §24)

`UPLOADED → ANALYZING → OCR_PROCESSING → TEXT_EXTRACTED → AI_PROCESSING →
METADATA_EXTRACTED → NORMALIZING → VALIDATING → NEEDS_REVIEW → APPROVED →
DEPOSITING → DEPOSITED` (con `REJECTED` y `ERROR`).

## Decisiones técnicas registradas

- SQLAlchemy 2.0 síncrono + Pydantic v2 (los workers Celery comparten el mismo código).
- Imagen de desarrollo instala el paquete en modo **editable** (`pip install -e ".[dev]"`):
  el código montado por volumen siempre gana sobre la copia en site-packages
  (evita imports obsoletos en pytest).
- Postgres en Docker requiere `seccomp:unconfined` en hosts con kernel 3.10 (CentOS 7).
- El firewall del hosting bloquea tráfico a rangos privados; ver `scripts/patch-firewall.sh`.
- Los FKs circulares (`ai_agents ↔ document_types`, `ai_agents → ai_agent_versions`)
  se crean diferidos (`use_alter`) en la migración inicial.
- `AIAgent.versions` se elimina con `cascade="all, delete-orphan" + passive_deletes`
  (la FK `agent_id` es NOT NULL; sin esto el ORM intentaría anularla al borrar el agente).
- Las relaciones uno-a-muchos de `metadata.py` con FK NOT NULL usan
  `cascade="all, delete-orphan" + passive_deletes` (esquema→campos,
  campo⇄tipo documental, vocabulario→valores) y el CASCADE lo resuelve la BD.
- Sinónimos de vocabulario se guardan con su grafía original; la normalización
  (minúsculas + sin acentos) se aplica al matchear (`normalize`, usado por el
  normalizador F10). El botón frontend se construye dinámicamente desde
  `/api/admin/metadata/fields` (FASE 6).
- El frontend Next.js se compila solo en su contenedor (node:20-alpine):
  las bindings nativas de Next requieren glibc ≥ 2.27 y el host es CentOS 7.
- API Keys de proveedores se cifran en reposo (Fernet derivado de `APP_SECRET_KEY`)
  y solo se exponen enmascaradas (`****last4`).
- JWT stateless: `logout` descarta el token en el cliente; revocación real (blacklist) en FASE 17.
- `httpx` es dependencia de runtime (pruebas de conexión de proveedores).