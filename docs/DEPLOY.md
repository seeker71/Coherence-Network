# Coherence Network — Deploy Guide

Production runs on the Hostinger VPS, not Railway. The current API and web
domains are:

- API: `https://api.coherencycoin.com`
- Web: `https://coherencycoin.com`

Read [`PRODUCTION-SUBSTRATE.md`](PRODUCTION-SUBSTRATE.md) before touching
database access, native kernel DB probes, or deployment credentials.

## Quick Deploy

After merge to `main`:

```bash
ssh -i ~/.ssh/hostinger-openclaw root@187.77.152.42 \
  'cd /docker/coherence-network/repo && git pull origin main && \
   cd /docker/coherence-network && docker compose build --no-cache api web && \
   docker compose up -d api web'
```

Verify:

```bash
curl -fsS https://api.coherencycoin.com/api/health | jq .
curl -fsS https://coherencycoin.com/api/health-proxy | jq .
./scripts/verify_web_api_deploy.sh https://api.coherencycoin.com https://coherencycoin.com
```

After deploy, also read the witness:

```bash
curl -sS --max-time 5 https://pulse.coherencycoin.com/pulse/now \
  | jq '{overall, silences: (.ongoing_silences | length), silent_organs: [.organs[] | select(.status != "breathing") | .name]}'
```

## Infrastructure

| Part | Current value |
|---|---|
| VPS | `187.77.152.42` |
| SSH key | `~/.ssh/hostinger-openclaw` |
| Deploy root | `/docker/coherence-network` |
| Repo on VPS | `/docker/coherence-network/repo` |
| Services | `api`, `web`, `postgres`, `neo4j` |
| Proxy | Traefik behind Cloudflare |
| Production DB | Internal Docker Compose Postgres service |

Secrets and DB credentials live in config files on the VPS and in local
machine-only overlays. Do not commit or print them.

## DB Checks

Use the safe current procedure in
[`PRODUCTION-SUBSTRATE.md`](PRODUCTION-SUBSTRATE.md#direct-production-db-proof).
Postgres is internal to the Docker network. Do not chase Railway Postgres,
Supabase pooler credentials, or shell `DATABASE_URL` as the current production
path.

## CI/CD Validation

The public contract validates the current public API and web domains. When a
check reports SHA drift while Hostinger deployment is still running, treat it as
rollout lag and re-run the deploy verifier after the host update completes:

```bash
gh run list --repo seeker71/Coherence-Network --branch main --limit 5
gh run watch <run-id> --repo seeker71/Coherence-Network
./scripts/verify_web_api_deploy.sh https://api.coherencycoin.com https://coherencycoin.com
```

## Failure Triage

1. Check latest `main` checks.
2. SSH to the VPS and inspect compose status:
   `cd /docker/coherence-network && docker compose ps`
3. Inspect API/web logs:
   `cd /docker/coherence-network && docker compose logs --tail=200 api web`
4. Rebuild/restart only the affected service when possible.
5. Re-run public deploy verification and witness read.

## Historical Note

Railway was a previous deployment path and its old URLs appear in historical
docs, tests, and audit records. It is not the current production system.
