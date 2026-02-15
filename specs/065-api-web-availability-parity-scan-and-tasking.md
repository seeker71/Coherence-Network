# Spec 065: API-Web Availability Parity Scan and Tasking

## Purpose

Prevent machine-only API surfaces by continuously scanning declared API endpoints against web UI usage and creating a tracked task for every gap.

## Requirements

1. `GET /api/inventory/system-lineage` includes `availability_gaps` with:
   - principle statement
   - explanation of why this was previously missed
   - API route total
   - web API usage path total
   - count/list of API endpoints not used by web UI
2. Add endpoint:
   - `POST /api/inventory/availability/scan?create_tasks=true|false`
3. When `create_tasks=true`, create (or dedupe) one task per API/web availability gap.
4. Gap scan must operate from repository source of truth:
   - API route declarations in `api/app/routers/*.py`
   - web API usage paths in `web/**/*.ts|tsx|js|jsx`
5. Tests validate:
   - `availability_gaps` section exists
   - scan endpoint returns gap list
   - task generation count matches gap count when enabled

## Validation

- `cd api && .venv/bin/pytest -v tests/test_inventory_api.py`
