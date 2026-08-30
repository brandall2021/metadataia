#!/usr/bin/env bash
# ====================================================================
# METADATAIA - Backup de produccion (FASE 18)
#
# Vuelca PostgreSQL y comprime el volumen de MinIO a ./backups.
# Uso: ./deploy/backup.sh [NUMERO_A_CONSERVAR=7]
#
# Requiere que el stack de produccion este levantado:
#   docker compose -f docker-compose.prod.yml up -d
# (En Dokploy los contenedores corren dentro del mismo arreglo; ajustar
#  los nombres de volumen/metodologia si se ejecuta desde otro host.)
# ====================================================================

set -euo pipefail

COMPOSE="docker compose -f docker-compose.prod.yml"
BACKUP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/backups"
KEEP="${1:-7}"
STAMP="$(date +%Y%m%d-%H%M%S)"
PG_USER="${POSTGRES_USER:-metadataia}"
PG_DB="${POSTGRES_DB:-metadataia}"

mkdir -p "$BACKUP_DIR"

echo "[backup] PostgreSQL -> $BACKUP_DIR/metadataia-${STAMP}.sql.gz"
$COMPOSE exec -T postgres pg_dump -U "$PG_USER" -d "$PG_DB" | gzip > "$BACKUP_DIR/metadataia-${STAMP}.sql.gz"

echo "[backup] MinIO -> $BACKUP_DIR/minio-${STAMP}.tar.gz"
docker run --rm \
  -v metadato-prod_minio_data:/data:ro \
  -v "$BACKUP_DIR":/backup \
  alpine:3.20 tar czf "/backup/minio-${STAMP}.tar.gz" -C /data .

echo "[backup] Purgando backups antiguos (se conservan $KEEP)..."
ls -1t "$BACKUP_DIR"/metadataia-*.sql.gz 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm -f
ls -1t "$BACKUP_DIR"/minio-*.tar.gz 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm -f

echo "[backup] Listo:"
ls -lh "$BACKUP_DIR" | tail -n +2