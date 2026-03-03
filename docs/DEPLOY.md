# Coherence Network — Deploy Guide (Railway Only)

This project deploys both API and web on Railway.

## Vercel Note (Disable PR Deployments)

If the web app is also connected to Vercel, ensure preview deployments are disabled to avoid Vercel deployment rate limits.

This repo enforces "deploy only from `main`" via `vercel.json` and `web/vercel.json` (`git.deploymentEnabled`).

## Deployment Targets

- API: `https://coherence-network-production.up.railway.app`
- Web: `https://coherence-web-production.up.railway.app`

## Required Railway Services

1. `coherence-network` (API, root directory `api/`)
2. `coherence-web` (web, root directory `web/`)
3. PostgreSQL (Railway plugin)

## Required Environment Variables

API service (`coherence-network`):

- `DATABASE_URL` (Railway Postgres)
- `NEO4J_URI`
- `NEO4J_USERNAME`
- `NEO4J_PASSWORD`
- `ALLOWED_ORIGINS=https://coherence-web-production.up.railway.app,http://localhost:3000`
- `PUBLIC_DEPLOY_VERIFICATION_MAX_ATTEMPTS=8` (guard retries per deploy check loop)
- `PUBLIC_DEPLOY_VERIFICATION_RETRY_SECONDS=60` (seconds between retries)
- `PUBLIC_DEPLOY_CONTRACT_BLOCK_THRESHOLD_SECONDS=600` (escalate when deployment contract blocked for >10 minutes)
- `PAID_TOOL_8H_LIMIT=300`
- `PAID_TOOL_WEEK_LIMIT=2200`
- `PAID_TOOL_WINDOW_BUDGET_FRACTION=0.333`

Web service (`coherence-web`):

- `NEXT_PUBLIC_API_URL=https://coherence-network-production.up.railway.app`

## Railway Auto-Deploy Settings

Set in both Railway services:

1. Source repository: `seeker71/Coherence-Network`
2. Branch: `main`
3. Auto deploy: enabled
4. Wait for CI (optional): enabled only if required GitHub checks are stable

## Local Validation Before Push

From repo root:

```bash
./scripts/verify_web_api_deploy.sh \
  https://coherence-network-production.up.railway.app \
  https://coherence-web-production.up.railway.app
```

## CI/CD Validation

- `.github/workflows/public-deploy-contract.yml` validates Railway API + Railway web.
- If contract fails and Railway CLI secrets are present, workflow triggers Railway redeploy and revalidates.

Required repo secrets for automated redeploy:

- `RAILWAY_TOKEN`
 - `RAILWAY_PROJECT_ID`
 - `RAILWAY_ENVIRONMENT`
 - `RAILWAY_SERVICE`

Optional repo variables to override deploy de-risk defaults:

- `PUBLIC_DEPLOY_VERIFICATION_MAX_ATTEMPTS`
- `PUBLIC_DEPLOY_VERIFICATION_RETRY_SECONDS`
- `PUBLIC_DEPLOY_REVALIDATE_MAX_ATTEMPTS`
- `PUBLIC_DEPLOY_REVALIDATE_SLEEP_SECONDS`
- `PUBLIC_DEPLOY_CONTRACT_BLOCK_THRESHOLD_SECONDS`

## Manual Railway Verification

```bash
curl -fsS https://coherence-network-production.up.railway.app/api/health | jq .
curl -fsS https://coherence-network-production.up.railway.app/api/gates/main-head | jq .
curl -fsS https://coherence-web-production.up.railway.app/api-health | jq .
curl -fsS https://coherence-web-production.up.railway.app/gates | head -c 200
```

## Failure Triage

If deployment is skipped or stale:

1. Check GitHub required checks on latest `main` commit.
2. Check Railway deployment logs for API and web services.
3. Re-run public contract workflow.
4. Trigger Railway redeploy with CLI and re-validate.
