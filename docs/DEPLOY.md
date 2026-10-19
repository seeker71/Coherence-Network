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

Public deployment completes with the serving revision and API/web route
observation. Independent reproducibility and authenticated witness work remain
separate claims: their identity checks stay intact, and no automatic second
kernel build or stale observer workflow pin is imposed on every deployment.
The release read reuses public health, API/web revision parity, the web root,
and CORS. Kernel status assertions, deleted-router canaries, unrelated profile
pages, assets, provider readiness, persistence, Telegram and pulse readings are
not recurring release gates. When one of those surfaces changes or signals an
issue, follow that finding at its source with the smallest relevant observation.
Pulse's schema/audit proof registrations have retired for the same reason:
bounded health does not observe those claims. Their historical retirement notes
remain in the silence ledger; the completed two-record retirement action is
released. Native `pulse/snapshot.bml` supplies reusable private online backup and
snapshot-backed native rollout care without rewriting historical receipts.
The compatibility health carrier reuses its native observation while artifact
bytes hold. A fifteen-second challenge-expiry timer has retired; changed carrier
bytes or explicit care give the observation work, not elapsed time alone.
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
TLS probes, cadence and query/repair templates are BML on the pinned fkwu; SQLite
is the single durable external resource, crossed once per round or database read.

Ordinary runtime telemetry invalidates its own event view, not provider facts.
The retired cross-service flush took the provider-refresh lock on the API event
loop, stalled `/api/ping`, and caused Docker/Traefik to withdraw the API route.
Provider collection keeps its own refresh and invalidation. Follow a new latency
finding with `pulse_latency_trace.bml`: one parallel HTTP wave retains private
bodies/headers and separates network timing from the serving runtime header.
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
Keep the image's native source home coherent: `/app/form/form-stdlib` pairs
with `/app/runtime`, just as the checkout's `form/form/form-stdlib` pairs with
`form/runtime`. The carrier derives runtime resources from that stdlib home.
`native_image_layout_care.bml` can publish the unchanged pinned resources at the
canonical live path while the corrected image assembles; the image retires the
former location rather than keeping a duplicate path or adding a kernel patch.
The query template has no runtime inputs: materialize it through fkwu once at
the immutable image's service initialization, then bind the source point at the
database door. Repeated source staging/compilation is not per-request work; a
changed image/source activates a new native template, not a wall-clock expiry.

The native build enumerates its private source copy with Form's
`source-tree.bml`; Docker snapshots need no usable Git metadata. Build scope
reads the serving container's immutable revision label. A failed build may
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
