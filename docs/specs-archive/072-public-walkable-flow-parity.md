# Spec 072: Fully Public Walkable Flow (API/Web Parity)

## Purpose
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
   - `/contributors` (reads `GET /v1/contributors`)
   - `/contributions` (reads `GET /v1/contributions`)
   - `/assets` (reads `GET /v1/assets`)
   - `/tasks` (reads `GET /api/agent/tasks`)
5. Add navigation links from `/portfolio` to those pages.


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: none

## Task Card

```yaml
goal: Implement the functionality described in this spec
files_allowed:
  - # TBD — determine from implementation
done_when:
  - Add `GET /api/value-lineage/links` to list lineage links (read-only, sorted newest-first).
  - Add `GET /api/inventory/page-lineage` to return a public mapping of web pages to `idea_id`.
  - Ensure `/api/inventory/system-lineage` spec inventory:
  - Add public pages:
  - Add navigation links from `/portfolio` to those pages.
commands:
  - python3 -m pytest api/tests/test_runtime_drift_check.py -x -v
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

## Files to Create/Modify
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
  - `GET https://coherencycoin.com/portfolio` and links to the new pages return 200

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

See `api/tests/test_public_walkable_flow_parity.py` for test cases covering this spec's requirements.


## Verification

```bash
python3 -m pytest api/tests/test_runtime_drift_check.py -x -v
cd api && /opt/homebrew/bin/python3.11 -m pytest -q tests/test_value_lineage.py tests/test_inventory_api.py
cd web && npm run build
```

## Out of Scope

- Editing contributor/contribution/asset/task records from the public web surface.
- Adding authenticated admin-only controls to the public walkable flow.

## Known Gaps and Follow-up Tasks

- No known gaps at time of writing.
- Follow-up: review after initial implementation for completeness.
