# Coherence Network — Deploy Guide (Railway Only)

This project deploys both API and web on Railway.

## Vercel Note (Disable PR Deployments)

If the web app is also connected to Vercel, ensure preview deployments are disabled to avoid Vercel deployment rate limits.

This repo enforces "deploy only from `main`" via `vercel.json` and `web/vercel.json` (`git.deploymentEnabled`).

## Deployment Targets

- API: `https://coherence-network-production.up.railway.app`
- Web: `https://coherence-web-production.up.railway.app`

| Endpoint | Purpose |
|----------|---------|
| `GET /api/health` | Liveness — returns 200, `{"status":"ok"}` |
| `GET /api/ready` | Readiness — returns 200, `{"ready":true}` (for k8s/Docker) |
| `GET /api/version` | Optional version endpoint (if wired in your API module) |

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

- Reverse proxy (nginx, Caddy) in front of uvicorn
- TLS termination at proxy
- Process manager (systemd, supervisord) for API and agent_runner

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

Use this for a full deployment with pipeline auto-contribution tracking.

### 1) Provision VM + firewall

- Ubuntu 22.04 VM on Oracle Cloud (VM.Standard.E2.1.Micro or larger)
- Open ingress ports:
  - `22` SSH
  - `80` HTTP (optional, for reverse proxy)
  - `443` HTTPS
  - `8000` only if exposing API directly (recommended: keep private and use reverse proxy)

### 2) Install runtime dependencies

```bash
sudo apt update && sudo apt install -y git python3.11 python3.11-venv python3-pip nginx
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

### 3) Clone and configure

```bash
git clone https://github.com/<your-org>/Coherence-Network.git
cd Coherence-Network/api
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
```

Set at least these values in `api/.env`:

- `ALLOWED_ORIGINS=https://<your-domain>`
- `AGENT_API_BASE=http://127.0.0.1:8000`
- `PIPELINE_AUTO_COMMIT=1`
- `PIPELINE_AUTO_PUSH=1` (only if the VM has git push credentials configured)
- `PIPELINE_AUTO_RECOVER=1`

### 4) Run API + autonomous pipeline with systemd

Create `/etc/systemd/system/coherence-api.service`:

```ini
[Unit]
Description=Coherence API
After=network.target

[Service]
Type=simple
WorkingDirectory=/home/ubuntu/Coherence-Network/api
ExecStart=/home/ubuntu/Coherence-Network/api/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Create `/etc/systemd/system/coherence-pipeline.service`:

```ini
[Unit]
Description=Coherence autonomous pipeline
After=coherence-api.service
Requires=coherence-api.service

[Service]
Type=simple
WorkingDirectory=/home/ubuntu/Coherence-Network/api
ExecStart=/home/ubuntu/Coherence-Network/api/scripts/run_autonomous.sh
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now coherence-api.service coherence-pipeline.service
```

### 5) Verify deployment and API usability

From VM (or a trusted workstation with network access):

```bash
cd Coherence-Network/api
.venv/bin/python scripts/verify_deployment.py --base-url http://127.0.0.1:8000
```

The verification checks:

- health/readiness endpoints (and `/api/version` if available)
- write/read flow for contributor, asset, and contribution creation
- total cost roll-up after contribution creation

### 6) Verify auto-contribution tracking is active

```bash
tail -f api/logs/commit_progress.log
tail -f api/logs/project_manager.log
tail -f api/logs/agent_runner.log
```

You should see completed tasks and auto-commit events when `PIPELINE_AUTO_COMMIT=1`.
