# Coherence Network — Deploy Guide

Production runs on the Hostinger VPS, not Railway. The current API and web
domains are:

- API: `https://api.coherencycoin.com`
- Web: `https://coherencycoin.com`

Read [`PRODUCTION-SUBSTRATE.md`](PRODUCTION-SUBSTRATE.md) before touching
database access, native kernel DB probes, or deployment credentials.

## Quick Deploy

Land a kernel dependency before the application PR that pins it. Deploy the
merged application commit through Hostinger Auto Deploy and read the public
API/web identity once the rollout completes. Reuse focused evidence while its
source and inputs hold; a new failure gives its owning surface new work.

Delivery policies live here as care reminders. Read review findings against the
current source, preserve useful findings with their owner, and observe only the
changed claim. Approval counts, resolved-thread flags, linear-history rules,
and routine broad suites do not gate landing. Main's active ruleset retains
branch-deletion and force-push protection, which also preserves the protected
ref identity used by the authenticated deployment observer.

The reminder itself is Form/BML:

```bash
cd form && ./fkwu ../api/app/form_recipes/delivery_care.bml
```

The native API owner reuses the application image with a fkwu entrypoint,
not the compatibility Python process. Its routes, template parameters and port
come from `api/config/native_api.json`. Compose care derives the public host
from the existing API owner and publishes the native route bindings atomically.
`mode: "observe"` reports only the image, routes and dependency plan. After the
merged image is built, apply the same care request with `activate: ["native-api"]`.
Keep its private config mount and `/app/form` assembly/runtime context together.
The image preserves the pinned source home: stdlib lives at
`/app/form/form/form-stdlib`, with `/app/form/control` and `/app/form/runtime`
beside it. Native imports use that one layout, not duplicated alias trees.
The compatibility service depends on that native owner; subsequent image updates
raise the dependency before the compatibility process. There is no native-to-Python
request fallback. Retire replaced Python route owners after the public handoff.
Current literal routes remain more specific than new parameter templates.
Compose care reads those declarations from their existing source owners rather
than inventing a reserved-name list or forwarding an unresolved native request.

`native_health.bml` owns public health, readiness, persistence and write-lane
observations on that same fkwu JIT. Each reads its live PostgreSQL dependency;
ordinary probes do not traverse the audit ledger, spawn kernel challenges, or
rebuild deployment witnesses. Release identity comes from the image's immutable
`config/image_identity.json`, not the host configuration for a queued successor.
The compatibility process keeps its own `/api/ping` liveness probe; a native
success is not evidence that a separate Python process is alive.

`native_instance_pulse.bml` shares one live native request/persistence reading
between `/api/pulse/self` and `/api/pulse/now`, with instance identity and
visibility supplied by file-backed federation configuration. Its peers read
returns the real stored federation observations. The Python self-check pool,
schema probe and environment-based identity/privacy switches are retired;
the active federation peer writer keeps its record ownership until that effect
moves natively too.

`native_substrate.bml` owns the public page binding, kernel-status observation
and source-offer door. `native_named_persistence.bml` holds reusable native
values and named cells in PostgreSQL. Existing lattice rows remain read
projections while their callers move, not a second Python write authority.
`native_health_observation.bml` carries the separately requested authenticated
target/nonce observation. Ordinary probes never enter that expensive effect;
it is not a scheduled audit or kernel validation band.

PostgreSQL owns application graph state and traversal. The unused Neo4j service,
driver and discovery probe are retired. Compose care accepts explicit released
service names, removes their dependency references and releases only project
volumes no remaining service holds; unrelated state stays with its owner.

Native assembly admits the application images once on tmpfs. Source admission,
one affected native route observation and the actual rollout answer this change;
routine kernel suites and historical response-contract comparisons do not.
Database care belongs to `native_api_prepare.bml`: concurrent indexes and a
missing selectivity reading, not TTL response masking or per-request discovery.

Hostinger deploy runs on a changed release or explicit request. The independent
public-deploy contract is available on demand; scheduled redeploys and scheduled
full-suite gates have retired.

Native image builds mount tmpfs at `/dev/shm`. fkwu's shared cell/program
arenas grow with the Form compilation; Docker's default 64 MiB mount caused
`SIGBUS` during `bml-floor-compile.fk` in run 39130139264. Keep the native build
on that shared-memory surface. Image assembly verifies artifact integrity;
runtime observations belong to the changed claim and release receipt.

The VPS's former five-minute redeploy cron is retired too. The Form/BML
`deployment_schedule_care.bml` action preserves the prior crontab on the host
and removes only the recurring deploy entry. Other schedules stay with their
owners.

Retrieval/index maintenance follows changed sources. The former post-rollout
Python bootstrap and text-format grounding gate have retired: they duplicated
the content migration and asserted the released host CLI's output contract.
Keep retrieval findings as native Form work with their source and owner.
`api/app/form_recipes/source_maintenance.bml` accepts explicit changed source
coordinates. Each child owns a separate input file; a Docker child cannot consume
the remaining paths of an inherited shell loop. The existing Python ARTIFACT/DB
projection and RAG coordinator remain named retiring migration doors, not release
requirements. BML owns the maintenance sequence and care; embedding runs on fkwu.
The former automatic shell ingest/heal release stage is retired. A stale binding
earns repair at its source, without relabeling a completed application rollout.

Public deployment completes with the serving revision and API/web route
observation. Independent reproducibility and authenticated witness work remain
separate claims: their identity checks stay intact, and no automatic second
kernel build or stale observer workflow pin is imposed on every deployment.
The rollout binds its native serving image and local health to its explicit target,
then observes the public host, API health, web root and CORS. A newer `main`
commit is queued work; an unchanged web image keeps its own identity. The former
moving-main API/web parity loops duplicated the owned-target boundary and could
hold the deployment lock while waiting for the next queued release behind that
same lock. Those loops and their timer fixture are retired. Independent
authenticated reproduction retains its source and identity checks.
Kernel status assertions, deleted-router canaries, unrelated profile
pages, assets, provider readiness, persistence, Telegram and pulse readings are
not recurring release gates. When one of those surfaces changes or signals an
issue, follow that finding at its source with the smallest relevant observation.
Pulse's schema/audit proof registrations have retired for the same reason:
bounded health does not observe those claims. Their historical retirement notes
remain in the silence ledger; the completed two-record retirement action is
released. Native `pulse/snapshot.bml` supplies consistent Form-store snapshots
without external database tools or rewriting historical receipts.
The public probe owners and the diagnostics overview's duplicate health and
persistence evaluations are retired from Python. The verifier's unused Pulse,
CSS, persistence, provider and Telegram gate functions and their obsolete
fixtures are retired too. The live release observation remains public API
health, web reachability and CORS. A separately requested authenticated observer
owns its nonce challenge and independent reproduction; ordinary health does not
perform that work or claim its result. Changed carrier bytes or explicit care
give that observation work, not elapsed time alone.
Retirement includes persisted deployment configuration as well as containers.
The native `deployment_compose_care.bml` action removes released router service
owners from the host's Compose model, preserving a private source backup and
publishing atomically. The shared unobserved-sample marker remains available to
pulse history analysis after the recurring proof probes retire.
Compose's build-argument references and writable-state binds are persistent
configuration, preserved by the native model edit. The retired line-oriented
Python writer dropped mount targets from canonical YAML; it no longer rewrites
or gates this model on every release. Changes to those fields belong in native
configuration care, with their current inputs and owner.
The same care action moves web routers onto one service owner before releasing
duplicate port declarations and the superseded two-host Hati router. The current
five-host Hati route stays intact; `www.coherencycoin.com` names its service
explicitly. Compose label arrays and maps share one native editable model.
Pulse builds from the repository root through `pulse/Dockerfile`, keeping the
original `pulse_data:/data` volume. File-backed `pulse/config.json` owns its
application settings; native Compose care retires PULSE_* environment values and
supplies the fkwu shared-memory resource. Image assembly realizes application BML
once on native tmpfs, and requests reuse those images. Pulse's socket listener,
TLS probes, cadence, persistence and query/repair templates are BML on the pinned
fkwu. Native Recipe pages and checksummed transaction logs replace the SQLite
engine. The completed SQLite importer and its startup/configuration path are
retired. Startup opens and recovers native pages directly. Private snapshots are
available recovery resources, not routine release gates. Follow an actual
persistence finding with its smallest native observation, not kernel suites.

The `/pulse` web route belongs to that same native owner. Compose care gives its
exact path on the existing web hosts priority over the Next.js router,
preserving the independent Pulse origin and unrelated web routes. Publish this
file-backed route configuration without activation before the merged rollout;
Compose derives the host expression from its existing web routers rather than
holding a second host list, and activates it with the new Pulse image. The Next.js Pulse family and its
cross-origin configuration are retired. Native HTML reads one coherent snapshot,
discloses complete day/archive evidence, and sends no hydration payload.
Its response forbids proxy transformations and scripts while retaining no-store
freshness. Observe the public HTML, not just the origin response: an injected
analytics beacon is a boundary finding, not native page code. Source-keyed
closed-endpoint indexes provide exact silence counts without decoding the archive
on every page; disclosure still reads every matching original receipt and note.
On the first indexed startup, native workers derive daily cards and exact range
summaries from retained daily history. Later starts compare raw-day sequence
coordinates and reconcile only changed sources, including writes from an older
service during handoff. Keep the existing volume and recovery copies. This
derivation is application startup, not a kernel validation run.
Readiness dispatch is Form/BML emitted through fkwu's RAM-image JIT. Linux images
carry their explicit ISA tag; an ARM image is never admitted as x86. The listener
admits its read cells once and retains held values in private copy-on-write request
contexts. Keep Pulse's `FK_STORE_PRIVATE` configuration with this ownership:
both values and JIT program pages must stay private, not merely the global node
field. A pre-fork completion pipe wakes the owner when the request exits. No external
server, replica, request-file adapter or nested executable serves the route.
Read views hold only brief checkpoint boundaries, not the writer lock through
rendering. The ending boundary waits out in-flight publication and re-enters a
crossed version before a response can leave. Observe independent health/document
progress beside a long archive read when this dispatch or ownership changes.

Ordinary runtime telemetry invalidates its own event view, not provider facts.
The retired cross-service flush took the provider-refresh lock on the API event
loop, stalled `/api/ping`, and caused Docker/Traefik to withdraw the API route.
Provider collection keeps its own refresh and invalidation. Follow a new latency
finding with `pulse/trace.bml`: one native parallel HTTP wave retains private
bodies/headers and reports total and serving runtime time separately. The curl
trace is retired; unexposed DNS/connect/first-byte timestamps are not inferred.
The retiring HTTP membrane gives synchronous readiness, contention, idea reads
and vitality calls to its existing synchronous dispatch rather than claiming the
event loop. No extra pool or second implementation sits beside Form. Native
`runtime_read_care.bml` declares the worker-history source/time access path and
builds its PostgreSQL index online; a fresh store or changed read shape gives
that schema care work, not a recurring full-table scan on every release.
Anonymous meeting summaries follow the same shape: `anonymous_trace_query.bml`
owns the ordered, source-point-bound read; the existing Form/SQL membrane only
passes bound values and rows. The matching native schema blueprint indexes the
source expression and update order. This retains full same-browser history and
the global view without loading every event for each meeting write. The source
carrier enters fkwu normally so its native grammar discovery carries BML; the
obsolete raw-reader forcing flag has retired.
Keep the image's native source home coherent: `/app/form/form/form-stdlib`,
`/app/form/control` and `/app/form/runtime` retain the pinned checkout layout.
The image owns these resources; the transitional live-copy repair is retired.
The query template has no runtime inputs: materialize it through fkwu once at
the immutable image's service initialization, then bind the source point at the
database door. Repeated source staging/compilation is not per-request work; a
changed image/source activates a new native template, not a wall-clock expiry.

The native build and form-cli private-body flow enumerate source copies with
Form's `source-tree.bml`. Docker snapshots need no usable Git metadata: actual
files own the source set, and the existing sealed closure owns build identity.
The retired `git ls-files` call mistook a refused snapshot pointer for an empty
body. Keep that finding at the source reader, not a Docker-specific bypass.
This consumer pins immutable fkwu source commits from kernel `main`; `.gitmodules`
tracks that same authority. The optional curated distribution is not a second
place to author fixes or a release gate. The accepted source seal and observed
image establish the deployed revision. Keep retired limitations retired on main
as well as in any distribution carry.
Native bundle copy publication carries recipe, symbols, attestation and the
source-ID derivative from that same verified seal, with the executable renamed
last. Keep missing bundle artifacts with that publisher rather than synthesizing
identity in Docker or a host-language adapter.
Build scope reads the serving container's immutable revision label. A failed build may
advance the VPS checkout without advancing the running image, so the checkout
alone does not establish the deployed comparison base.

Keep that serving revision as the comparison base even in a shallow checkout;
an unavailable diff asks for the existing complete service build. Native build
caching follows the pinned Form source, while the final API image carries the
application revision. Git metadata and a parent-only revision change do not
invalidate an unchanged native bundle.

Publish retiring host carrier files by same-directory rename. Transfer to an
`.incoming` name, set its mode, then rename it into place. A running Bash
process keeps its open inode while a later release receives the new file.
Overwriting that open file caused a parse error after a successful native build
when a second runner synced the carrier at 13:23:51 UTC on 2026-10-18.

**The images do NOT build from the VPS repo checkout.** Each service in
`/docker/coherence-network/docker-compose.yml` builds from a GitHub context
**pinned to a commit SHA**:

```yaml
context: https://github.com/seeker71/Coherence-Network.git#<sha>
```

`git pull` in `/docker/coherence-network/repo` alone deploys nothing. The merged
release triggers Hostinger Auto Deploy; its explicit dispatch accepts a commit
SHA when a release needs resuming. The deploy carrier advances the pinned image
contexts. The former manual text-rewrite path has retired; persistent model
changes belong to native Compose care.

Note: the SHA pin is shared across services (api, web, pulse);
updating it moves them all, and `up -d` recreates containers whose config
changed even if their image did not rebuild. Verify the SHA is a commit in
*this* repo before patching — `git branch --contains $NEW_SHA` should answer.

The deploy action reads public API/web revision parity, root and CORS. For a
pulse finding, also read the affected witness state:

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
| Services | `native-api`, `api`, `web`, `pulse`, `postgres` |
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
