#!/usr/bin/env bash
set -euo pipefail

FETCH_ALLOW_STALE_MAIN="${FETCH_ALLOW_STALE_MAIN:-0}"

has_cached_origin_main() {
  git show-ref --verify --quiet "refs/remotes/origin/main"
}

network_preflight() {
  python3 - <<'PY'
import socket
import sys

host = "github.com"
port = 443

try:
    socket.getaddrinfo(host, port)
except Exception as exc:
    print(f"fetch-origin-main: network preflight failed (dns): {exc}", file=sys.stderr)
    raise SystemExit(2)

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(5.0)
try:
    sock.connect((host, port))
except Exception as exc:
    print(f"fetch-origin-main: network preflight failed (tcp): {exc}", file=sys.stderr)
    raise SystemExit(3)
finally:
    sock.close()
PY
}

is_network_error() {
  local text="$1"
  [[ "$text" == *"Could not resolve host"* ]] || \
    [[ "$text" == *"Failed to connect"* ]] || \
    [[ "$text" == *"Connection timed out"* ]] || \
    [[ "$text" == *"No route to host"* ]] || \
    [[ "$text" == *"Name or service not known"* ]]
}

if ! network_preflight; then
  if [[ "$FETCH_ALLOW_STALE_MAIN" == "1" ]] && has_cached_origin_main; then
    echo "fetch-origin-main: warning: network unavailable; using cached refs/remotes/origin/main"
    exit 0
  fi
  echo "fetch-origin-main: ERROR: cannot reach GitHub; aborting fetch."
  echo "fetch-origin-main: hint: restore network or rerun with FETCH_ALLOW_STALE_MAIN=1 to proceed with cached origin/main."
  exit 1
fi

fetch_output=""
if ! fetch_output="$(git fetch origin main 2>&1)"; then
  echo "$fetch_output" >&2
  if is_network_error "$fetch_output"; then
    if [[ "$FETCH_ALLOW_STALE_MAIN" == "1" ]] && has_cached_origin_main; then
      echo "fetch-origin-main: warning: git fetch failed due to network; using cached refs/remotes/origin/main"
      exit 0
    fi
    echo "fetch-origin-main: ERROR: git fetch failed due to network."
    echo "fetch-origin-main: hint: restore network or rerun with FETCH_ALLOW_STALE_MAIN=1."
  fi
  exit 1
fi

echo "$fetch_output"
echo "fetch-origin-main: ok"
