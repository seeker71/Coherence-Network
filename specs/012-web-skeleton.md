# Spec: Web Skeleton

## Purpose

Deliver a minimal Next.js 15 app with a root route (`/`) and an `/api-health` check page so the Coherence web front is runnable and can verify backend connectivity. Supports Sprint 0 "landing live" (docs/PLAN.md). Stack: Next.js 15 + shadcn/ui.

## Requirements

- [ ] Next.js 15 app in `web/` directory
- [ ] Page `/` (root) renders without error; shows project name and link to API docs
- [ ] Page `/api-health` exists and displays API health status (fetches backend health endpoint)
- [ ] shadcn/ui installed with minimal components (e.g. Button)
- [ ] API base URL configurable via `NEXT_PUBLIC_API_URL`


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: 001, 014

## Task Card

```yaml
goal: Deliver a minimal Next.
files_allowed:
  - web/
  - web/app/page.tsx
  - web/app/api-health/page.tsx
  - web/.env.example
  - README.md
done_when:
  - Next.js 15 app in `web/` directory
  - Page `/` (root) renders without error; shows project name and link to API docs
  - Page `/api-health` exists and displays API health status (fetches backend health endpoint)
  - shadcn/ui installed with minimal components (e.g. Button)
  - API base URL configurable via `NEXT_PUBLIC_API_URL`
commands:
  - cd api && python -m pytest tests/ -q
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

## API Contract (consumed by web)

Web consumes the existing API health endpoint (see [001-health-check.md](001-health-check.md)).

### `GET /api/health` (backend)

**Response 200**
```json
{ "status": "ok" }
```

The `/api-health` page MUST call this URL (from `NEXT_PUBLIC_API_URL`) and display status or an error message if unreachable.


### Input Validation

- All string fields: min_length=1, max_length=1000
- Numeric fields: appropriate min/max bounds
- Required fields validated; missing returns 422
- Unknown fields rejected (Pydantic extra="forbid" where applicable)

## Data Model

N/A (frontend only; no new persisted entities).

## Files to Create/Modify

- `web/` — new Next.js app
- `web/app/page.tsx` — landing
- `web/app/api-health/page.tsx` — health check display
- `web/.env.example` — NEXT_PUBLIC_API_URL
- `README.md` — update Quick Start for web

## Acceptance Tests

- `cd web && npm run build` succeeds
- `/` renders without error
- `/api-health` shows API status when API is running

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


## Out of Scope

- Full dashboard (Sprint 2)
- Auth, user management
- Graph visualization

## See also

- [001-health-check.md](001-health-check.md) — API health consumed by /api-health
- [014-deploy-readiness.md](014-deploy-readiness.md) — deploy checklist for web

## Decision Gates

- npm/pnpm choice: use npm by default (matches Node.js ecosystem)

## Known Gaps and Follow-up Tasks

- No known gaps at time of writing.
- Follow-up: review after initial implementation for completeness.
