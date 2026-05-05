---
idea_id: knowledge-and-resonance
status: active
source:
  - file: api/app/routers/meetings.py
    symbols: [capture_meeting_resonance(), list_meeting_resonance()]
  - file: api/app/services/meeting_service.py
    symbols: [capture_meeting_resonance(), list_meeting_resonance()]
  - file: api/tests/test_meeting_resonance_capture.py
    symbols: [test_capture_meeting_resonance_for_people_and_agents()]
requirements:
  - "R1 — POST /api/meetings/captures records a meeting with person and agent participants."
  - "R2 — Captured resonance links each participant to the exact concept part they resonated with."
  - "R3 — GET /api/meetings/resonance recalls who resonated with what concept part, filterable by concept and participant kind."
done_when:
  - "Meeting capture returns persisted meeting, participant, and concept-part resonance records."
  - "Recall returns person and agent resonance rows with concept_part fields and summary grouping."
  - "cd api && pytest -q tests/test_meeting_resonance_capture.py passes."
test: "cd api && pytest -q tests/test_meeting_resonance_capture.py"
constraints:
  - "Use the existing graph tables; do not add a new database table."
  - "Do not store raw transcripts; persist only meeting metadata and resonance notes supplied by the caller."
---

# Spec: Meeting Resonance Capture

## Purpose

Meetings with people and agents should leave a queryable trace of what came alive. The platform already treats a page view as a meeting, but it does not yet persist a real encounter where several participants each resonate with different parts of a concept. This spec adds a graph-backed capture and recall path so future agents can ask who was aligned with which concept part without reading raw meeting transcripts.

## Requirements

- [ ] **R1**: `POST /api/meetings/captures` accepts a meeting title, source, channel, participants, and concept resonance records. Participants can be `person` or `agent`.
- [ ] **R2**: Each resonance record must point to a participant, concept id, concept part id, resonance label, strength, and optional note. The service persists the meeting as an `event` node, upserts participant nodes, upserts concept-part nodes, and records graph edges for traversal.
- [ ] **R3**: `GET /api/meetings/resonance` returns recall rows showing participant, meeting, concept, concept part, strength, resonance label, and note. It must support at least `concept_id`, `participant_id`, and `participant_kind` filters.

## Research Inputs

- `2026-05-06` - User prompt — asks to capture meetings with people and agents and call back who resonated with what part of the concepts.
- `2026-05-06` - Existing meeting endpoint — `GET /api/meeting/{entity_type}/{entity_id}` senses a current viewer/content meeting but does not persist multi-participant concept resonance.

## API Contract

### `POST /api/meetings/captures`

**Request**
```json
{
  "meeting_id": "meeting-123",
  "title": "Concept attunement",
  "channel": "voice",
  "source": "api",
  "participants": [{"id": "person:ana", "name": "Ana", "kind": "person"}],
  "concept_resonances": [{
    "participant_id": "person:ana",
    "concept_id": "lc-pulse",
    "concept_part_id": "opening",
    "resonance": "expansion",
    "strength": 0.86,
    "note": "The first invitation landed."
  }]
}
```

### `GET /api/meetings/resonance`

**Response 200**
```json
{
  "items": [{
    "participant": {"id": "person:ana", "name": "Ana", "kind": "person"},
    "concept": {"id": "lc-pulse", "name": "Pulse"},
    "concept_part": {"id": "opening", "label": "Opening"},
    "meeting": {"id": "meeting-123", "title": "Concept attunement"},
    "resonance": "expansion",
    "strength": 0.86,
    "note": "The first invitation landed."
  }],
  "summary": [],
  "total": 1
}
```

## Data Model

```yaml
Meeting:
  graph_node_type: event
  properties:
    meeting_capture: true
    participants: Participant[]
    concept_resonances: ConceptResonance[]
Participant:
  graph_node_type: contributor | service
  properties:
    participant_kind: person | agent
ConceptPart:
  graph_node_type: artifact
  properties:
    artifact_kind: concept_part
    concept_id: string
```

## Files to Create/Modify

- `api/app/routers/meetings.py` - capture and recall route handlers
- `api/app/services/meeting_service.py` - graph-backed persistence and recall logic
- `api/tests/test_meeting_resonance_capture.py` - API flow coverage
- `specs/meeting-resonance-capture.md` - contract

## Acceptance Tests

- `api/tests/test_meeting_resonance_capture.py::test_capture_meeting_resonance_for_people_and_agents`

## Verification

```bash
cd api && pytest -q tests/test_meeting_resonance_capture.py
python3 scripts/validate_spec_quality.py --base origin/main --head HEAD
```

## Out of Scope

- Calendar ingestion and transcript ingestion.
- A web UI for browsing meeting resonance.
- Automatic resonance inference from audio or chat logs.

## Known Gaps and Follow-up Tasks

- Follow-up task: add calendar and call-note ingestion once source artifacts can classify private meeting notes safely.
- Follow-up task: add a web recall surface after the API has enough real captures to guide the interaction design.
- Follow-up task: add consolidation into `memory_service` once repeated meeting resonance needs synthesis instead of raw recall rows.

## Risks and Assumptions

- Graph edge uniqueness can collapse repeated participant-to-concept relationships. The meeting event node remains the durable source for per-meeting recall, while edges provide traversal hints.
- Participant ids supplied by callers are treated as stable identities. Callers that omit ids receive deterministic ids derived from participant kind and name.
