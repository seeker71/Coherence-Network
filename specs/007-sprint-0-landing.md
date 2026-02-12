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

### Verification: landing complete

Landing is complete when all of the following hold:

1. **CI green** — `git push` runs GitHub Actions; pytest passes.
2. **Health** — `GET /api/health` returns 200 (spec 001).
3. **Root discovery** — `GET /` returns 200 with `name`, `version`, `docs`, `health` (this spec).
4. **Docs reachability** — `GET /docs` returns 200 (OpenAPI UI reachable; test below).

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

## Files to Create/Modify

- `api/app/main.py` — root response with version, docs URL, health URL (already done)
- `api/tests/test_health.py` — root and /docs acceptance tests for this spec (see Acceptance Tests)

## Acceptance Tests

See `api/tests/test_health.py`. Spec 007 tests (do not modify tests to make implementation pass):

- **Root landing** — `test_root_returns_landing_info`: GET / returns 200 with `name`, `version`, `docs` (value `/docs`), `health` (value `/api/health`).
- **/docs reachability** — `test_docs_returns_200`: GET /docs returns 200 (OpenAPI UI reachable).

All tests above must pass for landing to be considered complete.

## Out of Scope

- Actual deployment to Railway/Fly/Vercel (decision gate)
- Web UI landing page (Sprint 1+)

## See also

- [001-health-check.md](001-health-check.md) — /api/health contract
- [006-overnight-backlog.md](006-overnight-backlog.md) — backlog item for /docs test
- docs/PLAN.md — Sprint 0 exit criteria

## Decision Gates

- Deploy target and credentials require human approval
