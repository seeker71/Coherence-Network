# Spec: Sprint 0 — Landing Live

## Purpose

Complete Sprint 0 exit criteria from docs/PLAN.md: git push → CI green; /health 200; landing live.
CI and health already exist. This spec formalizes the landing experience and deploy readiness.

## Requirements

- [x] `git push` triggers CI (GitHub Actions)
- [x] CI runs pytest and passes
- [x] `GET /api/health` returns 200
- [x] Root `GET /` returns project info: name, version, docs URL, health URL (for discovery)
- [x] OpenAPI docs at `/docs` are reachable when API runs (FastAPI built-in)

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

## Files to Create/Modify

- `api/app/main.py` — extend root response with version, health URL

## Acceptance Tests

- Root returns 200 with `name`, `version`, `docs`, `health` fields
- `/docs` returns 200 when API is running (smoke test)

## Out of Scope

- Actual deployment to Railway/Fly/Vercel (decision gate)
- Web UI landing page (Sprint 1+)

## Decision Gates

- Deploy target and credentials require human approval
