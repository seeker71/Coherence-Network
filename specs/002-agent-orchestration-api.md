# Spec: Agent Orchestration API

*Format: [specs/TEMPLATE.md](TEMPLATE.md)*

## Purpose

Provide an API that Cursor (or any client) can call to submit agent tasks, get model routing decisions, and track status—enabling guided Claude Code execution from within Cursor with observability. All agent API items below are implemented; verification: `cd api && pytest tests/test_agent.py -v`.

## Requirements

- [x] POST /api/agent/tasks — Submit task, returns task_id + routed model + suggested command
- [x] GET /api/agent/tasks — List tasks with optional status/task_type filters and pagination (limit, offset)
- [x] GET /api/agent/tasks/attention — List tasks with status needs_decision or failed only
- [x] GET /api/agent/tasks/count — Lightweight counts (total, by_status) for dashboards
- [x] GET /api/agent/tasks/{id} — Get task by id (full shape: command, output, progress_pct, current_step, decision_prompt, decision)
- [x] GET /api/agent/tasks/{id}/log — Full task log (prompt, command, output); file streamed during execution
- [x] PATCH /api/agent/tasks/{id} — Update task (status, output, progress_pct, current_step, decision_prompt, decision); Telegram alert on needs_decision/failed
- [x] GET /api/agent/route — Route-only: given task_type (and optional executor), return model + command template (no persistence)
- [x] GET /api/agent/usage — Per-model usage and routing summary
- [x] GET /api/agent/monitor-issues — Monitor issues from automated pipeline check (spec 027)
- [x] GET /api/agent/fatal-issues — Unrecoverable failures; { "fatal": false } or { "fatal": true, ... } (autonomous pipeline)
- [x] GET /api/agent/metrics — Task metrics: success rate, execution time, by task_type, by model (spec 027)
- [x] GET /api/agent/effectiveness — Pipeline effectiveness: throughput, success rate, issues, progress, goal_proximity, heal_resolved_count
- [x] GET /api/agent/status-report — Hierarchical status (Layer 0 Goal → 3 Attention); meta_questions when file present
- [x] GET /api/agent/pipeline-status — Pipeline visibility: running, pending, recent_completed, attention, project_manager, live_tail
- [x] POST /api/agent/telegram/webhook — Receive Telegram updates; commands: /status, /tasks, /task, /reply, /attention, /usage, /direction
- [x] GET /api/agent/telegram/diagnostics — Diagnostics: webhook events, send results, config (masked)
- [x] POST /api/agent/telegram/test-send — Send test message to TELEGRAM_CHAT_IDS (debugging)
- [x] Tasks stored in memory for MVP; structure supports future PostgreSQL migration

## API Contract

### `POST /api/agent/tasks`

**Request**
```json
{
  "direction": "Add GET /api/projects endpoint",
  "task_type": "impl",
  "context": { "spec_ref": "specs/003-projects.md", "executor": "claude" }
}
```

- `direction`: string (required, 1–5000 chars)
- `task_type`: string, enum: spec | test | impl | review | heal
- `context`: object (optional); `executor`: "claude" (default) or "cursor" selects command template

**Response 201**
```json
{
  "id": "task_abc123",
  "direction": "Add GET /api/projects endpoint",
  "task_type": "impl",
  "status": "pending",
  "model": "ollama/glm-4.7-flash:latest",
  "command": "claude -p \"Add GET /api/projects endpoint\" ...",
  "created_at": "2026-02-12T12:00:00Z"
}
```

**Response 422** — Invalid task_type, empty direction, or direction > 5000 chars

### `GET /api/agent/tasks`

**Query params:** `status` (optional), `task_type` (optional), `limit` (default 20, 1–100), `offset` (default 0, ≥ 0)

**Response 200**
```json
{
  "tasks": [
    {
      "id": "task_abc123",
      "direction": "Add GET /api/projects endpoint",
      "task_type": "impl",
      "status": "pending",
      "model": "ollama/glm-4.7-flash:latest",
      "progress_pct": null,
      "current_step": null,
      "decision_prompt": null,
      "decision": null,
      "created_at": "2026-02-12T12:00:00Z",
      "updated_at": null
    }
  ],
  "total": 1
}
```

List items omit `command` and `output`.

### `GET /api/agent/tasks/attention`

**Query params:** `limit` (default 20, 1–100)

**Response 200** — Same list shape; only tasks with status `needs_decision` or `failed`.

**Response 422** — Invalid limit (e.g. limit=0 or limit=101)

### `GET /api/agent/tasks/count`

**Response 200**
```json
{
  "total": 42,
  "by_status": { "pending": 5, "running": 1, "completed": 30, "failed": 4, "needs_decision": 2 }
}
```

### `GET /api/agent/tasks/{id}`

**Response 200** — Full task (includes `command`, `output`, `progress_pct`, `current_step`, `decision_prompt`, `decision`).
**Response 404** — `{ "detail": "Task not found" }`

Path parameter `{id}` must not match fixed segments: `/attention` and `/count` are distinct routes; only unknown segments are treated as task ids.

### `GET /api/agent/tasks/{id}/log`

**Response 200** — `{ "task_id": "...", "log": "...", "command": "...", "output": "..." }` when the task log file exists.
**Response 404** — Task not found (non-existent task id), or task exists but log file is missing on disk. Body: `{ "detail": "Task not found" }` for unknown task id; `{ "detail": "Task log not found" }` when task exists but log file is missing.

### `PATCH /api/agent/tasks/{id}`

**Request** — At least one field required.
```json
{ "status": "running" }
```
or
```json
{ "status": "completed", "output": "Implementation complete. Tests pass." }
```
or
```json
{ "progress_pct": 50, "current_step": "Running tests", "decision_prompt": "Proceed?", "decision": "yes" }
```

- `status`: enum pending | running | completed | failed | needs_decision
- `output`: string (optional)
- `progress_pct`: int 0–100 (optional)
- `current_step`: string (optional)
- `decision_prompt`: string (optional)
- `decision`: string (optional); when set and task is needs_decision, status → running

**Response 200** — Updated task
**Response 400** — No fields provided (empty body or all optional fields null/absent) — "At least one field required"
**Response 404** — Task not found
**Response 422** — Invalid status or progress_pct out of range (e.g. < 0 or > 100)

### `GET /api/agent/route?task_type=impl&executor=claude`

**Query params:** `task_type` (required), `executor` (optional, default "claude": claude | cursor)

**Response 200**
```json
{
  "task_type": "impl",
  "model": "ollama/glm-4.7-flash:latest",
  "command_template": "claude -p \"{{direction}}\" ...",
  "tier": "local",
  "executor": "claude"
}
```

**Response 422** — Missing or invalid task_type

### `GET /api/agent/usage`

**Response 200** — `{ "by_model": {...}, "routing": {...} }`

### `GET /api/agent/monitor-issues`

**Response 200** — `{ "issues": [...], "last_check": "..." | null }`

### `GET /api/agent/metrics`

**Response 200** — `{ "success_rate": {...}, "execution_time": {...}, "by_task_type": {...}, "by_model": {...} }`

### `GET /api/agent/pipeline-status`

**Response 200** — `{ "running": [...], "pending": [...], "recent_completed": [...], "attention": { "stuck", "repeated_failures", "low_success_rate", "flags" }, "project_manager": {...} | null, "running_by_phase": {...}, ... }`. Running task may include `live_tail` (last lines of task log).

### `POST /api/agent/telegram/webhook`

**Request** — Telegram Update JSON (Body).

**Response 200** — `{ "ok": true }`. Commands: /status, /tasks [status], /task {id}, /reply {id} {decision}, /attention, /usage, /direction "..." or plain text to create task.

### `GET /api/agent/telegram/diagnostics`

**Response 200** — `{ "config": { "has_token", "token_prefix", "chat_ids", "allowed_user_ids" }, "webhook_events": [...], "send_results": [...] }`

### `POST /api/agent/telegram/test-send`

**Query param:** `text` (optional)

**Response 200** — `{ "ok": true/false, "results": [...] }` or `{ "ok": false, "error": "..." }`

## Data Model

```yaml
AgentTask:
  id: string (uuid or short id)
  direction: string
  task_type: enum(spec, test, impl, review, heal)
  status: enum(pending, running, completed, failed, needs_decision)
  model: string
  command: string
  output: string | null
  progress_pct: int 0-100 | null
  current_step: string | null
  decision_prompt: string | null
  decision: string | null
  context: object | null
  created_at: datetime
  updated_at: datetime | null
```

List items omit `command` and `output`; full GET includes them.

## Routing Logic (from docs/MODEL-ROUTING.md)

| task_type | model | tier |
|-----------|-------|------|
| spec | ollama/glm-4.7-flash:latest | local |
| test | ollama/glm-4.7-flash:latest | local |
| impl | ollama/glm-4.7-flash:latest | local |
| review | ollama/glm-4.7-flash:latest | local |
| heal | claude-3-5-haiku-20241022 | claude |

Fallback: use `context.model_override` for glm-5:cloud (cloud) or claude (claude). Command template uses `executor`: `claude` (default) or `cursor` (Cursor CLI).

## Files to Create/Modify

- `api/app/models/agent.py` — Pydantic models
- `api/app/services/agent_service.py` — routing + in-memory store + get_review_summary, get_usage_summary, get_pipeline_status, get_attention_tasks, get_task_count
- `api/app/services/telegram_adapter.py` — Telegram send_alert, send_reply, parse_command
- `api/app/services/telegram_diagnostics.py` — record_webhook, get_webhook_events, get_send_results
- `api/app/routers/agent.py` — route handlers + webhook + alert hook
- `api/app/main.py` — include agent router
- `api/tests/test_agent.py` — acceptance and edge-case tests

## Acceptance Tests

See `api/tests/test_agent.py`. All must pass.

**Core**
- test_post_task_returns_201_with_routed_model_and_command
- test_get_tasks_list_with_filters
- test_get_task_by_id_404_when_missing
- test_get_task_by_id_returns_full_task
- test_get_task_by_id_includes_output_when_set
- test_patch_task_updates_status
- test_patch_task_invalid_status_returns_422
- test_patch_task_progress_pct_out_of_range_returns_422
- test_post_task_invalid_task_type_returns_422
- test_post_task_empty_direction_returns_422
- test_post_task_direction_too_long_returns_422
- test_route_endpoint_returns_model_and_template
- test_spec_tasks_route_to_local, test_test_tasks_route_to_local, test_review_tasks_route_to_local
- test_impl_tasks_route_to_local
- test_heal_tasks_route_to_claude
- test_cursor_executor_routes_to_cursor_cli
- test_patch_accepts_progress_and_decision
- test_reply_command_records_decision_and_updates_status
- test_attention_lists_only_needs_decision_and_failed
- test_attention_limit_validation
- test_task_count_returns_200
- test_usage_endpoint_returns_200
- test_metrics_endpoint_returns_200
- test_pipeline_status_returns_200
- test_monitor_issues_returns_200
- test_task_log_returns_command_and_output
- test_task_log_404_when_log_file_missing
- test_list_items_omit_command_and_output
- test_root_returns_200
- test_agent_runner_polls_and_executes_one_task (smoke)
- test_update_spec_coverage_dry_run
- test_telegram_webhook_returns_200
- test_telegram_diagnostics_returns_200
- test_telegram_test_send_returns_structure

**Edge-case (see Edge-Case Tests table)**
- test_patch_task_404_when_missing
- test_patch_task_empty_body_returns_400
- test_patch_all_fields_explicit_null_returns_400
- test_route_without_task_type_returns_422
- test_route_invalid_task_type_returns_422
- test_get_tasks_limit_zero_returns_422
- test_get_tasks_limit_over_max_returns_422
- test_get_tasks_offset_negative_returns_422
- test_get_tasks_invalid_status_returns_422
- test_get_tasks_status_pending_returns_only_pending
- test_fixed_path_attention_not_matched_as_task_id
- test_fixed_path_count_not_matched_as_task_id
- test_task_id_path_resolves_to_task
- test_task_log_404_when_task_missing
- test_task_log_404_when_log_file_missing
- test_patch_progress_pct_negative_returns_422
- test_patch_progress_pct_over_100_returns_422
- test_patch_progress_pct_boundary_0_and_100_succeed
- test_patch_progress_pct_string_returns_422
- test_post_task_missing_direction_returns_422
- test_post_task_direction_null_returns_422
- test_post_task_missing_task_type_returns_422
- test_list_empty_returns_zero_tasks_and_total
- test_pagination_offset_beyond_total_returns_empty_tasks
- test_post_task_direction_5000_chars_returns_201
- test_telegram_webhook_no_message_returns_200
- test_task_count_empty_store_returns_zero_total
- test_task_log_returns_output_from_task_when_set
- test_route_executor_optional_default_claude
- test_get_tasks_limit_one_returns_at_most_one
- test_monitor_issues_empty_when_no_file
- test_telegram_test_send_accepts_optional_text_param

**Verification:** `cd api && pytest tests/test_agent.py -v` — all tests must pass; do not change tests to make implementation pass.

## Edge-Case Tests

The following edge cases must be covered by tests in `api/tests/test_agent.py`:

| Case | Endpoint / scenario | Expected |
|------|---------------------|----------|
| **PATCH 404** | PATCH /api/agent/tasks/{id} with non-existent id | 404, detail "Task not found" |
| **PATCH 400** | PATCH with empty body (no fields or all optional null/absent) | 400, detail "At least one field required" |
| **PATCH progress_pct negative** | PATCH with progress_pct &lt; 0 | 422 |
| **PATCH progress_pct &gt; 100** | PATCH with progress_pct &gt; 100 | 422 |
| **Route 422** | GET /api/agent/route without `task_type` query param | 422 |
| **List limit=0** | GET /api/agent/tasks?limit=0 | 422 |
| **List limit&gt;100** | GET /api/agent/tasks?limit=101 | 422 |
| **List offset&lt;0** | GET /api/agent/tasks?offset=-1 | 422 |
| **List status filter** | GET /api/agent/tasks?status=pending returns only pending | 200, all tasks pending |
| **List invalid status** | GET /api/agent/tasks?status=invalid | 422 |
| **List limit=1** | GET /api/agent/tasks?limit=1 returns at most one task, total unchanged | 200, len(tasks) ≤ 1 |
| **Fixed path vs task id** | GET /api/agent/tasks/attention returns list (not task by id "attention") | 200, shape { tasks, total } |
| **Fixed path vs task id** | GET /api/agent/tasks/count returns counts (not task by id "count") | 200, shape { total, by_status } |
| **Task id resolution** | GET /api/agent/tasks/{real_task_id} returns that task | 200, id and direction match |
| **Count empty store** | GET /api/agent/tasks/count when no tasks | 200, total: 0, by_status: {} |
| **Log 404** | GET /api/agent/tasks/{id}/log with non-existent task id | 404, detail "Task not found" |
| **Log file missing** | GET /api/agent/tasks/{id}/log when task exists but log file missing on disk | 404, detail "Task log not found" |
| **Log output when set** | GET /api/agent/tasks/{id}/log when task has output | 200, output in response |
| **Attention limit** | GET /api/agent/tasks/attention?limit=0 or limit=101 | 422 |
| **Route invalid task_type** | GET /api/agent/route?task_type=invalid | 422 |
| **Route executor default** | GET /api/agent/route?task_type=impl without executor | 200, executor: "claude" |
| **PATCH progress_pct boundary** | PATCH with progress_pct=0 or progress_pct=100 | 200, value accepted |
| **POST missing direction** | POST /api/agent/tasks without `direction` (body missing key or null) | 422 |
| **POST direction null** | POST with `direction`: null | 422 |
| **POST missing task_type** | POST /api/agent/tasks without `task_type` | 422 |
| **List empty** | GET /api/agent/tasks when no tasks exist | 200, `tasks: []`, `total: 0` |
| **Pagination offset beyond total** | GET /api/agent/tasks?offset=999 when total &lt; 999 | 200, `tasks: []`, `total` unchanged |
| **Direction boundary 5000** | POST with `direction` exactly 5000 chars | 201, task created |
| **Direction boundary 5001** | POST with `direction` length 5001 | 422 |
| **PATCH invalid progress_pct type** | PATCH with progress_pct as string (e.g. `"50"`) | 422 |
| **Telegram webhook no message** | POST webhook with update containing no `message` or `edited_message` | 200, `ok: true` |
| **Telegram test-send text param** | POST /api/agent/telegram/test-send?text=... | 200, ok and results or error |
| **Monitor-issues no file** | GET /api/agent/monitor-issues when monitor_issues.json missing | 200, issues: [], last_check: null |

## Telegram Integration (OpenClaw-style)

- **Outbound alerts**: When task status → `needs_decision` or `failed`, send message to TELEGRAM_CHAT_IDS.
- **Inbound webhook**: POST /api/agent/telegram/webhook receives Telegram Update.
  - Commands: /status — summary; /tasks [status] — list; /task {id} — detail; /reply {task_id} {decision}; /attention — needs_decision/failed; /usage — usage summary; /direction "..." or plain text — create task.
  - Config: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_IDS, TELEGRAM_ALLOWED_USER_IDS (comma-separated).
  - Set webhook: `https://api.telegram.org/bot{token}/setWebhook?url={your-api}/api/agent/telegram/webhook`

## Out of Scope

- Actual execution of Claude Code (client runs command)
- PostgreSQL persistence (MVP uses in-memory)
- Authentication for API (Telegram uses allowed users)

## Usage from Cursor

1. Call `POST /api/agent/tasks` with direction and task_type.
2. Use returned `command` to run Claude Code (terminal or script).
3. Call `PATCH /api/agent/tasks/{id}` when status changes.
4. Call `GET /api/agent/tasks` or `/api/agent/tasks/attention` to see what needs action.

## Decision Gates

None for MVP.

## See also

- [005-project-manager-pipeline.md](005-project-manager-pipeline.md) — orchestrator that uses this API
- [003-agent-telegram-decision-loop.md](003-agent-telegram-decision-loop.md) — Telegram webhook integration
- [docs/MODEL-ROUTING.md](../docs/MODEL-ROUTING.md) — routing table and fallbacks
- [docs/PIPELINE-MONITORING-AUTOMATED.md](../docs/PIPELINE-MONITORING-AUTOMATED.md) — monitor-issues usage
