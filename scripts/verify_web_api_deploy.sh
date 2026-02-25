#!/usr/bin/env bash
set -euo pipefail

API_URL="${1:-https://coherence-network-production.up.railway.app}"
WEB_URL="${2:-https://coherence-web-production.up.railway.app}"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

CURL_MAX_TIME="${CURL_MAX_TIME:-25}"
CURL_CONNECT_TIMEOUT="${CURL_CONNECT_TIMEOUT:-5}"
VERIFY_REQUIRE_GATES_MAIN_HEAD="${VERIFY_REQUIRE_GATES_MAIN_HEAD:-1}"
VERIFY_REQUIRE_PERSISTENCE_CHECK="${VERIFY_REQUIRE_PERSISTENCE_CHECK:-1}"
VERIFY_REQUIRE_TELEGRAM_ALERTS="${VERIFY_REQUIRE_TELEGRAM_ALERTS:-0}"
VERIFY_REQUIRE_PROVIDER_READINESS="${VERIFY_REQUIRE_PROVIDER_READINESS:-0}"
VERIFY_REQUIRE_API_HEALTH_SHA="${VERIFY_REQUIRE_API_HEALTH_SHA:-0}"

check_url() {
  local name="$1"
  local url="$2"
  local slug
  slug="$(echo "$name" | tr "[:upper:]" "[:lower:]" | tr -cs "a-z0-9" "_")"
  local headers_file="$TMP_DIR/${slug}.headers.txt"
  local body_file="$TMP_DIR/${slug}.body.txt"

  echo
  echo "==> ${name}: ${url}"

  if ! curl -sS -L -D "$headers_file" -o "$body_file" \
    --max-time "$CURL_MAX_TIME" \
    --connect-timeout "$CURL_CONNECT_TIMEOUT" \
    "$url" >/dev/null; then
    echo "FAIL: request error"
    sed -n '1,12p' "$headers_file" 2>/dev/null || true
    return 1
  fi

  local status
  status="$(awk 'toupper($1) ~ /^HTTP\// { code=$2 } END { print code }' "$headers_file")"
  local server
  server="$(awk 'tolower($1) == "server:" { print $2 }' "$headers_file" | tail -n 1 | tr -d '\r')"
  if [[ -z "${status}" ]]; then
    echo "FAIL: could not read HTTP status"
    return 1
  fi

  echo "HTTP status: ${status}"
  [[ -n "$server" ]] && echo "Server: ${server}"

  if [[ "$status" -ge 200 && "$status" -lt 400 ]]; then
    echo "PASS"
    return 0
  fi

  echo "FAIL: non-success HTTP status"
  echo "Response preview:"
  head -c 250 "$body_file" || true
  echo

  if [[ "$status" == "404" ]]; then
    echo "Hint: web route not found. Verify Railway web service deployment and route config."
  fi

  return 1
}

check_cors() {
  local api_health_url="$1"
  local web_origin="$2"
  local headers_file="$TMP_DIR/cors_headers.txt"

  echo
  echo "==> CORS check: ${api_health_url} with Origin ${web_origin}"

  if ! curl -sS -D "$headers_file" -o /dev/null \
    --max-time "$CURL_MAX_TIME" \
    --connect-timeout "$CURL_CONNECT_TIMEOUT" \
    -H "Origin: ${web_origin}" "$api_health_url" >/dev/null; then
    echo "FAIL: request error"
    return 1
  fi

  local status acao
  status="$(awk 'toupper($1) ~ /^HTTP\// { code=$2 } END { print code }' "$headers_file")"
  acao="$(awk 'tolower($1) == "access-control-allow-origin:" { print $2 }' "$headers_file" | tail -n 1 | tr -d '\r')"

  echo "HTTP status: ${status:-unknown}"
  echo "Access-Control-Allow-Origin: ${acao:-<missing>}"

  if [[ "$status" -ge 200 && "$status" -lt 400 ]] && ([[ "$acao" == "*" ]] || [[ "$acao" == "$web_origin" ]]); then
    echo "PASS"
    return 0
  fi

  echo "FAIL: CORS origin is not allowed or health endpoint failed"
  return 1
}

check_persistence_contract() {
  local url="$1"
  local body_file="$TMP_DIR/persistence_contract.body.json"
  local status

  echo
  echo "==> Persistence contract: ${url}"
  status="$(curl -sS -o "$body_file" -w "%{http_code}" \
    --max-time "$CURL_MAX_TIME" \
    --connect-timeout "$CURL_CONNECT_TIMEOUT" \
    "$url" || true)"
  echo "HTTP status: ${status:-unknown}"
  if [[ -z "$status" || "$status" -lt 200 || "$status" -ge 400 ]]; then
    echo "FAIL: persistence contract endpoint unavailable"
    head -c 300 "$body_file" || true
    echo
    return 1
  fi

  if command -v jq >/dev/null 2>&1; then
    local pass required
    pass="$(jq -r '.pass_contract // empty' "$body_file" 2>/dev/null || true)"
    required="$(jq -r '.required // empty' "$body_file" 2>/dev/null || true)"
    echo "required: ${required:-unknown} | pass_contract: ${pass:-unknown}"
    if [[ "$pass" == "true" ]]; then
      echo "PASS"
      return 0
    fi
    echo "FAIL: pass_contract is not true"
    jq '.failures // []' "$body_file" 2>/dev/null || head -c 300 "$body_file" || true
    return 1
  fi

  if grep -q '"pass_contract"[[:space:]]*:[[:space:]]*true' "$body_file"; then
    echo "PASS"
    return 0
  fi
  echo "FAIL: pass_contract is not true"
  head -c 300 "$body_file" || true
  echo
  return 1
}

check_telegram_alert_config() {
  local url="$1"
  local body_file="$TMP_DIR/telegram_diagnostics.body.json"
  local status

  echo
  echo "==> Telegram alert diagnostics: ${url}"
  status="$(curl -sS -o "$body_file" -w "%{http_code}" \
    --max-time "$CURL_MAX_TIME" \
    --connect-timeout "$CURL_CONNECT_TIMEOUT" \
    "$url" || true)"
  echo "HTTP status: ${status:-unknown}"
  if [[ -z "$status" || "$status" -lt 200 || "$status" -ge 400 ]]; then
    echo "FAIL: diagnostics endpoint unavailable"
    head -c 300 "$body_file" || true
    echo
    return 1
  fi

  local has_token chat_ids_count
  if command -v jq >/dev/null 2>&1; then
    has_token="$(jq -r '.config.has_token // false' "$body_file" 2>/dev/null || echo "false")"
    chat_ids_count="$(jq -r '(.config.chat_ids // []) | map(select((. | tostring | length) > 0)) | length' "$body_file" 2>/dev/null || echo "0")"
  else
    has_token="$(grep -q '"has_token"[[:space:]]*:[[:space:]]*true' "$body_file" && echo "true" || echo "false")"
    chat_ids_count="$(grep -o '"chat_ids"[[:space:]]*:[[:space:]]*\\[[^]]*\\]' "$body_file" | grep -o ',' | wc -l | tr -d ' ')"
  fi
  echo "has_token: ${has_token} | chat_ids_count: ${chat_ids_count}"

  if [[ "$has_token" == "true" && "${chat_ids_count:-0}" -gt 0 ]]; then
    echo "PASS"
    return 0
  fi

  echo "FAIL: Telegram alert channel is not configured (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_IDS missing)"
  return 1
}

check_provider_readiness() {
  local url="$1"
  local required="${2:-0}"
  local body_file="$TMP_DIR/provider_readiness.body.json"
  local status

  echo
  echo "==> Provider readiness: ${url} (required=${required})"
  status="$(curl -sS -o "$body_file" -w "%{http_code}" \
    --max-time "$CURL_MAX_TIME" \
    --connect-timeout "$CURL_CONNECT_TIMEOUT" \
    "$url" || true)"
  echo "HTTP status: ${status:-unknown}"

  if [[ -z "$status" || "$status" -lt 200 || "$status" -ge 400 ]]; then
    if [[ "$required" == "1" ]]; then
      echo "FAIL: readiness endpoint unavailable"
      head -c 300 "$body_file" || true
      echo
      return 1
    fi
    echo "WARN: readiness endpoint unavailable (non-blocking)"
    return 0
  fi

  local all_ready blocking_count
  if command -v jq >/dev/null 2>&1; then
    all_ready="$(jq -r 'if has("all_required_ready") then (.all_required_ready | tostring) else "unknown" end' "$body_file" 2>/dev/null || echo "unknown")"
    blocking_count="$(jq -r '(.blocking_issues // []) | length' "$body_file" 2>/dev/null || echo "0")"
  else
    all_ready="$(grep -q '"all_required_ready"[[:space:]]*:[[:space:]]*true' "$body_file" && echo "true" || echo "false")"
    blocking_count="$(grep -o '"blocking_issues"[[:space:]]*:[[:space:]]*\\[[^]]*\\]' "$body_file" | grep -o ',' | wc -l | tr -d ' ')"
  fi
  echo "all_required_ready: ${all_ready} | blocking_issues: ${blocking_count}"

  if [[ "$all_ready" == "true" ]]; then
    echo "PASS"
    return 0
  fi

  if [[ "$required" == "1" ]]; then
    echo "FAIL: required provider readiness is not healthy"
    if command -v jq >/dev/null 2>&1; then
      jq '.blocking_issues // []' "$body_file" 2>/dev/null || true
    else
      head -c 300 "$body_file" || true
      echo
    fi
    return 1
  fi

  echo "WARN: provider readiness has blocking issues (non-blocking)"
  return 0
}

check_api_runtime_sha() {
  local health_url="$1"
  local main_head_url="$2"
  local required="${3:-0}"
  local health_body="$TMP_DIR/api_health_sha.body.json"
  local main_head_body="$TMP_DIR/api_main_head_sha.body.json"
  local health_status main_head_status

  echo
  echo "==> API runtime SHA parity: ${health_url} vs ${main_head_url} (required=${required})"
  health_status="$(curl -sS -o "$health_body" -w "%{http_code}" \
    --max-time "$CURL_MAX_TIME" \
    --connect-timeout "$CURL_CONNECT_TIMEOUT" \
    "$health_url" || true)"
  main_head_status="$(curl -sS -o "$main_head_body" -w "%{http_code}" \
    --max-time "$CURL_MAX_TIME" \
    --connect-timeout "$CURL_CONNECT_TIMEOUT" \
    "$main_head_url" || true)"
  echo "health status: ${health_status:-unknown} | main-head status: ${main_head_status:-unknown}"

  if [[ -z "$health_status" || "$health_status" -lt 200 || "$health_status" -ge 400 ]]; then
    echo "FAIL: api health endpoint unavailable for SHA parity check"
    return 1
  fi
  if [[ -z "$main_head_status" || "$main_head_status" -lt 200 || "$main_head_status" -ge 400 ]]; then
    if [[ "$required" == "1" ]]; then
      echo "FAIL: main-head endpoint unavailable for required SHA parity check"
      return 1
    fi
    echo "WARN: main-head endpoint unavailable (non-blocking SHA parity check)"
    return 0
  fi

  local expected_sha observed_sha
  expected_sha=""
  observed_sha=""
  if command -v jq >/dev/null 2>&1; then
    expected_sha="$(jq -r '.sha // ""' "$main_head_body" 2>/dev/null || true)"
    observed_sha="$(
      jq -r '(.deployed_sha // .updated_at // .commit_sha // .git_sha // "")' "$health_body" 2>/dev/null || true
    )"
  else
    expected_sha="$(grep -o '"sha"[[:space:]]*:[[:space:]]*"[^"]*"' "$main_head_body" | head -n 1 | sed 's/.*"sha"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/')"
    observed_sha="$(grep -o '"deployed_sha"[[:space:]]*:[[:space:]]*"[^"]*"' "$health_body" | head -n 1 | sed 's/.*"deployed_sha"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/')"
  fi
  expected_sha="$(echo "${expected_sha:-}" | tr -d '\r')"
  observed_sha="$(echo "${observed_sha:-}" | tr -d '\r')"
  echo "expected_sha: ${expected_sha:-<missing>}"
  echo "observed_sha: ${observed_sha:-<missing>}"

  if [[ -z "$expected_sha" ]]; then
    if [[ "$required" == "1" ]]; then
      echo "FAIL: expected SHA is missing from main-head response"
      return 1
    fi
    echo "WARN: expected SHA missing from main-head response"
    return 0
  fi

  local observed_normalized
  observed_normalized="$(echo "$observed_sha" | tr '[:upper:]' '[:lower:]')"
  if [[ -z "$observed_sha" || "$observed_normalized" == "unknown" || "$observed_normalized" == "none" || "$observed_normalized" == "n/a" ]]; then
    if [[ "$required" == "1" ]]; then
      echo "FAIL: API health does not expose deployed SHA (required)"
      return 1
    fi
    echo "WARN: API health does not expose deployed SHA (non-blocking)"
    return 0
  fi

  if [[ "$observed_sha" != "$expected_sha" ]]; then
    echo "FAIL: API deployed SHA does not match expected main-head SHA"
    return 1
  fi

  echo "PASS"
  return 0
}

fail=0
check_url "Railway API health" "${API_URL%/}/api/health" || fail=1
if [[ "$VERIFY_REQUIRE_GATES_MAIN_HEAD" == "1" ]]; then
  check_url "Railway gates main head" "${API_URL%/}/api/gates/main-head" || fail=1
else
  echo
  echo "==> Skipping Railway gates main head check (VERIFY_REQUIRE_GATES_MAIN_HEAD=0)"
fi
check_api_runtime_sha \
  "${API_URL%/}/api/health" \
  "${API_URL%/}/api/gates/main-head" \
  "$VERIFY_REQUIRE_API_HEALTH_SHA" || fail=1
if [[ "$VERIFY_REQUIRE_PERSISTENCE_CHECK" == "1" ]]; then
  check_persistence_contract "${API_URL%/}/api/health/persistence" || fail=1
else
  echo
  echo "==> Skipping API persistence contract check (VERIFY_REQUIRE_PERSISTENCE_CHECK=0)"
fi
check_provider_readiness "${API_URL%/}/api/automation/usage/readiness" "$VERIFY_REQUIRE_PROVIDER_READINESS" || fail=1
check_url "Railway web root" "${WEB_URL%/}/" || fail=1
check_url "Railway web gates page" "${WEB_URL%/}/gates" || fail=1
check_url "Railway web API health page" "${WEB_URL%/}/api-health" || fail=1
check_url "Railway web API health proxy" "${WEB_URL%/}/api/health-proxy" || fail=1
check_cors "${API_URL%/}/api/health" "${WEB_URL%/}" || fail=1
if [[ "$VERIFY_REQUIRE_TELEGRAM_ALERTS" == "1" ]]; then
  check_telegram_alert_config "${API_URL%/}/api/agent/telegram/diagnostics" || fail=1
else
  echo
  echo "==> Skipping Telegram alert config gate (VERIFY_REQUIRE_TELEGRAM_ALERTS=0)"
fi

if [[ "$fail" -eq 0 ]]; then
  echo
  echo "Deployment verification passed: Railway API and Railway web are reachable and CORS is aligned."
else
  echo
  echo "Deployment verification failed: at least one endpoint or CORS check failed."
  exit 1
fi
