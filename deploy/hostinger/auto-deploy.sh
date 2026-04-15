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

# Sense whether the RUNNING API is already at the target SHA. The previous
# guard only compared the repo's git HEAD to the target and skipped deploy
# when they matched — but that answered the wrong question. What the field
# needs to know is whether the CONTAINERS are serving the target code, not
# whether the filesystem mirrors it. When a manual `git pull` on the VPS
# advances the repo without rebuilding, subsequent deploys saw "no changes"
# and never rebuilt, so the running API stayed on the old SHA while the
# verification step kept failing. This query asks the living container.
RUNNING_SHA=""
HEALTH_JSON="$(docker compose -f "$COMPOSE_ROOT/docker-compose.yml" exec -T api \
    sh -lc 'curl -fsS --max-time 5 http://127.0.0.1:8000/api/health 2>/dev/null' \
    2>/dev/null || true)"
if [[ -n "$HEALTH_JSON" ]]; then
  RUNNING_SHA="$(printf '%s' "$HEALTH_JSON" \
    | python3 -c 'import sys, json
try:
    print((json.loads(sys.stdin.read()).get("deployed_sha") or "").strip())
except Exception:
    pass' 2>/dev/null || true)"
fi
RUNNING_SHORT="${RUNNING_SHA:0:12}"
[[ -z "$RUNNING_SHORT" ]] && RUNNING_SHORT="unknown"

if [[ "$OLD_SHA" == "$TARGET_SHA" && "$RUNNING_SHA" == "$TARGET_SHA" ]]; then
  log "Already flowing at ${TARGET_SHA:0:12} (repo and running API aligned)"
  exit 0
fi

if [[ "$OLD_SHA" == "$TARGET_SHA" ]]; then
  log "Repo aligned at ${TARGET_SHA:0:12} but running API is at ${RUNNING_SHORT} — rebuilding containers"
else
  log "Deploying ${OLD_SHA:0:12} -> ${TARGET_SHA:0:12} (running API at ${RUNNING_SHORT})"
  git reset --hard "$TARGET_SHA" >/dev/null
  git clean -fd >/dev/null
fi

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

# Give each container patient time to come up. A cold rebuild can take
# more than a minute from `up -d` through the first successful health
# response (python imports, router registration, DB connection warm-up).
# Fixed sleeps either wait too long on the fast path or give up too
# early on the slow path; a retry loop waits only as long as the
# container needs and no longer.
wait_for_api_health() {
  local deadline=$(( $(date +%s) + 180 ))
  while (( $(date +%s) < deadline )); do
    if docker compose exec -T api curl -fsS --max-time 5 http://127.0.0.1:8000/api/health >/dev/null 2>&1; then
      return 0
    fi
    sleep 3
  done
  return 1
}

if wait_for_api_health; then
  log "API health OK"
else
  log "FAIL: API health check did not reach ok within 180s after deploy"
  exit 1
fi

wait_for_web_root() {
  local deadline=$(( $(date +%s) + 120 ))
  while (( $(date +%s) < deadline )); do
    if docker compose exec -T web sh -lc 'wget -q -O - http://127.0.0.1:3000/ >/dev/null 2>&1' >/dev/null 2>&1; then
      return 0
    fi
    sleep 3
  done
  return 1
}

if wait_for_web_root; then
  log "Web health OK"
else
  log "FAIL: web root check failed after deploy"
  exit 1
fi

log "Deploy complete (${TARGET_SHA:0:12})"
