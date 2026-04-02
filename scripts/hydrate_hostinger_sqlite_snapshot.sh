#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SNAPSHOT_DIR="${SNAPSHOT_DIR:-${ROOT_DIR}/.cache/local-instance/hostinger-snapshot}"
BACKUP_DIR="${BACKUP_DIR:-${ROOT_DIR}/.cache/local-instance/hydration-backups/$(date +%Y%m%d_%H%M%S)}"

REMOTE_DATA_DB="${SNAPSHOT_DIR}/coherence.remote.data.db"
REMOTE_API_DB="${SNAPSHOT_DIR}/coherence.remote.api.db"
LOCAL_DATA_DB="${ROOT_DIR}/data/coherence.db"
LOCAL_API_DB="${ROOT_DIR}/api/data/coherence.db"
LOCAL_DATA_WAL="${LOCAL_DATA_DB}-wal"
LOCAL_DATA_SHM="${LOCAL_DATA_DB}-shm"
LOCAL_API_WAL="${LOCAL_API_DB}-wal"
LOCAL_API_SHM="${LOCAL_API_DB}-shm"

if [[ ! -f "${REMOTE_DATA_DB}" || ! -f "${REMOTE_API_DB}" ]]; then
  echo "Missing snapshot files in ${SNAPSHOT_DIR}. Run ./scripts/sync_hostinger_sqlite_snapshot.sh first." >&2
  exit 2
fi

mkdir -p "${BACKUP_DIR}" "$(dirname "${LOCAL_DATA_DB}")" "$(dirname "${LOCAL_API_DB}")"

if [[ -f "${LOCAL_DATA_DB}" ]]; then
  cp "${LOCAL_DATA_DB}" "${BACKUP_DIR}/coherence.data.db.bak"
fi
if [[ -f "${LOCAL_API_DB}" ]]; then
  cp "${LOCAL_API_DB}" "${BACKUP_DIR}/coherence.api.db.bak"
fi

rm -f "${LOCAL_DATA_WAL}" "${LOCAL_DATA_SHM}" "${LOCAL_API_WAL}" "${LOCAL_API_SHM}"

cp "${REMOTE_DATA_DB}" "${LOCAL_DATA_DB}"
cp "${REMOTE_API_DB}" "${LOCAL_API_DB}"

python3 - <<'PY' "${BACKUP_DIR}" "${LOCAL_DATA_DB}" "${LOCAL_API_DB}" "${REMOTE_DATA_DB}" "${REMOTE_API_DB}"
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

backup_dir = Path(sys.argv[1])
local_data = Path(sys.argv[2])
local_api = Path(sys.argv[3])
remote_data = Path(sys.argv[4])
remote_api = Path(sys.argv[5])

payload = {
    "hydrated_at": datetime.now(timezone.utc).isoformat(),
    "backup_dir": str(backup_dir),
    "targets": [
        {
            "local_path": str(local_data),
            "source_path": str(remote_data),
            "size_bytes": local_data.stat().st_size,
        },
        {
            "local_path": str(local_api),
            "source_path": str(remote_api),
            "size_bytes": local_api.stat().st_size,
        },
    ],
}
(backup_dir / "hydrate_meta.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps(payload, indent=2))
PY
