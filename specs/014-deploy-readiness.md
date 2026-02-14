# Spec: Deploy Readiness

## Purpose

Define minimum checklist for deploying the API and web to a hosted environment (e.g. cloud VM, container). Ensures health probes, env config, and basic security hygiene.

## Requirements

- [x] GET /api/health — liveness (returns 200)
- [x] GET /api/ready — readiness (returns 200; placeholder for DB checks when added)
- [x] Environment: all required vars documented in .env.example
- [x] No hardcoded secrets; use env vars
- [x] CORS: configurable via ALLOWED_ORIGINS in main.py
- [x] docs/DEPLOY.md: comprehensive deploy checklist for Railway + Vercel
- [x] Production deployment: Railway (API) + Vercel (web)
- [x] Verification script: scripts/verify_web_api_deploy.sh

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

## Production Deployment Status

### Live Environments
- **API**: https://coherence-network-production.up.railway.app (Railway)
- **Web**: https://coherence-network.vercel.app (Vercel)

### Verification
```bash
./scripts/verify_web_api_deploy.sh
```

Checks:
- API health endpoint
- Web root
- Web API health page (/api-health)
- CORS configuration

## Acceptance Tests

- GET /api/health, /api/ready, /api/version return 200
- docs/DEPLOY.md exists and lists env vars and checklist

## Out of Scope

- Dockerfile or docker-compose (separate spec)
- CI/CD pipeline for deploy
- Database migrations

## See also

- [001-health-check.md](001-health-check.md) — health endpoint
- [009-api-error-handling.md](009-api-error-handling.md) — error responses

## Decision Gates

None.
