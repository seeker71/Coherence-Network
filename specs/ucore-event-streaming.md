# Spec: Real-time event streaming (ucore-event-streaming)

## Purpose

Provide a single in-process pub/sub exchange so WebSocket clients (web, CLI, MCP adapters) subscribe to live activity with optional filters. Producers publish typed events with entity scope; runtime telemetry is mirrored automatically for cross-service visibility.

## Requirements

- [x] WebSocket endpoint accepts subscriptions with optional `event_types`, `entity`, `entity_id` query filters.
- [x] HTTP POST publishes events into the exchange (token-gated when `COHERENCE_EVENT_STREAM_PUBLISH_TOKEN` is set).
- [x] JSON envelope is versioned (`coherence.event_stream.v1`).
- [x] Runtime events are published after persistence (best-effort, non-blocking for core path).

## Research Inputs (Required)

- `2024-01-01` — [FastAPI WebSockets](https://fastapi.tiangolo.com/advanced/websockets/) — server-side WebSocket patterns.
- Internal: `api/app/services/openclaw_node_bridge_service.py` — queue backpressure pattern.

## Task Card (Required)

```yaml
goal: Ship cross-service WebSocket pub/sub with filterable subscriptions and publish API.
files_allowed:
  - specs/ucore-event-streaming.md
  - api/app/models/event_stream.py
  - api/app/services/event_stream_service.py
  - api/app/routers/event_stream.py
  - api/app/main.py
  - api/app/services/runtime_service.py
  - api/tests/test_event_stream.py
  - web/app/events/live/page.tsx
  - cli/lib/commands/listen.mjs
  - cli/bin/cc.mjs
done_when:
  - pytest api/tests/test_event_stream.py passes
  - WebSocket receives connected + published events
commands:
  - cd api && .venv/bin/pytest -v api/tests/test_event_stream.py
constraints:
  - Do not weaken existing tests; new tests only for new behavior.
```

## API Contract

### `WebSocket /api/events/stream`

**Query**

- `event_types`: optional comma-separated list; when set, only those types are delivered.
- `entity`: optional string; when set, must match published `entity`.
- `entity_id`: optional string; when set, must match published `entity_id`.
- `token`: optional; required to match `COHERENCE_EVENT_STREAM_TOKEN` when that env var is set.

**Server messages**

JSON lines (text frames), first message is `event_type: connected`, then `heartbeat` every 30s idle, plus published events.

### `POST /api/events/publish`

**Request**

```json
{
  "event_type": "string",
  "entity": "string",
  "entity_id": "string | null",
  "data": {}
}
```

**Headers**

- `X-Event-Stream-Token`: required when `COHERENCE_EVENT_STREAM_PUBLISH_TOKEN` is set.

**Response 201**

Envelope echo with `id` field for correlation.

## Data Model

```yaml
EventStreamPublish:
  event_type: { type: string }
  entity: { type: string, default: generic }
  entity_id: { type: string, optional: true }
  data: { type: object }
```

## Files to Create/Modify

- `api/app/models/event_stream.py` — publish payload + response models
- `api/app/services/event_stream_service.py` — pub/sub registry
- `api/app/routers/event_stream.py` — WebSocket + POST publish
- `api/app/main.py` — register router
- `api/app/services/runtime_service.py` — publish after `record_event`
- `api/tests/test_event_stream.py` — contract tests
- `web/app/events/live/page.tsx` — live viewer
- `cli/lib/commands/listen.mjs` — `--ws` WebSocket mode
- `cli/bin/cc.mjs` — help string for listen

## Acceptance Tests

- `api/tests/test_event_stream.py::test_event_stream_ws_connected`
- `api/tests/test_event_stream.py::test_event_stream_publish_delivers`
- `api/tests/test_event_stream.py::test_event_stream_filter_event_types`

## Verification

- Run `cd api && pytest -v api/tests/test_event_stream.py`.
- Manual: `websocat` or browser devtools to `ws://localhost:8000/api/events/stream`.

## Risks and Assumptions

- In-process only: horizontal scaling would need Redis/NATS (not in this slice).
- Publish open when publish token unset — intended for local dev only.

## Known Gaps and Follow-up Tasks

- Federate stream across API replicas.
- Optional SSE mirror for clients without WebSocket.
