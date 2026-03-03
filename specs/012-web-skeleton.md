# Spec: Web Skeleton

## Purpose

Deliver a minimal Next.js 15 app with a root route (`/`) and an `/api-health` check page so the Coherence web front is runnable and can verify backend connectivity. Supports Sprint 0 "landing live" (docs/PLAN.md). Stack: Next.js 15 + shadcn/ui.

## Requirements

- [ ] Next.js 15 app in `web/` directory
- [ ] Page `/` (root) renders without error; shows project name and link to API docs
- [ ] Page `/api-health` exists and displays API health status (fetches backend health endpoint)
- [ ] shadcn/ui installed with minimal components (e.g. Button)
- [ ] API base URL configurable via `NEXT_PUBLIC_API_URL`

## API Contract (consumed by web)

Web consumes the existing API health endpoint (see [001-health-check.md](001-health-check.md)).

### `GET /api/health` (backend)

**Response 200**
```json
{ "status": "ok" }
```

The `/api-health` page MUST call this URL (from `NEXT_PUBLIC_API_URL`) and display status or an error message if unreachable.

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

## Out of Scope

- Full dashboard (Sprint 2)
- Auth, user management
- Graph visualization

## See also

- [001-health-check.md](001-health-check.md) — API health consumed by /api-health
- [014-deploy-readiness.md](014-deploy-readiness.md) — deploy checklist for web

## Decision Gates

- npm/pnpm choice: use npm by default (matches Node.js ecosystem)
