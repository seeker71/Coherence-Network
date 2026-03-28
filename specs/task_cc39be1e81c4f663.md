# Spec: SSE Control Channel for Native Agent CLIs (Real-Time Steer, Checkpoint, Abort, Ask-Permission)

## Purpose

Native agent CLIs (Claude Code, Codex, Cursor Agent, Gemini CLI, and similar) today execute as long-running subprocesses with weak real-time observability: operators see little until a task completes or fails. This spec defines a **Server-Sent Events (SSE) control plane** so that when a runner starts a provider process for a Coherence task, the process **subscribes to an SSE stream** keyed by `task_id`. While the agent runs, the network can push **checkpoint**, **steer**, **abort**, **ask** (human-in-the-loop permission), and **report** commands. The runner wraps provider execution with an **SSE listener thread** that writes incoming commands to a **well-known command file** (or equivalent IPC) that the agent loop reads between steps; **responses and telemetry flow back via authenticated POST** endpoints so the API remains the system of record.

This makes every agent **observable and controllable in near real time** instead of a black box that runs for minutes with no visibility—without replacing provider CLIs or duplicating their internal state machines.

## Summary

- **Inbound (network → agent):** SSE events carrying typed control commands, delivered to the runner and surfaced to the CLI via a command queue (file-backed for portability across providers).
- **Outbound (agent → network):** Structured POST payloads for acknowledgements, progress, permission answers, and errors.
- **Proof over time:** Versioned event schema, metrics, and integration tests so operators can see whether the channel is **live**, **lossless enough for ops**, and **actually affecting** agent behavior.

## Requirements

- [ ] **R1 — SSE subscription:** For a running task, a client with valid credentials can open `GET /api/agent/tasks/{task_id}/control/stream` and receive a continuous `text/event-stream` with `event:` types `checkpoint`, `steer`, `abort`, `ask`, `report`, `ping`, and `error`.
- [ ] **R2 — Command envelope:** Each SSE `data:` line is JSON with at least: `command_id` (UUID), `type` (enum above), `payload` (object), `issued_at` (ISO 8601 UTC), `issuer` (string or service principal id). Duplicate `command_id` must be detectable idempotently on the consumer side.
- [ ] **R3 — Enqueue path (orchestrator/UI):** Authorized callers can enqueue a control command without holding the SSE connection long-term: `POST /api/agent/tasks/{task_id}/control/commands` with body matching the same envelope (minus stream-specific fields). The API fans out to connected SSE subscribers and persists a short retention audit for debugging.
- [ ] **R4 — Runner integration:** The federation runner (e.g. `api/scripts/local_runner.py` or successor) starts an **SSE listener thread** when spawning a provider CLI; the thread writes **one JSON line per command** to a deterministic path such as `.coherence/control/{task_id}.jsonl` (exact path documented in runner docs) and signals the agent wrapper to read between tool rounds.
- [ ] **R5 — Agent responses:** The agent (or thin wrapper) POSTs to `POST /api/agent/tasks/{task_id}/control/ack` with `command_id`, `status` (`received` | `applied` | `rejected` | `failed`), optional `message`, and optional structured `result` (e.g. checkpoint artifact URI, steer acceptance, ask answer).
- [ ] **R6 — Activity and status:** Steer/abort/checkpoint outcomes must be reflected in task-visible state: at minimum append **runtime events** (existing tracking) and update **task status / context** where applicable (e.g. `needs_decision` when `ask` is unanswered).
- [ ] **R7 — AuthN/AuthZ:** Stream and enqueue endpoints require the same class of credentials as execute/task mutation (e.g. `X-Execute-Token` and/or session token policy already used by `/api/agent/tasks/...`). Anonymous subscription is forbidden.
- [ ] **R8 — Backpressure and failure:** If the agent does not consume commands, define **max queue depth** and **drop/escalation** policy (documented); SSE disconnects must not corrupt task state.
- [ ] **R9 — Observability:** Emit counters/histograms (or runtime events) for: `control_commands_issued`, `control_commands_acked`, `sse_connections_active`, `sse_reconnects`, `command_queue_depth`.

## API Contract

### `GET /api/agent/tasks/{task_id}/control/stream`

**Purpose:** SSE subscription for control commands for `task_id`.

**Request**

- Path: `task_id` — existing task id string.
- Headers: Authorization per deployment (`X-Execute-Token` or equivalent); optional `Last-Event-ID` for resume (if supported in MVP, else document as follow-up).

**Response 200**

- `Content-Type: text/event-stream`
- Events as described in Requirements; heartbeat `ping` at least every 30s while idle (configurable).

**Response 404**

- Task does not exist.

**Response 401 / 403**

- Invalid or insufficient credentials.

### `POST /api/agent/tasks/{task_id}/control/commands`

**Purpose:** Enqueue a control command for fan-out to SSE subscribers and persistence.

**Request body (JSON)**

```json
{
  "type": "steer",
  "payload": { "direction": "Prefer pytest -q over verbose" },
  "issuer": "operator@example"
}
```

**Response 202**

```json
{
  "command_id": "cmd_01JQ...",
  "task_id": "task_...",
  "queued_at": "2026-03-28T12:00:00Z"
}
```

**Response 404 / 401 / 403 / 422** — standard error shapes.

### `POST /api/agent/tasks/{task_id}/control/ack`

**Purpose:** Agent/runner acknowledges or completes handling of a command.

**Request body**

```json
{
  "command_id": "cmd_01JQ...",
  "status": "applied",
  "message": "Checkpoint saved to branch codex/foo",
  "result": { "artifact": "git_sha", "value": "abc123" }
}
```

**Response 200** — echo ack record with server timestamp.

**Response 404** — task or unknown `command_id` (policy: 404 vs 409 documented).

### `GET /api/agent/tasks/{task_id}/control/commands` (optional read API)

**Purpose:** List recent commands and ack status for UI/debug (paginated). If omitted in MVP, document under Known Gaps.

## Data Model

```yaml
ControlCommand:
  command_id: string (UUID)
  task_id: string
  type: enum [checkpoint, steer, abort, ask, report, ping, error]
  payload: object
  issued_at: string (ISO 8601 UTC)
  issuer: string
  queued_at: string (optional, server)

ControlAck:
  command_id: string
  task_id: string
  status: enum [received, applied, rejected, failed]
  message: string (optional)
  result: object (optional)
  acked_at: string (ISO 8601 UTC)

RuntimeEvent extension (conceptual):
  tracking_kind: agent_control_channel
  metadata:
    command_id: string
    type: string
    latency_ms: int (optional)
```

Persistence: short-retention table or JSONL append for `ControlCommand` + `ControlAck` (implementation choice; must support audit queries for verification).

## Web (optional but recommended)

- **`/tasks/[task_id]/control`** — Live panel: connection status (SSE), last 20 commands, ack state, manual enqueue form (steer/abort/ask). If web is out of scope for first slice, mark explicit follow-up.

## CLI (operator / runner)

- No new **required** `cc` subcommand for MVP; operators use `curl` against the API. Optional later: `cc task control steer <task_id> "..."` wrapping `POST .../control/commands`.

## Files to Create/Modify (implementation phase — not part of this spec-only delivery)

- `api/app/routers/agent_control_routes.py` — SSE + POST routes (or merge into `agent_tasks_routes.py` if spec lists).
- `api/app/services/agent_control_channel_service.py` — fan-out, persistence, metrics.
- `api/app/models/agent_control.py` — Pydantic models.
- `api/scripts/local_runner.py` — SSE listener thread + command file writer.
- `api/tests/test_agent_control_channel.py` — SSE + ack + auth tests.
- `web/app/tasks/[id]/control/page.tsx` — optional UI.

Exact file list must be frozen in a follow-up task card before implementation.

## Concurrency Behavior

- **SSE:** Multiple subscribers possible (ops + automation); all receive the same fan-out; `command_id` idempotency prevents double-apply on the agent if reconnect replays.
- **Command file:** Single writer (runner thread), single reader (agent wrapper); use append + file locking or line-oriented JSONL with atomic rename if required by OS.
- **Ack ordering:** Total order per `task_id` not guaranteed across concurrent issuers; agent must handle conflicting steer by last-writer-wins or explicit revision in `payload`.

## Verification Scenarios

### Scenario 1 — Full cycle: enqueue command, receive on SSE, ack via POST

- **Setup:** Task `task_id=T1` exists with status `running`. Valid `X-Execute-Token` or auth header available. No prior control commands for `T1`.
- **Action:**
  1. `curl -sN -H "X-Execute-Token: $TOKEN" "$API/api/agent/tasks/T1/control/stream"` in background (or timeout 5s read).
  2. `curl -s -X POST "$API/api/agent/tasks/T1/control/commands" -H "Content-Type: application/json" -H "X-Execute-Token: $TOKEN" -d '{"type":"checkpoint","payload":{},"issuer":"verify"}'`
- **Expected:**
  - POST returns **202** with JSON containing `command_id` matching `^cmd_` or UUID format per implementation.
  - SSE client receives an event with `event: checkpoint` and `data:` containing the same `command_id` and `type":"checkpoint"`.
  3. `curl -s -X POST "$API/api/agent/tasks/T1/control/ack" -H "Content-Type: application/json" -H "X-Execute-Token: $TOKEN" -d '{"command_id":"<id>","status":"applied","message":"ok"}'`
  - Returns **200** with `acked_at` set; runtime events or list endpoint shows ack linked to `command_id`.
- **Edge:** POST ack with wrong `command_id` for `T1` returns **404** (or documented **409** if duplicate ack); never **500** for valid JSON shape.
- **Edge:** POST command with `type":"invalid_type"` returns **422** with field errors.

### Scenario 2 — Steer updates visible task context

- **Setup:** Task `T2` running; context field is readable via `GET /api/agent/tasks/T2`.
- **Action:** `POST .../control/commands` with `type":"steer"` and payload `{"direction":"New constraint"}`.
- **Expected:** Subsequent `GET /api/agent/tasks/T2` shows updated `context` or a nested `control.last_steer` field (exact field per implementation) containing the new direction and `command_id`.
- **Edge:** Steer on **completed** task returns **409** or **422** (documented), not silent no-op.

### Scenario 3 — Ask permission pauses / flags decision state

- **Setup:** Task `T3` running.
- **Action:** Enqueue `type":"ask"` with payload `{"question":"Approve schema migration?","options":["yes","no"]}`.
- **Expected:** Task transitions to `needs_decision` (or equivalent) **or** exposes an `awaiting_permission` flag in GET response; `GET /api/agent/monitor-issues` or task detail lists the pending question.
- **Action 2:** POST `.../control/ack` with `status":"applied"` and `result":{"answer":"yes"}`.
- **Expected:** Task returns to `running` or `completed` per workflow; ack stored.
- **Edge:** Second ack for same `command_id` returns **409** conflict.

### Scenario 4 — Auth failure and missing task

- **Setup:** Invalid token; nonexistent `task_id=T999`.
- **Action:** `curl -s -o /dev/null -w "%{http_code}" -H "X-Execute-Token: bad" "$API/api/agent/tasks/T1/control/stream"`
- **Expected:** **401** or **403**.
- **Action:** `curl -s -o /dev/null -w "%{http_code}" -H "X-Execute-Token: $TOKEN" "$API/api/agent/tasks/T999/control/stream"`
- **Expected:** **404**.

### Scenario 5 — Runner command file write (integration)

- **Setup:** Runner integration tests or staging runner with `COHERENCE_TASK_ID=T4` and writable worktree.
- **Action:** Issue `checkpoint` via API while a dry-run runner process is attached.
- **Expected:** File `.coherence/control/T4.jsonl` (or documented path) contains a new line with JSON matching the `command_id` and `type`.
- **Edge:** Disk full or permission denied: runner logs explicit error and emits `control_channel_write_failed` runtime event; task does not crash silently.

## Verification (CI / local)

```bash
python3 scripts/validate_spec_quality.py --file specs/task_cc39be1e81c4f663.md
cd api && pytest -q tests/test_agent_control_channel.py
```

## Improving the Idea, Proving It Works, and Clarifying Proof Over Time

1. **Health contract:** Define a **`control_channel_ready`** boolean on `GET /api/agent/tasks/{id}` plus **`last_control_ping_at`** so UIs and monitors can tell “SSE listener attached” vs “task running blind.”
2. **SLI metrics:** Track **command latency** (enqueue → ack) and **staleness** (no ack within N seconds for `ask`). Surface in `/api/runtime/endpoints/summary` or existing effectiveness endpoints.
3. **Version field:** Add `schema_version` on every SSE payload so clients can evolve without silent breakage; maintain a short changelog in `docs/` or spec appendix.
4. **Chaos tests:** Periodically kill SSE connection in CI and assert reconnect + idempotent replay does not duplicate side effects.
5. **Dashboard proof:** A single page (`/tasks/[id]/control`) that shows **green/red** for stream connected + **sparkline** of ack latency proves the feature to non-developers.

## Out of Scope (MVP)

- Replacing provider CLIs or parsing their proprietary transcripts.
- Guaranteed delivery stronger than “best effort + audit trail” (Kafka, etc.).
- Multi-tenant isolation beyond existing API auth (assumes one deployment’s token model).

## Risks and Assumptions

- **Risk:** SSE through proxies (Cloudflare, Traefik) may buffer or timeout; mitigate with `ping` interval and documented proxy settings.
- **Risk:** File-based IPC fails on exotic filesystems; mitigate with documented requirement for local disk worktree.
- **Assumption:** Task execution already associates a single active runner per claimed task; otherwise duplicate command files are possible.

## Known Gaps and Follow-up Tasks

- `Last-Event-ID` resume semantics for SSE (optional phase 2).
- Web UI panel and E2E Playwright tests.
- `cc task control` CLI sugar.
- Formal OpenAPI fragments for new routes once implemented.

## Failure/Retry Reflection

- **Failure mode:** Agent ignores control file → operator sees unacked commands and rising queue depth.
- **Blind spot:** Assuming CLI will voluntarily poll; may require a tiny wrapper injected by runner.
- **Next action:** Add **timeout escalation** (auto `needs_decision`) when `ask` is unacked > N minutes.

## Research Inputs

- `2026-03-28` — Internal codebase review: `api/app/routers/agent_tasks_routes.py`, `api/app/routers/agent_execute_routes.py`, `api/scripts/local_runner.py` (runner-side execution and task lifecycle).
- `2026-03-28` — MDN — [Using server-sent events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events) — SSE event format and reconnection behavior.
- `2026-03-28` — FastAPI — StreamingResponse patterns for SSE (project docs / existing streaming routes if any).

## Task Card (for implementation follow-up)

```yaml
goal: Implement SSE control channel with enqueue, stream, ack, runner jsonl bridge, and tests.
files_allowed:
  - api/app/routers/agent_control_routes.py
  - api/app/services/agent_control_channel_service.py
  - api/app/models/agent_control.py
  - api/app/main.py
  - api/scripts/local_runner.py
  - api/tests/test_agent_control_channel.py
done_when:
  - All Verification Scenarios in specs/task_cc39be1e81c4f663.md pass against local API.
  - pytest tests/test_agent_control_channel.py green.
  - Metrics or runtime events for control_commands_issued and control_commands_acked present.
commands:
  - python3 scripts/validate_spec_quality.py --file specs/task_cc39be1e81c4f663.md
  - cd api && pytest -q tests/test_agent_control_channel.py
constraints:
  - Do not weaken existing task auth; no provider-specific logic outside agent_service_executor/command_templates.
```

## Acceptance Criteria (spec approval)

- [ ] Spec links **exact** routes: `GET/POST .../control/stream`, `POST .../control/commands`, `POST .../control/ack`.
- [ ] At least one scenario covers **create → read → ack** cycle; at least one covers **error/auth**.
- [ ] Open question on proof is answered with measurable **SLIs + UI/health fields**.
- [ ] `python3 scripts/validate_spec_quality.py --file specs/task_cc39be1e81c4f663.md` passes after implementation-related sections are stable.
