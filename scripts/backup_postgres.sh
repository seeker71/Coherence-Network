#!/usr/bin/env bash
# Nightly Postgres backup for Coherence Network.
#
# Runs on the VPS (Hostinger, 187.77.152.42). Installed via cron:
#   15 3 * * * /docker/coherence-network/repo/scripts/backup_postgres.sh
#
# Writes timestamped gzipped dumps to /docker/coherence-network/backups/
# and prunes dumps older than $RETENTION_DAYS (default 30).
#
# Dumps are plain SQL (pg_dump -Fp) gzipped, readable by any Postgres 16+ psql.
# Restore with: scripts/restore_postgres.sh <dump-file>
#
# Exits non-zero on any failure so cron emails/logs surface it.

set -euo pipefail

COMPOSE_DIR="${COMPOSE_DIR:-/docker/coherence-network}"
BACKUP_DIR="${BACKUP_DIR:-/docker/coherence-network/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
DB_USER="${DB_USER:-coherence}"
DB_NAME="${DB_NAME:-coherence}"
POSTGRES_SERVICE="${POSTGRES_SERVICE:-postgres}"

TS="$(date -u +%Y%m%d-%H%M%SZ)"
OUT="${BACKUP_DIR}/coherence-${TS}.sql.gz"
LOG="${BACKUP_DIR}/backup.log"

mkdir -p "${BACKUP_DIR}"

{
  echo "[$(date -u +%FT%TZ)] backup starting -> ${OUT}"
} >> "${LOG}"

cd "${COMPOSE_DIR}"

if ! docker compose exec -T "${POSTGRES_SERVICE}" \
  pg_dump -U "${DB_USER}" -d "${DB_NAME}" -Fp --no-owner --no-privileges \
  | gzip -9 > "${OUT}"; then
  echo "[$(date -u +%FT%TZ)] ERROR: pg_dump failed" >> "${LOG}"
  rm -f "${OUT}"
  exit 1
fi

SIZE=$(du -h "${OUT}" | cut -f1)

# Sanity check: dump must contain contribution_ledger data
LEDGER_ROWS=$(gzip -cd "${OUT}" | awk '/^COPY public.contribution_ledger/,/^\\\.$/' | grep -c '^clr_' || true)

if [[ "${LEDGER_ROWS}" -lt 1 ]]; then
  echo "[$(date -u +%FT%TZ)] WARNING: dump contains 0 contribution_ledger rows — contribution_ledger may be empty, or dump format unexpected" >> "${LOG}"
fi

echo "[$(date -u +%FT%TZ)] backup ok size=${SIZE} contribution_ledger_rows=${LEDGER_ROWS}" >> "${LOG}"

# Prune old dumps
find "${BACKUP_DIR}" -maxdepth 1 -name 'coherence-*.sql.gz' -mtime "+${RETENTION_DAYS}" -print -delete >> "${LOG}" 2>&1 || true

echo "${OUT}"
