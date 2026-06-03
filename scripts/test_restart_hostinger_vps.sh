#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

fixture_dir="$(mktemp -d)"
trap 'rm -rf "$fixture_dir"' EXIT

mkdir -p "$fixture_dir/bin"

cat >"$fixture_dir/bin/curl" <<'SH'
#!/usr/bin/env bash
set -euo pipefail

printf '%s\n' "$*" > "$CURL_ARGS_LOG"

out=""
while (($#)); do
  case "$1" in
    --output)
      out="$2"
      shift 2
      ;;
    --write-out)
      shift 2
      ;;
    *)
      shift
      ;;
  esac
done

test -n "$out"
printf '{"id":91223344,"state":"restarting"}\n' > "$out"
printf '202'
SH
chmod +x "$fixture_dir/bin/curl"

args_log="$fixture_dir/curl-args.log"

output="$(
  PATH="$fixture_dir/bin:$PATH" \
  CURL_ARGS_LOG="$args_log" \
  HOSTINGER_API_TOKEN="redacted-test-token" \
  "$ROOT_DIR/scripts/restart_hostinger_vps.sh" "91223344"
)"

grep -F "hostinger-vps-restart: accepted status=202 virtual_machine_id=91223344" <<<"$output" >/dev/null
grep -F '{"id":91223344,"state":"restarting"}' <<<"$output" >/dev/null
grep -F -- "--request POST" "$args_log" >/dev/null
grep -F -- "--url https://developers.hostinger.com/api/vps/v1/virtual-machines/91223344/restart" "$args_log" >/dev/null
grep -F -- "--header Authorization: Bearer redacted-test-token" "$args_log" >/dev/null

echo "PASS: Hostinger VPS restart API request shape"
