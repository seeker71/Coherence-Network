# Spec: Health Check Endpoint

## Purpose

Provide a simple health endpoint so we can verify the API is running and validate the spec→test→impl pipeline. Enables load balancers and monitors to confirm the service is up without probing deeper dependencies.

## Requirements

- [x] GET /api/health returns 200
- [x] Response is valid JSON (Content-Type application/json; body parses as JSON)
- [x] Response includes required fields: status, version, timestamp
- [x] status is the string `"ok"`
- [x] version is a semantic-version-like string (MAJOR.MINOR.PATCH matching `\d+\.\d+\.\d+`)
- [x] timestamp is ISO8601 UTC (parseable; Z or +00:00)
- [x] Response contains exactly the specified top-level keys (no extra keys)
- [x] All response fields (status, version, timestamp) are strings


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: 007, 009, 014

## Task Card

```yaml
goal: Provide a simple health endpoint so we can verify the API is running and validate the spec→test→impl pipeline.
files_allowed:
  - api/app/main.py
  - api/app/routers/health.py
  - api/tests/test_health.py
done_when:
  - GET /api/health returns 200
  - Response is valid JSON (Content-Type application/json; body parses as JSON)
  - Response includes required fields: status, version, timestamp
  - status is the string `"ok"`
  - version is a semantic-version-like string (MAJOR.MINOR.PATCH matching `\d+\.\d+\.\d+`)
commands:
  - python3 -m pytest api/tests/test_health.py -x -v
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

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
- `version`: string, semantic version (e.g. `0.1.0`); MUST match pattern `\d+\.\d+\.\d+` (MAJOR.MINOR.PATCH)
- `timestamp`: string, ISO8601 UTC (e.g. `YYYY-MM-DDTHH:MM:SSZ` or equivalent with `+00:00`)

**Response 5xx**

Not defined by this spec. Unhandled server errors are covered by [009-api-error-handling.md](009-api-error-handling.md).


### Input Validation

- All string fields: min_length=1, max_length=1000
- Numeric fields: appropriate min/max bounds
- Required fields validated; missing returns 422
- Unknown fields rejected (Pydantic extra="forbid" where applicable)

## Data Model

None — stateless endpoint. Response shape is defined by the API contract above; implementation uses a Pydantic model with `extra="forbid"` to enforce exact keys.

## Files to Create/Modify

- `api/app/main.py` — FastAPI app, mount health router
- `api/app/routers/health.py` — route handler for GET /api/health; Pydantic response model with status, version, timestamp
- `api/tests/test_health.py` — acceptance tests for this spec (file also contains tests for 007, 009, 014)

## Acceptance Tests

See `api/tests/test_health.py`. The following tests define the contract for this spec; all must pass. Do not modify tests to make implementation pass; fix the implementation instead.

| Requirement | Test |
|-------------|------|
| GET /api/health returns 200 | `test_health_returns_200` |
| Response is valid JSON (Content-Type application/json; body parses as JSON) | `test_health_response_is_valid_json` |
| Response includes required fields (status, version, timestamp); status is "ok"; basic ISO8601 | `test_health_returns_valid_json` |
| timestamp is ISO8601 UTC (parseable; Z or +00:00) | `test_health_timestamp_iso8601_utc` |
| Response has exactly the required keys (no extra top-level keys) | `test_health_response_schema` |
| version is semantic-version format (`^\d+\.\d+\.\d+`) | `test_health_version_semver` |
| Response fields (status, version, timestamp) are strings | `test_health_response_value_types` |
| Full API contract (200, exact keys, status ok, semver, ISO8601 UTC) | `test_health_api_contract` |

**Verification:** Every requirement above has exactly one corresponding test (or is covered by the full-contract test). No requirement is untested. All listed tests exist in `api/tests/test_health.py`. Tests for root, /docs, /api/ready, CORS, and 500 handling live in the same file but belong to specs 007, 009, 014.

**Run 001-only tests:** `cd api && pytest tests/test_health.py -v -k 'health'`

**Verification checklist (all health items complete):**

1. All 8 requirements are checked [x].
2. Each requirement maps to a test in the table above.
3. Implementation: `api/app/routers/health.py` exposes GET /health with `HealthResponse` (extra="forbid"), returning status, version, timestamp.
4. Router is mounted at `/api` in `api/app/main.py` so endpoint is GET /api/health.
5. Contract test `test_spec_001_coverage_references_existing_tests` in `api/tests/test_update_spec_coverage.py` enforces that all 8 tests exist in `test_health.py` and are referenced in `docs/SPEC-COVERAGE.md`.

## Out of Scope

- Database connectivity check
- Dependency health
- Metrics
- Readiness (/api/ready) and version (/api/version) — see [014-deploy-readiness.md](014-deploy-readiness.md)

## Decision Gates

None.

## See also

- [014-deploy-readiness.md](014-deploy-readiness.md) — health probes for deploy
- [007-sprint-0-landing.md](007-sprint-0-landing.md) — root includes health URL
- [009-api-error-handling.md](009-api-error-handling.md) — 500 and error shapes

## Concurrency Behavior

- **Read operations**: Safe for concurrent access; no locking required.
- **Write operations**: Last-write-wins semantics; no optimistic locking for MVP.
- **Recommendation**: Clients should not assume atomic read-modify-write without explicit ETag support.

## Failure and Retry Behavior

- **Task failure**: Log error, mark task failed, advance to next item or pause for human review.
- **Retry logic**: Failed tasks retry up to 3 times with exponential backoff (initial 2s, max 60s).
- **Partial completion**: State persisted after each phase; resume from last checkpoint on restart.
- **External dependency down**: Pause pipeline, alert operator, resume when dependency recovers.
- **Timeout**: Individual task phases timeout after 300s; safe to retry from last phase.

## Risks and Assumptions

- **No auth gate**: Endpoints unprotected until C1 auth middleware applied.
- **No rate limiting**: Subject to abuse until M1 rate limiter active.
- **Single-node only**: No distributed locking; concurrent access may race.

## Known Gaps and Follow-up Tasks

- **Follow-up task**: Add distributed locking for multi-worker pipelines.
- **None** at spec time.


## Verification

```bash
python3 -m pytest api/tests/test_health.py -x -v
```
