# Deployment Update — 2026-02-14

## Summary

Updated project documentation and configuration to reflect the current public deployment on Railway (API) and Railway web (web).

## Public Deployments

| Service | Platform | URL | Status |
|---------|----------|-----|--------|
| API | Railway | https://coherence-network-production.up.railway.app | ✅ Live |
| Web | Railway web | https://coherence-web-production.up.railway.app | ✅ Live |

## Changes Made

### 1. CORS Configuration (api/app/main.py)
- ✅ Added `CORSMiddleware` to FastAPI app
- ✅ Reads `ALLOWED_ORIGINS` from environment variable
- ✅ Supports comma-separated list of origins
- ✅ All tests passing

### 2. Environment Configuration (api/.env.example, web/.env.example)
- ✅ Updated with production domain examples
- ✅ Added clear comments for local vs production
- ✅ Documented CORS requirements

### 3. Documentation Updates

#### STATUS.md
- ✅ Added "Production deployment" row to current state table
- ✅ Added "Public Deployments" section with URLs
- ✅ Added deployment health status

#### PLAN.md
- ✅ Added deployment maintenance to Product Delivery
- ✅ Added deployment health to Milestone A

#### CONTRIBUTING.md
- ✅ Complete rewrite to match current reality
- ✅ Added public deployment URLs
- ✅ Simplified to focus on actual contribution workflow
- ✅ Removed hypothetical features (tokenization, node operators, etc.)
- ✅ Added deployment verification instructions

#### specs/014-deploy-readiness.md
- ✅ Updated to reflect Railway (API + web) stack
- ✅ Added production deployment URLs
- ✅ Updated API contract examples
- ✅ Added verification script reference

## Next Steps (Railway Configuration)

### ⚠️ Action Required: Update Railway Environment Variable

The CORS configuration is now in the code, but Railway needs the environment variable set:

1. Go to Railway dashboard: https://railway.app/
2. Select project: `Coherence-Network`
3. Select service: API service
4. Go to **Variables** tab
5. Add or update:
   ```
   ALLOWED_ORIGINS=https://coherence-web-production.up.railway.app,http://localhost:3000
   ```
6. Redeploy the service

### Verification After Railway Update

Run the verification script:

```bash
./scripts/verify_web_api_deploy.sh
```

Expected result after Railway update:
```
==> Railway API health
✅ PASS

==> Railway web root
✅ PASS

==> Railway web API health page
✅ PASS

==> CORS check
✅ PASS (Access-Control-Allow-Origin: https://coherence-web-production.up.railway.app)

Deployment verification passed
```

## Current Verification Results

As of 2026-02-14, before Railway env update:

- ✅ API health endpoint responding (200)
- ✅ Web root responding (200)
- ✅ Web API health page responding (200)
- ❌ CORS header missing (needs Railway env update)

## Files Modified

- `api/app/main.py` — Added CORS middleware
- `api/.env.example` — Added production CORS example
- `web/.env.example` — Added production API URL example
- `docs/STATUS.md` — Added deployment status
- `docs/PLAN.md` — Added deployment operations
- `CONTRIBUTING.md` — Complete rewrite for current reality
- `specs/014-deploy-readiness.md` — Updated for Railway
- `docs/DEPLOYMENT-UPDATE-2026-02-14.md` — This file

## Testing

All API tests passing:
```bash
cd api
.venv/bin/pytest tests/ --ignore=tests/holdout -v
# 46 passed in 0.25s
```

## References

- [docs/DEPLOY.md](DEPLOY.md) — Full deployment guide
- [docs/STATUS.md](STATUS.md) — Current status
- [CONTRIBUTING.md](../CONTRIBUTING.md) — Contributor guide
- [specs/014-deploy-readiness.md](../specs/014-deploy-readiness.md) — Deployment spec
