# Coherence Network — Deploy Guide (Railway Only)

**Railway deploy paused:** Do not deploy to Railway until the account ban is lifted or a new account is used. Push to `origin/main` and open/merge PRs as normal; skip triggering Railway redeploys or linking production to this repo until then.

This project deploys both API and web on Railway (when enabled).

## Vercel Note (Disable PR Deployments)

If the web app is also connected to Vercel, ensure preview deployments are disabled to avoid Vercel deployment rate limits.

This repo enforces "deploy only from `main`" via `vercel.json` and `web/vercel.json` (`git.deploymentEnabled`).

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
- `PUBLIC_DEPLOY_REQUIRE_API_HEALTH_SHA=1` (strictly require `/api/health` to expose deployed SHA and match `main`)
- `PUBLIC_DEPLOY_REQUIRE_WEB_HEALTH_PROXY_SHA=1` (strictly require `/api/health-proxy` to expose web deployed SHA and match `main`)
- `PAID_TOOL_8H_LIMIT=300`
- `PAID_TOOL_WEEK_LIMIT=2200`
- `PAID_TOOL_WINDOW_BUDGET_FRACTION=0.333`

Web service (`coherence-web`):

- `NEXT_PUBLIC_API_URL=https://coherence-network-production.up.railway.app`

## n8n Security Baseline and HITL Contract

When automation flows depend on n8n, deployment validation must enforce:

1. Minimum secure n8n version:
- v1 track: `>=1.123.17`
- v2 track: `>=2.5.2`
2. Human-in-the-loop (HITL) approval for destructive/external-impacting tool calls (for example delete/write/send actions).

Optional pre-merge gate command (from `api/`):

```bash
.venv/bin/python scripts/validate_pr_to_public.py \
  --branch codex/<thread-name> \
  --wait-public \
  --n8n-version "${N8N_VERSION}"
```

If the provided n8n version is below floor, the script returns non-zero with `result=blocked_n8n_version`.

## Railway Auto-Deploy Settings

Set in both Railway services:

1. Source repository: `seeker71/Coherence-Network`
2. Branch: `main`
3. Auto deploy: enabled
4. Wait for CI (optional): enabled only if required GitHub checks are stable

## Local Validation Before Push

From repo root:

```bash
VERIFY_REQUIRE_API_HEALTH_SHA=1 \
VERIFY_REQUIRE_WEB_HEALTH_PROXY_SHA=1 \
./scripts/verify_web_api_deploy.sh \
  https://coherence-network-production.up.railway.app \
  https://coherence-web-production.up.railway.app
```

## CI/CD Validation

- `.github/workflows/public-deploy-contract.yml` validates Railway API + Railway web.
- If contract fails and Railway CLI secrets are present, workflow triggers Railway redeploy (API + web when both service secrets are set) and revalidates.

Required repo secrets for automated redeploy:

- `RAILWAY_TOKEN`
- `RAILWAY_PROJECT_ID`
- `RAILWAY_ENVIRONMENT`
- `RAILWAY_API_SERVICE` (preferred; falls back to legacy `RAILWAY_SERVICE` if unset)
- `RAILWAY_WEB_SERVICE` (required to auto-heal web SHA drift checks)
- `RAILWAY_SERVICE` (legacy fallback for API service)

Optional repo variables to override deploy de-risk defaults:

- `PUBLIC_DEPLOY_VERIFICATION_MAX_ATTEMPTS`
- `PUBLIC_DEPLOY_VERIFICATION_RETRY_SECONDS`
- `PUBLIC_DEPLOY_REVALIDATE_MAX_ATTEMPTS`
- `PUBLIC_DEPLOY_REVALIDATE_SLEEP_SECONDS`
- `PUBLIC_DEPLOY_CONTRACT_BLOCK_THRESHOLD_SECONDS`
- `PUBLIC_DEPLOY_REQUIRE_API_HEALTH_SHA`
- `PUBLIC_DEPLOY_REQUIRE_WEB_HEALTH_PROXY_SHA`

## Manual Railway Verification

```bash
curl -fsS https://coherence-network-production.up.railway.app/api/health | jq .
curl -fsS https://coherence-network-production.up.railway.app/api/gates/main-head | jq .
curl -fsS https://coherence-web-production.up.railway.app/api-health | jq .
curl -fsS https://coherence-web-production.up.railway.app/gates | head -c 200
```

## Railway ToS / policy (if you get a ToS violation)

Railway may flag accounts for policy or abuse. Possible triggers from this repo:

1. **Calling Railway’s API from the app**  
   With `RAILWAY_TOKEN` (and related env) set on the API service, the app calls `https://backboard.railway.com/graphql/v2` when building usage/readiness (e.g. `GET /api/automation/usage`, `GET /api/automation/usage/readiness`). The web automation page requests with `force_refresh=true`, so each load can trigger a GraphQL call from your Railway-hosted API to Railway’s backend. Programmatic or high-frequency use of their dashboard/GraphQL from a deployed app may be against their terms.  
   **Mitigation:** Unset `RAILWAY_TOKEN` (and `RAILWAY_PROJECT_ID`, `RAILWAY_ENVIRONMENT`, `RAILWAY_SERVICE`) on the API service so the app does not call backboard. Use the Railway CLI or dashboard only from your machine or CI when needed.

2. **Frequent redeploys from CI**  
   The public deploy contract runs every 30 minutes and, on failure, can run `railway redeploy` (and `railway link`) from GitHub Actions. If the contract fails often, that can mean many deploy/API calls.  
   **Mitigation:** Fix the underlying contract (e.g. SHA drift) so redeploys are rare, or temporarily disable the “Trigger Railway redeploy” step in `.github/workflows/public-deploy-contract.yml` (e.g. by removing/commenting the step or the workflow’s `schedule`).

3. **Heavy outbound or CPU from task execution**  
   With `AGENT_AUTO_EXECUTE=1`, creating tasks runs execution on the server (e.g. OpenRouter). Many tasks mean more outbound calls and CPU; extreme volume could trip resource or abuse policies.  
   **Mitigation:** Set `AGENT_AUTO_EXECUTE=0` in production until you control task creation, or throttle task creation and enforce limits.

4. **Other common Railway ToS reasons**  
   Card testing / payment issues, trial abuse, or account access problems are unrelated to this codebase; resolve those with Railway (e.g. team@railway.com from the account email).

**Next step:** Ask Railway support for the exact reason (e.g. “programmatic use of Railway API from hosted app”, “excessive redeploys”, “resource usage”). Then apply the matching mitigation above.

## Failure Triage

If deployment is skipped or stale:

1. Check GitHub required checks on latest `main` commit.
2. Check Railway deployment logs for API and web services.
3. Re-run public contract workflow.
4. Trigger Railway redeploy with CLI and re-validate.
