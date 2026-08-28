ESPECIFICACIÓN TÉCNICA Y PLAN DE DESARROLLO
PROYECTO: METADATAIA
Sistema de extracción, normalización, validación y depósito de metadatos desde documentos PDF mediante OCR + Agentes de IA + SNRD + DSpace 9

VERSIÓN: 1.0
FECHA: 2026-08-28

======================================================================
1. OBJETIVO GENERAL
======================================================================

Desarrollar una aplicación web denominada METADATAIA cuyo objetivo sea
procesar documentos PDF institucionales, extraer automáticamente sus
metadatos mediante inteligencia artificial, utilizar OCR cuando el PDF
sea escaneado, normalizar y validar los metadatos según la configuración
SNRD/Dublin Core definida por el administrador, permitir una revisión
humana y finalmente depositar el documento y sus metadatos en DSpace 9.

El sistema debe ser GENÉRICO Y CONFIGURABLE.

NO se debe programar de forma rígida:
- el proveedor de IA;
- el modelo de IA;
- el prompt;
- los campos de metadatos;
- los tipos documentales;
- los vocabularios;
- las reglas de validación;
- la colección DSpace;
- los valores específicos de una institución.

Todo lo anterior debe poder administrarse desde el panel de
Administración.

El sistema debe soportar inicialmente:
- Tesis;
- Artículos científicos;
- Resoluciones.

La arquitectura debe permitir agregar posteriormente:
- libros;
- capítulos de libros;
- informes;
- ordenanzas;
- disposiciones;
- actas;
- trabajos finales;
- ponencias;
- otros tipos documentales.

======================================================================
2. OBJETIVO FUNCIONAL
======================================================================

Flujo principal:

1. Usuario inicia sesión.
2. Usuario selecciona "Nuevo documento".
3. Usuario selecciona el tipo documental.
4. Usuario carga un PDF.
5. Sistema valida el archivo.
6. Sistema analiza el PDF.
7. Sistema determina si contiene texto suficiente.
8. Si no contiene texto suficiente, ejecuta OCR.
9. Sistema obtiene texto estructurado por página.
10. Sistema obtiene el perfil documental.
11. Sistema obtiene el agente IA asociado.
12. El agente obtiene el modelo y prompt configurados.
13. La IA extrae los metadatos en formato JSON estructurado.
14. Sistema registra confianza y evidencia por campo.
15. Motor de normalización transforma valores a los valores configurados.
16. Motor de validación ejecuta las reglas de metadatos.
17. Motor SNRD verifica cumplimiento.
18. Usuario revisa y modifica los metadatos.
19. Usuario aprueba.
20. Sistema valida nuevamente.
21. Sistema crea el objeto correspondiente en DSpace 9.
22. Sistema carga el PDF.
23. Sistema carga los metadatos.
24. Sistema completa el proceso de depósito.
25. Sistema almacena UUID/Handle y resultado.
26. Sistema registra toda la operación en auditoría.

======================================================================
3. REQUISITOS TECNOLÓGICOS
======================================================================

Backend:
- Python 3.12+
- FastAPI
- Pydantic
- SQLAlchemy
- Alembic

Frontend:
- Next.js
- TypeScript
- React
- UI responsive

Base de datos:
- PostgreSQL

Procesamiento asíncrono:
- Redis
- Celery

OCR:
- OCRmyPDF
- Tesseract

Almacenamiento:
- MinIO compatible con S3
- permitir filesystem local para desarrollo

Contenedores:
- Docker
- Docker Compose

Proxy:
- Nginx

Autenticación:
- JWT
- RBAC

Pruebas:
- pytest
- pruebas de API
- pruebas unitarias
- pruebas de integración
- pruebas end-to-end

======================================================================
4. PRINCIPIO ARQUITECTÓNICO FUNDAMENTAL
======================================================================

Separar estrictamente:

A. Procesamiento del documento
B. OCR
C. Extracción de texto
D. Inteligencia artificial
E. Normalización
F. Validación
G. Revisión humana
H. Repositorio

La IA NO debe escribir directamente en DSpace.

Flujo obligatorio:

PDF
 -> Analyzer
 -> OCR si corresponde
 -> Text Extraction
 -> AI Extraction
 -> Metadata Normalizer
 -> Metadata Validator
 -> Human Review
 -> SNRD Validator
 -> DSpace Connector

======================================================================
5. ARQUITECTURA DE COMPONENTES
======================================================================

Frontend
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
          Storage
             |
             v
       DSpace Connector
             |
             v
          DSpace 9

Componentes backend sugeridos:

backend/
  app/
    main.py
    core/
    auth/
    users/
    documents/
    pdf/
    ocr/
    extraction/
    ai/
    metadata/
    validation/
    snrd/
    dspace/
    workflows/
    audit/
    repositories/
    administration/
    jobs/

======================================================================
6. ESTRUCTURA DE BASE DE DATOS
======================================================================

Crear migraciones con Alembic.

TABLA users
- id UUID PK
- username
- email
- password_hash
- first_name
- last_name
- active
- created_at
- updated_at

TABLA roles
- id UUID PK
- name
- description

TABLA permissions
- id UUID PK
- code
- description

TABLA user_roles
- user_id FK
- role_id FK

TABLA role_permissions
- role_id FK
- permission_id FK

TABLA ai_providers
- id UUID PK
- name
- code
- type
- base_url
- api_key_encrypted
- active
- configuration_json
- created_at
- updated_at

Ejemplos de provider:
- OpenAI
- Anthropic
- Ollama
- proveedor compatible con OpenAI API
- proveedor institucional

TABLA ai_models
- id UUID PK
- provider_id FK
- name
- model_identifier
- context_window
- supports_json
- supports_vision
- temperature_default
- max_tokens_default
- active
- configuration_json

TABLA ai_agents
- id UUID PK
- name
- code
- description
- document_type_id FK nullable
- active
- current_version_id FK nullable
- created_at
- updated_at

TABLA ai_agent_versions
- id UUID PK
- agent_id FK
- version_number
- model_id FK
- system_prompt
- extraction_prompt
- temperature
- max_tokens
- output_schema_json
- configuration_json
- active
- created_by
- created_at

IMPORTANTE:
Nunca sobrescribir una versión utilizada anteriormente.
Crear nueva versión.

TABLA document_types
- id UUID PK
- name
- code
- description
- default_agent_id FK nullable
- active
- created_at
- updated_at

TABLA metadata_schemas
- id UUID PK
- name
- code
- namespace
- description
- active
- version

TABLA metadata_fields
- id UUID PK
- schema_id FK
- element
- qualifier nullable
- display_name
- description
- data_type
- required
- repeatable
- editable
- ai_extractable
- validation_type
- vocabulary_id nullable
- order_index
- active

Ejemplos:
- dc.title
- dc.contributor.author
- dc.date.issued
- dc.subject
- dc.description.abstract
- dc.language
- dc.type
- dc.rights
- dc.identifier.doi
- dc.identifier.orcid

TABLA document_type_metadata_fields
- id UUID PK
- document_type_id FK
- metadata_field_id FK
- required_override nullable
- order_index
- extraction_instruction nullable

TABLA vocabularies
- id UUID PK
- name
- code
- description
- source
- active

TABLA vocabulary_values
- id UUID PK
- vocabulary_id FK
- code
- label
- normalized_value
- synonyms_json
- active

TABLA repositories
- id UUID PK
- name
- code
- base_url
- api_url
- authentication_type
- username
- credential_reference
- active
- configuration_json

TABLA repository_collections
- id UUID PK
- repository_id FK
- external_id
- name
- handle nullable
- document_type_id nullable
- active

TABLA documents
- id UUID PK
- original_filename
- storage_path
- mime_type
- file_size
- sha256
- page_count
- document_type_id FK
- repository_collection_id FK nullable
- status
- uploaded_by FK
- created_at
- updated_at

TABLA document_pages
- id UUID PK
- document_id FK
- page_number
- text
- ocr_used
- text_length
- metadata_json

TABLA processing_jobs
- id UUID PK
- document_id FK
- job_type
- status
- progress
- started_at
- finished_at
- error_message
- worker_id
- metadata_json

TABLA extraction_runs
- id UUID PK
- document_id FK
- agent_id FK
- agent_version_id FK
- model_id FK
- prompt_hash
- started_at
- finished_at
- input_tokens
- output_tokens
- status
- raw_response_storage_path
- error_message

TABLA metadata_records
- id UUID PK
- document_id FK
- metadata_field_id FK
- value
- language nullable
- authority_value nullable
- confidence nullable
- source
- source_page nullable
- source_text nullable
- extraction_run_id nullable
- normalized
- validated
- manually_modified
- created_at
- updated_at

TABLA validation_results
- id UUID PK
- document_id FK
- validator_type
- status
- errors_json
- warnings_json
- created_at

TABLA depositions
- id UUID PK
- document_id FK
- repository_id FK
- collection_id FK
- external_item_id nullable
- handle nullable
- status
- request_json
- response_json
- started_at
- finished_at
- error_message

TABLA audit_logs
- id UUID PK
- user_id nullable
- action
- entity_type
- entity_id
- old_value_json
- new_value_json
- ip_address
- user_agent
- created_at

======================================================================
7. ADMINISTRACIÓN - PROVEEDORES DE IA
======================================================================

Ruta:
Administración > IA > Proveedores

Funciones:
- listar
- crear
- editar
- activar/desactivar
- probar conexión
- eliminar si no está siendo utilizado

Campos:
- nombre
- código
- tipo
- URL
- API Key
- configuración adicional
- activo

Nunca mostrar la API Key completa después de guardarla.

======================================================================
8. ADMINISTRACIÓN - MODELOS IA
======================================================================

Ruta:
Administración > IA > Modelos

Permitir seleccionar proveedor.

Campos:
- nombre visible
- identificador del modelo
- proveedor
- temperatura
- máximo de tokens
- ventana de contexto
- soporta JSON
- soporta visión
- activo

Botón:
"Probar modelo"

Debe ejecutar una llamada mínima y mostrar:
- conexión correcta
- tiempo
- modelo utilizado
- error si existe

======================================================================
9. ADMINISTRACIÓN - AGENTES
======================================================================

Ruta:
Administración > IA > Agentes

Un agente representa una configuración funcional para un tipo de
extracción.

Ejemplo:

Agente:
Extractor de Tesis

Modelo:
GPT seleccionado

Prompt:
configurable

Tipo documental:
Tesis

Schema:
Metadatos Tesis

Debe permitir:
- crear
- editar
- clonar
- activar/desactivar
- versionar
- probar
- consultar historial

======================================================================
10. ADMINISTRACIÓN - PROMPTS
======================================================================

El prompt debe ser editable desde administración.

Debe soportar variables.

Ejemplos:

{{document_type}}
{{metadata_schema}}
{{metadata_fields}}
{{document_text}}
{{language}}
{{institution}}
{{repository}}

El sistema debe construir el prompt final mediante una plantilla segura.

NO permitir que el contenido del documento modifique las instrucciones
del sistema.

Aplicar separación entre:
- system prompt
- extraction prompt
- document content

El documento se considera contenido no confiable.

======================================================================
11. ADMINISTRACIÓN - METADATOS
======================================================================

Ruta:
Administración > Metadatos > Esquemas

Debe permitir crear esquemas.

Ejemplo:

Schema:
SNRD Dublin Core

Namespace:
dc

Luego administrar campos.

Cada campo:
- elemento
- qualifier
- etiqueta
- descripción
- tipo
- obligatorio
- repetible
- editable
- extraíble por IA
- vocabulario
- regla de validación
- orden

NO modificar el código frontend para agregar un nuevo campo.

El frontend debe construir dinámicamente el formulario según la
configuración.

======================================================================
12. ADMINISTRACIÓN - TIPOS DOCUMENTALES
======================================================================

Ruta:
Administración > Documentos > Tipos

Crear:
- Tesis
- Artículo
- Resolución

Cada tipo debe permitir asociar:
- agente IA
- esquema de metadatos
- campos
- vocabularios
- colección DSpace

Ejemplo:

Tesis
 -> Agente Tesis
 -> Schema SNRD
 -> Colección Tesis

Resolución
 -> Agente Resoluciones
 -> Schema SNRD
 -> Colección Resoluciones

======================================================================
13. ADMINISTRACIÓN - VOCABULARIOS
======================================================================

Crear vocabularios configurables.

Debe permitir:
- importar CSV
- agregar valores manualmente
- editar
- activar/desactivar
- definir sinónimos

Ejemplo:

spa | Español
eng | Inglés
por | Portugués

El sistema debe normalizar:
"Español"
"Spanish"
"Castellano"

según los sinónimos configurados.

======================================================================
14. MOTOR DE PDF
======================================================================

Al cargar un archivo:

1. Validar extensión.
2. Validar MIME.
3. Verificar PDF válido.
4. Verificar tamaño máximo configurable.
5. Calcular SHA256.
6. Guardar archivo original.
7. Contar páginas.
8. Analizar existencia de texto.
9. Determinar necesidad de OCR.

Nunca modificar el archivo original.

======================================================================
15. OCR
======================================================================

Utilizar OCRmyPDF + Tesseract.

Flujo:

PDF original
 -> análisis
 -> texto insuficiente
 -> OCRmyPDF
 -> PDF searchable
 -> extracción de texto

Registrar:
- OCR utilizado
- versión de OCR
- idioma
- tiempo
- errores
- páginas procesadas

El idioma OCR debe poder configurarse por tipo documental o
configuración general.

Idiomas iniciales:
- spa
- eng
- por

======================================================================
16. EXTRACCIÓN DE TEXTO
======================================================================

Extraer texto página por página.

Guardar:
- página
- texto
- longitud
- OCR utilizado

No enviar documentos gigantes al modelo sin procesamiento.

Implementar estrategia de:
- truncamiento
- chunking
- resumen intermedio
- extracción por secciones

La estrategia debe depender del tamaño del documento y de la ventana
de contexto del modelo.

======================================================================
17. EXTRACCIÓN DE METADATOS CON IA
======================================================================

La IA debe recibir:
- tipo documental
- campos configurados
- instrucciones de cada campo
- texto del documento
- reglas necesarias

Debe responder exclusivamente JSON válido.

Ejemplo conceptual:

{
  "metadata": [
    {
      "field": "dc.title",
      "value": "Título detectado",
      "confidence": 0.98,
      "page": 1,
      "evidence": "Texto donde se detectó"
    }
  ]
}

La aplicación NO debe confiar ciegamente en el JSON.

Validar con Pydantic/JSON Schema.

Si la respuesta es inválida:
1. intentar reparación controlada;
2. si falla, marcar AI_ERROR;
3. permitir reintento.

======================================================================
18. CONFIDENCE SCORE
======================================================================

Cada valor extraído puede tener confianza entre 0 y 1.

Ejemplo:
0.98 = 98%

Visualización:
- alta
- media
- baja

La confianza no debe ser considerada una garantía de exactitud.

Utilizarla para priorizar revisión.

======================================================================
19. EVIDENCIA
======================================================================

Cada metadato extraído debe almacenar, cuando sea posible:
- página
- texto fuente
- posición
- modelo
- agente
- versión del prompt
- extraction_run

El usuario debe poder pulsar:
"Ver evidencia"

y visualizar la página correspondiente del PDF.

======================================================================
20. NORMALIZADOR
======================================================================

Crear un servicio independiente:

MetadataNormalizer

Responsabilidades:
- fechas
- idiomas
- tipos
- derechos
- vocabularios
- espacios
- mayúsculas/minúsculas
- nombres
- DOI
- ORCID

La normalización debe estar basada en reglas configurables.

Nunca depender exclusivamente del LLM.

======================================================================
21. VALIDACIÓN
======================================================================

Crear MetadataValidator.

Validar:
- obligatorios
- tipo de dato
- repetibilidad
- longitud
- expresiones regulares
- vocabularios
- fechas
- URLs
- DOI
- ORCID
- idiomas

Resultado:

{
  "valid": false,
  "errors": [],
  "warnings": []
}

Diferenciar:
ERROR = impide aprobación
WARNING = permite aprobación pero requiere atención

======================================================================
22. VALIDACIÓN SNRD
======================================================================

Crear módulo separado:

snrd/

No mezclarlo con DSpace.

Debe validar el conjunto de metadatos configurado para interoperabilidad
SNRD.

Debe contemplar como mínimo:
- elementos obligatorios definidos en el perfil adoptado;
- formatos de fecha;
- idioma;
- tipo;
- derechos;
- vocabularios;
- identificadores;
- condiciones de acceso/embargo cuando correspondan;
- consistencia del registro.

IMPORTANTE:
No asumir que cualquier conjunto Dublin Core es automáticamente
compatible con SNRD.

El administrador debe poder configurar el perfil institucional
utilizado.

======================================================================
23. INTERFAZ DE REVISIÓN
======================================================================

Pantalla principal:

COLumna izquierda:
visor PDF

Columna central:
metadatos

Columna derecha:
validación

Cada metadato debe mostrar:
- valor
- confianza
- estado
- evidencia
- posibilidad de editar

Acciones:
- guardar
- validar
- reprocesar IA
- rechazar
- aprobar
- depositar

No permitir depositar si existen errores bloqueantes.

======================================================================
24. WORKFLOW
======================================================================

Estados:

UPLOADED
ANALYZING
OCR_PROCESSING
TEXT_EXTRACTED
AI_PROCESSING
METADATA_EXTRACTED
NORMALIZING
VALIDATING
NEEDS_REVIEW
REJECTED
APPROVED
DEPOSITING
DEPOSITED
ERROR

Cada cambio de estado debe quedar registrado.

======================================================================
25. CONFIGURACIÓN DSPACE
======================================================================

Ruta:
Administración > Repositorios

Configurar:
- nombre
- URL
- API
- autenticación
- usuario
- credencial
- activo

Ruta:
Administración > Repositorios > Colecciones

Sincronizar o registrar:
- comunidades
- colecciones
- UUID
- nombre
- handle

Asociar tipo documental con colección.

======================================================================
26. CONECTOR DSPACE 9
======================================================================

Crear interfaz:

RepositoryConnector

Métodos:

authenticate()
get_communities()
get_collections()
get_collection()
create_workspace_item()
add_metadata()
upload_bitstream()
get_workspace_item()
submit_workspace_item()
get_item()

Implementar:

DSpace9Connector

El frontend nunca debe comunicarse directamente con DSpace.

Todas las operaciones pasan por backend.

======================================================================
27. DEPÓSITO DSPACE
======================================================================

Flujo:

APPROVED
 -> validación final
 -> crear workspace item
 -> agregar metadata
 -> cargar PDF
 -> completar submission
 -> registrar resultado

Guardar:
- repository
- collection
- workspace item
- item UUID
- handle
- fecha
- respuesta
- estado

Si falla:
- conservar estado
- registrar error
- permitir reintento

No duplicar un depósito ya exitoso.

Utilizar SHA256/idempotencia para evitar cargas duplicadas.

======================================================================
28. API REST
======================================================================

Autenticación:

POST /api/auth/login
POST /api/auth/refresh
POST /api/auth/logout

Usuarios:

GET /api/users
POST /api/users
PUT /api/users/{id}
DELETE /api/users/{id}

Documentos:

GET /api/documents
POST /api/documents
GET /api/documents/{id}
PUT /api/documents/{id}
DELETE /api/documents/{id}

Procesamiento:

POST /api/documents/{id}/analyze
POST /api/documents/{id}/ocr
POST /api/documents/{id}/extract-text
POST /api/documents/{id}/extract-metadata
POST /api/documents/{id}/normalize
POST /api/documents/{id}/validate

Revisión:

GET /api/documents/{id}/metadata
PUT /api/documents/{id}/metadata
POST /api/documents/{id}/approve
POST /api/documents/{id}/reject

Depósito:

POST /api/documents/{id}/deposit
GET /api/documents/{id}/deposition
POST /api/documents/{id}/deposit/retry

IA:

GET /api/admin/ai/providers
POST /api/admin/ai/providers
PUT /api/admin/ai/providers/{id}

GET /api/admin/ai/models
POST /api/admin/ai/models
PUT /api/admin/ai/models/{id}

GET /api/admin/ai/agents
POST /api/admin/ai/agents
PUT /api/admin/ai/agents/{id}

GET /api/admin/ai/agents/{id}/versions
POST /api/admin/ai/agents/{id}/versions

Metadatos:

GET /api/admin/metadata/schemas
POST /api/admin/metadata/schemas

GET /api/admin/metadata/fields
POST /api/admin/metadata/fields

GET /api/admin/document-types
POST /api/admin/document-types

Vocabularios:

GET /api/admin/vocabularies
POST /api/admin/vocabularies
POST /api/admin/vocabularies/{id}/import

Repositorios:

GET /api/admin/repositories
POST /api/admin/repositories
POST /api/admin/repositories/{id}/test
GET /api/admin/repositories/{id}/collections

======================================================================
29. FRONTEND
======================================================================

Menú:

Dashboard
Documentos
Nuevo documento
Pendientes de revisión
Aprobados
Depositados

Administración
  Usuarios
  Roles
  IA
    Proveedores
    Modelos
    Agentes
    Versiones
  Metadatos
    Esquemas
    Campos
    Vocabularios
  Tipos documentales
  Repositorios
    DSpace
    Colecciones
  Configuración

Auditoría
Logs

======================================================================
30. DASHBOARD
======================================================================

Mostrar:

- documentos totales
- procesados
- pendientes
- aprobados
- rechazados
- depositados
- errores
- OCR ejecutados
- extracciones IA
- tiempo promedio
- errores por agente
- errores por modelo

======================================================================
31. AUDITORÍA
======================================================================

Registrar:
- usuario
- fecha
- IP
- acción
- documento
- campo
- valor anterior
- valor nuevo

Registrar también:
- modelo utilizado
- agente
- versión
- prompt hash
- tokens
- duración
- respuesta
- errores

No guardar innecesariamente información sensible en logs.

======================================================================
32. SEGURIDAD
======================================================================

Implementar:
- HTTPS en producción
- JWT
- RBAC
- passwords con hash seguro
- rate limiting
- validación de archivos
- límites de tamaño
- sanitización
- protección contra path traversal
- protección contra prompt injection
- gestión segura de secretos
- CORS configurable
- logs de seguridad

El contenido del PDF debe considerarse NO CONFIABLE.

El prompt del documento no debe poder sobrescribir:
- system prompt
- reglas de extracción
- schema
- instrucciones de seguridad

======================================================================
33. MANEJO DE ERRORES
======================================================================

Cada servicio debe tener errores específicos.

Ejemplos:

PDF_INVALID
PDF_TOO_LARGE
OCR_ERROR
TEXT_EXTRACTION_ERROR
AI_CONNECTION_ERROR
AI_TIMEOUT
AI_INVALID_JSON
AI_SCHEMA_ERROR
NORMALIZATION_ERROR
VALIDATION_ERROR
SNRD_VALIDATION_ERROR
DSPACE_AUTH_ERROR
DSPACE_UPLOAD_ERROR
DSPACE_SUBMISSION_ERROR

Mostrar al usuario mensajes entendibles.

Guardar detalle técnico en logs.

======================================================================
34. PROCESAMIENTO ASÍNCRONO
======================================================================

No bloquear la petición HTTP durante:
- OCR
- extracción de documentos grandes
- IA
- depósito DSpace

Utilizar Celery + Redis.

Jobs:

analyze_document
run_ocr
extract_text
extract_metadata
normalize_metadata
validate_metadata
deposit_dspace

Cada job debe:
- actualizar progreso;
- registrar estado;
- manejar reintentos;
- registrar error.

======================================================================
35. REINTENTOS
======================================================================

Para errores transitorios:
- IA timeout
- conexión DSpace
- Redis
- almacenamiento

Implementar retry con backoff.

No reintentar automáticamente:
- PDF inválido
- schema inválido
- datos inválidos
- errores permanentes

======================================================================
36. IDEMPOTENCIA
======================================================================

El sistema no debe crear dos veces el mismo depósito.

Utilizar:
- SHA256
- document_id
- deposition status
- external item ID

Antes de depositar verificar si ya existe un depósito exitoso.

======================================================================
37. EVALUACIÓN DE IA
======================================================================

Crear posteriormente:

Administración > IA > Evaluación

Permitir seleccionar documentos de prueba.

Comparar:
- agente
- modelo
- versión del prompt

Métricas:
- exactitud por campo
- campos faltantes
- valores incorrectos
- confianza
- tiempo
- tokens
- costo si el proveedor lo permite

======================================================================
38. MULTIMODELO
======================================================================

La arquitectura debe permitir cambiar de modelo sin cambiar código.

Ejemplo:

Agente Tesis:
 -> Modelo A

Cambiar:
 -> Modelo B

El resto del sistema permanece igual.

======================================================================
39. MULTI-REPOSITORIO
======================================================================

Aunque inicialmente se utilizará DSpace 9, diseñar:

RepositoryConnector

para permitir posteriormente:
- DSpace 9
- otros DSpace
- otros repositorios

El sistema debe poder tener varios repositorios configurados.

======================================================================
40. CONFIGURACIÓN GLOBAL
======================================================================

Crear configuración administrable:

- tamaño máximo PDF
- extensiones permitidas
- idiomas OCR
- cantidad máxima de reintentos
- timeout IA
- timeout DSpace
- confianza mínima recomendada
- procesamiento automático OCR
- procesamiento automático IA
- almacenamiento
- políticas de conservación

======================================================================
41. FASES DE DESARROLLO
======================================================================

FASE 1 - Inicialización

Crear:
- repositorio Git
- estructura backend
- estructura frontend
- Docker Compose
- PostgreSQL
- Redis
- MinIO
- configuración .env.example

Criterio:
La aplicación inicia completamente mediante Docker Compose.

FASE 2 - Base de datos

Implementar:
- modelos
- relaciones
- migraciones
- seeds iniciales

Criterio:
Base de datos creada correctamente.

FASE 3 - Autenticación

Implementar:
- login
- JWT
- usuarios
- roles
- permisos

Criterio:
Usuario puede iniciar sesión y solo acceder a las funciones autorizadas.

FASE 4 - Administración IA

Implementar:
- proveedores
- modelos
- prueba de conexión

Criterio:
Administrador puede registrar un proveedor y probar un modelo.

FASE 5 - Agentes IA

Implementar:
- agentes
- prompts
- variables
- versiones
- asignación de modelo

Criterio:
Administrador puede crear un agente sin modificar código.

FASE 6 - Metadatos

Implementar:
- schemas
- fields
- vocabularios
- reglas
- tipos documentales
- asociaciones

Criterio:
Administrador puede crear un nuevo campo y verlo automáticamente en frontend.

FASE 7 - PDF

Implementar:
- upload
- SHA256
- análisis
- almacenamiento

Criterio:
PDF queda almacenado y analizado.

FASE 8 - OCR

Implementar:
- detección de texto
- OCRmyPDF
- Tesseract
- extracción por página

Criterio:
PDF escaneado queda procesable mediante texto.

FASE 9 - IA

Implementar:
- selección automática de agente
- construcción de prompt
- llamada al modelo
- JSON Schema
- extracción
- confidence
- evidencia

Criterio:
Una tesis produce metadatos estructurados.

FASE 10 - Normalización

Implementar:
- vocabularios
- fechas
- idioma
- tipos
- derechos
- identificadores

Criterio:
Valores IA son convertidos al formato configurado.

FASE 11 - Validación

Implementar:
- reglas
- errores
- warnings
- validación SNRD

Criterio:
Sistema identifica registros incompletos o inválidos.

FASE 12 - Revisión humana

Implementar:
- visor
- formulario dinámico
- edición
- evidencia
- aprobación

Criterio:
Catalogador puede corregir todos los metadatos antes del depósito.

FASE 13 - DSpace

Implementar:
- configuración
- autenticación
- comunidades
- colecciones
- workspace
- metadata
- bitstream
- submission

Criterio:
Documento aprobado puede depositarse correctamente en DSpace 9.

FASE 14 - Auditoría

Implementar:
- logs
- historial
- extracción IA
- cambios humanos
- depósitos

FASE 15 - Dashboard

Implementar estadísticas.

FASE 16 - Tests

Crear:
- unit tests
- integration tests
- API tests
- OCR tests
- AI mock tests
- DSpace mock tests
- end-to-end

FASE 17 - Seguridad

Auditar:
- autenticación
- permisos
- archivos
- prompts
- secretos
- API

FASE 18 - Producción

Crear:
- Docker Compose producción
- Nginx
- HTTPS
- backups
- health checks
- logging
- monitoring

======================================================================
42. CRITERIOS DE ACEPTACIÓN DEL MVP
======================================================================

El MVP se considera terminado cuando:

1. Usuario puede iniciar sesión.
2. Usuario puede seleccionar "Tesis".
3. Usuario puede cargar un PDF.
4. Sistema detecta si necesita OCR.
5. Sistema ejecuta OCR si corresponde.
6. Sistema extrae texto por página.
7. Sistema utiliza el agente configurado.
8. El administrador puede cambiar el modelo.
9. El administrador puede cambiar el prompt.
10. El administrador puede crear/modificar campos.
11. IA devuelve JSON estructurado.
12. Sistema registra confianza.
13. Sistema registra evidencia.
14. Sistema normaliza metadatos.
15. Sistema valida metadatos.
16. Sistema permite corrección humana.
17. Sistema impide depósito con errores bloqueantes.
18. Usuario puede aprobar.
19. Sistema deposita en DSpace 9.
20. Sistema registra UUID/Handle.
21. Sistema registra auditoría.
22. El proyecto funciona mediante Docker Compose.
23. Existe documentación de instalación.
24. Existen pruebas automatizadas.

======================================================================
43. REGLAS PARA LA IA PROGRAMADORA
======================================================================

REGLA 1:
No desarrollar toda la aplicación de una sola vez.

REGLA 2:
Implementar una fase por vez.

REGLA 3:
Al terminar cada fase:
- ejecutar tests;
- verificar migraciones;
- verificar compilación;
- verificar lint;
- verificar Docker;
- documentar cambios.

REGLA 4:
No modificar una fase anterior sin explicar por qué.

REGLA 5:
No hardcodear metadatos.

REGLA 6:
No hardcodear modelos IA.

REGLA 7:
No hardcodear prompts.

REGLA 8:
No hardcodear tipos documentales.

REGLA 9:
No hardcodear colecciones DSpace.

REGLA 10:
Toda configuración debe almacenarse en PostgreSQL o variables
seguras de entorno cuando corresponda.

REGLA 11:
No almacenar API Keys en el frontend.

REGLA 12:
No enviar directamente el PDF a DSpace sin pasar por aprobación.

REGLA 13:
La IA nunca puede aprobar automáticamente un documento en el MVP.

REGLA 14:
La decisión final debe ser humana.

REGLA 15:
El código debe ser modular.

REGLA 16:
Utilizar interfaces para proveedores IA y repositorios.

REGLA 17:
Toda operación larga debe ejecutarse como job asíncrono.

REGLA 18:
Todas las operaciones importantes deben generar logs.

REGLA 19:
No eliminar datos históricos de extracción IA.

REGLA 20:
Los prompts deben tener versionado.

======================================================================
44. INTERFACES DE ABSTRACCIÓN
======================================================================

Crear:

AIProvider
AIModel
AIAgent
RepositoryConnector
OCRProvider
MetadataNormalizer
MetadataValidator

Ejemplo conceptual:

AIProvider.generate_structured_output()

RepositoryConnector.create_item()

RepositoryConnector.upload_file()

RepositoryConnector.add_metadata()

RepositoryConnector.submit()

Esto permite cambiar tecnologías sin reescribir toda la aplicación.

======================================================================
45. DATOS DE PRUEBA
======================================================================

Crear tres documentos de prueba:
- tesis PDF con texto
- tesis escaneada
- resolución

Crear datos seed:
- usuario admin
- usuario catalogador
- usuario revisor
- proveedor IA de prueba
- modelo mock
- agente tesis
- agente artículo
- agente resolución
- schema SNRD
- campos básicos
- vocabulario idioma
- vocabulario tipo

Para pruebas IA utilizar mocks.
No depender de una API externa para ejecutar la suite.

======================================================================
46. DOCUMENTACIÓN OBLIGATORIA
======================================================================

Crear:

README.md
ARCHITECTURE.md
DATABASE.md
API.md
AI.md
AI_AGENTS.md
METADATA.md
SNRD.md
OCR.md
DSPACE.md
SECURITY.md
DEPLOYMENT.md
TESTING.md
TROUBLESHOOTING.md

======================================================================
47. VARIABLES DE ENTORNO
======================================================================

Crear .env.example.

Ejemplos:

APP_ENV=
APP_SECRET_KEY=

DATABASE_URL=

REDIS_URL=

MINIO_ENDPOINT=
MINIO_ACCESS_KEY=
MINIO_SECRET_KEY=
MINIO_BUCKET=

JWT_SECRET=

DEFAULT_MAX_FILE_SIZE=

OCR_LANGUAGES=

No colocar claves reales en Git.

======================================================================
48. DESARROLLO GUIADO POR PRUEBAS
======================================================================

Para cada módulo:

1. Definir comportamiento.
2. Crear test.
3. Implementar.
4. Ejecutar test.
5. Corregir.
6. Integrar.
7. Documentar.

No considerar terminada una fase solamente porque el código compila.

======================================================================
49. FUTURAS FUNCIONALIDADES
======================================================================

No son necesarias para el MVP, pero la arquitectura debe permitir:

- ORCID
- Crossref
- DOI
- OpenAlex
- autoridades de autores
- reconocimiento de firmas
- reconocimiento de sellos
- extracción de tablas
- extracción de imágenes
- clasificación automática del tipo documental
- detección automática de idioma
- comparación con metadatos existentes
- detección de duplicados
- sugerencia de palabras clave
- generación de resumen
- embeddings
- búsqueda semántica
- RAG para asistencia al catalogador
- múltiples repositorios
- múltiples instituciones
- estadísticas avanzadas

======================================================================
50. DEFINICIÓN FINAL DEL PRODUCTO
======================================================================

METADATAIA debe ser una plataforma configurable de catalogación
asistida por inteligencia artificial.

El sistema recibe un PDF.

Puede aplicar OCR.

Obtiene texto.

Selecciona un agente según el tipo documental.

El agente utiliza el modelo y prompt configurados desde Administración.

La IA devuelve metadatos estructurados.

El sistema normaliza y valida esos metadatos.

El sistema muestra evidencia y confianza.

Un usuario humano revisa y corrige.

El sistema ejecuta validación final SNRD.

Luego el sistema deposita el documento y los metadatos en DSpace 9.

Toda la operación queda auditada.

La arquitectura debe permitir cambiar:
- modelo;
- proveedor;
- prompt;
- agente;
- tipo documental;
- esquema de metadatos;
- vocabularios;
- reglas;
- repositorio;
- colección;

sin modificar el código fuente.

======================================================================
51. INSTRUCCIÓN FINAL PARA LA IA DESARROLLADORA
======================================================================

Desarrollar el sistema de manera incremental.

NO saltar directamente a la implementación completa.

Comenzar por FASE 1.

Al terminar cada fase entregar:

1. archivos creados/modificados;
2. código implementado;
3. migraciones;
4. tests;
5. instrucciones de ejecución;
6. resultado de los tests;
7. problemas encontrados;
8. decisiones técnicas;
9. pendientes de la siguiente fase.

Esperar confirmación para continuar a la siguiente fase si el entorno
de desarrollo así lo requiere.

Priorizar:
- modularidad;
- seguridad;
- mantenibilidad;
- configuración dinámica;
- trazabilidad;
- pruebas;
- interoperabilidad.

El objetivo no es crear un extractor de metadatos aislado, sino una
plataforma institucional reutilizable para catalogación asistida por
IA y depósito controlado en repositorios DSpace 9.
