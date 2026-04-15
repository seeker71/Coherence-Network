---
idea_id: value-attribution
status: draft
priority: high
source:
  - file: api/app/routers/assets.py
    symbols: [register_asset(), get_asset(), get_asset_content(), get_asset_analytics()]
  - file: api/app/routers/renderers.py
    symbols: [register_renderer(), list_renderers(), get_renderer_for_mime()]
  - file: api/app/routers/render_events.py
    symbols: [log_render_event()]
  - file: api/app/models/asset.py
    symbols: [AssetRegistration, AssetFull, AssetType]
  - file: api/app/models/renderer.py
    symbols: [Renderer, RendererCreate, RenderEvent, RenderCCSplit]
  - file: api/app/services/render_attribution_service.py
    symbols: [attribute_render_cc()]
  - file: web/app/assets/[asset_id]/page.tsx
    symbols: [AssetDetailPage, RendererComponent dynamic loading]
  - file: web/lib/renderer-sdk.ts
    symbols: [RendererProps, registerRenderer()]
requirements:
  - "Any MIME type can be registered as an asset via POST /api/assets/register"
  - "Renderers are pluggable — register via POST /api/renderers/register"
  - "Renderers are dynamically loaded in the browser from component_url"
  - "Renderer creators earn CC on every render alongside asset creators"
  - "CC split defaults to 80% asset creator / 15% renderer creator / 5% host node"
  - "CC split is configurable per renderer and overridable by asset creator"
  - "Built-in renderers ship for text/markdown, image/jpeg, image/png, text/html, application/pdf"
  - "Renderer SDK (web/lib/renderer-sdk.ts) exposes RendererProps interface and registerRenderer()"
  - "Renderer bundles sandboxed — no access to parent DOM or cookies"
  - "Maximum renderer bundle size 500KB for initial load"
  - "Renderer must call onReady within 5 seconds or timeout"
  - "POST /api/render-events logs a render and triggers CC attribution to both creators"
  - "GET /api/assets/{id}/analytics returns read counts, CC earned, top concept tags"
done_when:
  - "A GLTF model can be uploaded, rendered via a community renderer, and earns CC for both asset creator and renderer author"
  - "Custom renderer can be registered via API and loaded dynamically in the browser"
  - "Render events track both asset and renderer attribution"
  - "CC split is applied correctly (80/15/5 default, configurable override)"
  - "Built-in renderers work for markdown, images, PDF, and HTML"
  - "Renderer SDK type definitions exported from web/lib/renderer-sdk.ts"
  - "All tests pass"
test: "python3 -m pytest api/tests/test_asset_renderer.py -x -v"
constraints:
  - "Changes scoped to listed files only"
  - "Existing assets-api behavior (POST /api/assets, GET /api/assets/{id}, GET /api/assets) must not break"
  - "Renderer bundles sandboxed — loaded in iframe or shadow DOM, no access to parent DOM or cookies"
  - "Maximum bundle size 500KB for initial load"
  - "Renderer must call onReady within 5 seconds or platform shows timeout fallback"
  - "No schema migrations without explicit approval"
---

> **Parent idea**: [value-attribution](../ideas/value-attribution.md)
> **Source**: [`api/app/routers/assets.py`](../api/app/routers/assets.py) | [`api/app/models/asset.py`](../api/app/models/asset.py) | [`api/app/routers/renderers.py`](../api/app/routers/renderers.py) (new) | [`web/app/assets/[asset_id]/page.tsx`](../web/app/assets/%5Basset_id%5D/page.tsx)

# Spec: Pluggable Asset Renderers

## Purpose

The platform supports ANY digital asset format. A contributor uploads content in any format -- GLTF, PDF, MIDI, KML, CSV, custom binary -- and registers a MIME type. The platform does not need to understand the format. It only needs: (1) a renderer that can display it in the browser, and (2) an asset node in the graph with metadata.

Renderers are themselves contributed assets. Someone who builds a "GLTF 3D viewer" component registers it as a renderer for `model/gltf+json`. When that renderer displays any GLTF asset, BOTH the renderer creator AND the asset creator earn CC from the view. This creates a self-expanding ecosystem: every new format attracts renderer builders, and every new renderer makes existing content more accessible.

## Requirements

- [ ] **R1**: Any MIME type can be registered as an asset via `POST /api/assets/register`. The registration payload includes the MIME type, content hash (SHA-256), optional Arweave/IPFS storage IDs, concept tags with weights, creator ID, creation cost in CC, and format-specific metadata.
- [ ] **R2**: Renderers are registered via `POST /api/renderers/register`. Each renderer declares which MIME types it handles, provides a component URL (JS bundle or npm package), and has a version. Renderers are stored as graph nodes of type `renderer`.
- [ ] **R3**: The frontend dynamically loads renderers. Given an asset, the platform resolves the correct renderer via `GET /api/renderers/for/{mime_type}` and imports the component at runtime. If no renderer is found, a generic download fallback is shown.
- [ ] **R4**: Every render triggers a CC attribution event. `POST /api/render-events` logs the asset ID, renderer ID, reader ID, timestamp, and engagement duration. The render attribution service splits the CC pool between asset creator (80%), renderer creator (15%), and host node (5%) by default.
- [ ] **R5**: The CC split is configurable. A renderer can declare a custom split at registration. An asset creator can override the split for their specific asset. The platform enforces that all shares sum to 100%.
- [ ] **R6**: Built-in renderers ship with the platform for `text/markdown`, `image/jpeg`, `image/png`, `text/html`, and `application/pdf`. These have no external component URL -- they are internal React components.
- [ ] **R7**: A Renderer SDK (`web/lib/renderer-sdk.ts`) defines the `RendererProps` interface and `registerRenderer()` function so community developers can build compatible renderers.
- [ ] **R8**: Renderer bundles are sandboxed. They run in an iframe or shadow DOM with no access to the parent page's DOM, cookies, or authentication tokens. Communication happens only through the `RendererProps` callback interface.
- [ ] **R9**: Maximum renderer bundle size is 500KB for the initial load. The platform rejects registration of bundles exceeding this limit.
- [ ] **R10**: Renderers must call `onReady()` within 5 seconds of mount. If the timeout elapses, the platform shows a fallback "Content available for download" view.
- [ ] **R11**: `GET /api/assets/{id}/analytics` returns aggregated render counts, total CC earned (broken down by asset creator vs. renderer creator shares), and the top concept tags associated with the asset.

## Data Model

### Asset Registration (extends existing Asset)

```yaml
AssetRegistration:
  type: str                     # MIME type or custom type identifier
  name: str
  description: str
  content_hash: str             # SHA-256 of raw content
  arweave_tx: str | null        # permanent storage transaction ID
  ipfs_cid: str | null          # content-addressed retrieval CID
  concept_tags:                 # links to Living Collective concepts
    - concept_id: str
      weight: float             # 0.0-1.0
  creator_id: str
  creation_cost_cc: decimal
  metadata: dict                # format-specific (dimensions, duration, codec, etc.)
```

The existing `AssetType` enum (CODE, MODEL, CONTENT, DATA) is kept for backward compatibility. The new `type` field holds the MIME type for renderer resolution. Existing assets without a MIME type default to a built-in renderer based on their `AssetType`.

### Renderer

```yaml
Renderer:
  id: str                       # e.g. "gltf-viewer-v1"
  name: str
  mime_types: [str]             # what formats this renderer handles
  creator_id: str
  component_url: str            # URL to the renderer JS bundle (or npm package)
  creation_cost_cc: decimal
  version: str
  cc_split:                     # optional custom split
    asset_creator: float        # default 0.80
    renderer_creator: float     # default 0.15
    host_node: float            # default 0.05
  max_bundle_bytes: int         # enforced <= 512000 (500KB)
  created_at: datetime
```

### Render Event

```yaml
RenderEvent:
  id: uuid
  asset_id: str
  renderer_id: str
  reader_id: str
  timestamp: datetime
  duration_ms: int
  cc_pool: decimal              # base_rate * engagement_multiplier
  cc_asset_creator: decimal     # cc_pool * asset_creator_share
  cc_renderer_creator: decimal  # cc_pool * renderer_creator_share
  cc_host_node: decimal         # cc_pool * host_node_share
```

### CC Attribution per Render

```
render_cc_pool = base_rate * reader_engagement_multiplier

Default split:
  asset_creator:    80% of pool   (they made the content)
  renderer_creator: 15% of pool   (they made it viewable)
  host_node:         5% of pool   (they served it)

Override precedence:
  1. Asset creator override (if set)
  2. Renderer default split (if set at registration)
  3. Platform default (80/15/5)

Constraint: all shares must sum to 1.0 (100%).
```

## API Contract

### `POST /api/assets/register`

Register any digital asset. Extends the existing `POST /api/assets` endpoint.

**Request**
```json
{
  "type": "model/gltf+json",
  "name": "Forest Scene",
  "description": "A detailed 3D forest environment",
  "content_hash": "sha256:abc123...",
  "arweave_tx": "tx_abc123",
  "ipfs_cid": "QmXyz...",
  "concept_tags": [
    {"concept_id": "lc-030", "weight": 0.8},
    {"concept_id": "lc-015", "weight": 0.4}
  ],
  "creator_id": "contributor:alice",
  "creation_cost_cc": "5.00",
  "metadata": {
    "vertices": 50000,
    "textures": 12,
    "file_size_bytes": 2400000
  }
}
```

**Response 201**
```json
{
  "id": "asset:uuid-here",
  "type": "model/gltf+json",
  "name": "Forest Scene",
  "description": "A detailed 3D forest environment",
  "content_hash": "sha256:abc123...",
  "arweave_tx": "tx_abc123",
  "ipfs_cid": "QmXyz...",
  "concept_tags": [
    {"concept_id": "lc-030", "weight": 0.8}
  ],
  "creator_id": "contributor:alice",
  "creation_cost_cc": "5.00",
  "metadata": {"vertices": 50000, "textures": 12, "file_size_bytes": 2400000},
  "created_at": "2026-04-14T12:00:00Z"
}
```

### `GET /api/assets/{id}`

Returns asset metadata including content URLs. Same as existing endpoint, extended with new fields.

### `GET /api/assets/{id}/content`

Proxies raw content from Arweave or IPFS. Returns the binary content with the correct `Content-Type` header matching the asset's MIME type.

### `POST /api/renderers/register`

**Request**
```json
{
  "id": "gltf-viewer-v1",
  "name": "GLTF 3D Viewer",
  "mime_types": ["model/gltf+json", "model/gltf-binary"],
  "creator_id": "contributor:bob",
  "component_url": "https://cdn.coherencycoin.com/renderers/gltf-viewer-v1.js",
  "creation_cost_cc": "12.00",
  "version": "1.0.0",
  "cc_split": {
    "asset_creator": 0.75,
    "renderer_creator": 0.20,
    "host_node": 0.05
  }
}
```

**Response 201**
```json
{
  "id": "gltf-viewer-v1",
  "name": "GLTF 3D Viewer",
  "mime_types": ["model/gltf+json", "model/gltf-binary"],
  "creator_id": "contributor:bob",
  "component_url": "https://cdn.coherencycoin.com/renderers/gltf-viewer-v1.js",
  "creation_cost_cc": "12.00",
  "version": "1.0.0",
  "cc_split": {"asset_creator": 0.75, "renderer_creator": 0.20, "host_node": 0.05},
  "created_at": "2026-04-14T12:00:00Z"
}
```

**Validation**: Returns 422 if `cc_split` values do not sum to 1.0 or if `component_url` bundle exceeds 500KB.

### `GET /api/renderers`

List all registered renderers with pagination.

**Response 200**
```json
{
  "items": [
    {"id": "gltf-viewer-v1", "name": "GLTF 3D Viewer", "mime_types": ["model/gltf+json"], "version": "1.0.0"}
  ],
  "total": 1,
  "limit": 100,
  "offset": 0
}
```

### `GET /api/renderers/for/{mime_type}`

Find the best renderer for a given MIME type. Returns the highest-version renderer registered for that type. Returns 404 if no renderer is registered for the type.

**Response 200**
```json
{
  "id": "gltf-viewer-v1",
  "name": "GLTF 3D Viewer",
  "component_url": "https://cdn.coherencycoin.com/renderers/gltf-viewer-v1.js",
  "version": "1.0.0"
}
```

### `POST /api/render-events`

Log a render event. Called by the frontend when a user views an asset.

**Request**
```json
{
  "asset_id": "asset:uuid-here",
  "renderer_id": "gltf-viewer-v1",
  "reader_id": "contributor:charlie",
  "duration_ms": 15000
}
```

**Response 201**
```json
{
  "id": "event:uuid-here",
  "asset_id": "asset:uuid-here",
  "renderer_id": "gltf-viewer-v1",
  "reader_id": "contributor:charlie",
  "timestamp": "2026-04-14T12:05:00Z",
  "duration_ms": 15000,
  "cc_pool": "0.15",
  "cc_asset_creator": "0.12",
  "cc_renderer_creator": "0.0225",
  "cc_host_node": "0.0075"
}
```

### `GET /api/assets/{id}/analytics`

**Response 200**
```json
{
  "asset_id": "asset:uuid-here",
  "total_renders": 1420,
  "total_cc_earned": "213.00",
  "cc_to_asset_creator": "170.40",
  "cc_to_renderer_creators": "31.95",
  "cc_to_host_nodes": "10.65",
  "top_concepts": [
    {"concept_id": "lc-030", "weight": 0.8, "name": "Land and Place"}
  ],
  "unique_readers": 890,
  "avg_duration_ms": 22000
}
```

## Web Architecture

The Next.js frontend loads renderers dynamically.

```tsx
// web/app/assets/[assetId]/page.tsx
const asset = await fetchAsset(assetId);
const renderer = await fetchRenderer(asset.type);

// Dynamic import of the renderer component
const RendererComponent = dynamic(() => import(renderer.component_url));

return (
  <AssetContainer asset={asset} onRender={trackRenderEvent}>
    <RendererComponent
      contentUrl={asset.content_url}
      metadata={asset.metadata}
      onReady={handleReady}
      onEngagement={handleEngagement}
    />
  </AssetContainer>
);
```

Built-in renderers (shipped with the platform, no external URL):
- `text/markdown` -- story content renderer (already exists: `StoryContent.tsx`)
- `image/jpeg`, `image/png` -- image viewer (already exists)
- `text/html` -- article renderer
- `application/pdf` -- PDF viewer

Community-contributed renderers (loaded dynamically from `component_url`):
- `model/gltf+json` -- 3D model viewer (Three.js)
- `audio/midi` -- sheet music / playback
- `application/vnd.kml+xml` -- map/land survey viewer
- `text/csv` -- data table with charts
- Any future format anyone invents

## Renderer SDK

A minimal SDK so anyone can build a compatible renderer.

```typescript
// web/lib/renderer-sdk.ts — exported as @coherence/renderer-sdk

export interface RendererProps {
  contentUrl: string;                    // Arweave/IPFS URL to raw content
  metadata: Record<string, any>;         // format-specific metadata from registration
  onReady: () => void;                   // call when content is visible (must be within 5s)
  onEngagement: (seconds: number) => void; // periodic engagement signal for CC attribution
}

export interface RendererConfig {
  id: string;
  mimeTypes: string[];
  component: React.FC<RendererProps>;
}

export function registerRenderer(config: RendererConfig): void;
```

The SDK is intentionally small. Renderers are plain React components that receive content and call back with lifecycle signals. The platform handles all CC attribution, storage resolution, and sandboxing.

## Files to Create/Modify

- `api/app/routers/assets.py` -- extend with `POST /api/assets/register`, `GET /api/assets/{id}/content`, `GET /api/assets/{id}/analytics`
- `api/app/routers/renderers.py` (new) -- renderer registration and lookup
- `api/app/routers/render_events.py` (new) -- render event logging
- `api/app/models/asset.py` -- extend with `AssetRegistration`, MIME type field, concept tags, storage IDs
- `api/app/models/renderer.py` (new) -- `Renderer`, `RendererCreate`, `RenderEvent`, `RenderCCSplit`
- `api/app/services/render_attribution_service.py` (new) -- CC split calculation and attribution
- `web/app/assets/[asset_id]/page.tsx` -- dynamic renderer loading, sandbox container, timeout handling
- `web/lib/renderer-sdk.ts` (new) -- RendererProps interface and registerRenderer()
- `api/tests/test_asset_renderer.py` (new) -- integration tests

## Acceptance Tests

- `api/tests/test_asset_renderer.py::test_register_asset_with_mime_type` -- register asset with custom MIME type, verify stored
- `api/tests/test_asset_renderer.py::test_register_renderer` -- register renderer for a type, verify discoverable via `/api/renderers/for/{mime_type}`
- `api/tests/test_asset_renderer.py::test_render_event_attribution` -- render asset, verify both asset creator and renderer creator are attributed CC
- `api/tests/test_asset_renderer.py::test_cc_split_default` -- verify 80/15/5 default split
- `api/tests/test_asset_renderer.py::test_cc_split_custom` -- verify custom split from renderer registration
- `api/tests/test_asset_renderer.py::test_cc_split_override` -- verify asset creator can override split
- `api/tests/test_asset_renderer.py::test_cc_split_validation` -- verify 422 when shares do not sum to 1.0
- `api/tests/test_asset_renderer.py::test_renderer_not_found_fallback` -- request renderer for unknown MIME type, verify 404
- `api/tests/test_asset_renderer.py::test_asset_analytics` -- render several times, verify analytics aggregation
- `api/tests/test_asset_renderer.py::test_existing_assets_api_unchanged` -- existing POST/GET /api/assets still works

## Verification

```bash
python3 -m pytest api/tests/test_asset_renderer.py -x -v
```

## Out of Scope

- Content upload and storage (Arweave/IPFS integration is a separate spec)
- Renderer marketplace UI (browsing/rating renderers)
- Renderer versioning and migration (auto-upgrading assets to newer renderer versions)
- Payment settlement (CC attribution is recorded, actual payout is handled by the distribution engine)
- Renderer code review or security audit process

## Risks and Assumptions

- **Risk**: Dynamically loaded third-party JS in sandboxed iframes may have performance overhead. Mitigation: enforce 500KB bundle limit and 5s timeout; built-in renderers bypass the sandbox.
- **Risk**: CC split disputes between asset creators and renderer creators. Mitigation: splits are transparent, recorded on every render event, and overridable by asset creators who own the content.
- **Assumption**: The graph service can store renderer nodes with MIME type indexing for efficient lookup by type. If not, a secondary index or lookup table may be needed.
- **Assumption**: Arweave/IPFS content retrieval is handled by a separate storage layer. This spec only records the `arweave_tx` and `ipfs_cid` references; it does not implement the retrieval proxy beyond the `GET /api/assets/{id}/content` endpoint contract.
