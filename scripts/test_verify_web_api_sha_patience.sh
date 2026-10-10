#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

fixture_dir="$(mktemp -d)"
trap 'rm -rf "$fixture_dir"' EXIT

VERIFY_WEB_API_DEPLOY_SOURCE_ONLY=1 source "$ROOT_DIR/scripts/verify_web_api_deploy.sh" "http://api.example" "http://web.example"
source_tmp_dir="$TMP_DIR"
trap 'rm -rf "$fixture_dir" "$source_tmp_dir"' EXIT

target_sha="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
old_sha="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
api_health_calls_file="$fixture_dir/api_health_calls"
web_proxy_calls_file="$fixture_dir/web_proxy_calls"
web_proxy_transient_file="$fixture_dir/web_proxy_transient"
web_proxy_late_transient_file="$fixture_dir/web_proxy_late_transient"
fake_clock_file="$fixture_dir/fake_clock"
printf '0\n' > "$api_health_calls_file"
printf '0\n' > "$web_proxy_calls_file"

date() {
  if [[ -f "$fake_clock_file" && "${1:-}" == "+%s" ]]; then
    cat "$fake_clock_file"
    return 0
  fi
  command date "$@"
}

curl() {
  local output_file=""
  local write_format=""
  local url=""
  local http_status="200"
  while (($#)); do
    case "$1" in
      -o)
        output_file="$2"
        shift 2
        ;;
      -w)
        write_format="$2"
        shift 2
        ;;
      --max-time|--connect-timeout)
        shift 2
        ;;
      -*)
        shift
        ;;
      *)
        url="$1"
        shift
        ;;
    esac
  done

  local body=""
  case "$url" in
    http://api.example/api/health)
      local calls
      calls="$(cat "$api_health_calls_file")"
      calls=$((calls + 1))
      printf '%s\n' "$calls" > "$api_health_calls_file"
      if [[ "$calls" -eq 1 ]]; then
        body="{\"deployed_sha\":\"$old_sha\"}"
      else
        body="{\"deployed_sha\":\"$target_sha\"}"
      fi
      ;;
    http://api.example/api/gates/main-head)
      body="{\"sha\":\"$target_sha\"}"
      ;;
    http://api.example/api/utils/kernel_status)
      body='{"active":"fkwu","available":true,"binary_available":true}'
      ;;
    http://web.example/api/health-proxy)
      local calls
      calls="$(cat "$web_proxy_calls_file")"
      calls=$((calls + 1))
      printf '%s\n' "$calls" > "$web_proxy_calls_file"
      if [[ -f "$web_proxy_late_transient_file" && "$calls" -eq 1 ]]; then
        body="{\"api\":{\"status\":\"ok\"},\"web\":{\"deployed_sha\":\"$old_sha\"}}"
      elif [[ -f "$web_proxy_late_transient_file" && "$calls" -eq 2 ]]; then
        http_status="503"
        body='{"detail":"upstream cutover"}'
        printf '100\n' > "$fake_clock_file"
      elif [[ -f "$web_proxy_late_transient_file" && "$calls" -eq 3 ]]; then
        body="{\"api\":{\"status\":\"ok\"},\"web\":{\"deployed_sha\":\"$old_sha\"}}"
        printf '189\n' > "$fake_clock_file"
      elif [[ -f "$web_proxy_late_transient_file" && "$calls" -eq 4 ]]; then
        body="{\"api\":{\"status\":\"ok\"},\"web\":{\"deployed_sha\":\"$target_sha\"}}"
        printf '260\n' > "$fake_clock_file"
      elif [[ -f "$web_proxy_transient_file" && "$calls" -eq 1 ]]; then
        http_status="503"
        body='{"detail":"upstream restarting"}'
        printf '89\n' > "$fake_clock_file"
      elif [[ -f "$web_proxy_transient_file" && "$calls" -eq 2 ]]; then
        body="{\"api\":{\"status\":\"ok\"},\"web\":{\"deployed_sha\":\"$old_sha\"}}"
        printf '210\n' > "$fake_clock_file"
      elif [[ "$calls" -eq 1 ]]; then
        body="{\"api\":{\"status\":\"ok\"},\"web\":{\"deployed_sha\":\"$old_sha\"}}"
      else
        body="{\"api\":{\"status\":\"ok\"},\"web\":{\"deployed_sha\":\"$target_sha\"}}"
      fi
      ;;
    *)
      echo "unexpected curl url: $url" >&2
      return 9
      ;;
  esac

  if [[ -n "$output_file" ]]; then
    printf '%s\n' "$body" > "$output_file"
  else
    printf '%s\n' "$body"
  fi

  if [[ "$write_format" == "%{http_code}" ]]; then
    printf '%s' "$http_status"
  fi
}

api_output="$(
  SHA_PARITY_PATIENCE_SECONDS=2 \
  SHA_PARITY_PATIENCE_INTERVAL=0 \
    check_api_runtime_sha "http://api.example/api/health" "http://api.example/api/gates/main-head" 1
)"
grep -F "WARN: API deployed SHA does not match expected main-head SHA; retrying" <<<"$api_output" >/dev/null
grep -F "OK: API runtime SHA parity settled after 2 attempt(s)" <<<"$api_output" >/dev/null
grep -F "PASS" <<<"$api_output" >/dev/null

printf '1\n' > "$api_health_calls_file"
printf '{"deployed_sha":"%s"}\n' "$old_sha" > "$API_HEALTH_SNAPSHOT_FILE"
stale_cached_api_output="$(
  SHA_PARITY_PATIENCE_SECONDS=2 \
  SHA_PARITY_PATIENCE_INTERVAL=0 \
    check_api_runtime_sha \
      "http://api.example/api/health" \
      "http://api.example/api/gates/main-head" \
      1 \
      "$API_HEALTH_SNAPSHOT_FILE"
)"
grep -F "WARN: API deployed SHA does not match expected main-head SHA; retrying" <<<"$stale_cached_api_output" >/dev/null
grep -F "OK: API runtime SHA parity settled after 2 attempt(s)" <<<"$stale_cached_api_output" >/dev/null
[[ "$(cat "$api_health_calls_file")" == "2" ]]

printf '0\n' > "$api_health_calls_file"
cat > "$API_HEALTH_SNAPSHOT_FILE" <<JSON
{
  "deployed_sha": "$target_sha",
  "kernel_runtime": "fkwu",
  "native_runtime_observation": {
    "verified": true,
    "kernel": {
      "verified": true,
      "runtime": "fkwu",
      "execution_authority": "c-bootstrap-fkwu",
      "sibling_kernel_role": "differential-reference-only"
    },
    "form_cli": {"verified": true}
  }
}
JSON

cached_api_output="$(
  check_api_runtime_sha \
    "http://api.example/api/health" \
    "http://api.example/api/gates/main-head" \
    1 \
    "$API_HEALTH_SNAPSHOT_FILE"
)"
grep -F "PASS" <<<"$cached_api_output" >/dev/null
[[ "$(cat "$api_health_calls_file")" == "0" ]]

cached_fkwu_output="$(check_fkwu_native_authority)"
grep -F "PASS: c-bootstrap fkwu is verified" <<<"$cached_fkwu_output" >/dev/null
[[ "$(cat "$api_health_calls_file")" == "0" ]]

web_output="$(
  SHA_PARITY_PATIENCE_SECONDS=2 \
  SHA_PARITY_PATIENCE_INTERVAL=0 \
    check_web_runtime_sha "http://web.example/api/health-proxy" "http://api.example/api/gates/main-head" 1
)"
grep -F "WARN: web deployed SHA does not match expected main-head SHA; retrying" <<<"$web_output" >/dev/null
grep -F "OK: Web runtime SHA parity settled after 2 attempt(s)" <<<"$web_output" >/dev/null
grep -F "PASS" <<<"$web_output" >/dev/null

printf '0\n' > "$web_proxy_calls_file"
printf '0\n' > "$fake_clock_file"
touch "$web_proxy_transient_file"
web_rollout_output="$(
  GATEWAY_PATIENCE_SECONDS=90 \
  GATEWAY_PATIENCE_INTERVAL=0 \
  SHA_PARITY_PATIENCE_SECONDS=180 \
  SHA_PARITY_PATIENCE_INTERVAL=0 \
    check_web_runtime_sha "http://web.example/api/health-proxy" "http://api.example/api/gates/main-head" 1
)"
rm -f "$web_proxy_transient_file"
rm -f "$fake_clock_file"
grep -F "WARN: web health-proxy rollout status 503" <<<"$web_rollout_output" >/dev/null
grep -F "WARN: web deployed SHA does not match expected main-head SHA; retrying" <<<"$web_rollout_output" >/dev/null
grep -F "OK: Web runtime SHA parity settled after 3 attempt(s)" <<<"$web_rollout_output" >/dev/null
grep -F "PASS" <<<"$web_rollout_output" >/dev/null
[[ "$(cat "$web_proxy_calls_file")" == "3" ]]

printf '0\n' > "$web_proxy_calls_file"
printf '0\n' > "$fake_clock_file"
touch "$web_proxy_late_transient_file"
late_rollout_output="$(
  GATEWAY_PATIENCE_SECONDS=90 \
  GATEWAY_PATIENCE_INTERVAL=0 \
  SHA_PARITY_PATIENCE_SECONDS=180 \
  SHA_PARITY_PATIENCE_INTERVAL=0 \
    check_web_runtime_sha "http://web.example/api/health-proxy" "http://api.example/api/gates/main-head" 1
)"
rm -f "$web_proxy_late_transient_file"
rm -f "$fake_clock_file"
grep -F "WARN: web deployed SHA does not match expected main-head SHA; retrying" <<<"$late_rollout_output" >/dev/null
grep -F "WARN: web health-proxy rollout status 503" <<<"$late_rollout_output" >/dev/null
grep -F "OK: Web runtime SHA parity settled after 4 attempt(s)" <<<"$late_rollout_output" >/dev/null
grep -F "PASS" <<<"$late_rollout_output" >/dev/null
[[ "$(cat "$web_proxy_calls_file")" == "4" ]]

grep -F 'check_cors "${API_URL%/}/api/ping"' "$ROOT_DIR/scripts/verify_web_api_deploy.sh" >/dev/null
if grep -Fq 'check_url "Public web API health proxy"' "$ROOT_DIR/scripts/verify_web_api_deploy.sh"; then
  echo "duplicate web health-proxy read remains" >&2
  exit 1
fi

echo "PASS: API health snapshot is reused and SHA parity waits through rollout mismatch"
