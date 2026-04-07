---
idea_id: data-infrastructure
status: done
source:
  - file: api/app/services/coherence_service.py
    symbols: [compute_coherence()]
  - file: api/app/routers/coherence.py
    symbols: [coherence score endpoint]
  - file: api/app/services/coherence_signal_depth_service.py
    symbols: [signal depth]
requirements:
  - "Document inputs: contributor_diversity, dependency_health, activity_cadence, documentation_quality, community_responsive"
  - "Document output: score 0.0–1.0 per project"
  - "Document pitfalls: gaming prevention, contribution-type balance"
  - "Add weights stub (all equal or placeholder) — actual weights are decision gate"
done_when:
  - "Document inputs: contributor_diversity, dependency_health, activity_cadence, documentation_quality, community_respons..."
  - "Document output: score 0.0–1.0 per project"
  - "Document pitfalls: gaming prevention, contribution-type balance"
  - "Add weights stub (all equal or placeholder) — actual weights are decision gate"
test: "python3 -m pytest api/tests/test_cc_scoring.py -x -v"
constraints:
  - "changes scoped to listed files only"
  - "no schema migrations without explicit approval"
---

> **Parent idea**: [data-infrastructure](../ideas/data-infrastructure.md)
> **Source**: [`api/app/services/coherence_service.py`](../api/app/services/coherence_service.py) | [`api/app/routers/coherence.py`](../api/app/routers/coherence.py) | [`api/app/services/coherence_signal_depth_service.py`](../api/app/services/coherence_signal_depth_service.py)

# Spec: Coherence Algorithm — Formal Spec

## Purpose

Formalize the coherence score algorithm from docs/concepts/COHERENCE-ALGORITHM-SKETCH.md so implementation (Sprint 2+) has clear inputs, outputs, and weights. No implementation in this spec.

## Requirements

- [x] Document inputs: contributor_diversity, dependency_health, activity_cadence, documentation_quality, community_responsiveness, funding_sustainability, security_posture, downstream_impact
- [x] Document output: score 0.0–1.0 per project
- [x] Document pitfalls: gaming prevention, contribution-type balance
- [x] Add weights stub (all equal or placeholder) — actual weights are decision gate


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: 008

## Task Card

```yaml
goal: Formalize the coherence score algorithm from docs/concepts/COHERENCE-ALGORITHM-SKETCH.
files_allowed:
  - docs/concepts/COHERENCE-ALGORITHM-SKETCH.md
  - specs/coherence-algorithm-spec.md
done_when:
  - Document inputs: contributor_diversity, dependency_health, activity_cadence, documentation_quality, community_respons...
  - Document output: score 0.0–1.0 per project
  - Document pitfalls: gaming prevention, contribution-type balance
  - Add weights stub (all equal or placeholder) — actual weights are decision gate
commands:
  - python3 -m pytest api/tests/test_cc_scoring.py -x -v
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

## API Contract (implemented in spec 020)

GET /api/projects/{ecosystem}/{name}/coherence returns `{"score": 0.0–1.0, "components": {...}}`. Path matches project lookup from spec 008.


### Input Validation

- All string fields: min_length=1, max_length=1000
- Numeric fields: appropriate min/max bounds
- Required fields validated; missing returns 422
- Unknown fields rejected (Pydantic extra="forbid" where applicable)

## Files to Create/Modify

- `docs/concepts/COHERENCE-ALGORITHM-SKETCH.md` — expand with formal input/output, weights stub
- `specs/coherence-algorithm-spec.md` — this spec

## Acceptance Tests

- COHERENCE-ALGORITHM-SKETCH.md documents all 8 inputs
- Pitfalls section present
- Weights stub (e.g. "Default: equal weight per component; override via config")

## Out of Scope

- Implementation (Sprint 2)
- Actual weight values (decision gate)
- Data sourcing (deps.dev, GitHub — spec 008)

## See also

- [008-sprint-1-graph-foundation.md](008-sprint-1-graph-foundation.md) — graph data source
- docs/concepts/COHERENCE-ALGORITHM-SKETCH.md

## Decision Gates

- Actual weight values require human approval
- Coherence formula changes require needs-decision

## Concurrency Behavior

- **Read operations**: Safe for concurrent access; no locking required.
- **Write operations**: Last-write-wins semantics; no optimistic locking for MVP.
- **Recommendation**: Clients should not assume atomic read-modify-write without explicit ETag support.

## Failure and Retry Behavior

- **Invalid input**: Return 422 with field-level validation errors.
- **Resource not found**: Return 404 with descriptive message.
- **Database unavailable**: Return 503; client should retry with exponential backoff (initial 1s, max 30s).
- **Concurrent modification**: Last write wins; no optimistic locking required for MVP.
- **Timeout**: Operations exceeding 30s return 504; safe to retry.

## Risks and Known Gaps

- **No auth gate**: Endpoints unprotected until C1 auth middleware applied.
- **No rate limiting**: Subject to abuse until M1 rate limiter active.
- **Single-node only**: No distributed locking; concurrent access may race.
- **Follow-up**: Add integration tests for error edge cases.


## Verification

```bash
python3 -m pytest api/tests/test_cc_scoring.py -x -v
```

## Known Gaps and Follow-up Tasks

- No known gaps at time of writing.
- Follow-up: review after initial implementation for completeness.
