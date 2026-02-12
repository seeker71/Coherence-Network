# Spec: CI Pipeline

## Purpose

Ensure every push and PR runs tests so the spec→test→impl workflow is validated. Completes Sprint 0 exit criteria: `git push → CI green`. This spec also defines verification: confirm CI is complete and that the README shows CI status via a badge (adding the badge if missing).

## Requirements

- [ ] GitHub Actions workflow exists at `.github/workflows/test.yml` and runs on `push` to main/master and on `pull_request`
- [ ] Workflow installs Python 3.9+, installs API deps (`pip install -e ".[dev]"` in api/), and runs `pytest -v` in api/
- [ ] Workflow passes when all tests pass; fails otherwise
- [ ] README includes a CI status badge linking to the workflow; add the badge if missing

## Verification (CI complete)

- Workflow is present and triggers on push/PR
- `cd api && pip install -e ".[dev]" && pytest -v` passes locally (equivalent to CI)
- Workflow status visible in GitHub Actions tab
- Badge in README displays current status (e.g. `[![Test](https://github.com/OWNER/REPO/actions/workflows/test.yml/badge.svg)](url)`)

## API Contract

N/A — CI only.

## Data Model

N/A.

## Files to Create/Modify

- `.github/workflows/test.yml` — workflow definition (create if missing)
- `README.md` — add CI status badge if not present (badge target: workflow `test.yml`)

## Acceptance Tests

- Push or PR triggers the workflow
- Local equivalent passes: `cd api && pip install -e ".[dev]" && pytest -v`
- Workflow status visible in GitHub Actions tab
- README contains a badge that reflects the workflow status (add if missing)

## Out of Scope

- Coverage reports
- Lint in CI (ruff, etc.)
- Web E2E tests (see spec 017 for web build in CI)
- Deploy step

## See also

- [017-web-ci.md](017-web-ci.md) — web build step in CI

## Decision Gates

None.
