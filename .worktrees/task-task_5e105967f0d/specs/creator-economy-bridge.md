---
idea_id: creator-economy-bridge
status: active
source:
  - file: api/app/models/creator_economy.py
    symbols: [ExternalPlatform, MirroredAsset, FrequencyProfile, CreatorCommunity, CommunityAlgorithm]
  - file: api/app/services/creator_economy_service.py
    symbols: [compute_frequency_profile(), find_resonant_creators(), register_community(), apply_community_algorithm(), register_mirrored_asset()]
  - file: api/app/routers/creator_economy.py
    symbols: [mirror_external_content(), get_creator_frequency(), create_community(), get_community(), update_community_algorithm()]
  - file: api/tests/test_creator_economy_bridge.py
    symbols: [test_mirror_asset_200, test_frequency_profile_200, test_community_create_and_algorithm_update, test_resonant_creators_returned, test_engagement_ping_200]
  - file: web/app/creators/[handle]/page.tsx
    symbols: [CreatorProfilePage]
  - file: web/app/communities/page.tsx
    symbols: [CommunitiesPage]
  - file: web/app/communities/[id]/page.tsx
    symbols: [CommunityDetailPage]
requirements:
  - "POST /api/creator-economy/mirror — register an external content URL (platform, external_url, title, community_tags) and return a MirroredAsset with a local asset_id; creator identified by authenticated handle"
  - "POST /api/creator-economy/mirror/ping/{asset_id} — record one engagement event for a mirrored asset (proxy read/view), incrementing use_count; no auth required (beacon-style)"
  - "GET /api/creator-economy/creators/{handle}/frequency — return FrequencyProfile: top topic weights, resonance_score 0.0–1.0, active_platforms list, community_tags aggregated across all mirrored assets"
  - "GET /api/creator-economy/creators/{handle}/resonant — return up to 20 creators sorted by frequency profile cosine similarity to the given handle"
  - "POST /api/creator-economy/communities — create a CreatorCommunity with name, description, founding_handles (list), focus_tags (list); returns community_id"
  - "GET /api/creator-economy/communities/{id} — return community detail: name, member handles, focus_tags, algorithm weights, total_cc_distributed"
  - "PATCH /api/creator-economy/communities/{id}/algorithm — update CommunityAlgorithm weights (dict of tag → weight float); weights must sum to 1.0 ± 0.01; only founding members may call"
  - "CC distribution engine reads community algorithm weights when distributing to members of that community; fall back to platform default weights when no community algorithm is set"
  - "ExternalPlatform enum: YOUTUBE, INSTAGRAM, SUBSTACK, TIKTOK, OTHER"
  - "FrequencyProfile resonance_score derives from engagement rate (use_count / days_since_first_mirror) × tag diversity index; stored and refreshed on each ping"
done_when:
  - "POST /api/creator-economy/mirror returns HTTP 201 with asset_id and platform fields"
  - "POST /api/creator-economy/mirror/ping/{asset_id} returns HTTP 200 and increments use_count by 1"
  - "GET /api/creator-economy/creators/{handle}/frequency returns resonance_score between 0.0 and 1.0"
  - "GET /api/creator-economy/creators/{handle}/resonant returns list of handles sorted by similarity desc"
  - "POST /api/creator-economy/communities returns HTTP 201 with community_id"
  - "PATCH /api/creator-economy/communities/{id}/algorithm with weights summing to 0.999 returns HTTP 422"
  - "PATCH /api/creator-economy/communities/{id}/algorithm with valid weights returns HTTP 200"
  - "all tests in api/tests/test_creator_economy_bridge.py pass"
test: "cd api && python -m pytest tests/test_creator_economy_bridge.py -q"
constraints:
  - "No platform OAuth required — creators self-declare their external URLs; authenticity is the creator's responsibility"
  - "Engagement pings are unauthenticated to allow iframe/embed beacons; rate-limit to 1 unique IP per asset per hour in production"
  - "Community algorithm weights validation: all keys must appear in the community's focus_tags; values must be floats 0.0–1.0; sum 1.0 ± 0.01"
  - "Frequency profile computation is synchronous and in-process for MVP; no background jobs"
  - "Do not break existing creator-economy-promotion endpoints (stats, proof-card, featured)"
---

# Spec: Creator Economy Bridge

## Purpose

Creators who publish on YouTube, Instagram, Substack, or TikTok accumulate audiences they cannot own and earn from algorithms they cannot see. This spec lets them register their external content as mirrored assets inside the Coherence Network, track real engagement as a proxy, and earn CC in proportion to resonance — not ad impressions. When creators discover others with similar frequency profiles, they form communities and define their own distribution algorithm. The algorithm becomes the community's collective values made explicit.

## Requirements

- [ ] **R1 — Mirror Registration**: `POST /api/creator-economy/mirror` accepts `platform` (ExternalPlatform enum), `external_url`, `title`, optional `description`, optional `community_tags[]`. Returns a `MirroredAsset` with `asset_id`, `platform`, `external_url`, `creator_handle`, `community_tags`, `mirrored_at`. The asset is registered in the existing in-process asset registry so it appears in `/api/creator-economy/featured` and can earn CC through the distribution engine.

- [ ] **R2 — Engagement Beacon**: `POST /api/creator-economy/mirror/ping/{asset_id}` is an unauthenticated, rate-limited endpoint that increments `use_count` for the asset and triggers a `FrequencyProfile` refresh for the creator. Used as an embed beacon in iframes or linked-out pages. Returns `{"asset_id": "...", "use_count": N}`.

- [ ] **R3 — Frequency Profile**: `GET /api/creator-economy/creators/{handle}/frequency` returns the creator's `FrequencyProfile`: aggregated `topic_weights` (tag → float), `resonance_score` (0.0–1.0), `active_platforms` (list of ExternalPlatform values with at least one mirrored asset), `total_assets`, `total_uses`. `resonance_score` = min(1.0, (uses_per_day × tag_diversity_index) / calibration_constant) where calibration_constant = 10.0 for MVP.

- [ ] **R4 — Resonant Creator Discovery**: `GET /api/creator-economy/creators/{handle}/resonant?limit=20` returns a list of `{handle, resonance_score, shared_tags[]}` sorted by cosine similarity between the queried creator's `topic_weights` vector and each other registered creator's vector. Only creators with at least one mirrored asset are included.

- [ ] **R5 — Community Formation**: `POST /api/creator-economy/communities` accepts `name`, `description`, `founding_handles[]` (1–10), `focus_tags[]` (1–20). Returns `CreatorCommunity` with `community_id`, `name`, `founding_handles`, `focus_tags`, `created_at`. Any handle in `founding_handles` may later modify the community algorithm.

- [ ] **R6 — Community Detail**: `GET /api/creator-economy/communities/{id}` returns full community including `member_handles`, `focus_tags`, `algorithm` (CommunityAlgorithm with `weights` dict), `total_cc_distributed`.

- [ ] **R7 — Algorithm Customization**: `PATCH /api/creator-economy/communities/{id}/algorithm` accepts `weights: dict[str, float]`. Validates: all keys in `focus_tags`, all values in [0.0, 1.0], sum ∈ [0.99, 1.01]. On success stores and returns updated `CommunityAlgorithm`. Returns HTTP 422 on invalid weights with a `detail` message listing the violations.

- [ ] **R8 — Distribution Integration**: The CC distribution engine (`distribution_engine.py` or equivalent) checks if the receiving creator belongs to a community; if so, applies the community's `algorithm.weights` to scale CC allocation by tag relevance of the contributing asset. Falls back to uniform weighting when no community algorithm is defined.

## Research Inputs

- `2026-04-26` — Task description (Coherence Network pipeline) — defines the full creator bridge vision: platform mirroring, proxy engagement, frequency profiles, community formation, algorithm-as-values

## API Contract

### `POST /api/creator-economy/mirror`

**Request**
```json
{
  "platform": "YOUTUBE",
  "external_url": "https://youtube.com/watch?v=abc123",
  "title": "Regenerative Agriculture Deep Dive",
  "description": "45-minute exploration of soil biology",
  "community_tags": ["permaculture", "soil", "regenerative"]
}
```

**Response 201**
```json
{
  "asset_id": "mirror-abc123",
  "platform": "YOUTUBE",
  "external_url": "https://youtube.com/watch?v=abc123",
  "title": "Regenerative Agriculture Deep Dive",
  "creator_handle": "alice",
  "community_tags": ["permaculture", "soil", "regenerative"],
  "mirrored_at": "2026-04-26T10:00:00Z"
}
```

### `POST /api/creator-economy/mirror/ping/{asset_id}`

**Response 200**
```json
{
  "asset_id": "mirror-abc123",
  "use_count": 42
}
```

### `GET /api/creator-economy/creators/{handle}/frequency`

**Response 200**
```json
{
  "handle": "alice",
  "resonance_score": 0.73,
  "topic_weights": {"permaculture": 0.6, "soil": 0.3, "regenerative": 0.1},
  "active_platforms": ["YOUTUBE", "SUBSTACK"],
  "total_assets": 5,
  "total_uses": 312
}
```

### `GET /api/creator-economy/creators/{handle}/resonant`

**Response 200**
```json
{
  "handle": "alice",
  "resonant_creators": [
    {"handle": "bob", "similarity": 0.91, "shared_tags": ["permaculture", "soil"]},
    {"handle": "carol", "similarity": 0.74, "shared_tags": ["regenerative"]}
  ]
}
```

### `POST /api/creator-economy/communities`

**Request**
```json
{
  "name": "Regenerative Makers",
  "description": "Creators growing the living economy",
  "founding_handles": ["alice", "bob"],
  "focus_tags": ["permaculture", "soil", "regenerative", "food-systems"]
}
```

**Response 201**
```json
{
  "community_id": "comm-regen-001",
  "name": "Regenerative Makers",
  "founding_handles": ["alice", "bob"],
  "focus_tags": ["permaculture", "soil", "regenerative", "food-systems"],
  "created_at": "2026-04-26T10:00:00Z"
}
```

### `PATCH /api/creator-economy/communities/{id}/algorithm`

**Request**
```json
{
  "weights": {
    "permaculture": 0.4,
    "soil": 0.3,
    "regenerative": 0.2,
    "food-systems": 0.1
  }
}
```

**Response 200**
```json
{
  "community_id": "comm-regen-001",
  "weights": {
    "permaculture": 0.4,
    "soil": 0.3,
    "regenerative": 0.2,
    "food-systems": 0.1
  },
  "updated_at": "2026-04-26T11:00:00Z"
}
```

**Response 422 (invalid weights)**
```json
{
  "detail": "weights sum to 0.999, must be within 0.01 of 1.0"
}
```

## Data Model

```yaml
ExternalPlatform (enum):
  values: [YOUTUBE, INSTAGRAM, SUBSTACK, TIKTOK, OTHER]

MirroredAsset:
  asset_id: str          # "mirror-{slug}"
  platform: ExternalPlatform
  external_url: str
  title: str
  description: Optional[str]
  creator_handle: str
  community_tags: List[str]
  mirrored_at: datetime  # UTC
  use_count: int         # incremented by ping endpoint

FrequencyProfile:
  handle: str
  resonance_score: float  # 0.0–1.0
  topic_weights: dict     # tag → float (sum = 1.0)
  active_platforms: List[ExternalPlatform]
  total_assets: int
  total_uses: int
  computed_at: datetime

CreatorCommunity:
  community_id: str
  name: str
  description: str
  founding_handles: List[str]
  member_handles: List[str]  # grows as resonant creators join
  focus_tags: List[str]
  algorithm: Optional[CommunityAlgorithm]
  total_cc_distributed: Decimal
  created_at: datetime

CommunityAlgorithm:
  community_id: str
  weights: dict   # tag → float, sum = 1.0
  updated_at: datetime
```

## Files

### New files (to create)
- `api/tests/test_creator_economy_bridge.py` — flow tests: mirror registration, ping beacon, frequency profile, resonant discovery, community CRUD, algorithm validation, distribution integration

### Existing files (to modify)
- `api/app/models/creator_economy.py` — add `ExternalPlatform`, `MirroredAsset`, `FrequencyProfile`, `CreatorCommunity`, `CommunityAlgorithm`, `ResonantCreatorsResponse`
- `api/app/services/creator_economy_service.py` — add `register_mirrored_asset()`, `record_ping()`, `compute_frequency_profile()`, `find_resonant_creators()`, `register_community()`, `get_community()`, `apply_community_algorithm()`
- `api/app/routers/creator_economy.py` — add new routes: POST mirror, POST ping, GET frequency, GET resonant, POST communities, GET community, PATCH algorithm
- `web/app/creators/[handle]/page.tsx` — creator profile page: platform link cards, frequency radar chart, resonant creators section
- `web/app/communities/page.tsx` — community discovery list with frequency tag cloud
- `web/app/communities/[id]/page.tsx` — community detail: member list, algorithm weight editor, CC distributed counter

## Verification Scenarios

### Scenario 1 — Mirror a YouTube video and check it appears in featured

```bash
# Register a mirrored asset
curl -s -X POST https://api.coherencycoin.com/api/creator-economy/mirror \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"platform":"YOUTUBE","external_url":"https://youtube.com/watch?v=test1","title":"Test Video","community_tags":["permaculture"]}' \
  | jq '{asset_id,platform,creator_handle}'
# Expected: {"asset_id": "mirror-...", "platform": "YOUTUBE", "creator_handle": "<your handle>"}

# Confirm it appears in featured
curl -s "https://api.coherencycoin.com/api/creator-economy/featured?community_tag=permaculture" \
  | jq '.items | length'
# Expected: >= 1
```

### Scenario 2 — Ping beacon increments use_count

```bash
ASSET_ID="mirror-test-001"  # substitute real asset_id from Scenario 1

# Baseline
curl -s "https://api.coherencycoin.com/api/creator-economy/mirror/ping/$ASSET_ID" | jq '.use_count'
# Record N

# Second ping (from different IP or after rate-limit window)
curl -s "https://api.coherencycoin.com/api/creator-economy/mirror/ping/$ASSET_ID" | jq '.use_count'
# Expected: N+1
```

### Scenario 3 — Frequency profile reflects mirrored content

```bash
# After at least one mirrored asset + one ping
curl -s "https://api.coherencycoin.com/api/creator-economy/creators/alice/frequency" \
  | jq '{resonance_score, active_platforms, total_uses}'
# Expected: resonance_score in [0.0, 1.0], active_platforms includes "YOUTUBE", total_uses >= 1
```

### Scenario 4 — Community creation and algorithm validation

```bash
# Create community
COMM=$(curl -s -X POST https://api.coherencycoin.com/api/creator-economy/communities \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name":"Regen Makers","description":"test","founding_handles":["alice"],"focus_tags":["permaculture","soil"]}')
echo $COMM | jq '.community_id'
# Expected: non-empty string

COMM_ID=$(echo $COMM | jq -r '.community_id')

# Try invalid weights (sum < 1.0)
curl -s -X PATCH "https://api.coherencycoin.com/api/creator-economy/communities/$COMM_ID/algorithm" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"weights":{"permaculture":0.3,"soil":0.3}}' \
  | jq '.detail'
# Expected: string containing "sum"

# Apply valid weights
curl -s -X PATCH "https://api.coherencycoin.com/api/creator-economy/communities/$COMM_ID/algorithm" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"weights":{"permaculture":0.6,"soil":0.4}}' \
  | jq '.weights'
# Expected: {"permaculture": 0.6, "soil": 0.4}
```

### Scenario 5 — Resonant creator discovery

```bash
# After two creators have mirrored assets with overlapping tags
curl -s "https://api.coherencycoin.com/api/creator-economy/creators/alice/resonant?limit=5" \
  | jq '.resonant_creators[0]'
# Expected: object with handle, similarity (0–1), shared_tags array
```

## Risks and Assumptions

- **Risk — URL authenticity**: Creators self-declare external URLs. A bad actor could claim another creator's content. Mitigation: add optional `verification_token` in MVP (embed a text file at `{domain}/.well-known/coherence-verify.txt`); full OAuth integration is out of scope for this spec.
- **Risk — Ping abuse**: Unauthenticated beacon endpoint could be flooded. Mitigation: rate-limit to 1 event per (asset_id, remote_ip) per hour; implement with in-process set for MVP.
- **Risk — Frequency profile gaming**: Creators could self-ping to inflate resonance_score. Mitigation: the rate-limit above caps artificial inflation; long-term, weight organic referrers higher — out of scope here.
- **Assumption — Distribution engine extensibility**: The existing distribution engine accepts tag-weighted inputs or can be extended to do so. If the distribution engine has no concept of tag weights, R8 reduces to recording the community algorithm without yet applying it.
- **Assumption — Creator auth**: An authenticated creator handle is available on the request context. If the auth system does not yet surface a stable handle, mirror registration will need a `handle` field in the request body as a temporary bypass.
- **Out of scope**: OAuth token validation with external platforms, automatic content mirroring/RSS ingestion, revenue sharing with external platforms, mobile app deep-links, paid community tiers.
