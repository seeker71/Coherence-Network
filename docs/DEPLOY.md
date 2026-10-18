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
bounded health does not observe those claims. Native `pulse_proof_care.bml`
preserves the store and archives the two stale silences as retired proof work,
not as successful observations.

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

`git pull` in `/docker/coherence-network/repo` alone deploys nothing (a real
hour was nearly lost to this on 2026-07-01 — the container rebuilt cleanly and
still served the old code). After merge to `main`:

```bash
NEW_SHA=$(git rev-parse origin/main)   # run in a Coherence-Network checkout — NOT another repo
ssh -i ~/.ssh/hostinger-openclaw root@187.77.152.42 \
  "cd /docker/coherence-network && \
   cp docker-compose.yml docker-compose.yml.bak && \
   sed -i \"s|Coherence-Network.git#[0-9a-f]\\{40\\}|Coherence-Network.git#$NEW_SHA|g\" docker-compose.yml && \
   docker compose build api web && docker compose up -d api web"
```

Note: the SHA pin is shared across services (api, web, pulse);
updating it moves them all, and `up -d` recreates containers whose config
changed even if their image did not rebuild. Verify the SHA is a commit in
*this* repo before patching — `git branch --contains $NEW_SHA` should answer.

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
