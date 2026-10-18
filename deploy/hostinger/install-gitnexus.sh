#!/usr/bin/env bash
# Run the GitNexus sidecar MCP server on the VPS via npx.
#
# Per specs/gitnexus-integration-experiment.md R1. Idempotent: safe to
# run on every deploy. Uses the published npm package (not git clone)
# so there's no build step — npx fetches the pinned version on first
# call, caches it under ~/.npm, and runs it as a backgrounded process.
# PID tracked at /var/run/gitnexus.pid; stopped + restarted on each
# run so the new pin's index serves the new traffic.
#
# Non-blocking: any failure here logs and exits 0 so the api/web
# deploy is never held hostage. The trial spec explicitly counts
# install/staleness incidents as data, not setup bugs.
#
# Required env (passed by auto-deploy.sh):
#   REPO_DIR       — path to this repo on the VPS
#   COMPOSE_ROOT   — /docker/coherence-network (for log location)
#   LOG_FILE       — append-target shared with auto-deploy
#
# Optional env:
#   GITNEXUS_PORT  — sidecar port (default 8765)

set -uo pipefail

REPO_DIR="${REPO_DIR:?REPO_DIR required}"
COMPOSE_ROOT="${COMPOSE_ROOT:-/docker/coherence-network}"
LOG_FILE="${LOG_FILE:-${COMPOSE_ROOT}/deploy.log}"
GITNEXUS_PORT="${GITNEXUS_PORT:-8765}"
PIN_FILE="${REPO_DIR}/scripts/.gitnexus-pin"
PID_FILE="/var/run/gitnexus.pid"

ts() { date -u +%Y-%m-%dT%H:%M:%SZ; }
log() { printf '%s — gitnexus: %s\n' "$(ts)" "$*" | tee -a "$LOG_FILE"; }

if [[ ! -f "$PIN_FILE" ]]; then
  log "no pin file at $PIN_FILE — sidecar not installed (trial has not started)"
  exit 0
fi

# Pin file format (one key:value per line):
#   npm:1.6.3
#   sha:ffa0510...
NPM_VERSION="$(awk -F: '/^npm:/ {print $2; exit}' "$PIN_FILE" | tr -d '[:space:]')"
SHA_PIN="$(awk -F: '/^sha:/ {print $2; exit}' "$PIN_FILE" | tr -d '[:space:]')"

if [[ -z "$NPM_VERSION" ]]; then
  log "pin file has no npm: line — skipping"
  exit 0
fi
log "pinned: gitnexus@${NPM_VERSION} (sha ${SHA_PIN:0:12})"

if ! command -v npx >/dev/null 2>&1; then
  log "npx not on PATH — sidecar not started"
  exit 0
fi

# Stop the previous sidecar (if any) so the new pin's index serves traffic.
if [[ -f "$PID_FILE" ]]; then
  OLD_PID="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -n "${OLD_PID}" ]] && kill -0 "$OLD_PID" 2>/dev/null; then
    log "stopping previous sidecar (pid $OLD_PID)"
    kill "$OLD_PID" 2>/dev/null || true
    sleep 1
    kill -9 "$OLD_PID" 2>/dev/null || true
  fi
fi

# Pre-cache the npm package so the first agent call doesn't pay the
# fetch cost (fastest in-place install, no global pollution).
log "fetching gitnexus@${NPM_VERSION} into npx cache"
npx --yes "gitnexus@${NPM_VERSION}" --version >> "$LOG_FILE" 2>&1 || \
  log "pre-cache returned non-zero (sidecar may still start cleanly)"

mkdir -p "$(dirname "$PID_FILE")"
# Run in background. The sidecar is the long-lived MCP server;
# nohup detaches from the deploy SSH session so it survives the script.
nohup npx --yes "gitnexus@${NPM_VERSION}" mcp --port "$GITNEXUS_PORT" \
  > "$COMPOSE_ROOT/gitnexus.log" 2>&1 < /dev/null &
NEW_PID=$!
echo "$NEW_PID" > "$PID_FILE"
sleep 2
if kill -0 "$NEW_PID" 2>/dev/null; then
  log "sidecar running on port $GITNEXUS_PORT (pid $NEW_PID)"
else
  log "sidecar exited immediately — see $COMPOSE_ROOT/gitnexus.log"
fi
exit 0
