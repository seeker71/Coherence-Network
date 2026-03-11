# Spec: Second Brain — Idea-to-Spec Process (DiSSS Framework)

## Purpose

Raw ideas stall between capture and implementation because the pipeline lacks structured decomposition, principled selection, explicit sequencing, and real stakes. This spec introduces a four-phase intake process — Deconstruction, Selection, Sequencing, Stakes — applied to every idea before it earns a full spec. The goal is to eliminate spec bloat, surface the highest-leverage work faster, and create accountability that prevents ideas from rotting in the backlog.

## Requirements

- [ ] Every new idea submitted to the Ideas API or `specs/` must pass through a four-phase intake gate before a full spec is authored
- [ ] **Deconstruction phase**: idea is broken into atomic sub-claims, each with its own `potential_value`, `estimated_cost`, and `confidence`
- [ ] **Selection phase**: sub-claims are ranked by free energy score; only the top sub-claims (those covering ≥80% of total value) proceed to spec
- [ ] **Sequencing phase**: selected sub-claims declare explicit `depends_on` and `unblocks` references (spec IDs or capability names)
- [ ] **Stakes phase**: each selected sub-claim declares a `value_decay_days` (integer) — the number of days after which the opportunity cost doubles, and a `committed_by` date (ISO 8601)
- [ ] The spec template (`specs/TEMPLATE.md`) is updated with a new `## Intake: DiSSS` section containing these four phases
- [ ] `validate_spec_quality.py` is updated to check that new specs include the Intake section with non-placeholder content
- [ ] The Ideas API data model gains optional `sub_claims` and `intake_status` fields (enum: `raw`, `deconstructed`, `selected`, `sequenced`, `committed`)
- [ ] Ideas with `intake_status: raw` cannot have specs authored against them (enforced by validator)
- [ ] Existing specs are not retroactively required to have the Intake section (backwards compatible)

## Research Inputs (Required)

- `2007-01-01` - [The 4-Hour Chef / DiSSS framework (Tim Ferriss)](https://tim.blog/the-4-hour-chef/) - Deconstruction, Selection, Sequencing, Stakes as a meta-learning framework applied to skill acquisition; adapted here for idea-to-spec conversion
- `2026-03-11` - [Second Brain Substack](https://substack.com/@secondbrain1) - Principle articulation that prompted this spec

## Task Card (Required)

```yaml
goal: Add four-phase DiSSS intake gate to the idea-to-spec pipeline
files_allowed:
  - specs/TEMPLATE.md
  - specs/116-second-brain-idea-to-spec-process.md
  - scripts/validate_spec_quality.py
  - api/app/models/idea.py
  - api/app/services/idea_service.py
  - api/app/routers/ideas.py
  - api/tests/test_ideas.py
done_when:
  - TEMPLATE.md contains Intake DiSSS section
  - validate_spec_quality.py checks for Intake section on new specs
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

- **Risk:** Adding required fields to the intake process may slow down idea capture; mitigation: `intake_status` defaults to `raw` and all new fields are optional
- **Risk:** Sub-claim decomposition quality varies by author; mitigation: validator checks for minimum claim count (≥2) when intake_status is `deconstructed` or beyond
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

- `needs-decision`: Should `intake_status: raw` ideas be hard-blocked from spec authoring, or should it be a warning only?
