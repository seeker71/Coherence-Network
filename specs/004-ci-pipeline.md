# Spec: CI Pipeline

## Purpose

Ensure every push and PR runs tests so the spec→test→impl workflow is validated. Completes Sprint 0 exit criteria: `git push → CI green`.

## Requirements

- [ ] GitHub Actions workflow runs on push to main and on pull_request
- [ ] Workflow installs Python 3.9+, dependencies, runs pytest in api/
- [ ] Workflow passes when all tests pass; fails otherwise
- [ ] Badge (optional) in README showing CI status

## API Contract

N/A — CI only.

## Data Model

N/A.

## Files to Create/Modify

- `.github/workflows/test.yml` — new: workflow definition
- `README.md` — optional: add CI status badge

## Acceptance Tests

- Push triggers workflow
- `cd api && pip install -e ".[dev]" && pytest -v` passes locally (equivalent to CI)
- Workflow status visible in GitHub Actions tab

## Out of Scope

- Coverage reports
- Lint (ruff, etc.)
- Web app tests (web/ not yet present)
- Deploy step

## Decision Gates

None.
