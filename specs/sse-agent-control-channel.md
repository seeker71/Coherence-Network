# SSE control channel — native agent CLIs (steer, checkpoint, abort, ask, report)

## Goal

Give every native agent CLI (Claude, Codex, Cursor agent, Gemini) **observable, real-time control** while a task runs: visibility via **Server-Sent Events** on task-scoped URLs, **control** via **task context** patches the runner polls (abort, diagnostic), and **activity** via **POST** from runners. This prevents “black box” executions with no visibility for minutes.

## Scope (current implementation)

| Concern | Mechanism | Notes |
|--------|-----------|--------|
| Live event stream | `GET /api/agent/tasks/{task_id}/events` | `text/event-stream`; yields JSON lines + `event_type: end` when a terminal activity event exists |
| Activity log | `POST /api/agent/tasks/{task_id}/activity` | Runners report `claimed`, `executing`, `progress`, `output`, `completed`, `failed`, `timeout` |
| Snapshot | `GET /api/agent/tasks/{task_id}/stream` | Full event list for a task (JSON) |
| Cross-task feed | `GET /api/agent/tasks/activity` | Recent events with optional filters |
| Active tasks | `GET /api/agent/tasks/active` | Currently “running” activity rows (TTL) |
| Abort / control | `PATCH /api/agent/tasks/{task_id}` with `context` | Runner reads `context.control`, `abort_requested`, etc. (`api/scripts/agent_runner.py` → `_extract_control_signals`) |
| Checkpoint | Runner periodic git checkpoint | `AGENT_PERIODIC_CHECKPOINT_SECONDS`, `_checkpoint_partial_progress` (not a separate SSE verb) |

## Files (reference)

- `api/app/routers/task_activity_routes.py` — SSE + activity routes
- `api/app/services/task_activity_service.py` — in-memory ring buffer
- `api/app/routers/agent_tasks_routes.py` — `PATCH /tasks/{id}` merges `context`
- `api/scripts/agent_runner.py` — `_extract_control_signals`, execution loop

## Acceptance criteria

1. **SSE** returns `Content-Type: text/event-stream` and at least one `data:` line per stored event for the task, then ends after a terminal activity type when one exists.
2. **POST activity** returns `201` and a JSON body with `id`, `task_id`, `event_type`, `timestamp`.
3. **PATCH** with `context` containing `control` merges into the task and is visible on `GET /api/agent/tasks/{id}`.
4. **`_extract_control_signals`** correctly detects abort from `context.control` and top-level flags.

## Verification Scenarios

### 1. Full create → activity → read → SSE (happy path)

- **Setup:** API running; in-memory task store cleared; create task `task-sse-1` with `POST /api/agent/tasks` (`direction`, `task_type: impl`).
- **Action:** `POST /api/agent/tasks/task-sse-1/activity` with body `{"event_type":"executing","provider":"claude","data":{"step":"compile"}}`; then `GET /api/agent/tasks/task-sse-1/stream`; then `POST` again with `event_type:"completed"` and minimal `data`.
- **Expected:** Stream lists two events in order; `GET .../stream` returns both; last event has `event_type` `completed`.
- **Edge:** `POST` with missing `event_type` → `422` (validation error).

### 2. Control channel — abort signal in context (runner contract)

- **Setup:** Task `task-ctl-1` exists and is claimed/running (`PATCH` with `status: running`, `worker_id: manual-test`).
- **Action:** `PATCH /api/agent/tasks/task-ctl-1` with `{"context":{"control":{"action":"abort","reason":"operator stop"}}}` (no status change).
- **Expected:** `GET /api/agent/tasks/task-ctl-1` shows `context.control.action == "abort"` and reason preserved.
- **Edge:** `PATCH` with empty body fields → `400` “At least one field required”.

### 3. SSE ends after terminal event

- **Setup:** Task `task-sse-end`; log `completed` via `POST .../activity` before opening SSE.
- **Action:** `GET /api/agent/tasks/task-sse-end/events` (streaming) and read until `event_type: end` in payload.
- **Expected:** Response is `text/event-stream`; body contains JSON for each prior event and a final `end` marker.
- **Edge:** If no terminal event were ever logged, the stream would wait (production clients should always log completion or cancel); tests pre-populate terminal state.

### 4. Filtered activity

- **Setup:** Two tasks with distinct `task_id`s each receive one `POST /activity`.
- **Action:** `GET /api/agent/tasks/activity?task_id=<one>` with limit.
- **Expected:** Only events for that `task_id` appear.
- **Edge:** Unknown `task_id` filter returns empty list (not 404).

## Risks and Assumptions

- In-memory activity store resets on process restart; production observability may need persistence.
- SSE is **pull-based** every 2s in the generator loop; ultra-low-latency is not guaranteed.

## Known Gaps and Follow-up Tasks

- Explicit **steer** / **ask-permission** verbs in API (beyond `needs_decision` + Telegram) are not fully modeled as separate SSE command types; extend `context` schema and runner if needed.
- Durable **command file** for CLIs reading from disk is runner-local; not covered by the API spec above.

## Verification

- Automated: `cd api && python -m pytest api/tests/test_sse_control_channel_agent.py -v`
