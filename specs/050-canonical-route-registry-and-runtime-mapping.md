# Spec: Canonical Route Registry and Runtime Mapping

## Purpose

Define and expose a canonical route set for current milestone work, and ensure runtime telemetry maps to idea IDs by default so attribution is actionable.

## Requirements

- [ ] API exposes canonical route registry for machine/human tooling.
- [ ] Runtime mapping defaults avoid `unmapped` for standard API (`/api`, `/v1`) and web (`/`) surfaces.
- [ ] Tests validate canonical route endpoint and default mapping behavior.

## API Contract

### `GET /api/inventory/routes/canonical`

Returns canonical API/web routes with milestone metadata and idea linkage.

## Validation Contract

- `api/tests/test_inventory_api.py::test_canonical_routes_inventory_endpoint_returns_registry`
- `api/tests/test_runtime_api.py::test_runtime_default_mapping_avoids_unmapped_for_known_surfaces`

## Files

- `config/canonical_routes.json`
- `api/app/services/route_registry_service.py`
- `api/app/routers/inventory.py`
- `api/app/services/runtime_service.py`
- `api/tests/test_inventory_api.py`
- `api/tests/test_runtime_api.py`

