#!/usr/bin/env bash
# Restore the Coherence Network Postgres from a backup dump.
#
# Usage on VPS:
#   scripts/restore_postgres.sh /docker/coherence-network/backups/coherence-YYYYMMDD-HHMMSSZ.sql.gz
#
# DESTRUCTIVE: drops and recreates the target database before restoring.
# The script refuses to run without CONFIRM=yes to protect against accidents.
#
# Recommended flow before restore:
#   1. Take a fresh dump of the current state first (just in case):
#        scripts/backup_postgres.sh
#   2. Stop the api service so no writes race the restore:
#        docker compose stop api
#   3. Run this script with CONFIRM=yes
#   4. Restart: docker compose start api

set -euo pipefail

DUMP="${1:-}"
if [[ -z "${DUMP}" ]]; then
  echo "usage: $0 <dump-file.sql.gz>" >&2
  exit 2
fi
if [[ ! -f "${DUMP}" ]]; then
  echo "dump not found: ${DUMP}" >&2
  exit 2
fi

if [[ "${CONFIRM:-no}" != "yes" ]]; then
  cat >&2 <<EOF
This will DROP the coherence database and restore from:
  ${DUMP}

Set CONFIRM=yes and re-run to proceed:
  CONFIRM=yes $0 ${DUMP}
EOF
  exit 2
fi

COMPOSE_DIR="${COMPOSE_DIR:-/docker/coherence-network}"
DB_USER="${DB_USER:-coherence}"
DB_NAME="${DB_NAME:-coherence}"
POSTGRES_SERVICE="${POSTGRES_SERVICE:-postgres}"

cd "${COMPOSE_DIR}"

echo "[restore] dropping database ${DB_NAME}"
docker compose exec -T "${POSTGRES_SERVICE}" psql -U "${DB_USER}" -d postgres \
  -c "DROP DATABASE IF EXISTS ${DB_NAME};"
docker compose exec -T "${POSTGRES_SERVICE}" psql -U "${DB_USER}" -d postgres \
  -c "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};"

echo "[restore] loading dump ${DUMP}"
gzip -cd "${DUMP}" | docker compose exec -T "${POSTGRES_SERVICE}" \
  psql -U "${DB_USER}" -d "${DB_NAME}" -v ON_ERROR_STOP=1 > /dev/null

echo "[restore] verifying"
docker compose exec -T "${POSTGRES_SERVICE}" psql -U "${DB_USER}" -d "${DB_NAME}" \
  -c "SELECT 'contribution_ledger' AS tbl, COUNT(*) FROM contribution_ledger
      UNION ALL SELECT 'graph_nodes', COUNT(*) FROM graph_nodes
      UNION ALL SELECT 'graph_edges', COUNT(*) FROM graph_edges
      UNION ALL SELECT 'contributors', COUNT(*) FROM contributors;"

echo "[restore] done"
