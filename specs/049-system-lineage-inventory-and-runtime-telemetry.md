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


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: 115

## Task Card

```yaml
goal: Provide one API to inspect all core planning/execution artifacts (questions, ideas, specs, implementation usage) and add real-time runtime telemetry linked to ideas so cost/value can be measured continuously across API and web surfaces.
files_allowed:
  - api/app/models/runtime.py
  - api/app/services/runtime_service.py
  - api/app/services/inventory_service.py
  - api/app/routers/runtime.py
  - api/app/routers/inventory.py
  - api/app/main.py
  - api/tests/test_runtime_api.py
  - api/tests/test_inventory_api.py
  - web/app/api/runtime-beacon/route.ts
  - web/components/runtime-beacon.tsx
  - web/app/layout.tsx
done_when:
  - API exposes a unified inventory endpoint for questions, ideas, specs, and implementation usage.
  - API records runtime telemetry for API endpoints automatically.
  - API accepts runtime telemetry events from web clients/routes.
  - Runtime telemetry links each event to an idea id (explicitly or via endpoint mapping).
  - API exposes runtime summaries by idea (event count, runtime totals, estimated runtime cost).
commands:
  - python3 -m pytest api/tests/test_inventory_api.py -x -v
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

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


### Input Validation

- All string fields: min_length=1, max_length=1000
- Numeric fields: appropriate min/max bounds
- Required fields validated; missing returns 422
- Unknown fields rejected (Pydantic extra="forbid" where applicable)

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

## Downstream Consumers

- **Spec 115** ([115-grounded-cost-value-measurement.md](115-grounded-cost-value-measurement.md)) — Calls `runtime_service.summarize_by_idea(seconds=86400)` to collect usage adoption counts (API call count per idea) as an economic signal. Usage event count is normalized on a log scale (1 call = 0.1, 10 = 0.5, 100+ = 0.9+) and feeds into the grounded value formula as one of the strongest economic signals driving task-level ROI.

## Concurrency Behavior

- **Read operations**: Safe for concurrent access; no locking required.
- **Write operations**: Last-write-wins semantics; no optimistic locking for MVP.
- **Recommendation**: Clients should not assume atomic read-modify-write without explicit ETag support.

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

See `api/tests/test_system_lineage_inventory_and_runtime_telemetry.py` for test cases covering this spec's requirements.


## Verification

```bash
python3 -m pytest api/tests/test_inventory_api.py -x -v
```

## Known Gaps and Follow-up Tasks

- No known gaps at time of writing.
- Follow-up: review after initial implementation for completeness.
