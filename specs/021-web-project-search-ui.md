# Spec: Web Project Detail Page and Search UI

## Purpose

Per docs/PLAN.md Sprint 2: `/project/npm/react` shows score; search UI. Add search page and project detail page to the Next.js web app so users can search packages and view project info with coherence scores.

## Requirements

- [x] Page `/search` with search input; fetches GET /api/search?q={query}; displays results as links to /project/{eco}/{name}
- [x] Page `/project/[ecosystem]/[name]` fetches GET /api/projects/{eco}/{name} and GET /api/projects/{eco}/{name}/coherence; displays project info and coherence score
- [x] Uses NEXT_PUBLIC_API_URL for API base
- [x] Real API calls (no mocks)
- [x] Landing page links to /search


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: none

## Task Card

```yaml
goal: Per docs/PLAN.
files_allowed:
  - web/app/search/page.tsx
  - web/app/project/[ecosystem]/[name]/page.tsx
  - web/app/page.tsx
  - web/components/ui/input.tsx
done_when:
  - Page `/search` with search input; fetches GET /api/search?q={query}; displays results as links to /project/{eco}/{name}
  - Page `/project/[ecosystem]/[name]` fetches GET /api/projects/{eco}/{name} and GET /api/projects/{eco}/{name}/coherenc...
  - Uses NEXT_PUBLIC_API_URL for API base
  - Real API calls (no mocks)
  - Landing page links to /search
commands:
  - cd api && python -m pytest tests/ -q
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

## API Contract

Consumes existing API:
- GET /api/search?q={query} → { results: ProjectSummary[], total: number }
- GET /api/projects/{ecosystem}/{name} → Project
- GET /api/projects/{ecosystem}/{name}/coherence → CoherenceResponse


### Input Validation

- All string fields: min_length=1, max_length=1000
- Numeric fields: appropriate min/max bounds
- Required fields validated; missing returns 422
- Unknown fields rejected (Pydantic extra="forbid" where applicable)

## Files to Create/Modify

- `web/app/search/page.tsx` — search page with input and results
- `web/app/project/[ecosystem]/[name]/page.tsx` — project detail page with coherence
- `web/app/page.tsx` — add link to /search
- `web/components/ui/input.tsx` — search input (shadcn or minimal)

## Acceptance Tests

- `cd web && npm run build` succeeds
- /search renders; search input works; results link to /project
- /project/npm/react renders project info and coherence when API has data

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

- Auth, user management
- Graph visualization
- PyPI (npm only for MVP)

## Known Gaps and Follow-up Tasks

- No known gaps at time of writing.
- Follow-up: review after initial implementation for completeness.
