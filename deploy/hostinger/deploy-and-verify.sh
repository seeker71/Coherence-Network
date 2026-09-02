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
  echo "verify attempt $attempt failed (rc=$rc); likely rollout lag — sleeping ${backoff}s before retry" >&2
  sleep "$backoff"
  attempt=$((attempt + 1))
done
