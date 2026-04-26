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

CURL_MAX_TIME="${CURL_MAX_TIME:-25}"
CURL_CONNECT_TIMEOUT="${CURL_CONNECT_TIMEOUT:-5}"
CURL_RETRIES="${CURL_RETRIES:-3}"
CURL_RETRY_SLEEP_SECONDS="${CURL_RETRY_SLEEP_SECONDS:-3}"
# How long to stay patient with a gateway that says "still starting" (502/503/504).
# A fresh deploy can land the verify step mid-restart; the upstream container is
# up but Traefik's connection hasn't re-established yet. Wait for it.
GATEWAY_PATIENCE_SECONDS="${GATEWAY_PATIENCE_SECONDS:-90}"
GATEWAY_PATIENCE_INTERVAL="${GATEWAY_PATIENCE_INTERVAL:-5}"
VERIFY_REQUIRE_GATES_MAIN_HEAD="${VERIFY_REQUIRE_GATES_MAIN_HEAD:-1}"
VERIFY_REQUIRE_PERSISTENCE_CHECK="${VERIFY_REQUIRE_PERSISTENCE_CHECK:-1}"
VERIFY_REQUIRE_TELEGRAM_ALERTS="${VERIFY_REQUIRE_TELEGRAM_ALERTS:-0}"
VERIFY_REQUIRE_PROVIDER_READINESS="${VERIFY_REQUIRE_PROVIDER_READINESS:-0}"
VERIFY_REQUIRE_API_HEALTH_SHA="${VERIFY_REQUIRE_API_HEALTH_SHA:-0}"
VERIFY_REQUIRE_WEB_HEALTH_PROXY_SHA="${VERIFY_REQUIRE_WEB_HEALTH_PROXY_SHA:-0}"

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

run_with_retries_capture() {
  local attempts="$1"
  local sleep_seconds="$2"
  shift 2
  local attempt=1
  local rc=0
  local output=""
  while (( attempt <= attempts )); do
    if output="$("$@")"; then
      printf "%s" "$output"
      return 0
    fi
    rc=$?
    if (( attempt == attempts )); then
      return "$rc"
    fi
    echo "WARN: request attempt ${attempt}/${attempts} failed; retrying in ${sleep_seconds}s..." >&2
    sleep "$sleep_seconds"
    attempt=$((attempt + 1))
  done
  return "$rc"
}

check_url() {
  local name="$1"
  local url="$2"
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

check_pulse_witness() {
  # The witness at pulse.coherencycoin.com probes every organ every
  # 30s. When it reports overall != "breathing" or has ongoing
  # silences, a surface is broken — and the deploy that just landed
  # probably caused it (or the deploy before this one, if we weren't
  # looking). Previously the verifier only checked /api/health,
  # which missed silent page-level breakage for days. This check
  # closes the loop: a deploy that breaks a probed surface fails
  # verification here, not five days later when a human notices.
  local pulse_url="${PULSE_URL:-https://pulse.coherencycoin.com}/pulse/now"
  echo
  echo "==> Pulse witness: ${pulse_url}"
  local body_file="$TMP_DIR/pulse_now.json"
  if ! run_with_retries "$CURL_RETRIES" "$CURL_RETRY_SLEEP_SECONDS" curl -sS -L -o "$body_file" \
    --max-time "$CURL_MAX_TIME" \
    --connect-timeout "$CURL_CONNECT_TIMEOUT" \
    "$pulse_url" >/dev/null; then
    echo "WARN: pulse witness unreachable — skipping (treat as soft signal when the witness itself is down)"
    return 0
  fi
  local overall silences_count silent_organs
  overall="$(python3 -c 'import sys, json
try:
    print(json.load(open(sys.argv[1])).get("overall", ""))
except Exception:
    print("")' "$body_file" 2>/dev/null)"
  silences_count="$(python3 -c 'import sys, json
try:
    print(len(json.load(open(sys.argv[1])).get("ongoing_silences", []) or []))
except Exception:
    print(0)' "$body_file" 2>/dev/null)"
  silent_organs="$(python3 -c 'import sys, json
try:
    data = json.load(open(sys.argv[1]))
    names = [s.get("organ", "?") for s in (data.get("ongoing_silences") or [])]
    print(", ".join(names))
except Exception:
    print("")' "$body_file" 2>/dev/null)"

  echo "overall=${overall:-unknown} ongoing_silences=${silences_count}"

  # Only ongoing silences fail the deploy — those are hard organ
  # breakage. A transient `overall=strained` with zero silences is
  # common right after a deploy (container warming, latency
  # briefly high) and shouldn't block. If this matters for an
  # operator, they see the warn and can re-verify once the
  # witness's 30s probe cycle catches up. The next deploy will
  # either catch up naturally or surface a real silence.
  if [[ "${silences_count:-0}" -eq 0 ]]; then
    if [[ "$overall" == "breathing" ]]; then
      echo "OK: every organ breathing"
    else
      echo "WARN: overall=${overall} with no ongoing silences (likely transient; re-verify in 30s)"
    fi
    return 0
  fi

  echo "FAIL: pulse reports ongoing silences"
  if [[ -n "$silent_organs" ]]; then
    echo "Silent organs: $silent_organs"
  fi
  echo "Hint: hit $pulse_url for the full organ list + silence ids"
  return 1
}

check_web_css_assets() {
  local web_root_url="$1"
  local html_file="$TMP_DIR/web_root.body.html"
  local status

  echo
  echo "==> Web CSS asset contract: ${web_root_url}"

  status="$(run_with_retries_capture "$CURL_RETRIES" "$CURL_RETRY_SLEEP_SECONDS" curl -sS -L -o "$html_file" -w "%{http_code}" \
    --max-time "$CURL_MAX_TIME" \
    --connect-timeout "$CURL_CONNECT_TIMEOUT" \
    "$web_root_url" || true)"
  echo "HTML status: ${status:-unknown}"
  if [[ -z "$status" || "$status" -lt 200 || "$status" -ge 400 ]]; then
    echo "FAIL: could not fetch web root HTML for CSS asset contract"
    return 1
  fi

  local css_paths=()
  local css_line
  while IFS= read -r css_line; do
    [[ -n "$css_line" ]] && css_paths+=("$css_line")
  done < <(grep -Eo '/_next/static/css/[^"]+\.css' "$html_file" | awk '!seen[$0]++')

  if [[ "${#css_paths[@]}" -eq 0 ]]; then
    echo "FAIL: no Next CSS assets found in web root HTML"
    return 1
  fi

  local css_path css_url css_status
  for css_path in "${css_paths[@]}"; do
    css_url="${WEB_URL%/}${css_path}"
    css_status="$(run_with_retries_capture "$CURL_RETRIES" "$CURL_RETRY_SLEEP_SECONDS" curl -sS -L -o /dev/null -w "%{http_code}" \
      --max-time "$CURL_MAX_TIME" \
      --connect-timeout "$CURL_CONNECT_TIMEOUT" \
      "$css_url" || true)"
    echo "CSS ${css_path} -> ${css_status:-unknown}"
    if [[ -z "$css_status" || "$css_status" -lt 200 || "$css_status" -ge 400 ]]; then
      echo "FAIL: referenced CSS asset is not publicly reachable"
      return 1
    fi
  done

  echo "PASS"
  return 0
}

check_web_public_asset() {
  local name="$1"
  local path="$2"
  local expected_kind="$3"
  local url="${WEB_URL%/}${path}"
  local slug
  slug="$(echo "public_asset_${name}" | tr "[:upper:]" "[:lower:]" | tr -cs "a-z0-9" "_")"
  local headers_file="$TMP_DIR/${slug}.headers.txt"
  local body_file="$TMP_DIR/${slug}.body"

  echo
  echo "==> Web public asset (${name}): ${url}"

  local status
  status="$(run_with_retries_capture "$CURL_RETRIES" "$CURL_RETRY_SLEEP_SECONDS" curl -sS -L -D "$headers_file" -o "$body_file" -w "%{http_code}" \
    --max-time "$CURL_MAX_TIME" \
    --connect-timeout "$CURL_CONNECT_TIMEOUT" \
    "$url" || true)"
  local content_type
  content_type="$(awk 'tolower($1) == "content-type:" { print $2 }' "$headers_file" | tail -n 1 | tr -d '\r')"
  echo "HTTP status: ${status:-unknown}"
  echo "Content-Type: ${content_type:-<missing>}"

  if [[ -z "$status" || "$status" -lt 200 || "$status" -ge 400 ]]; then
    echo "FAIL: public asset is not reachable"
    head -c 120 "$body_file" || true
    echo
    return 1
  fi

  if python3 - "$body_file" "$expected_kind" <<'PY'
import sys
from pathlib import Path

body = Path(sys.argv[1]).read_bytes()
kind = sys.argv[2]

if kind == "svg":
    probe = body[:256].lstrip()
    ok = probe.startswith(b"<svg") or probe.startswith(b"<?xml")
elif kind == "jpeg":
    ok = body.startswith(b"\xff\xd8\xff")
else:
    ok = False

if not ok:
    text_probe = body[:256].lower()
    if b"<!doctype html" in text_probe or b"<html" in text_probe:
        print("body looks like HTML fallback, not a public asset")
    else:
        print(f"body did not match expected {kind} signature")
    raise SystemExit(1)
PY
  then
    echo "PASS"
    return 0
  fi

  echo "FAIL: public asset response bytes are not ${expected_kind}"
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

check_persistence_contract() {
  local url="$1"
  local body_file="$TMP_DIR/persistence_contract.body.json"
  local status

  echo
  echo "==> Persistence contract: ${url}"
  status="$(run_with_retries_capture "$CURL_RETRIES" "$CURL_RETRY_SLEEP_SECONDS" curl -sS -o "$body_file" -w "%{http_code}" \
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
  status="$(run_with_retries_capture "$CURL_RETRIES" "$CURL_RETRY_SLEEP_SECONDS" curl -sS -o "$body_file" -w "%{http_code}" \
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
  status="$(run_with_retries_capture "$CURL_RETRIES" "$CURL_RETRY_SLEEP_SECONDS" curl -sS -o "$body_file" -w "%{http_code}" \
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
  health_status="$(run_with_retries_capture "$CURL_RETRIES" "$CURL_RETRY_SLEEP_SECONDS" curl -sS -o "$health_body" -w "%{http_code}" \
    --max-time "$CURL_MAX_TIME" \
    --connect-timeout "$CURL_CONNECT_TIMEOUT" \
    "$health_url" || true)"
  main_head_status="$(run_with_retries_capture "$CURL_RETRIES" "$CURL_RETRY_SLEEP_SECONDS" curl -sS -o "$main_head_body" -w "%{http_code}" \
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
    if [[ "$required" == "1" ]]; then
      echo "FAIL: API deployed SHA does not match expected main-head SHA"
      return 1
    fi
    echo "WARN: API deployed SHA does not match expected main-head SHA (non-blocking)"
    return 0
  fi

  echo "PASS"
  return 0
}

check_web_runtime_sha() {
  local proxy_url="$1"
  local main_head_url="$2"
  local required="${3:-0}"
  local proxy_body="$TMP_DIR/web_health_proxy_sha.body.json"
  local main_head_body="$TMP_DIR/web_main_head_sha.body.json"
  local proxy_status main_head_status

  echo
  echo "==> Web runtime SHA parity: ${proxy_url} vs ${main_head_url} (required=${required})"
  proxy_status="$(run_with_retries_capture "$CURL_RETRIES" "$CURL_RETRY_SLEEP_SECONDS" curl -sS -o "$proxy_body" -w "%{http_code}" \
    --max-time "$CURL_MAX_TIME" \
    --connect-timeout "$CURL_CONNECT_TIMEOUT" \
    "$proxy_url" || true)"
  main_head_status="$(run_with_retries_capture "$CURL_RETRIES" "$CURL_RETRY_SLEEP_SECONDS" curl -sS -o "$main_head_body" -w "%{http_code}" \
    --max-time "$CURL_MAX_TIME" \
    --connect-timeout "$CURL_CONNECT_TIMEOUT" \
    "$main_head_url" || true)"
  echo "proxy status: ${proxy_status:-unknown} | main-head status: ${main_head_status:-unknown}"

  if [[ -z "$proxy_status" || "$proxy_status" -lt 200 || "$proxy_status" -ge 400 ]]; then
    echo "FAIL: web health-proxy endpoint unavailable for SHA parity check"
    return 1
  fi
  if [[ -z "$main_head_status" || "$main_head_status" -lt 200 || "$main_head_status" -ge 400 ]]; then
    if [[ "$required" == "1" ]]; then
      echo "FAIL: main-head endpoint unavailable for required web SHA parity check"
      return 1
    fi
    echo "WARN: main-head endpoint unavailable (non-blocking web SHA parity check)"
    return 0
  fi

  local expected_sha observed_sha api_status
  expected_sha=""
  observed_sha=""
  api_status=""
  if command -v jq >/dev/null 2>&1; then
    expected_sha="$(jq -r '.sha // ""' "$main_head_body" 2>/dev/null || true)"
    observed_sha="$(
      jq -r '(.web.deployed_sha // .web.updated_at // .web.commit_sha // .web.git_sha // "")' "$proxy_body" 2>/dev/null || true
    )"
    api_status="$(jq -r '.api.status // ""' "$proxy_body" 2>/dev/null || true)"
  else
    expected_sha="$(grep -o '"sha"[[:space:]]*:[[:space:]]*"[^"]*"' "$main_head_body" | head -n 1 | sed 's/.*"sha"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/')"
    observed_sha="$(grep -o '"deployed_sha"[[:space:]]*:[[:space:]]*"[^"]*"' "$proxy_body" | head -n 1 | sed 's/.*"deployed_sha"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/')"
    if [[ -z "$observed_sha" ]]; then
      observed_sha="$(grep -o '"updated_at"[[:space:]]*:[[:space:]]*"[^"]*"' "$proxy_body" | head -n 1 | sed 's/.*"updated_at"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/')"
    fi
    api_status="$(grep -o '"status"[[:space:]]*:[[:space:]]*"[^"]*"' "$proxy_body" | head -n 1 | sed 's/.*"status"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/')"
  fi
  expected_sha="$(echo "${expected_sha:-}" | tr -d '\r')"
  observed_sha="$(echo "${observed_sha:-}" | tr -d '\r')"
  api_status="$(echo "${api_status:-}" | tr -d '\r')"
  echo "expected_sha: ${expected_sha:-<missing>}"
  echo "observed_sha: ${observed_sha:-<missing>}"
  echo "api_status: ${api_status:-<missing>}"

  if [[ -n "$api_status" && "$api_status" != "ok" ]]; then
    echo "FAIL: web health-proxy indicates API is not healthy"
    return 1
  fi

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
      echo "FAIL: web health-proxy does not expose deployed SHA (required)"
      return 1
    fi
    echo "WARN: web health-proxy does not expose deployed SHA (non-blocking)"
    return 0
  fi

  if [[ "$observed_sha" != "$expected_sha" ]]; then
    echo "FAIL: web deployed SHA does not match expected main-head SHA"
    return 1
  fi

  echo "PASS"
  return 0
}

fail=0
check_url "Public API health" "${API_URL%/}/api/health" || fail=1
if [[ "$VERIFY_REQUIRE_GATES_MAIN_HEAD" == "1" ]]; then
  check_url "Public gates main head" "${API_URL%/}/api/gates/main-head" || fail=1
else
  echo
  echo "==> Skipping public gates main head check (VERIFY_REQUIRE_GATES_MAIN_HEAD=0)"
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
check_url "Public web root" "${WEB_URL%/}/" || fail=1
check_web_css_assets "${WEB_URL%/}/" || fail=1
check_web_public_asset "logo" "/assets/logo.svg" "svg" || fail=1
check_web_public_asset "generated vision image" "/visuals/generated/lc-space-0.jpg" "jpeg" || fail=1
check_url "Public web gates page" "${WEB_URL%/}/gates" || fail=1
check_url "Public web API health page" "${WEB_URL%/}/api-health" || fail=1
check_url "Public web API health proxy" "${WEB_URL%/}/api/health-proxy" || fail=1
check_web_runtime_sha \
  "${WEB_URL%/}/api/health-proxy" \
  "${API_URL%/}/api/gates/main-head" \
  "$VERIFY_REQUIRE_WEB_HEALTH_PROXY_SHA" || fail=1
check_cors "${API_URL%/}/api/health" "${WEB_URL%/}" || fail=1
check_pulse_witness || fail=1
if [[ "$VERIFY_REQUIRE_TELEGRAM_ALERTS" == "1" ]]; then
  check_telegram_alert_config "${API_URL%/}/api/agent/telegram/diagnostics" || fail=1
else
  echo
  echo "==> Skipping Telegram alert config gate (VERIFY_REQUIRE_TELEGRAM_ALERTS=0)"
fi

if [[ "$fail" -eq 0 ]]; then
  echo
  echo "Deployment verification passed: public API and web are reachable and CORS is aligned."
else
  echo
  echo "Deployment verification failed: at least one endpoint or CORS check failed."
  exit 1
fi
