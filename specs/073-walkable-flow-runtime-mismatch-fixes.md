# Spec 073: Walkable Flow Runtime Mismatch Fixes

## Goal
Fix public walkability mismatches discovered post-deploy:
- tasks UI requires `/api/agent/tasks` but agent router is not exposed publicly
- contributors/assets web pages assumed object-wrapped responses, but API returns arrays
- contributions web page requires a list endpoint, but API only supports POST

## Requirements
### API
1. Expose agent router under `/api` so `GET /api/agent/tasks` is publicly available.
2. Add `GET /v1/contributions` to list contributions (read-only).
3. Ensure stores implement listing contributions (in-memory + postgres).

### Web
4. Update `/contributors`, `/assets` to accept array responses from `/v1/*`.
5. Update `/contributions` to use the new `GET /v1/contributions`.

## Implementation (Allowed Files)
- `api/app/main.py`
- `api/app/routers/contributions.py`
- `api/app/adapters/graph_store.py`
- `api/app/adapters/postgres_store.py`
- `api/tests/test_contributions.py`
- `web/app/contributors/page.tsx`
- `web/app/assets/page.tsx`
- `web/app/contributions/page.tsx`
- `docs/system_audit/commit_evidence_2026-02-15_walkable-flow-runtime-mismatch-fixes.json`

## Validation
- `cd api && /opt/homebrew/bin/python3.11 -m pytest -q tests/test_contributions.py`
- `cd web && npm ci --cache ./tmp-npm-cache --no-fund --no-audit && npm run build`
- `python3 scripts/validate_commit_evidence.py --file docs/system_audit/commit_evidence_2026-02-15_walkable-flow-runtime-mismatch-fixes.json`
