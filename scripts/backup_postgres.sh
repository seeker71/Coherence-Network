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

# ---------------------------------------------------------------------------
# Off-site replica — optional, gated on env vars so existing crons keep
# working. Without this step, dumps live ONLY on the VPS — same disk and
# zone as the live DB. Off-site upload survives a VPS-loss event.
#
#   COHERENCE_OFFSITE_GH_REPO=owner/repo
#     Upload the gzipped dump to a GitHub release on the named repo.
#     The Coherence Network's posture is sovereign + transparent —
#     dumps belong with the rest of the public body of evidence —
#     so the configured repo is typically public (e.g.
#     seeker71/coherence-network-archive). Requires `gh` authenticated
#     on the host. Idempotent on tag.
#
#   COHERENCE_OFFSITE_GPG_RECIPIENT=key-id-or-email   (optional)
#     For deployments that *do* hold private state, the dump can be
#     encrypted to a GPG public key before upload. Not the default
#     — kept here as an opt-in for forks of the network that have
#     stricter privacy needs.
#
# When neither is set the script proceeds as before (local-only).
# ---------------------------------------------------------------------------

OFFSITE_OUT="${OUT}"
if [[ -n "${COHERENCE_OFFSITE_GPG_RECIPIENT:-}" ]]; then
  ENC="${OUT}.gpg"
  if gpg --batch --yes --trust-model always --output "${ENC}" \
       --encrypt --recipient "${COHERENCE_OFFSITE_GPG_RECIPIENT}" "${OUT}"; then
    OFFSITE_OUT="${ENC}"
    echo "[$(date -u +%FT%TZ)] gpg encrypted -> ${ENC}" >> "${LOG}"
  else
    echo "[$(date -u +%FT%TZ)] WARNING: gpg encryption failed — skipping offsite upload" >> "${LOG}"
    OFFSITE_OUT=""
  fi
fi

if [[ -n "${COHERENCE_OFFSITE_GH_REPO:-}" && -n "${OFFSITE_OUT}" ]]; then
  TAG="backup-postgres-${TS}"
  ASSET="$(basename "${OFFSITE_OUT}")"
  if gh release create "${TAG}" \
       --repo "${COHERENCE_OFFSITE_GH_REPO}" \
       --title "Postgres backup ${TS}" \
       --notes "Nightly pg_dump · size=${SIZE} · ledger_rows=${LEDGER_ROWS}$( [[ "${OFFSITE_OUT}" == *.gpg ]] && echo " · gpg-encrypted" )" \
       >> "${LOG}" 2>&1; then
    if gh release upload "${TAG}" "${OFFSITE_OUT}#${ASSET}" \
         --repo "${COHERENCE_OFFSITE_GH_REPO}" --clobber \
         >> "${LOG}" 2>&1; then
      echo "[$(date -u +%FT%TZ)] offsite ok repo=${COHERENCE_OFFSITE_GH_REPO} tag=${TAG}" >> "${LOG}"
    else
      echo "[$(date -u +%FT%TZ)] WARNING: gh release upload failed for ${ASSET}" >> "${LOG}"
    fi
  else
    echo "[$(date -u +%FT%TZ)] WARNING: gh release create failed for ${TAG}" >> "${LOG}"
  fi

  # If we encrypted before upload, leave the encrypted artifact in
  # the local backups dir too (cheap, useful for parity), but prune
  # it under the same retention rules below.
fi

# Prune old dumps (local + any encrypted siblings)
find "${BACKUP_DIR}" -maxdepth 1 -name 'coherence-*.sql.gz' -mtime "+${RETENTION_DAYS}" -print -delete >> "${LOG}" 2>&1 || true
find "${BACKUP_DIR}" -maxdepth 1 -name 'coherence-*.sql.gz.gpg' -mtime "+${RETENTION_DAYS}" -print -delete >> "${LOG}" 2>&1 || true

echo "${OUT}"
