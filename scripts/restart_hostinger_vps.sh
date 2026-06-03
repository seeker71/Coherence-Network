#!/usr/bin/env bash
set -euo pipefail

API_BASE="${HOSTINGER_API_BASE:-https://developers.hostinger.com}"
TOKEN="${HOSTINGER_API_TOKEN:-}"
VIRTUAL_MACHINE_ID="${1:-${HOSTINGER_VIRTUAL_MACHINE_ID:-}}"

fail() {
  echo "hostinger-vps-restart: FAIL: $*" >&2
  exit 1
}

test -n "$TOKEN" || fail "HOSTINGER_API_TOKEN is required"
test -n "$VIRTUAL_MACHINE_ID" || fail "virtual machine id argument or HOSTINGER_VIRTUAL_MACHINE_ID is required"

response_file="$(mktemp)"
trap 'rm -f "$response_file"' EXIT

status="$(
  curl -sS \
    --request POST \
    --url "${API_BASE%/}/api/vps/v1/virtual-machines/${VIRTUAL_MACHINE_ID}/restart" \
    --header "Accept: application/json" \
    --header "Authorization: Bearer ${TOKEN}" \
    --output "$response_file" \
    --write-out "%{http_code}"
)"

case "$status" in
  200|201|202|204)
    echo "hostinger-vps-restart: accepted status=${status} virtual_machine_id=${VIRTUAL_MACHINE_ID}"
    if [[ -s "$response_file" ]]; then
      if command -v jq >/dev/null 2>&1; then
        jq -c . "$response_file" || cat "$response_file"
      else
        cat "$response_file"
      fi
    fi
    ;;
  *)
    echo "hostinger-vps-restart: response status=${status}" >&2
    cat "$response_file" >&2 || true
    exit 1
    ;;
esac
