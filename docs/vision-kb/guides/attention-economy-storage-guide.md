---
id: attention-economy-storage
type: guide
status: seed
updated: 2026-04-14
---

# Attention Economy — Storage & Verification Design

## Constraints

1. **Storage efficient**: millions of reads per day at steady state. Cannot store one row per read.
2. **Publicly verifiable**: anyone can prove that reads happened and CC flowed correctly, without trusting the host.
3. **Append-only**: no retroactive editing of the read/flow record.
4. **Lightweight**: no blockchain consensus overhead — single-writer with cryptographic proof.

## Storage Design: Merkle-Aggregated Counters

Instead of storing every individual read event, aggregate into time-bucketed counters with Merkle proofs.

### Layer 1: Hot Counters (in-memory, Redis-like)

```
Per asset, per time bucket (1 hour):
  asset_id:hour → {
    read_count: int,
    unique_readers: HyperLogLog,     # probabilistic unique count, 12KB per counter
    concept_distribution: {concept_id: count},
    cc_distributed: decimal,
    reader_samples: [reader_id, ...]  # sample of 10 reader IDs for verification
  }
```

**Storage per asset per hour**: ~200 bytes + 12KB HyperLogLog = ~12.2KB
**Per day (24 buckets)**: ~293KB per active asset
**For 1000 active assets**: ~286MB/day in hot storage

### Layer 2: Daily Rollups (PostgreSQL)

Every hour, flush hot counters to a daily rollup row:

```sql
CREATE TABLE asset_reads_daily (
    asset_id     TEXT NOT NULL,
    day          DATE NOT NULL,
    read_count   BIGINT DEFAULT 0,
    unique_est   INT DEFAULT 0,         -- from HyperLogLog merge
    cc_total     NUMERIC(18,8) DEFAULT 0,
    concepts     JSONB,                 -- {concept_id: {reads: N, cc: X}}
    merkle_hash  BYTEA NOT NULL,        -- SHA-256 of this row's data
    prev_hash    BYTEA NOT NULL,        -- hash chain to previous day
    PRIMARY KEY (asset_id, day)
);
```

**Storage per row**: ~250 bytes
**Per year, 1000 assets**: ~91MB
**Per year, 100K assets**: ~9.1GB

### Layer 3: Merkle Chain (public verification)

Each daily rollup row includes:
- `merkle_hash`: SHA-256 of `(asset_id || day || read_count || cc_total || concepts_json)`
- `prev_hash`: previous day's merkle_hash for this asset

This creates a per-asset hash chain. To verify:
1. Anyone can request the full chain for any asset: `GET /api/assets/{id}/verification-chain`
2. Recompute each hash from the data — if any row was tampered with, the chain breaks
3. The latest hash is periodically published to a public ledger (IPFS pin, blockchain anchor, or simply a signed JSON file)

### Layer 4: Periodic Snapshots (IPFS/public)

Weekly, the system publishes a snapshot:

```json
{
  "week": "2026-W16",
  "total_reads": 847293,
  "total_cc_distributed": 12847.32,
  "assets_active": 1247,
  "merkle_root": "sha256:abc123...",  // root of all asset chains
  "signed_by": "node-id-xyz",
  "signature": "ed25519:..."
}
```

This snapshot is:
- Pinned to IPFS (immutable, content-addressed)
- Signed by the host node's Ed25519 key
- Recomputable by anyone with access to the daily rollups

## CC Flow Computation (Efficient)

Instead of computing CC per individual read, batch at the daily rollup level:

```
Daily CC pool for asset X = base_rate × read_count × quality_multiplier

Distribution:
  For each concept C tagged on asset X:
    concept_weight = asset_tag_weight[C]
    
    For each reader who read asset X today (sampled):
      reader_weight = reader_resonance_profile[C]
    
    concept_cc = pool × concept_weight × avg(reader_weights)
    
  Creator receives: sum(concept_cc for all C)
```

The reader's resonance profile doesn't need to be applied per-read. Aggregate by day:

```sql
-- Reader resonance profiles update from daily read aggregates
UPDATE resonance_profiles SET
  auto_weights = compute_weights(
    SELECT concept_id, SUM(read_count) 
    FROM asset_reads_daily 
    JOIN asset_concepts USING (asset_id)
    WHERE reader_id = $1 AND day > NOW() - INTERVAL '30 days'
    GROUP BY concept_id
  )
WHERE contributor_id = $1;
```

## Resonance Profile Storage

```sql
CREATE TABLE resonance_profiles (
    contributor_id  TEXT PRIMARY KEY,
    manual_weights  JSONB,              -- {concept_id: weight} set by user
    auto_weights    JSONB,              -- computed from reading patterns
    effective       JSONB,              -- blended: manual overrides auto
    updated_at      TIMESTAMPTZ
);
```

**Storage per profile**: ~500 bytes
**For 100K users**: ~50MB

The `effective` weights blend manual and auto:
- If manual is set for a concept, use it
- Otherwise, use auto-computed weight
- Normalize to sum = 1.0

## Verification API

```
GET /api/assets/{id}/reads                 -- daily read counts
GET /api/assets/{id}/cc-flow               -- daily CC distribution
GET /api/assets/{id}/verification-chain    -- merkle hash chain
GET /api/verification/snapshot/{week}      -- weekly published snapshot
GET /api/verification/recompute/{asset_id} -- anyone can recompute and compare
```

## Why This Works

| Property | How |
|----------|-----|
| **Storage efficient** | Aggregate counters, not per-read rows. ~9GB/year at 100K assets. |
| **Publicly verifiable** | Per-asset Merkle chains + weekly signed snapshots. Anyone can recompute. |
| **Append-only** | Hash chains break if any historical row is modified. |
| **No blockchain overhead** | Single-writer Merkle chain. Verification is O(n) hash comparison, not consensus. |
| **Privacy respecting** | Reader IDs sampled (not stored per-read). HyperLogLog gives unique counts without storing who. |
| **Micro-attribution** | CC flows at daily batch level, not per-read. Same economic result, 1000x less computation. |

## What This Enables

A community member in Portugal contributes a detailed rammed-earth building blueprint (GLTF 3D model + step-by-step instruction). It costs them 50 CC to produce (time, renders, documentation).

Over the next year, 47 communities worldwide view and download it. Each read is sensed. The blueprint earns 180 CC through micro-attribution. The creator's contribution is proven by the Merkle chain — anyone can verify. When a community in New Zealand actually builds from the blueprint and records implementation evidence, a larger CC flow triggers — the blueprint is now proven to serve life, not just attract attention.

The reader in New Zealand had their resonance profile set to 50% space, 30% land, 20% nourishment. Their reads naturally weighted CC toward creators who serve those concepts. The Portuguese blueprint creator didn't need to know this reader existed — the economic field connected them through shared resonance.
