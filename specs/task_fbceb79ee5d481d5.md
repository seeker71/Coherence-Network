# Spec 162 — Edge Navigation: Browse the Graph Through 46 Typed Relationships

**Spec ID**: task_fbceb79ee5d481d5
**Status**: draft
**Author**: product-manager agent
**Date**: 2026-03-28
**Priority**: High

---

## Summary

Every entity in the Coherence Network — idea, concept, contributor, spec, task, news item — can
be connected to any other entity via one of 46 typed relationships drawn from the Living Codex
ontology. These typed edges are the primary semantic layer of the graph: they define *how* things
connect, not just *that* they connect.

Today those edges exist in the database (schema is in place) but the system provides no dedicated
navigation surface. There is no `/api/edges/types` listing the canonical 46 types, no
`/api/entities/{id}/edges` endpoint that works uniformly across entity families, no `cc edges`
CLI command, and no interactive web graph view with edge-first navigation.

This spec defines the full vertical: API + CLI + Web, so that any user — human or agent — can
browse the graph by traversing typed relationships from any entity.

---

## Background: The 46 Living Codex Relationship Types

The Living Codex defines relationships across 7 semantic families:

### Family 1 — Ontological / Being
| slug | description |
|------|-------------|
| `resonates-with` | Shares deep harmonic alignment |
| `emerges-from` | Arises as a consequence or evolution |
| `transcends` | Supersedes or exceeds in abstraction |
| `instantiates` | Concretely expresses a general principle |
| `embodies` | Physically or symbolically manifests |
| `reflects` | Mirrors or echoes structurally |

### Family 2 — Process / Transformation
| slug | description |
|------|-------------|
| `transforms-into` | Changes state or form |
| `enables` | Provides conditions for |
| `blocks` | Inhibits or prevents |
| `catalyzes` | Accelerates transition |
| `stabilizes` | Prevents unwanted change |
| `amplifies` | Magnifies effect or signal |
| `dampens` | Reduces effect or signal |

### Family 3 — Knowledge / Structure
| slug | description |
|------|-------------|
| `implements` | Provides concrete realisation |
| `extends` | Adds to without replacing |
| `refines` | Narrows or improves precision |
| `generalises` | Broadens scope |
| `contradicts` | Is in direct logical opposition |
| `complements` | Adds without overlapping |
| `subsumes` | Fully contains semantically |

### Family 4 — Scale / Complexity
| slug | description |
|------|-------------|
| `fractal-scaling` | Repeats pattern at different scales |
| `composes-from` | Is assembled from sub-components |
| `decomposes-into` | Breaks into parts |
| `aggregates` | Combines many into one pattern |
| `specialises` | Is a specific case of |

### Family 5 — Temporal / Causal
| slug | description |
|------|-------------|
| `precedes` | Comes before in time or logic |
| `follows` | Comes after in time or logic |
| `co-occurs-with` | Happens simultaneously |
| `triggers` | Initiates as a direct cause |
| `resolves` | Brings to conclusion |
| `iterates` | Repeats in cycles |

### Family 6 — Tension / Resolution
| slug | description |
|------|-------------|
| `paradox-resolution` | Holds two opposing truths in synthesis |
| `polarity-of` | Is the opposing pole |
| `tension-with` | Is in productive creative tension |
| `bridges` | Connects two separate domains |
| `integrates` | Unifies previously separate things |

### Family 7 — Attribution / Operational
| slug | description |
|------|-------------|
| `contributes-to` | A person or agent adds work |
| `funded-by` | Financial or resource backing |
| `inspired-by` | Non-causal conceptual origin |
| `referenced-by` | Cited or mentioned |
| `challenges` | Poses a question or problem |
| `validates` | Provides evidence for |
| `invalidates` | Provides evidence against |
| `analogous-to` | Shares structural pattern without causation |
| `depends-on` | Requires in order to function |
| `precondition-of` | Must exist first |

**Total: 46 canonical types** (6+7+7+5+6+5+6). Implementations may also use untyped custom
relationship strings; validation should warn but not block on unknown types.

---

## Goal

Ship a complete, navigable edge layer so that:

1. **API** — dedicated `/api/edges` endpoints expose typed edges and the canonical type registry.
2. **CLI** — `cc edges <entity-id>` and `cc edge create` let agents and developers navigate/build the graph from the terminal.
3. **Web** — an interactive graph view on every entity page shows edges grouped by type, with click-to-navigate to connected entities. The entity detail page uses a tab layout: **Overview | Edges | History | Contributors**.

---

## Requirements

### API

- [ ] `GET /api/edges/types` — returns all 46 canonical relationship types with family, slug, description, and example use.
- [ ] `GET /api/edges` — list all edges; supports `?type=resonates-with&from_id=X&to_id=Y&limit=50&offset=0`.
- [ ] `GET /api/edges/{edge_id}` — get a single edge by ID.
- [ ] `POST /api/edges` — create an edge `{from_id, to_id, type, strength?, properties?, created_by?}`. Returns 201 on success, 409 if the triplet `(from_id, to_id, type)` already exists, 400 if `type` is unknown and `strict=true` is set.
- [ ] `DELETE /api/edges/{edge_id}` — remove an edge.
- [ ] `GET /api/entities/{id}/edges` — list all edges for any entity id regardless of its node type; supports `?type=resonates-with&direction=outgoing|incoming|both`.
- [ ] `GET /api/entities/{id}/neighbors` — returns the neighbouring node objects (not just edge records) reachable via 1 hop from `{id}`; supports `?type=<edge-type>&node_type=<node-type>`.
- [ ] All edge responses include the full node stubs for `from_id` and `to_id` (id, type, name) to avoid N+1 lookups on the frontend.
- [ ] `GET /api/edges/types` response is stable and cacheable (no DB query needed — it is derived from the canonical list in this spec).

### CLI

- [ ] `cc edges <entity-id>` — print all edges for an entity, grouped by relationship type, with direction indicators `→` / `←`.
- [ ] `cc edges <entity-id> --type resonates-with` — filter to a single type.
- [ ] `cc edges <entity-id> --direction outgoing|incoming|both` (default both).
- [ ] `cc edge create <from-id> <type> <to-id>` — create a typed edge; prints the created edge JSON.
- [ ] `cc edge create` validates that `<type>` is one of the 46 canonical slugs (warn, not error, for unknown types).
- [ ] `cc edge delete <edge-id>` — delete an edge by ID.
- [ ] `cc edge types` — print the full type registry as a formatted table.

### Web

- [ ] Every entity detail page (`/ideas/{id}`, `/concepts/{id}`, `/specs/{id}`, `/tasks/{id}`, `/contributors/{id}`) uses a **tab layout** with tabs: **Overview | Edges | History | Contributors**.
- [ ] The **Edges tab** renders an interactive graph canvas (force-directed or hierarchical) showing the selected entity at the centre with edges radiating outward.
- [ ] Each edge in the graph is colour-coded by relationship family (7 colours).
- [ ] Clicking an edge label shows a tooltip with the edge type description and strength.
- [ ] Clicking a connected node navigates to that entity's page.
- [ ] The Edges tab also shows a sidebar listing edges grouped by type with counts and a filter control.
- [ ] Edge creation UI: a "+ Add Edge" button opens a modal with `type` dropdown (grouped by family), entity search for the target, and optional strength slider (0.0–1.0).
- [ ] The graph view degrades gracefully when an entity has 0 edges (shows empty state, not blank canvas).

### Data / Validation

- [ ] The 46 canonical type slugs are defined in a single source-of-truth location: `api/app/config/edge_types.py`.
- [ ] All edge write operations validate `type` against the canonical list; unknown types are stored but flagged with `canonical: false` in the response.
- [ ] Edges are unique on `(from_id, to_id, type)` — the DB constraint already exists; the API must surface a 409 with a clear message.

---

## API Contract

### `GET /api/edges/types`

**Response 200**
```json
{
  "total": 46,
  "families": [
    {
      "name": "Ontological / Being",
      "slug": "ontological",
      "types": [
        {
          "slug": "resonates-with",
          "description": "Shares deep harmonic alignment",
          "canonical": true
        }
      ]
    }
  ]
}
```

### `GET /api/edges`

**Query params**: `type`, `from_id`, `to_id`, `limit` (default 50, max 500), `offset` (default 0)

**Response 200**
```json
{
  "items": [
    {
      "id": "edge_abc123",
      "from_id": "idea_001",
      "from_node": {"id": "idea_001", "type": "idea", "name": "Edge Navigation"},
      "to_id": "concept_resonance",
      "to_node": {"id": "concept_resonance", "type": "concept", "name": "Resonance"},
      "type": "resonates-with",
      "strength": 0.9,
      "canonical": true,
      "created_by": "agent_001",
      "created_at": "2026-03-28T10:00:00Z"
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

### `GET /api/edges/{edge_id}`

**Response 200**: single edge object (same shape as items above)
**Response 404**: `{"detail": "Edge 'edge_xyz' not found"}`

### `POST /api/edges`

**Request body**
```json
{
  "from_id": "idea_001",
  "to_id": "concept_resonance",
  "type": "resonates-with",
  "strength": 0.9,
  "created_by": "agent_001",
  "properties": {}
}
```

**Response 201**: created edge object
**Response 409**: `{"detail": "Edge already exists: idea_001 --[resonates-with]--> concept_resonance"}`
**Response 404**: `{"detail": "Node 'from_id' not found"}` if either endpoint is missing
**Response 400**: `{"detail": "Unknown edge type 'foo'. Use GET /api/edges/types for valid types.", "canonical": false}` when `strict=true` query param set

### `DELETE /api/edges/{edge_id}`

**Response 200**: `{"deleted": "edge_abc123"}`
**Response 404**: `{"detail": "Edge 'edge_xyz' not found"}`

### `GET /api/entities/{id}/edges`

**Query params**: `type`, `direction` (both|outgoing|incoming), `limit`, `offset`

**Response 200**: same shape as `GET /api/edges` but scoped to the entity
**Response 404**: `{"detail": "Entity '{id}' not found"}`

### `GET /api/entities/{id}/neighbors`

**Query params**: `type` (edge type filter), `node_type` (filter target node type), `limit`

**Response 200**
```json
{
  "entity_id": "idea_001",
  "neighbors": [
    {
      "node": {"id": "concept_resonance", "type": "concept", "name": "Resonance"},
      "via_edge": {"id": "edge_abc", "type": "resonates-with", "direction": "outgoing", "strength": 0.9}
    }
  ],
  "total": 1
}
```

---

## Data Model

The edge schema already exists (`graph_edges` table) with the required columns. This spec adds:

```python
# api/app/config/edge_types.py — canonical source of truth
EDGE_TYPE_FAMILIES = [
    {
        "name": "Ontological / Being",
        "slug": "ontological",
        "types": [
            {"slug": "resonates-with", "description": "..."},
            # ... 5 more
        ]
    },
    # ... 6 more families
]

# Flat set for O(1) validation
CANONICAL_EDGE_TYPES: set[str] = {t["slug"] for f in EDGE_TYPE_FAMILIES for t in f["types"]}
```

The `canonical` field in responses is a computed property — not stored in DB — derived by checking
`edge.type in CANONICAL_EDGE_TYPES`.

---

## Files Allowed

```yaml
goal: >
  Add /api/edges, /api/edges/types, /api/entities/{id}/edges, /api/entities/{id}/neighbors
  endpoints; add cc edges CLI commands; add Edges tab to entity detail pages.

files_allowed:
  - api/app/config/edge_types.py          # NEW — canonical 46 types
  - api/app/routers/edges.py              # NEW — dedicated edges router
  - api/app/routers/graph.py              # MODIFY — remove duplicated edge endpoints (or keep for compat)
  - api/app/main.py                       # MODIFY — register new router
  - api/app/services/graph_service.py     # MODIFY — add list_edges, get_edge, enrich with node stubs
  - web/src/components/EntityTabs.tsx     # NEW — tab layout component
  - web/src/components/EdgeGraph.tsx      # NEW — interactive graph canvas
  - web/src/components/EdgeSidebar.tsx    # NEW — edge list with type grouping
  - web/src/components/AddEdgeModal.tsx   # NEW — edge creation UI
  - web/src/app/ideas/[id]/page.tsx       # MODIFY — adopt tab layout
  - web/src/app/concepts/[id]/page.tsx    # MODIFY — adopt tab layout
  - web/src/app/specs/[id]/page.tsx       # MODIFY — adopt tab layout
  - web/src/app/tasks/[id]/page.tsx       # MODIFY — adopt tab layout
  - web/src/app/contributors/[id]/page.tsx # MODIFY — adopt tab layout
  - api/tests/test_edges.py               # NEW — pytest tests

done_when:
  - GET /api/edges/types returns 46 types across 7 families
  - GET /api/entities/{id}/edges returns edges for any entity
  - POST /api/edges creates an edge; duplicate returns 409
  - cc edges <id> prints grouped edge list
  - cc edge types prints type registry table
  - Web entity pages render Overview|Edges|History|Contributors tabs
  - Edges tab shows interactive graph with colour-coded families

constraints:
  - Do not modify tests to force passing
  - Backwards-compatible: keep /api/graph/edges and /api/graph/nodes/{id}/edges working
  - canonical edge type list in edge_types.py is the single source of truth
```

---

## Verification Scenarios

### Scenario 1 — Type Registry Returns All 46 Types

**Setup**: API is running
**Action**:
```bash
curl -s https://api.coherencycoin.com/api/edges/types
```
**Expected**:
- HTTP 200
- `response.total == 46`
- Response contains 7 family objects
- Each family contains at least 5 type objects with `slug`, `description`, `canonical: true`
- Specific type exists: `resonates-with` in family `Ontological / Being`

**Edge case**: `GET /api/edges/types?family=nonexistent` returns 200 with `{"total": 0, "families": []}` (not 404)

---

### Scenario 2 — Create Edge and Retrieve It

**Setup**: Entities `idea_001` (idea) and `concept_resonance` (concept) exist in the graph
**Action**:
```bash
# Create edge
curl -s -X POST https://api.coherencycoin.com/api/edges \
  -H "Content-Type: application/json" \
  -d '{"from_id":"idea_001","to_id":"concept_resonance","type":"resonates-with","strength":0.85}'
```
**Expected**: HTTP 201, response contains `{"id":"...","type":"resonates-with","canonical":true,"strength":0.85}`

**Then** (retrieve by entity):
```bash
curl -s "https://api.coherencycoin.com/api/entities/idea_001/edges?type=resonates-with"
```
**Expected**: 200, `items` array contains the created edge with `from_node.name` and `to_node.name` populated

**Then** (retrieve neighbors):
```bash
curl -s "https://api.coherencycoin.com/api/entities/idea_001/neighbors?type=resonates-with"
```
**Expected**: 200, `neighbors[0].node.id == "concept_resonance"`, `neighbors[0].via_edge.type == "resonates-with"`

**Edge case — duplicate create**:
```bash
# Same POST again
curl -s -X POST https://api.coherencycoin.com/api/edges \
  -d '{"from_id":"idea_001","to_id":"concept_resonance","type":"resonates-with"}' \
  -H "Content-Type: application/json"
```
**Expected**: HTTP 409, `{"detail":"Edge already exists: idea_001 --[resonates-with]--> concept_resonance"}`

---

### Scenario 3 — Delete Edge and Confirm Removal

**Setup**: Edge `edge_abc123` exists (created in Scenario 2)
**Action**:
```bash
curl -s -X DELETE https://api.coherencycoin.com/api/edges/edge_abc123
```
**Expected**: HTTP 200, `{"deleted":"edge_abc123"}`

**Then** (confirm gone):
```bash
curl -s "https://api.coherencycoin.com/api/edges/edge_abc123"
```
**Expected**: HTTP 404, `{"detail":"Edge 'edge_abc123' not found"}`

**Edge case — delete again**:
```bash
curl -s -X DELETE https://api.coherencycoin.com/api/edges/edge_abc123
```
**Expected**: HTTP 404 (not 500, not 200)

---

### Scenario 4 — CLI Edge Navigation

**Setup**: Entity `idea_001` has at least 2 edges of different types
**Actions**:
```bash
cc edges idea_001
```
**Expected**: Tabular output with columns `from → type → to | strength`, grouped by type family. No stack trace.

```bash
cc edges idea_001 --type resonates-with
```
**Expected**: Only `resonates-with` edges shown.

```bash
cc edge create idea_001 implements spec_007
```
**Expected**: Prints the created edge JSON including `id`, `type`, `canonical: true`.

```bash
cc edge types
```
**Expected**: Multi-column table with all 46 types, grouped by family.

**Edge case — unknown entity**:
```bash
cc edges nonexistent_entity_xyz
```
**Expected**: Error message `Entity not found: nonexistent_entity_xyz` (not Python traceback).

---

### Scenario 5 — Error Handling for Unknown Edge Type

**Setup**: Entities exist
**Action**:
```bash
curl -s -X POST https://api.coherencycoin.com/api/edges \
  -H "Content-Type: application/json" \
  -d '{"from_id":"idea_001","to_id":"concept_resonance","type":"not-a-real-type"}'
```
**Expected (default)**: HTTP 201, response includes `"canonical": false` as a warning flag — edge is still created.

**Action (strict mode)**:
```bash
curl -s -X POST "https://api.coherencycoin.com/api/edges?strict=true" \
  -H "Content-Type: application/json" \
  -d '{"from_id":"idea_001","to_id":"concept_resonance","type":"not-a-real-type"}'
```
**Expected**: HTTP 400, `{"detail":"Unknown edge type 'not-a-real-type'...","canonical":false}`

**Action — missing entity**:
```bash
curl -s -X POST https://api.coherencycoin.com/api/edges \
  -H "Content-Type: application/json" \
  -d '{"from_id":"does-not-exist","to_id":"concept_resonance","type":"resonates-with"}'
```
**Expected**: HTTP 404, `{"detail":"Node 'does-not-exist' not found"}`

---

## Risks and Assumptions

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| N+1 queries when enriching edge responses with node stubs | High | Batch-load from_node and to_node in a single `WHERE id IN (...)` query |
| 46 types is a moving target — Living Codex may add/remove types | Medium | `canonical` flag allows forward compatibility; old edges with deprecated types keep `canonical: false` |
| Interactive graph canvas (D3/vis.js) heavy for mobile | Medium | Cap default render at 50 nodes; add a "load more" trigger |
| `/api/graph/nodes/{id}/edges` already exists — naming conflict | Low | Keep old route as alias; new routes at `/api/edges` and `/api/entities/{id}/edges` are canonical |
| Web tab layout requires refactoring multiple entity pages | Medium | Introduce a shared `EntityTabs` component; each page opts in |

---

## Known Gaps and Follow-up Tasks

- **Edge weight visualisation**: display strength as edge thickness in the graph canvas — deferred to a follow-up.
- **Graph layout persistence**: save user's pan/zoom state in localStorage per entity — deferred.
- **Bulk edge import**: `POST /api/edges/bulk` for agent pipelines importing many relationships — deferred.
- **Edge history**: audit trail of who created/deleted edges (already captured via `created_by` but not surfaced in the Edges tab History sub-tab) — deferred.
- **Search by edge type across all entities**: `GET /api/edges?type=resonates-with` returns a global list — this is in scope but the UI entry point (a dedicated graph exploration page) is deferred.
- **CLI `cc edges` paging**: for entities with hundreds of edges, add `--limit` and `--offset` — deferred.

---

## Observability / Proof This Is Working

To answer the open question *"how can we show whether this is working and make proof clearer over time"*:

1. **Type coverage metric** — `GET /api/edges/stats` (add to the existing `/api/graph/stats` response): reports `edge_type_coverage` as the fraction of the 46 canonical types that have at least 1 edge in the graph. A coverage of 0/46 proves the graph is untyped; 30/46 proves real use.

2. **Edge count time-series** — edge creation events are logged to the audit ledger (already wired). Dashboard can chart `edges created per day by type family`.

3. **CI verification** — the test suite (Scenario 1–5 above) runs on every PR. A badge on the README reflects passing state.

4. **Graph connectivity index** — `GET /api/graph/stats` should include `avg_edges_per_node`. A healthy graph trends upward as agents and contributors add relationships.

5. **Edge type heatmap on web** — the Edges tab sidebar shows a mini heatmap of usage across 46 types for the current entity. Globally, the `/graph` page shows a network-wide heatmap. Empty heatmap = no edges = feature not adopted.

---

## Research Inputs

- `2026-03-28` — Living-Codex-CSharp (github.com/seeker71/Living-Codex-CSharp) — source of the 46 relationship types and the 7-axis ontology
- `2026-03-28` — `api/app/models/graph.py` — existing Node + Edge schema; `graph_edges` table is in place with unique constraint on `(from_id, to_id, type)`
- `2026-03-28` — `api/app/routers/graph.py` — existing `/api/graph/edges` endpoints; this spec adds dedicated `/api/edges` layer on top without removing the old routes
- `2026-03-28` — `CLAUDE.md` — code isolation rules, workflow (spec → test → implement → CI → review → merge)
