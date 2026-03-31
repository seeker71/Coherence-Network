# Spec 182: Fractal Zoom Navigation

**Spec ID**: 182-fractal-zoom-navigation
**Idea ID**: fractal-zoom-navigation
**Task ID**: task_c5f164e7234a5941
**Status**: draft
**Priority**: high
**Author**: product-manager agent
**Date**: 2026-03-28
**Depends on**: Spec 008 (Graph Foundation), Spec 166 (Universal Node + Edge Data Layer), Spec 169 (Fractal Node + Edge Primitives), Spec 172 (Fractal Self Balance)

---

## Purpose

Define the fractal zoom navigation system: the ability to traverse the Coherence Network graph at any scale — from planetary pillars down to atomic leaf metrics — and encounter the same structure at every level: a node with children, typed edges, a coherence score, and open questions. Non-technical users see cards and gardens; technical users see the graph. The pattern is invariant across depth.

---

## Summary

The Coherence Network is fundamentally fractal: every pillar contains domains, every domain contains ideas, every idea contains implementations, and every implementation contains metrics. At each level, the same four properties hold:

1. **Node** — a named entity with a type, lifecycle state, and coherence score
2. **Children** — zero or more child nodes connected by typed edges (`parent-of`, `depends-on`, `implements`)
3. **Coherence score** — a 0.0–1.0 signal computed from the quality of its children and their relationships
4. **Open questions** — structured unanswered questions attached to the node that drive iteration

This spec introduces the `GET /api/graph/zoom/{node_id}` endpoint (and associated query parameters for depth control), the `GET /api/graph/pillars` root-level anchor, and the front-end rendering contract for dual-mode display (card/garden for non-technical users; raw graph for technical users).

The canonical example hierarchy is:

```
Pillars (top-level zoom: depth=0)
  └── Trust (zoom depth=1)
        ├── Coherence Scoring (depth=2)
        │     ├── Test Coverage Analysis (depth=3)
        │     ├── Documentation Quality Metrics (depth=3)
        │     └── Simplicity Index (depth=3)
        ├── Contribution Verification (depth=2)
        └── Identity Attestation (depth=2)
  ├── Traceability (depth=1)
  ├── Freedom (depth=1)
  ├── Uniqueness (depth=1)
  └── Collaboration (depth=1)
```

At every level, the same API contract holds. The web UI switches between **Card View** (summary cards arranged in a garden layout) and **Graph View** (interactive node-edge network diagram) based on user preference or role.

---

## Requirements

- [ ] `GET /api/graph/pillars` returns all root-level pillar nodes: `traceability`, `trust`, `freedom`, `uniqueness`, `collaboration`
- [ ] Each pillar node response includes `id`, `name`, `node_type`, `coherence_score`, `child_count`, `open_question_count`, `lifecycle_state`
- [ ] `GET /api/graph/zoom/{node_id}` returns the node plus its immediate children (depth=1 by default)
- [ ] `GET /api/graph/zoom/{node_id}?depth=N` where N ∈ {1,2,3} returns the subtree up to N levels deep
- [ ] `GET /api/graph/zoom/{node_id}?depth=0` returns only the node itself with no children
- [ ] Every node in the zoom response contains `id`, `name`, `node_type`, `coherence_score`, `open_questions`, `children`, `edges`
- [ ] `GET /api/graph/zoom/{node_id}` returns HTTP 404 if the node does not exist
- [ ] `GET /api/graph/zoom/{node_id}?depth=4` returns HTTP 422 with a message that max depth is 3
- [ ] Coherence score for a leaf node (no children) is derived from its own `payload` quality metrics; never null — defaults to 0.0
- [ ] Coherence score for a non-leaf node is the weighted average of its children's coherence scores, where weights are determined by edge type (`implements` > `depends-on` > `parent-of`)
- [ ] Open questions are stored as an array of `{id, question, created_at, resolved}` objects in `graph_nodes.payload.open_questions`
- [ ] `POST /api/graph/nodes/{node_id}/questions` adds an open question to the node, returns the updated question list
- [ ] `PATCH /api/graph/nodes/{node_id}/questions/{question_id}` marks a question as resolved
- [ ] `GET /api/graph/zoom/{node_id}` response includes `view_hint: "garden"` for nodes at depth ≥ 2 (many children, visual layout) and `view_hint: "graph"` for nodes at depth ≤ 1 (few children, topology matters)
- [ ] `GET /api/graph/pillars` is accessible without authentication (public read)
- [ ] `GET /api/graph/zoom/{node_id}` is accessible without authentication (public read)
- [ ] The five canonical pillar nodes must be seeded during database initialization if they do not already exist
- [ ] `GET /api/graph/zoom/trust?depth=2` returns the Trust pillar with its three children: `coherence-scoring`, `contribution-verification`, `identity-attestation`
- [ ] `GET /api/graph/zoom/coherence-scoring?depth=1` returns the coherence-scoring node with its three leaf children: `test-coverage-analysis`, `documentation-quality-metrics`, `simplicity-index`

---

## Out of Scope

- Automatic coherence score recomputation on every graph mutation (this spec uses on-demand compute)
- Real-time WebSocket push for score changes
- Editing node names or types via the zoom API (covered in Spec 169 CRUD)
- User authentication and role-based access control for write operations
- Mobile-native views (responsive web only)
- AI-generated suggestions for resolving open questions (future spec)

---

## API Changes

### `GET /api/graph/pillars`

Returns all top-level pillar nodes anchoring the fractal hierarchy.

**Response 200**
```json
{
  "pillars": [
    {
      "id": "trust",
      "name": "Trust",
      "node_type": "concept",
      "coherence_score": 0.72,
      "child_count": 3,
      "open_question_count": 2,
      "lifecycle_state": "water"
    },
    {
      "id": "traceability",
      "name": "Traceability",
      "node_type": "concept",
      "coherence_score": 0.61,
      "child_count": 4,
      "open_question_count": 1,
      "lifecycle_state": "water"
    }
  ],
  "total": 5
}
```

---

### `GET /api/graph/zoom/{node_id}?depth={N}`

Returns a subtree rooted at `node_id` up to `N` levels deep.

**Path params**
- `node_id` — string, required. The `id` of the graph node.

**Query params**
- `depth` — integer, default 1, min 0, max 3.

**Response 200**
```json
{
  "node": {
    "id": "trust",
    "name": "Trust",
    "node_type": "concept",
    "coherence_score": 0.72,
    "lifecycle_state": "water",
    "view_hint": "graph",
    "open_questions": [
      {
        "id": "q1",
        "question": "How do we measure trust degradation over time?",
        "created_at": "2026-03-28T10:00:00Z",
        "resolved": false
      }
    ],
    "children": [
      {
        "id": "coherence-scoring",
        "name": "Coherence Scoring",
        "node_type": "concept",
        "coherence_score": 0.81,
        "lifecycle_state": "water",
        "view_hint": "garden",
        "open_questions": [],
        "children": [],
        "edges": [
          {
            "from": "trust",
            "to": "coherence-scoring",
            "edge_type": "parent-of"
          }
        ]
      }
    ],
    "edges": [
      {
        "from": "trust",
        "to": "coherence-scoring",
        "edge_type": "parent-of"
      }
    ]
  },
  "depth_requested": 1,
  "total_nodes_in_subtree": 4
}
```

**Response 404** — node not found
```json
{"detail": "Node 'unknown-id' not found"}
```

**Response 422** — depth out of range
```json
{"detail": "depth must be between 0 and 3, got 4"}
```

---

### `POST /api/graph/nodes/{node_id}/questions`

Adds an open question to a node.

**Request body**
```json
{"question": "How can we improve this signal over time?"}
```

**Response 201**
```json
{
  "id": "q2",
  "question": "How can we improve this signal over time?",
  "created_at": "2026-03-28T12:00:00Z",
  "resolved": false,
  "node_id": "trust"
}
```

---

### `PATCH /api/graph/nodes/{node_id}/questions/{question_id}`

Resolves or re-opens a question.

**Request body**
```json
{"resolved": true}
```

**Response 200**
```json
{
  "id": "q1",
  "question": "How do we measure trust degradation over time?",
  "resolved": true,
  "resolved_at": "2026-03-28T14:00:00Z",
  "node_id": "trust"
}
```

---

## Data Model

### New columns on `graph_nodes` (via migration)

No new columns are required. The open questions array is stored in `graph_nodes.payload` as a JSONB sub-key `open_questions`. The coherence score is stored in `graph_nodes.coherence_score` (already exists per Spec 166 or added here if absent).

If `coherence_score` does not exist on `graph_nodes`:

```sql
ALTER TABLE graph_nodes
  ADD COLUMN IF NOT EXISTS coherence_score FLOAT NOT NULL DEFAULT 0.0
  CHECK (coherence_score >= 0.0 AND coherence_score <= 1.0);
```

### Seed data

The five pillar nodes must be present at system boot. The seeding logic runs during API startup (idempotent `INSERT ... ON CONFLICT DO NOTHING`):

| id | name | node_type | lifecycle_state |
|----|------|-----------|----------------|
| `traceability` | Traceability | concept | water |
| `trust` | Trust | concept | water |
| `freedom` | Freedom | concept | water |
| `uniqueness` | Uniqueness | concept | water |
| `collaboration` | Collaboration | concept | water |

### Trust subtree seed

Second-level seed for the canonical Trust example:

| id | name | parent_id | edge_type |
|----|------|-----------|-----------|
| `coherence-scoring` | Coherence Scoring | trust | parent-of |
| `contribution-verification` | Contribution Verification | trust | parent-of |
| `identity-attestation` | Identity Attestation | trust | parent-of |

Third-level seed under coherence-scoring:

| id | name | parent_id | edge_type |
|----|------|-----------|-----------|
| `test-coverage-analysis` | Test Coverage Analysis | coherence-scoring | parent-of |
| `documentation-quality-metrics` | Documentation Quality Metrics | coherence-scoring | parent-of |
| `simplicity-index` | Simplicity Index | coherence-scoring | parent-of |

---

## Files to Create or Modify

- `api/routers/graph_zoom.py` — New router handling `GET /api/graph/pillars` and `GET /api/graph/zoom/{node_id}`
- `api/routers/graph_questions.py` — New router handling question CRUD: `POST` and `PATCH /api/graph/nodes/{node_id}/questions`
- `api/models/graph_zoom.py` — Pydantic response models: `ZoomNode`, `ZoomResponse`, `PillarListResponse`, `OpenQuestion`
- `api/services/zoom_service.py` — Business logic: recursive subtree fetch, coherence score computation, view_hint derivation
- `api/migrations/versions/XXX_add_coherence_score_to_graph_nodes.py` — Alembic migration for `coherence_score` column (if absent)
- `api/seed/pillar_seed.py` — Idempotent seed for 5 pillars + Trust subtree
- `api/main.py` — Register new routers; call seed on startup
- `api/tests/test_fractal_zoom.py` — Acceptance tests covering all requirements
- `web/app/graph/zoom/[nodeId]/page.tsx` — Zoom page: renders card/garden vs graph view based on `view_hint`
- `web/components/graph/ZoomCard.tsx` — Card component for garden/card view
- `web/components/graph/ZoomGraph.tsx` — Graph view component (wraps existing graph lib)

---

## Coherence Score Computation

The coherence score is computed lazily on read (not persisted on every write), then cached in `graph_nodes.coherence_score` with a 5-minute TTL.

**Leaf node score** (no children):
- Derived from `payload` quality fields: `has_description` (0.3), `has_tags` (0.1), `has_open_questions` indicating engagement (0.2), `resolved_question_ratio` (0.4)
- Formula: `sum(field_weight * field_present)`

**Non-leaf node score** (has children):
- Weighted average of children's scores
- Edge type weights: `implements` = 1.5, `depends-on` = 1.2, `parent-of` = 1.0
- Formula: `sum(child.score * edge_weight) / sum(edge_weight)`

**Score bounds**: Always clamped to `[0.0, 1.0]`.

---

## Web UI Rendering Contract

The `view_hint` field returned by the API drives the frontend rendering mode:

| `view_hint` | Component | Description |
|------------|-----------|-------------|
| `"garden"` | `ZoomCard` grid | Card layout — readable by non-technical users. Each child is a card showing name, coherence score, child_count, top open question. |
| `"graph"` | `ZoomGraph` | Interactive force-directed graph — for technical users. Nodes sized by coherence score; edges colored by type. |

The user can always override the hint via a toggle button ("View as Cards" / "View as Graph").

**URL structure for zoom navigation**:
- Root: `/graph` — shows pillar cards
- Pillar zoom: `/graph/zoom/trust` — shows Trust's children
- Deeper zoom: `/graph/zoom/coherence-scoring` — shows coherence scoring's leaf metrics

---

## Acceptance Criteria

- `GET /api/graph/pillars` returns HTTP 200 with exactly 5 pillar nodes, each having `id`, `name`, `coherence_score`, `child_count`, `open_question_count`, `lifecycle_state`
- `GET /api/graph/zoom/trust` (default depth=1) returns Trust node plus its 3 direct children
- `GET /api/graph/zoom/trust?depth=2` returns Trust node with full subtree including leaf nodes under `coherence-scoring`
- `GET /api/graph/zoom/trust?depth=0` returns Trust node with `children: []`
- `GET /api/graph/zoom/nonexistent` returns HTTP 404
- `GET /api/graph/zoom/trust?depth=4` returns HTTP 422
- Every node in zoom response has `coherence_score` in `[0.0, 1.0]`, never null
- Every node in zoom response has a `view_hint` of either `"garden"` or `"graph"`
- `POST /api/graph/nodes/trust/questions` returns HTTP 201 with question object including `id`, `resolved: false`
- `PATCH /api/graph/nodes/trust/questions/{id}` with `{"resolved": true}` returns `resolved: true` and `resolved_at`
- `POST /api/graph/nodes/nonexistent/questions` returns HTTP 404
- Seed is idempotent: running it twice does not create duplicate pillar nodes
- `pytest api/tests/test_fractal_zoom.py` passes with 0 failures

## Verification Scenarios

### Scenario 1: Pillar nodes exist and are readable

**Setup**: Fresh database with seed data applied (or existing instance with pillars seeded).

**Action**:
```bash
curl -s https://api.coherencycoin.com/api/graph/pillars
```

**Expected result**:
- HTTP 200
- Response body contains `"pillars"` array with exactly 5 items
- Each item has `id` in `["traceability","trust","freedom","uniqueness","collaboration"]`
- Each item has `coherence_score` in range `[0.0, 1.0]`
- Each item has `child_count` ≥ 0 (Trust should have `child_count: 3`)

**Edge case**: If seed has not been run, endpoint returns empty `"pillars": []` with `"total": 0` rather than 404 or 500.

---

### Scenario 2: Zoom into Trust at depth=1

**Setup**: Pillars seeded; Trust subtree seeded (`coherence-scoring`, `contribution-verification`, `identity-attestation` as children).

**Action**:
```bash
curl -s "https://api.coherencycoin.com/api/graph/zoom/trust?depth=1"
```

**Expected result**:
- HTTP 200
- `node.id == "trust"`
- `node.children` array has length 3
- `node.children[].id` contains `"coherence-scoring"`, `"contribution-verification"`, `"identity-attestation"`
- Each child has `coherence_score` in `[0.0, 1.0]`, `node_type: "concept"`, `edges` array with at least one entry where `edge_type == "parent-of"`
- `total_nodes_in_subtree == 4` (Trust + 3 children)
- `node.view_hint == "graph"` (depth=1, few children)

**Edge case**: `curl -s "https://api.coherencycoin.com/api/graph/zoom/trust?depth=0"` returns `node.children: []` and `total_nodes_in_subtree: 1`.

---

### Scenario 3: Zoom deep into coherence-scoring at depth=2

**Setup**: Full Trust subtree seeded including leaf nodes under coherence-scoring.

**Action**:
```bash
curl -s "https://api.coherencycoin.com/api/graph/zoom/trust?depth=2"
```

**Expected result**:
- HTTP 200
- `node.id == "trust"`, `node.children` has 3 items
- The `coherence-scoring` child itself has `children` with 3 items: `test-coverage-analysis`, `documentation-quality-metrics`, `simplicity-index`
- Leaf nodes have `children: []` and `view_hint: "garden"` (depth ≥ 2)
- `total_nodes_in_subtree == 7` (trust + 3 + 3)
- Trust's `coherence_score` ≥ coherence-scoring child's score (propagated upward)

**Edge case**:
```bash
curl -s "https://api.coherencycoin.com/api/graph/zoom/trust?depth=4"
```
Returns HTTP 422 with `"detail": "depth must be between 0 and 3, got 4"`.

---

### Scenario 4: Open question lifecycle (create and resolve)

**Setup**: Node `trust` exists.

**Action — Create**:
```bash
curl -s -X POST https://api.coherencycoin.com/api/graph/nodes/trust/questions \
  -H "Content-Type: application/json" \
  -d '{"question": "How can we improve this idea, show whether it is working yet, and make that proof clearer over time?"}'
```

**Expected result**:
- HTTP 201
- Response contains `id` (non-empty string), `question` matching input, `resolved: false`, `created_at` (ISO 8601)

**Action — Verify via zoom**:
```bash
curl -s "https://api.coherencycoin.com/api/graph/zoom/trust?depth=0"
```
- `node.open_questions` contains the newly created question with `resolved: false`
- `node.open_question_count == 1` (or incremented if others exist)

**Action — Resolve**:
```bash
QUESTION_ID=<id from create response>
curl -s -X PATCH "https://api.coherencycoin.com/api/graph/nodes/trust/questions/$QUESTION_ID" \
  -H "Content-Type: application/json" \
  -d '{"resolved": true}'
```
- HTTP 200, `resolved: true`, `resolved_at` populated

**Edge case — Bad node**:
```bash
curl -s -X POST https://api.coherencycoin.com/api/graph/nodes/nonexistent-node/questions \
  -H "Content-Type: application/json" \
  -d '{"question": "test"}'
```
Returns HTTP 404 with `"detail": "Node 'nonexistent-node' not found"`.

---

### Scenario 5: Missing node returns 404, not 500

**Setup**: Any database state.

**Action**:
```bash
curl -s "https://api.coherencycoin.com/api/graph/zoom/this-node-does-not-exist"
```

**Expected result**:
- HTTP 404 (not 422, not 500)
- Response body: `{"detail": "Node 'this-node-does-not-exist' not found"}`

**Edge case — Empty string simulation** (path routing prevents empty but test malformed ID):
```bash
curl -s "https://api.coherencycoin.com/api/graph/zoom/___invalid___"
```
Returns HTTP 404 (not 500).

---

## Risks and Assumptions

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Coherence score computation is expensive for deep subtrees | Medium | High | Cache in `graph_nodes.coherence_score`; recompute max once per 5 minutes per node |
| Recursive subtree fetch causes N+1 queries | High | High | Use single CTE query to fetch all descendants up to depth N |
| Pillar seed runs twice and creates duplicates | Low | Low | Use `INSERT ... ON CONFLICT DO NOTHING` on `id` |
| `view_hint` logic is brittle — child count thresholds may need tuning | Medium | Low | Make threshold configurable via env var `ZOOM_GARDEN_THRESHOLD` (default: 2) |
| Open questions stored in JSONB payload may be hard to query | Low | Medium | Keep questions in `payload.open_questions[]`; add GIN index if query performance degrades |

### Assumptions

- `graph_nodes` table exists with at least `id`, `name`, `node_type`, `payload`, `lifecycle_state` columns (from Spec 166)
- `graph_edges` table exists with `from_node_id`, `to_node_id`, `edge_type` columns (from Spec 166/169)
- The five pillar IDs (`traceability`, `trust`, `freedom`, `uniqueness`, `collaboration`) are stable and never renamed
- `coherence_score` will be added to `graph_nodes` if it does not exist; the migration must be `NOT VALID` to avoid table locks
- Frontend has access to a graph rendering library (e.g., react-force-graph or vis-network) already in the web stack

---

## Known Gaps and Follow-up Tasks

- **Real-time score propagation**: When a leaf node's coherence score changes, parent scores are not automatically invalidated. A future spec should add score invalidation events or a background recomputation job.
- **Coherence scoring rubric for leaf metrics**: The current spec defines a generic payload-quality formula. A follow-up spec should define domain-specific rubrics for `test-coverage-analysis` (maps to actual test coverage %), `documentation-quality-metrics` (maps to doc coverage score), and `simplicity-index` (maps to complexity score from static analysis).
- **Proof of working**: The open question "how can we improve this idea, show whether it is working yet, and make that proof clearer over time?" is answered at the system level by: (a) `GET /api/graph/zoom/{id}` always returning a coherence score; (b) open questions being attached to each node to track unresolved uncertainty; (c) the score trending upward as questions are resolved and children are added. Future work: add a `GET /api/graph/zoom/{id}/history` endpoint showing coherence score over time to make improvement visible.
- **Pillar ownership and governance**: Who can add a new pillar? Currently unrestricted. A future spec should introduce a governance model (e.g., requires 2+ maintainer approvals via idea lifecycle).
- **Web UI implementation depth**: This spec defines the rendering contract but not the full UI component implementation. A companion UI spec should detail accessibility requirements, mobile layout, and keyboard navigation.

---

## Task Card

```yaml
goal: Implement fractal zoom navigation — same structure at every graph depth, dual-mode rendering
files_allowed:
  - specs/182-fractal-zoom-navigation.md
  - api/routers/graph_zoom.py
  - api/routers/graph_questions.py
  - api/models/graph_zoom.py
  - api/services/zoom_service.py
  - api/migrations/versions/*_add_coherence_score_to_graph_nodes.py
  - api/seed/pillar_seed.py
  - api/main.py
  - api/tests/test_fractal_zoom.py
  - web/app/graph/zoom/[nodeId]/page.tsx
  - web/components/graph/ZoomCard.tsx
  - web/components/graph/ZoomGraph.tsx
  - .gitignore
  - .task-checkpoint.md
done_when:
  - GET /api/graph/pillars returns 5 pillar nodes
  - GET /api/graph/zoom/trust?depth=2 returns Trust subtree with coherence-scoring and its 3 leaf children
  - POST /api/graph/nodes/trust/questions creates a question; PATCH resolves it
  - GET /api/graph/zoom/nonexistent returns 404
  - GET /api/graph/zoom/trust?depth=4 returns 422
  - python3 scripts/validate_spec_quality.py --file specs/182-fractal-zoom-navigation.md exits 0
  - pytest api/tests/test_fractal_zoom.py passes with 0 failures
commands:
  - python3 scripts/validate_spec_quality.py --file specs/182-fractal-zoom-navigation.md
  - cd api && python -m pytest tests/test_fractal_zoom.py -q
constraints:
  - spec only in this task; no runtime code changes
  - coherence score is computed on-demand, not real-time propagated
  - seed data is idempotent
```
