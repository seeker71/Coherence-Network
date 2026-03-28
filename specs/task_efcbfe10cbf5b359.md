# Spec: SSE Control Channel — Real-Time Steer, Checkpoint, Abort, Ask-Permission for Native Agent CLIs

*Format: [specs/TEMPLATE.md](TEMPLATE.md)*

## Purpose

Native agent CLIs (claude, codex, cursor agent, gemini) run as opaque subprocesses today — they
start, produce output after several minutes, then stop. There is no way to redirect them mid-run,
save incremental progress, stop cleanly, or ask the user a question without polling a slow, lossy
log file.

This spec introduces a **bidirectional control channel**: agents open an SSE stream when they start
a task and receive typed control commands (checkpoint, steer, abort, ask, report) delivered by the
API in real time. The runner wraps each provider subprocess with an SSE listener thread that writes
commands to a well-known command file; the agent process reads that file and acts accordingly.
Responses flow back through `POST /api/agent/tasks/{id}/activity` (existing heartbeat path) and
a new `POST /api/agent/tasks/{id}/control/response` endpoint.

**Who benefits**: operators get immediate visibility and control; agents become steerable rather
than black-box fire-and-forget processes; the system can implement safety guardrails (abort on
budget overrun, ask before destructive ops) without killing the process blindly.

## Background — What Exists Today

| Component | Current state |
|-----------|---------------|
| `GET /api/agent/tasks/{id}/events` | Outbound SSE: pushes activity events TO the client. No inbound path. |
| `POST /api/agent/tasks/{id}/activity` | Inbound heartbeat from runners. Used but carries no typed commands. |
| `TaskStatus.NEEDS_DECISION` | Status exists, but there is no mechanism to pause execution and wait. |
| `checkpoint_sha` on task model | Field exists; nothing writes to it during execution. |
| `abort_evidence` on task model | Carry evidence for an abort decision; not wired to a live signal. |

This spec extends the existing `events` stream from read-only observation to a **full-duplex
control channel** and adds the server-side queue + agent-side polling contract.

---

## Requirements

### Server (API)

- [ ] **R-S1** — `GET /api/agent/tasks/{id}/control/stream` — SSE endpoint that yields `ControlCommand` events for the named task. Commands are queued server-side; each command is delivered once per connected consumer and acknowledged via the response endpoint.
- [ ] **R-S2** — `POST /api/agent/tasks/{id}/control` — Enqueue a `ControlCommand` for a running task. Accepted command types: `checkpoint`, `steer`, `abort`, `ask`, `report`. Returns `202 Accepted` with the queued command record.
- [ ] **R-S3** — `POST /api/agent/tasks/{id}/control/response` — Accept a `ControlResponse` from the agent: `command_id`, `status` (`received` | `ack` | `error`), and optional `payload` (progress snapshot, checkpoint sha, answer to `ask`). Returns `201 Created`.
- [ ] **R-S4** — `GET /api/agent/tasks/{id}/control/commands` — Return the full ordered list of commands sent to this task (for audit / UI display). Supports `?status=pending|ack|error` filter.
- [ ] **R-S5** — Commands persist in the in-memory store alongside the task. A command's `status` transitions: `queued → delivered → ack | error`. Auto-expire commands older than 10 minutes if task is terminal.
- [ ] **R-S6** — Sending a command to a task that does not exist returns `404`. Sending to a terminal task (`completed`, `failed`, `timed_out`) returns `409 Conflict`.
- [ ] **R-S7** — An `abort` command transitions the task status to `running` → `abort_requested` so the runner can detect it via PATCH and the agent can detect it via the command file.

### Runner (SSE Listener Thread)

- [ ] **R-R1** — When a task execution starts, the runner spawns a background thread that opens the `control/stream` SSE endpoint for that task and subscribes continuously.
- [ ] **R-R2** — On receiving a `ControlCommand` event, the runner writes the command JSON to `.cc-control/{task_id}.cmd` (appended, one JSON object per line) and POSTs a `received` response to `control/response`.
- [ ] **R-R3** — The runner checks the command file between agent subprocess output lines (or every 2 seconds in a polling thread) and acts on each unprocessed command in order.
- [ ] **R-R4** — `checkpoint`: runner sends `SIGUSR1` (or platform-equivalent) to the agent process; agent output snapshot is captured and saved as `checkpoint_sha`; response `ack` is POSTed.
- [ ] **R-R5** — `steer`: runner writes the steer payload to a second file `.cc-control/{task_id}.steer` which is an append-log of steering instructions; it also injects the steer text into the agent's stdin if the provider supports it. Response `ack` is POSTed.
- [ ] **R-R6** — `abort`: runner sends `SIGTERM` to the agent subprocess; waits up to 5 seconds for graceful exit; then `SIGKILL`. Task status is PATCHed to `failed` with `abort_evidence`. Response `ack` is POSTed.
- [ ] **R-R7** — `ask`: runner pauses submission of further prompts; POSTs `ControlResponse` with `status=received`; task status is PATCHed to `needs_decision` with `decision_prompt` set. Execution resumes when the task status returns to `running` (user has replied via `PATCH /api/agent/tasks/{id}`).
- [ ] **R-R8** — `report`: runner captures current agent output tail (last 200 lines) and POSTs it back as a `ControlResponse` with the snapshot in `payload`.
- [ ] **R-R9** — If the SSE connection drops, the runner retries with exponential backoff (1 s → 2 s → 4 s, max 30 s). If reconnect fails for 60 seconds the runner continues execution without the control channel (degraded mode) and logs a warning.

### Agent-Side Protocol (Command File)

- [ ] **R-A1** — Agents that natively support a control file path (claude `--control-file`, custom wrappers) read `.cc-control/{task_id}.cmd` at startup and re-read it every 2 seconds.
- [ ] **R-A2** — Each line in the command file is a JSON object with `{"id":"…","type":"checkpoint|steer|abort|ask|report","payload":{…},"ts":"ISO8601"}`.
- [ ] **R-A3** — Agents track the last-processed line index to avoid replaying commands.
- [ ] **R-A4** — For providers that do NOT support a control file (codex CLI), the runner wraps the execution in a watchdog process that reads the file and sends signals / stdin injections.

---

## Research Inputs

- `2026-03-28` — Internal codebase review of `api/app/routers/task_activity_routes.py` (existing SSE outbound path at `/tasks/{id}/events`)
- `2026-03-28` — `api/app/models/agent.py` — `TaskStatus`, `checkpoint_sha`, `abort_evidence`, `needs_decision` fields already present
- `2026-03-28` — `api/config/runner.json` — runner heartbeat, parallel execution config
- `2026-03-28` — `api/app/services/task_activity_service.py` — in-memory event store pattern (replicate for command queue)

---

## Task Card

```yaml
goal: >
  Add a bidirectional SSE control channel so operators can send checkpoint/steer/abort/ask/report
  commands to any running native agent CLI and receive structured responses — replacing opaque
  5-minute black-box runs with fully observable, steerable execution.

files_allowed:
  # New files
  - api/app/models/control_channel.py
  - api/app/services/control_channel_service.py
  - api/app/routers/control_channel_routes.py
  # Existing files to modify
  - api/app/main.py                              # register new router
  - api/app/services/task_activity_service.py   # share event-store helpers if appropriate
  - api/app/models/agent.py                     # add abort_requested to TaskStatus

done_when:
  - GET /api/agent/tasks/{id}/control/stream returns SSE events for queued commands
  - POST /api/agent/tasks/{id}/control accepts command, returns 202 with command record
  - POST /api/agent/tasks/{id}/control/response accepts ack/error from agent, returns 201
  - GET /api/agent/tasks/{id}/control/commands returns ordered command list with status
  - All 5 command types (checkpoint, steer, abort, ask, report) are accepted and validated
  - Sending command to nonexistent task returns 404
  - Sending command to terminal task returns 409
  - abort command transitions task status to abort_requested
  - ask command transitions task status to needs_decision with decision_prompt set
  - pytest tests pass for all acceptance scenarios

commands:
  - cd api && pytest tests/test_control_channel.py -x -v

constraints:
  - No changes to existing SSE stream at /api/agent/tasks/{id}/events (keep backward compat)
  - Command store is in-memory for MVP; no schema migrations required
  - Runner SSE listener implementation is out of scope for this spec iteration (spec only)
  - Do not modify tests to force passing behavior
```

---

## API Contract

### `POST /api/agent/tasks/{task_id}/control`

Enqueue a control command for a running task.

**Request body**
```json
{
  "type": "checkpoint | steer | abort | ask | report",
  "payload": {
    "instruction": "string (required for steer/ask; optional otherwise)",
    "reason": "string (optional, human-readable context)"
  },
  "sender": "operator | system | user"
}
```

**Response 202**
```json
{
  "id": "cmd_a1b2c3d4",
  "task_id": "task_efcbfe10cbf5b359",
  "type": "steer",
  "status": "queued",
  "payload": { "instruction": "focus only on the auth module" },
  "sender": "operator",
  "queued_at": "2026-03-28T17:35:00Z",
  "delivered_at": null,
  "acked_at": null
}
```

**Response 404** — Task not found
```json
{ "detail": "Task not found" }
```

**Response 409** — Task is in a terminal state
```json
{ "detail": "Task is terminal (completed) — cannot send control commands" }
```

**Response 422** — Unknown command type or missing required payload field
```json
{ "detail": [{ "loc": ["body", "type"], "msg": "value is not a valid enum member" }] }
```

---

### `GET /api/agent/tasks/{task_id}/control/stream`

SSE stream that delivers queued `ControlCommand` events to the connected agent/runner.

**Response** — `text/event-stream`
```
data: {"id":"cmd_a1b2c3d4","task_id":"task_efcbfe10cbf5b359","type":"steer","payload":{"instruction":"focus only on auth module"},"queued_at":"2026-03-28T17:35:00Z"}

data: {"id":"cmd_e5f6g7h8","task_id":"task_efcbfe10cbf5b359","type":"abort","payload":{"reason":"budget exceeded"},"queued_at":"2026-03-28T17:36:00Z"}

data: {"event_type":"end"}
```

- Events are delivered in queue order.
- Already-delivered commands are NOT re-sent to new connections (delivery is per-task, not per-connection). Use `/control/commands` to replay history.
- Stream ends when task is terminal.
- Poll interval: 1-second server-side tick.

---

### `POST /api/agent/tasks/{task_id}/control/response`

Accept a structured response from the agent process.

**Request body**
```json
{
  "command_id": "cmd_a1b2c3d4",
  "status": "received | ack | error",
  "payload": {
    "checkpoint_sha": "abc123 (for checkpoint ack)",
    "answer": "yes, proceed (for ask ack)",
    "output_tail": "last 200 lines... (for report ack)",
    "error": "description if status=error"
  }
}
```

**Response 201**
```json
{
  "command_id": "cmd_a1b2c3d4",
  "task_id": "task_efcbfe10cbf5b359",
  "status": "ack",
  "recorded_at": "2026-03-28T17:35:05Z"
}
```

**Response 404** — Command id not found
```json
{ "detail": "Command not found" }
```

---

### `GET /api/agent/tasks/{task_id}/control/commands`

Return the full ordered history of commands for a task.

**Query parameters**
- `status` (optional): `queued | delivered | ack | error`

**Response 200**
```json
[
  {
    "id": "cmd_a1b2c3d4",
    "task_id": "task_efcbfe10cbf5b359",
    "type": "steer",
    "status": "ack",
    "payload": { "instruction": "focus only on auth module" },
    "sender": "operator",
    "queued_at": "2026-03-28T17:35:00Z",
    "delivered_at": "2026-03-28T17:35:01Z",
    "acked_at": "2026-03-28T17:35:05Z"
  }
]
```

---

## Data Model

```yaml
ControlCommandType:
  values: [checkpoint, steer, abort, ask, report]

ControlCommandStatus:
  values: [queued, delivered, ack, error]
  transitions:
    queued -> delivered  # when SSE consumer reads it
    delivered -> ack     # when agent POSTs ControlResponse with status=ack
    delivered -> error   # when agent POSTs ControlResponse with status=error

ControlCommand:
  properties:
    id:           { type: string, format: "cmd_<8hex>" }
    task_id:      { type: string }
    type:         { type: ControlCommandType }
    status:       { type: ControlCommandStatus, default: queued }
    payload:      { type: object, nullable: true }
    sender:       { type: string, default: "operator" }
    queued_at:    { type: string, format: ISO8601 }
    delivered_at: { type: string, format: ISO8601, nullable: true }
    acked_at:     { type: string, format: ISO8601, nullable: true }

ControlResponse:
  properties:
    command_id:   { type: string }
    status:       { type: string, enum: [received, ack, error] }
    payload:      { type: object, nullable: true }

TaskStatus additions:
  ABORT_REQUESTED: "abort_requested"  # set by abort command; runner acts on this
```

**Storage**: in-memory dict keyed by `task_id`, value is list of `ControlCommand`. Evicted when task is deleted or 10 minutes after terminal state.

---

## Files to Create/Modify

### New files

| File | Purpose |
|------|---------|
| `api/app/models/control_channel.py` | Pydantic models: `ControlCommandType`, `ControlCommandStatus`, `ControlCommandCreate`, `ControlCommand`, `ControlResponse`, `ControlResponseCreate` |
| `api/app/services/control_channel_service.py` | In-memory command queue; enqueue, list, get, mark-delivered, mark-acked; SSE generator |
| `api/app/routers/control_channel_routes.py` | FastAPI router: POST control, GET stream, POST response, GET commands |
| `api/tests/test_control_channel.py` | Pytest tests for all acceptance scenarios |

### Modified files

| File | Change |
|------|--------|
| `api/app/main.py` | Register `control_channel_routes.router` under `/api/agent` prefix |
| `api/app/models/agent.py` | Add `ABORT_REQUESTED = "abort_requested"` to `TaskStatus` enum |

---

## Acceptance Tests

```
api/tests/test_control_channel.py::test_enqueue_command_returns_202
api/tests/test_control_channel.py::test_enqueue_all_five_command_types
api/tests/test_control_channel.py::test_enqueue_to_nonexistent_task_returns_404
api/tests/test_control_channel.py::test_enqueue_to_terminal_task_returns_409
api/tests/test_control_channel.py::test_command_list_returns_ordered_history
api/tests/test_control_channel.py::test_response_ack_updates_command_status
api/tests/test_control_channel.py::test_response_to_unknown_command_returns_404
api/tests/test_control_channel.py::test_abort_command_transitions_task_to_abort_requested
api/tests/test_control_channel.py::test_ask_command_transitions_task_to_needs_decision
api/tests/test_control_channel.py::test_steer_requires_instruction_payload
api/tests/test_control_channel.py::test_command_filter_by_status
api/tests/test_control_channel.py::test_sse_stream_yields_queued_commands
```

---

## Verification Scenarios

These scenarios must pass against production (`https://api.coherencycoin.com`). The reviewer runs
them sequentially. Replace `$API` with the base URL.

### Scenario 1 — Create and read a control command (full CRUD cycle)

**Setup**: A task `task_ctrl_test_01` exists with status `running`. (Create via `POST /api/agent/tasks`.)

**Action**:
```bash
# Create a running task
TASK=$(curl -s -X POST $API/api/agent/tasks \
  -H "Content-Type: application/json" \
  -d '{"direction":"test task","task_type":"spec"}' | jq -r .id)

# Patch to running so control commands are accepted
curl -s -X PATCH $API/api/agent/tasks/$TASK \
  -H "Content-Type: application/json" \
  -d '{"status":"running"}'

# Enqueue a checkpoint command
CMD=$(curl -s -X POST $API/api/agent/tasks/$TASK/control \
  -H "Content-Type: application/json" \
  -d '{"type":"checkpoint","payload":{"reason":"manual checkpoint test"},"sender":"operator"}')

echo $CMD | jq .status   # should be "queued"
CMD_ID=$(echo $CMD | jq -r .id)

# Read command history
curl -s $API/api/agent/tasks/$TASK/control/commands | jq '.[0].type'
# Expected: "checkpoint"
```

**Expected result**: HTTP 202 on enqueue; `status` = `"queued"`; list returns the command with matching `id`.

**Edge — duplicate command**: POST same checkpoint again → HTTP 202 again (commands are not deduplicated; each POST is a distinct command with a new `id`).

**Edge — unknown type**: POST `{"type":"nuke","payload":{}}` → HTTP 422 with validation error on `type`.

---

### Scenario 2 — Abort command transitions task status

**Setup**: Same running task from Scenario 1 (or a new one patched to `running`).

**Action**:
```bash
curl -s -X POST $API/api/agent/tasks/$TASK/control \
  -H "Content-Type: application/json" \
  -d '{"type":"abort","payload":{"reason":"budget exceeded"},"sender":"system"}'
```

**Expected result**: HTTP 202; task status immediately transitions to `abort_requested` (verify with `GET /api/agent/tasks/$TASK` → `"status": "abort_requested"`).

**Edge — send another command after abort**: POST `{"type":"checkpoint","payload":{}}` → HTTP 409 (`"Task is terminal"` message should NOT apply here since `abort_requested` is not a fully terminal state). The spec intentionally allows further commands to `abort_requested` tasks so the runner can still ACK the abort.

---

### Scenario 3 — Ask command pauses task with decision prompt

**Setup**: Running task.

**Action**:
```bash
curl -s -X POST $API/api/agent/tasks/$TASK/control \
  -H "Content-Type: application/json" \
  -d '{"type":"ask","payload":{"instruction":"Should I delete the /tmp/build folder? (yes/no)"},"sender":"operator"}'
```

**Expected result**: HTTP 202; `GET /api/agent/tasks/$TASK` returns `"status": "needs_decision"` and `"decision_prompt": "Should I delete the /tmp/build folder? (yes/no)"`.

**Edge — steer without instruction field**: POST `{"type":"steer","payload":{}}` → HTTP 422 (instruction is required for steer/ask types).

---

### Scenario 4 — Agent response ACKs a command

**Setup**: Task with a queued command from Scenario 1 (`CMD_ID` set).

**Action**:
```bash
# Agent sends back ack
curl -s -X POST $API/api/agent/tasks/$TASK/control/response \
  -H "Content-Type: application/json" \
  -d "{\"command_id\":\"$CMD_ID\",\"status\":\"ack\",\"payload\":{\"checkpoint_sha\":\"abc123def456\"}}"
```

**Expected result**: HTTP 201; subsequent `GET /api/agent/tasks/$TASK/control/commands` shows the command with `status: "ack"` and non-null `acked_at`.

**Edge — unknown command_id**: POST response with `command_id: "cmd_nonexistent"` → HTTP 404.

**Edge — duplicate ack**: POST the same `CMD_ID` response again → HTTP 201 idempotent (status stays `ack`, `acked_at` not overwritten) OR HTTP 409 (implementation choice; must be documented).

---

### Scenario 5 — Error handling for terminal task

**Setup**: Task that has been patched to `completed`.

**Action**:
```bash
curl -s -X POST $API/api/agent/tasks/$TASK/control \
  -H "Content-Type: application/json" \
  -d '{"type":"steer","payload":{"instruction":"add more logging"}}'
```

**Expected result**: HTTP 409 with `{ "detail": "Task is terminal (completed) — cannot send control commands" }`.

**Edge — nonexistent task**: POST to `/api/agent/tasks/task_does_not_exist_9999/control` → HTTP 404, not 500.

---

## Concurrency Behavior

- **Command queue**: in-memory `dict[task_id, list[ControlCommand]]`; Python GIL provides sufficient isolation for MVP (no async mutation races in FastAPI's single-threaded event loop).
- **SSE delivery**: each command is marked `delivered` the first time the SSE generator yields it; idempotent reads by the same generator are prevented by tracking the last-seen index.
- **Multi-runner scenario**: if two runner instances connect to the same task's `control/stream`, both will receive every command. This is a known limitation of the MVP — deduplication via `command_id` on the agent side prevents double-execution.
- **Recommendation**: upgrade to PostgreSQL-backed queue with advisory locks before scaling to 10+ concurrent runners per task.

---

## Verification (Pre-Advancement)

```bash
# Unit + integration tests
cd api && pytest tests/test_control_channel.py -v

# Smoke test against staging/prod
TASK=$(curl -s -X POST $API/api/agent/tasks \
  -H "Content-Type: application/json" \
  -d '{"direction":"smoke test","task_type":"spec"}' | jq -r .id)
curl -s -X PATCH $API/api/agent/tasks/$TASK -H "Content-Type: application/json" -d '{"status":"running"}'
curl -s -X POST $API/api/agent/tasks/$TASK/control -H "Content-Type: application/json" \
  -d '{"type":"report","payload":{"reason":"smoke test"}}'  | jq .status
# Expected: "queued"
```

---

## How to Know It's Working — Observability Plan

The spec asks to "show whether it is working and make that proof clearer over time." Concrete
mechanisms:

1. **Command queue depth metric** — expose `GET /api/agent/tasks/{id}/control/commands?status=queued` count; a nonzero count that doesn't shrink over 60 seconds means the runner is not consuming the stream. Alert via Telegram on stale queue.
2. **Round-trip latency** — `acked_at - queued_at`; log this in the activity event stream. P99 < 5 s is healthy.
3. **SSE connection count** — add a counter in `control_channel_service.py` tracking active stream connections per task; expose via `GET /api/agent/tasks/{id}/control/status` (`{"connections": 1, "queue_depth": 0, "last_ack_at": "..."}`).
4. **Runner command-file growth** — runner logs `CMD_FILE_WRITTEN` activity event when it writes `.cc-control/{id}.cmd`; visible in `/tasks/{id}/stream`.
5. **Integration test coverage** — `test_sse_stream_yields_queued_commands` uses `httpx` async client to connect to the SSE stream and asserts command delivery end-to-end in < 3 seconds.

---

## Out of Scope

- Runner-side SSE listener thread implementation (separate `impl` task)
- Agent-side command file reader for claude/codex/gemini CLIs (separate `impl` task)
- Persistent (PostgreSQL-backed) command queue — in-memory is sufficient for MVP
- UI changes to send control commands from the web dashboard (follow-up UX task)
- Authentication/authorization per command (uses existing execute token mechanism)
- Binary/streaming protocols (WebSocket upgrade) — SSE is sufficient and simpler

---

## Risks and Assumptions

- **Risk**: The existing `/tasks/{id}/events` SSE endpoint and the new `/tasks/{id}/control/stream` endpoint share the same in-process event loop. Under high task load (10+ concurrent streams), async generator pressure may cause latency spikes. Mitigation: implement 1-second tick with `asyncio.sleep(1)` identical to the existing pattern.
- **Risk**: `abort_requested` added to `TaskStatus` may break existing code that does exhaustive enum matching. Assumption: no existing code uses `match`/`switch` without a default branch — verify with `grep -r "TaskStatus\." api/ --include="*.py"` before merging.
- **Assumption**: Runner processes run as single-node per task. Multi-runner deduplication is deferred.
- **Assumption**: `steer` command does not need to be delivered atomically with agent mid-run context — eventual delivery within 2 seconds is acceptable.
- **Risk**: `ask` command sets `needs_decision` status, which pauses the runner. If the operator never replies, the task is stuck indefinitely. Mitigation: implement a `ask_timeout_sec` field (default 3600) after which the command auto-expires and execution resumes with a `no_response` payload.

---

## Known Gaps and Follow-up Tasks

- Follow-up task: `impl` — Runner SSE listener thread + command file writer
- Follow-up task: `impl` — Agent-side command file reader for claude CLI (`--control-file` flag)
- Follow-up task: `impl` — Watchdog wrapper for providers that don't support control files (codex)
- Follow-up task: `impl` — PostgreSQL migration for command queue (production durability)
- Follow-up task: `impl` — `GET /api/agent/tasks/{id}/control/status` — live health of the control channel
- Follow-up task: `ux` — Operator dashboard UI: send commands, view ack status, see output_tail from report
- Follow-up task: `spec` — Authorization model: restrict `abort` to task owner or admin role only

---

## Failure/Retry Reflection

- **Failure mode**: SSE stream silently drops (Cloudflare or Traefik idle-connection timeout at 90s)
  - **Blind spot**: intermittent commands never delivered; no visible error
  - **Next action**: add SSE keepalive ping every 30 s (`data: {"event_type":"ping"}\n\n`) identical to pattern in `federation.py`

- **Failure mode**: Command written to `.cc-control/` file but runner crashes before ACKing
  - **Blind spot**: command stuck in `delivered` state forever
  - **Next action**: implement command timeout — if `delivered_at` is set but `acked_at` is null for > 30 s, re-queue the command (at-least-once delivery)

- **Failure mode**: `abort` command sent but task status transition races with runner PATCH
  - **Blind spot**: task shows `abort_requested` but runner has already finished and PATCHed `completed`
  - **Next action**: runner checks `abort_requested` before final PATCH; if set, overrides with `failed` + abort evidence

---

## Decision Gates

- **DG-1**: Should `abort_requested` be a full `TaskStatus` entry or a flag on the task? (Current spec: full status entry. Alternative: `context.abort_requested: true`. Prefer status entry for query simplicity.)
- **DG-2**: Should `steer` require a running SSE connection to be accepted, or is queuing without a live consumer acceptable? (Current spec: queue always accepted; runner drains on reconnect. This enables offline queuing before runner connects.)
- **DG-3**: Idempotency of duplicate `ControlResponse`: return `201` (lenient) or `409` (strict)? (Recommendation: `201` idempotent to avoid runner retry storms.)
