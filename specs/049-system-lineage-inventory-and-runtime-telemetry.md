# Spec: System Lineage Inventory and Runtime Telemetry

## Purpose

Provide one API to inspect all core planning/execution artifacts (questions, ideas, specs, implementation usage) and add real-time runtime telemetry linked to ideas so cost/value can be measured continuously across API and web surfaces.

## Requirements

- [ ] API exposes a unified inventory endpoint for questions, ideas, specs, and implementation usage.
- [ ] API records runtime telemetry for API endpoints automatically.
- [ ] API accepts runtime telemetry events from web clients/routes.
- [ ] Runtime telemetry links each event to an idea id (explicitly or via endpoint mapping).
- [ ] API exposes runtime summaries by idea (event count, runtime totals, estimated runtime cost).
- [ ] Inventory endpoint includes answered vs unanswered question inventory.

## API Contract

### `GET /api/inventory/system-lineage`

Returns a machine-readable inventory of:
- idea portfolio and question status
- discovered specs from `specs/`
- value-lineage implementation usage
- runtime telemetry summary by idea

### `POST /api/runtime/events`

Ingest a runtime event (typically web-side beacon).

**Request**
```json
{
  "source": "web",
  "endpoint": "/gates",
  "method": "GET",
  "status_code": 200,
  "runtime_ms": 82.5,
  "idea_id": "oss-interface-alignment"
}
```

### `GET /api/runtime/events?limit=100`

List recent runtime events.

### `GET /api/runtime/ideas/summary?seconds=3600`

Return per-idea runtime aggregates for recent events.

## Validation Contract

- Tests cover unified inventory endpoint structure and non-empty ideas/specs.
- Tests cover runtime event ingestion and runtime-by-idea aggregation.
- Tests verify automatic API runtime capture records events for API requests.

## Files to Create/Modify

- `api/app/models/runtime.py`
- `api/app/services/runtime_service.py`
- `api/app/services/inventory_service.py`
- `api/app/routers/runtime.py`
- `api/app/routers/inventory.py`
- `api/app/main.py`
- `api/tests/test_runtime_api.py`
- `api/tests/test_inventory_api.py`
- `web/app/api/runtime-beacon/route.ts`
- `web/components/runtime-beacon.tsx`
- `web/app/layout.tsx`

