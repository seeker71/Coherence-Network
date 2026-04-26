#!/usr/bin/env bash
set -euo pipefail

REPO="${REPO:-seeker71/Coherence-Network}"
WORKFLOW="${WORKFLOW:-hostinger-auto-deploy.yml}"
API_URL="${1:-${PUBLIC_API_BASE_URL:-https://api.coherencycoin.com}}"
WEB_URL="${2:-${PUBLIC_WEB_BASE_URL:-https://coherencycoin.com}}"
TIMEOUT_SECONDS="${DEPLOY_SETTLE_TIMEOUT_SECONDS:-900}"
POLL_SECONDS="${DEPLOY_SETTLE_POLL_SECONDS:-15}"

need() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "missing required command: $1" >&2
    exit 2
  fi
}

need gh
need curl
need python3

json_get() {
  local expr="$1"
  python3 -c "import json,sys
try:
    data=json.load(sys.stdin)
    print(${expr})
except Exception:
    print('')"
}

latest_main_sha() {
  gh api "repos/${REPO}/branches/main" --jq '.commit.sha'
}

deployed_sha() {
  curl -fsS "${API_URL%/}/api/health" \
    | json_get "data.get('deployed_sha') or ''" \
    || true
}

main_head_sha() {
  curl -fsS "${API_URL%/}/api/gates/main-head" \
    | json_get "data.get('sha') or ''" \
    || true
}

latest_hostinger_run() {
  local runs_json
  runs_json="$(
    gh run list \
      --repo "$REPO" \
      --workflow "$WORKFLOW" \
      --branch main \
      --limit 1 \
      --json databaseId,status,conclusion,headSha,displayTitle,createdAt
  )"
  RUNS_JSON="$runs_json" python3 - <<'PY'
import json
import os

runs = json.loads(os.environ.get("RUNS_JSON") or "[]")
if not runs:
    print("")
else:
    run = runs[0]
    print("\037".join(str(run.get(k) or "-") for k in (
        "databaseId", "status", "conclusion", "headSha", "displayTitle"
    )))
PY
}

deadline=$(( $(date +%s) + TIMEOUT_SECONDS ))
last_run_id=""

echo "Settling public deploy for ${REPO}"
echo "API: ${API_URL}"
echo "Web: ${WEB_URL}"
echo "Workflow: ${WORKFLOW}"

while :; do
  target_sha="$(latest_main_sha)"
  gates_sha="$(main_head_sha)"
  live_sha="$(deployed_sha)"

  if [[ -n "$live_sha" && "$live_sha" == "$target_sha" ]]; then
    echo "deploy-sha: live=${live_sha} target=${target_sha}"
    break
  fi

  IFS=$'\037' read -r run_id run_status run_conclusion run_sha run_title <<<"$(latest_hostinger_run)"

  if [[
    -n "${run_id:-}" &&
    "${run_id}" != "-" &&
    "${run_status}" == "completed" &&
    "${run_conclusion}" == "success" &&
    -n "${live_sha}" &&
    "${live_sha}" == "${run_sha}" &&
    "${run_sha}" != "${target_sha}"
  ]]; then
    echo "deploy-sha: live=${live_sha} matches latest Hostinger deploy"
    echo "main-sha: ${target_sha} has no newer Hostinger deploy; treating as non-runtime/process-only drift"
    break
  fi

  if [[ -n "${run_id}" && "${run_id}" != "-" && "${run_id}" != "${last_run_id}" ]]; then
    echo "hostinger-run: id=${run_id} status=${run_status} conclusion=${run_conclusion:-pending} sha=${run_sha}"
    echo "title: ${run_title}"
    last_run_id="${run_id}"
  fi

  if [[ -z "${run_id:-}" || "${run_id}" == "-" ]]; then
    echo "waiting: no Hostinger run visible yet for main"
  elif [[ "${run_sha}" != "${target_sha}" ]]; then
    echo "waiting: latest Hostinger run targets ${run_sha}; main is ${target_sha}"
  elif [[ "${run_status}" == "completed" && "${run_conclusion}" == "success" ]]; then
    echo "hostinger-run: success for ${run_sha}; waiting for health SHA parity"
  elif [[ "${run_status}" == "completed" ]]; then
    echo "hostinger-run: ${run_conclusion} for current main ${run_sha}" >&2
    echo "Run: gh run view ${run_id} --repo ${REPO} --log-failed" >&2
    exit 1
  else
    echo "waiting: run ${run_id} ${run_status}; gates=${gates_sha:-unknown} live=${live_sha:-unknown} target=${target_sha}"
  fi

  if (( $(date +%s) >= deadline )); then
    echo "timeout waiting for deploy SHA parity: live=${live_sha:-unknown} target=${target_sha}" >&2
    exit 1
  fi
  sleep "$POLL_SECONDS"
done

VERIFY_REQUIRE_API_HEALTH_SHA="${VERIFY_REQUIRE_API_HEALTH_SHA:-0}" \
  "$(dirname "$0")/verify_web_api_deploy.sh" "$API_URL" "$WEB_URL"
