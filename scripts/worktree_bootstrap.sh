#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_DIR="${ROOT_DIR}/api"
WEB_DIR="${ROOT_DIR}/web"
STATE_DIR="${ROOT_DIR}/.worktree-state"
ACK_FILE="${STATE_DIR}/setup_ack.json"
DOC_PATH="${ROOT_DIR}/docs/WORKTREE-SETUP.md"
NPM_CACHE="${NPM_CACHE:-${ROOT_DIR}/.npm}"

require_cmd() {
  local cmd="$1"
  if ! command -v "${cmd}" >/dev/null 2>&1; then
    echo "Missing required command: ${cmd}"
    exit 1
  fi
}

select_python() {
  local candidate
  for candidate in "$(command -v python3.11 || true)" "$(command -v python3 || true)"; do
    if [[ -n "${candidate}" ]]; then
      echo "${candidate}"
      return 0
    fi
  done
  return 1
}

echo "==> Verifying linked worktree isolation"
python3 "${ROOT_DIR}/scripts/check_worktree_isolation.py"

echo "==> Reading setup guide: ${DOC_PATH}"
if [[ ! -f "${DOC_PATH}" ]]; then
  echo "Missing required guide: ${DOC_PATH}"
  exit 1
fi
head -n 80 "${DOC_PATH}" || true

require_cmd git
require_cmd npm
require_cmd python3

PYTHON_BIN="$(select_python || true)"
if [[ -z "${PYTHON_BIN}" ]]; then
  echo "No python interpreter found (expected python3.11 or python3)."
  exit 1
fi

echo "==> Python selected: ${PYTHON_BIN}"
if [[ ! -x "${API_DIR}/.venv/bin/python" ]]; then
  echo "==> Creating API virtualenv at ${API_DIR}/.venv"
  "${PYTHON_BIN}" -m venv "${API_DIR}/.venv"
fi

echo "==> Installing API dependencies"
"${API_DIR}/.venv/bin/python" -m pip install --upgrade pip
(
  cd "${API_DIR}"
  "${API_DIR}/.venv/bin/python" -m pip install -e ".[dev]"
)

echo "==> Installing web dependencies"
(
  cd "${WEB_DIR}"
  npm_config_cache="${NPM_CACHE}" npm ci
)

mkdir -p "${STATE_DIR}"
DOC_SHA="$("${API_DIR}/.venv/bin/python" - <<'PY'
from pathlib import Path
import hashlib
doc = Path("docs/WORKTREE-SETUP.md")
print(hashlib.sha256(doc.read_bytes()).hexdigest())
PY
)"
BRANCH="$(git -C "${ROOT_DIR}" rev-parse --abbrev-ref HEAD)"
TS_UTC="$("${API_DIR}/.venv/bin/python" - <<'PY'
from datetime import datetime, timezone
print(datetime.now(timezone.utc).isoformat())
PY
)"

cat > "${ACK_FILE}" <<EOF
{
  "doc_path": "docs/WORKTREE-SETUP.md",
  "doc_sha256": "${DOC_SHA}",
  "acknowledged_at_utc": "${TS_UTC}",
  "repo_root": "${ROOT_DIR}",
  "branch": "${BRANCH}"
}
EOF

echo "==> Worktree bootstrap complete"
echo "Ack file: ${ACK_FILE}"
