#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_DIR="${ROOT_DIR}/api"
SMOKE_SCRIPT="${API_DIR}/scripts/smoke_test.sh"
LOG_DIR="${THREAD_RUNTIME_LOG_DIR:-${ROOT_DIR}/.thread-runtime}"
API_HOST="${THREAD_RUNTIME_API_HOST:-127.0.0.1}"
API_PORT="${THREAD_RUNTIME_API_PORT:-18000}"
API_BASE="${THREAD_RUNTIME_API_BASE:-http://${API_HOST}:${API_PORT}}"

API_PID=""

require() {
  local name=$1
  if ! command -v "$name" >/dev/null 2>&1; then
    echo "error: required command '$name' is not installed" >&2
    exit 1
  fi
}

log() {
  printf '[%s] %s\n' "$(date '+%H:%M:%S')" "$*"
}

select_python() {
  local candidate
  local python_bin
  for candidate in "${API_DIR}/.venv/bin/python" "${API_DIR}/.venv/bin/python3" "$(command -v python3 || true)" "$(command -v python || true)"; do
    if [[ -n "${candidate}" && -x "${candidate}" ]]; then
      if "${candidate}" -c "import fastapi, uvicorn" >/dev/null 2>&1; then
        printf '%s\n' "${candidate}"
        return 0
      fi
    fi
  done
  return 1
}

cleanup() {
  local rc=$?
  if [[ -n "${API_PID}" ]]; then
    kill "${API_PID}" >/dev/null 2>&1 || true
    wait "${API_PID}" >/dev/null 2>&1 || true
  fi
  return "$rc"
}

api_is_healthy() {
  local code
  code="$(curl -sS -o /dev/null -w "%{http_code}" "${API_BASE}/api/health" || true)"
  [[ "${code}" =~ ^2[0-9][0-9]$ ]]
}

wait_for_api() {
  local elapsed=0
  local timeout=60
  while ((elapsed < timeout)); do
    if api_is_healthy; then
      return 0
    fi
    sleep 2
    elapsed=$((elapsed + 2))
  done
  echo "error: API did not become healthy at ${API_BASE}/api/health"
  return 1
}

start_api() {
  local python_bin
  python_bin="$(select_python)" || {
    echo "error: no python interpreter with fastapi+uvicorn available for API startup"
    echo "Hint: install deps in api/.venv and retry."
    return 1
  }

  mkdir -p "$LOG_DIR"
  local log_file="${LOG_DIR}/thread-runtime-api.log"
  log "Starting API on ${API_BASE}"
  (
    cd "$API_DIR"
    AGENT_TASKS_PERSIST=0 RUNTIME_TELEMETRY_ENABLED=0 "${python_bin}" -m uvicorn app.main:app --host "${API_HOST}" --port "${API_PORT}"
  ) >"$log_file" 2>&1 &
  API_PID=$!
  trap cleanup EXIT
  wait_for_api
  log "API started (pid ${API_PID})"
}

run_e2e_smoke() {
  log "Running API smoke flow"
  bash "${SMOKE_SCRIPT}" "${API_BASE}"
  log "API smoke flow passed"
}

cmd_check() {
  require curl
  require bash
  require sed
  if [[ ! -f "${SMOKE_SCRIPT}" ]]; then
    echo "error: missing ${SMOKE_SCRIPT}" >&2
    exit 1
  fi
  if [[ ! -f "${API_DIR}/app/main.py" ]]; then
    echo "error: missing FastAPI entrypoint ${API_DIR}/app/main.py" >&2
    exit 1
  fi
  echo "ok: thread runtime shell dependencies are available"
}

cmd_run_e2e() {
  trap cleanup EXIT
  if api_is_healthy; then
    log "Using existing API at ${API_BASE}"
    run_e2e_smoke
    return
  fi

  start_api
  run_e2e_smoke
}

cmd_smoke() {
  cmd_run_e2e
}

usage() {
  cat <<'USAGE'
Usage:
  ./scripts/thread-runtime.sh <command>

Commands:
  check
    Validate thread runtime shell prerequisites for local checks.

  run-e2e
    Run Coherence project e2e smoke flow using api/scripts/smoke_test.sh.

  smoke
    Alias for run-e2e.
USAGE
}

COMMAND="${1:-help}"
case "$COMMAND" in
  check)
    cmd_check
    ;;
  run-e2e)
    cmd_run_e2e
    ;;
  smoke)
    cmd_smoke
    ;;
  help|--help|-h)
    usage
    ;;
  *)
    usage
    echo
    echo "error: unknown command '$COMMAND'" >&2
    exit 1
    ;;
esac
