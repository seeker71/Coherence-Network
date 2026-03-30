# Coherence Network — Deployment Guide (Managed Hosting)

This guide standardizes deployment on low-cost managed services:
- **API**: Railway
- **Web**: Vercel
- **PostgreSQL**: Neon or Supabase (free tiers)
- **Neo4j**: AuraDB Free

## 1) Prepare environment values

Create a secure values list from `api/.env.example` and add real secrets in platform dashboards.

Required minimum:
- `OPENROUTER_API_KEY` (or your preferred model provider key)
- `DATABASE_URL`
- `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` (if graph features enabled)
- `ALLOWED_ORIGINS` (Vercel domain)

## 2) Deploy API (Railway)

1. Create Railway project and connect GitHub repo.
2. Set root directory to `api/`.
3. Configure start command:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

4. Add environment variables.
5. Deploy and copy API public URL.

## 3) Deploy Web (Vercel)

1. Import same repo in Vercel.
2. Set root directory to `web/`.
3. Set env var:

```bash
NEXT_PUBLIC_API_URL=https://<railway-api-domain>
```

4. Deploy and test the app.

## 4) Verify deployment

```bash
curl https://<api-domain>/api/health
curl https://<api-domain>/api/ready
curl https://<api-domain>/api/version
```

Expected:
- `/api/health` → `{"status":"ok"}`
- `/api/ready` → `{"ready":true}`
- `/api/version` → version payload

## 5) Run project checks after deployment

```bash
cd api && pytest -v --ignore=tests/holdout
```

## 6) Troubleshooting

- 502/timeout from API: verify Railway service root is `api/` and start command is correct.
- Web cannot reach API: verify `NEXT_PUBLIC_API_URL` and CORS `ALLOWED_ORIGINS`.
- DB errors: re-check credentials and outbound network settings in DB provider.
