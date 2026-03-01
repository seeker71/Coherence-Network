# Cheap Executor Task Card

goal: |
  Capture free-provider execution proof by running the openrouter/free smoke commands and logging the execution evidence.

files_allowed:
  - docs/task_card_provider_smoke_free_provider_execution.md
  - docs/system_audit/model_executor_runs.jsonl

done_when:
  - "POST /api/agent/tasks returns an id and GET shows context.route_decision.is_paid_provider == false"
  - "Open friction feed filtered for the task has zero paid_provider_blocked rows"
  - "docs/system_audit/model_executor_runs.jsonl has new entry for this task"

commands:
  - "API_URL=https://coherence-network-production.up.railway.app; TASK_ID=$(curl -s -X POST \"$API_URL/api/agent/tasks\" -H 'Content-Type: application/json' -d '{\"direction\":\"Provider smoke: free-provider execution proof. Do minimal safe work and return a short confirmation.\",\"task_type\":\"impl\",\"context\":{\"executor\":\"openclaw\",\"model_override\":\"openrouter/free\"}}' | jq -r '.id'); printf \"%s\n\" \"$TASK_ID\" | tee /tmp/free_provider_smoke_task_id"
  - "API_URL=https://coherence-network-production.up.railway.app; TASK_ID=$(cat /tmp/free_provider_smoke_task_id); curl -s \"$API_URL/api/agent/tasks/$TASK_ID\" | jq '{ id, status, is_paid: .context.route_decision.is_paid_provider, provider: .context.route_decision.provider, model: .context.route_decision.model }'"
  - "API_URL=https://coherence-network-production.up.railway.app; TASK_ID=$(cat /tmp/free_provider_smoke_task_id); curl -s \"$API_URL/api/friction/events?status=open&limit=20\" | jq --arg id \"$TASK_ID\" '[.[] | select(.block_type == \"paid_provider_blocked\" and (.metadata.task_id == $id))]'"

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
