# Spec 015 — Placeholder (merged into 018)

## Purpose

Spec 015 was planned in the backlog for "coherence algorithm: algorithm sketch, inputs, outputs, weights stub." That work was implemented as **spec 018** (Coherence Algorithm — Formal Spec). This file exists only to preserve spec numbering; all requirements live in [018-coherence-algorithm-spec.md](018-coherence-algorithm-spec.md).


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: 018, 020

## Task Card

```yaml
goal: Spec 015 was planned in the backlog for "coherence algorithm: algorithm sketch, inputs, outputs, weights stub.
files_allowed:
  - # TBD — determine from implementation
done_when:
  - All requirements implemented and tests pass
commands:
  - cd api && python -m pytest tests/ -q
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

## Status

- **Merged into:** [018-coherence-algorithm-spec.md](018-coherence-algorithm-spec.md)
- **API:** GET /api/projects/{ecosystem}/{name}/coherence implemented in [020-sprint-2-coherence-api.md](020-sprint-2-coherence-api.md)

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

## Acceptance Tests

See `api/tests/test_placeholder.py` for test cases covering this spec's requirements.

## Known Gaps and Follow-up Tasks

- No known gaps at time of writing.
- Follow-up: review after initial implementation for completeness.
