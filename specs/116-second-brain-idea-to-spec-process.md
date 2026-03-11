# Spec: Second Brain — Idea-to-Spec Process

## Purpose

Raw ideas stall between capture and implementation because they aren't examined through the right lenses, and because context lives in people's heads instead of in files. This spec adds an "Idea Shaping" section to the spec template with seven thinking prompts drawn from two frameworks: DiSSS (Deconstruct, Select, Sequence, Stakes) for breaking ideas apart, and Cowork principles (context as files, outcome-first, forced questions) for making specs actionable by both humans and AI agents.

## Idea Shaping

### Break it apart

**Deconstruct** — Two pieces: (1) the template section itself, (2) optional API fields for structured tracking.

**Select** — The template guidance is the high-leverage piece — it changes how every future spec gets written. The API fields are useful but secondary; they can follow once the guidance pattern proves out.

**Sequence** — Template first (no dependencies). API fields depend on seeing whether authors actually use the prompts.

**Stakes** — Every spec written without these lenses is a missed chance to catch vague thinking early. The template change costs nothing to try and is easy to revert.

### Make it actionable

**Context to read** — `specs/TEMPLATE.md` (the file being changed), `specs/053-ideas-prioritization.md` (existing ideas model), `scripts/validate_spec_quality.py` (to confirm no enforcement needed).

**Done state** — The spec template has an Idea Shaping section with seven prompts in two groups, positioned before Requirements. New specs can use the prompts to sharpen their thinking. Nothing breaks for existing specs.

**Open questions** — Should the API fields (`intake_status`, `sub_claims`) be in this spec or split into a follow-up? (Answer: follow-up — keep this spec focused on the template.)

## Requirements

- [ ] The spec template (`specs/TEMPLATE.md`) includes an "Idea Shaping" section before Requirements
- [ ] Seven thinking prompts in two groups: four for decomposition (Deconstruct, Select, Sequence, Stakes), three for execution (Context to read, Done state, Open questions)
- [ ] The section is marked as recommended guidance — authors can skip or adapt it
- [ ] `validate_spec_quality.py` does **not** enforce the section — it remains advisory
- [ ] Existing specs are unaffected (fully backwards compatible)

## Research Inputs (Required)

- `2007-01-01` - [The 4-Hour Chef / DiSSS framework (Tim Ferriss)](https://tim.blog/the-4-hour-chef/) - Deconstruction, Selection, Sequencing, Stakes as a meta-learning framework; adapted here for idea-to-spec conversion
- `2026-03-11` - [Second Brain Substack](https://substack.com/@secondbrain1) - Principle articulation that prompted this spec
- `2026-03-01` - [Cowork — Ruben Hassid](https://ruben.substack.com/p/claude-cowork) - Context via files not prompts, outcome-driven delegation, force the system to ask questions; adapted as three execution prompts

## Task Card (Required)

```yaml
goal: Add seven-lens idea shaping guidance to the spec template
files_allowed:
  - specs/TEMPLATE.md
  - specs/116-second-brain-idea-to-spec-process.md
done_when:
  - TEMPLATE.md contains Idea Shaping section with seven prompts before Requirements
  - Existing specs pass validation unchanged
commands:
  - python3 scripts/validate_spec_quality.py --file specs/TEMPLATE.md
constraints:
  - Backwards compatible — existing specs must not break
  - No changes to validate_spec_quality.py
  - No API or model changes in this spec
```

## API Contract (if applicable)

N/A - no API contract changes in this spec. API extensions (`intake_status`, `sub_claims`) are a follow-up.

## Data Model (if applicable)

N/A - no model changes in this spec.

## Files to Create/Modify

- `specs/TEMPLATE.md` — Add Idea Shaping section with seven thinking prompts, reorder before Requirements
- `specs/116-second-brain-idea-to-spec-process.md` — This spec

## Acceptance Tests

- Manual validation: `python3 scripts/validate_spec_quality.py --file specs/TEMPLATE.md` passes
- Manual validation: `python3 scripts/validate_spec_quality.py` (all specs) passes without regression

## Verification

```bash
python3 scripts/validate_spec_quality.py --file specs/TEMPLATE.md
python3 scripts/validate_spec_quality.py --file specs/116-second-brain-idea-to-spec-process.md
```

## Out of Scope

- API fields for structured intake tracking (`intake_status`, `sub_claims`) — follow-up spec
- AI-assisted idea deconstruction
- Web UI for idea shaping flow
- Enforcement via validator — this is guidance, not a gate
- Retroactive application to existing specs

## Risks and Assumptions

- **Risk:** Authors skip the section because it feels like overhead; mitigation: keep it short (seven one-line prompts), position it early in the template so it's seen before the detailed sections, and seed worked examples in high-priority specs
- **Assumption:** Guidance that improves thinking quality will be adopted voluntarily without enforcement; if adoption is low after 10+ new specs, reconsider adding a soft validator warning

## Known Gaps and Follow-up Tasks

- Follow-up task: API extensions — add optional `intake_status` and `sub_claims` fields to the Ideas data model for teams that want structured tracking
- Follow-up task: Worked examples — fill in Idea Shaping for 3 existing high-priority specs to demonstrate the pattern

## Failure/Retry Reflection

- Failure mode: Spec authors treat the section as boilerplate and fill it mechanically
- Blind spot: The prompts only work if they actually change the author's thinking, not just add text
- Next action: Review the first 5 specs that use the section — if the answers are generic, simplify or cut prompts that aren't earning their keep

## Decision Gates (if any)

- None — guidance approach chosen deliberately over enforcement.
