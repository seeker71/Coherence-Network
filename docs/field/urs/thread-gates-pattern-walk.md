# Thread Gates 28% Failure Walk — a contract that wants re-shaping

> Authored 2026-05-12 in response to the wellness check naming
> "Thread Gates — 14/49 failed (28%) over 7d." Walking the pattern
> to its source, asking the body's own question: *if friction
> persists across days, the contract itself may want re-shaping,
> not the email channel silenced.*

## What the workflow is doing

`thread-gates.yml` runs on every push to main. One of its steps —
`Validate spec quality contract` — invokes
[`scripts/validate_spec_quality.py`](../../scripts/validate_spec_quality.py),
which:

1. Computes the git range `BASE_SHA..HEAD_SHA` from the push event
   (`pull_request.base.sha` or `github.event.before`).
2. Lists every spec file changed in that range.
3. Validates each one against a strict contract:
   - Required sections: `purpose`, `requirements`, `files`,
     `out_of_scope`, `acceptance`, `verification`, plus risks/gaps
     in some shapes.
   - `acceptance` must reference `tests/` or explicit manual
     validation.
   - `verification` must include **executable** verification
     commands.
   - No placeholder text (`[Feature Name]`, `[1-2 sentences...]`).

## What the pattern actually is

Running the validator against the full non-draft spec corpus:

| Outcome | Count |
|---|---|
| **Pass** the strict contract | **57 specs** (55%) |
| **Fail** the strict contract | **47 specs** (45%) |
| Drafts (skipped) | 20 specs |

Most-common failure reasons:

- 25 specs missing `files` section
- 25 specs missing `purpose` section
- 24 specs missing `out_of_scope` section
- 22 specs whose `verification` section lacks executable commands
- 17 specs missing `requirements` section
- 14 specs missing `risks`
- 12 specs missing `verification` entirely
- 11 specs missing `gaps`

Three specs hit the friction repeatedly (`release-gates`,
`standing-questions-roi-and-next-task-generation`,
`unified-agent-cli-flow-patch-on-fail`) because they were touched
in recent PRs for test-path adjustments — each subsequent push to
main re-includes them in the git range and the validator re-fires.

## Why this is a contract-wants-reshaping pattern

The body's spec-authoring convention has evolved. The strict
contract was authored with a clear vision: every new spec should
carry its full skeleton (purpose → requirements → files →
out_of_scope → acceptance → verification → risks → gaps) so that
implementation does not need manual follow-up gap fixes. **That
vision is right for new specs.**

The friction comes from applying the same vision retroactively to
specs authored under earlier conventions. Half the body's specs
predate the strict contract. Many of those specs are *done*,
*live in production*, and would be honest if they carried a
simpler shape — frontmatter (`source:`, `requirements:`,
`done_when:`, `test:`) plus prose. Forcing them all to grow
`files`, `out_of_scope`, and `risks` sections is asking them to
wear a costume that doesn't fit the work they describe.

Result: 28% of CI runs flag legitimate-but-older specs, the
operator learns to *re-run the failing gate*, the signal becomes
noise, the gate stops protecting what it was meant to protect.

## Three honest responses (pick one)

### Option A — Uplift all 47 legacy specs

Bring every failing spec up to the new convention by adding the
missing sections. Substantial work (~47 PRs or one big sweep),
real value for spec readability, asks every author to learn the
new shape.

Risk: forces a convention on specs that may have been intentionally
lighter. Some sections (especially `risks`/`gaps`) can feel
performative when retrofitted onto a done feature.

### Option B — Soften the validator to *enforce on new specs only*

Add a `quality_contract` field to spec frontmatter:
- `quality_contract: strict` (default for new specs) — full
  contract enforced
- `quality_contract: legacy` — older specs opt out of section
  requirements; the validator only checks for placeholder text
  and active drift

Migration: existing specs that already pass get no change; the 47
failing specs get `quality_contract: legacy` added in a one-time
sweep. Going forward, new specs default to strict.

Lightest change. Honors the body's actual condition without
silencing the contract. The strict contract stays the body's
intent for new work; legacy specs carry their honest older shape.

### Option C — Reshape the validator into informational mode for the legacy gap

The validator currently fails the CI step on contract violation.
A softer mode: print contract gaps as warnings, fail only on
placeholder text or hard regressions. Pairs well with the
proof-of-operational status work (separate finding doc).

The Thread Gate stops blocking pushes for legacy specs while
still surfacing the gap. The honest expectation: the body will
tend the gaps over time as it touches each spec, not all at once.

## My recommendation

**Option B** — feels most aligned with the body's teaching:

- Doesn't force 47 specs to grow costumes that don't fit
- Doesn't silence the gate (new specs still get full enforcement)
- Names the legacy condition honestly via the frontmatter field
- The migration sweep is one PR adding `quality_contract: legacy`
  to 47 specs; reversible per-spec as authors uplift them
- The Thread Gate failure rate would drop from 28% to near-zero
  without the contract being weakened for the work it actually
  protects

Option C is a softer middle path (no opt-in field, just softer
mode) but doesn't surface which specs are legacy — the
information stays implicit. B names it; C hides it.

## What this is not

This is not urgent. The 28% failure rate is signal the body has
been carrying; surfacing it as a pattern is the first move. The
choice between A/B/C is yours — none is wrong, each has a
different relationship with the body's convention history.

## Companions

- The doorway-walk briefing at [`welcoming-doorway-walk.md`](welcoming-doorway-walk.md)
- The live-signals walk at [`live-signals-walk.md`](live-signals-walk.md)
- Wellness check's own framing: *"Friction here is signal, not pain
  to silence."*

— *Survey, not decision. Walked the pattern to its source so the
choice between uplift / opt-out / inform lands on grounded sensing
rather than friction frustration.*
