# Spec: Agent Orchestration API

## Purpose

Provide an API that Cursor (or any client) can call to submit agent tasks, get model routing decisions, and track status—enabling guided Claude Code execution from within Cursor with observability.

## Requirements

- [x] POST /api/agent/tasks — Submit task, returns task_id + routed model + suggested command
- [x] GET /api/agent/tasks — List tasks with optional status/type filters
- [x] GET /api/agent/tasks/{id} — Get task by id
- [x] PATCH /api/agent/tasks/{id} — Update task status (running, completed, failed, needs_decision)
- [x] GET /api/agent/route — Route-only: given task_type, return model + command template (no persistence)
- [x] Tasks stored in memory for MVP; structure supports future PostgreSQL migration

## API Contract

### `POST /api/agent/tasks`

**Request**
```json
{
  "direction": "Add GET /api/projects endpoint",
  "task_type": "impl",
  "context": { "spec_ref": "specs/003-projects.md" }
}
```

- `direction`: string (required)
- `task_type`: string, enum: spec | test | impl | review | heal
- `context`: object (optional)

**Response 201**
```json
{
  "id": "task_abc123",
  "direction": "Add GET /api/projects endpoint",
  "task_type": "impl",
  "status": "pending",
  "model": "ollama/glm-4.7-flash:latest",
  "command": "claude -p \"Add GET /api/projects endpoint\" --model glm-4.7-flash:latest --allowedTools Read,Edit,Bash --dangerously-skip-permissions",
  "created_at": "2026-02-12T12:00:00Z"
}
```

### `GET /api/agent/tasks`

**Query params:** `status`, `task_type`, `limit` (default 20)

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
      "created_at": "2026-02-12T12:00:00Z",
      "updated_at": null
    }
  ],
  "total": 1
}
```

### `GET /api/agent/tasks/{id}`

**Response 200** — same shape as task in list, plus `command`, `output` (optional)
**Response 404** — `{ "detail": "Task not found" }`

### `PATCH /api/agent/tasks/{id}`

**Request**
```json
{ "status": "running" }
```
or
```json
{ "status": "completed", "output": "Implementation complete. Tests pass." }
```

**Response 200** — updated task
**Response 404** — task not found
**Response 422** — invalid status

### `GET /api/agent/route?task_type=impl`

**Response 200**
```json
{
  "task_type": "impl",
  "model": "ollama/glm-4.7-flash:latest",
  "command_template": "claude -p \"{{direction}}\" --model glm-4.7-flash:latest --allowedTools Read,Edit,Bash --dangerously-skip-permissions",
  "tier": "local"
}
```

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
  context: object | null
  created_at: datetime
  updated_at: datetime | null
```

## Routing Logic (from docs/MODEL-ROUTING.md)

| task_type | model | tier |
|-----------|-------|------|
| spec | ollama/glm-4.7-flash:latest | local |
| test | ollama/glm-4.7-flash:latest | local |
| impl | ollama/glm-4.7-flash:latest | local |
| review | ollama/glm-4.7-flash:latest | local |
| heal | claude-3-5-haiku-20241022 | claude |

Fallback: use `context.model_override` for glm-5:cloud (cloud) or claude-3-5-haiku-20241022 (claude).

## Files to Create/Modify

- `api/app/models/agent.py` — Pydantic models
- `api/app/services/agent_service.py` — routing + in-memory store + get_review_summary
- `api/app/services/telegram_adapter.py` — Telegram send_alert, send_reply, parse_command
- `api/app/routers/agent.py` — route handlers + webhook + alert hook
- `api/app/main.py` — include agent router
- `api/tests/test_agent.py` — acceptance tests

## Acceptance Tests

- test_post_task_returns_201_with_routed_model_and_command
- test_get_tasks_list_with_filters
- test_get_task_by_id_404_when_missing
- test_patch_task_updates_status
- test_route_endpoint_returns_model_and_template
- test_impl_tasks_route_to_local
- test_heal_tasks_route_to_claude

## Telegram Integration (OpenClaw-style)

- **Outbound alerts**: When task status → `needs_decision` or `failed`, send message to TELEGRAM_CHAT_IDS.
- **Inbound webhook**: POST /api/agent/telegram/webhook receives Telegram Update.
  - Commands: `/status` — summary; `/tasks [status]` — list; `/task {id}` — detail; `/direction "..."` or plain text — create task.
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
4. Call `GET /api/agent/tasks` to see what's running or pending.

## See also

- [005-project-manager-pipeline.md](005-project-manager-pipeline.md) — orchestrator that uses this API
- [003-agent-telegram-decision-loop.md](003-agent-telegram-decision-loop.md) — Telegram webhook integration

## Decision Gates

None for MVP.

## See Also

- [003-agent-telegram-decision-loop.md](003-agent-telegram-decision-loop.md) — /reply, /attention, progress tracking, agent runner
