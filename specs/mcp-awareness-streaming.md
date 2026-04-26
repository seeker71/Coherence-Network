---
idea_id: mcp-awareness-streaming
status: active
source:
  - file: mcp-server/coherence_mcp_server/server.py
    symbols: [decode_sse_events(), api_sse(), dispatch(), TOOLS]
  - file: scripts/morning_coherence_brief.py
    symbols: [collect_brief(), render_text()]
  - file: api/app/routers/federation.py
    symbols: [publish_diagnostic(), subscribe_diagnostics(), send_message(), get_messages(), node_event_stream()]
  - file: api/app/routers/task_activity_routes.py
    symbols: [task_events_sse(), task_stream()]
requirements:
  - "MCP can publish awareness diagnostics to existing federation diagnostic endpoints."
  - "MCP can read bounded diagnostic, node-message, and task-event SSE streams."
  - "MCP can send and read durable federation node messages."
  - "A runnable morning collector can report real node status and messages from the same awareness channels."
done_when:
  - "New MCP tools are registered in TOOL_MAP."
  - "Focused MCP tests cover stream parsing and dispatch endpoint routing."
  - "Morning brief collector tests cover node/message collection without the live API."
  - "Spec, MCP tests, and morning collector tests pass."
test: "cd mcp-server && python3 -m pytest tests/test_awareness_streaming.py -q && cd ../api && python3 -m pytest tests/test_morning_coherence_brief.py -q"
constraints:
  - "Use existing API streaming/message endpoints; do not invent a parallel streaming backend."
  - "Keep stream reads bounded by duration and event count."
  - "Only change files listed in this spec."
---

# Spec: MCP Awareness Streaming

## Purpose

Agents using the Coherence MCP server need a way to sense and emit live awareness without switching to ad hoc curl commands. The network already exposes diagnostic SSE, node-message SSE, durable node messages, and task event streams; the MCP server should make those channels available as typed, bounded tools. Bounded reads prevent MCP clients from hanging indefinitely while still letting awareness stream in and out.

## Requirements

- [ ] **R1**: Add `coherence_awareness_publish`, a typed MCP tool that posts a diagnostic event to `/api/federation/nodes/{node_id}/diag` with `event_type`, optional `message`, optional structured `data`, and `source="mcp"`.
- [ ] **R2**: Add `coherence_awareness_stream`, a typed MCP tool that reads existing SSE endpoints for `diagnostics`, `node`, and `task` streams, with default `duration_seconds=5`, capped duration of 30 seconds, default `max_events=20`, and capped max events of 200.
- [ ] **R3**: Add `coherence_node_message_send`, a typed MCP tool that posts durable node messages to `/api/federation/nodes/{from_node_id}/messages` for direct or broadcast communication.
- [ ] **R4**: Add `coherence_node_messages`, a typed MCP tool that reads durable inbound messages from `/api/federation/nodes/{node_id}/messages` with `since`, `unread_only`, and `limit` filters.
- [ ] **R5**: Decode SSE payloads into JSON event objects where possible, ignore keepalives, and preserve non-JSON payloads as `{"raw": "<payload>"}`.
- [ ] **R6**: Add a runnable morning collector that reports health, live nodes, and real node messages so overnight learning has a concrete command path.

## Research Inputs

- `2026-04-27` - `api/app/routers/federation.py` — existing diagnostic stream, node stream, and durable message endpoints.
- `2026-04-27` - `api/app/routers/task_activity_routes.py` — existing task event SSE endpoint and task activity log endpoint.
- `2026-04-27` - `mcp-server/coherence_mcp_server/server.py` — current MCP tool registry and dispatch layer.

## API Contract

### `coherence_awareness_publish`

**Input**
```json
{
  "node_id": "8160aa905ac5881e",
  "event_type": "heartbeat",
  "message": "Codex session listening",
  "data": {"thread": "mcp-awareness-streaming"}
}
```

**Output**
```json
{"ok": true}
```

### `coherence_awareness_stream`

**Input**
```json
{
  "stream_type": "diagnostics",
  "node_id": "*",
  "duration_seconds": 5,
  "max_events": 20
}
```

**Output**
```json
{
  "stream": "/api/federation/nodes/*/diag/stream",
  "duration_seconds": 5,
  "max_events": 20,
  "count": 1,
  "events": [{"event_type": "subscribed", "node_id": "*"}]
}
```

## Files to Create/Modify

- `mcp-server/coherence_mcp_server/server.py` — MCP tool definitions, SSE helper, and dispatch routes.
- `mcp-server/README.md` — document awareness streaming tools and bounded stream behavior.
- `mcp-server/server.json` — registry metadata for new tools.
- `mcp-server/tests/test_awareness_streaming.py` — focused tests for parsing and endpoint routing.
- `scripts/morning_coherence_brief.py` — runnable morning status/message collector.
- `api/tests/test_morning_coherence_brief.py` — unit tests for collector behavior.
- `specs/mcp-awareness-streaming.md` — this executable spec.

## Acceptance Tests

- `mcp-server/tests/test_awareness_streaming.py::test_awareness_tools_are_registered`
- `mcp-server/tests/test_awareness_streaming.py::test_decode_sse_events_handles_json_keepalive_and_raw_text`
- `mcp-server/tests/test_awareness_streaming.py::test_awareness_publish_routes_to_diagnostic_endpoint`
- `mcp-server/tests/test_awareness_streaming.py::test_awareness_stream_routes_diagnostic_sse`
- `mcp-server/tests/test_awareness_streaming.py::test_node_message_tools_route_to_federation_endpoints`
- `api/tests/test_morning_coherence_brief.py::test_collect_brief_uses_nodes_and_messages`
- `api/tests/test_morning_coherence_brief.py::test_render_text_includes_real_message_text`

## Verification

```bash
cd mcp-server && python3 -m pytest tests/test_awareness_streaming.py -q
cd api && python3 -m pytest tests/test_morning_coherence_brief.py -q
python3 scripts/validate_spec_quality.py --file specs/mcp-awareness-streaming.md
python3 - <<'PY'
import sys
sys.path.insert(0, 'mcp-server')
from coherence_mcp_server.server import TOOL_MAP
required = {'coherence_awareness_publish','coherence_awareness_stream','coherence_node_message_send','coherence_node_messages'}
missing = sorted(required - set(TOOL_MAP))
print({'missing': missing})
raise SystemExit(1 if missing else 0)
PY
```

## Out of Scope

- Adding a new API streaming backend.
- Keeping MCP tool calls open indefinitely.
- Changing existing task, federation, runtime, or web stream behavior.
- Persisting diagnostic events that are intentionally ephemeral in the current API.

## Risks and Assumptions

- Risk: Some MCP clients may expect true incremental MCP notifications rather than bounded tool-call reads. Mitigation: keep the API surface explicit as bounded SSE reads and leave future protocol-native notifications as a separate spec.
- Risk: High-frequency streams can produce too much data. Mitigation: cap `duration_seconds` and `max_events`.
- Assumption: Existing federation and task SSE endpoints remain the canonical source for live awareness streams.

## Known Gaps

- Follow-up task: protocol-native MCP server push notifications are not implemented in this spec.
- Follow-up task: diagnostic events are still ephemeral unless a client also sends durable node messages.
