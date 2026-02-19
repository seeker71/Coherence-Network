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
SHOW_PORTS=0

THREAD_RUNTIME_HELPER="${ROOT_DIR}/scripts/thread_runtime_ports.sh"
if [[ -f "${THREAD_RUNTIME_HELPER}" ]]; then
  # shellcheck disable=SC1091
  source "${THREAD_RUNTIME_HELPER}"
fi

usage() {
  cat <<'USAGE'
Usage:
  ./scripts/verify_worktree_local_web.sh [--start|--thread-ports]

Options:
  --start
      Start missing API/web services and then validate.
  --thread-ports
      Print thread-runtime port usage snapshot before validation.

Environment:
  THREAD_RUNTIME_START_SERVERS=1
      Same as --start.
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

check_url() {
  local name="$1"
  local url="$2"
  local required_text="${3:-}"
  local headers_file="${TMP_DIR}/$(echo "${name}" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '_').headers"
  local body_file="${TMP_DIR}/$(echo "${name}" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '_').body"

  echo "==> ${name}: ${url}"
  curl -sS -L -D "${headers_file}" -o "${body_file}" "${url}" >/dev/null

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
  (
    cd "${API_DIR}"
    AGENT_TASKS_PERSIST=0 RUNTIME_TELEMETRY_ENABLED=0 "${python_bin}" -m uvicorn app.main:app --host 127.0.0.1 --port "${API_PORT}"
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
  NEXT_PUBLIC_API_URL="${API_BASE}" npm run build
  (
    cd "${WEB_DIR}"
    NEXT_PUBLIC_API_URL="${API_BASE}" npm run start -- --hostname 127.0.0.1 --port "${WEB_PORT}"
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
  check_url "API system lineage" "${API_BASE}/api/inventory/system-lineage"
  check_url "API endpoint runtime summary" "${API_BASE}/api/runtime/endpoints/summary"

  check_url "Web root" "${WEB_BASE}/" "/ideas"
  check_url "Web root nav flow" "${WEB_BASE}/" "/flow"
  check_url "Web root nav specs" "${WEB_BASE}/" "/specs"
  check_url "Web root nav tasks" "${WEB_BASE}/" "/tasks"
  check_url "Web root nav contribute" "${WEB_BASE}/" "/contribute"
  check_url "Web root nav gates" "${WEB_BASE}/" "/gates"
  check_url "Web ideas" "${WEB_BASE}/ideas"
  check_url "Web specs" "${WEB_BASE}/specs"
  check_url "Web flow" "${WEB_BASE}/flow"
  check_url "Web tasks" "${WEB_BASE}/tasks"
  check_url "Web gates" "${WEB_BASE}/gates"
  check_url "Web contribute" "${WEB_BASE}/contribute"
  check_url "Web API health page" "${WEB_BASE}/api-health"
}

parse_args "$@"
configure_ports
maybe_dump_thread_ports

echo "Using repo root: ${ROOT_DIR}"
echo "Using API base: ${API_BASE}"
echo "Using web base: ${WEB_BASE}"
if [[ -n "${THREAD_RUNTIME_KEY:-}" ]]; then
  echo "Thread runtime key: ${THREAD_RUNTIME_KEY}"
fi

if api_ready && web_ready; then
  echo "Local services already running; performing route checks only."
elif (( START_SERVERS == 1 )); then
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
