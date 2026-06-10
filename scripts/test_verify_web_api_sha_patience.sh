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
printf '0\n' > "$api_health_calls_file"
printf '0\n' > "$web_proxy_calls_file"

curl() {
  local output_file=""
  local write_format=""
  local url=""
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
    http://web.example/api/health-proxy)
      local calls
      calls="$(cat "$web_proxy_calls_file")"
      calls=$((calls + 1))
      printf '%s\n' "$calls" > "$web_proxy_calls_file"
      if [[ "$calls" -eq 1 ]]; then
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
    printf '200'
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

web_output="$(
  SHA_PARITY_PATIENCE_SECONDS=2 \
  SHA_PARITY_PATIENCE_INTERVAL=0 \
    check_web_runtime_sha "http://web.example/api/health-proxy" "http://api.example/api/gates/main-head" 1
)"
grep -F "WARN: web deployed SHA does not match expected main-head SHA; retrying" <<<"$web_output" >/dev/null
grep -F "OK: Web runtime SHA parity settled after 2 attempt(s)" <<<"$web_output" >/dev/null
grep -F "PASS" <<<"$web_output" >/dev/null

echo "PASS: API and web SHA parity wait through rollout mismatch"
