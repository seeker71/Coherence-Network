#!/usr/bin/env bash
set -euo pipefail

API_URL="${1:-${PUBLIC_API_BASE_URL:-}}"
WEB_URL="${2:-${PUBLIC_WEB_BASE_URL:-}}"

if [[ -z "$API_URL" || -z "$WEB_URL" ]]; then
  echo "Usage: ./scripts/verify_web_api_deploy.sh <api_base_url> <web_base_url>"
  echo "Or set PUBLIC_API_BASE_URL and PUBLIC_WEB_BASE_URL."
  exit 2
fi

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT
API_HEALTH_SNAPSHOT_FILE="$TMP_DIR/public_api_health_snapshot.json"

CURL_MAX_TIME="${CURL_MAX_TIME:-25}"
CURL_CONNECT_TIMEOUT="${CURL_CONNECT_TIMEOUT:-5}"
CURL_RETRIES="${CURL_RETRIES:-3}"
CURL_RETRY_SLEEP_SECONDS="${CURL_RETRY_SLEEP_SECONDS:-3}"
# How long to stay patient with a gateway that says "still starting" (502/503/504).
# A fresh deploy can land the verify step mid-restart; the upstream container is
# up but Traefik's connection hasn't re-established yet. Wait for it.
GATEWAY_PATIENCE_SECONDS="${GATEWAY_PATIENCE_SECONDS:-90}"
GATEWAY_PATIENCE_INTERVAL="${GATEWAY_PATIENCE_INTERVAL:-5}"

run_with_retries() {
  local attempts="$1"
  local sleep_seconds="$2"
  shift 2
  local attempt=1
  local rc=0
  while (( attempt <= attempts )); do
    if "$@"; then
      return 0
    fi
    rc=$?
    if (( attempt == attempts )); then
      return "$rc"
    fi
    echo "WARN: request attempt ${attempt}/${attempts} failed; retrying in ${sleep_seconds}s..."
    sleep "$sleep_seconds"
    attempt=$((attempt + 1))
  done
  return "$rc"
}


check_url() {
  local name="$1"
  local url="$2"
  local required_text="${3:-}"
  local snapshot_file="${4:-}"
  local slug
  slug="$(echo "$name" | tr "[:upper:]" "[:lower:]" | tr -cs "a-z0-9" "_")"
  local headers_file="$TMP_DIR/${slug}.headers.txt"
  local body_file="$TMP_DIR/${slug}.body.txt"

  echo
  echo "==> ${name}: ${url}"

  # Patient retry for fresh-deploy gateway states. 502/503/504 from
  # Cloudflare/Traefik right after a rollout usually mean the upstream
  # container is up but the gateway's connection is still re-establishing.
  # Wait for it rather than reporting failure on the first probe.
  local deadline=$(( $(date +%s) + GATEWAY_PATIENCE_SECONDS ))
  local status=""
  local server=""
  while :; do
    if ! run_with_retries "$CURL_RETRIES" "$CURL_RETRY_SLEEP_SECONDS" curl -sS -L -D "$headers_file" -o "$body_file" \
      --max-time "$CURL_MAX_TIME" \
      --connect-timeout "$CURL_CONNECT_TIMEOUT" \
      "$url" >/dev/null; then
      if (( $(date +%s) < deadline )); then
        echo "WARN: curl request error; waiting ${GATEWAY_PATIENCE_INTERVAL}s for the gateway..."
        sleep "$GATEWAY_PATIENCE_INTERVAL"
        continue
      fi
      echo "FAIL: request error"
      sed -n '1,12p' "$headers_file" 2>/dev/null || true
      return 1
    fi

    status="$(awk 'toupper($1) ~ /^HTTP\// { code=$2 } END { print code }' "$headers_file")"
    server="$(awk 'tolower($1) == "server:" { print $2 }' "$headers_file" | tail -n 1 | tr -d '\r')"
    if [[ -z "${status}" ]]; then
      echo "FAIL: could not read HTTP status"
      return 1
    fi

    # Patient retry covers the brief window right after a rollout where the
    # gateway is reconnecting to a fresh upstream. 502/503/504 are the
    # expected "backend unreachable" signals, but 404 also appears briefly
    # when Traefik has torn down the old route and not yet registered the
    # new one — the catch-all handler returns 404 while the routing table
    # is mid-update. Treating 404 as a transient during the rollout window
    # lets the body finish its own breath before the verify script reports.
    case "$status" in
      502|503|504|404)
        if (( $(date +%s) < deadline )); then
          echo "WARN: rollout status ${status}; waiting ${GATEWAY_PATIENCE_INTERVAL}s for the gateway to settle..."
          sleep "$GATEWAY_PATIENCE_INTERVAL"
          continue
        fi
        ;;
    esac
    break
  done

  echo "HTTP status: ${status}"
  [[ -n "$server" ]] && echo "Server: ${server}"

  if [[ "$status" -ge 200 && "$status" -lt 400 ]]; then
    if [[ -n "$required_text" ]] && ! grep -Fq "$required_text" "$body_file"; then
      echo "FAIL: expected text not found: $required_text"
      return 1
    fi
    if [[ -n "$snapshot_file" ]]; then
      cp "$body_file" "$snapshot_file"
    fi
    echo "PASS"
    return 0
  fi

  echo "FAIL: non-success HTTP status"
  echo "Response preview:"
  head -c 250 "$body_file" || true
  echo

  if [[ "$status" == "404" ]]; then
    echo "Hint: web route not found. Verify the public web deployment and route config."
  fi

  return 1
}


check_cors() {
  local api_health_url="$1"
  local web_origin="$2"
  local headers_file="$TMP_DIR/cors_headers.txt"

  echo
  echo "==> CORS check: ${api_health_url} with Origin ${web_origin}"

  if ! run_with_retries "$CURL_RETRIES" "$CURL_RETRY_SLEEP_SECONDS" curl -sS -D "$headers_file" -o /dev/null \
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


fail=0
check_url "Public API health" "${API_URL%/}/api/health" "" "$API_HEALTH_SNAPSHOT_FILE" || fail=1
check_url "Public web root" "${WEB_URL%/}/" || fail=1
check_cors "${API_URL%/}/api/ping" "${WEB_URL%/}" || fail=1

if [[ "$fail" -eq 0 ]]; then
  echo
  echo "Deployment verification passed: public API and web are reachable and CORS is aligned."
else
  echo
  echo "Deployment verification failed: at least one endpoint or CORS check failed."
  exit 1
fi
