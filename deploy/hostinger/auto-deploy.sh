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
git fetch --prune origin "+refs/heads/${BRANCH}:refs/remotes/origin/${BRANCH}" --quiet

if [[ -z "$TARGET_SHA" ]]; then
  TARGET_SHA="$(git rev-parse "origin/${BRANCH}")"
fi

if ! git cat-file -e "${TARGET_SHA}^{commit}" 2>/dev/null; then
  log "Target ${TARGET_SHA:0:12} missing after branch fetch; fetching explicit target"
  if ! git fetch origin "$TARGET_SHA" --quiet; then
    if [[ "$(git rev-parse --is-shallow-repository)" == "true" ]]; then
      log "Explicit target fetch failed; unshallowing ${BRANCH}"
      git fetch origin "$BRANCH" --unshallow --quiet || true
    fi
  fi
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

python3 - <<PY
import json
from pathlib import Path

sha = "${TARGET_SHA}"
config_path = Path("${REPO_DIR}/api/config/api.json")
config = json.loads(config_path.read_text())
config["deployed_sha"] = sha
web = config.setdefault("web", {})
web["deployed_sha"] = sha
web["updated_at"] = sha
tmp_path = config_path.with_suffix(config_path.suffix + ".tmp")
tmp_path.write_text(json.dumps(config, indent=2) + "\n")
tmp_path.replace(config_path)
PY

cd "$COMPOSE_ROOT"
# api + web + pulse share the same repo and SHA. Rebuilding all three
# on every push keeps the witness in step with what it's probing —
# when the web page's marker vocabulary drifts (as it did when locale
# messages started embedding "Something went wrong" inline), the
# pulse probe that reads those pages needs to redeploy alongside to
# pick up the updated marker, otherwise it silences real organs on
# false positives.
log "docker compose build api web pulse"
docker compose build api web pulse 2>&1 | tee -a "$LOG_FILE"
log "docker compose up -d api web pulse"
docker compose up -d api web pulse 2>&1 | tee -a "$LOG_FILE"

sync_field_docs() {
  if [[ ! -d "$REPO_DIR/docs/field" ]]; then
    log "field docs: no docs/field directory found (skipped)"
    return 0
  fi

  for target_parent in /app/docs /app/api/docs; do
    log "field docs: syncing docs/field to api:${target_parent}/field"
    docker compose exec -T api sh -lc "mkdir -p '${target_parent}' && rm -rf '${target_parent}/field'" \
      2>&1 | tee -a "$LOG_FILE"
    docker compose cp "$REPO_DIR/docs/field" "api:${target_parent}/field" \
      2>&1 | tee -a "$LOG_FILE"
  done
}

sync_field_docs

# Substrate auto-ingest. The coherence-substrate (content-addressed
# numeric lattice) lives in the api's database. Each deploy syncs the
# source-of-truth content (specs, ideas, vision-kb concepts, presences)
# into the container and re-runs the ingester. Re-ingestion is
# idempotent — content-addressed Blueprint NodeIDs hash-match existing
# cells. Memory cells live outside the repo (in ~/.claude/) and are
# skipped automatically. Non-blocking: any failure logs and the deploy
# still succeeds; the substrate's empty state is visible via the API.
# Runs AFTER wait_for_running api so the DB connection is stable.
sync_substrate_content() {
  log "substrate: syncing content + scripts into api container"
  docker compose exec -T api sh -lc 'rm -rf /app/specs /app/ideas /app/scripts /app/docs/vision-kb /app/docs/presences' \
    2>&1 | tee -a "$LOG_FILE" || true
  docker compose cp "$REPO_DIR/scripts" api:/app/scripts 2>&1 | tee -a "$LOG_FILE"
  docker compose cp "$REPO_DIR/specs" api:/app/specs 2>&1 | tee -a "$LOG_FILE"
  docker compose cp "$REPO_DIR/ideas" api:/app/ideas 2>&1 | tee -a "$LOG_FILE"
  if [[ -d "$REPO_DIR/docs/vision-kb" ]]; then
    docker compose cp "$REPO_DIR/docs/vision-kb" api:/app/docs/vision-kb 2>&1 | tee -a "$LOG_FILE"
  fi
  if [[ -d "$REPO_DIR/docs/presences" ]]; then
    docker compose cp "$REPO_DIR/docs/presences" api:/app/docs/presences 2>&1 | tee -a "$LOG_FILE"
  fi
}

run_substrate_ingest() {
  log "substrate: running coh_substrate.py ingest --all"
  set +e
  docker compose exec -T api sh -lc 'cd /app && python3 scripts/coh_substrate.py ingest --all' \
    2>&1 | tee -a "$LOG_FILE"
  local rc=$?
  set -e
  if [[ "$rc" -ne 0 ]]; then
    log "substrate: ingest returned $rc — non-blocking, deploy continues"
  fi
  return 0
}

# Wait for both containers to reach the "running" state in docker compose.
# The deeper health check is left to the workflow's Verify Public Deployment
# step, which curls the real public domain through the full request path
# (Traefik, Cloudflare, TLS). That sensor sees the organism the way every
# caller sees it and is the truth. Anything we could check here locally is
# a thinner, redundant version of the same question, and the previous
# `docker compose exec api curl` shape caught a false failure when curl
# happened not to be present inside the api container image.
wait_for_running() {
  local service="$1"
  local deadline=$(( $(date +%s) + 180 ))
  while (( $(date +%s) < deadline )); do
    local state
    state="$(docker compose ps --format '{{.Service}} {{.State}}' 2>/dev/null | awk -v s="$service" '$1==s {print $2}')"
    if [[ "$state" == "running" ]]; then
      return 0
    fi
    sleep 3
  done
  return 1
}

if wait_for_running api; then
  log "api container running"
else
  log "FAIL: api container did not reach running state within 180s"
  exit 1
fi

if wait_for_running web; then
  log "web container running"
else
  log "FAIL: web container did not reach running state within 180s"
  exit 1
fi

sync_substrate_content
run_substrate_ingest

log "Deploy complete (${TARGET_SHA:0:12}) — public health check runs next in CI"

# GitNexus sidecar (per specs/gitnexus-integration-experiment.md). Non-blocking:
# any failure is logged and the deploy still succeeds. The trial's spec
# explicitly counts install/staleness incidents as data, not setup bugs.
INSTALL_GITNEXUS="${COMPOSE_ROOT}/install-gitnexus.sh"
if [[ -x "$INSTALL_GITNEXUS" ]]; then
  REPO_DIR="$REPO_DIR" COMPOSE_ROOT="$COMPOSE_ROOT" LOG_FILE="$LOG_FILE" \
    "$INSTALL_GITNEXUS" || log "gitnexus: install script returned non-zero (deploy continues)"
else
  log "gitnexus: install script not present at $INSTALL_GITNEXUS (skipped)"
fi
