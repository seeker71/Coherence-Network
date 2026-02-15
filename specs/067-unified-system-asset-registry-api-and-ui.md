# Spec 067: Unified System Asset Registry API and UI

## Purpose

Treat all system parts as tracked assets and expose them through both machine API and human web interface.

## Requirements

1. `GET /api/inventory/system-lineage` includes an `assets` section with:
   - total assets
   - counts by type
   - coverage metrics for API/Web surface
   - asset items with machine and human access paths
2. Add `GET /api/inventory/assets` with optional filters:
   - `asset_type`
   - `limit`
3. `/portfolio` must show a System Asset Registry section with:
   - asset totals and coverage
   - asset type breakdown
   - browseable list of registered assets and access paths
4. Tests verify:
   - assets section is present in system-lineage
   - assets endpoint returns items and filter behavior

## Validation

- `cd api && .venv/bin/pytest -v tests/test_inventory_api.py`
- `cd web && npm run build`
