# Spec: OSS Interface Alignment

## Purpose

Ensure every public-facing web page in the Coherence Network dashboard displays real API data instead of placeholder or stub text. A user visiting any page should see live metrics, not "coming soon" copy. This spec documents the audit findings, codifies the data-integrity invariant, and defines the guard-rails that prevent regressions.

## Audit Summary

All seven routed pages were audited for data source (real API vs static/placeholder). The audit examined fetch calls, API URLs, fallback copy, and server/client component patterns.

| Page | File | Data Source | API Endpoints | Fallback Behavior |
|------|------|-------------|---------------|-------------------|
| `/` (Home) | `web/app/page.tsx` | Real API | `GET /api/ideas`, `GET /api/inventory/system-lineage`, `GET /api/runtime/ideas/summary` | Graceful: "The network is warming up..." when summary is null |
| `/ideas` | `web/app/ideas/page.tsx` | Real API | `GET /api/ideas` | Throws on API failure (no placeholder) |
| `/specs` | `web/app/specs/page.tsx` | Real API | `GET /api/inventory/system-lineage`, `GET /api/spec-registry`, `GET /api/inventory/flow` | "No data available yet..." when empty |
| `/usage` | `web/app/usage/page.tsx` | Real API | `GET /api/runtime/...`, `GET /api/daily-summary`, `GET /api/views/performance`, `GET /api/providers/stats` | Per-section "No data available"; warnings for unavailable APIs |
| `/automation` | `web/app/automation/page.tsx` | Real API | `GET /api/automation/usage`, alerts, readiness, provider-validation, `GET /api/providers/stats`, `GET /api/federation/nodes/stats` | Throws on primary failures; optional sections null-gated |
| `/flow` | `web/app/flow/page.tsx` | Real API | `GET /api/inventory/flow`, `GET /api/contributors`, `GET /api/contributions`, `GET /api/providers/stats` | Default empty response on failure; "No data available yet..." |
| `/contribute` | `web/app/contribute/page.tsx` | Real API (client) | `GET /api/contributors`, `GET /api/ideas`, `GET /api/spec-registry`, `GET /api/governance/change-requests`, plus POST endpoints | Loading/error UI states |

**Result: 7/7 pages fetch real API data. Zero pages display hardcoded stub content.**

## Requirements

- [ ] R1: Every page listed in the audit table must fetch its data exclusively from the live API (no hardcoded mock arrays or lorem-ipsum text).
- [ ] R2: Fallback messages shown when the API is unreachable must be clearly distinguishable from real data (e.g. styled as info/warning banners, not formatted like normal content).
- [ ] R3: A Playwright or Vitest integration test must assert that each page, when the API returns valid data, renders at least one dynamic value from the response (not only static labels).
- [ ] R4: No page may introduce new static placeholder content without an accompanying `data-placeholder` attribute so automated scans can detect it.
- [ ] R5: The `web/lib/api.ts` `getApiBase()` function must remain the single source of truth for API URL resolution across all pages.

## Research Inputs (Required)

- `2026-03-21` - Manual codebase audit of `web/app/*/page.tsx` files — confirmed all seven routes fetch from API endpoints via `getApiBase()` and `fetchJsonOrNull()`.
- `2026-03-21` - Review of `web/lib/api.ts` and `web/lib/fetch.ts` — verified centralized fetch wrapper with retry, timeout, and error handling.

## Task Card (Required)

```yaml
goal: Guarantee all web pages display live API data and add regression tests
files_allowed:
  - web/app/page.tsx
  - web/app/ideas/page.tsx
  - web/app/specs/page.tsx
  - web/app/usage/page.tsx
  - web/app/automation/page.tsx
  - web/app/flow/page.tsx
  - web/app/contribute/page.tsx
  - web/lib/api.ts
  - web/lib/fetch.ts
  - web/tests/integration/page-data-source.test.ts
done_when:
  - All 7 pages confirmed fetching real API data (audit table green)
  - Integration test file exists and passes for each page
  - No hardcoded mock data arrays in any page component
  - Fallback messages use data-placeholder attribute
commands:
  - cd web && npx vitest run tests/integration/page-data-source.test.ts
  - cd web && npm run build
constraints:
  - Do not remove existing fallback UX — only annotate it
  - Do not change API endpoint contracts
```

## API Contract

N/A - no API contract changes in this spec. All endpoints already exist and serve real data.

## Data Model (if applicable)

N/A - no model changes in this spec.

## Files to Create/Modify

- `web/tests/integration/page-data-source.test.ts` — new integration test asserting each page renders API data
- `web/app/page.tsx` — add `data-placeholder` attribute to fallback banners
- `web/app/specs/page.tsx` — add `data-placeholder` attribute to empty-state messages
- `web/app/usage/page.tsx` — add `data-placeholder` attribute to "No data available" sections
- `web/app/flow/page.tsx` — add `data-placeholder` attribute to empty-state messages
- `web/app/contribute/page.tsx` — add `data-placeholder` attribute to loading/error states

## Acceptance Tests

- `web/tests/integration/page-data-source.test.ts::each page renders dynamic API content`
- `web/tests/integration/page-data-source.test.ts::fallback messages carry data-placeholder attribute`
- `web/tests/integration/page-data-source.test.ts::no page contains hardcoded mock data arrays`
- Manual: `cd web && npm run build` completes without errors

## Concurrency Behavior

- **Read operations**: All pages are read-only views of API data; safe for concurrent access.
- **Write operations**: Only `/contribute` performs writes (POST). Uses standard HTTP semantics; no client-side locking needed.
- **Recommendation**: Server-side revalidation intervals (60-90s) naturally throttle concurrent fetch storms.

## Verification

```bash
cd web && npx vitest run tests/integration/page-data-source.test.ts
cd web && npm run build
# Grep for any remaining hardcoded mock arrays
grep -rn "mockData\|placeholder.*=.*\[" web/app/*/page.tsx || echo "No mock data found"
```

## Out of Scope

- Changing API endpoint contracts or response shapes
- Adding new API endpoints
- Redesigning fallback UX (only annotating existing fallbacks)
- Performance optimization of API calls
- Mobile responsiveness auditing

## Risks and Assumptions

- **Risk**: Integration tests may be flaky if the dev API is unavailable during CI. **Mitigation**: Tests should mock at the HTTP layer (e.g. MSW) rather than requiring a live API.
- **Assumption**: The seven routes listed are the complete set of public pages. If new pages are added, this spec's test suite must be extended.
- **Assumption**: `fetchJsonOrNull()` and `getApiBase()` remain the canonical fetch utilities. A refactor of these would require updating the test strategy.

## Known Gaps and Follow-up Tasks

- The `/ideas` page throws on API failure instead of showing a graceful fallback — this is a UX gap but out of scope for this spec. Follow-up task: `task_ideas_error_boundary`.
- No end-to-end Playwright tests yet; the integration tests here use Vitest with mocked HTTP. Full E2E is a separate effort.

## Failure/Retry Reflection

- Failure mode: Integration test fails because a page component import pulls in server-only dependencies unavailable in the test environment.
- Blind spot: Next.js server components may not be directly testable with Vitest without additional configuration.
- Next action: Use HTTP-level mocking (MSW) and test rendered output via `@testing-library/react` or switch to Playwright for true browser-based tests.

## Decision Gates (if any)

- Decide whether `data-placeholder` annotation should be a project-wide lint rule (enforced in CI) or advisory only.
