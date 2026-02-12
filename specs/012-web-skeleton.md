# Spec: Web Skeleton

## Purpose

Create minimal Next.js 16 app with landing page and API health check for Sprint 0 "landing live". Per docs/PLAN.md: Next.js 16 + shadcn/ui.

## Requirements

- [x] Next.js 15 app in `web/` directory
- [x] Page `/` shows project name and link to API docs
- [x] Page `/api-health` fetches GET /api/health from API and displays status
- [x] shadcn/ui installed (minimal components: Button)
- [x] API base URL configurable (NEXT_PUBLIC_API_URL)

## API Contract

N/A — web app consumes existing API.

## Data Model

N/A.

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
