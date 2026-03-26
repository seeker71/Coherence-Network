# Spec 157: OpenClaw skill auto-records interactions as contributions

## Purpose

OpenClaw sessions that use the Coherence Network skill perform real work (queries, analysis, user-visible outcomes). Without an explicit contribution step, that work is invisible to the network’s attribution and coherence ledger. This spec requires the published OpenClaw skill to **mandate recording each meaningful session as a contribution** via the existing non-interactive `cc contribute` path, so operator effort and agent-assisted outcomes align with Spec 048’s contribution model.

## Requirements

- [ ] The Coherence Network OpenClaw skill (`skills/coherence-network/SKILL.template.md`, regenerated `SKILL.md`) includes a dedicated section that orders the agent to run **`cc contribute`** after meaningful work (at minimum: **end of session** when any Coherence skill work was performed).
- [ ] That section documents the **non-interactive** form only: `cc contribute --type <type> --cc <amount> [--idea <idea_id>] --desc "<short summary>"`, consistent with `cli/lib/commands/contribute.mjs`.
- [ ] Automated test proves the skill text contains the mandatory command pattern and the ordered obligation (contribute step is not optional in the documented protocol).

## Research Inputs

- `2025+` — [Agent Skills / SKILL.md pattern](https://agentskills.io) — durable instructions for session-end behavior.
- `2026+` — Internal: `cli/lib/commands/contribute.mjs` — authoritative flags and `POST /api/contributions/record` mapping.
- `2026+` — [Spec 048: Contributions API](specs/048-contributions-api.md) — contribution semantics; record endpoint used by CLI.

## Task Card

```yaml
goal: Mandate OpenClaw skill documentation and tests so each meaningful session records a contribution via cc contribute.
files_allowed:
  - skills/coherence-network/SKILL.template.md
  - skills/coherence-network/SKILL.md
  - api/tests/test_openclaw_skill_auto_contribution.py
  - specs/157-openclaw-skill-auto-contribution.md
done_when:
  - SKILL.template.md and SKILL.md include mandatory cc contribute instruction after meaningful Coherence work (end of session minimum)
  - pytest passes and asserts required phrases/command form in skill text
commands:
  - python3 scripts/build_readmes.py
  - cd api && pytest -q tests/test_openclaw_skill_auto_contribution.py
constraints:
  - No new API endpoints; use existing POST /api/contributions/record via cc contribute only
  - Do not change contribution scoring rules
```

## API Contract

N/A — no API contract changes in this spec. Implementation uses existing `POST /api/contributions/record` as invoked by `cc contribute` (see `api/app/routers/contributions.py` and `cli/lib/commands/contribute.mjs`).

## Data Model

N/A — no schema changes; contributions use existing record payload (`contributor_id`, `type`, `amount_cc`, optional `idea_id`, `metadata.description`).

## Files to Create/Modify

- `skills/coherence-network/SKILL.template.md` — add “auto-record contribution” subsection under OpenClaw session protocol (or adjacent section).
- `skills/coherence-network/SKILL.md` — regenerate from template via `python3 scripts/build_readmes.py`.
- `api/tests/test_openclaw_skill_auto_contribution.py` — assert skill text encodes `cc contribute` non-interactive flags and end-of-session obligation.

## Acceptance Tests

- `api/tests/test_openclaw_skill_auto_contribution.py` — skill document contract (string checks mirroring Spec 149 pattern for inbox protocol).

## Concurrency Behavior

- **Reads**: N/A (documentation + static tests).
- **Writes**: Contribution POSTs follow existing store semantics for `POST /api/contributions/record` (last-write-wins at contribution row level; no new locking).

## Verification

```bash
python3 scripts/validate_spec_quality.py --base origin/main --head HEAD
python3 scripts/build_readmes.py
cd api && .venv/bin/pytest -q tests/test_openclaw_skill_auto_contribution.py
```

## Out of Scope

- Automatic contribution without an explicit `cc contribute` invocation (server-side inference from OpenClaw telemetry).
- Per-tool or per-token CC amounts; webhook or push-based recording.
- Changes to `cc contribute` flag parsing or new contribution types beyond documenting existing `--type` values.

## Risks and Assumptions

- **Risk**: Agents may skip the documented step; mitigation is the same as Spec 149 — explicit skill contract plus pytest regression on skill text.
- **Assumption**: `coherence-cli` is on PATH for OpenClaw sessions that install the skill (already required for `cc inbox` / `cc status` in Spec 149).

## Known Gaps and Follow-up Tasks

- None at spec time. Optional follow-up: measure contribution volume from OpenClaw-originated metadata tags (out of scope).

## Failure/Retry Reflection

- **Failure mode**: Operator forgets `--desc` or uses interactive `cc contribute` in automation.
- **Blind spot**: Non-interactive path not copy-pasted from skill.
- **Next action**: Skill text must show one complete example line with all required flags.

## Decision Gates

- None.
