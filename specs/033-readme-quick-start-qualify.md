# Spec: Fix README Quick Start — Qualify or Remove Web and Docker

## Purpose

README.md currently presents "cd web" and implies a web app as part of Quick Start, and may reference docker compose elsewhere. The web app and docker setup are not yet present (or not yet the supported path). New contributors should not be led to run commands that fail or depend on missing pieces. This spec aligns the README with the current scope: API-first, with web and docker qualified or omitted until those pieces exist.

## Requirements

- [ ] Quick Start does not present "cd web" / "npm run dev" as a primary or unqualified path; either remove that block or qualify it (e.g. "Web app: not yet available" or "See specs/012-web-skeleton.md when web/ is added").
- [ ] Any "docker compose" (or equivalent) instructions are removed or clearly qualified as future/not-yet-available; do not add docker compose to README until docker is present and documented.
- [ ] Quick Start keeps a working, copy-paste path for the API only (e.g. `cd api && uvicorn app.main:app --reload --port 8000`).
- [ ] No new broken or misleading links (e.g. "Visit http://localhost:3000" only if web is qualified as available).

## API Contract (if applicable)

N/A — documentation change only.

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
