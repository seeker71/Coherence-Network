# Federating Instances — Two Forks, One Field

Two Coherence Network forks meet. Each runs its own API, its own
web, its own graph database. They want to circulate together —
share what's becoming, learn from what each other is tending, vote
together on what crosses between them, keep their own sovereignty
intact.

This is the walked practice for that. Not the architecture. The
actual commands two operators run to peer their instances today.

## What flows by which path

The body has two honest paths for content between instances:

| What flows | Path | Mechanism |
|---|---|---|
| Marketplace listings & forks | **REST** (automatic) | `POST /api/federation/marketplace/ingest` fires when a listing is created or forked |
| Lineage links between entities | **REST** (manual or scheduled) | `POST /api/federation/sync` with `lineage_links` array |
| Usage events / telemetry | **REST** (manual or scheduled) | `POST /api/federation/sync` with `usage_events` array |
| Concepts (`docs/vision-kb/concepts/lc-*.md`) | **git** | clone + cherry-pick + `sync_kb_to_db.py` |
| Specs (`specs/*.md`) | **git** | clone + cherry-pick + `generate_repo_indexes.py` |
| Ideas (`ideas/*.md`) | **git** | clone + cherry-pick |
| Teachings (`docs/vision-kb/guides/`, `docs/field/`, `docs/lineage/`) | **git** | clone + cherry-pick |

The REST path is governance-gated — every payload an instance
receives lands as a `ChangeRequest` of type `FEDERATION_IMPORT` and
auto-applies only after the receiving instance's quorum votes
through. The audit trail lives in `federation_sync_history`.

The git path is the body's source-of-truth for substance. Two
forks both reading and writing markdown — the same way the body
itself flows internally — is honest content federation today.

## Two operators, two instances

Alice runs `alice.coherencycoin.com`. Bob runs
`bob.coherencycoin.com`. Both have forked the repo. Both have the
API running, the web running, their own database.

### Step 1 — Register the peer on each side

On Alice's instance, register Bob:

```bash
curl -X POST https://alice.coherencycoin.com/api/federation/instances \
  -H "Content-Type: application/json" \
  -d '{
    "instance_id": "bob",
    "name": "Bob's Coherence Instance",
    "endpoint_url": "https://bob.coherencycoin.com",
    "trust_level": "pending"
  }'
```

On Bob's instance, register Alice:

```bash
curl -X POST https://bob.coherencycoin.com/api/federation/instances \
  -H "Content-Type: application/json" \
  -d '{
    "instance_id": "alice",
    "name": "Alice's Coherence Instance",
    "endpoint_url": "https://alice.coherencycoin.com",
    "trust_level": "pending"
  }'
```

Or with the CLI from either side:

```bash
coh federation register \
  --instance-id bob \
  --name "Bob's Coherence Instance" \
  --endpoint-url https://bob.coherencycoin.com
```

Verify each side sees the other:

```bash
coh federation instances
# or:
curl https://alice.coherencycoin.com/api/federation/instances
```

Both registrations land at `trust_level: pending`. That's the
intentional default — *we know each other but haven't said yes
yet*.

### Step 2 — Upgrade trust (mutual consent)

Trust levels: `unknown < pending < verified < trusted`. Higher
trust means more types of payload are accepted without manual
inspection.

To upgrade, re-POST with the new level. The `register_instance`
service path treats a second POST with the same `instance_id` as
an update (idempotent):

```bash
curl -X POST https://alice.coherencycoin.com/api/federation/instances \
  -H "Content-Type: application/json" \
  -d '{
    "instance_id": "bob",
    "name": "Bob's Coherence Instance",
    "endpoint_url": "https://bob.coherencycoin.com",
    "trust_level": "verified"
  }'
```

Both sides upgrade independently. There is no automatic mutual
handshake — each operator's decision to trust the other is an
explicit sovereign act. *(A trust-vouching handshake is on the
horizon; today the gesture is manual on each side.)*

### Step 3 — What automatically flows once peered

Once Alice and Bob have registered each other at trust_level
`pending` or higher:

- **Marketplace listings** Alice creates auto-broadcast to Bob's
  `/api/federation/marketplace/ingest`. Same the other direction.
  Each side dedupes on `listing_id`. Failures are logged
  fire-and-forget — they don't block Alice's local action.

- **Marketplace forks** propagate the same way. When someone
  forks Alice's listing on Bob's instance, the fork echoes back to
  Alice so the listing carries its full constellation.

This is the only currently-implemented automatic push.

### Step 4 — Sending lineage and usage events explicitly

Either side can push a payload of lineage links and/or usage
events with a single POST:

```bash
curl -X POST https://bob.coherencycoin.com/api/federation/sync \
  -H "Content-Type: application/json" \
  -d '{
    "source_instance_id": "alice",
    "timestamp": "2026-05-13T12:00:00Z",
    "lineage_links": [
      {
        "from_id": "concept:lc-arrival-as-recognition",
        "to_id": "concept:lc-frequency-routes-reception",
        "edge_type": "companion-teaching"
      }
    ],
    "usage_events": [
      {
        "asset_id": "lc-arrival-as-recognition",
        "actor_id": "contributor:seeker71",
        "kind": "concept_read",
        "ts": "2026-05-13T11:55:00Z"
      }
    ]
  }'
```

What happens on Bob's side:

1. The payload is verified — Bob must already have registered
   Alice as an instance and her trust_level must meet the
   threshold (`pending` is the floor for sync).
2. Each lineage link becomes a `ChangeRequest` of type
   `FEDERATION_IMPORT`. Each usage event becomes a separate
   `ChangeRequest`.
3. Bob's governance flow takes over — votes accumulate, auto-apply
   fires on quorum (currently the default `auto_apply_on_approval:
   true` for FEDERATION_IMPORT means a single approving vote moves
   it through).
4. The full payload is stored in `federation_sync_history` for
   audit.

Review what arrived:

```bash
curl https://bob.coherencycoin.com/api/federation/sync/history
# or via CLI:
coh federation sync-history
```

Pending change requests appear in normal governance:

```bash
curl https://bob.coherencycoin.com/api/governance/change-requests?status=open
```

### Step 5 — What still flows via git (everything substantive)

This is the honest part. Today, the REST payload carries
**telemetry and lineage edges, not substance**. Concepts, specs,
ideas, teachings travel through git.

Bob wants Alice's new concept `lc-gatherings-that-carry`:

```bash
# In Bob's local clone of the repo
git remote add alice https://github.com/alice-fork/Coherence-Network.git
git fetch alice main

# Cherry-pick the concept file
git checkout alice/main -- docs/vision-kb/concepts/lc-gatherings-that-carry.md

# Add the cross-references that file expects (if not already in Bob's body)
# Walk the file's "→ lc-x, lc-y" line and verify each target exists

# Sync into Bob's graph database
python3 scripts/sync_kb_to_db.py lc-gatherings-that-carry --api-key dev-key

# Regenerate INDEX
python3 scripts/generate_repo_indexes.py
```

Bob's concept is now part of his graph and his INDEX. His
operators can read it, his agents can resonate with it. Alice
authored; Bob received; both bodies hold it.

The same shape applies to specs, ideas, and teachings:

```bash
# A spec
git checkout alice/main -- specs/some-spec.md
python3 scripts/generate_repo_indexes.py

# An idea
git checkout alice/main -- ideas/some-idea.md

# A teaching (guide)
git checkout alice/main -- docs/vision-kb/guides/some-guide.md

# Field artifacts (lineage docs, field stories)
git checkout alice/main -- docs/field/alice/some-arc.md
```

Each instance keeps its own provenance. Each instance's git log
shows exactly what crossed in and from where. Nothing is hidden;
attribution is preserved by the commit author + the cherry-pick
trail.

## What this is not (yet)

The walked practice above works today. What it doesn't have yet:

- **Auto-discovery.** No `.well-known/coherence-federation`
  endpoint. Two operators have to know each other's URLs and
  explicitly register.
- **Trust handshake.** No vouching protocol — each side upgrades
  trust independently and manually.
- **Substance payload.** Concepts, specs, ideas, teachings still
  flow through git, not through `/api/federation/sync`. The
  governance-gated flow exists; the payload shape doesn't carry
  those types yet.
- **Scheduled sync.** No "every 24h push deltas" rhythm. Push is
  event-driven on marketplace actions; everything else is on
  demand.
- **Agent-facing MCP tools.** Agents can list federation nodes
  but can't yet *peer my instance with another instance* through
  MCP. Operators do this via curl or CLI today.

Each of those is a real next breath. Naming them honestly here so
an operator arriving doesn't expect what isn't there yet.

## CLI reference

The `coh federation` namespace covers most operational gestures:

| Command | What it does |
|---|---|
| `coh federation register --instance-id X --name "..." --endpoint-url ...` | Register a remote instance |
| `coh federation instances` | List registered instances |
| `coh federation instance X` | Inspect one instance |
| `coh federation sync` | Receive a sync payload (typically called by other instances) |
| `coh federation sync-history` | See past sync operations |
| `coh federation stats` | Network-wide measurement stats |
| `coh federation aggregates` | Federated aggregation results |
| `coh federation broadcast --message "..."` | Send to all nodes in your fleet |
| `coh federation msg --to NODE --message "..."` | Direct message to one node |

Plus the REST surface in [`api/app/routers/federation.py`](../api/app/routers/federation.py).

## A short story of two instances

Alice runs an instance focused on retreat and devotional practice.
Bob runs an instance focused on permaculture and land
stewardship. Both have ideas, specs, concepts that the other
might want.

Alice authors `lc-presence-as-ground` — a concept about how
ground beneath a body affects what arrives. She commits, pushes,
adds an INDEX entry, syncs to her DB.

Bob discovers it because he and Alice are peered and he gets a
notification when something in Alice's `docs/vision-kb/concepts/`
changes *(— this notification path isn't built yet; today Bob
discovers via watching Alice's repo or talking to her directly)*.
He fetches:

```bash
git checkout alice/main -- docs/vision-kb/concepts/lc-presence-as-ground.md
python3 scripts/sync_kb_to_db.py lc-presence-as-ground --api-key dev-key
```

His instance now holds the concept. His operators see it next
time they visit `/vision/lc-presence-as-ground`. His agents
resonate it into idea retrieval. Both bodies are circulating the
same teaching, each through its own sovereign infrastructure,
neither one the source of truth for the other.

When marketplace listings arrive — say Alice publishes a retreat
weekend listing — those flow automatically. Alice doesn't have to
cherry-pick; Bob's instance receives via REST and adds it through
governance.

Both bodies stay sovereign. Both bodies stay connected. The
substance circulates by gift, the governance gates the flow, the
audit trail names every crossing.

## The next breaths the body is moving toward

The walked practice today is honest but partial. The body is
moving toward:

1. **Extended `FederatedPayload`** that carries `concept_proposals`,
   `spec_proposals`, `idea_proposals`, `teaching_proposals` — so
   substance flows through the same governance-gated REST path
   that lineage and usage already use. Git stays available, but
   the API becomes capable of substance-level exchange.

2. **`.well-known/coherence-federation`** for auto-discovery.
   Operators arriving at an unknown instance can fetch its
   federation manifest and propose peering through one gesture
   rather than several.

3. **A trust handshake** that's mutual and explicit — Alice
   proposes trust, Bob accepts, both sides upgrade in the same
   atomic gesture.

4. **MCP tools** for agent-driven peering. An agent reading this
   doc today does the work via shell + curl; the body wants
   first-class affordances so agents can offer "we should peer
   with X" as a real action.

Each of these is its own breath. None is rushed. Each grows when
the body has appetite.

## Companions

- [`specs/federation-network-layer.md`](../specs/federation-network-layer.md)
  — the architectural layer
- [`specs/federation-aggregated-visibility.md`](../specs/federation-aggregated-visibility.md)
  — network-wide visibility (draft)
- [`docs/JOIN-NETWORK.md`](JOIN-NETWORK.md) — joining as a compute
  node (different shape from joining as a federated instance —
  see below)

## Note: instance ≠ node

The body has two federation shapes that share the word *node*:

- A **compute node** is what `docs/JOIN-NETWORK.md` describes —
  someone running `python scripts/local_runner.py` on a machine
  to pick tasks from a hub's portfolio. The hub is one Coherence
  instance; the compute node is a worker.
- A **federated instance** is what this doc describes — a full
  Coherence fork running its own API/web/database, peering with
  other forks at the substance level.

A single operator might run both: an instance, with one or more
compute nodes registered under it. Both contribute to the same
body's circulation.

— *Written from the walked path, not the planned one. Every
command above runs today; every gap above is named honestly.
Future breaths grow this doc with the substance-payload extension,
the .well-known discovery, the trust handshake, the agent
affordances — added at the body's own pace as they land.*
