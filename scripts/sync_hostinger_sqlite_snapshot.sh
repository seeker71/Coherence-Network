#!/usr/bin/env bash
set -euo pipefail

HOSTINGER_HOST="${HOSTINGER_HOST:-root@187.77.152.42}"
HOSTINGER_KEY="${HOSTINGER_KEY:-$HOME/.ssh/hostinger-openclaw}"
REMOTE_ROOT="${REMOTE_ROOT:-/docker/coherence-network/repo}"
LOCAL_DIR="${LOCAL_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/.cache/local-instance/hostinger-snapshot}"

mkdir -p "${LOCAL_DIR}"

if [[ ! -f "${HOSTINGER_KEY}" ]]; then
  echo "Missing SSH key: ${HOSTINGER_KEY}" >&2
  exit 2
fi

echo "Syncing Hostinger snapshot from ${HOSTINGER_HOST}"
echo "Remote root: ${REMOTE_ROOT}"
echo "Local dir: ${LOCAL_DIR}"

scp -i "${HOSTINGER_KEY}" -o BatchMode=yes -o StrictHostKeyChecking=no \
  "${HOSTINGER_HOST}:${REMOTE_ROOT}/data/coherence.db" \
  "${LOCAL_DIR}/coherence.remote.data.db"

scp -i "${HOSTINGER_KEY}" -o BatchMode=yes -o StrictHostKeyChecking=no \
  "${HOSTINGER_HOST}:${REMOTE_ROOT}/api/data/coherence.db" \
  "${LOCAL_DIR}/coherence.remote.api.db"

python3 - <<'PY' "${LOCAL_DIR}"
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

root = Path(sys.argv[1])
payload = {
    "synced_at": datetime.now(timezone.utc).isoformat(),
    "files": [],
}
for name in ("coherence.remote.data.db", "coherence.remote.api.db"):
    p = root / name
    payload["files"].append(
        {
            "path": str(p),
            "exists": p.exists(),
            "size_bytes": p.stat().st_size if p.exists() else 0,
        }
    )

(root / "snapshot_meta.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps(payload, indent=2))
PY
