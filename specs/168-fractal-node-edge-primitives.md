# Spec 168: Universal Node + Edge Primitives with Typed Relationships

**Spec ID**: 168-fractal-node-edge-primitives
**Idea ID**: fractal-node-edge-primitives
**Task ID**: task_9125767b3db4bde2
**Status**: draft
**Priority**: high
**Author**: product-manager agent
**Date**: 2026-03-28
**Depends on**: Spec 166 (Universal Node + Edge Data Layer)

---

## Purpose

Establish a canonical, closed-but-extensible vocabulary of node types and typed edge relationships that makes the Coherence Network graph a reliable fractal data layer. Every meaningful entity becomes a node; every relationship between entities is expressed as a typed edge with explicit semantic meaning. This enables generic traversal queries, value lineage attribution, lifecycle-aware filtering, and pipeline-wide observability — replacing ad-hoc SQL with a uniform semantic contract. This is the data layer that makes the fractal possible.

---

## Requirements

- [ ] `node_type` is constrained to exactly 10 canonical values: `idea`, `concept`, `spec`, `implementation`, `service`, `contributor`, `domain`, `pipeline-run`, `event`, `artifact`
- [ ] `edge_type` is constrained to exactly 7 canonical values: `inspires`, `depends-on`, `implements`, `contradicts`, `extends`, `analogous-to`, `parent-of`
- [ ] POST `/api/graph/nodes` with an unrecognized `node_type` returns HTTP 422 with a message listing valid types
- [ ] POST `/api/graph/edges` with an unrecognized `edge_type` returns HTTP 422 with a message listing valid types
- [ ] POST `/api/graph/edges` where `from_node_id == to_node_id` (self-loop) returns HTTP 422
- [ ] Every `idea` node defaults to `lifecycle_state: gas` when not specified in payload
- [ ] Every `spec` node defaults to `lifecycle_state: ice` when not specified in payload
- [ ] Every `contributor` node defaults to `lifecycle_state: water` when not specified in payload
- [ ] GET `/api/graph/nodes/{id}/neighbors?lifecycle_state=ice` returns only neighbors whose payload `lifecycle_state` equals `"ice"`
- [ ] GET `/api/graph/node-types` returns all 10 node type registry entries with `type`, `description`, `lifecycle_default`
- [ ] GET `/api/graph/edge-types` returns all 7 edge type registry entries with `type`, `description`, `is_symmetric`
- [ ] GET `/api/graph/proof` returns HTTP 200 with `total_nodes`, `total_edges`, `nodes_by_type`, `edges_by_type`, `lifecycle_distribution`, `coverage_pct`
- [ ] GET `/api/graph/proof` returns HTTP 200 even with an empty graph — does not error on zero counts
- [ ] Alembic migration applies `NOT VALID` CHECK constraints on `node_type` and `edge_type` without locking the table
- [ ] `pytest api/tests/test_typed_node_edge_primitives.py` passes with 0 failures and ≥ 90% line coverage on new code

---

## Summary

This spec defines the **semantic layer** on top of the raw graph primitives introduced in Spec 166. Where Spec 166 established the *storage contract* (`graph_nodes`, `graph_edges` tables, CRUD endpoints), this spec establishes the *meaning contract*: a canonical, closed-but-extensible vocabulary of node types and edge types, the Ice/Water/Gas lifecycle model for nodes, and the constraint machinery that makes the graph *reliable* rather than merely *flexible*.

The central claim: **everything meaningful in the Coherence Network is a node** — ideas, concepts, services, contributors, specs, implementations, domains, pipeline runs, events. The relationships between them form a typed graph. When traversed, this graph encodes value lineage, attribution chains, dependency trees, and the epistemic state of the whole system. This is the data layer that makes the fractal possible: any node can contain sub-nodes of the same shape, and any two nodes at any depth can be linked by a semantically precise edge.

Without a typed vocabulary, the graph is a dumping ground. With one, it becomes the single source of truth for what the system knows, what it has done, and what it is becoming.

---

## Motivation

### The fractal claim

The Coherence Network is organized as a fractal: every idea can contain sub-ideas, every spec can have sub-specs, every contributor can sponsor other contributors. This is not a metaphor — it requires a real data structure. The current data model has ideas, tasks, and nodes as independent silos, connected only by ad-hoc foreign keys with no queryable type information on the relationship.

To traverse "what does this idea depend on?" or "what did this contributor inspire?", you currently need bespoke SQL. The typed edge layer makes those traversals generic: `GET /api/graph/nodes/{id}/neighbors?rel_type=depends-on&direction=incoming` answers any such question once the edge types are defined.

### The Living Codex lineage

This spec draws directly from the Living Codex origin project, which defined:
- **U-Core ontology**: universal primitives (entity, relation, attribute) that all domain concepts instantiate
- **Breath/water states**: entities cycle through states of activation, flow, and rest
- **Resonance and belief systems**: edges encode epistemic confidence, not just structural connectivity

The Ice/Water/Gas lifecycle maps to the breath/water state model: Ice = specification/frozen potential, Water = active flow/implementation, Gas = dissolved/ideation/pre-form. This is not arbitrary naming — it encodes the *phase* of an entity's development, enabling agents and humans to reason about where in the pipeline any node sits.

### The minimal edge set problem

The risk of a typed edge vocabulary is one of two failure modes:
1. **Too few types** — everything collapses into `RELATED_TO`, defeating the purpose
2. **Too many types** — combinatorial explosion, cognitive overload, low adoption

The seven types proposed here (`inspires`, `depends-on`, `implements`, `contradicts`, `extends`, `analogous-to`, `parent-of`) were selected by partitioning the space of meaningful relationships into non-overlapping semantic categories, then stress-testing with real node pairs from the existing graph.

---

## Node Types (Canonical)

All nodes are stored in `graph_nodes` with `node_type` constrained to the following vocabulary:

| `node_type` | Description | Example `external_id` |
|---|---|---|
| `idea` | A tracked concept or proposal | `fractal-node-edge-primitives` |
| `concept` | An abstract/theoretical construct | `ice-water-gas-lifecycle` |
| `spec` | A written specification document | `168-fractal-node-edge-primitives` |
| `implementation` | A code artifact, PR, or deployed feature | `pr-472-graph-router` |
| `service` | A running software service or API | `coherence-network-api` |
| `contributor` | A human or agent that contributes work | `agent-claude-sonnet-4-6` |
| `domain` | A knowledge domain or namespace | `graph-theory`, `osint` |
| `pipeline-run` | A single execution of a pipeline stage | `run-20260328-001` |
| `event` | A system event or signal | `task-completed`, `score-changed` |
| `artifact` | A produced output (test file, doc, report) | `test_graph_layer.py` |

**Extension path**: New node types require a migration `ALTER TYPE node_type_enum ADD VALUE 'new_type'` plus an entry in `api/config/node_type_registry.json` with `description`, `payload_schema`, and `example_id`. Additions without the registry entry are rejected by the service layer.

---

## Edge Types (Canonical — Minimal Set)

All edges are stored in `graph_edges` with `edge_type` constrained to the following 7 types:

| `edge_type` | Direction | Meaning | Example |
|---|---|---|---|
| `inspires` | A → B | A gave rise to or motivated B without directly implementing it | `idea:resonance-nav` → `inspires` → `idea:fractal-primitives` |
| `depends-on` | A → B | A requires B to function correctly or to be implemented first | `spec:168` → `depends-on` → `spec:166` |
| `implements` | A → B | A puts B into practice — code realizes a spec, a spec realizes an idea | `impl:graph-router` → `implements` → `spec:166` |
| `contradicts` | A ↔ B | A and B are in tension or mutually exclusive (symmetric) | `idea:centralise-auth` ↔ `contradicts` ↔ `idea:federated-identity` |
| `extends` | A → B | A adds to or refines B, building on its foundation without replacing it | `spec:168` → `extends` → `spec:166` |
| `analogous-to` | A ↔ B | A and B are structurally isomorphic or conceptually parallel (symmetric) | `concept:ice-water-gas` ↔ `analogous-to` ↔ `concept:breath-states` |
| `parent-of` | A → B | A hierarchically contains B (A is the container, B is the sub-unit) | `domain:graph-theory` → `parent-of` → `concept:edge-types` |

### Why exactly these 7?

The selection is derived from a 3-dimensional classification of relationship types:

1. **Causal / temporal direction** — captures *why* something exists: `inspires` (soft causal), `depends-on` (hard dependency), `implements` (realization)
2. **Epistemic opposition** — captures *conflict*: `contradicts`
3. **Structural expansion** — captures *how knowledge grows*: `extends` (additive), `parent-of` (hierarchical)
4. **Cross-domain isomorphism** — captures *analogical reasoning*: `analogous-to`

Relationships not in this set that teams might reach for, and why they are excluded:
- `authored-by` — this is a property (`contributor_id` in the node payload), not a graph edge; it doesn't add traversal value
- `tagged-with` — use `parent-of` from a domain/concept node; `tagged-with` is redundant and creates a degenerate star topology
- `succeeds` / `replaces` — use `extends` with `payload: {"replaces": true}`; the semantic difference doesn't warrant a new type
- `references` — too broad; ask *why* it references; that maps to `inspires`, `depends-on`, or `analogous-to`
- `generates` (from Spec 166 prototype) — subsumed by `implements` (an idea generates a spec via `implements` semantics at the pipeline level)

**Adding edge types in future**: Any proposed addition must clear 3 review criteria: (a) it cannot be expressed as a combination of existing types, (b) it enables a concrete new traversal query that returns actionable data, (c) it has ≥5 real examples from the existing graph.

---

## Lifecycle States: Ice / Water / Gas

Every node carries a `lifecycle_state` field (stored in `payload` under a reserved key, enforced in the service layer):

| State | Symbol | Meaning | Allowed transitions |
|---|---|---|---|
| `gas` | ☁ | Ideation phase. The entity is an unformed concept — described but not specified, not yet committed to. | → `ice` |
| `ice` | ❄ | Specification phase. The entity is specified/frozen — a spec exists, acceptance criteria are written, but implementation has not begun. | → `water`, ← `gas` |
| `water` | 💧 | Active phase. The entity is in active flow — being implemented, run, or used. Evidence of activity exists. | → `gas` (deprecated/dissolved), → `ice` (paused/re-specified) |

### Default lifecycle by node type

| node_type | Default `lifecycle_state` |
|---|---|
| `idea` | `gas` |
| `concept` | `gas` |
| `spec` | `ice` |
| `implementation` | `water` |
| `service` | `water` |
| `contributor` | `water` |
| `domain` | `ice` |
| `pipeline-run` | `water` |
| `event` | `water` |
| `artifact` | `water` |

### Transition rules

- Transition `water → gas` represents **deprecation or dissolution** — the entity was active but is no longer.
- No direct `ice → gas` transition (cannot un-specify without going through active).
- `pipeline-run` and `event` nodes are always `water` and cannot transition (ephemeral, append-only).
- Lifecycle state changes are tracked by recording an `event` node linked via `parent-of`.

### Lifecycle state in queries

The lifecycle state is queryable as a filter on the neighbors endpoint:
```
GET /api/graph/nodes/{id}/neighbors?lifecycle_state=ice
```
And on the bulk search endpoint:
```
GET /api/graph/nodes?node_type=idea&lifecycle_state=gas
```
This enables "show me all unspecified ideas" (gas), "show me all frozen specs waiting for implementation" (ice), or "show me all active services" (water).

---

## API Changes

### New endpoints (all under `/api/graph/`)

#### `GET /api/graph/node-types` *(new)*

Returns the full registry of valid node types and their schemas.

**Response 200**
```json
{
  "node_types": [
    {
      "type": "idea",
      "description": "A tracked concept or proposal",
      "lifecycle_default": "gas",
      "payload_schema": { "title": "string", "lifecycle_state": "gas|ice|water" }
    }
  ]
}
```

---

#### `GET /api/graph/edge-types` *(new)*

Returns the full registry of valid edge types and their semantics.

**Response 200**
```json
{
  "edge_types": [
    {
      "type": "inspires",
      "description": "A gave rise to or motivated B without directly implementing it",
      "is_symmetric": false,
      "example": "idea:resonance-nav → inspires → idea:fractal-primitives"
    }
  ]
}
```

---

#### `GET /api/graph/nodes/{id}/neighbors` *(extended from Spec 166)*

New query parameters:
- `lifecycle_state=gas|ice|water` — filter neighbors by lifecycle state
- `rel_type=<edge_type>` — filter by edge type
- `direction=incoming|outgoing|both` (default: `both`)
- `depth=1|2` (default: 1, max: 2)

---

#### `GET /api/graph/proof` *(new)*

Returns aggregate evidence that the graph is being used as the fractal data layer.

**Response 200**
```json
{
  "total_nodes": 1247,
  "total_edges": 3891,
  "nodes_by_type": { "idea": 342, "spec": 89, "implementation": 156, "contributor": 24 },
  "edges_by_type": { "implements": 89, "depends-on": 234, "inspires": 178 },
  "lifecycle_distribution": { "gas": 312, "ice": 187, "water": 748 },
  "graph_density": 0.0025,
  "connected_components": 3,
  "average_degree": 6.24,
  "last_edge_created_at": "2026-03-28T11:45:00Z",
  "coverage_pct": {
    "ideas_with_spec": 0.62,
    "specs_with_impl": 0.48,
    "impls_with_test": 0.71
  }
}
```

**Response 200 (empty graph)**
```json
{
  "total_nodes": 0,
  "total_edges": 0,
  "nodes_by_type": {},
  "edges_by_type": {},
  "lifecycle_distribution": {},
  "graph_density": 0.0,
  "connected_components": 0,
  "average_degree": 0.0,
  "last_edge_created_at": null,
  "coverage_pct": { "ideas_with_spec": 0.0, "specs_with_impl": 0.0, "impls_with_test": 0.0 }
}
```

This endpoint answers the open question "how can we show whether the graph is working and make that proof clearer over time?" — it exposes graph health as a single queryable API response, suitable for a dashboard panel, CI check, and scheduled alert.

#### `POST /api/graph/nodes` and `POST /api/graph/edges` *(extended from Spec 166)*

Both endpoints now enforce `node_type` and `edge_type` vocabularies, returning HTTP 422 with a descriptive message on violation. Self-loop edges are rejected. Lifecycle defaults are applied by node type when `lifecycle_state` is absent from payload.

**Response 422 — invalid node_type**
```json
{ "detail": "node_type 'widget' is not a recognized node type. See /api/graph/node-types for valid values." }
```

**Response 422 — invalid edge_type**
```json
{ "detail": "edge_type 'causes' is not a recognized edge type. Valid types: inspires, depends-on, implements, contradicts, extends, analogous-to, parent-of." }
```

**Response 422 — self-loop**
```json
{ "detail": "Self-loop edges are not allowed: from_node_id and to_node_id must be different." }
```

---

## Data Model Changes

### `graph_nodes` — additions to Spec 166

```sql
-- Enforce node_type as a constrained set (NOT VALID avoids table lock)
ALTER TABLE graph_nodes
  ADD CONSTRAINT chk_node_type
  CHECK (node_type IN (
    'idea', 'concept', 'spec', 'implementation', 'service',
    'contributor', 'domain', 'pipeline-run', 'event', 'artifact'
  ))
  NOT VALID;

-- Validate after backfill (in separate transaction)
ALTER TABLE graph_nodes VALIDATE CONSTRAINT chk_node_type;

-- Lifecycle state index for fast filtering
CREATE INDEX idx_graph_nodes_lifecycle
  ON graph_nodes ((payload->>'lifecycle_state'));
```

### `graph_edges` — additions to Spec 166

```sql
-- Enforce edge_type as a constrained set (NOT VALID avoids table lock)
ALTER TABLE graph_edges
  ADD CONSTRAINT chk_edge_type
  CHECK (edge_type IN (
    'inspires', 'depends-on', 'implements', 'contradicts',
    'extends', 'analogous-to', 'parent-of'
  ))
  NOT VALID;

-- Prevent self-loops
ALTER TABLE graph_edges
  ADD CONSTRAINT chk_no_self_loop
  CHECK (from_node_id != to_node_id);
```

### `node_type_registry` table *(new)*

```sql
CREATE TABLE node_type_registry (
  type_name         VARCHAR(64) PRIMARY KEY,
  description       TEXT NOT NULL,
  lifecycle_default VARCHAR(16) NOT NULL DEFAULT 'gas',
  payload_schema    JSONB NOT NULL DEFAULT '{}',
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

Seeded via migration with the 10 node types.

### `edge_type_registry` table *(new)*

```sql
CREATE TABLE edge_type_registry (
  type_name    VARCHAR(64) PRIMARY KEY,
  description  TEXT NOT NULL,
  is_symmetric BOOLEAN NOT NULL DEFAULT FALSE,
  example_text TEXT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

Seeded via migration with the 7 edge types.

---

## Task Card

```yaml
goal: >
  Implement the semantic layer on top of graph_nodes/graph_edges (Spec 166):
  enforce typed node/edge vocabulary, Ice/Water/Gas lifecycle states,
  registry endpoints, and a /api/graph/proof health endpoint that proves
  the fractal graph is being used in production.
files_allowed:
  - api/alembic/versions/xxxx_add_typed_node_edge_constraints.py
  - api/app/models/graph.py
  - api/app/services/graph_service.py
  - api/app/routers/graph.py
  - api/config/node_type_registry.json
  - api/config/edge_type_registry.json
  - api/tests/test_typed_node_edge_primitives.py
done_when:
  - alembic upgrade head applies NOT VALID CHECKs on node_type and edge_type
  - POST /api/graph/nodes with invalid node_type returns 422 with message listing valid types
  - POST /api/graph/edges with invalid edge_type returns 422 with message listing valid types
  - POST /api/graph/edges with from_node_id == to_node_id returns 422
  - GET /api/graph/node-types returns list of exactly 10 types
  - GET /api/graph/edge-types returns list of exactly 7 types
  - GET /api/graph/proof returns 200 with total_nodes, edges_by_type, lifecycle_distribution, coverage_pct
  - GET /api/graph/proof returns 200 with empty graph (no 500 on zero counts)
  - pytest api/tests/test_typed_node_edge_primitives.py passes 0 failed
commands:
  - cd api && alembic upgrade head
  - cd api && .venv/bin/pytest api/tests/test_typed_node_edge_primitives.py -v --tb=short
  - cd api && .venv/bin/ruff check app/models/graph.py app/services/graph_service.py app/routers/graph.py
  - curl -s https://api.coherencycoin.com/api/graph/proof | grep total_nodes
constraints:
  - Do NOT modify Spec 166's existing tables — additive constraints only (NOT VALID first)
  - Do NOT remove or rename existing endpoints from Spec 166
  - All new endpoints must return Pydantic response models (no raw dict)
  - CHECK constraints must use NOT VALID + VALIDATE CONSTRAINT pattern to avoid table lock
  - Node type and edge type vocabularies are closed — extension requires migration + registry update
```

---

## Proof Over Time: Observability Strategy

The open question "How can we show whether this is working and make that proof clearer over time?" is answered here.

### Immediate proof (Day 1 after deploy)

The `GET /api/graph/proof` endpoint provides a single-call health check. After deploy, run:

```bash
curl -sf https://api.coherencycoin.com/api/graph/proof
```

Initially, most values will be 0 or low — that **is the baseline**. The graph is working when these numbers grow.

### Trend proof (Day 7+)

Track `GET /api/graph/proof` as a time series in the pipeline metrics store. Key signals:

| Metric | Working signal | Concern signal |
|---|---|---|
| `coverage_pct.ideas_with_spec` | Growing toward 0.80 | Stagnant below 0.30 |
| `coverage_pct.specs_with_impl` | Growing toward 0.70 | Stagnant below 0.20 |
| `lifecycle_distribution.water / total_nodes` | > 0.40 (active system) | < 0.10 (frozen system) |
| `edges_by_type.inspires` | Growing (ideas connecting) | Zero (graph is unused) |
| `connected_components` | Decreasing toward 1 | Increasing (fragmentation) |

### Structural proof (Day 30+)

The strongest proof that the fractal works: run a depth-2 traversal from a known root node and verify that the path through `parent-of` → `inspires` → `implements` chains produces a coherent value-lineage tree. The `GET /api/graph/nodes/{id}/neighbors?depth=2` endpoint enables this.

A CI check (recommended as follow-up) could assert:
- `coverage_pct.ideas_with_spec >= 0.50` — fail the build if spec coverage drops
- `connected_components <= 5` — fail if graph fragments into isolated islands
- `lifecycle_distribution.gas / total_nodes <= 0.70` — fail if too much stays in ideation

### Displaying proof to humans

The `GET /api/graph/proof` response is designed for dashboard consumption. The `/api/graph/proof` URL is the authoritative source until a dedicated dashboard panel exists.

---

## Files to Create or Modify

- `api/alembic/versions/xxxx_add_typed_node_edge_constraints.py` — Migration: NOT VALID CHECK constraints on node_type and edge_type, node_type_registry and edge_type_registry tables, lifecycle state index
- `api/app/models/graph.py` — Add `NodeType`, `EdgeType`, `LifecycleState` enums; `NodeTypeEntry`, `EdgeTypeEntry` Pydantic models for registry responses; `GraphProofResponse` model
- `api/app/services/graph_service.py` — Validate node_type, edge_type, lifecycle_state on write; apply lifecycle defaults by node type; prevent self-loops; implement proof aggregation query
- `api/app/routers/graph.py` — Add `GET /api/graph/node-types`, `GET /api/graph/edge-types`, `GET /api/graph/proof`; extend neighbors with lifecycle_state and rel_type filters
- `api/config/node_type_registry.json` — JSON seed for 10 node types with lifecycle_default and description
- `api/config/edge_type_registry.json` — JSON seed for 7 edge types with is_symmetric flag and description
- `api/tests/test_typed_node_edge_primitives.py` — pytest tests for all constraints, registry endpoints, lifecycle defaults, proof endpoint, and error handling

---

## Acceptance Criteria

All acceptance criteria map 1:1 to tests in `api/tests/test_typed_node_edge_primitives.py`:

- `test_valid_node_type_accepted` — POST with `node_type: "idea"` returns 200
- `test_invalid_node_type_rejected` — POST with `node_type: "widget"` returns 422 with message naming the invalid type
- `test_valid_edge_type_accepted` — POST edge with `edge_type: "extends"` returns 200
- `test_invalid_edge_type_rejected` — POST edge with `edge_type: "causes"` returns 422
- `test_self_loop_rejected` — POST edge where `from_node_id == to_node_id` returns 422
- `test_lifecycle_state_gas_default_for_idea` — POST idea node without `lifecycle_state` in payload; GET returns `gas`
- `test_lifecycle_state_water_default_for_contributor` — POST contributor node; GET returns `water`
- `test_lifecycle_filter_on_neighbors` — GET neighbors with `?lifecycle_state=ice` returns only ice nodes
- `test_get_node_types_registry` — GET `/api/graph/node-types` returns list of 10 types with `description` and `lifecycle_default`
- `test_get_edge_types_registry` — GET `/api/graph/edge-types` returns list of 7 types with `description` and `is_symmetric`
- `test_get_proof_endpoint` — GET `/api/graph/proof` returns object with `total_nodes`, `edges_by_type`, `lifecycle_distribution`
- `test_proof_endpoint_empty_graph` — GET `/api/graph/proof` returns 200 with zero counts when no nodes exist
- `test_contradicts_symmetric_both_directions` — create A→B edge of type `contradicts`; neighbors of B shows A as incoming
- `test_full_lifecycle_transition` — create idea in gas, update payload lifecycle_state to ice, GET shows ice; update to water, GET shows water

---

## Verification

Run to confirm the feature is deployed and working:

```bash
API=https://api.coherencycoin.com
curl -sf $API/api/graph/node-types | grep -o '"type"' | wc -l
curl -sf $API/api/graph/edge-types | grep -o '"type"' | wc -l
curl -sf $API/api/graph/proof
pytest api/tests/test_typed_node_edge_primitives.py -v --tb=short
```

These scenarios are designed to be run against the production API after deployment. The reviewer will run them verbatim.

### Scenario 1: Full create-read cycle with typed nodes and edges

**Setup**: No nodes for `ext-id: test-prim-a` or `test-prim-b` exist.

**Action**:
```bash
API=https://api.coherencycoin.com

# Create node A (idea, starts in gas by default)
NODE_A=$(curl -sf -X POST $API/api/graph/nodes \
  -H "Content-Type: application/json" \
  -d '{"node_type":"idea","external_id":"test-prim-a","payload":{"title":"Node A"}}' \
  | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)

# Create node B (spec, starts in ice by default)
NODE_B=$(curl -sf -X POST $API/api/graph/nodes \
  -H "Content-Type: application/json" \
  -d '{"node_type":"spec","external_id":"test-prim-b","payload":{"title":"Node B"}}' \
  | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)

# Create edge: A inspires B
curl -sf -X POST $API/api/graph/edges \
  -H "Content-Type: application/json" \
  -d "{\"edge_type\":\"inspires\",\"from_node_id\":\"$NODE_A\",\"to_node_id\":\"$NODE_B\",\"weight\":1.0}"

# Read neighbors of A
curl -sf $API/api/graph/nodes/$NODE_A/neighbors
```

**Expected result**:
- Node A created with `lifecycle_state: "gas"` (default for idea)
- Node B created with `lifecycle_state: "ice"` (default for spec)
- Edge created with `edge_type: "inspires"`
- Neighbors of A returns Node B with `edge_type: "inspires"`, `direction: "outgoing"`

**Edge case**:
```bash
# POST same node A again → upsert, not 409
curl -sf -X POST $API/api/graph/nodes \
  -d '{"node_type":"idea","external_id":"test-prim-a","payload":{"title":"Node A"}}' \
  -H "Content-Type: application/json" | grep -o '"id":"[^"]*"'
# Must return same UUID as first call
```

---

### Scenario 2: Invalid edge type and self-loop rejected with clear errors

**Setup**: Two nodes exist (reuse from Scenario 1).

**Action**:
```bash
# Invalid edge type
curl -sf -X POST $API/api/graph/edges \
  -H "Content-Type: application/json" \
  -d "{\"edge_type\":\"causes\",\"from_node_id\":\"$NODE_A\",\"to_node_id\":\"$NODE_B\"}"
```

**Expected result**: HTTP 422 with body containing `"causes"` in the detail message and listing the 7 valid edge types.

**Edge case — self-loop**:
```bash
curl -sf -X POST $API/api/graph/edges \
  -H "Content-Type: application/json" \
  -d "{\"edge_type\":\"extends\",\"from_node_id\":\"$NODE_A\",\"to_node_id\":\"$NODE_A\"}"
# Must return HTTP 422 with message about self-loops
```

---

### Scenario 3: Registry endpoints return complete, stable data

**Setup**: Migration has been applied and registry tables seeded.

**Action**:
```bash
# Node types count
curl -sf $API/api/graph/node-types | grep -o '"type":"[^"]*"' | wc -l
# Edge types count
curl -sf $API/api/graph/edge-types | grep -o '"type":"[^"]*"' | wc -l
```

**Expected result**:
- Node types endpoint returns exactly 10 entries
- Edge types endpoint returns exactly 7 entries
- Both include `description` and relevant metadata

**Edge case**:
```bash
# Both endpoints must return 200 when graph is empty
curl -o /dev/null -w "%{http_code}" $API/api/graph/node-types
# Must return 200
```

---

### Scenario 4: Graph proof endpoint shows live graph health

**Setup**: At least 1 node and 1 edge exist (from Scenarios 1–2).

**Action**:
```bash
curl -sf $API/api/graph/proof
```

**Expected result**: HTTP 200 with JSON containing all of:
- `total_nodes` (integer ≥ 1)
- `total_edges` (integer ≥ 1)
- `nodes_by_type` (object with at least one key from the valid types list)
- `edges_by_type` (object with at least one key)
- `lifecycle_distribution` (object with at least one key from `gas|ice|water`)
- `coverage_pct` (object with `ideas_with_spec`, `specs_with_impl`, `impls_with_test` as floats)

**Edge case — empty graph returns 200, not 500**:
```bash
curl -o /dev/null -w "%{http_code}" $API/api/graph/proof
# Must return 200 even with empty graph
```

---

### Scenario 5: Lifecycle state filter on neighbors

**Setup**: 3 nodes: A (idea/gas), B (spec/ice), C (implementation/water). Edges: A→inspires→B, A→inspires→C.

**Action**:
```bash
# Filter: only ice neighbors of A
curl -sf "$API/api/graph/nodes/$NODE_A/neighbors?lifecycle_state=ice"
```

**Expected result**: Returns only Node B in the neighbors list. Node C (water) is excluded.

**Edge case — unknown lifecycle state returns 422**:
```bash
curl -o /dev/null -w "%{http_code}" "$API/api/graph/nodes/$NODE_A/neighbors?lifecycle_state=plasma"
# Must return 422 (not 200 or 500)
```

---

## Risks and Assumptions

| Risk | Likelihood | Mitigation |
|---|---|---|
| PostgreSQL CHECK constraints block existing rows with old/unknown `node_type` values | High | Migration uses `NOT VALID` first, then `VALIDATE CONSTRAINT` in a separate transaction after backfill |
| Teams add custom edge types to the database directly, bypassing the registry | Medium | CI `rg` check scans for direct `INSERT INTO graph_edges` with literal type strings not in the registry list |
| `payload->>'lifecycle_state'` GIN index has high cardinality on large tables | Low | Only 3 values; btree index on `((payload->>'lifecycle_state'))` is more efficient for this case |
| `GET /api/graph/proof` becomes a slow query at 1M+ nodes | Low | Materialize counts via a background refresh job (every 5 min) into a `graph_stats` table |
| `analogous-to` and `contradicts` are symmetric but stored as directed edges | Medium | Document clearly in `edge_type_registry.is_symmetric`; neighbors endpoint returns both directions for symmetric types |

**Assumptions**:
- Spec 166 migration has been applied and `graph_nodes`/`graph_edges` tables exist
- PostgreSQL 14+ (supports `gen_random_uuid()`, expression indexes, partial indexes)
- `alembic upgrade head` is run before the new service layer is deployed
- `node_type_registry` and `edge_type_registry` tables are seeded in the same migration that creates them

---

## Known Gaps and Follow-up Tasks

- **Lifecycle transition enforcement**: The state machine rules (gas→ice only, ice→water or ice, water→gas or ice) are documented but not enforced server-side in this spec. A follow-up spec should add `PATCH /api/graph/nodes/{id}/lifecycle` with explicit transition validation.
- **Symmetric edge materialization**: `contradicts` and `analogous-to` are logically symmetric but stored as one directed edge. Querying both directions requires callers to use `direction=both`. A follow-up may add auto-materialization of reverse edges.
- **Backfill of existing nodes**: Existing `ideas` and `tasks` rows are not automatically added to `graph_nodes` in this migration. A follow-up backfill job should create node records for all existing ideas, specs, and contributors.
- **Proof endpoint caching**: At scale (>100K nodes), this endpoint needs a materialized view or background cache.
- **Neo4j sync**: Long-term, `graph_nodes` and `graph_edges` should sync to Neo4j for traversal queries at graph scale. PostgreSQL-only in this spec.

---

## Out of Scope

- Backfilling existing `ideas`/`tasks` into `graph_nodes` — additive migration only
- ML-based edge weight prediction — weights are explicit floats set by callers
- Real-time CDC/event streaming (Debezium, pg_notify) on node/edge changes
- Graph visualization UI — covered by Spec 163 (Resonance Navigation)
- Per-route authentication — handled at Traefik level
- Recursive traversal beyond depth-2
