# Spec 077: Public Search E2E (API + Web)

## Goal
Make the public, human-visible search flow actually work end-to-end:
- `/` search form submits to `/search?q=...`
- `/search?q=...` renders results server-side (machine- and human-verifiable)
- API provides the endpoints the web calls (`/api/search`, `/api/projects/...`, `/coherence`)

This closes a critical gap where the web UI existed but the backing API routes returned 404 in production.

## Requirements
- [ ] API implements:
  - [ ] `GET /api/search?q={query}&limit={n}` → `{ results: ProjectSummary[], total: number }`
  - [ ] `GET /api/projects/{ecosystem}/{name}` → `Project` (404 with `{ "detail": "Project not found" }`)
  - [ ] `GET /api/projects/{ecosystem}/{name}/coherence` → `CoherenceResponse` (404 same detail)
- [ ] Web implements:
  - [ ] `/search` accepts `q` via query string and renders results server-side (no JS required to see results count)
- [ ] Runtime drift allowlist updated:
  - [ ] Remove `/api/search?q=` and `/api/projects/` from `docs/system_audit/runtime_drift_allowlist.json` once routes exist

## Design Notes
- Results may be empty in production if indexing/ingestion is sparse; this is acceptable as long as:
  - endpoints exist
  - response contracts hold
  - the web renders a clear "0 results" state for a query

## Files To Modify (Allowed)
- `api/app/routers/projects.py`
- `api/app/main.py`
- `api/app/services/coherence_service.py`
- `api/tests/test_projects_api.py`
- `web/app/search/page.tsx`
- `docs/system_audit/runtime_surface_audit_2026-02-14.json`
- `docs/system_audit/runtime_drift_allowlist.json`
- `specs/077-public-search-e2e.md`
- `docs/system_audit/commit_evidence_2026-02-16_public-search-e2e.json`

## Local Validation
```bash
cd api && pytest -v --ignore=tests/holdout -k 'projects_api'
cd web && npm ci --cache ./tmp-npm-cache --no-fund --no-audit --prefer-offline && npm run build
python3 scripts/validate_commit_evidence.py --file docs/system_audit/commit_evidence_2026-02-16_public-search-e2e.json
```

## Public Validation (Deployment Gate)
After merge + deploy:
```bash
# API contract exists (no 404)
curl -sS "https://coherence-network-production.up.railway.app/api/search?q=react" | python3 -c 'import json,sys; j=json.load(sys.stdin); print(\"keys\",sorted(j.keys()))'

# Web renders query state server-side (inspectable HTML)
curl -sS "https://coherence-network.vercel.app/search?q=react" | rg -n "Search projects|result"
```
