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

## Verification

- Local:
  - `cd web && npm run build`
- Manual:
  - Open `/`, `/usage`, `/friction`, `/gates`.
  - Confirm live-update bar refreshes quickly after tab focus.
  - Confirm context/nav links expose all key pages including `/friction`, `/import`, `/api-health`.
