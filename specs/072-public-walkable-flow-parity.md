# Spec 072: Fully Public Walkable Flow (API/Web Parity)

## Goal
Provide a fully public, verifiable flow that lets a human or machine start at the system portfolio and walk to:
ideas -> specs -> processes/routes -> implementations -> contributors/contributions/assets/tasks -> runtime usage/value usage.

## Requirements
### API
1. Add `GET /api/value-lineage/links` to list lineage links (read-only, sorted newest-first).
2. Add `GET /api/inventory/page-lineage` to return a public mapping of web pages to `idea_id`.
3. Ensure `/api/inventory/system-lineage` spec inventory:
   - enumerates all `specs/*.md`
   - returns `path` as repo-relative (e.g. `specs/049-...md`), never absolute server paths.

### Web
4. Add public pages:
   - `/contributors` (reads `GET /api/contributors`)
   - `/contributions` (reads `GET /api/contributions`)
   - `/assets` (reads `GET /api/assets`)
   - `/tasks` (reads `GET /api/agent/tasks`)
5. Add navigation links from `/portfolio` to those pages.

## Implementation (Allowed Files)
- `api/app/models/value_lineage.py`
- `api/app/routers/value_lineage.py`
- `api/app/routers/inventory.py`
- `api/app/services/inventory_service.py`
- `api/app/services/page_lineage_service.py` (new)
- `config/page_lineage.json` (new)
- `api/tests/test_value_lineage.py`
- `api/tests/test_inventory_api.py`
- `web/app/portfolio/page.tsx`
- `web/app/contributors/page.tsx` (new)
- `web/app/contributions/page.tsx` (new)
- `web/app/assets/page.tsx` (new)
- `web/app/tasks/page.tsx` (new)

## Validation
- `cd api && /opt/homebrew/bin/python3.11 -m pytest -q tests/test_value_lineage.py tests/test_inventory_api.py`
- `cd web && npm run build`
- Public smoke (post-deploy):
  - `GET https://coherence-network-production.up.railway.app/api/inventory/system-lineage`
  - `GET https://coherence-network-production.up.railway.app/api/inventory/page-lineage`
  - `GET https://coherence-network-production.up.railway.app/api/value-lineage/links`
  - `GET https://coherence-network.vercel.app/portfolio` and links to the new pages return 200
