# Spec: Fix README Quick Start — Qualify or Remove Web and Docker

## Purpose

README.md currently presents "cd web" and implies a web app as part of Quick Start, and may reference docker compose elsewhere. The web app and docker setup are not yet present (or not yet the supported path). New contributors should not be led to run commands that fail or depend on missing pieces. This spec aligns the README with the current scope: API-first, with web and docker qualified or omitted until those pieces exist.

## Requirements

- [ ] Quick Start does not present "cd web" / "npm run dev" as a primary or unqualified path; either remove that block or qualify it (e.g. "Web app: not yet available" or "See specs/012-web-skeleton.md when web/ is added").
- [ ] Any "docker compose" (or equivalent) instructions are removed or clearly qualified as future/not-yet-available; do not add docker compose to README until docker is present and documented.
- [ ] Quick Start keeps a working, copy-paste path for the API only (e.g. `cd api && uvicorn app.main:app --reload --port 8000`).
- [ ] No new broken or misleading links (e.g. "Visit http://localhost:3000" only if web is qualified as available).


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: 012

## Task Card

```yaml
goal: README.
files_allowed:
  - README.md
done_when:
  - Quick Start does not present "cd web" / "npm run dev" as a primary or unqualified path; either remove that block or q...
  - Any "docker compose" (or equivalent) instructions are removed or clearly qualified as future/not-yet-available; do no...
  - Quick Start keeps a working, copy-paste path for the API only (e.g. `cd api && uvicorn app.main:app --reload --port 8...
  - No new broken or misleading links (e.g. "Visit http://localhost:3000" only if web is qualified as available).
commands:
  - python3 -m pytest api/tests/test_readme_contract.py -x -v
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

## API Contract (if applicable)

N/A — documentation change only.


### Input Validation

- All string fields: min_length=1, max_length=1000
- Numeric fields: appropriate min/max bounds
- Required fields validated; missing returns 422
- Unknown fields rejected (Pydantic extra="forbid" where applicable)

## Data Model (if applicable)

N/A.

## Files to Create/Modify

- `README.md` — Quick Start: remove or qualify "cd web" and web visit; remove or qualify any "docker compose"; ensure API-only path is clear and correct.

## Acceptance Tests

- Manual: README Quick Start section, when followed as written, does not direct users to run "cd web" or "docker compose" as if those are current, working options, unless explicitly qualified (e.g. "Future: …" or "When web/ is set up: …").
- Optional: add a small check in CI or docs validation that README does not contain unqualified "docker compose" (e.g. grep/script); only if such validation already exists for docs.

## Out of Scope

- Adding or implementing the web app (see specs/012-web-skeleton.md).
- Adding or implementing docker/docker compose.
- Changing other sections of README (e.g. Vision, Documentation links) unless they reference web or docker in a way that contradicts the qualified stance.

## Decision Gates (if any)

- None. Doc-only change per spec-driven scope.

## Concurrency Behavior

- **Read operations**: Safe for concurrent access; no locking required.
- **Write operations**: Last-write-wins semantics; no optimistic locking for MVP.
- **Recommendation**: Clients should not assume atomic read-modify-write without explicit ETag support.

## Failure and Retry Behavior

- **Render error**: Show fallback error boundary with retry action.
- **API failure**: Display user-friendly error message; retry fetch on user action or after 5s.
- **Network offline**: Show offline indicator; queue actions for replay on reconnect.
- **Asset load failure**: Retry asset load up to 3 times; show placeholder on permanent failure.
- **Timeout**: API calls timeout after 10s; show loading skeleton until resolved or failed.

## Risks and Known Gaps

- **No auth gate**: Endpoints unprotected until C1 auth middleware applied.
- **No rate limiting**: Subject to abuse until M1 rate limiter active.
- **Single-node only**: No distributed locking; concurrent access may race.
- **Follow-up**: Add end-to-end browser tests for critical paths.


## Verification

```bash
python3 -m pytest api/tests/test_readme_contract.py -x -v
```
