# METADATAIA — Despliegue de producción (FASE 18)

Guía para poner el sistema en producción con **Docker Compose** detrás de
**Dokploy** (proxy inverso + HTTPS automático con Let's Encrypt).

## 1. Arquitectura de producción

Un único stack (`docker-compose.prod.yml`, proyecto `metadato-prod`) con:

| Servicio | Imagen / build | Rol |
|---|---|---|
| `postgres` | postgres:16-alpine | Base de datos (volumen nombrado `pg_data`) |
| `redis` | redis:7-alpine | Cola Celery / sesiones |
| `minio` | minio/minio | Almacenamiento S3 de PDFs y OCR (volumen `minio_data`) |
| `migrate` | build `./backend` | One-shot: `alembic upgrade head` al arrancar |
| `api` | build `./backend` | API FastAPI (uvicorn, :8000) |
| `worker` | build `./backend` | Celery worker (OCR, extracción IA, depósito) |
| `frontend` | build `./frontend` (Dockerfile.prod) | Next.js build + `npm start` (:3000) |

**Flujo**: Dokploy publica una **única URL** `https://DOMAIN` → contenedor
`frontend:3000`. El frontend llama a la API por el **mismo origen**
(`https://DOMAIN/api`): un *rewrite* de Next (`next.config.ts`) enruta `/api`
hacia `http://api:8000` dentro de la red del stack. No hace falta CORS ni
subdominios adicionales; los PDFs y las llamadas IA llegan a través de nginx
de Dokploy sin exponer el backend directo.

> Alternativa para cargas muy pesadas: si se prefiere que el navegador hable
> directo con la API, en Dokploy se asigna un subdominio (p. ej.
> `api.DOMAIN`) al contenedor `api:8000` y se define
> `NEXT_PUBLIC_API_URL=https://api.DOMAIN/api`; en ese caso
> `CORS_ORIGINS` debe incluir `https://DOMAIN`.

**Seguridad (FASE 17 activa en producción)**:
- `APP_ENV=production` hace fallar el arranque si `JWT_SECRET`,
  `APP_SECRET_KEY` o `CORS_ORIGINS` son los valores de desarrollo.
- El compose exige **todos** los secretos con `${VAR:?…}`: sin `.env` (o sin
  las variables en Dokploy) no arranca.

## 2. Requisitos del host / servidor

- Docker Engine 24+ y Docker Compose v2 (Dokploy los gestiona en su instalación).
- **Puertos 80 y 443** abiertos en el firewall del proveedor (los usa Dokploy
  para el proxy y Let's Encrypt).
- **Firewall del host (importante en hosts con reglas estrictas)**:
  algunos proveedores incluyen reglas que descartan tráfico a redes privadas
  (p. ej. `DROP 172.16.0.0/12` en las cadenas `OUTPUT`/`INPUT`). Docker usa
  la red `172.17/172.18.x`, así que esas reglas **bloquean el acceso host →
  contenedor** (healthchecks de Dokploy y publicaciones de puertos). Si se
  observa "sin respuesta" apuntando al puerto publicado, verificar con
  `iptables -L OUTPUT -n -v` y permitir las subredes de Docker delante de los
  DROP:

  ```bash
  iptables -I OUTPUT 3 -d 172.16.0.0/12 -j ACCEPT
  iptables -I INPUT  8 -s 172.16.0.0/12 -j ACCEPT
  ```

  Los números de posición dependen de la cadena real; el objetivo es que el
  ACCEPT quede **antes** del DROP de 172.16/12. Para persistir, reinstalar las
  reglas tras reiniciar (o incorporarlas al script de firewall del proveedor).

- **`ip_forward` / NAT de contenedores**: si los contenedores no tienen salida
  a internet (falla `pip install` en el build, sin DNS en contenedores),
  verificar que el reenvío de IP esté activo y que exista el NAT por red
  Docker (ambos requeridos por Docker; el daemon los gestiona normalmente):

  ```bash
  # Reenvio IP (persistir en /etc/sysctl.conf)
  sysctl -w net.ipv4.ip_forward=1
  echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf

  # SNAT/Masquerade por rango Docker (cubre cualquier red 172.1x docker0/br-)
  iptables -t nat -A POSTROUTING -s 172.16.0.0/12 ! -o br-+ -j MASQUERADE
  ```

  Reglas de iptables son **transitorias** (se pierden al reiniciar): persistir
  con `iptables-save > /etc/iptables.rules` + restauración al arranque, o
  reaplicarlas (en este servidor de desarrollo también fue necesario recrear
  las cadenas `DOCKER-ISOLATION-STAGE-1/2` y el salto `FORWARD -j
  DOCKER-ISOLATION-STAGE-1` tras reorganizar las cadenas).

- **Kernel < 4.8** (p. ej. CentOS 7): si Postgres no arranca con `EPERM` al
  escribir `postmaster.pid`, el servicio `postgres` de `docker-compose.prod.yml`
  ya trae ACTIVO `security_opt: seccomp:unconfined` (requerido en estos hosts
  e inofensivo en kernels modernos).
- **Puerto 80 de salida**: algunos proveedores bloquean el egress TCP/80 desde
  los contenedores; la aplicación solo necesita **443 saliente** (pip, IA,
  DSpace), así que no es un problema para el funcionamiento.

## 3. Generar secretos

En el servidor (o localmente) generar claves seguras:

```bash
openssl rand -base64 48   # POSTGRES_PASSWORD
openssl rand -base64 48   # APP_SECRET_KEY
openssl rand -base64 48   # JWT_SECRET
openssl rand -base64 9    # MINIO_ACCESS_KEY (legible pero aleatorio)
openssl rand -base64 48   # MINIO_SECRET_KEY
```

O de una vez:

```bash
echo "POSTGRES_PASSWORD=$(openssl rand -base64 48)"
echo "APP_SECRET_KEY=$(openssl rand -base64 48)"
echo "JWT_SECRET=$(openssl rand -base64 48)"
echo "MINIO_ACCESS_KEY=$(openssl rand -base64 9 | tr -d '=+/')"
echo "MINIO_SECRET_KEY=$(openssl rand -base64 48)"
```

## 4. Variables de entorno (producción)

Copiar `.env.prod.example` a `.env` y completar. **Nunca** subir el `.env` a
Git. Las variables obligatorias son:

| Variable | Descripción |
|---|---|
| `DOMAIN` | Dominio público que asignará Dokploy (sin `https://`) |
| `POSTGRES_PASSWORD` | Password de PostgreSQL |
| `APP_SECRET_KEY` | Clave maestra (cifrado Fernet de secretos de proveedores IA / repositorios) |
| `JWT_SECRET` | Firma de los JWT |
| `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` | Credenciales del bucket S3 |

Opcionales con valor por defecto: `POSTGRES_USER=metadataia`, `POSTGRES_DB=metadataia`,
`DEFAULT_MAX_FILE_SIZE_MB=100`, `OCR_LANGUAGES=spa+eng+por`,
`AI_TIMEOUT_SECONDS=120`, `DSPACE_TIMEOUT_SECONDS=120`, `AUTO_OCR=true`,
`AUTO_AI=true`, `JWT_EXPIRE_MINUTES=30`.

## 5. Configuración en Dokploy (paso a paso)

1. **Proyecto**: botón *New Project* → nombre, p. ej. `metadataia-produccion`.
2. **Servicio**: dentro del proyecto, *New Service* → **Docker Compose**.
3. **Repositorio**: seleccionar el repo `brandall2021/metadataia`, rama `main`
   y el **Path** del compose: `docker-compose.prod.yml`.
4. **Variables de entorno**: en la pestaña *Environment* del servicio agregar
   **todas** las del punto 4 (`DOMAIN`, `POSTGRES_PASSWORD`, `APP_SECRET_KEY`,
   `JWT_SECRET`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY` y las opcionales que se
   quieran ajustar). Dokploy las inyecta como `.env` del compose.
5. **Build / Deploy**: *Deploy* construye las imágenes (el compose usa
   `build:` local, no registros externos). El one-shot `migrate` corre
   `alembic upgrade head` automáticamente antes de levantar `api` y `worker`
   (Dokploy muestra cada contenedor en la vista *Containers*).
6. **Dominio y HTTPS**: pestaña **Domains** del servicio → *Add Domain* →
   escribir `DOMAIN` (p. ej. `miapp.dominio.gob.ar`) y en **Port** seleccionar
   el contenedor `frontend` interno `3000`. Activar HTTPS: Dokploy emite el
   certificado Let's Encrypt automáticamente (Nginx del paisa). Responder
   correctamente al reto ACME requiere que el DNS apunte al servidor.
7. **Verificar**: abrir `https://DOMAIN` → el frontend debe cargar y el
   login funcionar (la API responde por `https://DOMAIN/api`).

   > Si se usó Script/Docker en lugar de Docker Compose, el servicio Docker
   > equivalente expone el puerto 3000 del frontend y se definen las mismas
   > variables.

### 5.1 Bootstrap del administrador inicial

El seed crea roles, permisos y el usuario **`admin`**. Se ejecuta **una vez** (después del primer despliegue). En Dokploy, desde la pestaña *Terminal* del contenedor `api`:

```bash
python -m app.seed
```

O desde el host del stack:

```bash
docker compose -f docker-compose.prod.yml run --rm api python -m app.seed
```

El seed es idempotente y define el password del admin en su código
(`backend/app/seed.py`); tras el primer login **cambiar el password** del
admin desde el panel (o desde `PUT /api/users`).

### 5.2 Configuración inicial desde el panel

1. **IA**: *Configuración → Proveedores de IA* → alta del proveedor (OpenAI /
   Anthropic / compatible) con API key; las claves se cifran con
   `APP_SECRET_KEY` y nunca se muestran completas.
2. **Repositorio**: *Configuración → Repositorios* → alta de DSpace (url,
   usuario y password); el password se guarda cifrado.
3. **Esquemas / tipos**: cargar el esquema de metadatos, campos y tipos
   documentales (o el backup de un entorno previo).
4. Opcional: ajustar `AUTO_OCR`/`AUTO_AI` según el flujo deseado.

## 6. Operación

### Logs y estado

En Dokploy: pestaña *Logs* de cada contenedor. Desde el host:

```bash
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f --tail=100
```

### Migraciones en releases posteriores

Al hacer *Deploy* de un nuevo commit que incluya una migración, el servicio
`migrate` la aplica automáticamente antes de subir `api`/`worker` (Dokploy
recrea los contenedores).

### Backups

`deploy/backup.sh` vuelca PostgreSQL y comprime el volumen de MinIO a
`./backups/` (conserva las últimas 7 por defecto):

```bash
docker compose -f docker-compose.prod.yml up -d   # ensamblado
./deploy/backup.sh 7
```

**Restaurar PostgreSQL** (en el stack detenido, por ejemplo para migrar de
entorno):

```bash
docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U metadataia -d metadataia < backups/metadataia-20260101-010203.sql.gz \
  # descomprimir previamente: gunzip -c backups/....sql.gz | ...
```

**Restaurar MinIO**: detener el stack, reemplazar el contenido del volumen
`metadato-prod_minio_data` con el tar y levantar de nuevo.

> En Dokploy se recomienda además el backup automático del paisa (volúmenes)
> y, en un entorno institucional, copias fuera del servidor (S3/oferta local).

### Actualizaciones

1. Push a `main` (rama configurada en el servicio).
2. En Dokploy: *Deploy* otra vez — reconstruye imágenes, corre `migrate`
   (si hay migraciones nuevas), recrea `api`/`worker`/`frontend`.
3. Verificar `/health` y el flujo de un documento de prueba.

## 7. Troubleshooting

| Síntoma | Causa probable / solución |
|---|---|
| `https://DOMAIN` no responde | DNS apuntando al servidor; puertos 80/443 abiertos; revisar reglas de firewall del host (sección 2) |
| El compose falla al arrancar con "Defina …" | Falta una variable obligatoria en Environment de Dokploy (sección 4) |
| `RuntimeError: APP_ENV=production requiere …` | `APP_SECRET_KEY`/`JWT_SECRET`/`CORS_ORIGINS` con valores de desarrollo (guarda FASE 17) |
| `api` no arranca tras deploy | Revisar logs del one-shot `migrate` (migraciones) y de `api` |
| Login OK pero la API responde 404 en `/api` | El rewrite de Next no encontró `API_INTERNAL_URL`; verificar variable en el contenedor `frontend` |
| Subida de archivos muy grande falla | Usar la alternativa con subdominio `api.DOMAIN` (sección 1) o ajustar límites del proxy |
| Postgres `EPERM` / no arranca en kernel 3.10 | `seccomp:unconfined` ya viene activo en `postgres` (sección 2) |
| Contenedores sin internet/DNS (pip, IA, DSpace) | `net.ipv4.ip_forward=1` + MASQUERADE por rango Docker (sección 2) |
| `Couldn't load target DOCKER-ISOLATION-STAGE-1` | Recrear las cadenas de aislamiento de Docker + salto en FORWARD (sección 2) |

## 8. Seguridad recomendada (post-despliegue)

- Cambiar el password del admin creado por el seed.
- Revisar la auditoría (`/admin/audit`) periódicamente.
- Mantener actualizados Dokploy y los contenedores (recrear imágenes al desplegar).
- Almacenar los backups cifrados y fuera del servidor.
- Restringir el acceso a la consola de MinIO (puerto 9003) mediante el
  firewall del host (solo IPs administrativas).