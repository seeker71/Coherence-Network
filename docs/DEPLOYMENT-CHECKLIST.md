# Deployment Checklist — Hostinger + GitHub

This checklist names the current deployment path. Railway setup instructions
were composted because they no longer describe the live system.

## Current Status

| Item | Status |
|---|---|
| Public API | `https://api.coherencycoin.com` |
| Public web | `https://coherencycoin.com` |
| Host | Hostinger VPS `187.77.152.42` |
| Runtime | Docker Compose behind Traefik + Cloudflare |
| Production DB | Internal Postgres compose service |
| DB credentials | Config files only; never committed or printed |

## Before Deploy

```bash
git rev-parse --abbrev-ref HEAD
git status --short
git fetch origin main && git rebase origin/main
python3 scripts/worktree_pr_guard.py --mode local --base-ref origin/main
python3 scripts/check_pr_followthrough.py --stale-minutes 90 --fail-on-stale --strict
```

For commit-scoped evidence, add and validate:

```bash
python3 scripts/validate_commit_evidence.py --file docs/system_audit/commit_evidence_<date>_<topic>.json
```

## Deploy

```bash
ssh -i ~/.ssh/hostinger-openclaw root@187.77.152.42 \
  'cd /docker/coherence-network/repo && git pull origin main && \
   cd /docker/coherence-network && docker compose build --no-cache api web && \
   docker compose up -d api web'
```

## Verify

```bash
curl -fsS https://api.coherencycoin.com/api/health | jq .
curl -fsS https://coherencycoin.com/api/health-proxy | jq .
./scripts/verify_web_api_deploy.sh https://api.coherencycoin.com https://coherencycoin.com
curl -sS --max-time 5 https://pulse.coherencycoin.com/pulse/now \
  | jq '{overall, silences: (.ongoing_silences | length), silent_organs: [.organs[] | select(.status != "breathing") | .name]}'
```

## Production DB

Read [`PRODUCTION-SUBSTRATE.md`](PRODUCTION-SUBSTRATE.md). The current database
is the Hostinger compose Postgres service. Railway Postgres, Supabase pooler
secrets, and shell `DATABASE_URL` are not the current production credential path.

## Failure Triage

```bash
ssh -i ~/.ssh/hostinger-openclaw root@187.77.152.42 \
  'cd /docker/coherence-network && docker compose ps && docker compose logs --tail=200 api web'
```

Then repair the smallest failing service, rerun public verification, and read
the witness.
