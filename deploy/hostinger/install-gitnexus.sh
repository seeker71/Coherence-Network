#!/usr/bin/env bash
# Run the GitNexus sidecar MCP server on the VPS through a pinned Node carrier.
#
# Per specs/gitnexus-integration-experiment.md R1. Idempotent: safe to
# run on every deploy. GitNexus 1.6.3 exposes MCP over stdio; the pinned
# Supergateway carrier makes that real server available over SSE. Docker is the
# production authority, with host npx retained as a fallback. The index remains
# outside tracked repository state in both cases.
#
# The caller keeps this trial non-blocking. This script returns non-zero when
# neither carrier can start the sidecar so the incident remains observable.
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
CONTAINER_NAME="coherence-network-gitnexus"

ts() { date -u +%Y-%m-%dT%H:%M:%SZ; }
log() { printf '%s — gitnexus: %s\n' "$(ts)" "$*" | tee -a "$LOG_FILE"; }

if [[ ! -f "$PIN_FILE" ]]; then
  log "no pin file at $PIN_FILE — sidecar not installed (trial has not started)"
  exit 0
fi

# Pin file format (one key:value per line):
#   npm:1.6.3
#   sha:ffa0510...
#   gateway:4.2.0
#   node-image:node:20-bookworm
NPM_VERSION="$(awk -F: '/^npm:/ {print $2; exit}' "$PIN_FILE" | tr -d '[:space:]')"
SHA_PIN="$(awk -F: '/^sha:/ {print $2; exit}' "$PIN_FILE" | tr -d '[:space:]')"
GATEWAY_VERSION="$(awk -F: '/^gateway:/ {print $2; exit}' "$PIN_FILE" | tr -d '[:space:]')"
NODE_IMAGE="$(sed -n 's/^node-image://p' "$PIN_FILE" | head -1 | tr -d '[:space:]')"

if [[ ! "$NPM_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  log "pin file has no valid npm version"
  exit 1
fi
if [[ ! "$GATEWAY_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  log "pin file has no valid Supergateway version"
  exit 1
fi
if [[ ! "$GITNEXUS_PORT" =~ ^[0-9]+$ ]] || (( GITNEXUS_PORT < 1 || GITNEXUS_PORT > 65535 )); then
  log "GITNEXUS_PORT must be an integer from 1 through 65535"
  exit 1
fi
log "pinned: gitnexus@${NPM_VERSION} (sha ${SHA_PIN:0:12}), supergateway@${GATEWAY_VERSION}"

wait_for_gateway() {
  attempt=1
  while (( attempt <= 60 )); do
    if curl -fsS --max-time 5 "http://127.0.0.1:${GITNEXUS_PORT}/healthz" >/dev/null 2>&1; then
      return 0
    fi
    sleep 3
    attempt=$((attempt + 1))
  done
  return 1
}

stop_host_sidecar() {
  if [[ ! -f "$PID_FILE" ]]; then
    return
  fi
  OLD_PID="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -n "${OLD_PID}" ]] && kill -0 "$OLD_PID" 2>/dev/null; then
    log "stopping previous host sidecar (pid $OLD_PID)"
    kill "$OLD_PID" 2>/dev/null || true
    sleep 1
    kill -9 "$OLD_PID" 2>/dev/null || true
  fi
  rm -f "$PID_FILE"
}

start_with_host_npx() {
  stop_host_sidecar
  if command -v docker >/dev/null 2>&1; then
    docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
  fi

  index_dir="$COMPOSE_ROOT/gitnexus-index"
  mkdir -p "$index_dir"
  if [[ ! -e "$REPO_DIR/.gitnexus" ]]; then
    ln -s "$index_dir" "$REPO_DIR/.gitnexus"
  elif [[ -L "$REPO_DIR/.gitnexus" ]]; then
    existing_index="$(readlink "$REPO_DIR/.gitnexus")"
    if [[ "$existing_index" != "$index_dir" ]]; then
      log "host carrier found a different .gitnexus index link: $existing_index"
      return 1
    fi
  else
    log "host carrier requires $REPO_DIR/.gitnexus to be an external index link"
    return 1
  fi

  log "fetching pinned GitNexus and Supergateway into host npx cache"
  npx --yes "gitnexus@${NPM_VERSION}" --version >> "$LOG_FILE" 2>&1 || \
    log "pre-cache returned non-zero (sidecar may still start cleanly)"
  npx --yes "supergateway@${GATEWAY_VERSION}" --version >> "$LOG_FILE" 2>&1 || \
    log "gateway pre-cache returned non-zero (sidecar may still start cleanly)"

  mkdir -p "$(dirname "$PID_FILE")"
  nohup bash -lc \
    'cd "$1" && npx --yes "gitnexus@$2" analyze --skip-agents-md . && exec npx --yes "supergateway@$3" --stdio "npx --yes gitnexus@$2 mcp" --port "$4" --host 127.0.0.1 --healthEndpoint /healthz --healthCheck server' \
    bash "$REPO_DIR" "$NPM_VERSION" "$GATEWAY_VERSION" "$GITNEXUS_PORT" \
    > "$COMPOSE_ROOT/gitnexus.log" 2>&1 < /dev/null &
  NEW_PID=$!
  echo "$NEW_PID" > "$PID_FILE"
  if wait_for_gateway && kill -0 "$NEW_PID" 2>/dev/null; then
    log "host MCP gateway healthy on port $GITNEXUS_PORT (pid $NEW_PID)"
    return 0
  fi
  log "host MCP gateway did not become healthy — see $COMPOSE_ROOT/gitnexus.log"
  return 1
}

start_with_docker() {
  if [[ ! "$NODE_IMAGE" =~ ^node:[A-Za-z0-9._@:-]+$ ]]; then
    log "pin file has no valid node image for the Docker carrier"
    return 1
  fi
  index_dir="$COMPOSE_ROOT/gitnexus-index"
  registry_dir="$COMPOSE_ROOT/gitnexus-registry"
  npm_cache="$COMPOSE_ROOT/gitnexus-npm-cache"
  stop_host_sidecar
  mkdir -p "$index_dir" "$registry_dir" "$npm_cache"
  docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
  log "starting Docker carrier ${NODE_IMAGE}"
  if ! docker run -d \
      --name "$CONTAINER_NAME" \
      --restart unless-stopped \
      --network host \
      -v "$REPO_DIR:/repo:ro" \
      -v "$index_dir:/repo/.gitnexus" \
      -v "$registry_dir:/root/.gitnexus" \
      -v "$npm_cache:/root/.npm" \
      -w /repo \
      "$NODE_IMAGE" \
      sh -lc "npx --yes gitnexus@${NPM_VERSION} analyze --skip-agents-md /repo && exec npx --yes supergateway@${GATEWAY_VERSION} --stdio 'npx --yes gitnexus@${NPM_VERSION} mcp' --port ${GITNEXUS_PORT} --host 127.0.0.1 --healthEndpoint /healthz --healthCheck server" \
      >> "$LOG_FILE" 2>&1; then
    log "Docker carrier could not create the sidecar"
    return 1
  fi
  if wait_for_gateway && docker ps --format '{{.Names}}' | grep -qx "$CONTAINER_NAME"; then
    log "Docker MCP gateway healthy on port $GITNEXUS_PORT"
    return 0
  fi
  docker logs --tail 80 "$CONTAINER_NAME" >> "$LOG_FILE" 2>&1 || true
  log "Docker MCP gateway did not become healthy — inspect docker logs $CONTAINER_NAME"
  return 1
}

if command -v docker >/dev/null 2>&1; then
  start_with_docker
elif command -v npx >/dev/null 2>&1; then
  start_with_host_npx
else
  log "neither host npx nor Docker is available"
  exit 1
fi
