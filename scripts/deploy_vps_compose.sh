#!/usr/bin/env bash
# Non-interactive VPS deploy: SSH to host, pull main, rebuild api+web, restart.
# Expects ssh-agent to provide the deploy key (CI). Env: VPS_HOST, VPS_USER (default root).
set -euo pipefail

VPS_HOST="${VPS_HOST:?VPS_HOST is required}"
VPS_USER="${VPS_USER:-root}"

SSH_OPTS=(
  -o BatchMode=yes
  -o StrictHostKeyChecking=accept-new
)

exec ssh "${SSH_OPTS[@]}" "${VPS_USER}@${VPS_HOST}" bash -s <<'REMOTE'
set -euo pipefail
REPO_DIR="/docker/coherence-network/repo"
COMPOSE_DIR="/docker/coherence-network"
cd "$REPO_DIR"
git fetch origin main
git checkout main
git pull --ff-only origin main
cd "$COMPOSE_DIR"
docker compose build --no-cache api web
docker compose up -d api web
REMOTE
