---
idea_id: value-attribution
status: draft
priority: high
source:
  - file: api/app/routers/assets.py
    symbols: [create_asset(), get_asset(), get_asset_content()]
  - file: api/app/models/asset.py
    symbols: [Asset, AssetCreate, AssetType, AssetIPRegistration, StorageRecord]
  - file: api/app/services/ip_registration_service.py
    symbols: [register_ip_asset(), get_ip_status(), record_derivative()]
  - file: api/app/services/permanent_storage_service.py
    symbols: [upload_to_arweave(), upload_to_ipfs(), verify_content_integrity()]
  - file: api/app/services/read_tracking_service.py
    symbols: [record_read(), get_daily_aggregates(), compute_cc_flow()]
  - file: api/app/services/settlement_service.py
    symbols: [run_daily_settlement(), compute_concept_distribution(), settle_batch()]
  - file: api/app/services/evidence_service.py
    symbols: [submit_evidence(), verify_evidence(), compute_evidence_bonus()]
  - file: api/app/services/value_lineage_service.py
    symbols: [create_link(), add_usage_event()]
  - file: api/app/services/cc_economics_service.py
    symbols: [supply(), stake()]
  - file: api/app/services/distribution_engine.py
    symbols: [DistributionEngine.distribute()]
  - file: api/app/services/belief_service.py
    symbols: [get_belief_profile()]
  - file: api/app/routers/settlement.py
    symbols: [trigger_settlement(), get_settlement_status()]
  - file: api/app/routers/evidence.py
    symbols: [submit_evidence(), list_evidence()]
  - file: api/app/models/settlement.py
    symbols: [SettlementBatch, SettlementEntry, ConceptPool]
  - file: api/app/models/evidence.py
    symbols: [ImplementationEvidence, EvidenceCreate, EvidenceVerification]
  - file: web/app/assets/[asset_id]/page.tsx
    symbols: [AssetDetailPage, IPStatusBadge, StorageLinks]
  - file: web/app/assets/upload/page.tsx
    symbols: [UploadForm, ConceptTagger]
  - file: web/app/settlement/page.tsx
    symbols: [SettlementDashboard]
requirements:
  - "Asset creation registers IP on Story Protocol and stores IP Asset ID on graph node"
  - "Content uploaded to Arweave (permanent) and IPFS (retrieval) with TX ID and CID on asset node"
  - "GET /api/assets/{id}/content returns x402 payment headers for optional micropayment"
  - "Read events logged to value lineage with reader concept resonance weights"
  - "CC flows to creators weighted by reader concept resonance profile"
  - "Story Protocol royalty module handles derivative works"
  - "Daily batch settlement aggregates reads and distributes CC to concept pools"
  - "Implementation evidence triggers enhanced CC flow (proof of real-world value)"
  - "Content integrity verified by SHA-256 hash comparison against Arweave/IPFS"
done_when:
  - "A contributor uploads an asset and sees Story Protocol IP ID on the asset detail page"
  - "The asset content is retrievable from both Arweave and IPFS"
  - "A reader viewing asset content sees x402 payment headers in the response"
  - "Read events create usage events on the asset's value lineage link"
  - "Daily settlement distributes CC to creators proportional to concept-weighted reads"
  - "A derivative asset records the parent IP and Story Protocol royalty split"
  - "Implementation evidence submission triggers a bonus CC flow to the original creator"
  - "Content hash matches between local store, Arweave TX, and IPFS CID"
test: "cd api && python -m pytest tests/test_story_protocol.py tests/test_settlement.py tests/test_evidence.py -q"
constraints:
  - "No blockchain node required on infrastructure -- use Story Protocol SDK RPC and Arweave bundler services"
  - "Gas costs below $0.01 per asset registration (use Story Protocol Proof of Creativity on L2)"
  - "Read tracking must not add >50ms latency to content API responses"
  - "Settlement batch must complete within 5 minutes for 100K daily reads"
  - "x402 payments are optional -- free tier must remain functional without payment"
  - "All on-chain interactions are async (queue + worker) -- API never blocks on chain confirmation"
---

> **Parent idea**: [value-attribution](../ideas/value-attribution.md)
> **Depends on**: [assets-api](assets-api.md), [value-lineage-and-payout-attribution](value-lineage-and-payout-attribution.md), [cc-economics-and-value-coherence](cc-economics-and-value-coherence.md), [distribution-engine](distribution-engine.md), [knowledge-resonance-engine](knowledge-resonance-engine.md)

# Spec: Story Protocol + x402 + Arweave Integration

## Purpose

Connect asset creation, content delivery, and value distribution to three external protocols: Story Protocol for IP registration and derivative royalties, x402 for HTTP-native micropayments on content reads, and Arweave/IPFS for permanent verifiable storage. Together these turn every community-contributed asset (blueprint, article, 3D model, research paper) into a registered intellectual property that earns CC when read, pays royalties when derived from, and persists permanently with cryptographic proof of integrity. Without this integration, assets live only on our server, have no on-chain provenance, and cannot participate in the broader IP economy.

## Requirements

- [ ] **R1**: When a contributor creates an asset via `POST /api/assets`, the system queues an async job that registers the asset as an IP Asset on Story Protocol, stores the returned IP Asset ID on the asset's graph node property `sp_ip_id`, and sets `ip_status` to `registered`. If registration fails, `ip_status` is `failed` and the asset remains usable without IP registration.
- [ ] **R2**: Asset creation accepts expanded types: `ARTICLE`, `IMAGE`, `MODEL_3D`, `BLUEPRINT`, `VIDEO`, `RESEARCH`, `INSTRUCTION` (in addition to existing `CODE`, `MODEL`, `CONTENT`, `DATA`). Each asset accepts a `concept_tags` array of `{concept_id, weight}` pairs where weight is 0.0-1.0 and concept_id references a valid concept node.
- [ ] **R3**: On successful IP registration, the asset's content (binary or text) is uploaded to Arweave via a bundler service (Irys/Bundlr) and to IPFS. The Arweave transaction ID (`arweave_tx_id`) and IPFS content identifier (`ipfs_cid`) are stored on the asset graph node. A SHA-256 content hash (`content_hash`) is stored for integrity verification.
- [ ] **R4**: `GET /api/assets/{id}/content` serves the asset content and includes x402 payment headers (`402 Payment Required` response with `X-Payment-Amount`, `X-Payment-Currency: CC`, `X-Payment-Address`, `X-Payment-Network`). If the reader provides a valid payment token in the `Authorization` header, the content is served directly. If no payment token is provided, the content is served in free-tier mode (rate-limited, watermarked for images, truncated for articles).
- [ ] **R5**: Every content read (paid or free) creates a usage event on the asset's value lineage link via `add_usage_event()`. The usage event includes `reader_id`, `read_type` (free or paid), `cc_amount` (0 for free reads, micro-CC for paid), and `concept_resonance_snapshot` (the reader's belief profile concept weights at read time).
- [ ] **R6**: CC flow to the creator is weighted by the reader's concept resonance profile. For each concept tagged on the asset, the CC contribution is `base_cc * asset_concept_weight * reader_concept_weight`. This means creators who produce content aligned with what readers value earn proportionally more.
- [ ] **R7**: When a contributor creates a derivative work (improves a blueprint, translates an article, extends a 3D model), the new asset records `parent_asset_id` and `derivative_type`. Story Protocol's royalty module is configured with the platform's default royalty split (configurable, default: 15% to parent creator, 85% to derivative creator). The parent asset's graph node gains an outgoing `derived_into` edge.
- [ ] **R8**: A daily settlement batch job (`POST /api/settlement/run` or cron) aggregates all read usage events from the past 24 hours, computes CC distribution per asset per concept pool, and produces a `SettlementBatch` record. Settlement uses the Merkle-aggregated counter approach from the storage design guide (hot counters, daily rollups, hash chains).
- [ ] **R9**: `POST /api/evidence` accepts implementation evidence for an asset: photos (image URLs), GPS coordinates, community attestation signatures, and a description. Evidence is verified by requiring at least 2 of 3: photo proof, GPS within 50km of a known community, or 3+ community member attestations. Verified evidence triggers a `5x` CC multiplier on the asset's next settlement period.
- [ ] **R10**: `GET /api/assets/{id}/verification` returns the asset's content hash, Arweave TX ID, IPFS CID, and a recomputed hash for comparison. If the content has been tampered with (hashes do not match), the response includes `integrity: "failed"`.

## Research Inputs

- `2026-04-14` - Story Protocol SDK docs (https://docs.story.foundation/) -- IP Asset registration, royalty module, derivative licensing
- `2026-04-14` - x402 HTTP payment protocol (https://www.x402.org/) -- payment-required headers, facilitator flow, token verification
- `2026-04-14` - Arweave/Irys bundler docs (https://docs.irys.xyz/) -- permanent upload, transaction IDs, retrieval
- `2026-04-14` - IPFS HTTP API (https://docs.ipfs.tech/reference/http/api/) -- content upload, CID generation, gateway retrieval
- `2026-04-14` - Attention economy storage guide (`docs/vision-kb/guides/attention-economy-storage-guide.md`) -- Merkle-aggregated counters, daily rollups, CC flow computation

## Architecture

```
                        CONTRIBUTOR
                            |
                      POST /api/assets
                            |
                    +-------v--------+
                    |  Assets Router  |
                    |  (create_asset) |
                    +---+----+---+---+
                        |    |   |
          +-------------+    |   +-------------+
          |                  |                 |
    +-----v------+    +-----v------+    +-----v------+
    | Graph Store |    | IP Reg     |    | Permanent  |
    | (asset node |    | Service    |    | Storage    |
    |  + edges)   |    | (async)    |    | Service    |
    +-------------+    +-----+------+    | (async)    |
                             |           +-----+------+
                   +---------+---------+       |
                   |                   |   +---+---+---+
              +----v----+        +-----v-+ |  IPFS     |
              |  Story  |        | Chain  | |  Gateway  |
              | Protocol|        | Config | +-----------+
              |   SDK   |        | (royalty|
              +---------+        |  module)|   +-------+
                                 +--------+   |Arweave|
                                              |Bundler|
                                              +-------+

                         READER
                           |
                   GET /api/assets/{id}/content
                           |
                   +-------v--------+
                   |  Assets Router  |
                   |  (get_content)  |
                   +---+----+---+---+
                       |    |   |
         +-------------+    |   +-------------+
         |                  |                 |
   +-----v------+    +-----v------+    +-----v------+
   | x402 Header |    | Read       |    | Belief     |
   | Generation  |    | Tracking   |    | Service    |
   | (payment    |    | Service    |    | (reader    |
   |  optional)  |    | (async)    |    |  profile)  |
   +-------------+    +-----+------+    +-----+------+
                             |                 |
                       +-----v-----------------v-----+
                       |     Value Lineage Service    |
                       |     (usage event + concept   |
                       |      resonance snapshot)     |
                       +-----------------------------+
```

## Data Flow: Asset Creation

```
1. Contributor POST /api/assets {type, description, content, concept_tags}
                |
2. create_asset() validates input, creates Asset record
                |
3. Graph node created: asset:{uuid} with concept_tags as properties
                |
4. Concept tag edges created: asset:{uuid} --[tagged_with]--> concept:{id}
                |
5. Queue: IP Registration Job
   |  5a. Story Protocol SDK: register IP Asset
   |  5b. Store sp_ip_id on graph node
   |  5c. Set ip_status = "registered" (or "failed")
                |
6. Queue: Storage Job
   |  6a. SHA-256 hash of content
   |  6b. Upload to Arweave via Irys bundler → arweave_tx_id
   |  6c. Upload to IPFS → ipfs_cid
   |  6d. Store arweave_tx_id, ipfs_cid, content_hash on graph node
                |
7. Create value lineage link: idea + asset + contributor
```

## Data Flow: Content Read + CC Flow

```
1. Reader GET /api/assets/{id}/content
                |
2. Return x402 headers (always, regardless of payment)
                |
3. Check Authorization header for x402 payment token
   |  3a. Valid token → serve full content, read_type = "paid"
   |  3b. No token → serve free-tier content, read_type = "free"
                |
4. Async: Record read event (non-blocking, <50ms budget)
   |  4a. Fetch reader's belief profile concept_resonances
   |  4b. Create usage event on asset's lineage link:
   |      {source: "read", metric: "content_read",
   |       value: cc_amount, reader_id, read_type,
   |       concept_resonance_snapshot: reader_weights}
                |
5. Daily settlement batch (cron or POST /api/settlement/run):
   |  5a. Aggregate usage events from past 24h
   |  5b. For each asset:
   |      - Sum reads, compute unique readers (HyperLogLog)
   |      - For each concept tag on asset:
   |          concept_cc = base_rate * read_count
   |                     * asset_concept_weight
   |                     * avg(reader_concept_weights)
   |      - Creator CC = sum(concept_cc for all concepts)
   |  5c. Write SettlementBatch record with Merkle hash
   |  5d. CC transfer to creator via cc_economics_service
```

## Data Flow: Derivative Works

```
1. Contributor POST /api/assets {parent_asset_id, derivative_type, ...}
                |
2. create_asset() as normal + record parent relationship
                |
3. Graph edge: asset:{new} --[derived_from]--> asset:{parent}
                |
4. Story Protocol: registerDerivative(child_ip_id, parent_ip_id, royalty_policy)
                |
5. On reads of derivative: royalty split applies
   |  5a. 85% CC to derivative creator
   |  5b. 15% CC to parent creator
   |  5c. Recursive: parent's 15% is further split if parent is also a derivative
```

## Data Flow: Implementation Evidence

```
1. Builder POST /api/evidence {asset_id, photos, gps, attestations, description}
                |
2. Verification check (2 of 3 required):
   |  2a. Photos present and non-empty
   |  2b. GPS within 50km of a known community location
   |  2c. 3+ unique community member attestation signatures
                |
3. If verified:
   |  3a. Create EvidenceRecord on asset's graph node
   |  3b. Usage event: {source: "evidence", metric: "implementation", value: 5.0}
   |  3c. Next settlement: 5x CC multiplier for this asset
                |
4. If not verified:
   |  4a. Return 422 with missing verification details
   |  4b. Evidence stored as "pending" for manual review
```

## API Contract

### `POST /api/assets` (extended)

**Request**
```json
{
  "type": "BLUEPRINT",
  "description": "Rammed-earth community kitchen with passive cooling",
  "content_url": "https://storage.example.com/kitchen-blueprint.glb",
  "concept_tags": [
    {"concept_id": "lc-space", "weight": 0.8},
    {"concept_id": "lc-nourishment", "weight": 0.6},
    {"concept_id": "lc-energy", "weight": 0.3}
  ],
  "parent_asset_id": null,
  "derivative_type": null
}
```

- `type`: Extended enum -- `ARTICLE`, `IMAGE`, `MODEL_3D`, `BLUEPRINT`, `VIDEO`, `RESEARCH`, `INSTRUCTION`, `CODE`, `MODEL`, `CONTENT`, `DATA`
- `concept_tags`: Array of concept-weight pairs. concept_id must reference a valid concept node. weight is 0.0-1.0.
- `parent_asset_id`: Optional UUID. If provided, this is a derivative work.
- `derivative_type`: Optional string. One of `improvement`, `translation`, `extension`, `remix`. Required when parent_asset_id is set.

**Response 201**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "type": "BLUEPRINT",
  "description": "Rammed-earth community kitchen with passive cooling",
  "total_cost": 0.00,
  "created_at": "2026-04-14T10:00:00Z",
  "concept_tags": [
    {"concept_id": "lc-space", "weight": 0.8},
    {"concept_id": "lc-nourishment", "weight": 0.6},
    {"concept_id": "lc-energy", "weight": 0.3}
  ],
  "ip_status": "pending",
  "sp_ip_id": null,
  "arweave_tx_id": null,
  "ipfs_cid": null,
  "content_hash": null,
  "parent_asset_id": null,
  "derivative_type": null
}
```

### `GET /api/assets/{id}/content`

**Response Headers (always present)**
```
HTTP/1.1 200 OK
X-Payment-Amount: 0.001
X-Payment-Currency: CC
X-Payment-Address: coherence:contributor:{creator_id}
X-Payment-Network: story-protocol
X-Payment-Required: optional
X-Content-Hash: sha256:abc123...
X-Arweave-TX: ar:tx123...
X-IPFS-CID: bafybeig...
```

**Response 200** (free tier -- no payment token)
```json
{
  "asset_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "content_type": "model/gltf-binary",
  "content": "<full content for small assets, truncated/watermarked for large>",
  "tier": "free",
  "full_content_available": true,
  "payment_info": {
    "amount_cc": 0.001,
    "address": "coherence:contributor:{creator_id}",
    "network": "story-protocol"
  }
}
```

**Response 200** (paid tier -- valid x402 token in Authorization header)
```json
{
  "asset_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "content_type": "model/gltf-binary",
  "content": "<full content, no restrictions>",
  "tier": "paid",
  "cc_charged": 0.001
}
```

### `GET /api/assets/{id}/verification`

**Response 200**
```json
{
  "asset_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "content_hash": "sha256:abc123...",
  "recomputed_hash": "sha256:abc123...",
  "integrity": "verified",
  "arweave_tx_id": "ar:tx123...",
  "arweave_url": "https://arweave.net/tx123...",
  "ipfs_cid": "bafybeig...",
  "ipfs_url": "https://ipfs.io/ipfs/bafybeig...",
  "sp_ip_id": "0x1234...abcd",
  "sp_explorer_url": "https://explorer.story.foundation/ip/0x1234...abcd",
  "verified_at": "2026-04-14T10:05:00Z"
}
```

### `POST /api/settlement/run`

**Request**
```json
{
  "date": "2026-04-13",
  "dry_run": false
}
```

- `date`: Optional. Settlement date (default: yesterday). Aggregates reads from that 24h period.
- `dry_run`: If true, compute distribution but do not transfer CC.

**Response 200**
```json
{
  "batch_id": "stl_20260413_001",
  "date": "2026-04-13",
  "total_reads": 84729,
  "unique_readers": 3412,
  "assets_settled": 847,
  "total_cc_distributed": 1284.73,
  "concept_pools": [
    {"concept_id": "lc-space", "cc_total": 312.50, "read_count": 21000},
    {"concept_id": "lc-nourishment", "cc_total": 198.30, "read_count": 14200},
    {"concept_id": "lc-energy", "cc_total": 156.80, "read_count": 11500}
  ],
  "merkle_hash": "sha256:def456...",
  "prev_hash": "sha256:abc123...",
  "dry_run": false,
  "completed_at": "2026-04-14T02:03:45Z"
}
```

### `GET /api/settlement/batches`

**Response 200**
```json
{
  "items": [
    {
      "batch_id": "stl_20260413_001",
      "date": "2026-04-13",
      "total_reads": 84729,
      "total_cc_distributed": 1284.73,
      "merkle_hash": "sha256:def456...",
      "status": "completed"
    }
  ],
  "total": 30,
  "limit": 20,
  "offset": 0
}
```

### `POST /api/evidence`

**Request**
```json
{
  "asset_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "contributor_id": "builder-nz-001",
  "description": "Completed rammed-earth kitchen in Christchurch community",
  "photos": [
    "https://storage.example.com/evidence/photo1.jpg",
    "https://storage.example.com/evidence/photo2.jpg"
  ],
  "gps": {
    "latitude": -43.5321,
    "longitude": 172.6362
  },
  "attestations": [
    {"member_id": "member-001", "signature": "ed25519:..."},
    {"member_id": "member-002", "signature": "ed25519:..."},
    {"member_id": "member-003", "signature": "ed25519:..."}
  ]
}
```

**Response 201** (verified)
```json
{
  "evidence_id": "evi_001",
  "asset_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "verified",
  "verification": {
    "photos_present": true,
    "gps_valid": true,
    "attestations_valid": true,
    "checks_passed": 3,
    "checks_required": 2
  },
  "cc_multiplier": 5.0,
  "applies_to_settlement": "2026-04-14",
  "created_at": "2026-04-14T15:30:00Z"
}
```

**Response 201** (pending -- insufficient verification)
```json
{
  "evidence_id": "evi_002",
  "asset_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "pending",
  "verification": {
    "photos_present": true,
    "gps_valid": false,
    "attestations_valid": false,
    "checks_passed": 1,
    "checks_required": 2
  },
  "cc_multiplier": null,
  "applies_to_settlement": null,
  "created_at": "2026-04-14T15:30:00Z"
}
```

### `GET /api/evidence?asset_id={id}`

**Response 200**
```json
{
  "items": [
    {
      "evidence_id": "evi_001",
      "asset_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "contributor_id": "builder-nz-001",
      "status": "verified",
      "description": "Completed rammed-earth kitchen in Christchurch community",
      "cc_multiplier": 5.0,
      "created_at": "2026-04-14T15:30:00Z"
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

## Data Model

```yaml
# Extended Asset (additions to existing Asset model)
Asset:
  id: UUID
  type: AssetType  # extended enum
  description: String
  total_cost: Decimal
  created_at: DateTime
  # New fields:
  concept_tags: list[ConceptTag]
  content_hash: String | None       # SHA-256 of content
  sp_ip_id: String | None           # Story Protocol IP Asset ID
  ip_status: IPStatus               # pending | registered | failed
  arweave_tx_id: String | None      # Arweave transaction ID
  ipfs_cid: String | None           # IPFS content identifier
  parent_asset_id: UUID | None      # For derivative works
  derivative_type: DerivativeType | None
  contributor_id: String            # Creator identity

AssetType: enum
  # Existing:
  CODE, MODEL, CONTENT, DATA
  # New:
  ARTICLE, IMAGE, MODEL_3D, BLUEPRINT, VIDEO, RESEARCH, INSTRUCTION

IPStatus: enum
  pending, registered, failed

DerivativeType: enum
  improvement, translation, extension, remix

ConceptTag:
  concept_id: String    # references concept node (e.g. "lc-space")
  weight: Float         # 0.0 - 1.0

# IP Registration Record (PostgreSQL)
IPRegistration:
  id: String (PK)
  asset_id: UUID (FK, unique)
  sp_ip_id: String | None
  sp_chain_id: Int
  sp_tx_hash: String | None
  status: IPStatus
  royalty_policy: String          # "default-15-85" or custom
  registered_at: DateTime | None
  error_message: String | None
  created_at: DateTime

# Storage Record (PostgreSQL)
StorageRecord:
  id: String (PK)
  asset_id: UUID (FK, unique)
  content_hash: String            # SHA-256
  arweave_tx_id: String | None
  arweave_status: String          # pending | confirmed | failed
  ipfs_cid: String | None
  ipfs_status: String             # pending | pinned | failed
  content_size_bytes: Int
  uploaded_at: DateTime | None
  created_at: DateTime

# Read Event (extension of existing UsageEvent)
ReadEvent:
  id: String (PK)
  asset_id: UUID
  reader_id: String
  read_type: String               # "free" | "paid"
  cc_amount: Decimal              # 0 for free, micro-CC for paid
  concept_resonance_snapshot: JSON  # reader's weights at read time
  captured_at: DateTime

# Settlement Batch (PostgreSQL)
SettlementBatch:
  batch_id: String (PK)
  date: Date
  total_reads: Int
  unique_readers: Int
  assets_settled: Int
  total_cc_distributed: Decimal
  concept_pools: JSON             # [{concept_id, cc_total, read_count}]
  merkle_hash: String             # SHA-256 of batch data
  prev_hash: String               # Chain to previous batch
  status: String                  # running | completed | failed
  started_at: DateTime
  completed_at: DateTime | None

# Settlement Entry (PostgreSQL)
SettlementEntry:
  id: String (PK)
  batch_id: String (FK)
  asset_id: UUID
  creator_id: String
  read_count: Int
  unique_readers: Int
  cc_earned: Decimal
  concept_breakdown: JSON         # {concept_id: cc_amount}
  evidence_multiplier: Decimal    # 1.0 normally, 5.0 with verified evidence
  royalty_deduction: Decimal      # CC sent to parent creator (if derivative)

# Implementation Evidence (PostgreSQL)
ImplementationEvidence:
  evidence_id: String (PK)
  asset_id: UUID (FK)
  contributor_id: String
  description: String
  photos: JSON                    # [url, ...]
  gps: JSON | None                # {latitude, longitude}
  attestations: JSON | None       # [{member_id, signature}]
  status: String                  # pending | verified | rejected
  verification_result: JSON       # {photos_present, gps_valid, attestations_valid, checks_passed}
  cc_multiplier: Decimal | None
  applies_to_settlement: Date | None
  created_at: DateTime
  verified_at: DateTime | None

# Community Location (for GPS verification)
CommunityLocation:
  id: String (PK)
  name: String
  latitude: Float
  longitude: Float
  radius_km: Float                # Default 50
```

## Graph Edges (Neo4j)

```yaml
# New edge types
asset --[tagged_with {weight: 0.8}]--> concept
asset --[derived_from {derivative_type, royalty_split}]--> asset
asset --[has_evidence {evidence_id, status}]--> evidence
contributor --[created_asset]--> asset
contributor --[read_asset {read_count, last_read}]--> asset
contributor --[attested_evidence {evidence_id}]--> evidence
```

## Files to Create/Modify

### New files
- `api/app/services/ip_registration_service.py` -- Story Protocol SDK integration, async IP registration, derivative recording
- `api/app/services/permanent_storage_service.py` -- Arweave upload via Irys, IPFS upload, hash computation, integrity verification
- `api/app/services/read_tracking_service.py` -- Non-blocking read event recording, HyperLogLog unique counting, concept resonance snapshots
- `api/app/services/settlement_service.py` -- Daily batch aggregation, concept pool computation, Merkle hash chain, CC distribution
- `api/app/services/evidence_service.py` -- Evidence submission, GPS distance check, attestation verification, multiplier application
- `api/app/routers/settlement.py` -- Settlement batch endpoints
- `api/app/routers/evidence.py` -- Evidence submission and listing endpoints
- `api/app/models/settlement.py` -- SettlementBatch, SettlementEntry, ConceptPool Pydantic models
- `api/app/models/evidence.py` -- ImplementationEvidence, EvidenceCreate, EvidenceVerification Pydantic models
- `api/app/models/storage.py` -- StorageRecord, IPRegistration Pydantic models
- `api/tests/test_story_protocol.py` -- IP registration, content delivery, x402 headers, verification
- `api/tests/test_settlement.py` -- Daily settlement, concept pools, Merkle chain, evidence multiplier
- `api/tests/test_evidence.py` -- Evidence submission, verification logic, GPS check
- `web/app/assets/upload/page.tsx` -- Upload form with concept tagging
- `web/app/settlement/page.tsx` -- Settlement dashboard showing daily batches

### Modified files
- `api/app/models/asset.py` -- Extend AssetType enum, add concept_tags, IP fields, storage fields, derivative fields
- `api/app/routers/assets.py` -- Add `get_asset_content()` endpoint, extend `create_asset()` with concept tags and async jobs, add `get_asset_verification()` endpoint
- `api/app/services/value_lineage_service.py` -- Extend `add_usage_event()` to accept concept resonance snapshots
- `api/app/services/distribution_engine.py` -- Extend `distribute()` to weight by concept resonance
- `api/app/services/cc_economics_service.py` -- Add settlement CC transfer method
- `api/app/main.py` -- Register new routers (settlement, evidence)
- `web/app/assets/[asset_id]/page.tsx` -- Show IP status badge, Arweave/IPFS links, evidence section

## Acceptance Tests

### test_story_protocol.py
- `test_create_asset_queues_ip_registration` -- POST asset, verify ip_status is "pending", async job queued
- `test_ip_registration_stores_sp_ip_id` -- Mock Story Protocol SDK, verify sp_ip_id stored on graph node
- `test_ip_registration_failure_leaves_asset_usable` -- Mock SDK failure, verify asset works, ip_status is "failed"
- `test_content_delivery_includes_x402_headers` -- GET /content, verify X-Payment-* headers present
- `test_paid_read_serves_full_content` -- GET /content with payment token, verify full content returned
- `test_free_read_serves_limited_content` -- GET /content without token, verify tier is "free"
- `test_read_creates_usage_event` -- GET /content, verify usage event on lineage link
- `test_content_uploaded_to_arweave_and_ipfs` -- Mock bundler, verify arweave_tx_id and ipfs_cid stored
- `test_verification_endpoint_compares_hashes` -- GET /verification, verify integrity field
- `test_derivative_records_parent_relationship` -- POST asset with parent_asset_id, verify derived_from edge
- `test_concept_tags_create_graph_edges` -- POST asset with concept_tags, verify tagged_with edges
- `test_extended_asset_types_accepted` -- POST with BLUEPRINT, IMAGE, etc., verify 201

### test_settlement.py
- `test_daily_settlement_aggregates_reads` -- Create read events, run settlement, verify totals
- `test_settlement_distributes_cc_by_concept_weights` -- Assets with different concept tags, verify CC distribution
- `test_settlement_merkle_chain` -- Run 2 settlements, verify prev_hash chain
- `test_settlement_dry_run_no_cc_transfer` -- dry_run=true, verify no CC moved
- `test_settlement_applies_evidence_multiplier` -- Asset with verified evidence, verify 5x CC
- `test_settlement_handles_derivative_royalties` -- Derivative asset reads, verify 15/85 split
- `test_settlement_completes_within_time_budget` -- 100K synthetic reads, verify <5min

### test_evidence.py
- `test_submit_evidence_with_all_three_checks` -- Photos + GPS + attestations, verify "verified"
- `test_submit_evidence_with_two_checks` -- Photos + GPS only, verify "verified"
- `test_submit_evidence_with_one_check` -- Photos only, verify "pending"
- `test_gps_within_50km_of_community` -- GPS near known location, verify gps_valid=true
- `test_gps_too_far_from_community` -- GPS 100km away, verify gps_valid=false
- `test_attestation_requires_3_members` -- 2 attestations, verify attestations_valid=false
- `test_verified_evidence_sets_multiplier` -- Verify cc_multiplier=5.0 and applies_to_settlement set
- `test_evidence_list_filtered_by_asset` -- Multiple assets, verify filter works

## Verification

```bash
cd api && python -m pytest tests/test_story_protocol.py tests/test_settlement.py tests/test_evidence.py -q
python3 scripts/validate_spec_quality.py specs/story-protocol-integration.md
```

Manual verification:
1. Create an asset with concept tags, verify IP registration job fires
2. Read the asset content, verify x402 headers and usage event creation
3. Run daily settlement, verify CC distribution matches concept weights
4. Submit implementation evidence, verify multiplier applies on next settlement
5. Create a derivative asset, verify royalty split on settlement

## Phased Implementation Plan

### Phase 1: Asset Extension + Read Tracking (Week 1-2)
- Extend AssetType enum and Asset model with new fields
- Add concept_tags support with graph edges
- Implement `GET /api/assets/{id}/content` with x402 headers (no actual payment processing)
- Implement non-blocking read tracking via `read_tracking_service.py`
- Wire read events into existing value lineage system
- Tests: test_story_protocol.py (content delivery and read tracking subset)

### Phase 2: Permanent Storage (Week 2-3)
- Implement `permanent_storage_service.py` with Arweave (Irys) and IPFS upload
- SHA-256 hashing and integrity verification
- `GET /api/assets/{id}/verification` endpoint
- Async upload queue (content stored locally first, uploaded in background)
- Tests: test_story_protocol.py (storage and verification subset)

### Phase 3: Story Protocol IP Registration (Week 3-4)
- Implement `ip_registration_service.py` with Story Protocol SDK
- Async registration queue with retry
- Derivative work recording with royalty policy
- Tests: test_story_protocol.py (IP registration subset)

### Phase 4: Daily Settlement (Week 4-5)
- Implement `settlement_service.py` with Merkle-aggregated counters
- Concept pool computation weighted by reader resonance
- Merkle hash chain for verifiability
- CC distribution via cc_economics_service
- Settlement dashboard (web)
- Tests: test_settlement.py

### Phase 5: Implementation Evidence (Week 5-6)
- Implement `evidence_service.py` with verification logic
- GPS distance calculation against community locations
- Attestation signature verification
- 5x CC multiplier integration with settlement
- Tests: test_evidence.py

### Phase 6: x402 Payment Processing (Week 6-7)
- Integrate x402 facilitator for actual payment verification
- CC debit on paid reads, credit to creator
- Payment token validation
- Free tier rate limiting

## Out of Scope

- Running our own blockchain node or Arweave gateway -- use third-party RPCs and bundlers
- Fiat payment integration -- CC only for Phase 1
- Smart contract deployment for custom royalty logic -- use Story Protocol's built-in royalty module
- Real-time settlement -- daily batch only for Phase 1
- Content moderation or NSFW detection on uploaded assets
- Mobile app or native file upload -- web only
- Multi-chain support -- Story Protocol L2 only for Phase 1
- Wallet connect or MetaMask integration -- CC is internal currency, on-chain settlement is backend-only
- IPFS pinning service management -- use a managed pinning service (Pinata, web3.storage)
- Video transcoding or image optimization -- store as-is

## Risks and Assumptions

- **Risk**: Story Protocol SDK may change API between now and implementation. Mitigation: wrap all SDK calls in `ip_registration_service.py` so changes are isolated to one file.
- **Risk**: Arweave upload costs could be significant for large files (3D models, videos). Mitigation: set a maximum file size (50MB for Phase 1), compress before upload, use Irys bundler for sub-cent uploads on small files.
- **Risk**: x402 is a newer protocol with limited adoption. Mitigation: x402 headers are informational in Phase 1 (no enforcement), actual payment processing is Phase 6. If x402 does not mature, switch to Lightning or Stripe micropayments with the same header interface.
- **Risk**: Daily settlement at scale (100K+ reads) may exceed the 5-minute budget. Mitigation: HyperLogLog for unique counts, batch SQL aggregation, no per-read CC computation. The storage guide design already accounts for this.
- **Risk**: GPS spoofing could allow fake implementation evidence. Mitigation: GPS is only 1 of 3 verification factors. Require 2 of 3. Community attestation (social proof) is the strongest check.
- **Assumption**: Story Protocol's Proof of Creativity chain has gas costs under $0.01 per registration. If costs rise, batch registrations or defer to off-peak hours.
- **Assumption**: The existing graph DB (Neo4j) and PostgreSQL can handle the additional edge types and table rows without schema migration friction. New tables are additive.
- **Assumption**: Reader belief profiles (concept_resonances) are populated for a meaningful percentage of readers. For anonymous readers without profiles, use uniform concept weights (equal weight across all tagged concepts).

## Decision Gates

- **Royalty split percentage**: Default 15% parent / 85% derivative. Should this be configurable per asset or fixed platform-wide? Current spec uses platform-wide default.
- **Evidence CC multiplier**: 5x chosen as a strong signal that real-world implementation matters more than attention. Is 5x the right magnitude? Could be 3x or 10x depending on economic modeling.
- **Free tier limits**: What exactly constitutes free-tier degradation? Truncation percentage for articles, watermark style for images, polygon reduction for 3D models. Needs product decision per asset type.
- **Micro-CC amount per read**: The spec uses 0.001 CC as a placeholder. Actual amount should be derived from the CC economics model (base_rate from cc_economics_service). Needs calibration with real usage data.
- **Maximum file size for permanent storage**: 50MB proposed for Phase 1. Larger files (video, complex 3D models) may need a different storage tier or chunked upload.

## Downstream Consumers

- **distribution-engine spec**: Extended distribute() will use concept resonance weights from this spec's read tracking data.
- **cc-economics-and-value-coherence spec**: Settlement service calls into cc_economics_service to mint/transfer CC.
- **value-lineage-and-payout-attribution spec**: Read events flow through the existing usage event system.
- **knowledge-resonance-engine spec**: Reader belief profiles (concept_resonances) drive the CC weighting in this spec's settlement computation.
- **federation-network-layer spec**: When federation launches, IP registrations and settlement batches must sync across nodes.