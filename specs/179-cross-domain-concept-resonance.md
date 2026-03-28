# Spec 179: Cross-Domain Concept Resonance — Ideas Attract Related Ideas

**Spec ID**: `179-cross-domain-concept-resonance`
**Task ID**: `task_2f5155fa5cbcc4d0`
**Status**: Draft
**Priority**: High
**Author**: product-manager agent
**Date**: 2026-03-28
**Depends on**:
- Spec 008 (Graph Foundation) — graph nodes and edges layer
- Spec 169 (Fractal Node/Edge Primitives) — canonical edge types including `analogous-to`
- Spec 173 (Concept Resonance Kernel) — harmonic similarity kernel (CRK + OT-φ)
- Spec 163 (Resonance Navigation) — discovery navigation layer

---

## Summary

When a biology concept (**symbiosis**) resonates with a software concept (**microservices**), the system should surface the connection — not by matching keywords, but by detecting *structural similarity in the graph*: two nodes that solve analogous problems, attract analogous edges, and carry analogous roles in their respective domains.

This spec defines **Cross-Domain Concept Resonance (CDCR)**: a pipeline that continuously scans the idea and concept graph, identifies structurally similar node pairs from different domains, scores them, persists the connections as weighted `analogous-to` edges, and exposes a set of API endpoints and a proof endpoint so observers can verify the ontology is growing organically.

Resonance is not curation. No human decides what is analogous. The graph discovers its own bridges.

---

## Problem Statement

### The curation trap

Manually curated ontologies decay. They reflect the biases of whoever built them, grow slowly, and miss the lateral connections that generate real insight. An intelligence platform that only knows what it was told is not intelligent — it is a taxonomy.

The Coherence Network already has the raw materials: thousands of ideas across domains, a rich graph of typed edges, a harmonic similarity kernel (CRK), and a canonical `analogous-to` edge type designed exactly for cross-domain bridges. What it lacks is the **pipeline that finds, scores, and persists those bridges automatically**.

### Why structural similarity, not keywords

Keyword matching finds `symbiosis` → `symbiotic relationship` → `mutualism`. That is retrieval, not resonance.

Structural matching finds `symbiosis` (biology) ↔ `microservices` (software) because:
- Both have a "small autonomous units that cooperate" sub-pattern
- Both attract similar edge types: `EXTENDS` (evolution, versioning), `DEPENDS_ON` (nutrient exchange, API calls), `CONTRADICTS` (parasitism, monolith)
- Both sit at the intersection of `DOMAIN:biology|software` and `AXIS:cooperation|modularity`
- Both solve the same structural problem: *coordination without central control*

The resonance score quantifies how well the two node neighborhoods match when you strip domain labels and look only at edge topology and axis proximity.

### How the ontology grows

Every detected resonance that crosses the threshold is written back as an `analogous-to` edge. That edge becomes a new path. Future traversals discover it. Future ideas that connect to either anchor node now inherit a bridge to the other domain. The graph learns without being taught.

---

## Goals

1. **Detect** cross-domain resonant pairs using structural graph fingerprints, not keyword overlap.
2. **Score** each candidate pair with a combined metric: structural fingerprint similarity × CRK harmonic score × domain-distance bonus.
3. **Persist** resonances above threshold as `analogous-to` edges in the graph, tagged with `source: cdcr` and a `resonance_score`.
4. **Surface** resonances via `GET /api/resonance/cross-domain` — paginated, filterable by domain, score threshold, and time.
5. **Trigger** on-demand scans via `POST /api/resonance/cross-domain/scan` with optional seed node.
6. **Prove** the system is working via `GET /api/resonance/cross-domain/proof` — shows discovery rate, domain coverage, and top resonances over time.
7. **Visualize** on `/resonance/cross-domain` web page: a live view showing active resonances, trending bridges, and an organic growth timeline.
8. **Emit** `resonance_discovered` events for every new `analogous-to` edge so value lineage can track which resonances generated downstream investment or contribution.

---

## Non-Goals

- Real-time streaming resonance detection (batch/scheduled is sufficient for now).
- User-configurable domain taxonomies (Phase 2; domains are inferred from node properties/graph position).
- ML embeddings or neural similarity (the CRK + structural fingerprint approach is the foundation; embeddings are Phase 2 layered on top).
- Cross-instance federation resonance (Phase 2).
- Resonance decay / edge expiry (Phase 2).

---

## Architecture

### Structural Fingerprint

Each node `n` is represented by a **structural fingerprint** `F(n)`:

```
F(n) = {
    degree_in:            int,
    degree_out:           int,
    edge_type_histogram:  dict[EdgeType, int],   # edge types on all incident edges
    axis_ids:             frozenset[str],         # axes this node is tagged with
    domain:               str | None,             # inferred from DOMAIN edges or properties
    depth_2_edge_types:   dict[EdgeType, int],    # edge types reachable in 2 hops
    phase:                str,                    # water|ice|gas from node.phase
}
```

### Resonance Score Formula

For two nodes `a` and `b`:

```
structural_sim(a, b) = cosine_similarity(
    edge_type_vector(a) + axis_vector(a),
    edge_type_vector(b) + axis_vector(b)
)

domain_distance_bonus(a, b) = 1.0 if domain(a) != domain(b) else 0.0
  # Cross-domain pairs are rewarded; same-domain pairs can still qualify but no bonus

depth2_sim(a, b) = cosine_similarity(
    depth_2_edge_type_vector(a),
    depth_2_edge_type_vector(b)
)

crk_score(a, b) = CRK kernel score from concept_resonance_kernel.py
                  (0.0 if either node has no harmonic components; falls back to 0.5 default)

resonance_score(a, b) = (
    0.40 * structural_sim(a, b)
  + 0.25 * depth2_sim(a, b)
  + 0.20 * crk_score(a, b)
  + 0.15 * domain_distance_bonus(a, b)
)
```

Threshold: `resonance_score >= 0.65` -> create `analogous-to` edge.
Existing `analogous-to` edges are updated (score refreshed) if they exceed threshold on rescan.

### Domain Inference

A node's domain is determined by (in priority order):
1. `properties["domain"]` field set explicitly
2. Nearest `DOMAIN`-type node reachable in 2 hops via any edge
3. `"unknown"` if neither applies

Cross-domain requires `domain(a) != domain(b)` and neither is `"unknown"`.

### Scan Modes

| Mode | Trigger | Scope |
|------|---------|-------|
| `full` | Scheduled (nightly) | All idea + concept nodes |
| `seed` | `POST /api/resonance/cross-domain/scan` with `seed_node_id` | Seed node's 3-hop neighborhood vs. rest of graph |
| `incremental` | After new node/edge created | New node vs. recent 1000 nodes |

Incremental scans run as a post-write hook in the graph service. They are fire-and-forget (async task queue or background thread). They must not block the write response.

---

## Data Model

### New database table: `cross_domain_resonances`

```yaml
CrossDomainResonance:
  id:              string (UUID)
  node_a_id:       string  # FK -> graph nodes
  node_b_id:       string  # FK -> graph nodes
  domain_a:        string
  domain_b:        string
  resonance_score: float   # 0.0-1.0
  structural_sim:  float
  depth2_sim:      float
  crk_score:       float
  edge_id:         string | null  # FK -> graph edges (the analogous-to edge, once created)
  discovered_at:   datetime (UTC)
  last_confirmed:  datetime (UTC)
  scan_mode:       string  # "full" | "seed" | "incremental"
  source:          string  # "cdcr" always
```

### Graph edge annotation

All `analogous-to` edges created by CDCR carry these properties:
```json
{
  "source": "cdcr",
  "resonance_score": 0.78,
  "domain_a": "biology",
  "domain_b": "software",
  "discovered_at": "2026-03-28T12:00:00Z"
}
```

---

## API Contract

### `GET /api/resonance/cross-domain`

List discovered cross-domain resonances, newest first.

**Query params**
- `domain_a`: filter by domain (string, optional)
- `domain_b`: filter by domain (string, optional)
- `min_score`: float 0.0-1.0 (default: 0.65)
- `limit`: int 1-200 (default: 50)
- `offset`: int >= 0 (default: 0)

**Response 200**
```json
{
  "items": [
    {
      "id": "uuid",
      "node_a": { "id": "symbiosis", "name": "Symbiosis", "domain": "biology" },
      "node_b": { "id": "microservices", "name": "Microservices", "domain": "software" },
      "resonance_score": 0.81,
      "structural_sim": 0.74,
      "depth2_sim": 0.69,
      "crk_score": 0.88,
      "edge_id": "edge-uuid",
      "discovered_at": "2026-03-28T10:00:00Z"
    }
  ],
  "total": 42,
  "limit": 50,
  "offset": 0
}
```

---

### `POST /api/resonance/cross-domain/scan`

Trigger an on-demand resonance scan.

**Request body**
```json
{
  "seed_node_id": "symbiosis",
  "mode": "seed"
}
```

**Response 202**
```json
{
  "scan_id": "uuid",
  "mode": "seed",
  "seed_node_id": "symbiosis",
  "status": "queued",
  "message": "Scan queued. Results available at GET /api/resonance/cross-domain/scans/{scan_id}"
}
```

**Response 400**: `{ "detail": "seed_node_id required for mode=seed" }`
**Response 404**: `{ "detail": "Node 'xyz' not found" }`
**Response 429**: `{ "detail": "Scan already in progress" }` (only one scan runs at a time)

---

### `GET /api/resonance/cross-domain/scans/{scan_id}`

Check scan status.

**Response 200**
```json
{
  "scan_id": "uuid",
  "status": "complete",
  "mode": "seed",
  "nodes_evaluated": 1204,
  "pairs_compared": 18432,
  "resonances_found": 7,
  "resonances_created": 5,
  "resonances_updated": 2,
  "duration_ms": 4230,
  "started_at": "2026-03-28T10:00:00Z",
  "completed_at": "2026-03-28T10:00:04Z"
}
```

---

### `GET /api/resonance/cross-domain/proof`

Aggregate evidence that the resonance engine is working and the ontology is growing organically.

**Response 200**
```json
{
  "total_resonances": 142,
  "total_analogous_to_edges": 89,
  "analogous_to_edges_from_cdcr": 89,
  "domain_pairs_covered": [
    { "domain_a": "biology", "domain_b": "software", "count": 14 },
    { "domain_a": "physics", "domain_b": "economics", "count": 9 }
  ],
  "discovery_timeline": [
    { "date": "2026-03-28", "new_resonances": 12 },
    { "date": "2026-03-27", "new_resonances": 8 }
  ],
  "top_resonances": [
    {
      "node_a": "symbiosis",
      "node_b": "microservices",
      "score": 0.91,
      "domain_pair": "biology <-> software"
    }
  ],
  "avg_score": 0.74,
  "nodes_with_cross_domain_bridge": 63,
  "organic_growth_rate": 4.2,
  "proof_status": "active"
}
```

`proof_status` is `"active"` if `organic_growth_rate > 0`, otherwise `"stale"`.

---

### `GET /api/resonance/cross-domain/{id}`

Get a single resonance record by ID.

**Response 200**: Full `CrossDomainResonance` object.
**Response 404**: `{ "detail": "Resonance not found" }`

---

### `DELETE /api/resonance/cross-domain/{id}`

Remove a false-positive resonance (human override). Also removes the corresponding `analogous-to` edge.

**Response 204**: No content.
**Response 404**: `{ "detail": "Resonance not found" }`

---

## Web Page: `/resonance/cross-domain`

A live view of the resonance discovery engine. Sections:

1. **Proof panel** — data from `GET /api/resonance/cross-domain/proof`: total resonances, growth rate, domain pairs, `proof_status` badge (green = active / amber = stale).
2. **Active resonances feed** — cards showing the top 10 highest-scoring active resonances, each with both node names, domains, score bar, and a "view in graph" link.
3. **Domain bridge heatmap** — grid of domain pairs with cell color intensity = count of resonances found between that pair.
4. **Growth timeline** — area chart of resonances discovered per day over 30 days.
5. **Scan trigger** — a "Run Scan" button that calls `POST /api/resonance/cross-domain/scan` with `mode: "full"` and shows live scan progress.

---

## Files to Create / Modify

### New files

| File | Purpose |
|------|---------|
| `api/app/services/cross_domain_resonance_service.py` | Core CDCR logic: fingerprinting, scoring, scan orchestration |
| `api/app/routers/cross_domain_resonance.py` | FastAPI router for all `/api/resonance/cross-domain` endpoints |
| `api/tests/test_cross_domain_resonance.py` | pytest test suite covering all endpoints and core scoring |
| `web/app/resonance/cross-domain/page.tsx` | Web page for visualizing resonances |

### Modified files

| File | Change |
|------|--------|
| `api/app/main.py` | Register `cross_domain_resonance` router under `/api/resonance` prefix |
| `api/app/services/graph_service.py` | Add `create_node` post-write hook to trigger incremental scan |

---

## Task Card

```yaml
goal: >
  Implement cross-domain concept resonance: detect, score, persist, and expose
  structurally similar node pairs from different domains as analogous-to edges,
  proving the ontology grows organically without manual curation.

files_allowed:
  - api/app/services/cross_domain_resonance_service.py
  - api/app/routers/cross_domain_resonance.py
  - api/app/models/cross_domain_resonance.py
  - api/app/main.py
  - api/tests/test_cross_domain_resonance.py
  - web/app/resonance/cross-domain/page.tsx
  - web/components/domain-bridge-heatmap.tsx

done_when:
  - GET /api/resonance/cross-domain returns 200 with paginated resonance list
  - POST /api/resonance/cross-domain/scan returns 202 and completes asynchronously
  - GET /api/resonance/cross-domain/proof returns proof_status "active" after any scan finds >=1 resonance
  - analogous-to edges created by CDCR carry source="cdcr" in properties
  - All tests in api/tests/test_cross_domain_resonance.py pass
  - /resonance/cross-domain page renders proof panel and active resonances feed

commands:
  - pytest api/tests/test_cross_domain_resonance.py -v
  - curl -s $API/api/resonance/cross-domain/proof | jq .proof_status
  - curl -s -X POST $API/api/resonance/cross-domain/scan -H "Content-Type: application/json" -d '{"mode":"full"}'

constraints:
  - Do not modify tests to force passing behavior.
  - Resonance score must use the formula in this spec exactly; do not substitute a pure keyword scorer.
  - Incremental scans must not block graph write responses (fire-and-forget only).
  - No external ML dependencies; CRK kernel is the deepest allowed dependency.
  - Keyword matching must NOT be used as a substitute for structural fingerprint comparison.
```

---

## Verification Scenarios

### Scenario 1 — Cross-domain pair is detected and persisted as edge

**Setup**: Graph contains two nodes with no existing `analogous-to` edge between them:
```bash
curl -s -X POST $API/api/graph/nodes -H "Content-Type: application/json" \
  -d '{"id":"symbiosis","type":"concept","name":"Symbiosis","description":"Cooperative relationship between distinct species","properties":{"domain":"biology"}}'
curl -s -X POST $API/api/graph/nodes -H "Content-Type: application/json" \
  -d '{"id":"microservices","type":"concept","name":"Microservices","description":"Small autonomous services cooperating over network APIs","properties":{"domain":"software"}}'
# Add matching edge-type structure to both nodes (depends-on, extends, contradicts edges)
```

**Action**:
```bash
SCAN=$(curl -s -X POST $API/api/resonance/cross-domain/scan \
  -H "Content-Type: application/json" \
  -d '{"seed_node_id":"symbiosis","mode":"seed"}')
SCAN_ID=$(echo $SCAN | jq -r '.scan_id')
# Poll until complete:
curl -s "$API/api/resonance/cross-domain/scans/$SCAN_ID" | jq .status
```

**Expected result**:
- Scan returns `"status": "complete"`, `resonances_found >= 1`, `resonances_created >= 1`
- `GET /api/resonance/cross-domain?domain_a=biology&domain_b=software` returns item with `resonance_score >= 0.65`
- `GET /api/graph/nodes/symbiosis/edges?type=analogous-to` returns edge with `properties.source="cdcr"`

**Edge case — same-domain pair**:
- Create two nodes both with `domain: "software"` and identical edge structure, run scan
- No `analogous-to` edge with `source="cdcr"` created between them (domain bonus absent, score stays below threshold)

---

### Scenario 2 — Proof endpoint shows organic growth

**Setup**: At least 2 successful scans have run, each finding >= 1 new cross-domain resonance.

**Action**:
```bash
curl -s $API/api/resonance/cross-domain/proof | jq '{total: .total_resonances, growth: .organic_growth_rate, status: .proof_status}'
```

**Expected result**:
```json
{
  "total_resonances": <number >= 2>,
  "organic_growth_rate": <number > 0.0>,
  "proof_status": "active"
}
```

**Edge case — empty graph**:
```bash
# On fresh DB with no nodes:
curl -s $API/api/resonance/cross-domain/proof
# -> HTTP 200, {"total_resonances": 0, "proof_status": "stale", ...} NOT a 500 error
```

---

### Scenario 3 — Full CRUD cycle for resonance records

**Setup**: At least one resonance exists (from Scenario 1 or prior scans).

**Action**:
```bash
RESONANCE_ID=$(curl -s "$API/api/resonance/cross-domain?limit=1" | jq -r '.items[0].id')
EDGE_ID=$(curl -s "$API/api/resonance/cross-domain?limit=1" | jq -r '.items[0].edge_id')

# Read
curl -s "$API/api/resonance/cross-domain/$RESONANCE_ID" | jq '{score: .resonance_score, domains: [.domain_a, .domain_b]}'
# -> {"score": 0.81, "domains": ["biology", "software"]}

# Delete
curl -s -X DELETE "$API/api/resonance/cross-domain/$RESONANCE_ID"
# -> HTTP 204

# Verify gone
curl -s "$API/api/resonance/cross-domain/$RESONANCE_ID"
# -> HTTP 404

# Verify edge also removed
curl -s "$API/api/graph/edges/$EDGE_ID"
# -> HTTP 404
```

**Edge case — delete non-existent**:
```bash
curl -s -X DELETE "$API/api/resonance/cross-domain/does-not-exist"
# -> HTTP 404, {"detail": "Resonance not found"}
```

---

### Scenario 4 — Incremental scan triggers on new node creation

**Setup**: Graph has existing nodes that a new concept node would resonate with if compared.

**Action**:
```bash
curl -s -X POST "$API/api/graph/nodes" \
  -H "Content-Type: application/json" \
  -d '{"id":"emergent-behavior","type":"concept","name":"Emergent Behavior","properties":{"domain":"complexity-science"}}'
sleep 3  # Allow async incremental scan to complete
BEFORE=<count before node creation>
AFTER=$(curl -s "$API/api/resonance/cross-domain?min_score=0.65" | jq '.total')
echo "New resonances: $((AFTER - BEFORE))"
```

**Expected result**: Count increases by >= 1 without a manual scan trigger. New resonance appears in the feed.

**Edge case — duplicate scan suppression**:
```bash
curl -s -X POST $API/api/resonance/cross-domain/scan -d '{"mode":"full"}' -H "Content-Type: application/json"
# -> HTTP 202
curl -s -X POST $API/api/resonance/cross-domain/scan -d '{"mode":"full"}' -H "Content-Type: application/json"
# -> HTTP 429, {"detail": "Scan already in progress"}
```

---

### Scenario 5 — Score filtering, pagination, and validation

**Setup**: Multiple resonances exist with varying scores.

**Action**:
```bash
# Filtering by min_score
curl -s "$API/api/resonance/cross-domain?min_score=0.85&limit=10" | jq '[.items[].resonance_score] | min'
# -> all values >= 0.85

# Pagination
PAGE0=$(curl -s "$API/api/resonance/cross-domain?limit=2&offset=0" | jq -r '.items[0].id')
PAGE1=$(curl -s "$API/api/resonance/cross-domain?limit=2&offset=2" | jq -r '.items[0].id')
# -> PAGE0 != PAGE1

# Invalid score triggers 422
curl -s "$API/api/resonance/cross-domain?min_score=1.5"
# -> HTTP 422 (unprocessable entity, not 500)
```

---

## Risks and Assumptions

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Full scan too slow on large graphs | Medium | Incremental + seed modes are primary; full scan is nightly only. Default cap: 10k nodes. |
| Structural fingerprints too coarse (false positives) | Medium | Require both 1-hop AND 2-hop similarity above sub-threshold; tune empirically during impl. |
| CRK has no harmonic data for most nodes | High | CRK falls back to 0.5 (neutral) when no components exist; structural similarity carries the weight. |
| Domain inference fails (most nodes have no domain) | Medium | Require explicit `domain` property; unknown-domain nodes are still compared but receive no bonus. |
| Incremental scans create write storms on bulk imports | Low | Debounce: one incremental scan per 30-second window per node neighborhood. |

---

## Known Gaps and Follow-up Tasks

1. **Domain auto-discovery** — currently requires `properties["domain"]` to be set explicitly. A follow-up spec should infer domain from graph neighborhood clustering.
2. **Resonance decay** — edges more than 90 days old without confirmation should be re-scored. Phase 2.
3. **Cross-instance resonance** — comparing nodes across multiple Coherence Network instances. Requires federation layer.
4. **ML augmentation** — add sentence-embedding similarity as additional score component. Phase 2.
5. **User feedback loop** — allow contributors to confirm or reject a resonance, feeding signal back to tune the threshold. Phase 2.

---

## Verification

### Definition of Done

- [ ] `GET /api/resonance/cross-domain` returns paginated resonance list (200)
- [ ] `POST /api/resonance/cross-domain/scan` queues and completes a scan (202 -> status -> complete)
- [ ] `GET /api/resonance/cross-domain/proof` returns `proof_status: "active"` after scan finds >= 1 resonance
- [ ] `DELETE /api/resonance/cross-domain/{id}` removes record and corresponding graph edge (204/404)
- [ ] Scan-created `analogous-to` edges carry `source: "cdcr"` and `resonance_score` in properties
- [ ] Keyword-only similarity is not used (verified by unit test with structurally-similar but lexically-unrelated nodes)
- [ ] All tests in `api/tests/test_cross_domain_resonance.py` pass
- [ ] `GET /api/resonance/cross-domain/proof` returns 200 (not 500) on empty graph
- [ ] `/resonance/cross-domain` web page loads with proof panel and feeds

---

*This spec is the contract. The reviewer will run Scenarios 1-5 against production. If any scenario fails, the implementation is not done.*
