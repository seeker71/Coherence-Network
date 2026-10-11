#!/usr/bin/env bash
set -Eeuo pipefail

DEPLOY_PATH="${1:?deploy path is required}"
TARGET_SHA="${2:?target SHA is required}"
PUBLIC_API_BASE="${3:?public API base URL is required}"
PUBLIC_WEB_BASE="${4:?public web base URL is required}"

# The caller holds /tmp/coh-deploy.lock around this whole script. Keep rollout
# and its public proof in one process so a queued cron caller cannot recreate
# services between auto-deploy returning and the readiness checks completing.
COMPOSE_ROOT="$DEPLOY_PATH" \
REPO_DIR="$DEPLOY_PATH/repo" \
BRANCH=main \
  bash "$DEPLOY_PATH/auto-deploy.sh" "$TARGET_SHA"

cd "$DEPLOY_PATH/repo"
attempt=1
max_attempts=3
backoff=30
repair_used=0

wait_for_api_readiness() {
  local deadline=$(( $(date +%s) + 180 ))
  while (( $(date +%s) < deadline )); do
    if docker compose -f "$DEPLOY_PATH/docker-compose.yml" exec -T api \
        sh -lc 'curl -fsS --max-time 15 http://127.0.0.1:8000/api/ping >/dev/null' \
        >/dev/null 2>&1; then
      return 0
    fi
    sleep 5
  done
  echo "API route repair did not become ready within 180 seconds" >&2
  return 1
}

repair_public_api_route() {
  echo "public API route disappeared after rollout — recreating api once to re-register Traefik" >&2
  if docker compose up --help 2>/dev/null | grep -q -- '--wait'; then
    if ! docker compose -f "$DEPLOY_PATH/docker-compose.yml" up -d \
        --wait --wait-timeout 180 --force-recreate api; then
      echo "waited API route repair did not become healthy; polling the same container" >&2
    fi
  else
    echo "Compose has no --wait support; recreating once and polling readiness" >&2
    docker compose -f "$DEPLOY_PATH/docker-compose.yml" up -d --force-recreate api
  fi
  wait_for_api_readiness
}

while :; do
  set +e
  VERIFY_REQUIRE_API_HEALTH_SHA=1 \
  VERIFY_REQUIRE_WEB_HEALTH_PROXY_SHA=1 \
  SHA_PARITY_PATIENCE_SECONDS=180 \
    ./scripts/verify_web_api_deploy.sh "$PUBLIC_API_BASE" "$PUBLIC_WEB_BASE"
  rc=$?
  set -e
  if [[ "$rc" -eq 0 ]]; then
    break
  fi
  if [[ "$attempt" -ge "$max_attempts" ]]; then
    echo "verify_web_api_deploy.sh failed after $attempt attempts (rc=$rc)" >&2
    exit "$rc"
  fi
  if [[ "$repair_used" -eq 0 ]] \
    && ! curl -fsS --max-time 15 "$PUBLIC_API_BASE/api/ping" >/dev/null 2>&1; then
    repair_public_api_route
    repair_used=1
  fi
  echo "verify attempt $attempt failed (rc=$rc); API route reconciled when needed — sleeping ${backoff}s before retry" >&2
  sleep "$backoff"
  attempt=$((attempt + 1))
done
