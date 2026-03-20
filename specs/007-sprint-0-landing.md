# Spec: Sprint 0 — Landing Live

## Purpose

Complete Sprint 0 exit criteria from docs/PLAN.md: git push → CI green; /health 200; landing live.
CI and health already exist. This spec formalizes the landing experience and deploy readiness, and defines how to verify landing complete including /docs reachability.

## Requirements

- [x] `git push` triggers CI (GitHub Actions)
- [x] CI runs pytest and passes
- [x] `GET /api/health` returns 200
- [x] Root `GET /` returns project info: name, version, docs URL, health URL (for discovery)
- [x] OpenAPI docs at `/docs` are reachable when API runs (FastAPI built-in)
- [x] Landing complete is verifiable via automated tests (root + /docs reachability)

### Concurrency Behavior

- **Read operations**: Safe for concurrent access; no locking required.
- **Write operations**: Last-write-wins semantics; no optimistic locking for MVP.
- **Recommendation**: Clients should not assume atomic read-modify-write without explicit ETag support.

## Verification: landing complete

Landing is complete when all of the following hold:

1. **CI green** — `git push` runs GitHub Actions; pytest passes.
2. **Health** — `GET /api/health` returns 200 (spec 001).
3. **Root discovery** — `GET /` returns 200 with `name`, `version`, `docs`, `health` (this spec).
4. **Docs reachability** — `GET /docs` returns 200 (OpenAPI UI reachable; test below).


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: 001, 006

## Task Card

```yaml
goal: Complete Sprint 0 exit criteria from docs/PLAN.
files_allowed:
  - api/app/main.py
  - api/tests/test_health.py
done_when:
  - `git push` triggers CI (GitHub Actions)
  - CI runs pytest and passes
  - `GET /api/health` returns 200
  - Root `GET /` returns project info: name, version, docs URL, health URL (for discovery)
  - OpenAPI docs at `/docs` are reachable when API runs (FastAPI built-in)
commands:
  - cd api && python -m pytest api/tests/test_health.py -q
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

## API Contract

### `GET /`

**Response 200**
```json
{
  "name": "Coherence Network API",
  "version": "0.1.0",
  "docs": "/docs",
  "health": "/api/health"
}
```

### `GET /docs` (reachability)

**Response 200** — HTML (FastAPI Swagger UI). No JSON contract; only reachability is required. The test asserts `status_code == 200`.

#### Acceptance test: GET /docs returns 200 (OpenAPI UI reachable)

- **Requirement:** Add (or keep) a test that `GET /docs` returns HTTP 200 so the OpenAPI UI is reachable when the API runs.
- **Test name:** `test_docs_returns_200`
- **Test file:** `api/tests/test_health.py`
- **Assertion:** `response = client.get("/docs"); assert response.status_code == 200`
- **Out of scope:** No assertion on response body (HTML); status code only.


### Input Validation

- All string fields: min_length=1, max_length=1000
- Numeric fields: appropriate min/max bounds
- Required fields validated; missing returns 422
- Unknown fields rejected (Pydantic extra="forbid" where applicable)

## Files to Create/Modify

- `api/app/main.py` — root response with version, docs URL, health URL (already done)
- `api/tests/test_health.py` — root and /docs acceptance tests for this spec (see Acceptance Tests)

## Acceptance Tests

See `api/tests/test_health.py`. Spec 007 tests (do not modify tests to make implementation pass):

- **Root landing** — `test_root_returns_landing_info`: GET / returns 200 with `name`, `version`, `docs` (value `/docs`), `health` (value `/api/health`).
- **/docs reachability** — `test_docs_returns_200`: GET /docs returns 200 (OpenAPI UI reachable).

All tests above must pass for landing to be considered complete.

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


## Out of Scope

- Actual deployment to Railway/Fly/Vercel (decision gate)
- Web UI landing page (Sprint 1+)

## See also

- [001-health-check.md](001-health-check.md) — /api/health contract
- [006-overnight-backlog.md](006-overnight-backlog.md) — backlog item for /docs test
- docs/PLAN.md — Sprint 0 exit criteria

## Decision Gates

- Deploy target and credentials require human approval
