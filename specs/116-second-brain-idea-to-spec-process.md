# Spec: Second Brain — Idea-to-Spec Process (DiSSS Framework)

## Purpose

Raw ideas stall between capture and implementation because they aren't examined through the right lenses. This spec introduces four thinking prompts — Deconstruct, Select, Sequence, Stakes — as recommended guidance when shaping an idea into a spec. The goal is sharper specs and faster surfacing of high-leverage work, without adding process overhead that discourages contribution.

## Requirements

- [ ] The spec template (`specs/TEMPLATE.md`) includes an "Idea Shaping" section with four thinking prompts: Deconstruct, Select, Sequence, Stakes
- [ ] The section is marked as recommended guidance, not a hard gate — authors can skip or adapt it
- [ ] The Ideas API data model gains optional `sub_claims` and `intake_status` fields for teams that want structured tracking
- [ ] `intake_status` values: `raw`, `deconstructed`, `selected`, `sequenced`, `committed` — all optional, default `raw`
- [ ] Sub-claims support optional `depends_on`, `unblocks`, `value_decay_days`, and `committed_by` fields
- [ ] `validate_spec_quality.py` does **not** enforce the Idea Shaping section — it remains advisory
- [ ] Existing specs are unaffected (fully backwards compatible)

## Research Inputs (Required)

- `2007-01-01` - [The 4-Hour Chef / DiSSS framework (Tim Ferriss)](https://tim.blog/the-4-hour-chef/) - Deconstruction, Selection, Sequencing, Stakes as a meta-learning framework applied to skill acquisition; adapted here for idea-to-spec conversion
- `2026-03-11` - [Second Brain Substack](https://substack.com/@secondbrain1) - Principle articulation that prompted this spec

## Task Card (Required)

```yaml
goal: Add four-lens idea shaping guidance to the spec template and optional intake fields to the Ideas API
files_allowed:
  - specs/TEMPLATE.md
  - specs/116-second-brain-idea-to-spec-process.md
  - scripts/validate_spec_quality.py
  - api/app/models/idea.py
  - api/app/services/idea_service.py
  - api/app/routers/ideas.py
  - api/tests/test_ideas.py
done_when:
  - TEMPLATE.md contains Idea Shaping section with four lenses
  - validate_spec_quality.py unchanged (section is advisory)
  - Ideas model includes sub_claims and intake_status fields
  - Existing specs pass validation without Intake section
commands:
  - python3 scripts/validate_spec_quality.py --file specs/TEMPLATE.md
  - cd api && pytest -q tests/test_ideas.py
constraints:
  - Backwards compatible — existing specs must not break
  - No changes to scoring algorithm
  - intake_status fields are optional (default: raw)
```

## API Contract (if applicable)

### Changes to existing endpoints

#### `GET /api/ideas` — Response additions

Each idea in the `ideas` array gains optional fields:

```json
{
  "intake_status": "deconstructed",
  "sub_claims": [
    {
      "claim": "Route registry can be derived from FastAPI app introspection",
      "potential_value": 40.0,
      "estimated_cost": 4.0,
      "confidence": 0.9,
      "free_energy_score": 9.0,
      "selected": true,
      "depends_on": [],
      "unblocks": ["spec-055"],
      "value_decay_days": 14,
      "committed_by": "2026-03-25"
    }
  ]
}
```

#### `PATCH /api/ideas/{idea_id}` — Body additions

```json
{
  "intake_status": "selected",
  "sub_claims": [...]
}
```

- `intake_status`: String (optional) — One of: "raw", "deconstructed", "selected", "sequenced", "committed"
- `sub_claims`: List (optional) — Atomic decomposition of the idea

## Data Model (if applicable)

```yaml
IntakeStatus: enum
  - raw            # Idea captured, not yet decomposed
  - deconstructed  # Broken into sub-claims
  - selected       # Top sub-claims chosen (≥80% value coverage)
  - sequenced      # Dependencies and unblocks declared
  - committed      # Stakes set, ready for spec authoring

SubClaim:
  claim: String (min 1 char)
  potential_value: Float (≥ 0.0)
  estimated_cost: Float (≥ 0.0)
  confidence: Float (0.0–1.0)
  free_energy_score: Float (computed, read-only)
  selected: Boolean (default: false)
  depends_on: List[String] (default: [])
  unblocks: List[String] (default: [])
  value_decay_days: Integer | null (≥ 1)
  committed_by: String | null (ISO 8601 date)

Idea (extended):
  # ... existing fields ...
  intake_status: IntakeStatus (default: raw)
  sub_claims: List[SubClaim] (default: [])
```

## Files to Create/Modify

- `specs/TEMPLATE.md` — Add `## Intake: DiSSS` section with four subsections
- `specs/116-second-brain-idea-to-spec-process.md` — This spec
- `scripts/validate_spec_quality.py` — Add intake section validation for new specs
- `api/app/models/idea.py` — Add `IntakeStatus`, `SubClaim`, and extend `Idea` model
- `api/app/services/idea_service.py` — Compute `free_energy_score` for sub-claims
- `api/app/routers/ideas.py` — Accept `intake_status` and `sub_claims` in PATCH
- `api/tests/test_ideas.py` — Add tests for intake fields and sub-claim scoring

## Acceptance Tests

- `api/tests/test_ideas.py::test_patch_idea_intake_status` — PATCH updates intake_status
- `api/tests/test_ideas.py::test_patch_idea_sub_claims_with_scoring` — Sub-claims get computed free_energy_score
- `api/tests/test_ideas.py::test_list_ideas_includes_intake_fields` — GET /api/ideas returns intake_status and sub_claims
- Manual validation: `python3 scripts/validate_spec_quality.py --file specs/TEMPLATE.md` passes
- Manual validation: existing specs without Intake section still pass validation

## Verification

```bash
python3 scripts/validate_spec_quality.py --file specs/116-second-brain-idea-to-spec-process.md
python3 scripts/validate_spec_quality.py --file specs/TEMPLATE.md
cd api && pytest -q tests/test_ideas.py
```

## Out of Scope

- Automated idea decomposition (AI-assisted breakdown is a follow-up)
- UI for the intake flow (web pages for DiSSS phases)
- Enforcing committed_by deadlines (alerting/escalation is a follow-up)
- Changing the existing free energy scoring formula
- Retroactive intake annotation of existing ideas

## Risks and Assumptions

- **Risk:** If guidance is too prescriptive, authors skip it entirely; mitigation: keep it to four short prompts, not a form to fill out
- **Risk:** Sub-claim decomposition quality varies by author; mitigation: seed examples in existing high-priority ideas so the pattern is learned by imitation, not enforcement
- **Assumption:** The free energy score formula applies equally well at the sub-claim level as at the idea level; if sub-claims have fundamentally different cost structures, the formula may need tuning

## Known Gaps and Follow-up Tasks

- Follow-up task: AI-assisted deconstruction — use LLM to suggest sub-claims from a raw idea description
- Follow-up task: Decay alerting — notify when an idea's `value_decay_days` threshold is crossed without a spec
- Follow-up task: Web UI for intake flow — visual pipeline from raw → committed
- Follow-up task: Sequencing graph visualization — show depends_on/unblocks as a DAG

## Failure/Retry Reflection

- Failure mode: Spec authors skip the intake section because it feels like overhead
- Blind spot: Process adoption requires visible value within the first 2-3 uses
- Next action: Seed 3 existing high-priority ideas with fully worked intake sections as examples

## Decision Gates (if any)

- None — guidance approach chosen deliberately over enforcement.
