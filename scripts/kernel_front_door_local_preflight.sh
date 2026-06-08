#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_DIR="${ROOT_DIR}/api"
KERNEL_DIR="${ROOT_DIR}/form/form-kernel-rust"
KERNEL_BIN="${KERNEL_DIR}/target/release/form-kernel-rust"
ROUTES_FILE="${ROOT_DIR}/deploy/kernel-router/production-routes.fk"
STDLIB_DIR="${ROOT_DIR}/form/form-stdlib"
API_PORT="${API_PORT:-18180}"
ROUTER_PORT="${ROUTER_PORT:-18181}"
API_BASE="http://127.0.0.1:${API_PORT}"
ROUTER_BASE="http://127.0.0.1:${ROUTER_PORT}"
TMP_DIR="$(mktemp -d)"
API_PID=""
ROUTER_PID=""

cleanup() {
  if [[ -n "${ROUTER_PID}" ]] && kill -0 "${ROUTER_PID}" >/dev/null 2>&1; then
    kill "${ROUTER_PID}" >/dev/null 2>&1 || true
    wait "${ROUTER_PID}" >/dev/null 2>&1 || true
  fi
  if [[ -n "${API_PID}" ]] && kill -0 "${API_PID}" >/dev/null 2>&1; then
    kill "${API_PID}" >/dev/null 2>&1 || true
    wait "${API_PID}" >/dev/null 2>&1 || true
  fi
  rm -rf "${TMP_DIR}"
}
trap cleanup EXIT

need() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "missing required command: $1" >&2
    exit 2
  fi
}

need cargo
need curl
need lsof

select_python() {
  local candidate
  for candidate in "${API_DIR}/.venv/bin/python" "${API_DIR}/.venv/bin/python3" "$(command -v python3 || true)"; do
    if [[ -n "${candidate}" && -x "${candidate}" ]]; then
      if "${candidate}" -c "import fastapi, uvicorn" >/dev/null 2>&1; then
        echo "${candidate}"
        return 0
      fi
    fi
  done
  return 1
}

PYTHON_BIN="$(select_python || true)"
if [[ -z "${PYTHON_BIN}" ]]; then
  echo "could not find a Python with fastapi and uvicorn installed" >&2
  exit 2
fi

port_must_be_free() {
  local port="$1"
  if lsof -tiTCP:"${port}" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "port ${port} is already in use; choose API_PORT/ROUTER_PORT or stop the listener" >&2
    exit 2
  fi
}

wait_for_http() {
  local url="$1"
  local attempts="${2:-60}"
  local code=""
  for _ in $(seq 1 "${attempts}"); do
    code="$(curl -s -o /dev/null -w "%{http_code}" "${url}" || true)"
    if [[ "${code}" =~ ^2[0-9][0-9]$ ]]; then
      return 0
    fi
    sleep 1
  done
  echo "timed out waiting for ${url}; last status=${code:-none}" >&2
  return 1
}

header_value() {
  local headers_file="$1"
  local key="$2"
  awk -v key="${key}" 'tolower($1)==tolower(key) { $1=""; sub(/^ /,""); print }' \
    "${headers_file}" | tr -d '\r' | tail -1
}

json_value_contract() {
  "${PYTHON_BIN}" - "$1" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as fh:
    obj = json.load(fh)
obj.pop("runtime", None)
print(json.dumps(obj, separators=(",", ":")))
PY
}

check_image_packaging() {
  local dockerfile="${ROOT_DIR}/Dockerfile.kernel-router"
  grep -q 'STDLIB_DIR=/app/form/form-stdlib' "${dockerfile}"
  grep -q 'COPY deploy/kernel-router/shadow-routes.fk /routes/shadow-routes.fk' "${dockerfile}"
  grep -q 'COPY deploy/kernel-router/production-routes.fk /routes/production-routes.fk' "${dockerfile}"
  grep -q 'COPY deploy/kernel-router/production-routes-data.json /routes/production-routes-data.json' "${dockerfile}"
  echo "PASS image-packaging route manifests and stdlib default are baked"
}

check_fanout_exact() {
  local name="$1"
  local route_path="$2"
  local direct_body="${TMP_DIR}/${name}.direct.body"
  local router_body="${TMP_DIR}/${name}.router.body"
  local router_headers="${TMP_DIR}/${name}.router.headers"
  local direct_code router_code router

  direct_code="$(curl -s -o "${direct_body}" -w "%{http_code}" "${API_BASE}${route_path}")"
  router_code="$(curl -s -D "${router_headers}" -o "${router_body}" -w "%{http_code}" "${ROUTER_BASE}${route_path}")"
  router="$(header_value "${router_headers}" "x-form-router:")"

  if ! cmp -s "${direct_body}" "${router_body}"; then
    echo "FAIL fanout-exact ${name}: body mismatch for ${route_path}" >&2
    exit 1
  fi
  if [[ "${direct_code}" != "${router_code}" || "${router}" != "fanout-python" ]]; then
    echo "FAIL fanout-exact ${name}: direct=${direct_code} router=${router_code} x-form-router=${router}" >&2
    exit 1
  fi
  echo "PASS fanout-exact ${name} status=${router_code} router=${router} bytes=$(wc -c < "${router_body}" | tr -d ' ')"
}

check_native_value_contract() {
  local name="$1"
  local route_path="$2"
  local direct_body="${TMP_DIR}/${name}.direct.body"
  local router_body="${TMP_DIR}/${name}.router.body"
  local router_headers="${TMP_DIR}/${name}.router.headers"
  local direct_code router_code router direct_contract router_contract

  direct_code="$(curl -s -o "${direct_body}" -w "%{http_code}" "${API_BASE}${route_path}")"
  router_code="$(curl -s -D "${router_headers}" -o "${router_body}" -w "%{http_code}" "${ROUTER_BASE}${route_path}")"
  router="$(header_value "${router_headers}" "x-form-router:")"
  direct_contract="$(json_value_contract "${direct_body}")"
  router_contract="$(json_value_contract "${router_body}")"

  if [[ "${direct_code}" != "200" || "${router_code}" != "200" || "${router}" != "native-kernel" ]]; then
    echo "FAIL native-value ${name}: direct=${direct_code} router=${router_code} x-form-router=${router}" >&2
    exit 1
  fi
  if [[ "${direct_contract}" != "${router_contract}" ]]; then
    echo "FAIL native-value ${name}: value contract mismatch for ${route_path}" >&2
    exit 1
  fi
  echo "PASS native-value ${name} status=${router_code} router=${router} bytes=$(wc -c < "${router_body}" | tr -d ' ')"
}

check_attention_metrics() {
  local body="${TMP_DIR}/attention.body"
  local headers="${TMP_DIR}/attention.headers"
  local code router
  code="$(curl -s -D "${headers}" -o "${body}" -w "%{http_code}" "${ROUTER_BASE}/api/attention/kernel-runtime")"
  router="$(header_value "${headers}" "x-form-router:")"
  if [[ "${code}" != "200" || "${router}" != "native-kernel" ]]; then
    echo "FAIL native-attention: status=${code} x-form-router=${router}" >&2
    exit 1
  fi
  "${PYTHON_BIN}" - "${body}" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as fh:
    measurements = json.load(fh)["measurements"]
for key in ("choice_attempts", "choice_successes", "choice_failures", "total_requests", "native_requests", "fanout_requests"):
    if key not in measurements:
        raise SystemExit(f"missing measurement {key}")
if measurements["fanout_requests"] < 2:
    raise SystemExit(f"fanout_requests did not include fan-out probes: {measurements['fanout_requests']}")
if measurements["native_requests"] < 1:
    raise SystemExit(f"native_requests did not include native probe: {measurements['native_requests']}")
if measurements["total_requests"] < 3:
    raise SystemExit(f"total_requests did not include prior probes: {measurements['total_requests']}")
if measurements["choice_attempts"] <= 0 or measurements["choice_failures"] <= 0:
    raise SystemExit("choice counters did not move")
print(
    "total_requests={total_requests} native_requests={native_requests} "
    "fanout_requests={fanout_requests} choice_attempts={choice_attempts} "
    "choice_successes={choice_successes} choice_failures={choice_failures}".format(**measurements)
)
PY
  echo "PASS native-attention status=${code} router=${router} bytes=$(wc -c < "${body}" | tr -d ' ')"
}

port_must_be_free "${API_PORT}"
port_must_be_free "${ROUTER_PORT}"

echo "kernel-front-door-local-preflight: building release kernel"
(cd "${KERNEL_DIR}" && cargo build --release --bin form-kernel-rust)

echo "kernel-front-door-local-preflight: checking route manifests"
"${ROOT_DIR}/scripts/check_route_manifests.sh"
check_image_packaging

echo "kernel-front-door-local-preflight: starting API ${API_BASE}"
(
  cd "${API_DIR}"
  COH_ENV=dev "${PYTHON_BIN}" -m uvicorn app.main:app --host 127.0.0.1 --port "${API_PORT}" --log-level warning
) >"${TMP_DIR}/api.log" 2>&1 &
API_PID="$!"
wait_for_http "${API_BASE}/api/health" 90

echo "kernel-front-door-local-preflight: starting kernel-router ${ROUTER_BASE}"
(
  cd "${KERNEL_DIR}"
  "${KERNEL_BIN}" serve \
    --host 127.0.0.1 \
    --port "${ROUTER_PORT}" \
    --workers 2 \
    --routes "${ROUTES_FILE}" \
    --stdlib "${STDLIB_DIR}" \
    --upstream "${API_BASE}"
) >"${TMP_DIR}/router.log" 2>&1 &
ROUTER_PID="$!"
wait_for_http "${ROUTER_BASE}/api/health" 90

check_fanout_exact version /api/version
check_fanout_exact health /api/health
check_native_value_contract coherence_weight '/api/utils/coherence_weight?values=10,20,30&threshold=15'
check_attention_metrics

echo "PASS: local kernel front-door preflight"
