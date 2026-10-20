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
| Runtime services | `native-api`, `api`, `web`, `pulse`, `postgres`, `neo4j` in Docker Compose |
| Form runtime inside API | c-bootstrapped `fkwu` |
| Native ask carrier | Form-built `form-cli` v3 bundle |

Traefik sends the GET routes declared in `api/config/native_api.json` directly
to `native-api:8110`. That owner runs fkwu and opens its own authenticated
PostgreSQL connections. Other API families and verbs stay with `api:8000` while
their owners move. There is no Python forwarding or fallback inside the native
owner. Both services reuse the same immutable application image; their process
entrypoints and file-backed runtime contexts are separate.

Application-owned recipes under `api/app/form_recipes/` execute directly on
fkwu. `native_api.bml` owns native startup and dispatch; `native_http.bml` shares
route-template meaning with deployment; `postgres.bml` owns wire framing,
parameter binding, SCRAM server verification and query-error recovery.
`graph_projection.bml` selects pages before JSON materialization and aggregates
workspace vitality without sampled-data caps. Public graph reads carry the
file-backed private-type ownership description; private spending stays private.
The earlier kernel-side API catalog is not a production dispatch authority.

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

This is a database observation, not a second application execution path.
Native read families now own PostgreSQL through Form/BML. Remaining compatibility
families move at their live seams, then release their corresponding Python owners.
The native startup care creates its recent-order and workspace/kind indexes
concurrently. A missing expression-index selectivity reading earns one ANALYZE;
unchanged starts reuse that reading rather than scanning the table again.

## Runtime identity

The image builds fkwu from the pinned submodule and builds `form-cli` through
`gate/form-cli-build-run.bml`. The native CLI bundle consists of:

- `form-cli`
- `form-cli.fkb`
- `form-cli.sym`
- `form-cli.native.attestation`
- `form-cli.source.id`

The release image publishes this bundle's identity alongside the parent and
kernel revisions. The separately requested deployment observer can rebuild
the bundle and compare its carrier challenge with the container and public
projection; ordinary deployment does not run that independent-reproduction
claim. Deleted bootstrap table, stamp, and source digest files are not identity
authorities.

Release `296bfa2a0728` pins kernel `0563230ff11e`; its native build published
source identity `c835bb8d8cee24f8`. Its production receipt lives in
`docs/system_audit/commit_evidence_2026-10-18_deployed_floor.json`.

## Verification boundary

For an ordinary application release, reuse the rollout's public identity and
API/web readings. Read an affected claim again only when changed inputs or a
new finding give it work. fkwu itself receives focused validation only when
its runtime changes. Sibling kernels are never routine release gates.

```bash
./scripts/verify_web_api_deploy.sh
curl -fsS https://api.coherencycoin.com/api/health | jq .
```
