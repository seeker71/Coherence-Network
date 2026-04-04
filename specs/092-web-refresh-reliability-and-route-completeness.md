# Spec 092 — Web Refresh Reliability and Route Completeness

## Goal

Ensure all key web pages remain reachable via visible navigation and reliably refresh when data or deployed web version changes.

## Problem

- Some pages were not discoverable from shared navigation surfaces.
- Live refresh could miss a deployment update before first version baseline capture.
- Several interactive page fetches still used default cache behavior, which could present stale data.

## Scope

- Improve global navigation and page-context links so `/friction`, `/import`, and `/api-health` are consistently reachable.
- Harden `LiveUpdatesController` so it:
  - runs an immediate refresh tick on mount/focus/visibility return,
  - captures version baseline immediately,
  - reloads on detected web version change.
- Ensure remaining interactive `fetch` calls use `cache: "no-store"`.

## Out of Scope

- Replacing polling with server push (SSE/WebSocket).
- Redesigning page content structure beyond route discoverability and freshness.

## Acceptance Criteria

1. `web/components/live_updates_controller.tsx` performs an immediate run on mount and on focus/visibility regain.
2. Version checks initialize baseline immediately and trigger reload when `web.updated_at` changes.
3. Global navigation includes direct links to `/friction`, `/import`, and `/api-health`.
4. Context-link band includes those same routes and dynamic route contexts for idea/project pages.
5. `web/app/friction/page.tsx`, `web/app/gates/page.tsx`, `web/app/search/page.tsx`, and `web/app/project/[ecosystem]/[name]/page.tsx` use `cache: "no-store"` for data reads.
6. `cd web && npm run build` passes.


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: none

## Task Card

```yaml
goal: Implement the functionality described in this spec
files_allowed:
  - # TBD — determine from implementation
done_when:
  - `web/components/live_updates_controller.tsx` performs an immediate run on mount and on focus/visibility regain.
  - Version checks initialize baseline immediately and trigger reload when `web.updated_at` changes.
  - Global navigation includes direct links to `/friction`, `/import`, and `/api-health`.
  - Context-link band includes those same routes and dynamic route contexts for idea/project pages.
  - `web/app/friction/page.tsx`, `web/app/gates/page.tsx`, `web/app/search/page.tsx`, and `web/app/project/[ecosystem]/[n...
commands:
  - - `cd web && npm run build`
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

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

## Acceptance Tests

See `api/tests/test_web_refresh_reliability_and_route_completeness.py` for test cases covering this spec's requirements.


## Verification

- Local:
  - `cd web && npm run build`
- Manual:
  - Open `/`, `/usage`, `/friction`, `/gates`.
  - Confirm live-update bar refreshes quickly after tab focus.
  - Confirm context/nav links expose all key pages including `/friction`, `/import`, `/api-health`.

## Known Gaps and Follow-up Tasks

- No known gaps at time of writing.
- Follow-up: review after initial implementation for completeness.
