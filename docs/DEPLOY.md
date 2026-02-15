# Coherence Network — Deploy Guide (Railway + Vercel)

This guide covers **initial setup**, **configuration**, and **verification** for:
- **API on Railway**
- **Web app on Vercel**

Recommended stack:
- **API**: Railway
- **Web**: Vercel
- **PostgreSQL**: Neon or Supabase
- **Neo4j**: AuraDB Free

---

## 1) Prerequisites

Before deploying:

1. Fork/clone this repo and ensure `main` is up to date.
2. Create accounts:
   - Railway
   - Vercel
   - Neon/Supabase (Postgres)
   - Neo4j Aura
3. Gather production secrets/values:
   - PostgreSQL connection URL
   - Neo4j URI/user/password
   - Any Telegram/agent env vars you use
   - Final Vercel domain (for CORS)

Do **not** commit secrets to git.

---

## 2) Configure data services first

### PostgreSQL (Neon or Supabase)

1. Create a new database project.
2. Copy the connection string (usually `postgresql://...`).
3. Save it for Railway env configuration.

### Neo4j Aura

1. Create an AuraDB instance.
2. Copy:
   - Bolt URI (`neo4j+s://...`)
   - Username
   - Password
3. Save them for Railway env configuration.

---

## 3) Railway account + project setup (step by step)

### A. Create and prepare your Railway account

1. Go to Railway and sign in (GitHub login recommended).
2. Complete onboarding:
   - Choose personal account or team.
   - Add billing method if required for your plan/usage.
3. In Railway dashboard, create/select the workspace where this project will live.

### B. Create a Railway project from GitHub

1. Click **New Project**.
2. Choose **Deploy from GitHub repo**.
3. Authorize Railway GitHub access if prompted.
4. Select this repository (`Coherence-Network`).
5. Railway creates an initial service for the selected repo.

### C. Configure the API service

1. Open the service settings and set:
   - **Root Directory**: `api/`
2. Commit includes deployment files for Railway auto-detection:
   - `api/requirements.txt` (dependency install source)
   - `api/Procfile` (web start process)
3. In Railway, **clear custom Build/Start commands** and use defaults (recommended).
   - Railway/Nixpacks should install from `requirements.txt` and run `Procfile`.
4. Add environment variables in Railway (**Variables** tab):
   - Start with values from `api/.env.example`
   - Add production DB and Neo4j values
   - Set `ALLOWED_ORIGINS=https://<your-vercel-domain>`
5. Redeploy the service after variable changes.

**Fallback (only if auto-detect fails):**
- Build command:

```bash
pip install --upgrade pip && pip install -r requirements.txt
```

- Start command:

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### D. Create/confirm public domain

1. Open Railway service **Networking**.
2. Generate a Railway public domain if one is not already assigned.
3. Copy the generated API URL as `https://<api-domain>`.

### E. Verify deployment in Railway UI

1. Open **Deployments** tab:
   - Latest deploy status should be **Success**.
2. Open **Logs** tab:
   - Confirm `uvicorn` startup appears.
   - Confirm no crash loop/restart storm.

### F. Verify deployment with HTTP checks

Replace `<api-domain>` with your Railway domain:

```bash
curl -fsS https://<api-domain>/api/health
curl -fsS https://<api-domain>/api/ready
curl -fsS https://<api-domain>/api/version
```

Expected:
- `/api/health` → status ok
- `/api/ready` → ready true
- `/api/version` → version payload

If a check fails:
1. Re-check Railway variables for missing/invalid values.
2. Confirm root dir is `api/` and custom Build/Start commands are empty (recommended default mode).
3. If logs show `No module named uvicorn`, confirm `requirements.txt` exists at `api/requirements.txt` and redeploy.
4. If still failing, set explicit fallback commands (`pip install -r requirements.txt` + `python -m uvicorn ...`) and redeploy.
5. Review logs for other startup/import errors and redeploy.

---

## 4) Background worker services (currently disabled)

⚠️ **Do not deploy autonomous pipeline workers yet** until usage limits are under control.

That means **do not** run these in Railway production services right now:
- `./scripts/run_overnight_pipeline.sh`
- `./scripts/run_autonomous.sh`

If you need to validate worker behavior temporarily, run it manually in a controlled environment with explicit limits and monitoring.

---

## 5) Setup Vercel project (web)

1. In Vercel, click **Add New Project** and import this repository.
2. Configure project:
   - **Root Directory**: `web/`
   - Framework should detect Next.js automatically.
3. Add environment variable:
   - `NEXT_PUBLIC_API_URL=https://<api-domain>`
4. Deploy.

### CLI smoke check (Railway + Vercel)

From repository root:

```bash
./scripts/verify_web_api_deploy.sh \
  https://<railway-api-domain> \
  https://<vercel-web-domain>
```

This checks:
- `GET <railway-api-domain>/api/health`
- `GET <vercel-web-domain>/`
- `GET <vercel-web-domain>/api-health`
- CORS header alignment (`Origin: <vercel-web-domain>` against API health endpoint)

Use this as a quick connectivity + CORS check after each deployment.

### If Vercel domain returns 404

A Vercel `404` on the project domain usually means the domain is not attached to the correct project or there is no active deployment for that domain.

Verify in Vercel dashboard:
1. **Project selected**: correct repository imported.
2. **Root Directory**: `web/`.
3. **Domains**: the exact domain (for example `coherencenetwork.vercel.app`) is listed under this project.
4. **Latest deployment**: Production deployment status is **Ready**.
5. **Environment variable**: `NEXT_PUBLIC_API_URL=https://coherence-network-production.up.railway.app` in Production scope.

Quick CLI checks from your machine:

```bash
curl -I https://coherencenetwork.vercel.app/
curl -I https://coherencenetwork.vercel.app/api-health
./scripts/verify_web_api_deploy.sh \
  https://coherence-network-production.up.railway.app \
  https://coherencenetwork.vercel.app
```

Expected: non-404 responses on `/` and `/api-health`, plus passing CORS check.

### Vercel error: `No Output Directory named "public" found`

If Vercel shows:
- `No Output Directory named "public" found after the Build completed.`

it means the project is being treated like a generic static site, not a Next.js app.

Fix:
1. In Vercel Project Settings, set **Framework Preset** to **Next.js**.
2. Confirm **Root Directory** is `web/`.
3. Clear any custom **Output Directory** (leave empty for Next.js).
4. Redeploy.

Repository guardrail added:
- `web/vercel.json` now pins `"framework": "nextjs"` so Vercel does not expect a static `public/` output.

### Interpreting Vercel build logs

If logs show entries like:
- `Vercel CLI <version>`
- `Installing dependencies...`
- `Running "npm run build"`
- `> next build`

that only confirms build execution started. A `404` on `https://<project>.vercel.app` after this usually indicates **domain/deployment routing**, not a Next.js compile error.

In Vercel dashboard, verify all of the following:
1. **Project Settings → General → Root Directory** is `web/`.
2. **Project Settings → Git** has the correct Production Branch.
3. **Deployments** has a Production deployment with status **Ready** (not just queued/building).
4. **Settings → Domains** includes the exact hostname you are opening.

CLI checks from your machine:

```bash
curl -I https://coherencenetwork.vercel.app/
curl -I https://coherencenetwork.vercel.app/api-health
```

Helpful header clues:
- `server: Vercel` + `404` + `x-vercel-error` => routing/domain attachment issue.
- `200/3xx` on `/` and `/api-health` => project/domain is connected correctly.

### Verify Vercel deployment

1. Open the Vercel URL.
2. Confirm pages load.
3. Confirm UI requests API successfully (browser network tab, no CORS errors).
   - `/api-health` now uses a server-side proxy route (`/api/health-proxy`) to avoid browser CORS issues while still validating upstream API reachability.

---

## 6) Cross-platform configuration checks (Railway + Vercel)

After both are deployed:

1. **CORS alignment**
   - Railway API env must include exact Vercel domain in `ALLOWED_ORIGINS`.
   - If preview deployments are used, add required preview domains.

---

## 7) Automated deploy-gate healing (GitHub checks -> Railway deploy)

Railway can skip deployment when commit check status is not green. This repo now includes an automatic recovery loop:

- Workflow: `.github/workflows/auto-heal-deploy-gates.yml`
- Trigger:
  - `workflow_run` when `Test`, `Thread Gates`, or `Change Contract` completes on `main` with non-success conclusion
  - Manual `workflow_dispatch` with optional commit SHA
- Script: `api/scripts/auto_heal_deploy_gates.py`

What it does:
1. Resolves target SHA on `main`.
2. Reads branch protection required checks.
3. Evaluates failing required contexts.
4. Finds rerunnable GitHub Actions workflow runs for those failed required checks.
5. Calls GitHub API `rerun-failed-jobs` for each run.
6. Polls check state until retried runs complete with `success` (or timeout/failure).
7. Uploads `auto_heal_report.json` as workflow artifact.

Manual run (local):

```bash
cd api
GITHUB_TOKEN=<token> python scripts/auto_heal_deploy_gates.py \
  --repo seeker71/Coherence-Network \
  --branch main \
  --base main \
  --timeout-seconds 900 \
  --poll-seconds 30 \
  --json
```

Exit codes:
- `0`: checks already green or healed to green
- `2`: still blocked (non-rerunnable failure, retry still failed, or retry timeout)

2. **API URL alignment**
   - Vercel `NEXT_PUBLIC_API_URL` must point to Railway API domain (https).

3. **Environment scope**
   - In Vercel, set env vars for the environments you use (Production/Preview/Development).
   - In Railway, ensure API service has all required env vars.

4. **Logs writable**
   - `api/logs/` should be writable at runtime (created automatically if missing).

---

## 7) Capture and monitor signals

Capture these operational signals continuously (Railway logs and/or external observability stack):
- API process logs
- API diagnostics endpoints (monitor/effectiveness/status/fatal)

Recommended periodic snapshots (every 5–15 min):

```bash
curl -fsS https://<api-domain>/api/agent/monitor-issues
curl -fsS https://<api-domain>/api/agent/effectiveness
curl -fsS https://<api-domain>/api/agent/status-report
curl -fsS https://<api-domain>/api/agent/fatal-issues
```

Store snapshots in your observability tool (Datadog, CloudWatch, Grafana Loki, etc.) for trend + incident review.

---

## 8) Post-deploy verification checklist

Run after every config/deploy change:

1. **API probes**

```bash
curl -fsS https://<api-domain>/api/health
curl -fsS https://<api-domain>/api/ready
curl -fsS https://<api-domain>/api/version
```

2. **API diagnostics**

```bash
curl -fsS https://<api-domain>/api/agent/pipeline-status
curl -fsS https://<api-domain>/api/agent/metrics
curl -fsS https://<api-domain>/api/agent/monitor-issues
curl -fsS https://<api-domain>/api/agent/fatal-issues
```

3. **Log health**
   - API service emitted logs in the last 5 minutes
   - No restart loops

4. **End-to-end smoke**
   - Create one low-risk task through `/api/agent/tasks`
   - Confirm status transitions and visible output in task list/details

---

## 9) Optional hardening

- Add custom domains for API and web.
- Add uptime checks for `/api/health` and `/api/ready`.
- Add rate limiting/WAF (Cloudflare optional).
- Route logs/metrics to centralized observability.
