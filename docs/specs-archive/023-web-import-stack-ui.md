# Spec: Web UI for Import Stack

## Purpose

Per docs/STATUS.md next priority: Web UI for import stack. Allow users to upload package-lock.json from the web app and see risk analysis results. Builds on spec 022 (POST /api/import/stack).

## Requirements

- [x] Page `/import` with file input for package-lock.json
- [x] On submit: POST to API, display packages and risk_summary
- [x] Show packages list with name, version, coherence, status
- [x] Show risk_summary (unknown, low, medium, high counts)
- [x] Uses NEXT_PUBLIC_API_URL for API base
- [x] Real API calls (no mocks)


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: none

## Task Card

```yaml
goal: Per docs/STATUS.
files_allowed:
  - web/app/import/page.tsx
  - web/app/page.tsx
done_when:
  - Page `/import` with file input for package-lock.json
  - On submit: POST to API, display packages and risk_summary
  - Show packages list with name, version, coherence, status
  - Show risk_summary (unknown, low, medium, high counts)
  - Uses NEXT_PUBLIC_API_URL for API base
commands:
  - cd api && python -m pytest tests/ -q
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

## API Contract

Consumes existing API:
- POST /api/import/stack with multipart file → ImportStackResponse


### Input Validation

- All string fields: min_length=1, max_length=1000
- Numeric fields: appropriate min/max bounds
- Required fields validated; missing returns 422
- Unknown fields rejected (Pydantic extra="forbid" where applicable)

## Files to Create/Modify

- `web/app/import/page.tsx` — import page with file upload and results
- `web/app/page.tsx` — add link to /import

## Acceptance Tests

- `cd web && npm run build` succeeds
- /import renders; file upload works; results display after submit

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

- requirements.txt (PyPI) — future
- Drag-and-drop zone
- Export results

## Known Gaps and Follow-up Tasks

- No known gaps at time of writing.
- Follow-up: review after initial implementation for completeness.
