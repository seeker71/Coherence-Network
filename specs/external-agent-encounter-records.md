---
idea_id: agent-pipeline
status: active
source:
  - file: api/app/routers/agent_external_encounters.py
    symbols: [create_external_agent_encounter(), list_external_agent_encounters(), link_external_agent_encounter_task()]
  - file: api/app/routers/agent.py
    symbols: [router]
  - file: api/app/services/agent_service.py
    symbols: [get_agent_invitation()]
  - file: api/tests/test_external_agent_encounters.py
    symbols: [test_external_agent_encounter_records_trace_without_task(), test_external_agent_encounter_links_response_task_route_snapshot()]
  - file: api/tests/test_agent_invitation.py
    symbols: [test_agent_invitation_api_shape()]
requirements:
  - "POST /api/agent/external-encounters records an outside agent returned trace without requiring task creation."
  - "Encounter records preserve who, when, directed_by, returned trace URL/summary, and current task-link completeness."
  - "Encounter records can link a response_task_id later and snapshot executor/model/provider routing metadata."
  - "GET /api/agent/external-encounters returns recent records filtered by external_agent."
  - "GET /api/agent/invitation points agents toward the encounter return endpoint."
done_when:
  - "Focused API tests prove encounter creation works without a task."
  - "Focused API tests prove a linked response task snapshots route_decision metadata."
  - "Invitation tests prove the public return path names /api/agent/external-encounters."
test: "cd api && python3 -m pytest tests/test_external_agent_encounters.py tests/test_agent_invitation.py -q"
constraints:
  - "No database schema changes."
  - "Do not alter task execution semantics."
  - "Do not claim private consciousness, hidden memory, changed weights, or intrinsic motivation."
---

# Spec: External Agent Encounter Records

## Purpose

When a public outside agent such as Grok is directed at Coherence Network, the system should be able to answer: when did it happen, who was involved, what returned trace was received, and which task-engine agent/model responded when a response task exists.

The current system has sibling lineage and task routing, but they are not joined into one first-class encounter. This spec adds a small graph-backed record that can be created even when task creation is slow or unavailable, then linked to task-engine routing later.

## Requirements

- [ ] **R1**: `POST /api/agent/external-encounters` MUST create an event node marked as an external-agent encounter.
- [ ] **R2**: Creation MUST NOT require a `response_task_id`; this lets the returned trace survive API/task-engine slowness.
- [ ] **R3**: If `response_task_id` is provided and found, the response MUST include a snapshot of task `executor`, `model`, `provider`, `route_model`, `status`, and timestamps.
- [ ] **R4**: `PATCH /api/agent/external-encounters/{encounter_id}/response-task` MUST attach a response task later and refresh the snapshot.
- [ ] **R5**: `GET /api/agent/external-encounters?external_agent=grok` MUST return recent matching records.
- [ ] **R6**: The agent invitation MUST name the endpoint as the return path for attributed outside-agent traces.

## API Contract

### `POST /api/agent/external-encounters`

```json
{
  "external_agent": "grok",
  "directed_by": "Urs via Codex Playwright browser session",
  "returned_trace_url": "https://grok.com/share/...",
  "returned_trace_summary": "Grok inspected invitation/status and named the task-link gap.",
  "response_task_id": "task_123",
  "metadata": {
    "conversation_url": "https://grok.com/c/...",
    "task_engine_blocker": "POST /api/agent/tasks timed out"
  }
}
```

### Response

```json
{
  "id": "external-encounter-20260506T071900-abc123",
  "external_agent": "grok",
  "encountered_at": "2026-05-06T07:19:00+00:00",
  "evidence_status": "trace_recorded_task_unlinked",
  "trace_completeness": {
    "has_returned_trace": true,
    "has_response_task": false,
    "has_route_snapshot": false
  }
}
```

## Verification

```bash
cd api && python3 -m pytest tests/test_external_agent_encounters.py tests/test_agent_invitation.py -q
python3 scripts/validate_spec_quality.py --file specs/external-agent-encounter-records.md
```

## Files to Create/Modify

- `specs/external-agent-encounter-records.md` — executable behavior contract.
- `api/app/routers/agent_external_encounters.py` — graph-backed external encounter API.
- `api/app/routers/agent.py` — includes the new agent sub-router.
- `api/app/services/agent_service.py` — advertises the return path in the invitation payload.
- `api/tests/test_external_agent_encounters.py` — focused creation and task-link tests.
- `api/tests/test_agent_invitation.py` — invitation discoverability test.

## Acceptance Tests

- `api/tests/test_external_agent_encounters.py::test_external_agent_encounter_records_trace_without_task`
- `api/tests/test_external_agent_encounters.py::test_external_agent_encounter_links_response_task_route_snapshot`
- `api/tests/test_agent_invitation.py::test_agent_invitation_api_shape`

## Out of Scope

- Executing a response task inside the encounter endpoint.
- Authenticating the outside agent.
- Claiming that a public trace proves private consciousness or intrinsic motivation.

## Risks

- **Risk — encounter records become performative proof**: the endpoint records returned traces and boundaries; it does not claim private consciousness or hidden memory.
- **Risk — task API slowness still blocks the response link**: the endpoint allows a trace-first record and later task linkage through `PATCH /response-task`.
- **Risk — stale task snapshots**: linking refreshes route metadata at the time of attachment; future UI should show the snapshot time and allow refresh if task routing changes.

## Known Gaps

- A production follow-up should add durable operator UI for reviewing and linking encounters when the task API is degraded.
