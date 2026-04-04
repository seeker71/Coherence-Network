# Spec: Deploy Readiness

## Purpose

Define minimum checklist for deploying the API and web to a hosted environment (e.g. cloud VM, container). Ensures health probes, env config, and basic security hygiene.

## Requirements

- [x] GET /api/health — liveness (returns 200)
- [x] GET /api/ready — readiness (returns 200; placeholder for DB checks when added)
- [x] Environment: all required vars documented in .env.example
- [x] No hardcoded secrets; use env vars
- [x] CORS: configurable via ALLOWED_ORIGINS in main.py
- [x] docs/DEPLOY.md: comprehensive deploy checklist for current public hosting
- [x] Production deployment: public API + public web on the VPS
- [x] Verification script: scripts/verify_web_api_deploy.sh


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: 001, 009

## Task Card

```yaml
goal: Define minimum checklist for deploying the API and web to a hosted environment (e.
files_allowed:
  - docs/DEPLOY.md
  - api/app/main.py
  - docs/SETUP.md
done_when:
  - GET /api/health — liveness (returns 200)
  - GET /api/ready — readiness (returns 200; placeholder for DB checks when added)
  - Environment: all required vars documented in .env.example
  - No hardcoded secrets; use env vars
  - CORS: configurable via ALLOWED_ORIGINS in main.py
commands:
  - cd api && python -m pytest tests/ -q
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

## Deploy Checklist (Documentation)

Create or update docs to include:

1. **Pre-deploy**
   - Copy .env.example → .env; fill required keys
   - Set ALLOWED_ORIGINS for production domain
   - Ensure logs/ directory writable (or set LOG_DIR)

2. **Health probes**
   - Liveness: GET /api/health
   - Readiness: GET /api/ready (for k8s/Docker)

3. **Optional**
   - Reverse proxy (nginx, Caddy) in front of uvicorn
   - TLS termination at proxy

## Files to Create/Modify

- `docs/DEPLOY.md` — new file: deploy checklist, env vars, health endpoints
- `api/app/main.py` — verify CORS and env usage (audit only)
- `docs/SETUP.md` — link to DEPLOY.md for production

## API Contract (Existing)

### GET /api/health
Returns 200, JSON `{"status": "ok", "service": "coherence-contribution-network", "version": "1.0.0"}`

### GET /api/ready
Returns 200, JSON `{"status": "ready"}` — future: check DB connectivity


### Field Constraints

- All string fields: min_length=1, max_length=1000
- Numeric fields: appropriate min/max bounds
- Required fields validated; missing returns 422
- Unknown fields rejected (Pydantic extra="forbid" where applicable)

## Production Deployment Status

### Live Environments
- **API**: https://coherence-network-production.up.railway.app (Railway)
- **Web**: https://coherencycoin.com (legacy web host)

### Concurrency Behavior

- **Read operations**: Safe for concurrent access; no locking required.
- **Write operations**: Last-write-wins semantics; no optimistic locking for MVP.
- **Recommendation**: Clients should not assume atomic read-modify-write without explicit ETag support.

## Verification
```bash
./scripts/verify_web_api_deploy.sh
curl -fsS https://api.coherencycoin.com/api/health
curl -fsS https://api.coherencycoin.com/api/ready
curl -fsS https://coherencycoin.com/api-health
```

Checks:
- API health endpoint
- Web root
- Web API health page (/api-health)
- CORS configuration

## Acceptance Tests

- Manual validation: `curl -fsS https://api.coherencycoin.com/api/health`, `curl -fsS https://api.coherencycoin.com/api/ready`, and `curl -fsS https://coherencycoin.com/api-health` all succeed.
- `docs/DEPLOY.md` exists and lists deploy checklist steps for the public Hostinger API and web surfaces.
- `scripts/verify_web_api_deploy.sh` passes against the public production endpoints.

## Failure and Retry Behavior

- **Gate failure**: CI gate blocks merge; author must fix and re-push.
- **Flaky test**: Re-run up to 2 times before marking as genuine failure.
- **Rollback behavior**: Failed deployments automatically roll back to last known-good state.
- **Infrastructure failure**: CI runner unavailable triggers alert; jobs re-queue on recovery.
- **Timeout**: CI jobs exceeding 15 minutes are killed and marked failed; safe to re-trigger.

## Risks and Known Gaps

- **No auth gate**: Endpoints unprotected until C1 auth middleware applied.
- **No rate limiting**: Subject to abuse until M1 rate limiter active.
- **Single-node only**: No distributed locking; concurrent access may race.
- **Follow-up**: Add deployment smoke tests post-release.


## Out of Scope

- Dockerfile or docker-compose (separate spec)
- CI/CD pipeline for deploy
- Database migrations

## See also

- [001-health-check.md](001-health-check.md) — health endpoint
- [009-api-error-handling.md](009-api-error-handling.md) — error responses

## Decision Gates

None.

## Known Gaps and Follow-up Tasks

- No known gaps at time of writing.
- Follow-up: review after initial implementation for completeness.
