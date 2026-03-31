spec = r"""# Spec: SSE Control Channel — Real-time Steer, Checkpoint, Abort, Ask-Permission for Native Agent CLIs

**Idea ID:** `fecc6d087c4e`
**Task ID:** `task_f2ace9b291d80cfd`
**Status:** specced
**Format:** [specs/TEMPLATE.md](TEMPLATE.md)

---

## Summary

Native agent CLIs (Claude Code, Codex, Cursor Agent, Gemini CLI) today execute as long-running subprocesses with **outbound** visibility (logs, `POST /api/agent/tasks/{id}/activity` heartbeats) but **no low-latency inbound control plane**. Operators cannot steer, checkpoint, abort, or request permission without polling task state or forcibly killing processes.

This spec defines a **Server-Sent Events (SSE) control channel** that transforms every agent run from a black box into an observable, steerable process. When a task starts, the runner opens an SSE connection and runs a lightweight listener thread. Incoming **control commands** (`checkpoint`, `steer`, `abort`, `ask`, `report`, `ping`) are written to a local JSONL command file that the agent loop reads between tool turns. Agent **responses** return via POST endpoints consistent with Coherence Network Pydantic conventions.

**Goal:** Every agent run is observable and controllable in near-real-time — not a black box that runs for 5 minutes with no visibility.

### Relationship to existing behavior

| Layer | State |
|-------|-------|
| `GET /api/agent/tasks/{id}/events` (viewer SSE, ring buffer) | **Shipped** — `task_activity_routes.py` |
| `POST /api/agent/tasks/{id}/activity` (heartbeat) | **Shipped** |
| `api/scripts/task_control_channel.py` (`TaskControlChannel` runner class) | **Partial** — file protocol + SSE client |
| `api/tests/test_sse_control_channel.py` (855 lines) | **Partial** — runner-side unit tests |
| API control endpoints (`control-stream`, `control/issue`, etc.) | **MISSING** — this spec |
| Runner integration wiring in `agent_runner.py` | **MISSING** — this spec |

---

## Purpose

1. Give operators and automation a **single, documented contract** to steer live agent work without SSH or ad hoc signals.
2. Reduce incident response time: `abort` persists partial output; `steer` adjusts direction without losing audit trail.
3. Enable **ask-permission** flows where the agent pauses, surfaces a question, and resumes only after explicit allow/deny.
4. Align with CLAUDE.md: `/api/{resource}/{id}` paths, ISO 8601 UTC timestamps, Pydantic response models.

---

## Requirements

- [ ] **R1** — `GET /api/agent/tasks/{task_id}/control-stream` returns `Content-Type: text/event-stream`, supports `Last-Event-ID` resume, emits heartbeat `: ping` comments every ≤ 30s.
- [ ] **R2** — SSE command vocabulary: `checkpoint`, `steer`, `abort`, `ask`, `report`, `ping`. Each carries `command_id` (UUID4), `issued_at` (ISO UTC), optional `payload`, and `issuer`.
- [ ] **R3** — `POST /api/agent/tasks/{task_id}/control/issue` enqueues, fans out to SSE subscribers, returns HTTP 201 with `command_id`. Idempotent via optional `client_command_id`.
- [ ] **R4** — `POST /api/agent/tasks/{task_id}/control/ack` returns 201 first call, 200 on repeat (idempotent).
- [ ] **R5** — `POST /api/agent/tasks/{task_id}/control/permission` with `{command_id, decision: allow|deny}` returns 200 and unblocks runner waiting on `ask`.
- [ ] **R6** — `POST /api/agent/tasks/{task_id}/control/report` accepts structured status snapshot; stored as task activity event.
- [ ] **R7** — Commands totally ordered per `task_id`; duplicate `command_id` does NOT double-apply.
- [ ] **R8** — `TaskControlChannel` wired into `agent_runner.py`: started before subprocess spawn, stopped after. Command file: `{worktree}/.task-control` (JSONL append).
- [ ] **R9** — SSE client thread: exponential backoff with jitter on disconnect; surfaces `control_channel_disconnected` runtime event after 3 failures.
- [ ] **R10** — `ask` sets task status to `awaiting_permission`; runner blocks until permission POST or 600s timeout (auto-deny on expiry with log entry).
- [ ] **R11** — AuthZ: issue/ack/permission callers need write permission on task (same as `PATCH /api/agent/tasks/{id}`); stream subscriber needs read permission.
- [ ] **R12** — All queue/dispatch logic in `api/app/services/task_control_service.py`; routers thin (per CLAUDE.md).
- [ ] **R13** — Runtime events emitted: `control_command_issued`, `control_command_acked`, `control_channel_error`, `control_channel_connected`.
- [ ] **R14** — `api/tests/test_sse_control_channel.py` passes; new route contract tests in `api/tests/test_task_control_routes.py`.

---

## API Contract

### `GET /api/agent/tasks/{task_id}/control-stream`

**Purpose:** Runner opens at task start, keeps open for task lifetime.

**Query:** `since_event_id` (optional) — resume from last event id after reconnect.

**SSE format:**
```
id: 42
data: {"type":"control_command","command":"steer","command_id":"a1b2c3d4-e5f6-7890-abcd-ef1234567890","issued_at":"2026-03-28T12:00:00Z","issuer":"operator","payload":{"new_direction":"Fix tests only"}}

: ping
```

**Stream close:** `event: end` with `data: {"type":"control_closed","task_id":"..."}` when task reaches terminal status.

**Errors:** 404 (task not found), 403 (not authorized), 409 (exclusive consumer conflict if single-runner policy chosen).

---

### `POST /api/agent/tasks/{task_id}/control/issue`

**Request:**
```json
{"command": "checkpoint", "payload": {}, "client_command_id": "optional-uuid"}
```

**Response 201:**
```json
{"command_id": "uuid4", "task_id": "task_...", "queued_at": "2026-03-28T12:00:00.000Z", "duplicate": false}
```

**Response 202:** Same body with `"duplicate": true` on replayed `client_command_id`.

**Errors:** 404 (task not found), 409 (task terminal), 422 (invalid command or missing payload).

---

### `POST /api/agent/tasks/{task_id}/control/ack`

**Request:** `{"command_id": "uuid4", "status": "applied", "detail": "Checkpoint written"}`

**Response 201:** `{"ok": true, "recorded_at": "2026-03-28T12:00:01.000Z"}`

**Edge:** Second ack with same `command_id` returns **200** (idempotent), not 500.

---

### `POST /api/agent/tasks/{task_id}/control/permission`

**Request:** `{"command_id": "uuid4", "decision": "allow", "note": "Approved shell command"}`

**Response 200:** `{"ok": true}`

**Errors:** 404 (command_id not found), 409 (already resolved).

---

### `POST /api/agent/tasks/{task_id}/control/report`

**Request:**
```json
{
  "command_id": "uuid4",
  "phase": "implementing",
  "progress_pct": 40,
  "current_files": ["api/app/foo.py"],
  "summary": "Handler added; running tests next"
}
```

**Response 201:** `{"ok": true}`

---

## Data Model

```yaml
ControlCommand:
  command_id:    { type: string, format: uuid4 }
  task_id:       { type: string }
  command:       { type: string, enum: [checkpoint, steer, abort, ask, report, ping] }
  issued_at:     { type: string, format: date-time }
  issuer:        { type: string }
  payload:       { type: object, nullable: true }
  state:         { type: string, enum: [queued, delivered, acked, failed] }

ControlAck:
  command_id:    { type: string, format: uuid4 }
  status:        { type: string, enum: [received, applied, rejected] }
  detail:        { type: string, nullable: true }
  reason_code:   { type: string, nullable: true }

PermissionResolution:
  command_id:    { type: string, format: uuid4 }
  decision:      { type: string, enum: [allow, deny] }
  note:          { type: string, nullable: true }

ControlReport:
  command_id:    { type: string, format: uuid4 }
  phase:         { type: string }
  progress_pct:  { type: integer, minimum: 0, maximum: 100 }
  current_files: { type: array, items: string }
  summary:       { type: string }
```

**Storage (MVP):** In-memory per-task command queue (consistent with activity ring buffer). Production follow-up: PostgreSQL `task_control_commands` table.

---

## Observability and Proof Evolution

*Answering the open question: "How can we improve this idea, show whether it is working yet, and make that proof clearer over time?"*

### Phase 0 — Design (current)
This spec + task card. Idea stage: `specced`.

### Phase 1 — MVP proof (after implementation)
- Dashboard widget: command latency histogram (issued_at to ack timestamp), from runtime events.
- CI: `pytest api/tests/test_task_control_routes.py` required on every PR.
- Manual Scenario 1 curl output pasted into PR description.

### Phase 2 — Synthetic production verification
- Nightly CI creates `synthetic_sse_probe` task, issues `report`, asserts ack < 2s P95.
- Publishes `control_smoke_test` runtime event; status badge in `docs/STATUS.md`.

### Phase 3 — Continuous metrics in `docs/STATUS.md`

| Metric | SLO |
|--------|-----|
| `control_commands_issued` (7d) | — |
| `control_acks_p95_ms` | < 2000 ms |
| `control_failures` (7d) | 0 |
| `ask_permission_unblocked` (7d) | — |

### Proof artifacts per PR
- OpenAPI diff showing new paths.
- `pytest -q tests/test_task_control_routes.py` green output.
- Curl Scenario 1 output pasted in PR description.

---

## Files to Create/Modify

| File | Action |
|------|--------|
| `api/app/routers/task_control_routes.py` | CREATE — SSE + 4 POST routes |
| `api/app/services/task_control_service.py` | CREATE — queue, idempotency, fan-out |
| `api/app/models/task_control.py` | CREATE — Pydantic models |
| `api/app/main.py` | MODIFY — register router |
| `api/scripts/agent_runner.py` | MODIFY — wire TaskControlChannel |
| `api/scripts/task_control_channel.py` | EXISTS — update SSE URL to `/control-stream` |
| `api/tests/test_sse_control_channel.py` | EXISTS — add route contract tests |
| `api/tests/test_task_control_routes.py` | CREATE — FastAPI TestClient tests |
| `docs/RUNBOOK.md` | MODIFY — operator procedures section |

---

## Acceptance Criteria

- [x] Bidirectional control (SSE + POST) and command file bridge fully described.
- [x] Concrete API paths and JSON shapes with examples.
- [x] 5 verification scenarios executable against production (see below).
- [x] Auth, idempotency, and ordering addressed.
- [x] Risks, Known Gaps, Verification sections per CLAUDE.md / SPEC-QUALITY-GATE.
- [x] Proof evolution plan answering the open question.
- [x] Existing partial implementation acknowledged; delta scoped precisely.

---

## Task Card

```yaml
goal: Add SSE control-stream + POST control/* endpoints and wire TaskControlChannel into agent_runner so native CLIs receive checkpoint/steer/abort/ask/report commands in real-time.
files_allowed:
  - api/app/routers/task_control_routes.py
  - api/app/services/task_control_service.py
  - api/app/models/task_control.py
  - api/app/main.py
  - api/scripts/agent_runner.py
  - api/scripts/task_control_channel.py
  - api/tests/test_sse_control_channel.py
  - api/tests/test_task_control_routes.py
  - docs/RUNBOOK.md
done_when:
  - GET /api/agent/tasks/{id}/control-stream emits SSE with id fields and ping heartbeats
  - POST .../control/issue returns 201 with command_id; fans out to connected subscribers
  - POST .../control/ack idempotent (201 first, 200 repeat)
  - POST .../control/permission unblocks runner, returns 200
  - POST .../control/report stores activity event
  - agent_runner.py starts TaskControlChannel before provider subprocess, stops after
  - all 5 verification scenarios pass via curl against staging
  - pytest api/tests/test_task_control_routes.py passes
commands:
  - cd api && pytest -q tests/test_sse_control_channel.py tests/test_task_control_routes.py
  - python3 scripts/validate_spec_quality.py --base origin/main --head HEAD
constraints:
  - no provider-specific logic in routers (CLAUDE.md)
  - do not modify existing tests to force passing
  - auth must match existing agent route patterns exactly
```

---

## Verification Scenarios

All scenarios: `API=https://api.coherencycoin.com`. Replace `{task_id}` with a running task ID.

### Scenario 1 — Full control cycle: issue -> SSE delivery -> ack

**Setup:** Task with `status=running`. Runner connected to `GET /api/agent/tasks/{task_id}/control-stream`.

**Action:**
```bash
# Issue a report command
RESP=$(curl -sS -X POST "$API/api/agent/tasks/{task_id}/control/issue" \
  -H "Content-Type: application/json" \
  -d '{"command":"report","payload":{}}')
echo "$RESP"
# SSE client receives matching command_id within 2s (runner or test harness)
CMD_ID=$(echo "$RESP" | jq -r '.command_id')
# Runner acks
curl -sS -X POST "$API/api/agent/tasks/{task_id}/control/ack" \
  -H "Content-Type: application/json" \
  -d "$(jq -n --arg id "$CMD_ID" '{command_id:$id,status:"applied",detail:"ok"}')"
```

**Expected:**
- Issue: HTTP 201, non-empty `command_id`, `"duplicate": false`, ISO `queued_at`.
- SSE: `data:` line within 2s containing `"command":"report"` with matching `command_id`.
- Ack: HTTP 201, `{"ok": true, "recorded_at": "<timestamp>"}`.

**Edge:** Re-POST ack with same `command_id` returns HTTP **200** (idempotent), not 500 or duplicate row.

---

### Scenario 2 — Steer changes visible in task context

**Setup:** Task with `status=running`.

**Action:**
```bash
curl -sS -X POST "$API/api/agent/tasks/{task_id}/control/issue" \
  -H "Content-Type: application/json" \
  -d '{"command":"steer","payload":{"new_direction":"Fix only translate_service.py, ignore all other files"}}'
```

**Expected:** HTTP 201. `GET /api/agent/tasks/{task_id}` shows updated `context.direction` or `steer_history` entry with ISO timestamp. Field stable in OpenAPI.

**Edge:** `steer` with `"payload": {}` (missing `new_direction`) returns HTTP **422** Pydantic detail — not 500.

---

### Scenario 3 — Ask + permission gate blocks and unblocks runner

**Setup:** Task with `status=running`; runner subscribed to control-stream.

**Action:**
```bash
ASK=$(curl -sS -X POST "$API/api/agent/tasks/{task_id}/control/issue" \
  -H "Content-Type: application/json" \
  -d '{"command":"ask","payload":{"prompt":"May I delete /tmp/build-artifacts?","scope":"shell"}}')
CMD_ID=$(echo "$ASK" | jq -r '.command_id')

# Verify blocking state
STATUS=$(curl -sS "$API/api/agent/tasks/{task_id}" | jq -r '.status')
# $STATUS must be needs_decision or awaiting_permission

# Resolve permission
curl -sS -X POST "$API/api/agent/tasks/{task_id}/control/permission" \
  -H "Content-Type: application/json" \
  -d "$(jq -n --arg id "$CMD_ID" '{command_id:$id,decision:"allow",note:"Approved"}')"
```

**Expected:**
- Status shows `needs_decision` or `awaiting_permission` (documented enum value).
- Permission: HTTP 200. Subsequent GET shows `status=running`. Runtime event `permission_resolved` in `/api/agent/tasks/{task_id}/events`.

**Edge:** Permission with unknown `command_id` returns HTTP **404** `{"detail":"command not found"}` — not 500.

---

### Scenario 4 — Abort stops execution and preserves partial output

**Setup:** Long-running task with runner subscribed.

**Action:**
```bash
ABORT=$(curl -sS -X POST "$API/api/agent/tasks/{task_id}/control/issue" \
  -H "Content-Type: application/json" \
  -d '{"command":"abort","payload":{"reason":"operator_requested"}}')
CMD_ID=$(echo "$ABORT" | jq -r '.command_id')
# Runner acks when stopping
curl -sS -X POST "$API/api/agent/tasks/{task_id}/control/ack" \
  -H "Content-Type: application/json" \
  -d "$(jq -n --arg id "$CMD_ID" '{command_id:$id,status:"applied",detail:"Graceful stop, checkpoint written"}')"
# Verify terminal state
curl -sS "$API/api/agent/tasks/{task_id}" | jq '.status'
# Must be: failed or cancelled
```

**Expected:** Task status in `{failed, cancelled}` with non-empty `output` or `current_step` referencing abort. Log tail contains abort reference. Activity includes `control_command_acked`.

**Edge:** Second `abort` on already terminal task returns HTTP **409** `{"detail":"task_not_running"}`.

---

### Scenario 5 — Error handling: missing task and bad auth

**Setup:** Use task ID `nonexistent-task-id-000`.

**Action:**
```bash
# 404: unknown task
curl -sS -o /dev/null -w "%{http_code}\n" \
  -X POST "$API/api/agent/tasks/nonexistent-task-id-000/control/issue" \
  -H "Content-Type: application/json" -d '{"command":"checkpoint"}'
# Expected: 404

# 401/403: bad auth token
curl -sS -o /dev/null -w "%{http_code}\n" \
  -X POST "$API/api/agent/tasks/{valid_task_id}/control/issue" \
  -H "Authorization: Bearer invalid-token" \
  -H "Content-Type: application/json" -d '{"command":"checkpoint"}'
# Expected: 401 or 403

# 422: invalid command enum value
curl -sS -o /dev/null -w "%{http_code}\n" \
  -X POST "$API/api/agent/tasks/{valid_task_id}/control/issue" \
  -H "Content-Type: application/json" -d '{"command":"unknown_command_xyz"}'
# Expected: 422
```

**Expected:** None return 500. Each returns the documented error code with a JSON body matching the API error schema.

---

## Concurrency Behavior

- **Per task:** One authoritative command queue; SSE subscribers receive broadcast copies.
- **Exclusive runner vs. multi-observer:** Multiple readers on `control-stream` OK; second exclusive runner 409 policy is product choice — document in OpenAPI.
- **Command file:** Append-only JSONL, single-writer (one runner per task), no cross-process locking for MVP.
- **Permission gate:** Runner blocks on `threading.Event` per `command_id`; 600s timeout auto-denies.

---

## Out of Scope

- Replacing existing log streaming or viewer-facing activity SSE.
- Vendor-specific wire protocols inside Claude/Codex binaries.
- WebSockets or bidirectional RPC.
- Persistent PostgreSQL audit table (follow-up task).

---

## Risks and Assumptions

- **Risk:** SSE buffered by Cloudflare/proxies. Mitigation: `: ping` heartbeats, `X-Accel-Buffering: no` header.
- **Risk:** In-memory queue lost on API restart. Mitigation: document MVP limitation; operator re-issues.
- **Risk:** `ask` gate blocks runner indefinitely. Mitigation: 600s default timeout, auto-deny on expiry.
- **Assumption:** Runners have outbound HTTPS to API (already required for activity heartbeats).
- **Assumption:** One runner per task at a time (single-writer for command file).

---

## Known Gaps and Follow-up Tasks

- Persisted PostgreSQL `task_control_commands` audit table.
- Rate limits on `control/issue` per task.
- Telegram: `/steer` reply -> `POST .../control/issue` (via `agent_telegram.py`).
- Web UI: "Steer / Checkpoint / Abort" buttons in task detail drawer.
- CLI subcommand: `cc task control <id> steer "..."`.
- `Last-Event-ID` reconnect replay (requires persistence follow-up).

---

## Failure/Retry Reflection

- **Failure mode:** SSE disconnect mid-task loses queued commands. **Blind spot:** Silent loss without resume. **Next action:** Persist queue + implement `Last-Event-ID` replay.
- **Failure mode:** Permission gate timeout not implemented. **Blind spot:** Runner hangs forever on unanswered ask. **Next action:** Add `ask_timeout_seconds` config (default 600), auto-deny on expiry.

---

## Research Inputs

- `2026-03-28` — `api/app/routers/task_activity_routes.py` — existing `StreamingResponse` SSE pattern for in-memory ring buffer.
- `2026-03-28` — `api/scripts/task_control_channel.py` — existing `TaskControlChannel` class confirming file protocol and command vocabulary.
- `2026-03-28` — `api/tests/test_sse_control_channel.py` — 855-line test suite; confirms command vocabulary and JSONL format.
- `2026-03-28` — `api/app/routers/federation.py` — SSE broadcast fan-out pattern to adapt for control channel.
- `2026-03-28` — `specs/agent-sse-control-channel.md` — prior draft; superseded by this file.

---

## Decision Gates

- **Single-consumer vs. broadcast** for `control-stream` — decide before coding; document in OpenAPI `description` field.
- **`ask` status value** — use existing `needs_decision` or new `awaiting_permission`? Impacts Telegram handler and dashboard filter chips. Must align with task status enum before implementing R10.
"""

with open("specs/task_f2ace9b291d80cfd.md", "w") as f:
    f.write(spec)

print(f"Written: {len(spec)} chars, {spec.count(chr(10))} lines")
