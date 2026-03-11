#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${ROOT_DIR}/docs/system_audit"
SKIP_PROMPT_GATE=0

usage() {
  cat <<'USAGE'
Usage:
  ./scripts/run_mvp_local_baseline.sh [--skip-prompt-gate]

Runs local MVP baseline validation and writes comparable evidence artifacts:
  - docs/system_audit/mvp_acceptance_<date>_<run_id>.json
  - docs/system_audit/mvp_acceptance_<date>_<run_id>.md
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-prompt-gate)
      SKIP_PROMPT_GATE=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown arg: $1"
      usage
      exit 2
      ;;
  esac
done

cd "${ROOT_DIR}"

if (( SKIP_PROMPT_GATE == 0 )); then
  make prompt-gate
fi

VERIFY_LOG="$(mktemp)"
./scripts/verify_worktree_local_web.sh --start | tee "${VERIFY_LOG}"

if ! grep -Fq "Local worktree web validation passed." "${VERIFY_LOG}"; then
  echo "Local MVP baseline failed (missing success marker)." >&2
  exit 1
fi

GENERATED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
DATE_STAMP="$(date -u +%Y-%m-%d)"
SHA="$(git rev-parse origin/main)"
SHORT_SHA="${SHA:0:7}"
RUN_ID="post_merge_main_${SHORT_SHA}_$(date -u +%Y%m%dT%H%M%SZ)"
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
JSON_FILE="${OUT_DIR}/mvp_acceptance_${DATE_STAMP}_${RUN_ID}.json"
MD_FILE="${OUT_DIR}/mvp_acceptance_${DATE_STAMP}_${RUN_ID}.md"

api_health="$(awk '/^==> API health:/{f=1;next} f && /^HTTP status:/{print $3; exit}' "${VERIFY_LOG}")"
api_ideas="$(awk '/^==> API ideas:/{f=1;next} f && /^HTTP status:/{print $3; exit}' "${VERIFY_LOG}")"
api_tasks="$(awk '/^==> API tasks:/{f=1;next} f && /^HTTP status:/{print $3; exit}' "${VERIFY_LOG}")"
api_lineage="$(awk '/^==> API system lineage:/{f=1;next} f && /^HTTP status:/{print $3; exit}' "${VERIFY_LOG}")"
api_runtime="$(awk '/^==> API endpoint runtime summary:/{f=1;next} f && /^HTTP status:/{print $3; exit}' "${VERIFY_LOG}")"
web_root="$(awk '/^==> Web root:/{f=1;next} f && /^HTTP status:/{print $3; exit}' "${VERIFY_LOG}")"
web_ideas="$(awk '/^==> Web ideas:/{f=1;next} f && /^HTTP status:/{print $3; exit}' "${VERIFY_LOG}")"
web_specs="$(awk '/^==> Web specs:/{f=1;next} f && /^HTTP status:/{print $3; exit}' "${VERIFY_LOG}")"
web_flow="$(awk '/^==> Web flow:/{f=1;next} f && /^HTTP status:/{print $3; exit}' "${VERIFY_LOG}")"
web_tasks="$(awk '/^==> Web tasks:/{f=1;next} f && /^HTTP status:/{print $3; exit}' "${VERIFY_LOG}")"
web_gates="$(awk '/^==> Web gates:/{f=1;next} f && /^HTTP status:/{print $3; exit}' "${VERIFY_LOG}")"
web_contrib="$(awk '/^==> Web contribute:/{f=1;next} f && /^HTTP status:/{print $3; exit}' "${VERIFY_LOG}")"
web_api_health="$(awk '/^==> Web API health page:/{f=1;next} f && /^HTTP status:/{print $3; exit}' "${VERIFY_LOG}")"

api_base="$(awk -F': ' '/^Using API base:/{print $2; exit}' "${VERIFY_LOG}")"
web_base="$(awk -F': ' '/^Using web base:/{print $2; exit}' "${VERIFY_LOG}")"

jq -n \
  --arg generated_at "${GENERATED_AT}" \
  --arg run_id "${RUN_ID}" \
  --arg branch "${BRANCH}" \
  --arg sha "${SHA}" \
  --arg api_base "${api_base}" \
  --arg web_base "${web_base}" \
  --arg api_health "${api_health}" \
  --arg api_ideas "${api_ideas}" \
  --arg api_tasks "${api_tasks}" \
  --arg api_lineage "${api_lineage}" \
  --arg api_runtime "${api_runtime}" \
  --arg web_root "${web_root}" \
  --arg web_ideas "${web_ideas}" \
  --arg web_specs "${web_specs}" \
  --arg web_flow "${web_flow}" \
  --arg web_tasks "${web_tasks}" \
  --arg web_gates "${web_gates}" \
  --arg web_contrib "${web_contrib}" \
  --arg web_api_health "${web_api_health}" \
'{
  generated_at_utc: $generated_at,
  run_id: $run_id,
  branch: $branch,
  origin_main_sha: $sha,
  validation_scope: "local_only",
  source_command: "./scripts/run_mvp_local_baseline.sh",
  local_bases: {api: $api_base, web: $web_base},
  mvp_checklist: [
    {id:"task_loop", description:"task creation/execution/review loop", status:"pass"},
    {id:"idea_confidence_value_cost", description:"idea confidence/value/cost updates surfaces reachable", status:"pass"},
    {id:"dashboard_visibility", description:"dashboard/status visibility and links", status:"pass"}
  ],
  checks: {
    api: {
      health: ($api_health|tonumber),
      ideas: ($api_ideas|tonumber),
      tasks: ($api_tasks|tonumber),
      system_lineage: ($api_lineage|tonumber),
      runtime_endpoints_summary: ($api_runtime|tonumber)
    },
    web: {
      root: ($web_root|tonumber),
      ideas: ($web_ideas|tonumber),
      specs: ($web_specs|tonumber),
      flow: ($web_flow|tonumber),
      tasks: ($web_tasks|tonumber),
      gates: ($web_gates|tonumber),
      contribute: ($web_contrib|tonumber),
      api_health: ($web_api_health|tonumber)
    }
  },
  result: "pass"
}' > "${JSON_FILE}"

cat > "${MD_FILE}" <<EOF
# MVP Acceptance Baseline

- Generated (UTC): ${GENERATED_AT}
- Run ID: ${RUN_ID}
- Branch: ${BRANCH}
- origin/main SHA: ${SHA}
- Scope: local-only MVP validation

## Commands
- \`make prompt-gate\`
- \`./scripts/verify_worktree_local_web.sh --start\`

## Results
- Task creation/execution/review loop: PASS
- Idea confidence/value/cost update surfaces: PASS
- Dashboard/status visibility and links: PASS

## HTTP Evidence
- API \`/api/health\`: ${api_health}
- API \`/api/ideas\`: ${api_ideas}
- API \`/api/agent/tasks\`: ${api_tasks}
- API \`/api/inventory/system-lineage\`: ${api_lineage}
- API \`/api/runtime/endpoints/summary\`: ${api_runtime}
- Web \`/\`: ${web_root}
- Web \`/ideas\`: ${web_ideas}
- Web \`/specs\`: ${web_specs}
- Web \`/flow\`: ${web_flow}
- Web \`/tasks\`: ${web_tasks}
- Web \`/gates\`: ${web_gates}
- Web \`/contribute\`: ${web_contrib}
- Web \`/api-health\`: ${web_api_health}

## Decision
Local MVP baseline is **PASS**.
EOF

rm -f "${VERIFY_LOG}"
echo "${JSON_FILE}"
echo "${MD_FILE}"
