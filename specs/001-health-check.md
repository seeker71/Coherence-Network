# Spec: Health Check Endpoint

## Purpose

Provide a simple health endpoint so we can verify the API is running and validate the spec→test→impl pipeline.

## Requirements

- [x] GET /api/health returns 200
- [x] Response includes status, version, timestamp (ISO8601)
- [x] Response is valid JSON

## API Contract

### `GET /api/health`

**Response 200**
```json
{
  "status": "ok",
  "version": "0.1.0",
  "timestamp": "2026-02-12T00:00:00Z"
}
```

## Data Model

None — stateless endpoint.

## Files to Create/Modify

- `api/app/main.py` — FastAPI app, mount router
- `api/app/routers/health.py` — route handler
- `api/tests/test_health.py` — acceptance tests

## Acceptance Tests

See `api/tests/test_health.py`. All tests must pass.

## Out of Scope

- Database connectivity check
- Dependency health
- Metrics

## See also

- [014-deploy-readiness.md](014-deploy-readiness.md) — health probes for deploy

## Decision Gates

None.
