# Spec: Web Project Detail Page and Search UI

## Purpose

Per docs/PLAN.md Sprint 2: `/project/npm/react` shows score; search UI. Add search page and project detail page to the Next.js web app so users can search packages and view project info with coherence scores.

## Requirements

- [x] Page `/search` with search input; fetches GET /api/search?q={query}; displays results as links to /project/{eco}/{name}
- [x] Page `/project/[ecosystem]/[name]` fetches GET /api/projects/{eco}/{name} and GET /api/projects/{eco}/{name}/coherence; displays project info and coherence score
- [x] Uses NEXT_PUBLIC_API_URL for API base
- [x] Real API calls (no mocks)
- [x] Landing page links to /search

## API Contract

Consumes existing API:
- GET /api/search?q={query} → { results: ProjectSummary[], total: number }
- GET /api/projects/{ecosystem}/{name} → Project
- GET /api/projects/{ecosystem}/{name}/coherence → CoherenceResponse

## Files to Create/Modify

- `web/app/search/page.tsx` — search page with input and results
- `web/app/project/[ecosystem]/[name]/page.tsx` — project detail page with coherence
- `web/app/page.tsx` — add link to /search
- `web/components/ui/input.tsx` — search input (shadcn or minimal)

## Acceptance Tests

- `cd web && npm run build` succeeds
- /search renders; search input works; results link to /project
- /project/npm/react renders project info and coherence when API has data

## Out of Scope

- Auth, user management
- Graph visualization
- PyPI (npm only for MVP)
