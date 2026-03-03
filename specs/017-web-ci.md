# Spec: Web Build in CI

## Purpose

Add web app build to the CI pipeline so every push validates both API tests and web build. Completes coverage for spec 012 (web skeleton) in CI.

## Requirements

- [x] CI workflow runs `cd web && npm ci && npm run build` after API tests
- [x] Web build step fails CI if build fails
- [x] No deploy step; build-only validation

## API Contract

N/A — CI only.

## Files to Create/Modify

- `.github/workflows/test.yml` — add web build job or step
- `specs/004-ci-pipeline.md` — update Out of Scope (remove "Web app tests")

## Acceptance Tests

- Push triggers workflow
- API tests pass
- Web build passes (`cd web && npm ci && npm run build`)
- Workflow fails if either API tests or web build fail

## Out of Scope

- Web E2E tests (Playwright, etc.)
- Deploy step
- Lint for web (ESLint in CI)

## See also

- [004-ci-pipeline.md](004-ci-pipeline.md) — base CI workflow (updated Out of Scope)
- [012-web-skeleton.md](012-web-skeleton.md) — web app

## Decision Gates

None.
