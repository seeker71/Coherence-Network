# Spec: CI Pipeline

## Purpose

Ensure every push and PR runs tests so the spec→test→impl workflow is validated. Completes Sprint 0 exit criteria: `git push → CI green`. This spec defines the CI pipeline, how to **verify CI is complete**, and requires that the README shows CI status via a badge (**add the badge if missing**).

## Requirements

- [ ] GitHub Actions workflow exists at `.github/workflows/test.yml` and runs on `push` to main/master and on `pull_request`
- [ ] Workflow installs Python 3.9+, installs API deps (`pip install -e ".[dev]"` in api/), and runs `pytest -v` in api/
- [ ] Workflow passes when all tests pass; fails otherwise
- [ ] README includes a CI status badge linking to the workflow; **add the badge if missing**
- [ ] Verification: CI is confirmed complete (workflow present, triggers correct, local equivalent passes, badge present)

## Verification (CI complete)

Before considering CI "complete", verify:

1. **Workflow present** — `.github/workflows/test.yml` exists and triggers on `push` (main/master) and `pull_request`
2. **Local equivalent passes** — `cd api && pip install -e ".[dev]" && pytest -v` succeeds locally (same as CI core)
3. **GitHub Actions** — Workflow runs and status is visible in the repository Actions tab
4. **Badge in README** — README contains a status badge that reflects the workflow (e.g. `[![Test](https://github.com/OWNER/REPO/actions/workflows/test.yml/badge.svg)](https://github.com/OWNER/REPO/actions/workflows/test.yml)`). **Add this badge to README if it is missing.**

## API Contract

N/A — CI only.

## Data Model

N/A.

## Files to Create/Modify

- `.github/workflows/test.yml` — workflow definition (create if missing; must run API tests as above)
- `README.md` — add CI status badge if not present (badge target: workflow `test.yml`; use repo OWNER/REPO in URLs)

## Acceptance Tests

- Push or PR triggers the workflow
- Local equivalent passes: `cd api && pip install -e ".[dev]" && pytest -v`
- Workflow status visible in GitHub Actions tab
- README contains a badge that reflects the workflow status (**add if missing**)

## Out of Scope

- Coverage reports
- Lint in CI (ruff, etc.)
- Web E2E tests (see spec 017 for web build in CI)
- Deploy step

## See also

- [017-web-ci.md](017-web-ci.md) — web build step in CI

## Decision Gates

None.

## Idea Traceability
- `idea_id`: `coherence-network-overall`
- Rationale: umbrella roadmap linkage for Coherence Network work.
