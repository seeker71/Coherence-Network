# Production substrate

This is the current production memory for API, web, native Form execution, and
durable data. Railway, Supabase, the deleted kernel-router overlay, and sibling
kernel deployment paths are historical rather than live topology.

## Current topology

| Surface | Current carrier |
|---|---|
| Public API | `https://api.coherencycoin.com` |
| Public web | `https://coherencycoin.com` |
| Host | Hostinger VPS `187.77.152.42` |
| Deploy root | `/docker/coherence-network` |
| Repo on host | `/docker/coherence-network/repo` |
| Front proxy | Traefik behind Cloudflare |
| Runtime services | `api`, `web`, `postgres`, `neo4j` in Docker Compose |
| Form runtime inside API | c-bootstrapped `fkwu` |
| Native ask carrier | Form-built `form-cli` v3 bundle |

Traefik sends API traffic to `api:8000`. The API container is the current
compatibility HTTP host and contains only one Form runtime: fkwu. There is no
Go/Rust/TypeScript kernel-router service, native-preview header overlay, or
Python-fallback fanout in the current deployment.

Application-owned recipes under `api/app/form_recipes/` execute directly on
fkwu. The native BML application catalog at
`form/form/apps/coherence-network/api.bml` is the destination host surface;
its route families become public only when fkwu owns their HTTP dispatch,
configuration, persistence, and startup effects end to end.

## Configuration and credentials

Do not paste credentials into chat, docs, logs, commits, shell history, or task
cards.

Current production carriers are:

- VPS configuration: `/root/.coherence-network/config.json`
- VPS Compose secrets: `/docker/coherence-network/.env`

Postgres is internal to the Docker Compose network and is not publicly
exposed. Application configuration remains file-backed. Do not add
environment-variable fallbacks to application code.

## Direct database observation

When database state itself is the subject, observe it inside the VPS without
printing credentials:

```bash
ssh -i ~/.ssh/hostinger-openclaw root@187.77.152.42 <<'SH'
cd /docker/coherence-network
docker compose exec -T postgres sh -lc \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "select current_database(), current_schema(), count(*) from graph_nodes;"'
SH
```

This is a database observation, not a second application execution path. The
remaining production work is to move Postgres ownership into the fkwu/BML
application host and then remove each corresponding Python owner.

## Runtime identity

The image builds fkwu from the pinned submodule and builds `form-cli` through
`gate/form-cli-build-run.bml`. The native CLI bundle consists of:

- `form-cli`
- `form-cli.fkb`
- `form-cli.sym`
- `form-cli.native.attestation`
- `form-cli.source.id`

The deployment observer rebuilds that bundle from the pinned kernel source and
compares its v3 carrier identity and challenge with both the deployed container
and the public health projection. Deleted bootstrap table, stamp, and source
digest files are not identity authorities.

## Verification boundary

For an ordinary application release, use the repository deployment checks and
public API/web verification. fkwu itself receives focused validation only when
its source changes. Sibling kernels are never routine release gates.

```bash
./scripts/verify_web_api_deploy.sh
curl -fsS https://api.coherencycoin.com/api/health | jq .
```
