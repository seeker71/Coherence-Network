#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

fixture_dir="$(mktemp -d)"
trap 'rm -rf "$fixture_dir"' EXIT

target_sha="11320490e197780f0393b8fee700442b2a82c658"
live_sha="5dad3d6f0d7f48495b9644fde0e8d26572962ae1"
run_id="26888975044"

mkdir -p "$fixture_dir/bin"

cat >"$fixture_dir/bin/gh" <<'SH'
#!/usr/bin/env bash
set -euo pipefail

case "$*" in
  "api repos/seeker71/Coherence-Network/branches/main --jq .commit.sha")
    printf '%s\n' "$TARGET_SHA"
    ;;
  "run list --repo seeker71/Coherence-Network --workflow hostinger-auto-deploy.yml --branch main --limit 1 --json databaseId,status,conclusion,headSha,displayTitle,createdAt")
    printf '[{"databaseId":%s,"status":"completed","conclusion":"failure","headSha":"%s","displayTitle":"Hostinger Auto Deploy","createdAt":"2026-06-03T13:46:30Z"}]\n' "$RUN_ID" "$TARGET_SHA"
    ;;
  workflow\ run\ hostinger-auto-deploy.yml\ --repo\ seeker71/Coherence-Network\ -r\ main\ -f\ sha=*)
    printf '%s\n' "$*" >> "$GH_WORKFLOW_RUN_LOG"
    ;;
  *)
    echo "unexpected gh command: $*" >&2
    exit 9
    ;;
esac
SH
chmod +x "$fixture_dir/bin/gh"

cat >"$fixture_dir/bin/curl" <<'SH'
#!/usr/bin/env bash
set -euo pipefail

url="${*: -1}"
case "$url" in
  http://api.example/api/health)
    printf '{"deployed_sha":"%s"}\n' "$LIVE_SHA"
    ;;
  http://api.example/api/gates/main-head)
    printf '{"sha":"%s"}\n' "$TARGET_SHA"
    ;;
  *)
    echo "unexpected curl url: $url" >&2
    exit 9
    ;;
esac
SH
chmod +x "$fixture_dir/bin/curl"

workflow_log="$fixture_dir/workflow-run.log"

set +e
output="$(
  PATH="$fixture_dir/bin:$PATH" \
  TARGET_SHA="$target_sha" \
  LIVE_SHA="$live_sha" \
  RUN_ID="$run_id" \
  GH_WORKFLOW_RUN_LOG="$workflow_log" \
  DEPLOY_SETTLE_TIMEOUT_SECONDS=3 \
  DEPLOY_SETTLE_POLL_SECONDS=1 \
  "$ROOT_DIR/scripts/settle_public_deploy.sh" "http://api.example" "http://web.example" 2>&1
)"
rc=$?
set -e

test "$rc" -eq 1
grep -F "hostinger-run: failure for current main $target_sha" <<<"$output" >/dev/null
grep -F "dispatching Hostinger deploy for $target_sha" <<<"$output" >/dev/null
grep -F "waiting: deploy dispatch accepted for $target_sha" <<<"$output" >/dev/null
test "$(wc -l < "$workflow_log" | tr -d ' ')" = "1"
grep -F "workflow run hostinger-auto-deploy.yml --repo seeker71/Coherence-Network -r main -f sha=$target_sha" "$workflow_log" >/dev/null

echo "PASS: settle_public_deploy dispatches one bounded deploy rerun"
