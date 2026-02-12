# Spec: Health Check Endpoint

## Purpose

Provide a simple health endpoint so we can verify the API is running and validate the spec→test→impl pipeline.

## Requirements

- [x] GET /api/health returns 200
- [x] Response includes status, version, timestamp (ISO8601 UTC)
- [x] Response is valid JSON
- [x] Response contains only the specified top-level keys (no extra required fields)

## API Contract

### `GET /api/health`

**Request**

- No parameters.

**Response 200**

```json
{
  "status": "ok",
  "version": "0.1.0",
  "timestamp": "2026-02-12T00:00:00Z"
}
```

- `status`: string, value `"ok"`
- `version`: string, semantic version (e.g. `0.1.0`)
- `timestamp`: string, ISO8601 UTC (e.g. `YYYY-MM-DDTHH:MM:SSZ`)

## Data Model

None — stateless endpoint.

## Files to Create/Modify

- `api/app/main.py` — FastAPI app, mount router
- `api/app/routers/health.py` — route handler
- `api/tests/test_health.py` — acceptance tests

## Acceptance Tests

See `api/tests/test_health.py`. All of the following must pass for this spec:

- **GET /api/health returns 200** — `test_health_returns_200`
- **Response is valid JSON with required fields** — `test_health_returns_valid_json` (status, version, timestamp; timestamp ISO8601)
- **Response has exactly the required keys** — `test_health_response_schema` (no extra top-level keys)

## Out of Scope

- Database connectivity check
- Dependency health
- Metrics
- Readiness (/api/ready) and version (/api/version) — see [014-deploy-readiness.md](014-deploy-readiness.md)

## See also

- [014-deploy-readiness.md](014-deploy-readiness.md) — health probes for deploy
- [007-sprint-0-landing.md](007-sprint-0-landing.md) — root includes health URL

## Decision Gates

None.
