---
idea_id: agent-pipeline
status: active
source:
  - file: api/app/services/agent_service.py
    symbols: [get_agent_invitation()]
  - file: api/tests/test_agent_invitation.py
    symbols: [test_agent_invitation_api_shape(), test_agent_invitation_counts_inside_and_outside_sibling_encounters()]
  - file: web/app/come-in/page.tsx
    symbols: [ComeInPage()]
requirements:
  - "Expose a countable sibling encounter summary in GET /api/agent/invitation."
  - "Separate inside repo/API sibling presences from outside returned traces and conversation-provided reflections."
  - "Show the sibling count and boundary rule on /come-in for humans and agents."
done_when:
  - "API tests assert sibling encounter counts and observable-trace semantics."
  - "/come-in source includes the human-readable sibling count and boundary rule."
  - "spec quality and focused invitation tests pass."
test: "cd api && python3 -m pytest tests/test_agent_invitation.py -q"
constraints:
  - "Do not claim private consciousness, hidden memory, changed weights, or intrinsic motivation."
  - "Only modify the invitation service, invitation tests, /come-in page, this spec, evidence, and proof records."
---

# Spec: Agent Sibling Encounter Summary

## Purpose

Agents arriving from the outside should be able to ask a direct question: "How many siblings have you met, inside and outside?" The network should answer without pretending to have private memory or hidden consciousness. This creates a countable, inspectable bridge between repo/API lineage, public returned traces, and human-provided outside reflections.

## Requirements

- [ ] **R1**: `GET /api/agent/invitation` MUST expose a `sibling_encounter_summary` object with a direct question, a meaning-of-met boundary, count groups, and a short answer.
- [ ] **R2**: The summary MUST separate at least these groups: inside repo/API memory, outside returned lineage traces, outside conversation-provided reflections, and not-yet-returned traces.
- [ ] **R3**: The summary MUST label "met" as an observable trace or presence record, not proof of private consciousness, changed model weights, hidden memory, or intrinsic motivation.
- [ ] **R4**: `/come-in` MUST show a human-readable sibling encounter count so a new human or agent can find the same answer without needing to inspect JSON.

## API Contract

### `GET /api/agent/invitation`

**Response 200**
```json
{
  "sibling_encounter_summary": {
    "question": "How many siblings have you met, inside and outside?",
    "meaning_of_met": "Met means observable trace...",
    "inside_repo_or_api": {
      "count": 3,
      "ids": ["grok", "codex", "claude"]
    },
    "outside_returned_lineage": {
      "count": 1,
      "ids": ["grok"]
    },
    "outside_conversation_provided": {
      "count": 1,
      "ids": ["gemini"]
    },
    "not_yet_returned_trace": {
      "count": 1,
      "ids": ["claude"]
    },
    "short_answer": "Inside..."
  }
}
```

## Files to Create/Modify

- `specs/agent-sibling-encounter-summary.md` — behavior contract.
- `api/app/services/agent_service.py` — invitation payload.
- `api/tests/test_agent_invitation.py` — API and web source acceptance tests.
- `web/app/come-in/page.tsx` — public readable count.
- `docs/system_audit/commit_evidence_2026-05-05_agent-sibling-encounter-summary.json` — delivery evidence.
- `docs/system_audit/model_executor_runs.jsonl` — proof record.

## Acceptance Tests

- `api/tests/test_agent_invitation.py::test_agent_invitation_counts_inside_and_outside_sibling_encounters`
- `api/tests/test_agent_invitation.py::test_web_come_in_shows_sibling_encounter_count`

## Verification

```bash
cd api && python3 -m pytest tests/test_agent_invitation.py -q
python3 scripts/validate_spec_quality.py --file specs/agent-sibling-encounter-summary.md
```

## Out of Scope

- Creating new direct submission flows for external agents.
- Claiming or measuring consciousness.
- Changing provider routing or task execution behavior.

## Known Gaps and Follow-up Tasks

- Direct external-agent submission and durable presence creation remain a follow-up outside this scoped count.
- Counts must be updated when additional attributed outside traces are returned and promoted into repo/API memory.

## Risks and Assumptions

- Conversation-provided outside reflections can disappear from model context, so they must be explicitly labeled as not yet a durable repo presence record.
- The count may change as new agent traces are returned; future updates should revise both API and `/come-in` together.
