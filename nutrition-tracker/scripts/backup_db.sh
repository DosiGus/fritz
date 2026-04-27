#!/usr/bin/env bash
# Daily PostgreSQL backup — run via cron or docker exec
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/backups}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
FILENAME="nutrition_${TIMESTAMP}.sql.gz"

mkdir -p "$BACKUP_DIR"

echo "Starting backup: $FILENAME"

pg_dump \
  --host="${PGHOST:-db}" \
  --port="${PGPORT:-5432}" \
  --username="${PGUSER:-postgres}" \
  --dbname="${PGDATABASE:-nutrition}" \
  --no-password \
  | gzip > "${BACKUP_DIR}/${FILENAME}"

echo "Backup complete: ${BACKUP_DIR}/${FILENAME}"

# Retain last 14 backups
find "$BACKUP_DIR" -name "nutrition_*.sql.gz" -type f | sort -r | tail -n +15 | xargs -r rm -v
