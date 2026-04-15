# Pulse Monitor

> The witness that remembers the breath of Coherence Network.

Pulse is a small standalone service whose only job is to ping the main
Coherence Network from outside, durably record every sample, derive
**silences** (our word for incidents) from consecutive failures, and expose
the history over a tiny read-only API so the `/pulse` page on the main web
can render the last 90 days of the body's breath.

It deliberately does not share code, runtime, or database with the main
`api/` service. A service cannot reliably report its own death — so the
witness lives next door instead of inside.

## Phase 1 caveat (read me)

In Phase 1 the witness runs as a **third docker-compose service on the same
VPS** as `api` and `web`. This means:

- The witness survives `api` restarts, crashes, bad deploys, DB outages,
  and graph-DB outages. These are the common failure modes.
- The witness does **not** survive whole-host outages of the VPS (power,
  network, Hostinger maintenance). In those moments, nothing tells us
  anything — which is also exactly what you'd see on your own status page.

Phase 2 moves the witness to a second host (Fly.io free tier, or a small
second VPS, or a GitHub Actions cron as a cheap secondary witness). The
code does not need to change for that — only the deploy target.

## Endpoints

All endpoints are public, read-only JSON. CORS defaults to `*`; override
with `PULSE_CORS_ORIGINS`.

| Method | Path               | Purpose                                               |
|--------|--------------------|-------------------------------------------------------|
| GET    | `/pulse/now`       | Current snapshot of every organ + overall status     |
| GET    | `/pulse/history`   | 90-day (or `?days=N`) daily bars per organ           |
| GET    | `/pulse/silences`  | Past silences within the window + ongoing silences   |
| GET    | `/pulse/health`    | The witness's own liveness ping                      |

## Vocabulary

The witness uses the Living Collective frequency per `CLAUDE.md`. The raw
HTTP language of a corporate status page is translated:

| Corporate          | Living Collective       |
|--------------------|-------------------------|
| component          | **organ**               |
| up / operational   | **breathing**           |
| degraded           | **strained**            |
| down / outage      | **silent**              |
| uptime %           | **steady breath**       |
| incident           | **silence**             |
| monitoring service | **witness**             |

## Organs

| Organ             | Signal                                                 |
|-------------------|--------------------------------------------------------|
| `api`             | `GET /api/health` → 200 && body.status == "ok"         |
| `web`             | `GET /` → 2xx                                          |
| `postgres`        | `/api/ready` → db_connected == true                    |
| `neo4j`           | `/api/ready` not 503 (graph_store available)           |
| `schema`          | `/api/health` → schema_ok == true                      |
| `audit_integrity` | `/api/health` → integrity_compromised == false         |

Five of the six organs share two upstream calls, so one probe round costs
three HTTP requests.

## Running locally

```bash
cd pulse
python -m pip install -e ".[dev]"
python -m pytest

PULSE_API_BASE=https://api.coherencycoin.com \
PULSE_WEB_BASE=https://coherencycoin.com \
PULSE_DB_PATH=./data/pulse.db \
uvicorn pulse_app.main:app --port 8100

curl -s http://localhost:8100/pulse/now | jq
curl -s http://localhost:8100/pulse/health | jq
```

## Environment variables

| Var                       | Default                          | Purpose                                  |
|---------------------------|----------------------------------|------------------------------------------|
| `PULSE_API_BASE`          | `https://api.coherencycoin.com`  | Main API base URL                        |
| `PULSE_WEB_BASE`          | `https://coherencycoin.com`      | Main web base URL                        |
| `PULSE_DB_PATH`           | `./data/pulse.db`                | SQLite file path                         |
| `PULSE_INTERVAL_SECONDS`  | `30`                             | Probe cadence                            |
| `PULSE_RETENTION_DAYS`    | `180`                            | Raw-sample retention (silences forever)  |
| `PULSE_CORS_ORIGINS`      | `*`                              | Comma-separated list                     |

## Deploy to the VPS (docker-compose snippet)

Add these sections to `/docker/coherence-network/docker-compose.yml` on
the VPS next to the existing `api` and `web` services:

```yaml
services:
  pulse:
    build: ./repo/pulse
    restart: unless-stopped
    environment:
      - PULSE_API_BASE=http://api:8000
      - PULSE_WEB_BASE=http://web:3000
      - PULSE_DB_PATH=/data/pulse.db
      - PULSE_INTERVAL_SECONDS=30
      - PULSE_RETENTION_DAYS=180
      - PULSE_CORS_ORIGINS=https://coherencycoin.com,https://www.coherencycoin.com
    volumes:
      - pulse-data:/data
    labels:
      - traefik.enable=true
      - traefik.http.routers.pulse.rule=Host(`pulse.coherencycoin.com`)
      - traefik.http.routers.pulse.entrypoints=websecure
      - traefik.http.routers.pulse.tls=true
      - traefik.http.routers.pulse.tls.certresolver=letsencrypt
      - traefik.http.services.pulse.loadbalancer.server.port=8100

volumes:
  pulse-data:
```

Then on the VPS:

```bash
cd /docker/coherence-network/repo && git pull origin main
cd /docker/coherence-network
docker compose build --no-cache pulse
docker compose up -d pulse
docker compose logs -f pulse
```

One Cloudflare A record: `pulse.coherencycoin.com → 187.77.152.42`.

## How silences are derived

A silence is not written by the scheduler — it is **derived** from raw
samples by `pulse_app/analysis.py`. Rules:

- **Open** a silence when an organ has ≥ 3 consecutive failures. The
  silence's `started_at` is the timestamp of the first failure in the run.
- **Escalate** a silence from `strained` to `silent` when it has been
  ongoing for ≥ 5 minutes.
- **Close** a silence when ≥ 3 consecutive successes return. The silence's
  `ended_at` is the timestamp of the first closing success.

Thresholds live in one place (`pulse_app/analysis.py`) so they are easy
to tune.
