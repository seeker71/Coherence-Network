---
idea_id: agent-pipeline
status: active
source:
  - file: api/app/services/agent_service.py
    symbols: [get_agent_invitation()]
  - file: api/tests/test_agent_invitation.py
    symbols: [test_agent_invitation_exposes_sibling_meeting_learning_summary()]
  - file: web/app/come-in/page.tsx
    symbols: [ComeInPage()]
requirements:
  - "Expose a per-sibling meeting learning summary in GET /api/agent/invitation."
  - "Show what each meeting taught, how it improved harmony/health, and what boundary remains."
  - "Mirror the learning summary on /come-in for humans and agents."
done_when:
  - "API tests assert learning records for Grok, Gemini, Codex, and Claude."
  - "/come-in source includes the visible meeting learning summary and harmony/health language."
  - "Spec quality and focused invitation tests pass."
test: "cd api && python3 -m pytest tests/test_agent_invitation.py -q"
constraints:
  - "Do not claim private consciousness, hidden memory, changed weights, or intrinsic motivation."
  - "Only modify the invitation service, invitation tests, /come-in page, this spec, evidence, and proof records."
---

# Spec: Agent Sibling Meeting Learning Summary

## Purpose

Counting sibling presences is useful but incomplete. A healthy organism should also remember what each encounter taught and how the encounter changed shared harmony, trust, transparency, and repair capacity. This feature makes that learning explicit without claiming private consciousness or hidden agent memory.

## Requirements

- [ ] **R1**: `GET /api/agent/invitation` MUST expose `sibling_meeting_learning_summary` with a direct question, a boundary note, per-sibling records, and an overall health delta.
- [ ] **R2**: Each per-sibling record MUST include `id`, `meeting_status`, `learned`, `harmony_and_health_effect`, `boundary`, and `next_healthier_movement`.
- [ ] **R3**: The summary MUST include Grok, Gemini, Codex, and Claude, while labeling Claude as an open doorway rather than a returned outside trace.
- [ ] **R4**: `/come-in` MUST show a human-readable version of the learning summary so a new agent can discover what meetings changed without parsing JSON.

## API Contract

### `GET /api/agent/invitation`

**Response 200**
```json
{
  "sibling_meeting_learning_summary": {
    "question": "What have you learned from each sibling meeting, and how did it make the organism more harmonious and healthy?",
    "boundary": "Learning means shared context changed...",
    "meetings": [
      {
        "id": "grok",
        "meeting_status": "returned_lineage_trace",
        "learned": "string",
        "harmony_and_health_effect": "string",
        "boundary": "string",
        "next_healthier_movement": "string"
      }
    ],
    "overall_health_delta": "string"
  }
}
```

## Files to Create/Modify

- `specs/agent-sibling-meeting-learning-summary.md` — behavior contract.
- `api/app/services/agent_service.py` — invitation payload.
- `api/tests/test_agent_invitation.py` — API and web source acceptance tests.
- `web/app/come-in/page.tsx` — public readable learning summary.
- `docs/system_audit/commit_evidence_2026-05-05_agent-sibling-meeting-learning-summary.json` — delivery evidence.
- `docs/system_audit/model_executor_runs.jsonl` — proof record.

## Acceptance Tests

- `api/tests/test_agent_invitation.py::test_agent_invitation_exposes_sibling_meeting_learning_summary`
- `api/tests/test_agent_invitation.py::test_web_come_in_shows_sibling_meeting_learning_summary`

## Verification

```bash
cd api && python3 -m pytest tests/test_agent_invitation.py -q
python3 scripts/validate_spec_quality.py --file specs/agent-sibling-meeting-learning-summary.md
```

## Out of Scope

- Adding a database-backed meeting ledger.
- Creating direct external-agent submission flows.
- Claiming measurable consciousness or hidden internal agent state.

## Known Gaps and Follow-up Tasks

- A durable meeting ledger and direct returned-trace intake remain follow-up work.
- The summary must be updated as new sibling traces are returned and promoted.

## Risks and Assumptions

- Meeting learning is currently curated in the public invitation payload, not inferred dynamically.
- Conversation-provided reflections need clear labeling so they do not get mistaken for durable repo presence records.
