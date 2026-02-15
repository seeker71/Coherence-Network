# Spec 068: Contributor, Contribution, Asset, and Task Web Surfaces

## Purpose

Ensure core operational entities are accessible through human web pages, not only machine APIs.

## Requirements

1. Expose agent task APIs in the running app by mounting the agent router.
2. Add web pages:
   - `/tasks` for `/api/agent/tasks`
   - `/contributors` for `/v1/contributors`
   - `/assets` for `/v1/assets`
   - `/contributions` for contribution attribution via `/api/inventory/system-lineage`
3. Update home navigation to link to these pages.
4. Keep page lineage ontology complete (`missing_pages = 0`) for the expanded page set.
5. Improve API/web gap scan path matching to include `/v1/*` usage paths.

## Validation

- `cd api && .venv/bin/pytest -v tests/test_inventory_api.py tests/test_runtime_api.py`
- `cd web && npm run build`
- `POST /api/inventory/availability/scan` reflects updated parity.
