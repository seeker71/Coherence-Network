# Maintainability Audit Pattern Walk — twelve weeks of red

> Authored 2026-05-12 in response to the wellness check naming
> "Maintainability Architecture Audit — 1/1 failed (100%) over 7d."
> The 1/1 understates: it's run weekly on a cron schedule and has
> failed **five out of five** consecutive runs over the last
> twelve weeks. Open issue #219 has been carrying the same drift
> notice since 2026-02-19. The body has not picked it up.

## What the audit measures

`api/scripts/run_maintainability_audit.py` produces a structured
report on every Monday/Thursday at 11:00 UTC. Current run:

| Metric | Value |
|---|---|
| Severity | **high** |
| Risk score | 640 |
| Regression vs baseline | **yes** |
| Layer violations | 1 |
| Large modules | 28 |
| Very large modules | 9 |
| Long functions | 98 |
| Placeholders | 6 |

Severity = high and regression = yes is what flips the workflow's
`--fail-on-regression --fail-on-blocking` switches. Issue #219
gets updated with the same drift notice each Monday and Thursday.

## What's actually in there

### The 6 placeholders, examined

1. `api/app/routers/onboarding.py:93` — `/upgrade` endpoint marked
   `[stub 501]`. Returns 501 Not Implemented honestly. Real
   placeholder.
2. `api/app/services/agent_execution_completion.py:93,95` —
   `# TODO: pass executor explicitly if available` /
   `# TODO: use real token count when available`. Two TODOs, one
   code path.
3. `api/app/services/agent_execution_completion.py:176,178` — the
   same two TODOs in a second code path. The duplication itself
   is a refactor smell.
4. `web/components/inspired-by/shared.tsx:206` —
   `title="Placeholder held open for the real person to claim"`.
   **False positive.** This is the deliberate UI text on the card
   shown when an inspired-by figure hasn't been claimed yet. The
   audit's regex matched the word "Placeholder"; the semantic is
   intentional, not deferred work.

So the body honestly has *one stub endpoint* + *four TODOs in two
duplicated code paths* + *one false positive*.

### Large / very large modules

28 large + 9 very large. Without knowing the threshold, this is
the body's accumulated weight in places. Some growth is honest
(`automation_usage_service.py` is 6000+ lines because it carries
real complexity); some may have crossed the line into the kind of
file that's hard to reason about. The audit doesn't name which
modules; the JSON report lists them.

### 98 long functions

Same shape. Some functions are long because the work they do is
genuinely sequential and splitting hurts readability; some are
long because they ossified.

### 1 layer violation

A single cross-layer dependency the audit flags. Small in count,
worth knowing what it is — layer drift compounds.

## Why this is a contract-wants-reshaping pattern

Twelve weeks of weekly fails with **no behavior change** is the
body telling a story:

- Either the body is comfortable with the current state, and the
  audit's HIGH severity threshold is too strict for what the body
  considers urgent. (The audit's role then is informational, not
  blocking.)
- Or the body wants to tend this but the work (~45 hours per
  recommendation) is larger than any weekly breath has carried.
  (The audit then is doing its job — surfacing — and the body
  needs a non-weekly response.)

The actionable distinction matters:

- **Contract-too-strict** → adjust thresholds, mark intentional
  exceptions (the inspired-by false positive, the deliberate
  `[stub 501]` endpoint), and let HIGH severity mean *"the body
  agrees this is urgent."*
- **Body-deferring** → pick the smallest concrete tend (eliminate
  the four TODO duplications by extracting a helper; either
  implement `/upgrade` or document it as intentional stub) and
  begin the long arc on modules/functions.

Twelve weeks of no response suggests *both* are partly true. The
audit's threshold doesn't match the body's felt urgency; *and*
the body is also deferring real tends.

## Three honest responses

### Option A — Adjust the audit's thresholds + mark exceptions

- Add an exclusions list for known-intentional placeholders (the
  inspired-by UI text, the documented `[stub 501]` endpoint).
- Recalibrate HIGH severity threshold — maybe HIGH should require
  more than the current count of large modules to fire, given the
  body's deliberate complexity in services like
  `automation_usage_service`.
- Keep the audit running weekly; let it inform rather than block.
- Issue #219 stays open as a long-running tend with periodic
  updates.

### Option B — Pick one concrete tend per cycle

- Each weekly run, pick the highest-ROI item (currently
  runtime-placeholder-elimination, ROI 17.6, 3.4h) and the body
  tends it.
- Other items wait their turn.
- The audit's report becomes a sorted backlog rather than a
  failure signal.

### Option C — Reshape the gate to never block, just surface

- Workflow stops `exit 1` on regression; only updates the open
  issue.
- The body's signal still fires; nothing waits on the gate.
- Frees the audit from being a CI failure that operators learn to
  ignore.

## My recommendation

**A + small piece of B.** Adjust the audit to honor intentional
exceptions (the inspired-by UI text isn't a placeholder; the
`[stub 501]` is documented intent). That alone may not flip the
audit green but it reduces false noise. Pair with a *one
TODO-deduplication tend* — collapse the `executor`/`token_count`
duplicate TODOs in `agent_execution_completion.py` to a shared
helper. Small, concrete, real signal-following.

What to leave: the big architecture-modularization-review
(45-hour refactor) wants a real plan, not a "tend it in one
breath" approach. Holding that for separate consideration.

## What this is not

Not urgent. The audit's signal has been present for twelve weeks;
the body has been carrying it. Naming the pattern is the breath;
the choice between A / B / C / wait is yours.

## Companions

- [`thread-gates-pattern-walk.md`](thread-gates-pattern-walk.md) —
  the parallel finding for the Thread Gates 28% pattern. Same
  shape: contract that wants reshaping rather than channel silenced.
- The wellness check's own framing: *"Friction here is signal, not
  pain to silence. If a pattern persists across days, the contract
  itself may want re-shaping."* Twelve weeks is a lot of "across
  days."

— *Walked the pattern, surfaced its shape, named three honest
responses. The body's twelve-week silence is itself signal; the
audit and the body have been speaking past each other.*
