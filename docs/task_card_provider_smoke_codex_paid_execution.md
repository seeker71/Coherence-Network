# Cheap Executor Task Card

goal: |
  Capture codex paid execution proof by running the provider smoke commands and logging the model executor evidence.

files_allowed:
  - docs/task_card_provider_smoke_codex_paid_execution.md
  - docs/system_audit/cursor_fact_report_2026-03-01.json
  - docs/system_audit/model_executor_runs.jsonl

done_when:
  - "cursor_fact_report writes docs/system_audit/cursor_fact_report_2026-03-01.json"
  - "Public paid smoke task shows executor codex + force_paid context in GET response"
  - "docs/system_audit/model_executor_runs.jsonl has new entry for this task"

commands:
  - "cd api && /Users/ursmuff/source/Coherence-Network/api/.venv/bin/python scripts/cursor_fact_report.py --output docs/system_audit/cursor_fact_report_2026-03-01.json"
  - "API_URL=https://coherence-network-production.up.railway.app; TASK_ID=$(curl -s -X POST \"$API_URL/api/agent/tasks\" -H 'Content-Type: application/json' -d '{\"direction\":\"Provider smoke: codex paid execution proof\",\"task_type\":\"impl\",\"context\":{\"executor\":\"codex\",\"model_override\":\"openai/gpt-4o-mini\",\"force_paid_providers\":true}}' | jq -r '.id'); printf \"%s\n\" \"$TASK_ID\" | tee /tmp/codex_paid_smoke_task_id"
  - "API_URL=https://coherence-network-production.up.railway.app; TASK_ID=$(cat /tmp/codex_paid_smoke_task_id); curl -s \"$API_URL/api/agent/tasks/$TASK_ID\" | jq"
  - "API_URL=https://coherence-network-production.up.railway.app; curl -s \"$API_URL/api/runtime/endpoints/summary?limit=20\" | jq"
  - "API_URL=https://coherence-network-production.up.railway.app; TASK_ID=$(cat /tmp/codex_paid_smoke_task_id); curl -s \"$API_URL/api/runtime/events?limit=100\" | jq --arg id \"$TASK_ID\" '.[] | select(.metadata.task_id == $id and .metadata.tracking_kind == \"agent_tool_call\")'"
  - "API_URL=https://coherence-network-production.up.railway.app; curl -s \"$API_URL/api/friction/events?status=open&limit=20\" | jq"
  - "curl -sS https://coherence-network-production.up.railway.app/api/automation/usage/readiness | jq"
  - "curl -sS https://coherence-network-production.up.railway.app/api/automation/usage | jq"

constraints:
  - "No tests unless listed"
  - "No extra files"
  - "No extra edits"

proof_record:
  destination: docs/system_audit/model_executor_runs.jsonl
  fields:
    - model_used
    - input_tokens
    - output_tokens
    - attempts
    - commands_run
    - pass_fail
    - failure_reason

---

## Cursor paid execution (after OAuth login)

goal: |
  Confirm cursor paid execution success after OAuth login: create a task with executor cursor and force_paid_providers, then verify the task shows cursor routing and paid context.

done_when:
  - "POST returns task id; GET /api/agent/tasks/{id} shows context.executor or effective executor cursor and context.force_paid_providers true"
  - "No open paid_provider_blocked friction for this task (or task completes)"

commands:
  - "API_URL=https://coherence-network-production.up.railway.app; TASK_ID=$(curl -s -X POST \"$API_URL/api/agent/tasks\" -H 'Content-Type: application/json' -d '{\"direction\":\"Provider smoke: cursor paid execution success after oauth login\",\"task_type\":\"impl\",\"context\":{\"executor\":\"cursor\",\"force_paid_providers\":true}}' | jq -r '.id'); echo $TASK_ID | tee /tmp/cursor_paid_smoke_task_id"
  - "API_URL=https://coherence-network-production.up.railway.app; TASK_ID=$(cat /tmp/cursor_paid_smoke_task_id); curl -s \"$API_URL/api/agent/tasks/$TASK_ID\" | jq '{ id, status, context: .context }'"
  - "API_URL=https://coherence-network-production.up.railway.app; curl -s \"$API_URL/api/friction/events?status=open&limit=20\" | jq '[.[] | select(.block_type == \"paid_provider_blocked\")] | length'"
