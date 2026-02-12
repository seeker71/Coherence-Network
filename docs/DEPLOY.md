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
| `GET /api/version` | Version — returns `{"version":"0.1.0"}` |

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
