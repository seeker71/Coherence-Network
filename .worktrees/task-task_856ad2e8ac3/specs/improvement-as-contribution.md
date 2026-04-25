---
idea_id: improvement-as-contribution
status: active
source:
  - file: api/app/routers/renderers.py
    symbols: [register_renderer(), list_renderers(), get_renderer_for_mime(), get_renderer_versions()]
  - file: api/app/models/renderer.py
    symbols: [Renderer, RendererCreate, RendererVersion, ProviderType]
  - file: api/app/services/render_attribution_service.py
    symbols: [attribute_render_cc(), resolve_renderer_for_asset()]
  - file: api/app/routers/hosting_nodes.py
    symbols: [register_node(), record_node_request(), get_node_stats()]
  - file: api/app/models/hosting_node.py
    symbols: [HostingNode, NodeRequest, NodePerformanceStats]
  - file: api/app/services/node_attribution_service.py
    symbols: [attribute_node_cc(), select_fastest_node()]
  - file: api/app/routers/generators.py
    symbols: [register_generator(), list_generators(), get_generator_versions()]
  - file: api/app/models/generator.py
    symbols: [Generator, GeneratorVersion, GenerationEvent]
  - file: api/app/services/generation_attribution_service.py
    symbols: [attribute_generation_cc(), record_generation_event()]
  - file: api/app/routers/provider_versions.py
    symbols: [register_provider_version(), list_provider_versions(), get_version_stats()]
  - file: api/app/models/provider_version.py
    symbols: [ProviderVersion, ProviderType, VersionStats]
  - file: api/app/services/provider_competition_service.py
    symbols: [select_provider_version(), record_usage_event(), compute_usage_share()]
  - file: api/tests/test_improvement_as_contribution.py
    symbols: [test cases for all provider types and version competition]
requirements:
  - "Any renderer, hosting node, or generator can be forked and registered as a new provider version via POST /api/provider-versions/register"
  - "Every render event, hosting request, or generation event records which provider version served it"
  - "CC attribution flows to the provider version that served the event at its configured share rate"
  - "Multiple versions of the same provider coexist — usage decides winner, no committee"
  - "Provider version stats (usage count, CC earned, p95 latency) exposed via GET /api/provider-versions/{id}/stats"
  - "Default CC split for renderers: 80% asset creator / 15% renderer version / 5% host node"
  - "Default CC split for hosting nodes: 5% per request, drawn from content-access CC pool"
  - "Default CC split for generators: 10% generator creator per downstream read of generated assets"
  - "CC shares are configurable per provider version at registration time and frozen after first use"
  - "Superseded versions remain active and continue earning if users still select them"
  - "GET /api/provider-versions lists all registered versions grouped by provider type and base provider"
  - "GET /api/provider-versions/{id}/competition shows all sibling versions and their usage share"
  - "POST /api/render-events, POST /api/hosting-events, POST /api/generation-events each accept a provider_version_id field"
  - "Missing or unknown provider_version_id falls back to the default (highest usage share) version"
  - "Dashboard endpoint GET /api/provider-versions/leaderboard returns top N versions by CC earned in a time window"
done_when:
  - "POST /api/provider-versions/register returns 201 with version_id for renderer, hosting, and generator provider types"
  - "POST /api/render-events with provider_version_id triggers CC attribution to that version's creator"
  - "GET /api/provider-versions/{id}/stats returns usage_count, cc_earned, p95_latency_ms"
  - "GET /api/provider-versions/{id}/competition returns all sibling versions with usage_share summing to 1.0"
  - "GET /api/provider-versions/leaderboard returns top versions sorted by cc_earned descending"
  - "Two versions of the same renderer both appear in competition response and each earn CC on their respective events"
  - "all tests in api/tests/test_improvement_as_contribution.py pass"
test: "cd api && python -m pytest tests/test_improvement_as_contribution.py -q"
constraints:
  - "CC shares frozen after first use — no retroactive redistribution"
  - "Provider version registration is append-only; no deletion of versions with usage history"
  - "Existing render-events, hosting, and generation flows must remain backward compatible"
  - "No changes to existing CC split defaults in asset-renderer-plugin spec"
  - "provider_version_id is optional on all event endpoints; unknown IDs fall back gracefully"
---

# Spec: Improvement as Contribution

## Purpose

Every infrastructure improvement — faster renderer, higher-availability hosting node, better image generator — earns Coherence Credit when it serves real usage. The improvement IS the contribution: fork it, register it, let usage decide the winner. This closes the loop between infrastructure work and value attribution without requiring any committee to pick a winner. The original provider keeps earning; the improvement earns in parallel, proportional to how often it is chosen. Over time the leaderboard makes it visible which improvements are gaining ground — that visibility IS the proof.

## Requirements

### R1 — Provider Version Registry

A unified registry (`provider_version_id`) covers all infrastructure provider types: `renderer`, `hosting_node`, `generator`. Each version record carries:

- `provider_type`: enum(`renderer` | `hosting_node` | `generator`)
- `base_provider_id`: ID of the provider being improved (or `null` for first-generation)
- `creator_id`: contributor who registered this version
- `component_url` / `endpoint_url`: where the provider is reachable
- `cc_share`: fraction of the applicable CC pool this version claims (frozen after first event)
- `registered_at`, `first_used_at` (set on first event), `status`: `active` | `deprecated`

Files:
- `api/app/routers/provider_versions.py` — CRUD for all provider version types
- `api/app/models/provider_version.py` — `ProviderVersion`, `ProviderType`, `VersionStats`

### R2 — Renderer Version Competition

When a render event arrives, the event body MAY include `provider_version_id`. If present and valid, CC is attributed to that version's creator at its `cc_share`. If absent, the platform selects the version with the highest current usage share for that MIME type.

Both the original renderer and any forked improvement remain active. Neither is deprecated unless its creator explicitly marks it so.

Files:
- `api/app/routers/renderers.py` — add `get_renderer_versions()` endpoint
- `api/app/models/renderer.py` — add `RendererVersion` extending `ProviderVersion`
- `api/app/services/render_attribution_service.py` — update `attribute_render_cc()` to accept `provider_version_id`

### R3 — Hosting Node Version Competition

Hosting nodes earn CC on each request they serve. A faster node registers as a new version of an existing node provider. The platform can route new requests to the faster node (explicit `provider_version_id` or automatic selection by lowest p95 latency). Both nodes earn CC on requests they serve.

Files:
- `api/app/routers/hosting_nodes.py` — add `record_node_request()` with `provider_version_id`
- `api/app/models/hosting_node.py` — `HostingNode`, `NodeRequest`, `NodePerformanceStats`
- `api/app/services/node_attribution_service.py` — `attribute_node_cc()`, `select_fastest_node()`

### R4 — Generator Version Competition

Image and content generators are registered as versioned providers. Each generation event records which version produced the asset. When the generated asset is subsequently read, a fraction of the read CC flows back to the generator version's creator. A better generator producing higher-read assets earns more over time.

Files:
- `api/app/routers/generators.py` — `register_generator()`, `list_generators()`, `get_generator_versions()`
- `api/app/models/generator.py` — `Generator`, `GeneratorVersion`, `GenerationEvent`
- `api/app/services/generation_attribution_service.py` — `attribute_generation_cc()`, `record_generation_event()`

### R5 — Competition Dashboard

The competition endpoint and leaderboard make it observable which versions are winning:

- `GET /api/provider-versions/{id}/competition` — all sibling versions, their `usage_count`, `cc_earned`, `usage_share` (sums to 1.0 across siblings)
- `GET /api/provider-versions/leaderboard?type=renderer&window=7d&limit=10` — top N versions by CC earned

This is the proof that the system works. The leaderboard IS the signal.

Files:
- `api/app/routers/provider_versions.py` — add `get_competition()`, `get_leaderboard()`
- `api/app/services/provider_competition_service.py` — `compute_usage_share()`, leaderboard query

## API Contract

### `POST /api/provider-versions/register`

**Request**
```json
{
  "provider_type": "renderer",
  "base_provider_id": "renderer-abc123",
  "creator_id": "contributor-xyz",
  "component_url": "https://cdn.example.com/fast-gltf-renderer.js",
  "cc_share": 0.15,
  "metadata": {"mime_type": "model/gltf+json", "description": "WASM-accelerated GLTF renderer"}
}
```

**Response 201**
```json
{
  "version_id": "pv-gltf-v2-789",
  "provider_type": "renderer",
  "base_provider_id": "renderer-abc123",
  "creator_id": "contributor-xyz",
  "cc_share": 0.15,
  "status": "active",
  "registered_at": "2026-04-26T00:00:00Z"
}
```

### `GET /api/provider-versions/{id}/stats`

**Response 200**
```json
{
  "version_id": "pv-gltf-v2-789",
  "usage_count": 4821,
  "cc_earned": 96.42,
  "p95_latency_ms": 312,
  "first_used_at": "2026-04-26T01:00:00Z"
}
```

### `GET /api/provider-versions/{id}/competition`

**Response 200**
```json
{
  "base_provider_id": "renderer-abc123",
  "versions": [
    {"version_id": "pv-gltf-v1-001", "usage_count": 3200, "cc_earned": 64.0, "usage_share": 0.399},
    {"version_id": "pv-gltf-v2-789", "usage_count": 4821, "cc_earned": 96.42, "usage_share": 0.601}
  ]
}
```

### `GET /api/provider-versions/leaderboard`

Query params: `type` (renderer|hosting_node|generator), `window` (e.g. `7d`), `limit` (default 10)

**Response 200**
```json
{
  "window": "7d",
  "type": "renderer",
  "entries": [
    {"version_id": "pv-gltf-v2-789", "creator_id": "contributor-xyz", "cc_earned": 96.42, "usage_count": 4821, "rank": 1}
  ]
}
```

## Data Model

```yaml
ProviderVersion:
  version_id: string (pk)
  provider_type: enum(renderer, hosting_node, generator)
  base_provider_id: string (nullable — null for first-gen providers)
  creator_id: string (FK → contributors)
  component_url: string (nullable — for renderer/generator)
  endpoint_url: string (nullable — for hosting nodes)
  cc_share: float (0.0–1.0, frozen after first_used_at is set)
  status: enum(active, deprecated)
  registered_at: datetime
  first_used_at: datetime (nullable)
  metadata: jsonb

VersionStats:
  version_id: string (FK → ProviderVersion)
  usage_count: int
  cc_earned: float
  p95_latency_ms: int (nullable)
  window_start: datetime
  window_end: datetime

GenerationEvent:
  event_id: string (pk)
  generator_version_id: string (FK → ProviderVersion)
  asset_id: string (FK → assets — the generated asset)
  generated_at: datetime
```

## Files

### New files
- `api/app/routers/provider_versions.py` — unified registry CRUD: register, list, stats, competition, leaderboard
- `api/app/models/provider_version.py` — `ProviderVersion`, `ProviderType`, `VersionStats`
- `api/app/services/provider_competition_service.py` — `select_provider_version()`, `record_usage_event()`, `compute_usage_share()`, leaderboard query
- `api/app/routers/generators.py` — generator CRUD + version listing
- `api/app/models/generator.py` — `Generator`, `GeneratorVersion`, `GenerationEvent`
- `api/app/services/generation_attribution_service.py` — `attribute_generation_cc()`, `record_generation_event()`
- `api/app/routers/hosting_nodes.py` — node registration + per-request recording
- `api/app/models/hosting_node.py` — `HostingNode`, `NodeRequest`, `NodePerformanceStats`
- `api/app/services/node_attribution_service.py` — `attribute_node_cc()`, `select_fastest_node()`
- `api/tests/test_improvement_as_contribution.py` — all acceptance tests

### Modified files
- `api/app/routers/renderers.py` — add `get_renderer_versions()` endpoint; accept `provider_version_id` on render events
- `api/app/models/renderer.py` — add `RendererVersion` linking to `ProviderVersion`
- `api/app/services/render_attribution_service.py` — update `attribute_render_cc()` to route attribution by `provider_version_id`
- `api/app/main.py` — include new routers (`provider_versions`, `generators`, `hosting_nodes`)

## Verification Scenarios

### Scenario 1 — Register a new renderer version and verify it earns CC

```bash
# Register improved GLTF renderer
curl -s -X POST https://api.coherencycoin.com/api/provider-versions/register \
  -H "Content-Type: application/json" \
  -d '{"provider_type":"renderer","base_provider_id":"renderer-gltf-v1","creator_id":"alice","component_url":"https://cdn.example.com/gltf-v2.js","cc_share":0.15}' \
  | jq '.version_id'
# Expected: "pv-gltf-v2-<id>"

# Log a render event using the new version
curl -s -X POST https://api.coherencycoin.com/api/render-events \
  -H "Content-Type: application/json" \
  -d '{"asset_id":"asset-001","renderer_id":"renderer-gltf-v1","provider_version_id":"pv-gltf-v2-<id>"}' \
  | jq '.cc_attributed'
# Expected: object with renderer_version_creator credited at 0.15 share
```

### Scenario 2 — Competition: both original and improved version earn in parallel

```bash
# Send 3 events to v1, 7 events to v2
# ... (register + log events for each version)

# Check competition split
curl -s https://api.coherencycoin.com/api/provider-versions/pv-gltf-v1-<id>/competition \
  | jq '.versions | map({version_id, usage_share})'
# Expected: two entries, usage_share ≈ [0.3, 0.7], summing to 1.0
```

### Scenario 3 — Hosting node registers faster version and earns per request

```bash
# Register fast hosting node
curl -s -X POST https://api.coherencycoin.com/api/provider-versions/register \
  -H "Content-Type: application/json" \
  -d '{"provider_type":"hosting_node","base_provider_id":"node-us-east-1","creator_id":"bob","endpoint_url":"https://fast-node.example.com","cc_share":0.05}' \
  | jq '.version_id'
# Expected: "pv-node-fast-<id>"

# Record a hosting request served by this node
curl -s -X POST https://api.coherencycoin.com/api/hosting-events \
  -H "Content-Type: application/json" \
  -d '{"asset_id":"asset-001","provider_version_id":"pv-node-fast-<id>","latency_ms":45}' \
  | jq '.cc_attributed.hosting_node'
# Expected: positive float (bob earns CC)
```

### Scenario 4 — Generator version earns on downstream reads

```bash
# Register improved image generator
curl -s -X POST https://api.coherencycoin.com/api/provider-versions/register \
  -H "Content-Type: application/json" \
  -d '{"provider_type":"generator","creator_id":"carol","endpoint_url":"https://genv2.example.com","cc_share":0.10}' \
  | jq '.version_id'
# Expected: "pv-gen-v2-<id>"

# Record a generation event
curl -s -X POST https://api.coherencycoin.com/api/generation-events \
  -H "Content-Type: application/json" \
  -d '{"generator_version_id":"pv-gen-v2-<id>","asset_id":"asset-generated-001"}' \
  | jq '.event_id'
# Expected: "gev-<id>"

# Simulate a read of the generated asset; verify generation attribution
curl -s https://api.coherencycoin.com/api/assets/asset-generated-001/analytics \
  | jq '.cc_breakdown.generator_version_creator'
# Expected: > 0 after read events are logged
```

### Scenario 5 — Leaderboard reflects CC earned in time window

```bash
curl -s "https://api.coherencycoin.com/api/provider-versions/leaderboard?type=renderer&window=7d&limit=5" \
  | jq '.entries[0] | {version_id, cc_earned, rank}'
# Expected: {"version_id": "pv-...", "cc_earned": <positive float>, "rank": 1}
# cc_earned for rank 1 >= cc_earned for rank 2 (sorted descending)
```

## Out of Scope

- Automatic routing/load-balancing between provider versions (manual `provider_version_id` selection only for v1)
- Provider version deletion or merging
- Dispute resolution when a version's CC share is contested
- Slashing or penalizing underperforming versions
- Multi-version A/B testing infrastructure (beyond what usage-share reporting provides)

## Risks and Assumptions

- **Risk**: Spam registrations flood the provider version registry. Mitigation: require `creator_id` with a minimum CC balance to register; rate-limit registrations per contributor.
- **Risk**: `cc_share` freeze after first use could lock in a bad value. Mitigation: allow creator to set `status=deprecated` and register a corrected version; the original keeps earning on existing events.
- **Assumption**: Existing render-events API accepts new optional `provider_version_id` without breaking current clients that omit it.
- **Assumption**: The CC pool for each event type (render, host, generate) is already settled — this spec only changes how the provider's share is routed within that pool.
- **Risk**: p95 latency stats require a time-series store or percentile approximation. Mitigation: store raw event latencies in `generation_events`/`node_requests` tables; compute p95 on query with `limit=10000` recent events.
