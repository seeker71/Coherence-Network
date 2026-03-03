# Coherence Network — Deploy Checklist

Quick reference for deploying API and web to a hosted environment.

## Pre-deploy

1. **Environment**
   - Copy `api/.env.example` to `api/.env`
   - Fill required keys: `ANTHROPIC_API_KEY` or `OLLAMA_BASE_URL` for agent; `TELEGRAM_BOT_TOKEN` if using Telegram
   - See [API-KEYS-SETUP.md](API-KEYS-SETUP.md) for details

2. **CORS**
   - Set `ALLOWED_ORIGINS=https://your-domain.com` (comma-separated for multiple). Default: `*` (all origins).

3. **Logs**
   - Ensure `api/logs/` is writable (created automatically on first run)
   - See [RUNBOOK.md](RUNBOOK.md) for log locations

## Health Probes

| Endpoint | Purpose |
|----------|---------|
| `GET /api/health` | Liveness — returns 200, `{"status":"ok"}` |
| `GET /api/ready` | Readiness — returns 200, `{"ready":true}` (for k8s/Docker) |
| `GET /api/version` | Optional version endpoint (if wired in your API module) |

## Run API

```bash
cd api
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

For production, run behind a reverse proxy (nginx, Caddy) with TLS termination.

## Web

```bash
cd web
npm ci
npm run build
npm start
```

Set `NEXT_PUBLIC_API_URL` to your API base URL.

## Optional

- Reverse proxy (nginx, Caddy) in front of uvicorn
- TLS termination at proxy
- Process manager (systemd, supervisord) for API and agent_runner

## Oracle Cloud VM deployment (recommended path)

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
