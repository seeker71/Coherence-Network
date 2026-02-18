#!/usr/bin/env bash
set -euo pipefail

API_URL="${REMOTE_OPS_API_URL:-https://coherence-network-production.up.railway.app}"
WEB_URL="${REMOTE_OPS_WEB_URL:-https://coherence-web-production.up.railway.app}"
EXEC_TOKEN="${REMOTE_OPS_EXEC_TOKEN:-}"
TASK_TYPE="${REMOTE_OPS_TASK_TYPE:-impl}"
RUN_EXEC="${REMOTE_OPS_RUN_EXEC:-0}"
CURL_TIMEOUT="${REMOTE_OPS_CURL_TIMEOUT:-20}"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

HAS_JQ=0
if command -v jq >/dev/null 2>&1; then
  HAS_JQ=1
fi

log() {
  echo "[$(date -u +%H:%M:%S)] $*"
}

require_2xx() {
  local name="$1"
  local status="$2"
  local body_file="$3"
  if [[ "$status" -ge 200 && "$status" -lt 400 ]]; then
    log "PASS: ${name} (${status})"
    return 0
  fi

  log "FAIL: ${name} (${status})"
  if [[ -f "$body_file" ]]; then
    log "body preview: $(head -c 240 "$body_file")"
  fi
  return 1
}

http_call() {
  local method="$1"
  local url="$2"
  local out_file="$3"
  shift 3
  local response
  response="$(curl -sS -X "$method" "$@" \
    --max-time "$CURL_TIMEOUT" \
    --connect-timeout 5 \
    -o "$out_file" \
    -w '\n%{http_code}' \
    "$url" || true)"

  local status
  status="$(printf '%s' "$response" | tail -n 1 | tr -cd '0-9')"
  if [[ -z "$status" ]]; then
    echo "000"
    return
  fi
  echo "$status"
}

check_endpoint() {
  local name="$1"
  local url="$2"
  local out_file="$3"
  local method="GET"
  shift 3
  if (( $# >= 1 )); then
    method="$1"
    shift
  fi
  local status
  status="$(http_call "$method" "$url" "$out_file" "$@")"
  require_2xx "$name" "$status" "$out_file"
  return "$?"
}

extract_task_id() {
  local file="$1"
  if [[ "$HAS_JQ" == "1" ]]; then
    jq -r '.id // empty' "$file"
  else
    grep -o '"id"[[:space:]]*:[[:space:]]*"[^"]*"' "$file" | head -n 1 | sed -E 's/.*"id"[[:space:]]*:[[:space:]]*"([^"]*)".*/\1/'
  fi
}

extract_task_status() {
  local file="$1"
  if [[ "$HAS_JQ" == "1" ]]; then
    jq -r '.status // empty' "$file"
  else
    grep -o '"status"[[:space:]]*:[[:space:]]*"[^"]*"' "$file" | head -n 1 | sed -E 's/.*"status"[[:space:]]*:[[:space:]]*"([^"]*)".*/\1/'
  fi
}

log "Remote Ops smoke check start"
log "Target API: ${API_URL}"
log "Target Web: ${WEB_URL}"
if [[ -n "$EXEC_TOKEN" ]]; then
  log "Execute token: provided"
else
  log "Execute token: not set (set REMOTE_OPS_EXEC_TOKEN to exercise dispatch)"
fi
log ""

fail=0

check_endpoint "API health" "${API_URL%/}/api/health" "$TMP_DIR/health.json"
fail=$((fail + $?))

if [[ -f "$TMP_DIR/health.json" ]] && [[ "$HAS_JQ" == "1" ]]; then
  HEALTH_STATUS="$(jq -r '.status // "unknown"' "$TMP_DIR/health.json")"
  log "Health payload status: ${HEALTH_STATUS}"
fi

check_endpoint "Public deploy contract" "${API_URL%/}/api/gates/public-deploy-contract" "$TMP_DIR/deploy_contract.json"
fail=$((fail + $?))

check_endpoint "Pipeline status" "${API_URL%/}/api/agent/pipeline-status" "$TMP_DIR/pipeline.json"
fail=$((fail + $?))

check_endpoint "Pending tasks window" "${API_URL%/}/api/agent/tasks?status=pending&limit=20" "$TMP_DIR/pending.json"
fail=$((fail + $?))

if [[ "$HAS_JQ" == "1" ]]; then
  if [[ -f "$TMP_DIR/pending.json" ]]; then
    PENDING_TOTAL="$(jq -r '.total // 0' "$TMP_DIR/pending.json")"
    log "Pending tasks total: ${PENDING_TOTAL}"
  fi
fi

check_endpoint "Web health proxy" "${WEB_URL%/}/api/health-proxy" "$TMP_DIR/health_proxy.json"
fail=$((fail + $?))

check_endpoint "Web /remote-ops page" "${WEB_URL%/}/remote-ops" "$TMP_DIR/remote_ops_page.html" "GET"
fail=$((fail + $?)

if [[ "${RUN_EXEC}" == "1" ]]; then
  log ""
  log "Smoke execution enabled; creating a non-destructive queue item"
  cat > "$TMP_DIR/new_task.json" <<EOF
{
  "direction": "Remote ops smoke check: verify execute pipeline after deploy",
  "task_type": "${TASK_TYPE}",
  "context": {
    "executor": "remote-ops-smoke",
    "model_override": "openrouter/free"
  }
}
EOF

  task_payload="$TMP_DIR/task_create.json"
  status="$(http_call POST "${API_URL%/}/api/agent/tasks" "$task_payload" \
    -H "Content-Type: application/json" \
    --data-binary "@$TMP_DIR/new_task.json")"
  if require_2xx "Create smoke task" "$status" "$task_payload"; then
    task_id="$(extract_task_id "$task_payload")"
    if [[ -n "$task_id" ]]; then
      log "Created task: ${task_id}"
      if [[ -n "$EXEC_TOKEN" ]]; then
        log "Dispatching task via pickup-and-execute"
        status="$(http_call POST "${API_URL%/}/api/agent/tasks/pickup-and-execute?task_id=${task_id}&task_type=${TASK_TYPE}&force_paid_providers=true" "$TMP_DIR/task_execute.json" \
          -H "Content-Type: application/json" \
          -H "X-Agent-Execute-Token: ${EXEC_TOKEN}")"
        if require_2xx "Dispatch via pickup-and-execute" "$status" "$TMP_DIR/task_execute.json"; then
          log "Pickup+execute requested for ${task_id}"
        else
          fail=$((fail + 1))
        fi

        sleep 1
        check_endpoint "Task readback" "${API_URL%/}/api/agent/tasks/${task_id}" "$TMP_DIR/task_readback.json"
        task_status="$(extract_task_status "$TMP_DIR/task_readback.json")"
        log "Task readback status: ${task_status:-unknown}"
      else
        log "No execute token provided. Testing whether execute is currently protected."
        status="$(http_call POST "${API_URL%/}/api/agent/tasks/pickup-and-execute?task_id=${task_id}&task_type=${TASK_TYPE}&force_paid_providers=true" "$TMP_DIR/task_execute_unauth.json" \
          -H "Content-Type: application/json")"
        if [[ "$status" == "401" || "$status" == "403" ]]; then
          log "Execute endpoint is token-protected (${status}) as expected."
        elif require_2xx "Dispatch via pickup-and-execute without token" "$status" "$TMP_DIR/task_execute_unauth.json"; then
          log "Pickup+execute accepted without token."
        else
          fail=$((fail + 1))
        fi
      fi
    else
      log "WARN: Could not parse task id"
      fail=$((fail + 1))
    fi
  else
    fail=$((fail + 1))
  fi
else
  log "RUN_EXEC=${RUN_EXEC}; skipping live dispatch path."
fi

log ""
if [[ "$fail" -eq 0 ]]; then
  log "Remote Ops smoke check passed."
  exit 0
fi

log "Remote Ops smoke check failed (fail count: ${fail})."
exit 1
