#!/usr/bin/env bash
set -euo pipefail

COMPOSE_ROOT="${COMPOSE_ROOT:-/docker/coherence-network}"
REPO_DIR="${REPO_DIR:-${COMPOSE_ROOT}/repo}"
BRANCH="${BRANCH:-main}"
TARGET_SHA="${1:-}"
LOG_FILE="${LOG_FILE:-${COMPOSE_ROOT}/deploy.log}"

timestamp() {
  date -u +%Y-%m-%dT%H:%M:%SZ
}

log() {
  printf '%s — %s\n' "$(timestamp)" "$*" | tee -a "$LOG_FILE"
}

require_file() {
  local path="$1"
  if [[ ! -e "$path" ]]; then
    log "FAIL: missing required path $path"
    exit 1
  fi
}

require_file "$REPO_DIR/.git"
require_file "$COMPOSE_ROOT/docker-compose.yml"
require_file "$COMPOSE_ROOT/.env"

cd "$REPO_DIR"
OLD_SHA="$(git rev-parse HEAD)"
git fetch origin "$BRANCH" --quiet

if [[ -z "$TARGET_SHA" ]]; then
  TARGET_SHA="$(git rev-parse "origin/${BRANCH}")"
fi

git cat-file -e "${TARGET_SHA}^{commit}"

if [[ "$OLD_SHA" == "$TARGET_SHA" ]]; then
  log "No changes (still at ${OLD_SHA:0:12})"
  exit 0
fi

log "Deploying ${OLD_SHA:0:12} -> ${TARGET_SHA:0:12}"
git reset --hard "$TARGET_SHA" >/dev/null
git clean -fd >/dev/null

python3 - <<PY
from pathlib import Path

sha = "${TARGET_SHA}"
env_path = Path("${COMPOSE_ROOT}/.env")
lines = env_path.read_text().splitlines()
keys = {"GIT_COMMIT_SHA": sha, "DEPLOYED_SHA": sha}
out = []
seen = set()
for line in lines:
    if "=" not in line:
        out.append(line)
        continue
    key, value = line.split("=", 1)
    if key in keys:
        out.append(f"{key}={keys[key]}")
        seen.add(key)
    else:
        out.append(line)
for key, value in keys.items():
    if key not in seen:
        out.append(f"{key}={value}")
env_path.write_text("\n".join(out) + "\n")
PY

cd "$COMPOSE_ROOT"
docker compose build api web >> "$LOG_FILE" 2>&1
docker compose up -d api web >> "$LOG_FILE" 2>&1

sleep 10

if docker compose exec -T api curl -fsS --max-time 10 http://127.0.0.1:8000/api/health >/dev/null 2>&1; then
  log "API health OK"
else
  log "FAIL: API health check failed after deploy"
  exit 1
fi

if docker compose exec -T web sh -lc 'wget -q -O - http://127.0.0.1:3000/ >/dev/null 2>&1' >/dev/null 2>&1; then
  log "Web health OK"
else
  log "FAIL: web root check failed after deploy"
  exit 1
fi

log "Deploy complete (${TARGET_SHA:0:12})"
