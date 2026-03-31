# Spec: Web Build in CI

## Purpose

Add web app build to the CI pipeline so every push validates both API tests and web build. Completes coverage for spec 012 (web skeleton) in CI.

## Requirements

- [x] CI workflow runs `cd web && npm ci && npm run build` after API tests
- [x] Web build step fails CI if build fails
- [x] No deploy step; build-only validation


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: 004, 012

## Task Card

```yaml
goal: Add web app build to the CI pipeline so every push validates both API tests and web build.
files_allowed:
  - .github/workflows/test.yml
  - specs/004-ci-pipeline.md
done_when:
  - CI workflow runs `cd web && npm ci && npm run build` after API tests
  - Web build step fails CI if build fails
  - No deploy step; build-only validation
commands:
  - cd api && python -m pytest tests/ -q
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

## API Contract

N/A — CI only.


### Input Validation

- All string fields: min_length=1, max_length=1000
- Numeric fields: appropriate min/max bounds
- Required fields validated; missing returns 422
- Unknown fields rejected (Pydantic extra="forbid" where applicable)

## Files to Create/Modify

- `.github/workflows/test.yml` — add web build job or step
- `specs/004-ci-pipeline.md` — update Out of Scope (remove "Web app tests")

## Acceptance Tests

- Push triggers workflow
- API tests pass
- Web build passes (`cd web && npm ci && npm run build`)
- Workflow fails if either API tests or web build fail

## Concurrency Behavior

- **Read operations**: Safe for concurrent access; no locking required.
- **Write operations**: Last-write-wins semantics; no optimistic locking for MVP.
- **Recommendation**: Clients should not assume atomic read-modify-write without explicit ETag support.

## Failure and Retry Behavior

- **Gate failure**: CI gate blocks merge; author must fix and re-push.
- **Flaky test**: Re-run up to 2 times before marking as genuine failure.
- **Rollback behavior**: Failed deployments automatically roll back to last known-good state.
- **Infrastructure failure**: CI runner unavailable triggers alert; jobs re-queue on recovery.
- **Timeout**: CI jobs exceeding 15 minutes are killed and marked failed; safe to re-trigger.

## Risks and Known Gaps

- **No auth gate**: Endpoints unprotected until C1 auth middleware applied.
- **No rate limiting**: Subject to abuse until M1 rate limiter active.
- **Single-node only**: No distributed locking; concurrent access may race.
- **Follow-up**: Add deployment smoke tests post-release.


## Out of Scope

- Web E2E tests (Playwright, etc.)
- Deploy step
- Lint for web (ESLint in CI)

## See also

- [004-ci-pipeline.md](004-ci-pipeline.md) — base CI workflow (updated Out of Scope)
- [012-web-skeleton.md](012-web-skeleton.md) — web app

## Decision Gates

None.
