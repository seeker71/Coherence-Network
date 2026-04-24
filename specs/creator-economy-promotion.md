---
idea_id: creator-economy-promotion
status: active
source:
  - file: api/app/routers/creator_economy.py
    symbols: [get_creator_stats(), get_asset_proof_card(), list_featured_assets()]
  - file: api/app/services/creator_economy_service.py
    symbols: [compute_creator_stats(), build_proof_card()]
  - file: api/app/models/creator_economy.py
    symbols: [CreatorStats, ProofCard, FeaturedAsset]
  - file: api/app/models/asset.py
    symbols: [AssetType]
  - file: web/app/creators/page.tsx
    symbols: [CreatorsLandingPage]
  - file: web/app/creators/submit/page.tsx
    symbols: [CreatorSubmitPage]
  - file: web/app/assets/[asset_id]/proof/page.tsx
    symbols: [AssetProofPage]
requirements:
  - "GET /api/creator-economy/stats — public stats: total_creators, total_blueprints, total_cc_distributed, total_uses, verified_since"
  - "GET /api/assets/{id}/proof-card — shareable proof card: asset name, creator, use_count, cc_earned, arweave_url, verification_url"
  - "GET /api/creator-economy/featured — paginated list of featured assets with use_count, asset_type, creator handle"
  - "AssetType enum gains BLUEPRINT, DESIGN, RESEARCH values (backwards-compatible extension)"
  - "POST /api/assets with type=BLUEPRINT|DESIGN|RESEARCH registers creator asset with community_tags field"
  - "Web /creators page renders pitch + live stats from /api/creator-economy/stats"
  - "Web /creators/submit page drives asset submission for BLUEPRINT/DESIGN/RESEARCH types"
  - "Web /assets/{id}/proof renders proof card with shareable link + verification chain link"
done_when:
  - "GET /api/creator-economy/stats returns JSON with all 5 fields and HTTP 200"
  - "GET /api/assets/{id}/proof-card returns proof card with arweave_url field for any published asset"
  - "BLUEPRINT, DESIGN, RESEARCH values accepted by POST /api/assets without 422"
  - "GET /api/creator-economy/featured returns paginated list with community_tags field"
  - "Web /creators page loads without 500, renders stats section"
  - "Web /assets/{id}/proof page renders for a valid asset ID"
test: "cd api && python -m pytest tests/test_creator_economy.py -x -q"
constraints:
  - "No schema migrations — community_tags stored as JSON string in existing asset metadata column"
  - "Stats endpoint adds zero latency to asset read path (pre-computed, cached 5 min)"
  - "Proof card links to existing /api/verification/chain/{asset_id} — no new chain logic"
  - "AssetType extension is additive only — existing CODE/MODEL/CONTENT/DATA values unchanged"
  - "No paywalls, subscriptions, or gating on any creator-facing surface"
---

# Spec: Creator Economy Promotion

## Purpose

Once the attribution system is publicly verified (Story Protocol + Arweave), the next bottleneck is awareness: creators in target communities don't know provably fair attribution exists. This spec builds the minimal surfaces that let creators discover, verify, and share proof that contributing blueprints, designs, and research to Coherence Network earns CC when others use their work — with no paywalls, no subscriptions, and a public audit trail anyone can check. Target communities: GEN/ic.org intentional communities, Printables/Thingiverse 3D model creators, WikiHouse/One Community Global open-source architecture, permaculture designers, transition towns.

## Requirements

- [ ] **R1**: `GET /api/creator-economy/stats` — returns a public, cached summary object with fields: `total_creators` (distinct contributors with at least one BLUEPRINT/DESIGN/RESEARCH asset), `total_blueprints` (asset count across those types), `total_cc_distributed` (sum of CC earned on those assets), `total_uses` (sum of use/download counts), `verified_since` (ISO 8601 date of first Arweave snapshot). HTTP 200 always; values computed from existing assets + contributions tables and cached 5 minutes.

- [ ] **R2**: `GET /api/assets/{id}/proof-card` — returns a shareable proof card for any asset with fields: `asset_id`, `name`, `creator_handle`, `asset_type`, `use_count`, `cc_earned`, `arweave_url` (latest snapshot URL or `null` if not yet published), `verification_url` (link to `/api/verification/chain/{asset_id}`), `community_tags` (list, may be empty). 404 if asset not found.

- [ ] **R3**: `GET /api/creator-economy/featured` — returns paginated list of featured assets (query params: `limit` default 12, `offset` default 0, optional `asset_type` filter, optional `community_tag` filter). Each item includes `asset_id`, `name`, `creator_handle`, `asset_type`, `use_count`, `cc_earned`, `community_tags`. Ordered by `use_count DESC`.

- [ ] **R4**: `AssetType` enum in `api/app/models/asset.py` gains three new values: `BLUEPRINT` (physical or digital design file, e.g. 3D model, CAD), `DESIGN` (architectural or spatial design), `RESEARCH` (documentation, data, or analysis). Existing values `CODE`, `MODEL`, `CONTENT`, `DATA` remain unchanged. The DB column accepts these values via the existing string storage — no migration needed.

- [ ] **R5**: `POST /api/assets` accepts the new asset types and an optional `community_tags` field (list of strings, max 10 tags, each max 50 chars). Tags stored as JSON string in the asset's `metadata` column under key `"community_tags"`. Existing asset creation flow unchanged for assets without this field.

- [ ] **R6**: Web `/creators` page — static Next.js page that renders: (a) the creator pitch in plain language ("contribute your blueprints, designs, research — earn CC when others use them — provably fair, no paywalls"), (b) a live stats section pulling from `GET /api/creator-economy/stats`, (c) a call-to-action linking to `/creators/submit`, and (d) a list of featured assets from `GET /api/creator-economy/featured`. Page renders correctly with a loading state if the API is slow.

- [ ] **R7**: Web `/creators/submit` page — form-driven asset submission for BLUEPRINT, DESIGN, and RESEARCH types. Fields: name (required), asset_type (required, picker showing the three types with descriptions), description (required), community_tags (optional, free-text comma-separated), file URL or GitHub URL (required). Submits to `POST /api/assets`. On success, redirects to `/assets/{id}/proof`. On error, displays the API error message.

- [ ] **R8**: Web `/assets/{id}/proof` page — renders the proof card for an asset using `GET /api/assets/{id}/proof-card`. Shows: name, creator, type, use count, CC earned, a "Verify on Arweave" button (links to `arweave_url`), a "Check Verification Chain" button (links to `verification_url`), and a copy-to-clipboard "Share proof" button with the full URL. Renders 404 gracefully. This page is shareable — it is the artifact creators send to community admins as proof.

## Research Inputs

- `2026-04-24` — GEN Network (gen.ecovillage.org) — accepts project submissions; prefers shareable links showing provenance and open licensing
- `2026-04-24` — ic.org directory — community submission form exists; needs clear one-sentence pitch + proof link
- `2026-04-24` — Printables community — top creators share "model stats" screenshots; a proof card URL would fit that behavior
- `2026-04-24` — WikiHouse / One Community Global — both are GitHub-centric; proof of CC earnings from design reuse is a novel value prop
- `2026-04-24` — Transition Towns network — newsletter-driven; a single public URL with live stats is the right entry point

## API Contract

### `GET /api/creator-economy/stats`

**Response 200**
```json
{
  "total_creators": 14,
  "total_blueprints": 38,
  "total_cc_distributed": 1240.5,
  "total_uses": 892,
  "verified_since": "2026-01-15T00:00:00Z"
}
```

### `GET /api/assets/{id}/proof-card`

**Response 200**
```json
{
  "asset_id": "a1b2c3d4-...",
  "name": "WikiHouse Roof Panel v2",
  "creator_handle": "builder_zenn",
  "asset_type": "BLUEPRINT",
  "use_count": 47,
  "cc_earned": 94.0,
  "arweave_url": "https://arweave.net/abc123",
  "verification_url": "/api/verification/chain/a1b2c3d4-...",
  "community_tags": ["wikihouse", "open-architecture", "transition-towns"]
}
```

**Response 404**
```json
{"detail": "Asset not found"}
```

### `GET /api/creator-economy/featured`

**Query params**: `limit` (int, default 12), `offset` (int, default 0), `asset_type` (optional string), `community_tag` (optional string)

**Response 200**
```json
{
  "items": [
    {
      "asset_id": "a1b2c3d4-...",
      "name": "WikiHouse Roof Panel v2",
      "creator_handle": "builder_zenn",
      "asset_type": "BLUEPRINT",
      "use_count": 47,
      "cc_earned": 94.0,
      "community_tags": ["wikihouse"]
    }
  ],
  "total": 38,
  "limit": 12,
  "offset": 0
}
```

## Data Model

```yaml
# New Pydantic models in api/app/models/creator_economy.py
CreatorStats:
  total_creators: int
  total_blueprints: int
  total_cc_distributed: float
  total_uses: int
  verified_since: datetime | None

ProofCard:
  asset_id: str
  name: str
  creator_handle: str
  asset_type: str
  use_count: int
  cc_earned: float
  arweave_url: str | None
  verification_url: str
  community_tags: list[str]

FeaturedAsset:
  asset_id: str
  name: str
  creator_handle: str
  asset_type: str
  use_count: int
  cc_earned: float
  community_tags: list[str]

FeaturedAssetsResponse:
  items: list[FeaturedAsset]
  total: int
  limit: int
  offset: int

# AssetType enum extension (api/app/models/asset.py)
# Existing: CODE, MODEL, CONTENT, DATA
# Added:
BLUEPRINT = "BLUEPRINT"
DESIGN = "DESIGN"
RESEARCH = "RESEARCH"

# community_tags stored in existing asset metadata JSON column:
# asset.metadata["community_tags"] = ["tag1", "tag2"]
```

## Files

### New files
- `api/app/routers/creator_economy.py` — three route handlers: `get_creator_stats`, `get_asset_proof_card`, `list_featured_assets`
- `api/app/services/creator_economy_service.py` — `compute_creator_stats()` (cached), `build_proof_card(asset_id)`, `list_featured(limit, offset, asset_type, community_tag)`
- `api/app/models/creator_economy.py` — `CreatorStats`, `ProofCard`, `FeaturedAsset`, `FeaturedAssetsResponse`
- `api/tests/test_creator_economy.py` — flow tests covering all three endpoints
- `web/app/creators/page.tsx` — creator landing page
- `web/app/creators/submit/page.tsx` — asset submission form
- `web/app/assets/[asset_id]/proof/page.tsx` — shareable proof card page

### Modified files
- `api/app/models/asset.py` — add `BLUEPRINT`, `DESIGN`, `RESEARCH` to `AssetType` enum; add `community_tags` optional field to `AssetCreate`
- `api/app/routers/assets.py` — accept `community_tags` in `create_asset()`; store in `metadata` JSON
- `api/app/main.py` — register `creator_economy` router at `/api/creator-economy`

## Verification Scenarios

**Scenario 1 — Stats endpoint returns all fields**
```bash
curl -s https://api.coherencycoin.com/api/creator-economy/stats | \
  python3 -c "import sys,json; d=json.load(sys.stdin); \
  assert 'total_creators' in d and 'total_cc_distributed' in d and 'verified_since' in d, \
  'missing fields'; print('PASS:', d)"
# Expected: PASS: {...} with all 5 fields present
```

**Scenario 2 — Create a BLUEPRINT asset and retrieve its proof card**
```bash
# Create the asset
ASSET=$(curl -s -X POST https://api.coherencycoin.com/api/assets \
  -H "Content-Type: application/json" \
  -d '{"name":"Test Roof Panel","description":"WikiHouse test","asset_type":"BLUEPRINT","community_tags":["wikihouse"],"contributor_id":"test-user"}')
ID=$(echo $ASSET | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# Fetch proof card
curl -s https://api.coherencycoin.com/api/assets/$ID/proof-card | \
  python3 -c "import sys,json; d=json.load(sys.stdin); \
  assert d['asset_type']=='BLUEPRINT', 'wrong type'; \
  assert 'wikihouse' in d['community_tags'], 'tag missing'; print('PASS')"
# Expected: PASS
```

**Scenario 3 — Featured assets endpoint with community_tag filter**
```bash
curl -s "https://api.coherencycoin.com/api/creator-economy/featured?asset_type=BLUEPRINT&limit=5" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); \
  assert 'items' in d and 'total' in d, 'missing pagination'; \
  assert all(i['asset_type']=='BLUEPRINT' for i in d['items']), 'type filter broken'; \
  print('PASS: total=', d['total'])"
# Expected: PASS: total= <N>
```

**Scenario 4 — Proof card 404 for unknown asset**
```bash
curl -s -o /dev/null -w "%{http_code}" \
  https://api.coherencycoin.com/api/assets/00000000-0000-0000-0000-000000000000/proof-card
# Expected: 404
```

**Scenario 5 — AssetType rejection for invalid type is still enforced**
```bash
curl -s -X POST https://api.coherencycoin.com/api/assets \
  -H "Content-Type: application/json" \
  -d '{"name":"Bad","description":"bad","asset_type":"INVALID","contributor_id":"test-user"}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); \
  assert d.get('detail') is not None, 'should have rejected invalid type'; print('PASS')"
# Expected: PASS (422 Unprocessable Entity)
```

## Measuring Whether It's Working

The open question from the idea brief — "how do we show whether this is working and make proof clearer over time" — is addressed through these built-in signals:

1. **`total_uses` growth rate** in `/api/creator-economy/stats` over time is the primary indicator. If creators share proof cards and communities adopt, use counts on BLUEPRINT/DESIGN/RESEARCH assets rise.
2. **`community_tags` distribution** in `/api/creator-economy/featured` shows which communities are actually engaging vs. which are aspirational.
3. **`total_cc_distributed`** growth relative to `total_creators` shows whether the per-creator value proposition is increasing (attribution is paying off) or stagnating (creators are contributing but not seeing CC flow back).
4. **Proof card share rate** is a proxy metric — if `/assets/{id}/proof` page views grow, creators are finding it worth sharing. This is visible in existing API request logs.
5. **Monthly snapshot**: run `GET /api/creator-economy/stats` and log to a file; diff over 30 days gives a clear trend signal without any new analytics infrastructure.

## Out of Scope

- Payment gateway or fiat conversion for CC earnings (covered by `financial-integration` spec)
- Automated community outreach bots or newsletter automation (covered by `external-presence-bots-and-news` spec)
- Creator identity verification or KYC (covered by `identity-driven-onboarding-tofu` spec)
- Marketplace listing or searchable catalog beyond the featured endpoint (covered by `assets-api` + future marketplace spec)
- IP registration on Story Protocol for new creator assets (covered by `story-protocol-integration` spec)

## Risks and Assumptions

- **Assumption**: Existing `asset.metadata` column is a JSON-compatible string field that can hold `community_tags`. If it's absent or typed differently, the `community_tags` storage approach changes to a new `asset_tags` join table — but spec requirements do not change.
- **Risk**: Stats endpoint cold-starts (no BLUEPRINT/DESIGN/RESEARCH assets yet) return zeros, which may look empty on launch. Mitigation: seed 2-3 real demo assets during deploy verification.
- **Risk**: `total_cc_distributed` only reflects assets where distribution has been computed. If the distribution engine hasn't run for newer assets, the number understates reality. Mitigation: document this clearly on the `/creators` page stats section with a "last computed" timestamp.
- **Assumption**: The `contributor_handle` is derivable from the contributor record linked to the asset's contributions. If contributors have no handle set, fall back to `contributor_id[:8]` for display.
- **Risk**: Community targeting (GEN, ic.org, Printables) requires human outreach that this spec's surfaces enable but do not perform. The spec delivers the proof surfaces; actual community engagement is an operational task outside this implementation.
