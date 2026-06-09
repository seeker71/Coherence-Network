# Production Substrate

This is the current production memory for API, web, and durable data. Read this
before chasing Railway, Supabase, local SQLite, shell environment variables, or
old deployment checklists.

## Current Topology

| Surface | Current carrier |
|---|---|
| Public API | `https://api.coherencycoin.com` |
| Public web | `https://coherencycoin.com` |
| Host | Hostinger VPS `187.77.152.42` |
| SSH | `~/.ssh/hostinger-openclaw` |
| Deploy root | `/docker/coherence-network` |
| Repo on host | `/docker/coherence-network/repo` |
| Front proxy | Traefik behind Cloudflare |
| Runtime services | `api`, `web`, `postgres`, `neo4j` in Docker Compose |

Postgres is not publicly exposed. It lives on the internal Docker Compose
network and is reached by production services through config files.

The normal API front door remains Traefik → `api:8000`. A header-gated
kernel-router canary is layered beside it: requests to `api.coherencycoin.com`
with `X-Form-Native-Preview: 1` or `X-Form-Native-Public-Gate: 1` route to the
`kernel-router` service, which runs `production-routes.fk`, reads the mounted
production config overlay at `/run/coherence-network/config.json`, executes
public-gate/default mutable SQL through Form-native `pg_exec` when
`database.url` is present, and fans out the tail to `api:8000`. No-header
traffic stays on the ordinary API route. Verify the public gate with:

```bash
scripts/verify_kernel_canary_public_gate.sh https://api.coherencycoin.com
```

## Where Credentials Live

Do not paste credentials into chat, docs, logs, commits, shell history, or task
cards.

Current production credential carriers:

- VPS config: `/root/.coherence-network/config.json`
- VPS compose secrets: `/docker/coherence-network/.env`
- Local kernel-only overlay, when present:
  `~/.coherence-network/secrets/form-kernel-postgres-tunnel.json`

The local overlay is a machine-local `0600` file for native kernel probes through
an SSH tunnel. It is not repository memory and must never be committed.

Application configuration follows the project rule: config files first. Do not
add `DATABASE_URL` or environment-variable fallbacks to application code.

## Direct Production DB Proof

Run direct checks on the VPS without revealing secrets:

```bash
ssh -i ~/.ssh/hostinger-openclaw root@187.77.152.42 <<'SH'
cd /docker/coherence-network
docker compose exec -T postgres sh -lc \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "select current_database(), current_schema(), count(*) from graph_nodes where type = '\''idea'\'';"'
SH
```

Observed on 2026-06-05 during the direct VPS read:

```text
coherence|public|1656
```

The count is expected to move as the graph changes; the native route probes later
in the same session returned `pagination.total=1659`. The important proof is
that the live database is the `coherence` Postgres database inside the Hostinger
compose stack.

## Local Native-Kernel Access

For read-only native kernel probes from this machine:

1. Ensure the local overlay exists:
   `~/.coherence-network/secrets/form-kernel-postgres-tunnel.json`
2. Keep it mode `0600`.
3. Keep an SSH tunnel open to the current Postgres container IP.

Discover the container IP and open the tunnel:

```bash
POSTGRES_IP=$(ssh -i ~/.ssh/hostinger-openclaw root@187.77.152.42 \
  "cd /docker/coherence-network && docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' \$(docker compose ps -q postgres)")

ssh -i ~/.ssh/hostinger-openclaw -fN \
  -L 15432:${POSTGRES_IP}:5432 \
  root@187.77.152.42
```

Verify the tunnel:

```bash
lsof -nP -iTCP:15432 -sTCP:LISTEN
```

Run the Go kernel against the BML front-door catalog:

```bash
cd form/form-kernel-go
go run . serve --port 19086 \
  --config ~/.coherence-network/secrets/form-kernel-postgres-tunnel.json \
  --stdlib ../form-stdlib ../form-stdlib/json.fk ../../deploy/front-door/api.bml
```

Then curl the native route:

```bash
curl -sS -i -H 'Accept: application/json' \
  'http://127.0.0.1:19086/api/ideas?query=kernel&limit=2&sort=marginal_cc'
```

Current status on 2026-06-05: the native Go kernel reaches production Postgres
through the tunnel and local overlay. The route returns `200 OK` with
`X-Form-Router: native-kernel-go`; `/api/ideas?limit=2&sort=marginal_cc` returns
the same first idea and live total as the public FastAPI route. Do not describe
this as missing credentials.

Important route-contract note: native BML currently implements a free-text
`query` filter, while the public FastAPI `/api/ideas` route does not accept
`query`/`search` for the list endpoint. Use no `query` parameter for
apples-to-apples latency comparison, or explicitly treat `query=kernel` as new
native semantics.

Native observation route:

```bash
curl -sS -H 'Accept: application/json' -H 'X-Form-Observe: 1' \
  'http://127.0.0.1:19086/api/_form/ideas-observation?limit=2&sort=marginal_cc&event_limit=50000'
```

Native timing route:

```bash
curl -sS -H 'Accept: application/json' -H 'X-Form-Observe: 1' \
  'http://127.0.0.1:19086/api/_form/ideas-timing?limit=2&sort=marginal_cc'
```

Reusable timing probe:

```bash
python3 scripts/ideas_route_timing_breakdown.py --samples 40 --warmup 5
```

Observed on 2026-06-05:

- Full native route: `status=200`, body bytes `4226`, framebuffer event rows
  `36141`, aggregate count rows `132`.
- Full detail response with `event_limit=50000` returned every event row.
- Warmed in-kernel observation with `warm=40` returned `21` JIT compile-failed
  bodies, `75` warming bodies, and `0` dispatch-hit rows. Current misses point
  to missing list ABI plus string/JSON/node primitives, not to Postgres access.
- Next walked JIT pass on 2026-06-05 added a Go value ABI for list/string-shaped
  recipes, TS fallback/dispatch-miss accounting for list-shaped compiled calls,
  and Go JIT miss attribution that prefers the value-ABI reason when all ABIs
  fail. Warmed `/api/ideas` then returned `15` compile-failed bodies, `75`
  warming bodies, `6` compiled bodies, and `6` dispatch-hit bodies. The remaining
  top misses are now specific general primitives: `scan_run`, `_dict_get`,
  `intern_node_at`, `intern_trivial_float`, JSON emitter helpers, and node
  introspection (`node_category`, `node_children`, `node_type`).
- Comparable 40-request timing without `query`: native Go through local SSH
  tunnel `p50=551.986 ms`, `p95=630.708 ms`; public FastAPI
  `p50=261.254 ms`, `p95=1117.920 ms`.
- Fresh timing after the JIT value-ABI pass, still without `query`: native Go
  through local SSH tunnel `p50=560.926 ms`, `p95=748.992 ms`; public FastAPI
  `p50=263.719 ms`, `p95=1162.181 ms`. This pass improved compression and
  observability, not median latency yet.
- Next walked helper-call pass on 2026-06-05 added interprocedural value-ABI
  lowering for static Form helper families plus scanner/string primitives
  (`scan_run`, `substring`, `char_at`, `ord`, `byte_to_str`, `str_eq`). Warmed
  `/api/ideas` moved again to `11` compile-failed bodies, `76` warming bodies,
  `9` compiled bodies, and `8` dispatch-hit bodies; framebuffer event rows fell
  to `26394`. `scan_run` is no longer a top miss. Remaining top pressure is
  `node_value`, logic ops, `_dict_get`, `intern_node_at`,
  `intern_trivial_float`, and node introspection (`node_category`,
  `node_children`, `node_type`).
- Fresh timing after helper-call lowering: native Go through local SSH tunnel
  `p50=564.986 ms`, `p95=601.781 ms`; public FastAPI `p50=265.967 ms`,
  `p95=1090.011 ms`. Tail latency tightened; median still has not moved.
- Timing breakdown pass on 2026-06-05 added
  `/api/_form/ideas-timing`, which measures the BML handler internally without
  treating process startup, TCP accept, client network, or response write as
  optimizable handler cost. The same pass added
  `scripts/ideas_route_timing_breakdown.py`, which compares public FastAPI HTTP
  total, local native Go HTTP total, native handler segments, and Python
  same-SQL segments against the production Postgres tunnel.
- Public FastAPI over the internet for
  `/api/ideas?limit=2&offset=0&sort=marginal_cc`: `200`, body bytes `4450`,
  `p50=269.859 ms`, `p95=1087.374 ms`, `p99=1639.319 ms`.
- Local native Go over the SSH tunnel for the same route: `200`, body bytes
  `4226`, HTTP total `p50=547.091 ms`, `p95=1303.667 ms`,
  `p99=2078.092 ms`.
- Native handler-internal median split for the same route: `connect p50=248 ms`,
  `summary_query p50=137 ms`, `page_query p50=154 ms`, `params p50=1 ms`,
  `shape_tree p50=5 ms`, `json_emit p50=3 ms`, `handler_total p50=555 ms`.
  Median optimization attention is therefore connection reuse/pooling and query
  strategy before JSON/string work.
- Native handler tail split shows a different pressure: slowest requests assigned
  `1483 ms` to `shape_tree`, `1531 ms` to `json_emit`, or `748 ms` to parameter
  projection while DB segments stayed near median. Treat these as substrate
  allocation/GC/JIT/emitter attention, not Postgres attention.
- Python same-SQL microbreakdown against the same tunnel, using the BML SQL and
  fresh DB connection per sample: body bytes `4318`, `connect p50=215.906 ms`,
  `summary_query p50=93.528 ms`, `page_query p50=101.260 ms`,
  `shape_dicts p50=0.082 ms`, `json_dumps p50=0.102 ms`,
  `handler_total p50=412.903 ms`. This is not the production FastAPI service
  path; it isolates Python around the same SQL/JSON shape.

## Composted Paths

These paths are historical or local-dev only unless a new explicit deployment
decision revives them:

- Railway deployment and Railway Postgres are not the current production system.
- The Railway public URLs are stale.
- Railway CLI metadata does not prove current DB access.
- Supabase pooler credentials found locally are stale and not the production DB.
- Local `api/config/api.json` SQLite config is a development carrier, not proof
  of production data reach.
- Shell `DATABASE_URL` is not the configuration contract.

When docs, scripts, or comments present any of these as the live operational
path, update the current guide or compost the stale instruction.
