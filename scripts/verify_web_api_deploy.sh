#!/usr/bin/env bash
set -euo pipefail

API_URL="${1:-https://coherence-network-production.up.railway.app}"
WEB_URL="${2:-https://coherence-web-production.up.railway.app}"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

check_url() {
  local name="$1"
  local url="$2"
  local slug
  slug="$(echo "$name" | tr "[:upper:]" "[:lower:]" | tr -cs "a-z0-9" "_")"
  local headers_file="$TMP_DIR/${slug}.headers.txt"
  local body_file="$TMP_DIR/${slug}.body.txt"

  echo
  echo "==> ${name}: ${url}"

  if ! curl -sS -L -D "$headers_file" -o "$body_file" "$url" >/dev/null; then
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

  if ! curl -sS -D "$headers_file" -o /dev/null -H "Origin: ${web_origin}" "$api_health_url" >/dev/null; then
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
  status="$(curl -sS -o "$body_file" -w "%{http_code}" "$url" || true)"
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

fail=0
check_url "Railway API health" "${API_URL%/}/api/health" || fail=1
check_url "Railway gates main head" "${API_URL%/}/api/gates/main-head" || fail=1
check_persistence_contract "${API_URL%/}/api/health/persistence" || fail=1
check_url "Railway web root" "${WEB_URL%/}/" || fail=1
check_url "Railway web gates page" "${WEB_URL%/}/gates" || fail=1
check_url "Railway web API health page" "${WEB_URL%/}/api-health" || fail=1
check_url "Railway web API health proxy" "${WEB_URL%/}/api/health-proxy" || fail=1
check_cors "${API_URL%/}/api/health" "${WEB_URL%/}" || fail=1

if [[ "$fail" -eq 0 ]]; then
  echo
  echo "Deployment verification passed: Railway API and Railway web are reachable and CORS is aligned."
else
  echo
  echo "Deployment verification failed: at least one endpoint or CORS check failed."
  exit 1
fi
