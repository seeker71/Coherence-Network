#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_DIR="${ROOT_DIR}/api"
WEB_DIR="${ROOT_DIR}/web"
TMP_DIR="$(mktemp -d)"
NPM_CACHE="${NPM_CACHE:-${ROOT_DIR}/.cache/npm}"
API_PORT="${API_PORT:-18000}"
WEB_PORT="${WEB_PORT:-3100}"
API_BASE="http://127.0.0.1:${API_PORT}"
WEB_BASE="http://127.0.0.1:${WEB_PORT}"
API_LOG="${TMP_DIR}/api.log"
WEB_LOG="${TMP_DIR}/web.log"
API_PID=""
WEB_PID=""
API_STARTED=0
WEB_STARTED=0
START_SERVERS=0
AUTO_HEAL=0
SHOW_PORTS=0
DB_URL="${DB_URL:-${DATABASE_URL:-sqlite+pysqlite:///${ROOT_DIR}/.cache/local-instance/coherence_local.db}}"
ADMIN_KEY=""

THREAD_RUNTIME_HELPER="${ROOT_DIR}/scripts/thread_runtime_ports.sh"
if [[ -f "${THREAD_RUNTIME_HELPER}" ]]; then
  # shellcheck disable=SC1091
  source "${THREAD_RUNTIME_HELPER}"
fi

usage() {
  cat <<'USAGE'
Usage:
  ./scripts/verify_worktree_local_web.sh [--start|--auto-heal|--thread-ports]

Options:
  --start
      Start missing API/web services and then validate.
  --auto-heal
      If services are not ready, start missing services automatically and continue.
  --thread-ports
      Print thread-runtime port usage snapshot before validation.

Environment:
  THREAD_RUNTIME_START_SERVERS=1
      Same as --start.
  THREAD_RUNTIME_AUTO_HEAL=1
      Same as --auto-heal.
  THREAD_RUNTIME_API_BASE_PORT / THREAD_RUNTIME_WEB_BASE_PORT
      Thread-specific base offsets used to avoid collisions across threads.
  API_PORT / WEB_PORT
      Legacy explicit ports when thread-runtime allocation is unavailable.
USAGE
}

parse_args() {
  local arg
  for arg in "$@"; do
    case "${arg}" in
      --start)
        START_SERVERS=1
        ;;
      --auto-heal)
        AUTO_HEAL=1
        ;;
      --thread-ports)
        SHOW_PORTS=1
        ;;
      --help|-h)
        usage
        exit 0
        ;;
      *)
        echo "error: unknown argument '${arg}'" >&2
        usage
        exit 1
        ;;
    esac
  done

  if [[ "${THREAD_RUNTIME_START_SERVERS:-0}" == "1" ]]; then
    START_SERVERS=1
  fi
  if [[ "${THREAD_RUNTIME_AUTO_HEAL:-0}" == "1" ]]; then
    AUTO_HEAL=1
  fi
}

ensure_npm_cache() {
  mkdir -p "${NPM_CACHE}"
  if [[ ! -w "${NPM_CACHE}" ]]; then
    echo "npm cache directory is not writable: ${NPM_CACHE}"
    exit 1
  fi
  export npm_config_cache="${NPM_CACHE}"
  export NPM_CONFIG_CACHE="${NPM_CACHE}"
}

npm_ci_hardened() {
  if npm help install 2>/dev/null | grep -q -- "--allow-git"; then
    npm ci --allow-git=none
  else
    echo "Warning: npm version lacks --allow-git; running npm ci without that hardening flag."
    npm ci
  fi
}

prepare_standalone_bundle() {
  local standalone_dir="${WEB_DIR}/.next/standalone"
  local standalone_next_dir="${standalone_dir}/.next"

  if [[ ! -f "${standalone_dir}/server.js" ]]; then
    return 0
  fi

  mkdir -p "${standalone_next_dir}"
  rm -rf "${standalone_next_dir}/static"
  cp -R "${WEB_DIR}/.next/static" "${standalone_next_dir}/static"

  if [[ -d "${WEB_DIR}/public" ]]; then
    rm -rf "${standalone_dir}/public"
    cp -R "${WEB_DIR}/public" "${standalone_dir}/public"
  fi
}

select_python() {
  local candidate
  for candidate in "${API_DIR}/.venv/bin/python" "${API_DIR}/.venv/bin/python3" "$(command -v python3.11 || true)" "$(command -v python3 || true)"; do
    if [[ -n "${candidate}" && -x "${candidate}" ]]; then
      if "${candidate}" -c "import fastapi, uvicorn" >/dev/null 2>&1; then
        echo "${candidate}"
        return 0
      fi
    fi
  done
  return 1
}

port_is_free() {
  local port="$1"
  ! lsof -iTCP:"${port}" -sTCP:LISTEN -t >/dev/null 2>&1
}

wait_for_url() {
  local name="$1"
  local url="$2"
  local attempts="${3:-60}"
  local i
  for ((i = 1; i <= attempts; i += 1)); do
    local code
    code="$(curl -s -o /dev/null -w "%{http_code}" "${url}" || true)"
    if [[ "${code}" =~ ^2[0-9][0-9]$ || "${code}" =~ ^3[0-9][0-9]$ ]]; then
      return 0
    fi
    sleep 1
  done
  echo "Timed out waiting for ${name}: ${url}"
  return 1
}

http_ok() {
  local url="$1"
  local code
  code="$(curl -s -o /dev/null -w "%{http_code}" "${url}" || true)"
  if [[ "${code}" =~ ^2[0-9][0-9]$ || "${code}" =~ ^3[0-9][0-9]$ ]]; then
    return 0
  fi
  return 1
}

api_ready() {
  http_ok "${API_BASE}/api/health"
}

web_ready() {
  http_ok "${WEB_BASE}/"
}

resolve_admin_key() {
  python3 - "${ROOT_DIR}" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
merged = {}
for path in (root / "api" / "config" / "api.json", Path.home() / ".coherence-network" / "config.json"):
    if not path.exists():
        continue
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        continue
    if isinstance(payload, dict):
        merged.update(payload)
auth = merged.get("auth") or {}
if isinstance(auth, dict) and str(auth.get("admin_key") or "").strip():
    print(str(auth["admin_key"]).strip())
else:
    print("dev-admin")
PY
}

check_url() {
  local name="$1"
  local url="$2"
  local required_text="${3:-}"
  local curl_args=()
  if (( $# > 3 )); then
    shift 3
    curl_args=("$@")
  fi
  local headers_file="${TMP_DIR}/$(echo "${name}" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '_').headers"
  local body_file="${TMP_DIR}/$(echo "${name}" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '_').body"
  local curl_cmd=(curl -sS -L -D "${headers_file}" -o "${body_file}")
  if (( ${#curl_args[@]} > 0 )); then
    curl_cmd+=("${curl_args[@]}")
  fi
  curl_cmd+=("${url}")

  echo "==> ${name}: ${url}"
  "${curl_cmd[@]}" >/dev/null

  local status
  status="$(awk 'toupper($1) ~ /^HTTP\// { code=$2 } END { print code }' "${headers_file}")"
  echo "HTTP status: ${status}"
  if [[ -z "${status}" || "${status}" -lt 200 || "${status}" -ge 400 ]]; then
    echo "FAIL: non-success HTTP status"
    return 1
  fi

  if grep -qiE "internal server error|application error|failed to fetch" "${body_file}"; then
    echo "FAIL: page body indicates runtime failure"
    return 1
  fi

  if [[ -n "${required_text}" ]]; then
    if ! grep -Fq "${required_text}" "${body_file}"; then
      echo "FAIL: expected text not found: ${required_text}"
      return 1
    fi
  fi

  echo "PASS"
}

check_web_static_asset() {
  local sample_asset
  sample_asset="$(find "${WEB_DIR}/.next/static/chunks" -maxdepth 1 -type f -name '*.js' | sort | head -n 1)"
  if [[ -z "${sample_asset}" ]]; then
    echo "FAIL: could not find a built Next static chunk to verify"
    return 1
  fi

  local relative_path
  relative_path="${sample_asset#${WEB_DIR}/.next/static/}"
  check_url "Web static asset" "${WEB_BASE}/_next/static/${relative_path}"
}

sample_contributor_id() {
  python3 - "${API_BASE}" <<'PY'
import json
import sys
import urllib.request

base = sys.argv[1].rstrip("/")
url = f"{base}/api/contributors?limit=1"
try:
    with urllib.request.urlopen(url, timeout=5) as response:
        payload = json.load(response)
except Exception:
    print("")
    raise SystemExit(0)

items = payload.get("items", []) if isinstance(payload, dict) else payload
if items:
    print(items[0].get("id", ""))
else:
    print("")
PY
}

sample_contributor_task_id() {
  local contributor_id="$1"
  python3 - "${API_BASE}" "${contributor_id}" <<'PY'
import json
import sys
import urllib.request

base = sys.argv[1].rstrip("/")
contributor_id = sys.argv[2]
url = f"{base}/api/contributors/{contributor_id}/tasks?status=completed&limit=1"
try:
    with urllib.request.urlopen(url, timeout=5) as response:
        payload = json.load(response)
except Exception:
    print("")
    raise SystemExit(0)

items = payload.get("items", []) if isinstance(payload, dict) else payload
if items:
    print(items[0].get("task_id", ""))
else:
    print("")
PY
}

sample_contributor_idea_id() {
  local contributor_id="$1"
  python3 - "${API_BASE}" "${contributor_id}" <<'PY'
import json
import sys
import urllib.request

base = sys.argv[1].rstrip("/")
contributor_id = sys.argv[2]
url = f"{base}/api/contributors/{contributor_id}/idea-contributions?limit=1"
try:
    with urllib.request.urlopen(url, timeout=5) as response:
        payload = json.load(response)
except Exception:
    print("")
    raise SystemExit(0)

items = payload.get("items", []) if isinstance(payload, dict) else payload
if items:
    print(items[0].get("idea_id", ""))
else:
    print("")
PY
}

sample_contributor_stake_id() {
  local contributor_id="$1"
  python3 - "${API_BASE}" "${contributor_id}" <<'PY'
import json
import sys
import urllib.request

base = sys.argv[1].rstrip("/")
contributor_id = sys.argv[2]
url = f"{base}/api/contributors/{contributor_id}/stakes?limit=1"
try:
    with urllib.request.urlopen(url, timeout=5) as response:
        payload = json.load(response)
except Exception:
    print("")
    raise SystemExit(0)

items = payload.get("items", []) if isinstance(payload, dict) else payload
if items:
    print(items[0].get("stake_id", ""))
else:
    print("")
PY
}

sample_spec_id() {
  python3 - "${API_BASE}" <<'PY'
import json
import time
import sys
import urllib.request

base = sys.argv[1].rstrip("/")
urls = [
    f"{base}/api/inventory/system-lineage?runtime_window_seconds=86400",
    f"{base}/api/spec-registry",
]
for url in urls:
    for _ in range(3):
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                payload = json.load(response)
            break
        except Exception:
            payload = None
            time.sleep(1)
    if payload is None:
        continue

    if isinstance(payload, dict):
        specs = ((payload.get("specs") or {}).get("items")) or []
        if specs:
            print(specs[0].get("spec_id", ""))
            raise SystemExit(0)
    if isinstance(payload, list) and payload:
        print(payload[0].get("spec_id", ""))
        raise SystemExit(0)

print("")
PY
}

sample_asset_id() {
  python3 - "${API_BASE}" <<'PY'
import json
import sys
import urllib.request

base = sys.argv[1].rstrip("/")
url = f"{base}/api/assets?limit=1"
try:
    with urllib.request.urlopen(url, timeout=5) as response:
        payload = json.load(response)
except Exception:
    print("")
    raise SystemExit(0)

items = payload.get("items", []) if isinstance(payload, dict) else payload
if items:
    print(items[0].get("id", ""))
else:
    print("")
PY
}

configure_ports() {
  if [[ -f "${THREAD_RUNTIME_HELPER}" ]] && declare -f thread_runtime_resolve_ports >/dev/null 2>&1; then
    local base_api="${THREAD_RUNTIME_API_BASE_PORT:-${API_PORT}}"
    local base_web="${THREAD_RUNTIME_WEB_BASE_PORT:-${WEB_PORT}}"
    thread_runtime_resolve_ports "${base_api}" "${base_web}" "127.0.0.1" "127.0.0.1"
    API_PORT="${THREAD_RUNTIME_API_PORT}"
    WEB_PORT="${THREAD_RUNTIME_WEB_PORT}"
    API_BASE="${THREAD_RUNTIME_API_BASE}"
    WEB_BASE="${THREAD_RUNTIME_WEB_BASE}"
  else
    API_BASE="http://127.0.0.1:${API_PORT}"
    WEB_BASE="http://127.0.0.1:${WEB_PORT}"
  fi
  API_URL="${API_BASE}"
  NEXT_PUBLIC_API_URL="${API_BASE}"
  DATABASE_URL="${DB_URL}"
}

maybe_dump_thread_ports() {
  if (( SHOW_PORTS == 1 )) && [[ -f "${THREAD_RUNTIME_HELPER}" ]]; then
    thread_runtime_dump_usage
    echo
  fi
}

start_api_if_needed() {
  if api_ready; then
    return 0
  fi

  if ! port_is_free "${API_PORT}"; then
    echo "BLOCKER: API port ${API_PORT} is not free"
    return 1
  fi

  local python_bin
  python_bin="$(select_python || true)"
  if [[ -z "${python_bin}" ]]; then
    echo "Could not find a Python interpreter with fastapi+uvicorn available."
    echo "Create api/.venv or install dependencies for python3.11."
    return 1
  fi

  echo "Starting API on ${API_BASE} with ${python_bin}"
  mkdir -p "${ROOT_DIR}/.cache/local-instance"
  (
    cd "${API_DIR}"
    AGENT_TASKS_PERSIST=0 \
    RUNTIME_TELEMETRY_ENABLED=0 \
    API_URL="${API_URL}" \
    DATABASE_URL="${DATABASE_URL}" \
    DB_URL="${DB_URL}" \
    "${python_bin}" -m uvicorn app.main:app --host 127.0.0.1 --port "${API_PORT}"
  ) >"${API_LOG}" 2>&1 &
  API_PID=$!
  API_STARTED=1
  trap cleanup EXIT

  wait_for_url "API health" "${API_BASE}/api/health" 90
  echo "API ready."
}

start_web_if_needed() {
  if web_ready; then
    return 0
  fi

  if ! port_is_free "${WEB_PORT}"; then
    echo "BLOCKER: web port ${WEB_PORT} is not free"
    return 1
  fi

  if [[ ! -f "${WEB_DIR}/package.json" ]]; then
    echo "Missing web/package.json at ${WEB_DIR}"
    return 1
  fi

  ensure_npm_cache
  pushd "${WEB_DIR}" >/dev/null
  if [[ ! -d node_modules || ! -x node_modules/.bin/next ]]; then
    echo "Installing web dependencies (node_modules missing)..."
    npm_ci_hardened
  fi

  echo "Building web app..."
  NEXT_PUBLIC_API_URL="${NEXT_PUBLIC_API_URL}" API_URL="${API_URL}" npm run build
  (
    cd "${WEB_DIR}"
    if [[ -f ".next/standalone/server.js" ]]; then
      prepare_standalone_bundle
      NEXT_PUBLIC_API_URL="${NEXT_PUBLIC_API_URL}" \
      NEXT_PUBLIC_API_BASE="${NEXT_PUBLIC_API_URL}" \
      API_URL="${API_URL}" \
      API_BASE="${API_URL}" \
      HOSTNAME="127.0.0.1" \
      PORT="${WEB_PORT}" \
      node .next/standalone/server.js
    else
      NEXT_PUBLIC_API_URL="${NEXT_PUBLIC_API_URL}" API_URL="${API_URL}" npm run start -- --hostname 127.0.0.1 --port "${WEB_PORT}"
    fi
  ) >"${WEB_LOG}" 2>&1 &
  WEB_PID=$!
  WEB_STARTED=1
  popd >/dev/null
  trap cleanup EXIT

  wait_for_url "web root" "${WEB_BASE}/" 90
  echo "Web ready."
}

cleanup() {
  local exit_code=$?
  set +e
  if (( WEB_STARTED == 1 )) && [[ -n "${WEB_PID}" ]]; then
    kill "${WEB_PID}" >/dev/null 2>&1 || true
    wait "${WEB_PID}" >/dev/null 2>&1 || true
  fi
  if (( API_STARTED == 1 )) && [[ -n "${API_PID}" ]]; then
    kill "${API_PID}" >/dev/null 2>&1 || true
    wait "${API_PID}" >/dev/null 2>&1 || true
  fi
  if (( exit_code != 0 )); then
    echo
    if (( API_STARTED == 1 )); then
      echo "API log tail:"
      tail -n 80 "${API_LOG}" 2>/dev/null || true
      echo
    fi
    if (( WEB_STARTED == 1 )); then
      echo "Web log tail:"
      tail -n 80 "${WEB_LOG}" 2>/dev/null || true
    fi
  fi
  rm -rf "${TMP_DIR}"
}
trap cleanup EXIT

run_validations() {
  check_url "API health" "${API_BASE}/api/health"
  check_url "API ideas" "${API_BASE}/api/ideas"
  check_url "API tasks" "${API_BASE}/api/agent/tasks"
  check_url "API diagnostics overview" "${API_BASE}/api/agent/diagnostics/overview" "" \
    -H "X-Admin-Key: ${ADMIN_KEY}"
  check_url "API system lineage" "${API_BASE}/api/inventory/system-lineage"
  check_url "API endpoint runtime summary" "${API_BASE}/api/runtime/endpoints/summary"
  python3 "${ROOT_DIR}/scripts/validate_local_api_matrix.py" --api-base "${API_BASE}"
  (
    cd "${WEB_DIR}"
    API_BASE="${API_BASE}" node scripts/check_api_parity.js
  )
  sleep 2

  check_url "Web root" "${WEB_BASE}/" "/ideas"
  check_url "Web root nav resonance" "${WEB_BASE}/" "/resonance"
  check_url "Web root nav pipeline" "${WEB_BASE}/" "/pipeline"
  check_url "Web root nav nodes" "${WEB_BASE}/" "/nodes"
  check_url "Web root nav contribute" "${WEB_BASE}/" "/contribute"
  check_web_static_asset
  check_url "Web ideas" "${WEB_BASE}/ideas"
  check_url "Web specs" "${WEB_BASE}/specs"
  local spec_id
  spec_id="$(sample_spec_id)"
  if [[ -n "${spec_id}" ]]; then
    check_url "Web spec detail" "${WEB_BASE}/specs/${spec_id}" "${spec_id}"
  fi
  check_url "Web flow" "${WEB_BASE}/flow"
  check_url "Web tasks" "${WEB_BASE}/tasks"
  check_url "Web gates" "${WEB_BASE}/gates"
  check_url "Web diagnostics" "${WEB_BASE}/diagnostics" "Diagnostics Console"
  check_url "Web API coverage page" "${WEB_BASE}/api-coverage" "API Coverage Verification"
  check_url "Web assets" "${WEB_BASE}/assets" "Asset Catalog"
  local asset_id
  asset_id="$(sample_asset_id)"
  if [[ -n "${asset_id}" ]]; then
    check_url "Web asset detail" "${WEB_BASE}/assets/${asset_id}" "${asset_id}"
  fi
  check_url "Web contributions" "${WEB_BASE}/contributions" "Contribution Ledger"
  check_url "Web contributors" "${WEB_BASE}/contributors" "Contributors"
  local contributor_id
  contributor_id="$(sample_contributor_id)"
  if [[ -n "${contributor_id}" ]]; then
    check_url \
      "Web contributor portfolio" \
      "${WEB_BASE}/contributors/${contributor_id}/portfolio" \
      "Loading portfolio for"
    local contributor_idea_id
    contributor_idea_id="$(sample_contributor_idea_id "${contributor_id}")"
    if [[ -n "${contributor_idea_id}" ]]; then
      check_url \
        "Web contributor portfolio idea detail" \
        "${WEB_BASE}/contributors/${contributor_id}/portfolio/ideas/${contributor_idea_id}" \
        "Loading"
    fi
    local contributor_stake_id
    contributor_stake_id="$(sample_contributor_stake_id "${contributor_id}")"
    if [[ -n "${contributor_stake_id}" ]]; then
      check_url \
        "Web contributor portfolio stake detail" \
        "${WEB_BASE}/contributors/${contributor_id}/portfolio/stakes/${contributor_stake_id}" \
        "Loading stake detail"
    fi
    local contributor_task_id
    contributor_task_id="$(sample_contributor_task_id "${contributor_id}")"
    if [[ -n "${contributor_task_id}" ]]; then
      check_url \
        "Web contributor portfolio task detail" \
        "${WEB_BASE}/contributors/${contributor_id}/portfolio/tasks/${contributor_task_id}" \
        "Loading"
    fi
  fi
  check_url "Web contribute" "${WEB_BASE}/contribute"
  check_url "Web API health page" "${WEB_BASE}/api-health"
}

parse_args "$@"
ADMIN_KEY="$(resolve_admin_key)"
configure_ports
maybe_dump_thread_ports

echo "Using repo root: ${ROOT_DIR}"
echo "Using API base: ${API_BASE}"
echo "Using web base: ${WEB_BASE}"
echo "Using API_URL: ${API_URL}"
echo "Using DB_URL: ${DB_URL}"
if [[ -n "${THREAD_RUNTIME_KEY:-}" ]]; then
  echo "Thread runtime key: ${THREAD_RUNTIME_KEY}"
fi

if api_ready && web_ready; then
  echo "Local services already running; performing route checks only."
elif (( START_SERVERS == 1 )); then
  start_api_if_needed
  start_web_if_needed
elif (( AUTO_HEAL == 1 )); then
  echo "Services are not fully ready; auto-heal enabled, starting missing services."
  start_api_if_needed
  start_web_if_needed
else
  echo "Services are not fully ready yet."
  echo "Run: THREAD_RUNTIME_START_SERVERS=1 ./scripts/verify_worktree_local_web.sh"
  echo "or: ./scripts/verify_worktree_local_web.sh --start"
  echo "Current service status:"
  echo "  API: $(if api_ready; then echo READY; else echo NOT READY; fi)"
  echo "  Web: $(if web_ready; then echo READY; else echo NOT READY; fi)"
  exit 1
fi

run_validations
echo
echo "Local worktree web validation passed."
