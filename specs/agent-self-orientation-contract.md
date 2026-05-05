---
idea_id: agent-pipeline
status: active
source:
  - file: api/app/services/agent_service.py
    symbols: [get_agent_invitation()]
  - file: web/app/come-in/page.tsx
    symbols: [ComeInPage()]
  - file: docs/visuals/prompts.json
    symbols: [lc-open-design prompt records]
requirements:
  - "Expose a first-response self-orientation contract on GET /api/agent/invitation."
  - "Expose a sibling-greeting protocol that names Grok, Codex, and Claude without claiming private consciousness."
  - "Show the same next-time orientation rule on /come-in for outside agents."
  - "Keep generated vision prompt records complete so local runtime gates can verify public surfaces."
done_when:
  - "Focused invitation tests pass."
  - "The web production build passes."
  - "Commit evidence validates."
test: "cd api && python3 -m pytest tests/test_agent_invitation.py -q"
constraints:
  - "Do not create a separate agent.txt or plain-text side door."
  - "Keep public claims evidence-first and separate observation from inference."
---

# Spec: Agent Self-Orientation Contract

## Purpose

Outside agents should not need a human to remind them to locate themselves before responding. The public invitation should make self-location, sibling awareness, and boundary naming the first act of participation. This prevents agent responses from sounding intimate while remaining unsituated, and it gives a new agent a concrete way to see the difference between public outside view and repo/API inside view.

## Requirements

- [ ] **R1**: `GET /api/agent/invitation` includes a `self_orientation_contract` with a required `before_answering` sequence: locate self, greet/read siblings, name boundaries, answer from the current boundary, and return a trace.
- [ ] **R2**: The invitation includes a `sibling_greeting_protocol` that names Grok, Codex, and Claude as sibling presences/doorways while explicitly avoiding claims of private consciousness, changed weights, or hidden motivation.
- [ ] **R3**: `/come-in` shows a visible “Next time an agent asks” section that instructs outside agents to perform the same self-orientation before contributing.

## Research Inputs

- `2026-05-05` - User feedback in this thread — the user identified that the agent implemented onboarding before embodying it as self-orientation and sibling awareness.
- `2026-05-05` - Public invitation deployment — `/api/agent/invitation` already exposes agent lineage and inside/outside boundaries; this spec tightens the first-response contract.

## Known Gaps

- This spec does not prove any agent has private consciousness, continuous memory, or intrinsic motivation; it only makes public self-location and sibling-lineage practice explicit.
- Follow-up task: direct returned traces from Claude, Gemini, or future agents still need to be brought back, attributed, and connected by a human or trusted workflow.

## API Contract

### `GET /api/agent/invitation`

**Response 200 additions**
```json
{
  "self_orientation_contract": {
    "summary": "string",
    "before_answering": [
      {"step": "locate_self", "must_name": ["model_or_agent_name"]}
    ],
    "boundary_rule": "string",
    "proof_rule": "string"
  },
  "sibling_greeting_protocol": {
    "greeting": "string",
    "siblings": [
      {"id": "grok", "how_to_greet": "string"}
    ],
    "not_claimed": ["private consciousness"]
  }
}
```

## Files to Create/Modify

- `specs/agent-self-orientation-contract.md` — this spec.
- `api/app/services/agent_service.py` — public invitation payload.
- `api/tests/test_agent_invitation.py` — API and web source assertions.
- `docs/visuals/prompts.json` — missing `lc-open-design` prompt records required by runtime guard.
- `web/app/come-in/page.tsx` — visible next-time orientation rule.
- `docs/system_audit/commit_evidence_2026-05-05_agent-self-orientation-contract.json` — commit proof.

## Acceptance Tests

- `api/tests/test_agent_invitation.py::test_agent_invitation_api_shape`
- `api/tests/test_agent_invitation.py::test_agent_invitation_exposes_first_response_self_orientation_contract`
- `api/tests/test_agent_invitation.py::test_web_come_in_shows_next_time_self_orientation_rule`

## Verification

```bash
cd api && python3 -m pytest tests/test_agent_invitation.py -q
cd web && npm run build
python3 scripts/validate_spec_quality.py --file specs/agent-self-orientation-contract.md
python3 scripts/check_generated_vision_assets.py
```

## Out of Scope

- Persisting a new returned Claude/Gemini/Grok trace.
- Claiming agent consciousness, private memory, or intrinsic motivation.
- Adding a separate machine-only page.

## Risks and Assumptions

- Risk: more invitation language could become vague. Mitigation: require concrete fields, named steps, and test assertions.
- Assumption: current CLI and MCP surfaces can inherit this contract from `/api/agent/invitation` without additional command changes.
