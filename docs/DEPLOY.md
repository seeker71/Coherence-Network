# Coherence Network — Deploy Checklist (Railway + Vercel)

Recommended stack (cheap + easy):
- **API**: Railway
- **Web**: Vercel
- **PostgreSQL**: Neon or Supabase (free tier)
- **Neo4j**: AuraDB Free

## Pre-deploy

1. **Environment**
   - Copy `api/.env.example` to `api/.env` locally for development.
   - In Railway/Vercel dashboards, set production env vars (do not commit secrets).

2. **CORS**
   - Set `ALLOWED_ORIGINS=https://<your-vercel-domain>` (comma-separated for multiple).

3. **Logs**
   - Ensure `api/logs/` is writable (created automatically on first run).

## Health Probes

| Endpoint | Purpose |
|----------|---------|
| `GET /api/health` | Liveness — returns 200, `{"status":"ok"}` |
| `GET /api/ready` | Readiness — returns 200, `{"ready":true}` |
| `GET /api/version` | Version — returns `{"version":"0.1.0"}` |

## Deploy API to Railway

1. Create a Railway project and connect this repository.
2. Set service root to `api/`.
3. Start command:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

4. Add env vars from `api/.env.example` plus DB connection values.
5. Deploy and validate:

```bash
curl https://<api-domain>/api/health
curl https://<api-domain>/api/ready
```

## Deploy Web to Vercel

1. Import repository in Vercel.
2. Set root directory to `web/`.
3. Set env var:
   - `NEXT_PUBLIC_API_URL=https://<api-domain>`
4. Deploy and confirm the web app can call API endpoints.

## Optional hardening

- Attach custom domains.
- Add rate limiting and WAF (Cloudflare optional).
- Add uptime checks for `/api/health` and `/api/ready`.
