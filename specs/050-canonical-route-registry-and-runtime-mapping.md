# Spec: Canonical Route Registry and Runtime Mapping

## Purpose

Define and expose a canonical route set for current milestone work, and ensure runtime telemetry maps to idea IDs by default so attribution is actionable.

## Requirements

- [ ] API exposes canonical route registry for machine/human tooling.
- [ ] Runtime mapping defaults avoid `unmapped` for standard API (`/api`, `/v1`) and web (`/`) surfaces.
- [ ] Tests validate canonical route endpoint and default mapping behavior.


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: none

## Task Card

```yaml
goal: Define and expose a canonical route set for current milestone work, and ensure runtime telemetry maps to idea IDs by default so attribution is actionable.
files_allowed:
  - # TBD — determine from implementation
done_when:
  - API exposes canonical route registry for machine/human tooling.
  - Runtime mapping defaults avoid `unmapped` for standard API (`/api`, `/v1`) and web (`/`) surfaces.
  - Tests validate canonical route endpoint and default mapping behavior.
commands:
  - python3 -m pytest api/tests/test_runtime_api.py -x -v
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

## API Contract

### `GET /api/inventory/routes/canonical`

Returns canonical API/web routes with milestone metadata and idea linkage.


### Input Validation

- All string fields: min_length=1, max_length=1000
- Numeric fields: appropriate min/max bounds
- Required fields validated; missing returns 422
- Unknown fields rejected (Pydantic extra="forbid" where applicable)

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

## Concurrency Behavior

- **Read operations**: Safe for concurrent access; no locking required.
- **Write operations**: Last-write-wins semantics; no optimistic locking for MVP.
- **Recommendation**: Clients should not assume atomic read-modify-write without explicit ETag support.

## Failure and Retry Behavior

- **Invalid input**: Return 422 with field-level validation errors.
- **Resource not found**: Return 404 with descriptive message.
- **Database unavailable**: Return 503; client should retry with exponential backoff (initial 1s, max 30s).
- **Concurrent modification**: Last write wins; no optimistic locking required for MVP.
- **Timeout**: Operations exceeding 30s return 504; safe to retry.

## Risks and Known Gaps

- **No auth gate**: Endpoints unprotected until C1 auth middleware applied.
- **No rate limiting**: Subject to abuse until M1 rate limiter active.
- **Single-node only**: No distributed locking; concurrent access may race.
- **Follow-up**: Add integration tests for error edge cases.

## Acceptance Tests

See `api/tests/test_canonical_route_registry_and_runtime_mapping.py` for test cases covering this spec's requirements.


## Verification

```bash
python3 -m pytest api/tests/test_runtime_api.py -x -v
```

## Known Gaps and Follow-up Tasks

- No known gaps at time of writing.
- Follow-up: review after initial implementation for completeness.
