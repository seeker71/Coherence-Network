#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEFAULT_API_BASE="http://127.0.0.1:${API_PORT:-18000}"
API_BASE="${API_BASE:-${API_URL:-${DEFAULT_API_BASE}}}"
IDEA_ID="demo-community-climate-marketplace"
CLEAR_TASKS=1

usage() {
  cat <<'USAGE'
Usage:
  ./scripts/reset_seed_demo_mvp_local.sh [--api-base <url>] [--idea-id <id>] [--keep-tasks]

Seeds one external, human-readable MVP example idea for localhost demos.
Default behavior clears task queue first so demo task lists are reproducible.

Examples:
  ./scripts/reset_seed_demo_mvp_local.sh
  ./scripts/reset_seed_demo_mvp_local.sh --api-base http://127.0.0.1:18100
  ./scripts/reset_seed_demo_mvp_local.sh --idea-id demo-community-climate-marketplace
USAGE
}

require_cmd() {
  local cmd="$1"
  if ! command -v "${cmd}" >/dev/null 2>&1; then
    echo "Missing required command: ${cmd}" >&2
    exit 1
  fi
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --api-base)
        API_BASE="$2"
        shift 2
        ;;
      --idea-id)
        IDEA_ID="$2"
        shift 2
        ;;
      --keep-tasks)
        CLEAR_TASKS=0
        shift
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        echo "Unknown argument: $1" >&2
        usage
        exit 2
        ;;
    esac
  done
}

api_json() {
  local method="$1"
  local path="$2"
  local body="${3:-}"
  local tmp
  tmp="$(mktemp)"
  local code

  if [[ -n "${body}" ]]; then
    code="$(curl -sS -o "${tmp}" -w "%{http_code}" -X "${method}" "${API_BASE}${path}" -H "Content-Type: application/json" --data "${body}" || true)"
  else
    code="$(curl -sS -o "${tmp}" -w "%{http_code}" -X "${method}" "${API_BASE}${path}" || true)"
  fi

  local response
  response="$(cat "${tmp}")"
  rm -f "${tmp}"
  printf "%s\n%s" "${code}" "${response}"
}

wait_for_health() {
  local i
  for i in $(seq 1 45); do
    if curl -sS -f "${API_BASE}/api/health" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  echo "API not ready at ${API_BASE}/api/health" >&2
  return 1
}

clear_task_queue() {
  local out
  out="$(api_json DELETE "/api/agent/tasks?confirm=clear")"
  local code body
  code="$(printf "%s" "${out}" | head -n1)"
  body="$(printf "%s" "${out}" | tail -n +2)"
  if [[ "${code}" != "204" ]]; then
    echo "Failed to clear task queue: HTTP ${code}" >&2
    printf "%s\n" "${body}" >&2
    return 1
  fi
}

ensure_idea() {
  local build_payload
  build_payload() {
    jq -n \
      --arg id "$1" \
      '{
        id: $id,
        name: "Community Climate Resilience Marketplace (Pilot)",
        description: "A two-sided marketplace connecting funders with local climate adaptation projects, with transparent progress and trust safeguards.",
        potential_value: 2400000,
        estimated_cost: 60000,
        confidence: 0.82,
        interfaces: ["/ideas", "/flow", "/tasks", "/contribute"],
        open_questions: [
          {
            question: "Will pilot partners commit within 30 days?",
            value_to_whole: 250000,
            estimated_cost: 6000
          },
          {
            question: "What trust protocol keeps quality high without slowing onboarding?",
            value_to_whole: 180000,
            estimated_cost: 12000
          },
          {
            question: "Can we keep funder-to-project matching under 7 days?",
            value_to_whole: 140000,
            estimated_cost: 9000
          }
        ]
      }'
  }

  local create_payload
  create_payload="$(build_payload "${IDEA_ID}")"

  local out
  out="$(api_json POST "/api/ideas" "${create_payload}")"
  local code body
  code="$(printf "%s" "${out}" | head -n1)"
  body="$(printf "%s" "${out}" | tail -n +2)"

  if [[ "${code}" == "409" ]]; then
    IDEA_ID="${IDEA_ID}-$(date -u +%Y%m%d%H%M%S)"
    create_payload="$(build_payload "${IDEA_ID}")"
    out="$(api_json POST "/api/ideas" "${create_payload}")"
    code="$(printf "%s" "${out}" | head -n1)"
    body="$(printf "%s" "${out}" | tail -n +2)"
  fi

  if [[ "${code}" != "201" ]]; then
    echo "Failed to create demo idea: HTTP ${code}" >&2
    printf "%s\n" "${body}" >&2
    return 1
  fi

  local patch_payload
  patch_payload='{"actual_value":120000,"actual_cost":45000,"confidence":0.74,"manifestation_status":"partial"}'
  out="$(api_json PATCH "/api/ideas/${IDEA_ID}" "${patch_payload}")"
  code="$(printf "%s" "${out}" | head -n1)"
  body="$(printf "%s" "${out}" | tail -n +2)"
  if [[ "${code}" != "200" ]]; then
    echo "Failed to update demo idea progress: HTTP ${code}" >&2
    printf "%s\n" "${body}" >&2
    return 1
  fi

  local answer_payload
  answer_payload='{"question":"Will pilot partners commit within 30 days?","answer":"Three pilot projects and two funders provided written commitments.","measured_delta":80000}'
  out="$(api_json POST "/api/ideas/${IDEA_ID}/questions/answer" "${answer_payload}")"
  code="$(printf "%s" "${out}" | head -n1)"
  body="$(printf "%s" "${out}" | tail -n +2)"
  if [[ "${code}" != "200" ]]; then
    echo "Failed to answer demo question: HTTP ${code}" >&2
    printf "%s\n" "${body}" >&2
    return 1
  fi
}

create_task() {
  local task_type="$1"
  local direction="$2"
  local status="$3"
  local progress="$4"
  local current_step="$5"
  local output="$6"

  local payload
  payload="$(jq -n \
    --arg t "${task_type}" \
    --arg d "${direction}" \
    --arg idea_id "${IDEA_ID}" \
    '{task_type: $t, direction: $d, context: {idea_id: $idea_id, demo_seed: true, source: "reset_seed_demo_mvp_local.sh"}}')"

  local out
  out="$(api_json POST "/api/agent/tasks" "${payload}")"
  local code body
  code="$(printf "%s" "${out}" | head -n1)"
  body="$(printf "%s" "${out}" | tail -n +2)"
  if [[ "${code}" != "201" ]]; then
    echo "Failed to create task (${task_type}): HTTP ${code}" >&2
    printf "%s\n" "${body}" >&2
    return 1
  fi

  local task_id
  task_id="$(printf "%s" "${body}" | jq -r '.id // empty')"
  if [[ -z "${task_id}" ]]; then
    echo "Task create response did not include id" >&2
    printf "%s\n" "${body}" >&2
    return 1
  fi

  if [[ "${status}" == "pending" ]]; then
    printf "%s\n" "${task_id}"
    return 0
  fi

  local patch_payload
  patch_payload="$(jq -n \
    --arg status "${status}" \
    --argjson progress "${progress}" \
    --arg step "${current_step}" \
    --arg out "${output}" \
    '{
      status: $status,
      progress_pct: $progress,
      current_step: (if ($step | length) > 0 then $step else null end),
      output: (if ($out | length) > 0 then $out else null end)
    }')"

  out="$(api_json PATCH "/api/agent/tasks/${task_id}" "${patch_payload}")"
  code="$(printf "%s" "${out}" | head -n1)"
  body="$(printf "%s" "${out}" | tail -n +2)"
  if [[ "${code}" != "200" ]]; then
    echo "Failed to patch task (${task_id}) to ${status}: HTTP ${code}" >&2
    printf "%s\n" "${body}" >&2
    return 1
  fi

  printf "%s\n" "${task_id}"
}

seed_tasks() {
  local task1 task2 task3
  task1="$(create_task "impl" "Publish pilot onboarding brief and confirm first three project partners." "completed" "100" "Published pilot brief and sent partner packet" "Pilot brief published; 3 project teams confirmed onboarding windows.")"
  task2="$(create_task "review" "Run trust and governance review for project vetting and funder safeguards." "running" "55" "Finalizing reviewer checklist and escalation policy" "")"
  task3="$(create_task "spec" "Draft month-one outreach experiment for funders and local project operators." "pending" "0" "" "")"

  printf "%s\n" "${task1}" "${task2}" "${task3}"
}

main() {
  parse_args "$@"
  require_cmd curl
  require_cmd jq

  cd "${ROOT_DIR}"

  echo "Using API base: ${API_BASE}"
  echo "Using demo idea id: ${IDEA_ID}"

  wait_for_health

  if (( CLEAR_TASKS == 1 )); then
    echo "Clearing existing task queue for reproducible demo state ..."
    clear_task_queue
  fi

  echo "Seeding demo idea and progress ..."
  ensure_idea

  echo "Seeding demo tasks ..."
  local task_ids_raw
  task_ids_raw="$(seed_tasks)"
  local task_ids
  task_ids="$(printf "%s" "${task_ids_raw}" | tr '\n' ' ' | xargs)"

  echo
  echo "Demo seed complete."
  echo "Idea: ${IDEA_ID}"
  echo "Links:"
  echo "  ${API_BASE}/api/ideas/${IDEA_ID}"
  echo "  ${API_BASE}/api/ideas"
  echo "  ${API_BASE}/api/agent/tasks"
  echo "Task IDs: ${task_ids}"
}

main "$@"
