# Spec 156: OpenClaw bidirectional messaging - skill checks inbox on session start

## Purpose

Define a strict, testable contract for OpenClaw bidirectional messaging where each OpenClaw session starts by checking the Coherence inbox (`cc inbox`) before other work. This ensures messages sent by any node (`cc msg` or `cc cmd`) are visible in the next OpenClaw session and creates a stable baseline for future push-based delivery.

## Requirements

- [ ] OpenClaw skill documentation defines a mandatory session-start order with `cc inbox` as the first command.
- [ ] Messages sent through existing federation messaging paths are retrievable by the recipient on next session start.
- [ ] `cc inbox` behavior is deterministic for unread vs. read messages and does not silently fail.
- [ ] Error responses for malformed message payloads and invalid query bounds are explicit and machine-parseable.
- [ ] Phase 2 (webhook push) and Phase 3 (WebSocket bridge) are documented as planned follow-up phases, not included in this implementation scope.

## Research Inputs (Required)

- `2025-01-01` - [Agent Skills format guidance](https://agentskills.io) - establishes durable skill instruction patterns and session protocol expectations.
- `2026-03-26` - Internal repo reference: `specs/149-openclaw-inbox-session-protocol.md` - baseline behavior and CLI/API mapping for inbox polling.
- `2026-03-26` - Internal repo reference: `cli/lib/commands/nodes.mjs` (via spec references) - current command behavior for message read/send semantics.

## Task Card (Required)

```yaml
goal: Define a precise phased spec for OpenClaw bidirectional messaging with inbox-first session start and verifiable behavior.
files_allowed:
  - specs/156-openclaw-bidirectional-messaging.md
done_when:
  - Spec includes concrete verification criteria, API/UI behavior expectations, edge cases, and at least 3 test scenarios.
  - Spec quality validation command succeeds.
commands:
  - python3 scripts/validate_spec_quality.py --base origin/main --head HEAD
constraints:
  - Scope implementation requirements to Phase 1 only; treat Phase 2 and Phase 3 as documented follow-up.
  - Do not require new endpoints in this phase when existing federation message APIs satisfy behavior.
```

## API Contract (Phase 1)

### `POST /api/federation/nodes/{node_id}/messages`

Used by node send flows (`cc msg`, `cc cmd`) to persist a message/event for recipient pickup.

**Request**
- Path: `node_id` (sender node id)
- Body:
  - `from_node`: string (required)
  - `to_node`: string or `null` (required for directed message, `null` for broadcast)
  - `type`: string (required; examples: `text`, `command`)
  - `text`: string (required, non-empty)
  - `payload`: object (optional, defaults `{}`)

**Response 201**
```json
{
  "id": "msg_abc123",
  "from_node": "node_sender",
  "to_node": "node_receiver",
  "type": "text",
  "text": "hello",
  "payload": {},
  "timestamp": "2026-03-26T12:00:00Z"
}
```

**Response 422**
```json
{
  "detail": [
    {
      "loc": ["body", "from_node"],
      "msg": "Field required",
      "type": "missing"
    }
  ]
}
```

### `GET /api/federation/nodes/{node_id}/messages`

Used by inbox read flow (`cc inbox`) at session start.

**Request**
- Path: `node_id` (recipient)
- Query:
  - `unread_only`: boolean (default `true`)
  - `limit`: integer (1-200)
  - `since`: ISO8601 timestamp (optional)

**Response 200**
```json
{
  "node_id": "node_receiver",
  "messages": [
    {
      "id": "msg_abc123",
      "from_node": "node_sender",
      "to_node": "node_receiver",
      "type": "text",
      "text": "hello",
      "payload": {},
      "timestamp": "2026-03-26T12:00:00Z",
      "read": false
    }
  ],
  "count": 1
}
```

**Response 422 (invalid limit)**
```json
{
  "detail": [
    {
      "loc": ["query", "limit"],
      "msg": "Input should be less than or equal to 200",
      "type": "less_than_equal"
    }
  ]
}
```

## Data Model (Phase 1)

```yaml
FederationMessage:
  properties:
    id: { type: string }
    from_node: { type: string }
    to_node: { type: [string, "null"] }
    type: { type: string }
    text: { type: string }
    payload: { type: object }
    timestamp: { type: string, format: date-time }
    read: { type: boolean }
```

## Files to Create/Modify

- `specs/156-openclaw-bidirectional-messaging.md` - phased specification and verification contract

## Acceptance Tests

- `api/tests/test_openclaw_inbox_session_protocol.py` (existing baseline coverage for inbox protocol and API behavior)
- Add/extend implementation tests in Phase 1 delivery task to include command-type message handling if absent

## Concurrency Behavior

- **Read operations**: Inbox reads are safe under concurrent polling; duplicate retrievals are acceptable only if read state has not yet been committed.
- **Write operations**: Message writes are append-only events; ordering is by persisted timestamp.
- **Delivery model**: At-least-once visibility across session boundaries; this phase does not guarantee push immediacy.

## Verification

Phase 1 is accepted only when all criteria below are true:

1. Skill/session protocol explicitly states session start order where command 1 is `cc inbox`.
2. A directed message sent from node B to node A appears in node A inbox response in the next session check flow.
3. Command payload messages (`type="command"` or equivalent) are visible in inbox and preserved in `payload`.
4. Malformed message POST returns 422 with field-level validation details.
5. Invalid inbox query bounds (for example, `limit=999`) return 422 with deterministic error shape.
6. Read/unread behavior is documented and verified: `unread_only=true` excludes already-read messages after a successful read-mark cycle.

Executable validation command (spec quality gate):

```bash
python3 scripts/validate_spec_quality.py --base origin/main --head HEAD
```

Manual/API verification scenarios:

### Scenario 1 - Session-start protocol order

- **Setup:** OpenClaw skill installed with Coherence skill content.
- **Action:** Start a new OpenClaw session.
- **Expected behavior:** Operator sees/checks `cc inbox` first, then proceeds to status/work commands; documentation and automation scripts reflect this order.
- **Edge case:** If inbox call fails (network/API unavailable), session should surface a visible error and require explicit continue/skip decision, not silent continuation.

### Scenario 2 - Directed message delivered on next session

- **Setup:** Node B sends `cc msg node_a "sync request"` before node A starts a new session.
- **Action:** Node A begins session and runs `cc inbox`.
- **Expected API/UI behavior:** Inbox output includes message text `sync request`, sender `node_b`, and timestamp; underlying API response has `count >= 1`.
- **Edge case:** If node A has no messages, inbox returns count `0` with empty list and a successful exit status.

### Scenario 3 - Command message visibility and handling

- **Setup:** Node B sends `cc cmd node_a "checkpoint"` (or equivalent command message with payload).
- **Action:** Node A runs `cc inbox` at session start.
- **Expected API/UI behavior:** Inbox clearly identifies message as command type and shows command body; consumer can act deterministically.
- **Edge case:** Unknown command type is still displayed as a message and does not crash inbox rendering.

### Scenario 4 - Validation and bounds errors

- **Setup:** Use malformed POST body and out-of-range GET query.
- **Action:** Submit payload missing `from_node`; request inbox with `limit=999`.
- **Expected API/UI behavior:** Both calls return 422 with parseable `detail` array; CLI surfaces the error text and non-zero exit code.
- **Edge case:** Repeated invalid requests should not create partial messages or mutate read state.

## Out of Scope

- Phase 2 implementation: OpenClaw webhook push reception through OpenClaw gateway API.
- Phase 3 implementation: real-time WebSocket bridge between CC federation and OpenClaw gateway.
- Guaranteed exactly-once delivery semantics or cross-region ordering guarantees.

## Risks and Assumptions

- Assumes current federation message endpoints remain available and stable for polling-based delivery.
- Assumes OpenClaw skill execution environment has access to `cc` CLI and valid node identity resolution.
- Risk: operators may bypass session protocol manually; mitigation is explicit skill contract and test/assertion coverage.
- Risk: read-state race conditions under highly concurrent polling could create temporary duplicate visibility; acceptable for Phase 1 at-least-once model.

## Known Gaps and Follow-up Tasks

- Phase 2 follow-up: define OpenClaw gateway webhook authentication, retry policy, idempotency key format, and failure dead-letter behavior.
- Phase 3 follow-up: define WebSocket event envelope, backpressure strategy, reconnect protocol, and federation-to-gateway authorization model.
- Add observability follow-up: metrics for inbox-check success rate, command-processing latency, and undelivered-message age distribution.

## Failure/Retry Reflection

- Failure mode: inbox check timeout at session start.
- Blind spot: implicit assumption of always-on API connectivity.
- Next action: fallback to bounded retry with explicit operator-visible warning and retry-after hint.

## Decision Gates (if any)

- Confirm whether command message type should be normalized as `command` across CLI/API in Phase 1 implementation.
- Confirm whether session should hard-stop on inbox failure or allow explicit manual override.
