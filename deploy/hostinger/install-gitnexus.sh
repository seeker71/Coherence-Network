#!/usr/bin/env bash
# Install / update / run the GitNexus sidecar MCP server on the VPS.
#
# Per specs/gitnexus-integration-experiment.md R1 + R5. Idempotent:
# safe to run on every deploy. The sidecar runs as a backgrounded
# `node ... mcp serve` process; PID tracked in /var/run/gitnexus.pid.
#
# Non-blocking: any failure here logs and exits 0 so the API/web
# deploy is not held hostage to GitNexus availability. The trial
# spec explicitly counts staleness/install incidents as data, not
# setup bugs to silence.
#
# Required env (passed by auto-deploy.sh):
#   REPO_DIR       — path to this repo on the VPS
#   COMPOSE_ROOT   — /docker/coherence-network (for log location)
#   LOG_FILE       — append-target shared with auto-deploy
#
# Optional env:
#   GITNEXUS_HOME  — install dir (default /docker/gitnexus)
#   GITNEXUS_PORT  — sidecar port (default 8765)

set -uo pipefail

REPO_DIR="${REPO_DIR:?REPO_DIR required}"
COMPOSE_ROOT="${COMPOSE_ROOT:-/docker/coherence-network}"
LOG_FILE="${LOG_FILE:-${COMPOSE_ROOT}/deploy.log}"
GITNEXUS_HOME="${GITNEXUS_HOME:-/docker/gitnexus}"
GITNEXUS_PORT="${GITNEXUS_PORT:-8765}"
PIN_FILE="${REPO_DIR}/scripts/.gitnexus-pin"
PID_FILE="/var/run/gitnexus.pid"

ts() { date -u +%Y-%m-%dT%H:%M:%SZ; }
log() { printf '%s — gitnexus: %s\n' "$(ts)" "$*" | tee -a "$LOG_FILE"; }

if [[ ! -f "$PIN_FILE" ]]; then
  log "no pin file at $PIN_FILE — sidecar not installed (trial has not started)"
  exit 0
fi

PIN="$(tr -d '[:space:]' < "$PIN_FILE")"
if [[ -z "$PIN" ]]; then
  log "pin file empty — skipping"
  exit 0
fi
log "pinned SHA: ${PIN:0:12}"

# Clone or update
if [[ ! -d "$GITNEXUS_HOME/.git" ]]; then
  log "cloning into $GITNEXUS_HOME"
  if ! git clone --quiet https://github.com/abhigyanpatwari/GitNexus.git "$GITNEXUS_HOME" >> "$LOG_FILE" 2>&1; then
    log "clone failed — sidecar not installed"
    exit 0
  fi
fi

cd "$GITNEXUS_HOME"
CURRENT="$(git rev-parse HEAD 2>/dev/null || echo unknown)"
if [[ "$CURRENT" != "$PIN" ]]; then
  log "advancing ${CURRENT:0:12} -> ${PIN:0:12}"
  git fetch --quiet origin >> "$LOG_FILE" 2>&1 || true
  if ! git checkout --quiet "$PIN" >> "$LOG_FILE" 2>&1; then
    log "pin SHA not reachable — leaving sidecar at ${CURRENT:0:12}"
    exit 0
  fi
  if ! npm install --no-audit --no-fund >> "$LOG_FILE" 2>&1; then
    log "npm install failed — leaving sidecar at previous build state"
    exit 0
  fi
  npm run build >> "$LOG_FILE" 2>&1 || log "npm run build returned non-zero (continuing)"
fi

# Locate the CLI entry. GitNexus's package.json exposes a `bin` map;
# the build output is typically at dist/cli.js.
CLI_ENTRY=""
for candidate in "$GITNEXUS_HOME/dist/cli.js" "$GITNEXUS_HOME/dist/index.js" "$GITNEXUS_HOME/bin/gitnexus.js"; do
  [[ -f "$candidate" ]] && CLI_ENTRY="$candidate" && break
done
if [[ -z "$CLI_ENTRY" ]]; then
  log "could not locate CLI entrypoint after build — sidecar not started"
  exit 0
fi

# (Re)index this repo. Incremental keeps the index aligned with HEAD.
log "indexing $REPO_DIR"
if ! node "$CLI_ENTRY" index "$REPO_DIR" --incremental >> "$LOG_FILE" 2>&1; then
  # Some GitNexus versions don't support --incremental; fall back to full reindex.
  node "$CLI_ENTRY" index "$REPO_DIR" >> "$LOG_FILE" 2>&1 || \
    log "indexing returned non-zero (sidecar will still serve previous index)"
fi

# Restart sidecar — kill existing if any, then start in background.
if [[ -f "$PID_FILE" ]]; then
  OLD_PID="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -n "${OLD_PID}" ]] && kill -0 "$OLD_PID" 2>/dev/null; then
    log "stopping previous sidecar (pid $OLD_PID)"
    kill "$OLD_PID" 2>/dev/null || true
    sleep 1
    kill -9 "$OLD_PID" 2>/dev/null || true
  fi
fi

mkdir -p "$(dirname "$PID_FILE")"
nohup node "$CLI_ENTRY" mcp serve --port "$GITNEXUS_PORT" \
  > "$COMPOSE_ROOT/gitnexus.log" 2>&1 < /dev/null &
NEW_PID=$!
echo "$NEW_PID" > "$PID_FILE"
sleep 1
if kill -0 "$NEW_PID" 2>/dev/null; then
  log "sidecar running on port $GITNEXUS_PORT (pid $NEW_PID)"
else
  log "sidecar exited immediately — see $COMPOSE_ROOT/gitnexus.log"
fi
exit 0
