# Spec 121: OpenClaw Idea Marketplace

**Depends on**: Spec 119 (Coherence Credit), Spec 120 (Federation Layer), Spec 048 (Value Lineage)
**Depended on by**: Spec 122 (Crypto Treasury Bridge), Spec 123 (Transparent Audit Ledger)

## Purpose

The Coherence Network currently operates as a single-instance knowledge system. OpenClaw is a multi-user collaborative platform whose users generate, refine, and implement ideas. This spec turns the Coherence Network into a shared knowledge layer for OpenClaw by enabling any OpenClaw user to publish ideas into a cross-instance marketplace, browse and fork ideas from other users, and receive CC-denominated reputation credit when their ideas are adopted downstream. The marketplace uses the existing federation protocol (spec 120) for cross-instance sync and the value lineage service (spec 048) to trace adoption evidence back to original authors. Without this, ideas stay siloed inside individual instances and contributors receive no measurable credit for the spread of their work.

## Resonance Mechanics

Ideas flow through the marketplace based on resonance — natural selection by the network, not curation by a committee.

1. **Publishing is permissionless with quality gates** — Any idea with confidence ≥ 0.3 and at least one evidence-backed value basis can be published. No approval committee. The quality gate ensures minimum coherence, not editorial judgment.

2. **Forking is the signal** — When someone forks your idea, builds on it, and generates evidence of value, that's resonance. The attribution flows back automatically through the value lineage (spec 048). Popular ideas naturally accumulate more CC attribution.

3. **No promotion, no featuring, no algorithmic boost** — The browse endpoint returns ideas sorted by actual evidence-backed metrics (fork count, total downstream value, coherence score). There's no "featured" section, no paid placement, no engagement optimization. The sorting IS the curation.

4. **Dead ideas fade naturally** — Ideas with no forks, no evidence, and declining confidence lose visibility in browse results over time. They're never deleted (transparency), but they naturally sink. No manual archiving needed.

5. **Cross-instance resonance** — When an idea published on instance A is forked on instance B and generates value on instance C, the attribution chain is fully traceable across all three instances via the federation protocol. The network's coherence spans instances.

## Requirements

- [ ] **R1: Idea publishing** -- An authenticated OpenClaw user can publish an existing Idea to the marketplace via `POST /api/marketplace/publish`. The published listing includes the idea's id, name, description, author identity (instance + user), potential_value, estimated_cost, confidence, tags, and a content hash for integrity verification.
- [ ] **R2: Marketplace browsing** -- Any user can browse published ideas via `GET /api/marketplace/browse` with pagination, tag filtering, sort by recency or popularity, and full-text search on name/description. Results include origin instance, author, publish date, fork count, and aggregate adoption score.
- [ ] **R3: Idea forking** -- A user can fork a published idea via `POST /api/marketplace/fork/{listing_id}`. Forking creates a local copy of the idea linked to the original via a `forked_from` reference. The fork event is recorded in the audit ledger (spec 123) and propagated to the origin instance via federation sync.
- [ ] **R4: Spread tracking and CC attribution** -- When a forked idea progresses through the value lineage (spec 048) stages (spec creation, implementation, review, usage), the measured value flows back to the original author as CC credit. Attribution uses the existing payout-preview weights with a new `origin_author` role at 10% of measured value.
- [ ] **R5: Federation sync for marketplace** -- Published listings are synced across federated instances using the federation protocol (spec 120). Each listing is wrapped in a `FederatedPayload` with type `MARKETPLACE_LISTING`. Fork events are synced as `MARKETPLACE_FORK` payloads. Sync is pull-based: instances poll peers on a configurable interval (default 5 minutes).
- [ ] **R6: OpenClaw plugin interface** -- The marketplace exposes a plugin manifest at `GET /api/marketplace/manifest` that conforms to OpenClaw's extension registration format. The manifest declares capabilities (publish, browse, fork), required permissions (read ideas, write ideas, read user identity), and webhook endpoints for event notifications.
- [ ] **R7: Reputation scoring** -- Each marketplace author accumulates a reputation score computed as: `reputation = sum(adoption_value_cc * confidence) / (1 + age_penalty)` across all their published ideas. Reputation is queryable via `GET /api/marketplace/authors/{author_id}/reputation`.
- [ ] **R8: Anti-spam and quality gate** -- Publishing requires the idea to have confidence >= 0.3 and at least one non-empty `value_basis` entry (spec 119). Ideas failing this gate receive a 422 response with specific field-level errors.
- [ ] **R9: Duplicate detection** -- On publish, the system computes a content hash (SHA-256 of normalized name + description) and rejects listings that match an existing active listing's hash. Response: 409 Conflict with the existing listing ID.

## Research Inputs (Required)

- `2026-03-18` - Spec 119 Coherence Credit models -- CC denomination for marketplace value flows
- `2026-03-18` - Spec 120 Federation Layer -- cross-instance sync protocol that marketplace builds on
- `2026-03-18` - Spec 048 Value Lineage -- attribution pipeline that traces adoption back to authors
- `2026-03-20` - OpenClaw plugin specification (draft) -- extension manifest format for third-party integrations
- `2026-03-18` - Spec 094 Governance -- change request model used for marketplace moderation

## Task Card (Required)

```yaml
goal: Implement cross-instance idea marketplace with publish, browse, fork, and CC attribution
files_allowed:
  - api/app/models/marketplace.py
  - api/app/services/marketplace_service.py
  - api/app/routers/marketplace.py
  - api/app/main.py
  - api/tests/test_marketplace.py
  - api/app/models/federation.py
  - api/app/services/federation_service.py
  - specs/121-openclaw-idea-marketplace.md
done_when:
  - POST /api/marketplace/publish creates a listing and returns 201
  - GET /api/marketplace/browse returns paginated listings with filtering
  - POST /api/marketplace/fork/{listing_id} creates local idea copy with forked_from link
  - Fork events propagate CC attribution to origin author via value lineage
  - GET /api/marketplace/manifest returns valid OpenClaw plugin manifest
  - Duplicate publish returns 409
  - Low-quality publish returns 422
  - All tests in test_marketplace.py pass
commands:
  - python3 -m pytest api/tests/test_marketplace.py -x -v
  - python3 -m pytest api/tests/test_value_lineage.py -x -q
  - python3 -m pytest api/tests/test_minimum_federation_layer.py -x -q
constraints:
  - No modifications to existing idea model fields (additive only)
  - Federation sync payloads must be compatible with spec 120 FederatedPayload schema
  - CC attribution must use existing value lineage payout-preview mechanism
```

## API Contract

### `POST /api/marketplace/publish`

Publish an idea to the cross-instance marketplace.

**Request**
```json
{
  "idea_id": "string (existing local idea ID)",
  "tags": ["oss", "infrastructure"],
  "author_display_name": "alice",
  "visibility": "public"
}
```

**Response 201**
```json
{
  "listing_id": "mkt_abc123",
  "idea_id": "my-idea-id",
  "origin_instance_id": "instance-001",
  "author_id": "alice@instance-001",
  "author_display_name": "alice",
  "name": "Idea Name",
  "description": "Idea description...",
  "potential_value": 500.0,
  "estimated_cost": 120.0,
  "confidence": 0.8,
  "tags": ["oss", "infrastructure"],
  "content_hash": "sha256:abcdef...",
  "published_at": "2026-03-20T12:00:00Z",
  "fork_count": 0,
  "adoption_score": 0.0
}
```

**Response 409**
```json
{
  "detail": "Duplicate listing exists",
  "existing_listing_id": "mkt_existing123"
}
```

**Response 422**
```json
{
  "detail": "Idea does not meet marketplace quality gate",
  "errors": [
    {"field": "confidence", "message": "Must be >= 0.3, got 0.1"},
    {"field": "value_basis", "message": "At least one entry required"}
  ]
}
```

**Response 404**
```json
{ "detail": "Idea not found" }
```

### `GET /api/marketplace/browse`

Browse published ideas with filtering and pagination.

**Request (query params)**
- `page`: int (default 1)
- `page_size`: int (default 20, max 100)
- `tags`: comma-separated string (optional)
- `sort`: enum("recent", "popular", "value") (default "recent")
- `search`: string (optional, full-text on name+description)
- `min_confidence`: float (optional)

**Response 200**
```json
{
  "listings": [
    {
      "listing_id": "mkt_abc123",
      "idea_id": "my-idea-id",
      "origin_instance_id": "instance-001",
      "author_id": "alice@instance-001",
      "author_display_name": "alice",
      "name": "Idea Name",
      "description": "Idea description...",
      "potential_value": 500.0,
      "confidence": 0.8,
      "tags": ["oss"],
      "published_at": "2026-03-20T12:00:00Z",
      "fork_count": 3,
      "adoption_score": 45.0
    }
  ],
  "total": 42,
  "page": 1,
  "page_size": 20
}
```

### `POST /api/marketplace/fork/{listing_id}`

Fork a marketplace listing into the local instance.

**Request**
- `listing_id`: string (path)

**Request body**
```json
{
  "forker_id": "bob",
  "notes": "Adapting for our infrastructure"
}
```

**Response 201**
```json
{
  "fork_id": "fork_xyz789",
  "local_idea_id": "forked-my-idea-id",
  "forked_from_listing_id": "mkt_abc123",
  "forked_from_idea_id": "my-idea-id",
  "forked_from_instance_id": "instance-001",
  "forked_by": "bob",
  "forked_at": "2026-03-20T13:00:00Z"
}
```

**Response 404**
```json
{ "detail": "Marketplace listing not found" }
```

### `GET /api/marketplace/authors/{author_id}/reputation`

**Response 200**
```json
{
  "author_id": "alice@instance-001",
  "reputation_score": 127.5,
  "total_publications": 8,
  "total_forks": 23,
  "total_adoption_cc": 450.0,
  "computed_at": "2026-03-20T14:00:00Z"
}
```

### `GET /api/marketplace/manifest`

OpenClaw plugin registration manifest.

**Response 200**
```json
{
  "plugin_id": "coherence-network-marketplace",
  "version": "1.0.0",
  "name": "Coherence Network Idea Marketplace",
  "capabilities": ["publish", "browse", "fork", "reputation"],
  "required_permissions": ["read:ideas", "write:ideas", "read:user_identity"],
  "endpoints": {
    "publish": "/api/marketplace/publish",
    "browse": "/api/marketplace/browse",
    "fork": "/api/marketplace/fork/{listing_id}",
    "reputation": "/api/marketplace/authors/{author_id}/reputation"
  },
  "webhooks": {
    "on_fork": "/api/marketplace/webhooks/fork",
    "on_adoption": "/api/marketplace/webhooks/adoption"
  }
}
```

## Data Model

```yaml
MarketplaceListing:
  properties:
    listing_id: { type: string, format: "mkt_{uuid}" }
    idea_id: { type: string, min_length: 1 }
    origin_instance_id: { type: string, min_length: 1 }
    author_id: { type: string, format: "{user}@{instance}" }
    author_display_name: { type: string }
    name: { type: string, min_length: 1 }
    description: { type: string, min_length: 1 }
    potential_value: { type: float, ge: 0 }
    estimated_cost: { type: float, ge: 0 }
    confidence: { type: float, ge: 0.3, le: 1.0 }
    tags: { type: "list[str]", default: [] }
    content_hash: { type: string, format: "sha256:{hex}" }
    visibility: { type: string, enum: ["public", "unlisted"], default: "public" }
    published_at: { type: datetime }
    fork_count: { type: int, default: 0 }
    adoption_score: { type: float, default: 0.0 }
    status: { type: string, enum: ["active", "archived", "flagged"], default: "active" }

MarketplaceFork:
  properties:
    fork_id: { type: string, format: "fork_{uuid}" }
    local_idea_id: { type: string }
    forked_from_listing_id: { type: string }
    forked_from_idea_id: { type: string }
    forked_from_instance_id: { type: string }
    forked_by: { type: string }
    notes: { type: string, default: "" }
    forked_at: { type: datetime }
    lineage_link_id: { type: "string | null", description: "Value lineage link created for attribution" }

AuthorReputation:
  properties:
    author_id: { type: string }
    reputation_score: { type: float }
    total_publications: { type: int }
    total_forks: { type: int }
    total_adoption_cc: { type: float }
    computed_at: { type: datetime }
```

## Files to Create/Modify

- `api/app/models/marketplace.py` -- Pydantic models: MarketplaceListing, MarketplaceFork, AuthorReputation, PublishRequest, ForkRequest
- `api/app/services/marketplace_service.py` -- business logic: publish, browse, fork, reputation computation, duplicate detection, quality gate, federation sync adapter
- `api/app/routers/marketplace.py` -- route handlers for all marketplace endpoints
- `api/app/main.py` -- wire marketplace router
- `api/app/models/federation.py` -- add MARKETPLACE_LISTING and MARKETPLACE_FORK to payload type handling
- `api/app/services/federation_service.py` -- handle marketplace payload types in sync processing
- `api/tests/test_marketplace.py` -- contract tests for all requirements

## Acceptance Tests

- `api/tests/test_marketplace.py::test_publish_idea_201` -- valid publish returns listing with content_hash
- `api/tests/test_marketplace.py::test_publish_low_confidence_422` -- confidence < 0.3 rejected
- `api/tests/test_marketplace.py::test_publish_no_value_basis_422` -- missing value_basis rejected
- `api/tests/test_marketplace.py::test_publish_duplicate_409` -- same content_hash returns 409
- `api/tests/test_marketplace.py::test_publish_nonexistent_idea_404` -- unknown idea_id returns 404
- `api/tests/test_marketplace.py::test_browse_pagination` -- page/page_size params work correctly
- `api/tests/test_marketplace.py::test_browse_tag_filter` -- tag filter returns only matching listings
- `api/tests/test_marketplace.py::test_browse_search` -- full-text search matches name and description
- `api/tests/test_marketplace.py::test_fork_creates_local_idea` -- fork produces local idea with forked_from reference
- `api/tests/test_marketplace.py::test_fork_increments_fork_count` -- origin listing fork_count increases
- `api/tests/test_marketplace.py::test_fork_creates_lineage_link` -- fork creates value lineage link with origin_author role
- `api/tests/test_marketplace.py::test_fork_nonexistent_listing_404` -- unknown listing returns 404
- `api/tests/test_marketplace.py::test_reputation_score_computation` -- reputation reflects adoption CC
- `api/tests/test_marketplace.py::test_manifest_shape` -- manifest contains required OpenClaw fields
- `api/tests/test_marketplace.py::test_federation_sync_listing` -- published listing syncs to federated instance

## Concurrency Behavior

- **Read operations**: Safe for concurrent access; no locking required.
- **Write operations** (publish, fork): Last-write-wins semantics for MVP. Duplicate detection uses content_hash which is deterministic, so concurrent duplicate publishes are safe (second attempt gets 409).
- **Fork count**: Incremented non-atomically; minor undercounting possible under extreme concurrency. Acceptable for MVP.

## Failure and Retry Behavior

- **Invalid input**: Return 422 with field-level validation errors.
- **Idea not found**: Return 404 with descriptive message.
- **Federation sync failure**: Log error, continue local operation. Failed syncs are retried on next poll interval. Listing remains available locally even if federation is unreachable.
- **Database unavailable**: Return 503; client should retry with exponential backoff (initial 1s, max 30s).
- **Content hash collision** (astronomically unlikely): SHA-256 collision treated as duplicate. No mitigation needed for practical purposes.

## Verification

```bash
python3 -m pytest api/tests/test_marketplace.py -x -v
python3 -m pytest api/tests/test_value_lineage.py -x -q
python3 -m pytest api/tests/test_minimum_federation_layer.py -x -q
python3 scripts/validate_spec_quality.py --file specs/121-openclaw-idea-marketplace.md
```

Manual verification:
- Publish an idea, browse the marketplace, fork it to a second instance, verify fork event appears in origin instance's listing.
- Verify forked idea's lineage link credits origin author at 10% weight.

## Out of Scope

- Full OpenClaw OAuth integration (requires OpenClaw auth spec finalization)
- Marketplace moderation UI (future spec)
- Paid listing promotion or advertising
- Idea versioning beyond fork (no merge-back flow)
- Real-time WebSocket notifications for new listings
- Marketplace analytics dashboard

## Risks and Assumptions

- **Risk: Sybil attacks** -- A user could create multiple identities to inflate fork counts and reputation. Mitigation: reputation computation weights by instance diversity (forks from same instance count at 50%). Long-term: require identity verification via OpenClaw's auth system.
- **Risk: Spam publishing** -- Automated publishing of low-quality ideas to flood the marketplace. Mitigation: quality gate (R8) requires confidence >= 0.3 and value_basis. Future: rate limiting per author.
- **Risk: Federation partition** -- If instances cannot reach each other, marketplace state diverges. Mitigation: eventual consistency model; listings include content_hash for deduplication on reconnect.
- **Assumption**: OpenClaw's plugin extension mechanism supports the manifest format described here. If the format changes, the manifest endpoint must be updated.
- **Assumption**: Value lineage service (spec 048) accepts an `origin_author` role without schema changes. If not, the payout-preview weights need to be extended.
- **Assumption**: The 10% origin_author attribution rate is acceptable. This is a governance-tunable parameter but hardcoded for MVP.

## Known Gaps and Follow-up Tasks

- Follow-up task: OpenClaw OAuth integration for identity verification
- Follow-up task: Marketplace moderation workflow (flag, review, remove)
- Follow-up task: Listing analytics (view counts, click-through rates)
- Follow-up task: Merge-back flow (forked idea improvements propagating to origin)
- Follow-up task: Rate limiting per author per time window
- Follow-up task: Configurable origin_author attribution percentage via governance

## Failure/Retry Reflection

- Failure mode: Federation sync timeout causes listing to appear on origin but not on peer instances
- Blind spot: No retry queue for failed sync attempts; relies on next poll interval
- Next action: Add a pending_sync queue that retries failed payloads with exponential backoff up to 3 attempts

## Decision Gates

- **DG1**: Origin author attribution percentage (10%) -- needs founder approval before implementation
- **DG2**: OpenClaw plugin manifest format -- needs validation against actual OpenClaw extension API docs
