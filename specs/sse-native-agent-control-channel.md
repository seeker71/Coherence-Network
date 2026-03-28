# Spec: SSE control channel for native agent CLIs

## Goal

Make every provider-backed agent run **observable and steerable in real time**: operators and automation can send **checkpoint**, **steer**, **abort**, **ask** (permission), and **report** commands while a task runs; agents read commands from a local control file and send responses via `POST /api/agent/tasks/{task_id}/activity`. The API exposes **Server-Sent Events** so UIs and runners can subscribe to per-task event timelines.

## Scope

| Layer | Responsibility |
|--------|------------------|
| **API** | Persist/emit task activity; `GET /api/agent/tasks/{task_id}/events` SSE; `GET .../stream` snapshot |
| **Runner** (`api/scripts/task_control_channel.py`) | Subscribe to federation node SSE, append JSONL to `.task-control`, POST agent responses to activity |
| **Federation** | `GET /api/federation/nodes/{node_id}/stream` delivers network messages to the runner |

## Files (reference)

- `api/app/routers/task_activity_routes.py` — activity POST, task stream list, SSE
- `api/app/services/task_activity_service.py` — ring buffer + per-task streams
- `api/scripts/task_control_channel.py` — `TaskControlChannel`, `inject_control_instructions`
- `api/app/routers/federation.py` — node SSE (`/api/federation/nodes/{node_id}/stream`)

## Acceptance criteria

1. **Activity logging**: `POST /api/agent/tasks/{task_id}/activity` returns 201 and events appear on `GET /api/agent/tasks/{task_id}/stream`.
2. **SSE**: `GET /api/agent/tasks/{task_id}/events` returns `Content-Type: text/event-stream` and, once a terminal event (`completed` \| `failed` \| `timeout`) exists, emits at least one `data: {...}` line and a final `event_type: end` payload.
3. **Control file protocol**: `TaskControlChannel.send_command` appends JSON lines to `{task_dir}/.task-control` with `type`, `task_id`, `payload`, `timestamp`.
4. **Prompt injection**: `inject_control_instructions` appends the documented `cc` / checkpoint / steer / abort / ask guidance to the prompt.

## Verification Scenarios

### Scenario 1 — Create–read–update activity timeline

- **Setup**: API running (test client), new `task_id` not used before.
- **Action**:
  1. `curl -s -X POST "$API/api/agent/tasks/$TASK_ID/activity" -H "Content-Type: application/json" -d '{"event_type":"executing","node_id":"n1","provider":"codex","data":{"phase":"run"}}'`
  2. `curl -s "$API/api/agent/tasks/$TASK_ID/stream"`
  3. `curl -s -X POST "$API/api/agent/tasks/$TASK_ID/activity" -H "Content-Type: application/json" -d '{"event_type":"progress","data":{"pct":50}}'`
  4. `curl -s "$API/api/agent/tasks/$TASK_ID/stream"`
- **Expected**:
  - Steps 1 and 3 return HTTP 201 with JSON containing `event_type` and `timestamp`.
  - Step 2: JSON array length ≥ 1, last element has `event_type` `executing`.
  - Step 4: array length ≥ 2, includes both `executing` and `progress`.
- **Edge**: POST with `{}` (missing `event_type`) → HTTP 422 with validation detail.

### Scenario 2 — SSE stream ends after terminal event

- **Setup**: Same API; `TASK_ID` unique.
- **Action**:
  1. `curl -s -X POST "$API/api/agent/tasks/$TASK_ID/activity" -H "Content-Type: application/json" -d '{"event_type":"completed","data":{"outcome":"ok"}}'`
  2. `curl -sN "$API/api/agent/tasks/$TASK_ID/events"` (or TestClient stream in CI)
- **Expected**:
  - Response headers include `text/event-stream`.
  - Body contains `data: ` lines including a JSON object with `"event_type":"completed"` and a final line with `"event_type":"end"`.
- **Edge**: If no events exist for `TASK_ID`, stream blocks until a terminal event appears (production clients should POST progress first); tests pre-seed `completed` to avoid long waits.

### Scenario 3 — Control response lineage

- **Setup**: Task with a simulated agent response logged as activity.
- **Action**:
  - `curl -s -X POST "$API/api/agent/tasks/$TASK_ID/activity" -H "Content-Type: application/json" -d '{"event_type":"control_response_ack","data":{"type":"ack","note":"steer applied"}}'`
  - `curl -s "$API/api/agent/tasks/$TASK_ID/stream"`
- **Expected**: Stream contains an event with `event_type` `control_response_ack` and `data.type` == `ack`.
- **Edge**: Empty `data` object is allowed; event still stored.

### Scenario 4 — Unknown task stream (no error)

- **Setup**: `TASK_ID` never written.
- **Action**: `curl -s "$API/api/agent/tasks/$TASK_ID/stream"`
- **Expected**: HTTP 200, JSON `[]`.
- **Edge**: Same for `GET /api/agent/tasks/activity?task_id=$TASK_ID` — may return `[]` when nothing logged.

### Scenario 5 — Federation node SSE (connectivity)

- **Setup**: Registered federation node `node_id` (16 chars per existing validation).
- **Action**: `curl -sN -H "Accept: text/event-stream" "$API/api/federation/nodes/$NODE_ID/stream"` (first line or initial chunk).
- **Expected**: `text/event-stream` and initial `connected` style payload (implementation sends `event_type: connected`).
- **Edge**: Invalid/unregistered `node_id` may still open stream per current router behavior — document actual status code if tightened later.

## Risks and Assumptions

- Task activity is **in-memory** in default configuration; restart clears streams (acceptable for dev/CI; production may need persistence later).
- Runner **TaskControlChannel** depends on outbound HTTP to API; network failures retry with backoff (see script).

## Known Gaps and Follow-up Tasks

- Persist activity to DB for cross-restart audit trails.
- Align federation push payload field names (`type` vs `event_type`) across all publishers for the control channel filter.
- Add metrics: count of steer/checkpoint/abort commands per task.

## Open questions (product)

- **Proof over time**: expose a small **health dashboard** snippet: last control command latency, count of `.task-control` lines read per task, and `control_response_*` events per hour — makes “is it working?” visible without reading raw logs.
