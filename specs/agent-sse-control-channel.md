# Spec: SSE Control Channel for Native Agent CLIs (idea `agent-sse-control-channel`)

*Format: [specs/TEMPLATE.md](TEMPLATE.md)*

## Summary

Native agent CLIs (Claude Code, Codex, Cursor agent, Gemini CLI, OpenClaw-wrapped flows) today execute as long-running subprocesses with **outbound** visibility (logs, `POST /api/agent/tasks/{id}/activity` heartbeats) but **no low-latency inbound control plane**. Operators and automation cannot steer, checkpoint, abort, or request permission without polling task state or killing processes.

This spec defines a **Server-Sent Events (SSE) control channel** scoped to a running `task_id`: when execution starts, the runner opens an SSE connection to the API and runs a lightweight listener thread. **Control commands** (checkpoint, steer, abort, ask, report-request) are delivered as SSE events, persisted in order, and mirrored to a **local command file** that the agent loop reads between tool turns. **Agent responses** (acknowledgements, permission answers, status payloads) return via existing or new `POST` endpoints so the API and UIs stay consistent with Coherence Network’s Pydantic response model.

**Goal:** Every agent run is **observable and controllable in near real time**—not a black box that runs for minutes with no steering surface.

**Relationship to existing behavior**

- **Already implemented (observe path):** `GET /api/agent/tasks/{task_id}/events` exposes SSE for **viewers** (polls in-memory task stream every 2s). `POST /api/agent/tasks/{task_id}/activity` records runner events. See `api/app/routers/task_activity_routes.py`.
- **This spec adds (control path):** A distinct SSE stream (or clearly namespaced event types) for **commands addressed to the runner**, plus POST endpoints for command lifecycle and agent replies, plus runner-side command-file protocol shared across providers.

---

## Purpose

1. Give operators and automation a **single, documented contract** to steer live agent work without SSH or ad hoc signals.
2. Reduce incident time when a task drifts: **abort** and persist partial output; **steer** without losing audit trail.
3. Enable **ask-permission** flows where the agent pauses, surfaces a question through the API, and resumes only after an explicit allow/deny.
4. Align with CLAUDE.md conventions: API paths `/api/{resource}/{id}`, ISO 8601 UTC timestamps, Pydantic models for requests and responses.

---

## Requirements

- [ ] **R1 — Control SSE endpoint:** Expose `GET /api/agent/tasks/{task_id}/control-stream` (or equivalent name fixed at implementation) that returns `Content-Type: text/event-stream`, supports **Last-Event-ID** / resume semantics for reconnects, and emits **only** control-plane events (not duplicate full log tail unless explicitly requested).
- [ ] **R2 — Command vocabulary:** SSE `data` JSON MUST support at minimum: `checkpoint`, `steer`, `abort`, `ask`, `report` (report = request a structured status snapshot from the agent). Each carries `command_id` (UUID), `issued_at` (ISO UTC), optional `payload` (object), and optional `issuer` (`operator` | `automation` | `telegram` | `api_key`).
- [ ] **R3 — Idempotency & ordering:** Commands are **totally ordered** per `task_id`. Duplicate delivery with the same `command_id` MUST NOT double-apply; runner acknowledges once via POST.
- [ ] **R4 — Command file bridge:** Runner writes incoming commands to a deterministic path, e.g. `{worktree}/.coherence/control/{task_id}.jsonl` (exact path in implementation spec), appending one JSON line per command. File rotation/truncation rules MUST be documented (max size, head trim on checkpoint).
- [ ] **R5 — Listener thread:** Provider execution wrapper (`local_runner.py` / `agent_runner.py` integration point) starts an SSE client thread **before** subprocess spawn; on connection failure, exponential backoff with jitter and surfaced friction event (`control_channel_disconnected`).
- [ ] **R6 — POST acknowledgements:** `POST /api/agent/tasks/{task_id}/control/ack` with body `{ "command_id", "status": "received"|"applied"|"rejected", "detail"?: str }` (201). Rejected commands include machine-readable `reason_code`.
- [ ] **R7 — Ask-permission loop:** For `ask`, agent sets task `status` to `needs_decision` or a dedicated `awaiting_permission` (product decision); `POST /api/agent/tasks/{task_id}/control/permission` with `{ "command_id", "decision": "allow"|"deny", "note"?: str }` unblocks the runner.
- [ ] **R8 — AuthZ:** Only callers with permission to mutate the task (same rules as `PATCH /api/agent/tasks/{id}`) may issue controls; stream subscribers must be authenticated in production (token or session); document dev-mode bypass.
- [ ] **R9 — Executor isolation:** Per CLAUDE.md, **no** provider-specific branching in CRUD routers; command enqueue/dispatch lives in a dedicated service module (e.g. `task_control_service.py`) called from the router.
- [ ] **R10 — Observability:** Emit runtime events compatible with `/api/runtime/events` for `control_command_issued`, `control_command_acked`, `control_channel_error` (implementation detail, must be listed in verification).

---

## API Contract

### `GET /api/agent/tasks/{task_id}/control-stream`

**Purpose:** Runner (or authorized observer) opens this SSE stream at task start and keeps it open for the task lifetime.

**Query (optional)**

- `since_event_id`: string — resume after last received server-side event id (align with SSE `id:` field).

**Headers**

- `Authorization` / session cookie as per existing agent API.

**SSE format**

- Each message: optional `id: <monotonic_id>` line, then `data: <json>`.
- Heartbeat comment lines `: ping` every ≤ 30s if no command (configurable) to detect proxies dropping the connection.

**Example `data` payload (command)**

```json
{
  "type": "control_command",
  "command": "steer",
  "command_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "issued_at": "2026-03-28T12:00:00.000Z",
  "issuer": "operator",
  "payload": {
    "new_direction": "Focus on tests in api/tests/test_agent.py only"
  }
}
```

**Stream end:** When task reaches terminal status (`completed`, `failed`, `cancelled`), server sends final `event: end` with `data: {"type":"control_closed","task_id":"..."}` and closes.

**Errors**

- `404` — task does not exist.
- `403` — not allowed to attach control channel to this task.
- `409` — optional: second exclusive consumer when policy is single-runner-only (product choice; must be documented).

---

### `POST /api/agent/tasks/{task_id}/control/issue` (operator/automation → queue)

**Purpose:** Issue a control command without raw SSE (e.g. from UI, Telegram, or CI). Commands are **pushed** to any connected `control-stream` listeners and persisted to the task’s pending queue.

**Request**

```json
{
  "command": "checkpoint",
  "payload": {},
  "client_command_id": "optional-uuid-for-idempotency"
}
```

**Response 201**

```json
{
  "command_id": "uuid",
  "task_id": "task_...",
  "queued_at": "2026-03-28T12:00:00.000Z",
  "duplicate": false
}
```

**Response 202** — same as 201 with `duplicate: true` if `client_command_id` replayed.

---

### `POST /api/agent/tasks/{task_id}/control/ack`

**Request**

```json
{
  "command_id": "uuid",
  "status": "applied",
  "detail": "Wrote .task-checkpoint.md and flushed git stash pointer"
}
```

**Response 201** — `{ "ok": true, "recorded_at": "..." }`

---

### `POST /api/agent/tasks/{task_id}/control/permission`

**Request**

```json
{
  "command_id": "uuid",
  "decision": "allow",
  "note": "Approved shell command"
}
```

**Response 200** — `{ "ok": true }`; runner unblocks.

---

### `POST /api/agent/tasks/{task_id}/control/report` (agent → server)

**Purpose:** Structured status snapshot in response to `report` command or periodic telemetry.

**Request**

```json
{
  "command_id": "uuid",
  "phase": "implementing",
  "progress_pct": 40,
  "current_files": ["api/app/foo.py"],
  "summary": "Added handler; running tests next"
}
```

**Response 201**

---

## Data Model

```yaml
ControlCommand:
  command_id: { type: string, format: uuid }
  task_id: { type: string }
  command: { type: string, enum: [checkpoint, steer, abort, ask, report] }
  issued_at: { type: string, format: date-time }
  issuer: { type: string }
  payload: { type: object }
  state: { type: string, enum: [queued, delivered, acked, failed] }

ControlAck:
  command_id: { type: string }
  status: { type: string, enum: [received, applied, rejected] }
  detail: { type: string, optional: true }
  reason_code: { type: string, optional: true }

PermissionResolution:
  command_id: { type: string }
  decision: { type: string, enum: [allow, deny] }
  note: { type: string, optional: true }
```

**Storage:** MVP may use in-memory queue per task keyed by `task_id` (consistent with current task activity ring buffer); production path should persist to PostgreSQL for audit. Spec leaves migration as follow-up if DB already required elsewhere.

---

## Web / CLI Surfaces (reference)

| Surface | Purpose |
|--------|---------|
| **Web** | `/tasks` or task detail drawer: “Steer”, “Checkpoint”, “Abort”, “Ask” buttons calling `POST .../control/issue` |
| **CLI** | Extend `cc` (Coherence CLI) with `cc task control <task_id> steer "..."` → POST issue (exact subcommands in implementation ticket) |
| **curl** | All scenarios below use `curl` against `$API` for production verification |

---

## Files to Create/Modify (implementation phase — not part of this spec-only commit unless separately tasked)

- `api/app/routers/task_activity_routes.py` or new `api/app/routers/task_control_routes.py` — SSE + POST routes
- `api/app/services/task_control_service.py` — queue, idempotency, fan-out to SSE subscribers
- `api/app/models/task_control.py` — Pydantic models
- `api/scripts/local_runner.py` / `api/scripts/agent_runner.py` — SSE listener thread + JSONL command file
- `api/tests/test_task_control_channel.py` — contract tests
- `docs/RUNBOOK.md` — operator procedure for steer/abort

---

## Acceptance Criteria (spec quality)

- [x] Describes bidirectional control (SSE + POST) and command file bridge.
- [x] Lists concrete API paths and JSON shapes.
- [x] Names verification scenarios executable against production.
- [x] Addresses auth, idempotency, and ordering.
- [x] Includes Risks, Known Gaps, and **Verification** sections per CLAUDE.md / SPEC-QUALITY-GATE.
- [x] Explains how we will **prove** the feature works and improve that proof over time (see below).

---

## Observability & Proof Evolution (open question)

**How we improve the idea and show it is working**

1. **Phase 0 (design):** This spec + task card; idea stage `specced`.
2. **Phase 1 (MVP):** Implement control issue + SSE + ack; dashboard widget shows **command latency** (issued_at → ack timestamp histogram).
3. **Phase 2:** Golden-path integration test in CI using `httpx` AsyncClient + SSE client; nightly **synthetic task** on production that issues `report` and asserts ack &lt; 2s P95.
4. **Phase 3:** Link **runtime events** to Grafana-style exports (existing `/api/runtime/events`) with `task_id` + `command_id` for traceability.
5. **Clarity over time:** Publish a **single** markdown metric table in `docs/STATUS.md` or pipeline dashboard: `control_commands_issued`, `control_acks`, `control_failures`, `median_round_trip_ms` — updated by CI smoke.

**Proof artifacts**

- PR includes pytest + OpenAPI diff.
- Production verification via scenarios in the next section (curl + optional `cc`).

---

## Verification

### Automated (future implementation)

```bash
cd api && pytest -q api/tests/test_task_control_channel.py
cd api && ruff check api/app/routers api/app/services/task_control_service.py
```

### Spec quality (when this file changes)

```bash
python3 scripts/validate_spec_quality.py --base origin/main --head HEAD
```

---

## Verification Scenarios

These scenarios are the **contract** for reviewers. They MUST pass on production after implementation. All use `API=https://api.coherencycoin.com` (or staging equivalent documented in deploy notes).

### Scenario 1 — Full control cycle: issue → SSE delivery → ack

- **Setup:** A task exists with `status=running` (or create via `POST /api/agent/tasks` and mark running per test harness). A runner (or test harness) is connected to `GET /api/agent/tasks/{task_id}/control-stream` with valid auth.
- **Action:**
  1. `curl -sS -X POST "$API/api/agent/tasks/{task_id}/control/issue" -H "Content-Type: application/json" -d '{"command":"report","payload":{}}'`
  2. On the SSE client, read until one `data:` line contains `"command":"report"` and a `command_id` UUID.
  3. `curl -sS -X POST "$API/api/agent/tasks/{task_id}/control/ack" -H "Content-Type: application/json" -d '{"command_id":"<id>","status":"applied","detail":"ok"}'`
- **Expected result:**
  - Issue returns HTTP **201** with JSON containing non-empty `command_id` and `"duplicate": false`.
  - SSE payload includes `type`/`command` matching issue, same `command_id`.
  - Ack returns HTTP **201** and `{ "ok": true }` (or equivalent contract field).
- **Edge case:** Re-POST ack with same `command_id` returns **200** with idempotent success OR **409** with clear body — behavior must be one of these and documented; must not create duplicate audit rows with conflicting state.

### Scenario 2 — Steer changes visible task context

- **Setup:** Task `task_id` has `context.direction` set to an initial string (from `GET /api/agent/tasks/{id}`).
- **Action:** `curl -sS -X POST "$API/api/agent/tasks/{task_id}/control/issue" -d '{"command":"steer","payload":{"new_direction":"Updated: fix only translate_service.py"}}'`
- **Expected result:** After runner applies (simulated or real), `GET /api/agent/tasks/{task_id}` shows updated direction or a nested `context.steer_history` entry with timestamp (exact field per implementation, must be stable in OpenAPI).
- **Edge case:** `steer` with empty `new_direction` returns **422** with Pydantic detail array, not 500.

### Scenario 3 — Ask + permission gate

- **Setup:** Running task; runner receives `ask` command with `payload.prompt` describing the permission question.
- **Action:**
  1. Issue `ask` via `POST .../control/issue`.
  2. `GET /api/agent/tasks/{task_id}` shows status indicating wait (e.g. `needs_decision` or documented `awaiting_permission`).
  3. `curl -sS -X POST "$API/api/agent/tasks/{task_id}/control/permission" -d '{"command_id":"<id>","decision":"allow"}'`
- **Expected result:** HTTP **200** on permission; subsequent GET shows task back to `running` and an activity/runtime event `permission_resolved`.
- **Edge case:** `permission` with wrong `command_id` returns **404** or **409** with message `unknown_command_id` — not 500.

### Scenario 4 — Abort stops execution and persists outcome

- **Setup:** Long-running task with runner connected.
- **Action:** Issue `abort` via `POST .../control/issue`; runner sends final `POST .../control/ack` with `status":"applied"`; task completes with terminal status.
- **Expected result:** `GET /api/agent/tasks/{task_id}` returns `status` in `failed` or `cancelled` (documented enum) with non-empty `output` or `current_step` indicating graceful stop; `GET /api/agent/tasks/{task_id}/log` contains tail referencing abort.
- **Edge case:** Second `abort` for already terminal task returns **409** `task_not_running`.

### Scenario 5 — Error handling: missing task and bad auth

- **Setup:** Invalid task id `nonexistent-task-id`.
- **Action:** `curl -sS -o /dev/null -w "%{http_code}" -X POST "$API/api/agent/tasks/nonexistent-task-id/control/issue" -d '{"command":"checkpoint"}'`
- **Expected result:** HTTP **404** body `{"detail":"Not found"}` or consistent API error shape.
- **Edge case:** Valid task but missing/invalid auth header returns **401** or **403** (match existing agent routes).

---

## Concurrency Behavior

- **Per task:** One authoritative control queue; SSE subscribers receive a **copy** of each issued command.
- **Exclusive runner:** If product chooses single runner, second `control-stream` connection returns 409 or disconnects prior session — must be explicit in implementation.
- **Command file:** Runner must use file locking or atomic rename when updating JSONL to avoid torn reads.

---

## Out of Scope

- Replacing existing log streaming (`GET .../log`) or generic activity SSE for viewers.
- Defining vendor-specific wire protocols inside Claude/Codex binaries (we only specify **runner wrapper** behavior).
- WebRTC or bidirectional WebSockets (SSE-only for server→client; POST for client→server).

---

## Risks and Assumptions

- **Risk:** SSE through Cloudflare/proxies may buffer; mitigation: heartbeat comments, `X-Accel-Buffering: no`, documented timeout tuning.
- **Risk:** In-memory queue lost on API restart; mitigation: persist command queue when task store persists; document MVP limitation.
- **Assumption:** Runners always have outbound HTTPS to API (already required for activity); control stream uses same channel.

---

## Known Gaps and Follow-up Tasks

- Persisted queue + audit table for SOC2-style review.
- Rate limits on `control/issue` per task to prevent operator storms.
- Telegram mapping: map `/steer` replies to `control/issue` (see `api/app/routers/agent_telegram.py`).

---

## Failure/Retry Reflection

- **Failure mode:** SSE disconnect mid-task.
- **Blind spot:** Silent partial loss of commands without `since_event_id` resume.
- **Next action:** Implement `Last-Event-ID` and runner-side replay from API on reconnect.

---

## Task Card (implementation)

```yaml
goal: Add SSE control channel and POST control endpoints so native agent runners receive checkpoint/steer/abort/ask/report commands in real time, with JSONL bridge and ack/permission paths.
files_allowed:
  - api/app/routers/task_control_routes.py
  - api/app/services/task_control_service.py
  - api/app/models/task_control.py
  - api/app/routers/agent.py
  - api/scripts/local_runner.py
  - api/tests/test_task_control_channel.py
done_when:
  - GET /api/agent/tasks/{id}/control-stream emits control commands with SSE ids
  - POST /api/agent/tasks/{id}/control/issue queues and fans out
  - POST .../control/ack and .../permission behave per Verification Scenarios
  - Runner writes JSONL command file and passes pytest contract tests
commands:
  - cd api && pytest -q tests/test_task_control_channel.py
  - curl scenarios from Verification Scenarios section against staging
constraints:
  - provider-specific logic only in agent_service_executor / command_templates per CLAUDE.md
  - do not modify unrelated agent tests to mask failures
```

---

## Research Inputs (Required)

- `2026-03-28` - [task_activity_routes.py](../api/app/routers/task_activity_routes.py) — existing SSE pattern for task events (`GET /tasks/{task_id}/events`).
- `2026-03-28` - [task_activity_service.py](../api/app/services/task_activity_service.py) — in-memory task stream; control queue may extend or parallel this.
- `2026-03-28` - [002-agent-orchestration-api.md](./002-agent-orchestration-api.md) — baseline task API and PATCH semantics.
- `2026-03-28` - [MDN: Using server-sent events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events) — SSE reconnect and `EventSource` behavior (browser); runners may use HTTP client with stream read.
- `2026-03-28` - FastAPI `StreamingResponse` documentation — streaming patterns for production ASGI.

---

## Decision Gates

- Choose **single consumer vs broadcast** for `control-stream` before coding.
- Choose whether `ask` maps to existing `needs_decision` or a new substate (impacts Telegram and dashboards).
