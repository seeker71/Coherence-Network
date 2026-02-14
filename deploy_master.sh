#!/usr/bin/env bash
set -euo pipefail

cat <<'MSG'
Coherence Network deploy pivot
=============================
This project now uses managed hosting:
  - API: Railway
  - Web: Vercel
  - DB: Neon/Supabase + AuraDB Free

Manual steps:
  1) Deploy api/ service to Railway with:
       uvicorn app.main:app --host 0.0.0.0 --port $PORT
  2) Deploy web/ project to Vercel
  3) Set NEXT_PUBLIC_API_URL in Vercel
  4) Set ALLOWED_ORIGINS in API environment
  5) Run ./verify_deployment.sh

See docs/DEPLOY.md and DEPLOYMENT_GUIDE.md for full details.
MSG
