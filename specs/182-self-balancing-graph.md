# Spec 182: Self-Balancing Graph — Anti-Collapse, Organic Expansion, Entropy Management

**Spec ID**: 182-self-balancing-graph
**Idea ID**: self-balancing-graph
**Task ID**: task_65a2f746bf79ecaa
**Status**: draft
**Priority**: high
**Author**: product-manager agent
**Date**: 2026-03-28
**Depends on**: Spec 172 (Fractal Self-Balance), Spec 169 (Fractal Node + Edge Primitives), Spec 166 (Universal Node + Edge Layer)

---

## Purpose

Spec 172 defined a read-only health snapshot with basic anti-collapse signals. This spec extends and deepens that foundation by answering three open questions left in the original design:

1. **What metrics specifically signal a healthy vs unhealthy graph shape?** — Define numeric thresholds, named failure modes, and severity tiers.
2. **How do we prevent the balance algorithm from suppressing genuine convergence?** — Introduce a convergence-guard mechanism that lets intentionally dense clusters be exempted from split signals.
3. **How can we prove the system is working and make that proof clearer over time?** — Add a snapshot history store and a `/api/graph/health/timeline` endpoint so balance improvements are measurable across snapshots.

The system monitors its own shape. Balance is not static — it is dynamic equilibrium that adapts as the network grows.

---

## Summary

This spec adds three layers on top of Spec 172's read-only MVP:

| Layer | What it adds |
|-------|-------------|
| **Metric definitions** | Concrete formulas and thresholds for all six health dimensions |
| **Convergence guard** | `POST /api/graph/health/convergence-guard` — exempts intentional hubs from split signals |
| **History + timeline** | Snapshots are persisted; `GET /api/graph/health/timeline` shows balance trajectory |

The system remains advisory: no endpoint in this spec mutates the concept graph. Automatic split/merge actions are explicitly deferred to a later spec.

---

## Requirements

- [ ] `GET /api/graph/health` returns all six metrics: `balance_score`, `entropy_score`, `concentration_ratio`, `depth_diversity_score`, `orphan_pressure`, `gravity_well_count`
- [ ] `POST /api/graph/health/compute` recomputes and **persists** the snapshot; empty graph returns a zero-baseline, not 500
- [ ] A concept whose direct child count >= `SPLIT_THRESHOLD` (default 8) and is **not** in the convergence-guard list appears in `gravity_wells` with `severity` set to `warning` (8–14 children) or `critical` (15+ children)
- [ ] A disconnected component with 2–5 nodes appears in `orphan_clusters` and emits a `merge_signal`
- [ ] When the top-3 concepts hold >= 80% of energy, `surface_candidates` lists under-linked, non-orphan, non-guarded concepts ranked by `free_energy_score` descending
- [ ] `POST /api/graph/health/convergence-guard` accepts `{"concept_id": "...", "reason": "..."}` and adds the concept to the guard list; guarded concepts are excluded from `gravity_wells` in all future snapshots
- [ ] `DELETE /api/graph/health/convergence-guard/{concept_id}` removes a concept from the guard list and returns 204
- [ ] `GET /api/graph/health/convergence-guard` lists all currently guarded concepts with reasons and `added_at` timestamps
- [ ] `GET /api/graph/health/timeline?limit=20` returns an ordered list of historical snapshots (newest first) with `balance_score`, `entropy_score`, `concentration_ratio`, `gravity_well_count`, `orphan_cluster_count`, and `computed_at` for each
- [ ] `balance_score` is always bounded 0.0–1.0; a fully connected, evenly distributed, low-orphan graph scores >= 0.85; a hub-dominated graph scores <= 0.40
- [ ] All metric thresholds (`SPLIT_THRESHOLD`, `ORPHAN_CLUSTER_MAX_SIZE`, `CONCENTRATION_CEILING`) are configurable via environment variables with documented defaults

---

## Metric Definitions

### 1. `entropy_score` — Energy Distribution Health

Measures how evenly "energy" (approximated by incoming edge count + idea `potential_value`) is distributed across all concepts.

```
H = -sum(p_i * log2(p_i))  for each concept i
entropy_score = H / log2(N)   # normalized 0..1; 1 = perfectly even
```

**Thresholds**
| Score | Label |
|-------|-------|
| >= 0.75 | healthy |
| 0.50–0.74 | degraded |
| < 0.50 | critical |

### 2. `concentration_ratio` — Top-3 Dominance

```
concentration_ratio = sum(energy[top_3]) / sum(energy[all])
```

**Thresholds**
| Ratio | Label |
|-------|-------|
| < 0.50 | healthy |
| 0.50–0.79 | elevated |
| >= 0.80 | critical — `surface_candidates` must be emitted |

### 3. `depth_diversity_score` — Branch Depth Spread

A graph where all nodes live at depth 1 (flat star) scores near 0; a graph with a varied depth distribution scores near 1.

```
depths = [depth(node) for all nodes]
depth_diversity_score = std_dev(depths) / max_depth  # normalized 0..1
```

### 4. `orphan_pressure` — Disconnection Load

```
orphan_pressure = num_orphan_nodes / total_nodes
```

**Thresholds**
| Pressure | Label |
|----------|-------|
| < 0.05 | healthy |
| 0.05–0.19 | elevated |
| >= 0.20 | critical |

### 5. `gravity_well_count` — Hub Overload

Count of concepts with child_count >= `SPLIT_THRESHOLD` that are **not** in the convergence-guard list.

### 6. `balance_score` — Composite Health

```
balance_score = 0.30 * entropy_score
              + 0.25 * (1 - concentration_ratio)
              + 0.20 * depth_diversity_score
              + 0.15 * (1 - orphan_pressure)
              + 0.10 * (1 - min(gravity_well_count / 5, 1.0))
```

All components are clamped to [0.0, 1.0] before weighting.

---

## Convergence Guard

The convergence guard answers the question: *how do we prevent balance algorithms from suppressing genuine convergence?*

Some hubs are intentional. A central `fractal-ontology-core` idea may legitimately have 20+ children — it is a real attractor, not a failure mode. The guard lets human reviewers or trusted agents exempt named concepts from split signals.

### Guard semantics

- Guarded concepts are **never** listed in `gravity_wells`, regardless of child count.
- Guarded concepts are **never** listed in `surface_candidates` (they are presumed active).
- The guard list is stored in a dedicated table or in-process store; it survives service restarts.
- Guard entries include a mandatory `reason` string to prevent silent exemptions.
- The guard list is visible via `GET /api/graph/health/convergence-guard` for full auditability.

### Guard abuse prevention

- A concept may only appear in the guard list once; duplicate `POST` returns 409.
- The `reason` field is required (min 10 chars) to prevent empty exemptions.
- Removing a guard entry (`DELETE`) causes the concept to re-appear in future health snapshots if it still exceeds `SPLIT_THRESHOLD`.

---

## Proving the System Is Working: Timeline and Observability

The open question "how can we show whether it is working yet?" is answered by the **snapshot history** mechanism.

### How it works

1. Every call to `POST /api/graph/health/compute` persists the snapshot to a `graph_health_snapshots` table with a `computed_at` timestamp.
2. `GET /api/graph/health/timeline` returns the last N snapshots (default 20, max 100), ordered newest-first.
3. A rising `balance_score` trend over time indicates the system is working. A flat or falling score signals that interventions (e.g., acting on surface candidates) are not happening.
4. The timeline can be compared visually in the web UI (`/graph/health`) as a sparkline chart.

### Proving it worked

For any given snapshot, the system can compare to the previous snapshot and compute a `delta_balance_score`. When `delta_balance_score > 0` and `concentration_ratio` fell, that is evidence that the graph grew more evenly.

---

## API Changes

### `GET /api/graph/health`

Returns the most recently computed snapshot. Returns the zero-baseline if no snapshot has been computed.

**Response 200**
```json
{
  "balance_score": 0.74,
  "entropy_score": 0.68,
  "concentration_ratio": 0.41,
  "depth_diversity_score": 0.55,
  "orphan_pressure": 0.08,
  "gravity_well_count": 1,
  "gravity_wells": [
    {
      "concept_id": "concept-0",
      "child_count": 12,
      "severity": "warning",
      "reason": "child_count exceeded SPLIT_THRESHOLD"
    }
  ],
  "orphan_clusters": [
    {
      "cluster_id": "cluster-1",
      "node_ids": ["iso-0", "iso-1"],
      "size": 2
    }
  ],
  "surface_candidates": [],
  "signals": [
    {
      "type": "split_signal",
      "severity": "warning",
      "concept_id": "concept-0",
      "cluster_id": null
    }
  ],
  "computed_at": "2026-03-28T18:00:00Z"
}
```

### `POST /api/graph/health/compute`

Forces recomputation and persists the snapshot.

**Response 200** — same schema as GET.

**Edge cases**
- Empty graph: all scores return documented neutral values (see thresholds); no 500.
- Malformed concept entries: skipped; computation continues.

### `POST /api/graph/health/convergence-guard`

Adds a concept to the guard list.

**Request**
```json
{ "concept_id": "fractal-ontology-core", "reason": "Intentional hub: this is the root attractor for all ontology concepts." }
```

**Response 201**
```json
{ "concept_id": "fractal-ontology-core", "reason": "...", "added_at": "2026-03-28T18:05:00Z" }
```

**Response 409** — concept already guarded.
**Response 422** — `reason` missing or < 10 chars.

### `DELETE /api/graph/health/convergence-guard/{concept_id}`

Removes a concept from the guard list.

**Response 204** — removed.
**Response 404** — concept was not guarded.

### `GET /api/graph/health/convergence-guard`

Lists all guarded concepts.

**Response 200**
```json
{
  "guarded": [
    { "concept_id": "fractal-ontology-core", "reason": "Intentional hub...", "added_at": "2026-03-28T18:05:00Z" }
  ],
  "count": 1
}
```

### `GET /api/graph/health/timeline?limit=20&offset=0`

Returns historical snapshots in descending order of `computed_at`.

**Response 200**
```json
{
  "snapshots": [
    {
      "balance_score": 0.74,
      "entropy_score": 0.68,
      "concentration_ratio": 0.41,
      "depth_diversity_score": 0.55,
      "orphan_pressure": 0.08,
      "gravity_well_count": 1,
      "orphan_cluster_count": 1,
      "computed_at": "2026-03-28T18:00:00Z",
      "delta_balance_score": 0.03
    }
  ],
  "count": 1,
  "limit": 20,
  "offset": 0
}
```

---

## Data Model

### New table: `graph_health_snapshots`

```sql
CREATE TABLE graph_health_snapshots (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    balance_score   FLOAT NOT NULL,
    entropy_score   FLOAT NOT NULL,
    concentration_ratio FLOAT NOT NULL,
    depth_diversity_score FLOAT NOT NULL,
    orphan_pressure FLOAT NOT NULL,
    gravity_well_count INTEGER NOT NULL,
    orphan_cluster_count INTEGER NOT NULL,
    snapshot_json   JSONB NOT NULL,  -- full snapshot for replay/audit
    computed_at     TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

CREATE INDEX idx_ghs_computed_at ON graph_health_snapshots (computed_at DESC);
```

### New table: `graph_convergence_guards`

```sql
CREATE TABLE graph_convergence_guards (
    concept_id VARCHAR(255) PRIMARY KEY,
    reason     TEXT NOT NULL CHECK (length(reason) >= 10),
    added_at   TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);
```

### Pydantic models (new in `api/app/models/graph_health.py`)

```python
class GravityWell(BaseModel):
    concept_id: str
    child_count: int
    severity: Literal["warning", "critical"]
    reason: str

class OrphanCluster(BaseModel):
    cluster_id: str
    node_ids: list[str]
    size: int

class SurfaceCandidate(BaseModel):
    concept_id: str
    reason: str
    free_energy_score: float | None = None

class GraphSignal(BaseModel):
    type: Literal["split_signal", "merge_signal", "surface_signal"]
    severity: Literal["info", "warning", "critical"]
    concept_id: str | None = None
    cluster_id: str | None = None

class GraphHealthSnapshot(BaseModel):
    balance_score: float
    entropy_score: float
    concentration_ratio: float
    depth_diversity_score: float
    orphan_pressure: float
    gravity_well_count: int
    gravity_wells: list[GravityWell]
    orphan_clusters: list[OrphanCluster]
    surface_candidates: list[SurfaceCandidate]
    signals: list[GraphSignal]
    computed_at: datetime

class ConvergenceGuardEntry(BaseModel):
    concept_id: str
    reason: str
    added_at: datetime

class ConvergenceGuardRequest(BaseModel):
    concept_id: str
    reason: str = Field(..., min_length=10)

class TimelineSnapshot(BaseModel):
    balance_score: float
    entropy_score: float
    concentration_ratio: float
    depth_diversity_score: float
    orphan_pressure: float
    gravity_well_count: int
    orphan_cluster_count: int
    computed_at: datetime
    delta_balance_score: float | None = None

class HealthTimeline(BaseModel):
    snapshots: list[TimelineSnapshot]
    count: int
    limit: int
    offset: int
```

---

## Files to Create/Modify

- `api/app/models/graph_health.py` — Create/extend with all response and request Pydantic models
- `api/app/services/graph_health_service.py` — Create/extend with metric computation, guard logic, and timeline queries
- `api/app/routers/graph_health.py` — Create/extend with all 6 endpoints
- `api/alembic/versions/xxxx_graph_health_tables.py` — Create migration for `graph_health_snapshots` and `graph_convergence_guards`
- `api/tests/test_182_graph_health_extended.py` — Create acceptance tests for this spec
- `web/app/graph/health/page.tsx` — Create timeline sparkline + guard management UI
- `specs/182-self-balancing-graph.md` — This spec

---

## Out of Scope

- Automatic split operations: no endpoint in this spec may divide a concept into two child concepts
- Automatic merge operations: no endpoint in this spec may combine orphan clusters into a single concept
- Autonomous edge rewriting or concept renaming driven by health signals
- LLM-powered split suggestions (deferred to follow-up spec)
- Semantic similarity scoring for merge candidates (deferred to follow-up spec)
- Scheduled background recomputation (cron/webhook integration is a follow-up)
- Notification delivery (Slack/Discord alerts on health degradation) — follow-up
- ROI endpoint comparing before/after acting on signals — follow-up
- Multi-worker snapshot consistency beyond PostgreSQL persistence already specified

---

## Configuration

```bash
SPLIT_THRESHOLD=8              # child_count >= this triggers split_signal
ORPHAN_CLUSTER_MAX_SIZE=5      # component size <= this triggers merge_signal
CONCENTRATION_CEILING=0.80     # top-3 energy share >= this triggers surface_candidates
CONVERGENCE_GUARD_REASON_MIN_LEN=10
GRAPH_HEALTH_TIMELINE_MAX=100  # max snapshots returned
```

---

## Acceptance Tests

Tests live in `api/tests/test_182_graph_health_extended.py`.

- `test_get_health_returns_all_six_metrics`
- `test_compute_empty_graph_returns_zero_baseline_not_500`
- `test_gravity_well_warning_at_split_threshold_lower_bound`
- `test_gravity_well_critical_at_15_children`
- `test_guarded_concept_excluded_from_gravity_wells`
- `test_convergence_guard_post_409_on_duplicate`
- `test_convergence_guard_post_422_on_short_reason`
- `test_convergence_guard_delete_returns_204`
- `test_concentration_ratio_triggers_surface_candidates_at_80_percent`
- `test_timeline_returns_ordered_snapshots_newest_first`
- `test_timeline_delta_balance_score_computed_correctly`
- `test_balance_score_bounded_0_to_1_always`
- `test_entropy_score_approaches_1_for_uniform_distribution`

---

## Contract Scenarios

> The reviewer MUST run these scenarios against production. All must pass.

### Scenario 1 — Health snapshot shape (create-read cycle)

**Setup**: At least one concept exists in the graph.

**Action**:
```bash
curl -s -X POST https://api.coherencycoin.com/api/graph/health/compute
```

**Expected**: HTTP 200, response body contains all six numeric fields:
```
balance_score (float 0..1), entropy_score (float 0..1),
concentration_ratio (float 0..1), depth_diversity_score (float 0..1),
orphan_pressure (float 0..1), gravity_well_count (integer >= 0)
```

**Then**:
```bash
curl -s https://api.coherencycoin.com/api/graph/health
```
**Expected**: HTTP 200, `computed_at` matches the timestamp from the POST above (within 5 seconds).

**Edge case**: POST to `/api/graph/health/compute` on an empty graph returns HTTP 200 with `balance_score` in [0.0, 1.0] — not 500.

---

### Scenario 2 — Convergence guard prevents false positive split signal

**Setup**: Compute a baseline snapshot. Identify (or seed) a concept with >= 8 children. Verify it appears in `gravity_wells`.

**Action**:
```bash
# Step 1: confirm it appears without guard
curl -s https://api.coherencycoin.com/api/graph/health | python3 -c "import sys,json; d=json.load(sys.stdin); print([g['concept_id'] for g in d['gravity_wells']])"

# Step 2: add convergence guard
curl -s -X POST https://api.coherencycoin.com/api/graph/health/convergence-guard \
  -H "Content-Type: application/json" \
  -d '{"concept_id": "<hub_concept_id>", "reason": "Intentional hub: root of the ontology tree."}'

# Step 3: recompute
curl -s -X POST https://api.coherencycoin.com/api/graph/health/compute

# Step 4: confirm it is gone from gravity_wells
curl -s https://api.coherencycoin.com/api/graph/health | python3 -c "import sys,json; d=json.load(sys.stdin); print([g['concept_id'] for g in d['gravity_wells']])"
```

**Expected**: After step 3, the guarded concept no longer appears in `gravity_wells`.

**Edge case**: POST the same concept_id again returns HTTP 409.
**Edge case**: POST with `reason` = "short" (< 10 chars) returns HTTP 422.

---

### Scenario 3 — Guard removal restores signal

**Setup**: Guard list contains concept `X` which exceeds `SPLIT_THRESHOLD`.

**Action**:
```bash
curl -s -X DELETE https://api.coherencycoin.com/api/graph/health/convergence-guard/<concept_id>
curl -s -X POST https://api.coherencycoin.com/api/graph/health/compute
curl -s https://api.coherencycoin.com/api/graph/health | python3 -c "import sys,json; d=json.load(sys.stdin); print([g['concept_id'] for g in d['gravity_wells']])"
```

**Expected**: DELETE returns 204. After recompute, concept `X` is back in `gravity_wells`.

**Edge case**: `DELETE /api/graph/health/convergence-guard/nonexistent-concept` returns 404.

---

### Scenario 4 — Timeline shows improvement over time

**Setup**: Two or more snapshots exist in the database (run `POST /api/graph/health/compute` at least twice).

**Action**:
```bash
curl -s "https://api.coherencycoin.com/api/graph/health/timeline?limit=5"
```

**Expected**: HTTP 200, `snapshots` array is ordered newest-first by `computed_at`. Each entry contains `balance_score`, `entropy_score`, `concentration_ratio`, `depth_diversity_score`, `orphan_pressure`, `gravity_well_count`, `orphan_cluster_count`, `computed_at`, and `delta_balance_score` (null for the oldest snapshot; numeric for all others).

**Then**: The earliest snapshot in the result has `delta_balance_score: null` or is the oldest in the returned window.

**Edge case**: `GET /api/graph/health/timeline?limit=0` returns 422. `GET /api/graph/health/timeline?limit=101` returns 422 (above max).

---

### Scenario 5 — Concentration triggers surface candidates

**Setup**: Graph has >= 3 concepts. The top 3 hold >= 80% of total energy (measured by `potential_value` or incoming edge count).

**Action**:
```bash
curl -s -X POST https://api.coherencycoin.com/api/graph/health/compute
curl -s https://api.coherencycoin.com/api/graph/health | python3 -c \
  "import sys,json; d=json.load(sys.stdin); print('ratio:', d['concentration_ratio'], 'candidates:', [c['concept_id'] for c in d['surface_candidates']])"
```

**Expected**: `concentration_ratio >= 0.80` and `surface_candidates` is non-empty.
Each candidate has `concept_id` and `reason`.

**Edge case**: If the graph has < 3 concepts, `concentration_ratio` is well-defined (could be 1.0 if 1 concept owns all energy) and `surface_candidates` is empty (no non-dominant concepts to surface).

---

## Risks and Assumptions

### Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Degree-based heuristics flag intentional hubs | Medium | Convergence guard; advisory-only; no auto-mutation |
| Empty or missing `potential_value` on concepts skews entropy | Medium | Fall back to in-degree count; document metric source |
| Process-local snapshot differs across workers | Low | Persist snapshots in PostgreSQL; all workers read same history |
| Timeline grows unboundedly | Low | Add retention policy (default: keep last 1000 snapshots) |
| Guard abuse (blanket-exempting everything) | Low | `reason` required; guard list is auditable via GET endpoint |
| `balance_score` formula weights arbitrary | Medium | Document weights explicitly; allow future tuning via config |

### Assumptions

- Concepts and their relationships are readable from the existing graph service without schema changes.
- `potential_value` on ideas is a reasonable proxy for "energy" in the absence of explicit edge weights.
- Reviewers prefer narrow, advisory, testable spec over a broad autonomous rebalancing system.
- The PostgreSQL connection is available in the API service (already true per existing architecture).

---

## Known Gaps and Follow-up Tasks

- **Follow-up**: Web UI sparkline at `/graph/health` showing `balance_score` trend (visual proof it's working).
- **Follow-up**: Automatic split suggestions with proposed new concept names (requires LLM integration).
- **Follow-up**: Automatic merge suggestions with candidate concept pairs (requires semantic similarity).
- **Follow-up**: `GET /api/graph/health/roi` — before/after comparison for acted-upon signals.
- **Follow-up**: Scheduled recomputation (cron or post-commit hook) so the timeline fills automatically.
- **Follow-up**: Weight-aware balancing using typed edge weights from Spec 169.
- **Follow-up**: Notification integration — emit a Discord/Slack message when `balance_score` drops below 0.4.

---

## Verification

Run these commands to confirm the spec and implementation are complete:

```bash
# Validate spec quality contract
python3 scripts/validate_spec_quality.py --file specs/182-self-balancing-graph.md

# Confirm required sections exist
grep -n "^## " specs/182-self-balancing-graph.md

# Run acceptance tests
pytest api/tests/test_182_graph_health_extended.py -v

# Smoke test production endpoints
curl -s https://api.coherencycoin.com/api/graph/health | python3 -m json.tool
curl -s -X POST https://api.coherencycoin.com/api/graph/health/compute | python3 -m json.tool
curl -s https://api.coherencycoin.com/api/graph/health/timeline?limit=5 | python3 -m json.tool
curl -s https://api.coherencycoin.com/api/graph/health/convergence-guard | python3 -m json.tool
```

The spec is accepted when:

1. All six metrics are defined with formulas, not just named.
2. The convergence guard is fully specified (CRUD, semantics, abuse prevention).
3. The timeline endpoint is fully specified (schema, ordering, delta computation).
4. Verification Scenarios 1–5 are runnable verbatim against production.
5. `python3 scripts/validate_spec_quality.py --file specs/182-self-balancing-graph.md` exits 0.
