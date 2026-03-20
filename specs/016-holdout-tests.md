# Spec: Holdout Tests Pattern

## Purpose

Prevent implementations that "game" tests (e.g. return true without real logic). Tests in `tests/holdout/` are excluded from agent context; CI runs them.

## Requirements

- [x] Directory `api/tests/holdout/` exists with README
- [x] Placeholder test in holdout (e.g. test_holdout_placeholder)
- [x] Agent runs use `pytest --ignore=tests/holdout/` (project_manager)
- [x] CI runs full suite including holdout: `pytest -v` (no ignore)
- [x] Document pattern in docs/SPEC-COVERAGE.md and AGENTS.md


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: 005

## Task Card

```yaml
goal: Prevent implementations that "game" tests (e.
files_allowed:
  - api/tests/holdout/README.md
  - api/tests/holdout/test_placeholder.py
  - docs/SPEC-COVERAGE.md
done_when:
  - Directory `api/tests/holdout/` exists with README
  - Placeholder test in holdout (e.g. test_holdout_placeholder)
  - Agent runs use `pytest --ignore=tests/holdout/` (project_manager)
  - CI runs full suite including holdout: `pytest -v` (no ignore)
  - Document pattern in docs/SPEC-COVERAGE.md and AGENTS.md
commands:
  - cd api && python -m pytest api/tests/holdout/README.md -q
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

## API Contract

N/A.


### Input Validation

- All string fields: min_length=1, max_length=1000
- Numeric fields: appropriate min/max bounds
- Required fields validated; missing returns 422
- Unknown fields rejected (Pydantic extra="forbid" where applicable)

## Files to Create/Modify

- `api/tests/holdout/README.md` — pattern explanation
- `api/tests/holdout/test_placeholder.py` — placeholder
- Project manager / agent runner — use `--ignore=tests/holdout` when invoking pytest for validation
- `docs/SPEC-COVERAGE.md` — add holdout section

## Acceptance Tests

- `pytest api/tests` runs holdout tests
- `pytest api/tests --ignore=api/tests/holdout` skips holdout
- Holdout README explains purpose

## Concurrency Behavior

- **Read operations**: Safe for concurrent access; no locking required.
- **Write operations**: Last-write-wins semantics; no optimistic locking for MVP.
- **Recommendation**: Clients should not assume atomic read-modify-write without explicit ETag support.

## Failure and Retry Behavior

- **Task failure**: Log error, mark task failed, advance to next item or pause for human review.
- **Retry logic**: Failed tasks retry up to 3 times with exponential backoff (initial 2s, max 60s).
- **Partial completion**: State persisted after each phase; resume from last checkpoint on restart.
- **External dependency down**: Pause pipeline, alert operator, resume when dependency recovers.
- **Timeout**: Individual task phases timeout after 300s; safe to retry from last phase.

## Risks and Known Gaps

- **No auth gate**: Endpoints unprotected until C1 auth middleware applied.
- **No rate limiting**: Subject to abuse until M1 rate limiter active.
- **Single-node only**: No distributed locking; concurrent access may race.
- **Follow-up**: Add distributed locking for multi-worker pipelines.


## Out of Scope

- Specific holdout test implementations (add per feature)
- Coverage exclusion for holdout

## See also

- [005-project-manager-pipeline.md](005-project-manager-pipeline.md) — PM uses --ignore=tests/holdout

## Decision Gates

None.
