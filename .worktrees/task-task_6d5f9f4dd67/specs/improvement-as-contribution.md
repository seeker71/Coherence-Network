---
idea_id: improvement-as-contribution
status: draft
source:
  - file: api/app/models/renderer.py
    symbols: [Renderer, RendererCreate]
  - file: api/app/routers/renderers.py
    symbols: [register_renderer(), fork_renderer()]
  - file: api/app/routers/render_events.py
    symbols: [log_render_event()]
  - file: api/app/services/render_attribution_service.py
    symbols: [attribute_render_cc()]
  - file: api/app/routers/improvements.py
    symbols: [list_provider_versions(), get_version_earnings()]
  - file: api/app/models/improvement.py
    symbols: [ProviderVersion, ProviderVersionComparison]
  - file: api/app/services/improvement_attribution_service.py
    symbols: [get_version_comparison(), record_usage_event()]
  - file: api/tests/test_improvement_attribution.py
    symbols: [test suite]
requirements:
  - "POST /api/renderers/{id}/fork — register a new renderer version with parent_renderer_id link"
  - "Renderer model gains parent_renderer_id (Optional[str]) and version (str, default '1.0.0') fields"
  - "POST /api/render-events accepts renderer_id pointing to any version; CC flows to that version's owner"
  - "GET /api/improvements/renderers/{id}/versions — list all versions of a renderer with render_count and cc_earned"
  - "GET /api/improvements/renderers/{id}/compare — return ProviderVersionComparison: versions ranked by render_count"
  - "Forking does not deactivate the parent; both versions earn independently"
  - "Host node improvements: POST /api/improvements/hosting-nodes — register a node version with parent_node_id; per-request CC weighted by requests_served"
  - "Generator improvements: POST /api/improvements/generators — register a generator version with parent_generator_id"
  - "GET /api/improvements/{provider_type}/{id}/compare works for renderer, hosting-node, and generator provider types"
  - "All improvement registry records include contributor_id, registered_at (ISO 8601 UTC), and description"
done_when:
  - "POST /api/renderers/{id}/fork returns 201 with child renderer having parent_renderer_id set"
  - "Two render events against different versions of same renderer produce CC credited to each version's owner independently"
  - "GET /api/improvements/renderers/{id}/versions returns both parent and fork with accurate render_count"
  - "GET /api/improvements/renderers/{id}/compare returns versions sorted descending by render_count"
  - "POST /api/improvements/hosting-nodes returns 201 with parent_node_id set"
  - "all tests pass: cd api && python -m pytest tests/test_improvement_attribution.py -q"
test: "cd api && python -m pytest tests/test_improvement_attribution.py -q"
constraints:
  - "Forking never deactivates, deprecates, or modifies the parent provider"
  - "CC split percentages from asset-renderer-plugin spec (80/15/5) remain unchanged"
  - "No schema migrations — use in-process registry matching existing renderer storage pattern"
  - "Changes scoped to listed files only; do not modify distribution_engine or contributions router"
  - "Provider types are an open enum: renderer, hosting-node, generator — add new types without code changes"
---

# Spec: Improvement as Contribution

## Purpose

Infrastructure improvements are invisible without a registration mechanism. This spec makes every
improvement to a renderer, hosting node, or generator a first-class contribution: fork the provider,
register the new version, and let usage decide which version earns more CC. Both the original and
the improvement coexist permanently. No committee picks a winner — the render count and CC earned
are publicly queryable, so the market decides through actual usage.

## Requirements

- [ ] **R1 — Renderer fork endpoint**: `POST /api/renderers/{id}/fork` creates a new `Renderer` record
  with `parent_renderer_id = id` and all other fields from the fork body. Returns 201 with the new
  renderer. Returns 404 if the parent does not exist. Returns 409 if the submitted `id` conflicts
  with an existing renderer.

- [ ] **R2 — Renderer model versioning fields**: `RendererCreate` and `Renderer` gain two new optional
  fields: `parent_renderer_id: Optional[str] = None` and `version: str = "1.0.0"`. Both fields are
  optional to preserve backward compatibility with existing renderer registrations.

- [ ] **R3 — Version-aware render event CC**: `POST /api/render-events` already accepts `renderer_id`.
  No change to the contract — but `attribute_render_cc()` must look up whichever version was
  specified and credit CC to that version's `creator_id`. The parent and child versions earn
  independently; a render against the fork does not credit the parent.

- [ ] **R4 — Version listing**: `GET /api/improvements/renderers/{id}/versions` returns all renderers
  where `id == renderer.id OR id == renderer.parent_renderer_id` (i.e., the version family). Each
  entry includes `render_count` (count of render events with this `renderer_id`) and
  `cc_earned` (sum of CC attributed to this renderer_id).

- [ ] **R5 — Version comparison**: `GET /api/improvements/renderers/{id}/compare` returns a
  `ProviderVersionComparison` with `versions` sorted descending by `render_count`. The leading
  version is identified as `winning_version_id`.

- [ ] **R6 — Hosting node improvements**: `POST /api/improvements/hosting-nodes` registers a new
  hosting node version with `parent_node_id: Optional[str]`, `contributor_id`, `description`, and
  `registered_at`. Hosting node CC attribution (5% host share) accumulates per node version based
  on `requests_served` counter, incremented by `record_usage_event()`.

- [ ] **R7 — Generator improvements**: `POST /api/improvements/generators` registers a generator
  version with `parent_generator_id: Optional[str]`, `contributor_id`, `description`. Generator
  versions earn CC through asset reads when an asset records which generator produced it
  (`generator_version_id` field on asset). Attribution is via the existing render event flow.

- [ ] **R8 — Unified compare endpoint**: `GET /api/improvements/{provider_type}/{id}/compare` works
  for `provider_type` in `{renderer, hosting-node, generator}`. All three return
  `ProviderVersionComparison` with `versions`, `winning_version_id`, and `total_cc_in_family`.

- [ ] **R9 — Contributor linkage**: Every improvement record (fork or new registration) stores
  `contributor_id`. The existing `GET /api/contributors/{contributor_id}/contributions` endpoint
  must return improvement registrations as contribution records with `type = "improvement"`.

- [ ] **R10 — Idempotency**: Re-registering an identical fork (same `id`) returns 409. Registering
  a fork with a new `id` against the same parent is always allowed — multiple forks of the same
  parent are expected and encouraged.

## API Contract

### `POST /api/renderers/{id}/fork`

**Request body**
```json
{
  "id": "gltf-renderer-v2",
  "name": "GLTF Renderer v2 (faster geometry pass)",
  "version": "2.0.0",
  "mime_types": ["model/gltf+json", "model/gltf-binary"],
  "component_url": "https://cdn.example.com/gltf-v2.js",
  "creator_id": "contributor-abc",
  "description": "Replaces brute-force vertex iteration with BVH. ~40% faster on complex scenes."
}
```

**Response 201**
```json
{
  "id": "gltf-renderer-v2",
  "parent_renderer_id": "gltf-renderer-v1",
  "version": "2.0.0",
  "name": "GLTF Renderer v2 (faster geometry pass)",
  "mime_types": ["model/gltf+json", "model/gltf-binary"],
  "component_url": "https://cdn.example.com/gltf-v2.js",
  "creator_id": "contributor-abc",
  "cc_split": {"asset_creator": 0.80, "renderer_creator": 0.15, "host_node": 0.05},
  "registered_at": "2026-04-26T00:00:00Z"
}
```

**Response 404** — parent renderer not found
**Response 409** — `id` already registered

---

### `GET /api/improvements/renderers/{id}/versions`

**Response 200**
```json
{
  "family_root_id": "gltf-renderer-v1",
  "versions": [
    {
      "id": "gltf-renderer-v1",
      "version": "1.0.0",
      "parent_renderer_id": null,
      "render_count": 1200,
      "cc_earned": 48.00,
      "contributor_id": "contributor-xyz"
    },
    {
      "id": "gltf-renderer-v2",
      "version": "2.0.0",
      "parent_renderer_id": "gltf-renderer-v1",
      "render_count": 340,
      "cc_earned": 13.60,
      "contributor_id": "contributor-abc"
    }
  ]
}
```

---

### `GET /api/improvements/renderers/{id}/compare`

**Response 200**
```json
{
  "provider_type": "renderer",
  "family_root_id": "gltf-renderer-v1",
  "winning_version_id": "gltf-renderer-v1",
  "total_cc_in_family": 61.60,
  "versions": [
    {"id": "gltf-renderer-v1", "render_count": 1200, "cc_earned": 48.00},
    {"id": "gltf-renderer-v2", "render_count": 340, "cc_earned": 13.60}
  ]
}
```

---

### `POST /api/improvements/hosting-nodes`

**Request body**
```json
{
  "id": "node-fast-sfo-01",
  "parent_node_id": "node-sfo-01",
  "contributor_id": "contributor-def",
  "description": "NVMe-backed node with 2x faster asset delivery"
}
```

**Response 201**
```json
{
  "id": "node-fast-sfo-01",
  "parent_node_id": "node-sfo-01",
  "contributor_id": "contributor-def",
  "description": "NVMe-backed node with 2x faster asset delivery",
  "requests_served": 0,
  "cc_earned": 0.0,
  "registered_at": "2026-04-26T00:00:00Z"
}
```

---

### `POST /api/improvements/generators`

**Request body**
```json
{
  "id": "sdxl-v2-turbo",
  "parent_generator_id": "sdxl-v1",
  "contributor_id": "contributor-ghi",
  "description": "SDXL Turbo — 4-step distilled model, same quality at 8x speed"
}
```

**Response 201**
```json
{
  "id": "sdxl-v2-turbo",
  "parent_generator_id": "sdxl-v1",
  "contributor_id": "contributor-ghi",
  "description": "SDXL Turbo — 4-step distilled model, same quality at 8x speed",
  "assets_generated": 0,
  "cc_earned": 0.0,
  "registered_at": "2026-04-26T00:00:00Z"
}
```

## Data Model

```yaml
Renderer (extended):
  id: str
  version: str           # default "1.0.0"
  parent_renderer_id: Optional[str]   # null for root versions
  name: str
  mime_types: List[str]
  component_url: str
  creator_id: str
  cc_split: RenderCCSplit
  registered_at: datetime

ProviderVersion:
  id: str
  provider_type: str     # "renderer" | "hosting-node" | "generator"
  parent_id: Optional[str]
  contributor_id: str
  description: str
  registered_at: datetime
  render_count: int      # for renderer
  requests_served: int   # for hosting-node
  assets_generated: int  # for generator
  cc_earned: float

ProviderVersionComparison:
  provider_type: str
  family_root_id: str
  winning_version_id: str
  total_cc_in_family: float
  versions: List[ProviderVersionSummary]

ProviderVersionSummary:
  id: str
  render_count: int
  cc_earned: float
```

## Files

- `api/app/models/renderer.py` — add `parent_renderer_id: Optional[str] = None` and `version: str = "1.0.0"` to `RendererCreate` and `Renderer`
- `api/app/routers/renderers.py` — add `fork_renderer()` handler for `POST /api/renderers/{id}/fork`
- `api/app/routers/render_events.py` — no contract change; verify CC goes to the exact `renderer_id` from the event, not to parent
- `api/app/services/render_attribution_service.py` — confirm `attribute_render_cc()` uses `renderer_id` from event directly (no parent lookup)
- `api/app/models/improvement.py` — **NEW**: `ProviderVersion`, `ProviderVersionComparison`, `ProviderVersionSummary`, `HostingNodeCreate`, `GeneratorCreate`
- `api/app/routers/improvements.py` — **NEW**: all `/api/improvements/...` endpoints
- `api/app/services/improvement_attribution_service.py` — **NEW**: `get_version_comparison()`, `record_usage_event()`, `get_version_listing()`
- `api/tests/test_improvement_attribution.py` — **NEW**: full test suite

## Acceptance Tests

- `api/tests/test_improvement_attribution.py::test_fork_renderer_returns_201_with_parent_id`
- `api/tests/test_improvement_attribution.py::test_fork_unknown_parent_returns_404`
- `api/tests/test_improvement_attribution.py::test_fork_duplicate_id_returns_409`
- `api/tests/test_improvement_attribution.py::test_parent_unchanged_after_fork`
- `api/tests/test_improvement_attribution.py::test_render_event_credits_fork_not_parent`
- `api/tests/test_improvement_attribution.py::test_render_event_credits_parent_independently`
- `api/tests/test_improvement_attribution.py::test_version_listing_shows_both_versions`
- `api/tests/test_improvement_attribution.py::test_compare_returns_versions_sorted_by_render_count`
- `api/tests/test_improvement_attribution.py::test_register_hosting_node_improvement`
- `api/tests/test_improvement_attribution.py::test_register_generator_improvement`
- `api/tests/test_improvement_attribution.py::test_compare_works_for_all_provider_types`

## Verification Scenarios

### Scenario 1 — Fork a renderer, verify parent unchanged

```bash
# Register parent renderer
curl -s -X POST https://api.coherencycoin.com/api/renderers/register \
  -H "Content-Type: application/json" \
  -d '{"id":"gltf-v1","name":"GLTF v1","mime_types":["model/gltf+json"],"component_url":"https://cdn.example.com/v1.js","creator_id":"alice"}' \
  | jq '.id'
# Expected: "gltf-v1"

# Fork it
curl -s -X POST https://api.coherencycoin.com/api/renderers/gltf-v1/fork \
  -H "Content-Type: application/json" \
  -d '{"id":"gltf-v2","name":"GLTF v2","version":"2.0.0","mime_types":["model/gltf+json"],"component_url":"https://cdn.example.com/v2.js","creator_id":"bob"}' \
  | jq '{id:.id, parent:.parent_renderer_id}'
# Expected: {"id":"gltf-v2","parent":"gltf-v1"}

# Verify parent still registered and unmodified
curl -s https://api.coherencycoin.com/api/renderers/gltf-v1 | jq '.parent_renderer_id'
# Expected: null
```

### Scenario 2 — Render events credit correct version owners

```bash
# Register an asset
ASSET_ID=$(curl -s -X POST https://api.coherencycoin.com/api/assets/register \
  -H "Content-Type: application/json" \
  -d '{"title":"Test Scene","mime_type":"model/gltf+json","creator_id":"alice","content_hash":"abc123"}' \
  | jq -r '.id')

# Render with parent (credits alice as renderer owner)
curl -s -X POST https://api.coherencycoin.com/api/render-events \
  -H "Content-Type: application/json" \
  -d "{\"asset_id\":\"$ASSET_ID\",\"renderer_id\":\"gltf-v1\",\"reader_id\":\"reader-1\",\"duration_ms\":120}" \
  | jq '.renderer_cc_earned'
# Expected: positive float > 0

# Render with fork (credits bob as renderer owner)
curl -s -X POST https://api.coherencycoin.com/api/render-events \
  -H "Content-Type: application/json" \
  -d "{\"asset_id\":\"$ASSET_ID\",\"renderer_id\":\"gltf-v2\",\"reader_id\":\"reader-2\",\"duration_ms\":75}" \
  | jq '.renderer_cc_earned'
# Expected: positive float > 0
```

### Scenario 3 — Version comparison shows usage standing

```bash
# Submit several renders against each version (run scenario 2 a few times with reader IDs)
# Then compare
curl -s https://api.coherencycoin.com/api/improvements/renderers/gltf-v1/compare \
  | jq '{winning:.winning_version_id, versions:[.versions[]|{id:.id,count:.render_count}]}'
# Expected: {"winning":"gltf-v1","versions":[{"id":"gltf-v1","count":3},{"id":"gltf-v2","count":1}]}
# (or reversed if fork surpassed parent in your test run — sorted descending by count)
```

### Scenario 4 — Register a hosting node improvement

```bash
curl -s -X POST https://api.coherencycoin.com/api/improvements/hosting-nodes \
  -H "Content-Type: application/json" \
  -d '{"id":"node-fast-01","parent_node_id":"node-01","contributor_id":"carol","description":"NVMe upgrade"}' \
  | jq '{id:.id, parent:.parent_node_id, cc:.cc_earned}'
# Expected: {"id":"node-fast-01","parent":"node-01","cc":0.0}
```

### Scenario 5 — Register a generator improvement

```bash
curl -s -X POST https://api.coherencycoin.com/api/improvements/generators \
  -H "Content-Type: application/json" \
  -d '{"id":"sdxl-turbo","parent_generator_id":"sdxl-v1","contributor_id":"dave","description":"4-step distilled"}' \
  | jq '{id:.id, parent:.parent_generator_id}'
# Expected: {"id":"sdxl-turbo","parent":"sdxl-v1"}

# And verify it shows in the compare endpoint for the generator family
curl -s "https://api.coherencycoin.com/api/improvements/generator/sdxl-v1/compare" \
  | jq '.versions | length'
# Expected: 2
```

## Out of Scope

- Automatic "best version" promotion or deprecation of slower versions
- Frontend UI for the improvement registry (web pages, dashboards)
- Consensus-based or governance-based version selection
- Generator version CC attribution via asset reads (the full generator → asset → read → CC chain is a follow-up spec; this spec registers the generator versions and tracks `assets_generated` count)
- Node performance measurement infrastructure (latency probes, benchmarks) — this spec only provides the registration and CC accounting layer
- Persistence in PostgreSQL or Neo4j — uses in-process registry matching existing renderer storage pattern

## Risks and Assumptions

- **Risk**: The in-process registry does not survive restarts. This matches the existing renderer registry behavior and is explicitly acceptable for the first slice. Graph-backed persistence is the follow-up (same note as `asset-renderer-plugin`).
- **Risk**: A contributor registers a fork with misleading metadata (claims quality improvements that don't exist). Mitigation: usage is the verdict — low-quality forks get low render counts and earn little CC. No committee intervention needed.
- **Assumption**: `attribute_render_cc()` already routes CC by `renderer_id` directly. If it ever fell back to a "best renderer for MIME type" lookup, this spec's independence guarantee would break. Verify this before implementation.
- **Assumption**: `contributor_id` in the fork body corresponds to an existing contributor record. If validation is required, add a `GET /api/contributors/{id}` existence check in the fork handler — same pattern as `POST /api/contributions`.
- **Risk**: The `compare` endpoint uses in-process render event counts. If render events are stored in a dict (current pattern), counts are correct within a single process but won't aggregate across multiple API workers. Acceptable for the first slice; noted for distributed deployment.
