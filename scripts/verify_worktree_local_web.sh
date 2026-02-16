#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_DIR="${ROOT_DIR}/api"
WEB_DIR="${ROOT_DIR}/web"
TMP_DIR="$(mktemp -d)"
NPM_CACHE="${NPM_CACHE:-${ROOT_DIR}/.npm}"
API_PORT="${API_PORT:-18000}"
WEB_PORT="${WEB_PORT:-3100}"
API_BASE="http://127.0.0.1:${API_PORT}"
WEB_BASE="http://127.0.0.1:${WEB_PORT}"
API_LOG="${TMP_DIR}/api.log"
WEB_LOG="${TMP_DIR}/web.log"
API_PID=""
WEB_PID=""

select_python() {
  local candidate
  for candidate in "${API_DIR}/.venv/bin/python" "$(command -v python3.11 || true)" "$(command -v python3 || true)"; do
    if [[ -n "${candidate}" && -x "${candidate}" ]]; then
      if "${candidate}" -c "import fastapi, uvicorn" >/dev/null 2>&1; then
        echo "${candidate}"
        return 0
      fi
    fi
  done
  return 1
}

cleanup() {
  local exit_code=$?
  set +e
  if [[ -n "${WEB_PID}" ]]; then
    kill "${WEB_PID}" >/dev/null 2>&1 || true
    wait "${WEB_PID}" >/dev/null 2>&1 || true
  fi
  if [[ -n "${API_PID}" ]]; then
    kill "${API_PID}" >/dev/null 2>&1 || true
    wait "${API_PID}" >/dev/null 2>&1 || true
  fi
  if [[ "${exit_code}" -ne 0 ]]; then
    echo
    echo "Local worktree validation failed. API log tail:"
    tail -n 80 "${API_LOG}" 2>/dev/null || true
    echo
    echo "Web log tail:"
    tail -n 80 "${WEB_LOG}" 2>/dev/null || true
  fi
  rm -rf "${TMP_DIR}"
}
trap cleanup EXIT

check_port_free() {
  local port="$1"
  if lsof -iTCP:"${port}" -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "Port ${port} is already in use. Set API_PORT/WEB_PORT to free ports."
    exit 1
  fi
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

PYTHON_BIN="$(select_python || true)"
if [[ -z "${PYTHON_BIN}" ]]; then
  echo "Could not find a Python interpreter with fastapi+uvicorn available."
  echo "Create api/.venv or install dependencies for python3.11."
  exit 1
fi

if [[ ! -f "${WEB_DIR}/package.json" ]]; then
  echo "Missing web/package.json at ${WEB_DIR}"
  exit 1
fi

check_port_free "${API_PORT}"
check_port_free "${WEB_PORT}"

echo "Using repo root: ${ROOT_DIR}"
echo "Using Python: ${PYTHON_BIN}"
echo "Using API base: ${API_BASE}"
echo "Using web base: ${WEB_BASE}"
echo "Using npm cache: ${NPM_CACHE}"

pushd "${WEB_DIR}" >/dev/null
if [[ ! -d node_modules ]]; then
  echo "Installing web dependencies (node_modules missing)..."
  npm_config_cache="${NPM_CACHE}" npm ci
fi
echo "Building web app..."
NEXT_PUBLIC_API_URL="${API_BASE}" npm_config_cache="${NPM_CACHE}" npm run build
popd >/dev/null

echo "Starting API..."
(
  cd "${API_DIR}"
  AGENT_TASKS_PERSIST=0 RUNTIME_TELEMETRY_ENABLED=0 "${PYTHON_BIN}" -m uvicorn app.main:app --host 127.0.0.1 --port "${API_PORT}"
) >"${API_LOG}" 2>&1 &
API_PID=$!
wait_for_url "API health" "${API_BASE}/api/health" 60

echo "Starting web..."
(
  cd "${WEB_DIR}"
  NEXT_PUBLIC_API_URL="${API_BASE}" npm run start -- --hostname 127.0.0.1 --port "${WEB_PORT}"
) >"${WEB_LOG}" 2>&1 &
WEB_PID=$!
wait_for_url "web root" "${WEB_BASE}/" 60

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

echo
echo "Local worktree web validation passed."
