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

## API Contract

Consumes existing API:
- POST /api/import/stack with multipart file → ImportStackResponse

## Files to Create/Modify

- `web/app/import/page.tsx` — import page with file upload and results
- `web/app/page.tsx` — add link to /import

## Acceptance Tests

- `cd web && npm run build` succeeds
- /import renders; file upload works; results display after submit

## Out of Scope

- requirements.txt (PyPI) — future
- Drag-and-drop zone
- Export results
