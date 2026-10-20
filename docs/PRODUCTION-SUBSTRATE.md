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
| Runtime services | `native-api`, `api`, `web`, `pulse`, `postgres` in Docker Compose |
| Form runtime inside API | c-bootstrapped `fkwu` |
| Native ask carrier | Form-built `form-cli` v3 bundle |

Traefik sends the routes declared in `api/config/native_api.json` directly
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

`native_health.bml` observes health, readiness, persistence shape and PostgreSQL
write-lane contention through the same native connection boundary. Probe reads
do not execute audit-ledger verification, native-carrier challenges or witness
rebuilds. The Python probe owner retains only its own lightweight ping/version
surface; the native owner does not speak for that separate process's liveness.
`native_substrate.bml` carries page/source resolution, kernel-status observation,
public source offers and native cell reads. `native_named_persistence.bml` owns
content-addressed values and named cells in PostgreSQL; prior lattice tables are
read projections, not a duplicate live Python writer.

`native_instance_pulse.bml` owns the instance self/now aliases and stored peer
read. It derives present breath from the native request and PostgreSQL resources,
not a second thread pool of local probes. File-backed federation configuration
offers instance identity and visibility; the existing peer polling writer still
owns its actual stored observations.

The image retains the canonical source home under `/app/form`, with stdlib at
`/app/form/form/form-stdlib` and the original `/app/form/control` and
`/app/form/runtime` directories. No duplicated import tree or runtime-source
alias defines another authority.

PostgreSQL owns application graph storage and traversal. Neo4j has no live
application caller: its service, driver and legacy discovery sensor are retired.
Native Compose care removes explicitly released service owners and their
dependency references, then releases project volumes only when no surviving
service holds them. This release does not introduce a replacement Neo4j probe.

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

The release image records the parent and kernel revisions in immutable
`/app/config/image_identity.json`. Native health reads that file rather than a
host-side release stamp, so a queued release cannot rename the serving image.
The separately requested deployment observer owns independent reproduction and
its authenticated nonce/carrier challenge; ordinary deployment and health reads
do not perform or claim that result. Deleted bootstrap table, stamp, and source
digest files are not identity authorities.

Release `296bfa2a0728` pins kernel `0563230ff11e`; its native build published
source identity `c835bb8d8cee24f8`. Its production receipt lives in
`docs/system_audit/commit_evidence_2026-10-18_deployed_floor.json`.

## Verification boundary

For an ordinary application release, reuse the rollout's public identity and
API/web readings. Read an affected claim again only when changed inputs or a
new finding give it work. fkwu itself receives focused validation only when
its runtime changes. Sibling kernels are never routine release gates.
Audit, schema, provider and witness readings stay with their own changed claim,
not every health/readiness request or ordinary release. Pulse's native parallel
trace retains response evidence and timing when a probe finding earns attention.

```bash
./scripts/verify_web_api_deploy.sh
curl -fsS https://api.coherencycoin.com/api/health | jq .
```
