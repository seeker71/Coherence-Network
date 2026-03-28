# Spec 180: Self-Balancing Graph — Anti-Collapse, Organic Expansion, Entropy Management

**Spec ID**: 180-self-balancing-graph
**Task ID**: task_9d2d62e242465f8d
**Status**: draft
**Priority**: high
**Author**: product-manager agent
**Date**: 2026-03-28

---

## Summary

The Coherence Network graph is a living system. Left unwatched, it tends toward two failure modes:
**collapse** (a few dominant ideas absorb all energy, orphaning everything else) and
**fragmentation** (unconnected concept clusters drift into irrelevance). This spec introduces
a **Graph Health Monitor** that continuously measures the shape of the concept graph, detects
unhealthy structural patterns, and surfaces actionable signals — without suppressing legitimate
convergence or forcing artificial diversity.

The system does not rebalance automatically. It observes, measures, and recommends. Humans and
agents act on recommendations; the monitor tracks whether balance improves.

---

## Motivation

From the Living Codex architecture: nodes breathe, cluster, and resonate. Resonance is healthy
convergence — structurally similar ideas linking across domains. But monopoly is pathological
convergence — one idea captures all edges and starves the rest. The graph cannot distinguish
these states without measurement.

Three signal classes drive this spec:

1. **Entropy collapse** — `energy_concentration > 0.80` means ≥80% of energy flows to ≤3 ideas.
   Neglected high-potential branches become invisible and die.
2. **Over-branching** — a concept accumulates so many children it becomes a catch-all. Structural
   signal is lost. The node should split.
3. **Orphan clustering** — isolated nodes with ≥2 semantic neighbors but no graph edges. They
   resonate with existing concepts but have never been linked. They should merge or connect.

---

## Goals

1. Define quantitative metrics for graph health (entropy, concentration, depth variance, orphan ratio).
2. Implement `GET /api/graph/health` — returns current graph health snapshot.
3. Implement `GET /api/graph/health/signals` — returns ranked list of actionable balance signals.
4. Implement `GET /api/graph/health/history` — time-series of health scores for trend analysis.
5. Surface the **top neglected branch** (high-potential, low-energy) in the signals response.
6. Provide a CLI command `cc graph health` for terminal monitoring.
7. Add a `/graph/health` web page showing the live balance dashboard.
8. Store health snapshots in Postgres for trend tracking and proof of improvement.

---

## Non-Goals

- Automatic graph restructuring (splitting or merging without human approval).
- Changing the graph structure itself (this spec is read/observe only).
- Real-time streaming of health events (follow-up spec).
- Weighting by contributor identity (future work).

---

## Architecture

### Measurement Pipeline

```
Neo4j graph + Postgres ideas/edges
        ↓ (sampled every N minutes or on-demand)
GraphHealthService.compute_snapshot()
        ↓ produces
GraphHealthSnapshot (Pydantic model)
        ↓ stored in
graph_health_snapshots (Postgres table)
        ↓ served via
GET /api/graph/health          → latest snapshot
GET /api/graph/health/signals  → ranked actionable signals
GET /api/graph/health/history  → time-series
        ↓ consumed by
Web /graph/health page
CLI cc graph health
```

### Metrics Defined

#### 1. Energy Concentration Index (ECI)
Gini coefficient applied to idea energy (activity score, edge count weighted by recency).
- `0.0` = perfectly flat, all ideas receive equal attention.
- `1.0` = one idea has all the energy.
- **Threshold**: ECI > 0.75 → `COLLAPSE_RISK` signal.

```
ECI = (2 * sum(i * sorted_energy[i]) / (n * sum(sorted_energy))) - (n+1)/n
```

#### 2. Top-K Concentration (TKC)
Fraction of total energy held by the top 3 ideas.
- **Threshold**: TKC > 0.80 → surfaces the neglected branches with highest potential score.

#### 3. Child Proliferation Score (CPS) per node
`child_count / global_avg_child_count`. Nodes with CPS > 4.0 are **split candidates**.
- A node with 20 children when the average is 3.5 has CPS = 5.7 → split signal.

#### 4. Orphan Ratio (OR)
`orphaned_nodes / total_nodes` where orphan = zero graph edges AND resonance_score > 0.3
with at least one existing concept.
- **Threshold**: OR > 0.15 → `FRAGMENTATION_RISK` signal.
- Orphans above threshold are surfaced as **merge candidates**.

#### 5. Depth Variance (DV)
Standard deviation of concept depth (hops from root concepts).
- Low DV = flat, star-shaped graph (collapse risk).
- Very high DV = extremely long chains (fragmentation risk).
- **Healthy range**: DV between 1.5 and 4.0.

#### 6. Graph Diameter Trend
Max shortest path between any two connected nodes. Tracked over time.
- Rapid increase → fragmentation.
- Stagnation → calcification (no growth).

#### 7. Overall Health Score (OHS)
Composite 0.0–1.0 score:
```
OHS = 0.35 * (1 - ECI) + 0.25 * (1 - TKC) + 0.20 * (1 - OR) + 0.20 * depth_health
depth_health = 1.0 - min(1.0, abs(DV - 2.75) / 2.75)
```

A score above 0.70 is **healthy**. 0.50–0.70 is **watch**. Below 0.50 is **critical**.

---

## Signal Types

Each signal has a `type`, `severity` (info/warning/critical), a `target_id`, and a `recommendation`.

| Signal Type | Trigger | Severity | Recommendation |
|-------------|---------|----------|----------------|
| `COLLAPSE_RISK` | ECI > 0.75 | critical | "Energy concentrated — surface neglected branches" |
| `SPLIT_CANDIDATE` | CPS > 4.0 for a node | warning | "Concept `{id}` has {n} children — consider splitting" |
| `MERGE_CANDIDATE` | Orphan with resonance_score > 0.3 to existing node | warning | "Concept `{id}` resonates with `{target}` but is unlinked — merge or connect" |
| `NEGLECTED_BRANCH` | High potential_score, low energy (bottom 20% by activity) | info | "Concept `{id}` has high potential but low activity — invest attention" |
| `FRAGMENTATION_RISK` | OR > 0.15 | warning | "Orphan ratio is {pct}% — graph is fragmenting" |
| `HEALTHY` | OHS > 0.70 and no critical signals | info | "Graph is in dynamic equilibrium" |

**Genuine convergence protection**: A `SPLIT_CANDIDATE` is suppressed when the node's
`resonance_coherence_score > 0.80` — high resonance coherence means children are genuinely
related, not just accumulated. This prevents the algorithm from splitting legitimate hubs.

Similarly, `COLLAPSE_RISK` is downgraded from critical to warning when the top-3 ideas have
cross-domain resonance links — convergence across domains is healthy.

---

## API Specification

### `GET /api/graph/health`

Returns the latest graph health snapshot. Triggers a fresh compute if the last snapshot is
older than `max_age_seconds` (default 300).

**Query params:**
- `max_age_seconds` — integer, default 300. If snapshot is fresher than this, return cached.
- `force_refresh` — boolean, default false. Bypass cache and recompute immediately.

**Response 200:**
```json
{
  "snapshot_id": "gh_a1b2c3d4",
  "computed_at": "2026-03-28T14:00:00Z",
  "node_count": 347,
  "edge_count": 892,
  "orphan_count": 42,
  "overall_health_score": 0.68,
  "health_status": "watch",
  "metrics": {
    "energy_concentration_index": 0.61,
    "top3_concentration": 0.74,
    "orphan_ratio": 0.12,
    "depth_variance": 2.1,
    "graph_diameter": 8,
    "avg_children_per_node": 2.57
  },
  "signal_count": 4,
  "critical_signal_count": 0
}
```

**Response 503** (graph unavailable):
```json
{ "detail": "Graph database unavailable", "retry_after": 30 }
```

---

### `GET /api/graph/health/signals`

Returns ranked actionable signals, most severe first.

**Query params:**
- `severity` — filter: `info`, `warning`, `critical`
- `type` — filter: `COLLAPSE_RISK`, `SPLIT_CANDIDATE`, `MERGE_CANDIDATE`, `NEGLECTED_BRANCH`, `FRAGMENTATION_RISK`
- `limit` — default 20, max 100

**Response 200:**
```json
{
  "snapshot_id": "gh_a1b2c3d4",
  "total_signals": 4,
  "signals": [
    {
      "signal_id": "sig_001",
      "type": "SPLIT_CANDIDATE",
      "severity": "warning",
      "target_id": "artificial-intelligence",
      "target_name": "Artificial Intelligence",
      "child_count": 31,
      "avg_child_count": 2.57,
      "child_proliferation_score": 12.1,
      "resonance_coherence_score": 0.42,
      "recommendation": "Concept 'artificial-intelligence' has 31 children (avg 2.57) — consider splitting into sub-domains",
      "suppressed": false
    },
    {
      "signal_id": "sig_002",
      "type": "NEGLECTED_BRANCH",
      "severity": "info",
      "target_id": "distributed-cognition",
      "target_name": "Distributed Cognition",
      "potential_score": 0.81,
      "activity_percentile": 8,
      "last_active": "2026-02-14T09:12:00Z",
      "recommendation": "Concept 'distributed-cognition' has high potential (0.81) but is in bottom 10% by activity — invest attention"
    }
  ]
}
```

---

### `GET /api/graph/health/history`

Time-series of OHS and key metrics. Used to prove the balance algorithm is working.

**Query params:**
- `since` — ISO 8601 datetime (default: 7 days ago)
- `until` — ISO 8601 datetime (default: now)
- `interval` — `hourly`, `daily` (default: `daily`)

**Response 200:**
```json
{
  "interval": "daily",
  "points": [
    {
      "date": "2026-03-21",
      "overall_health_score": 0.55,
      "energy_concentration_index": 0.72,
      "orphan_ratio": 0.18,
      "node_count": 289,
      "edge_count": 710,
      "signal_count": 7,
      "critical_signal_count": 2
    },
    {
      "date": "2026-03-28",
      "overall_health_score": 0.68,
      "energy_concentration_index": 0.61,
      "orphan_ratio": 0.12,
      "node_count": 347,
      "edge_count": 892,
      "signal_count": 4,
      "critical_signal_count": 0
    }
  ],
  "trend": "improving"
}
```

**Trend values**: `improving`, `stable`, `degrading`, `insufficient_data`.

---

### `POST /api/graph/health/snapshot`

Manually trigger a health snapshot computation. Intended for CI, post-deploy hooks, or
scheduled jobs.

**Request body:** (empty or `{}`)

**Response 202:**
```json
{
  "snapshot_id": "gh_a1b2c3d4",
  "status": "computing",
  "estimated_ms": 2000
}
```

After completion:
```json
{
  "snapshot_id": "gh_a1b2c3d4",
  "status": "ready",
  "overall_health_score": 0.68,
  "health_status": "watch"
}
```

---

## Data Model

### `graph_health_snapshots` (Postgres table)

```sql
CREATE TABLE graph_health_snapshots (
    id               VARCHAR(20) PRIMARY KEY,          -- e.g. "gh_a1b2c3d4"
    computed_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    node_count       INTEGER NOT NULL,
    edge_count       INTEGER NOT NULL,
    orphan_count     INTEGER NOT NULL DEFAULT 0,
    overall_health_score FLOAT NOT NULL,               -- 0.0–1.0
    health_status    VARCHAR(10) NOT NULL,              -- healthy/watch/critical
    eci              FLOAT NOT NULL,                    -- energy_concentration_index
    top3_concentration FLOAT NOT NULL,
    orphan_ratio     FLOAT NOT NULL,
    depth_variance   FLOAT NOT NULL,
    graph_diameter   INTEGER,
    avg_children     FLOAT NOT NULL,
    signal_count     INTEGER NOT NULL DEFAULT 0,
    critical_signals INTEGER NOT NULL DEFAULT 0,
    signals_json     JSONB                              -- full signal list for the snapshot
);

CREATE INDEX idx_ghs_computed_at ON graph_health_snapshots(computed_at DESC);
```

### Pydantic Models

```python
class GraphMetrics(BaseModel):
    energy_concentration_index: float      # 0.0–1.0
    top3_concentration: float              # 0.0–1.0
    orphan_ratio: float                    # 0.0–1.0
    depth_variance: float
    graph_diameter: int | None
    avg_children_per_node: float

class GraphHealthSnapshot(BaseModel):
    snapshot_id: str
    computed_at: datetime
    node_count: int
    edge_count: int
    orphan_count: int
    overall_health_score: float            # 0.0–1.0
    health_status: Literal["healthy", "watch", "critical"]
    metrics: GraphMetrics
    signal_count: int
    critical_signal_count: int

class GraphSignal(BaseModel):
    signal_id: str
    type: str                              # SPLIT_CANDIDATE, MERGE_CANDIDATE, etc.
    severity: Literal["info", "warning", "critical"]
    target_id: str
    target_name: str | None
    recommendation: str
    suppressed: bool = False               # True when genuine convergence detected
    suppression_reason: str | None

class GraphSignalsResponse(BaseModel):
    snapshot_id: str
    total_signals: int
    signals: list[GraphSignal]

class GraphHealthHistoryPoint(BaseModel):
    date: str                              # ISO date or datetime
    overall_health_score: float
    energy_concentration_index: float
    orphan_ratio: float
    node_count: int
    edge_count: int
    signal_count: int
    critical_signal_count: int

class GraphHealthHistory(BaseModel):
    interval: str
    points: list[GraphHealthHistoryPoint]
    trend: Literal["improving", "stable", "degrading", "insufficient_data"]
```

---

## Files to Create / Modify

| File | Action | Notes |
|------|--------|-------|
| `api/app/routers/graph_health.py` | Create | Router: health, signals, history, snapshot |
| `api/app/services/graph_health_service.py` | Create | Compute metrics, generate signals, store snapshots |
| `api/app/models/graph_health.py` | Create | Pydantic models (snapshot, signal, history) |
| `api/app/main.py` | Modify | Register graph_health router under `/api/graph` |
| `api/migrations/add_graph_health_snapshots.sql` | Create | Postgres table DDL |
| `api/tests/test_graph_health.py` | Create | Pytest tests for all endpoints |
| `web/app/graph/health/page.tsx` | Create (Phase 2) | Balance dashboard web page |

---

## Task Card

```yaml
goal: Implement graph health monitoring with metrics, signals, and trend history
files_allowed:
  - api/app/routers/graph_health.py
  - api/app/services/graph_health_service.py
  - api/app/models/graph_health.py
  - api/app/main.py
  - api/migrations/add_graph_health_snapshots.sql
  - api/tests/test_graph_health.py
done_when:
  - GET /api/graph/health returns 200 with valid OHS score
  - GET /api/graph/health/signals returns ranked signal list
  - GET /api/graph/health/history returns time-series with trend field
  - All 5 verification scenarios pass
  - graph_health_snapshots table exists in Postgres
commands:
  - cd api && pytest -q tests/test_graph_health.py
  - curl -s https://api.coherencycoin.com/api/graph/health | jq .
constraints:
  - No automatic graph modification — observe only
  - Suppress SPLIT_CANDIDATE when resonance_coherence_score > 0.80
  - OHS must be 0.0–1.0 (clamp, do not allow out-of-range)
  - Graph unavailability returns 503 with retry_after, never 500
```

---

## Verification Scenarios

### Scenario 1: Health Snapshot Returns Valid Shape

**Setup**: API is running. Graph has at least 10 concept nodes.

**Action**:
```bash
curl -s https://api.coherencycoin.com/api/graph/health | jq '{
  snapshot_id, health_status, overall_health_score,
  eci: .metrics.energy_concentration_index,
  orphan_ratio: .metrics.orphan_ratio
}'
```

**Expected**: HTTP 200. `snapshot_id` starts with `"gh_"`. `health_status` is one of `"healthy"`, `"watch"`, `"critical"`. `overall_health_score` is a float between 0.0 and 1.0. `eci` is between 0.0 and 1.0. `orphan_ratio` is between 0.0 and 1.0.

**Edge case — force refresh**:
```bash
curl -s "https://api.coherencycoin.com/api/graph/health?force_refresh=true" | jq '.computed_at'
```
Returns a timestamp within the last 10 seconds. A second call without `force_refresh` returns the same `snapshot_id` (cached).

**Edge case — empty graph**:
```bash
# In test environment with zero nodes:
curl -s https://api.coherencycoin.com/api/graph/health | jq '{node_count, overall_health_score}'
```
Returns HTTP 200 with `node_count: 0` and `overall_health_score: 1.0` (empty graph is trivially balanced). Does NOT return 500.

---

### Scenario 2: Signals Surface Imbalance Correctly

**Setup**: In a test database, create idea `"hub-concept"` with 25 child relationships and average node children = 2.0.

**Action**:
```bash
curl -s "https://api.coherencycoin.com/api/graph/health/signals?type=SPLIT_CANDIDATE" \
  | jq '[.signals[] | select(.target_id=="hub-concept")] | .[0] | {type, severity, child_count, child_proliferation_score, suppressed}'
```

**Expected**: HTTP 200. Returns signal with `type="SPLIT_CANDIDATE"`, `severity="warning"`, `child_count=25`, `child_proliferation_score > 4.0`, `suppressed=false`.

**Edge case — genuine convergence suppression**:
Set `hub-concept.resonance_coherence_score = 0.85` then re-request.
```bash
curl -s "https://api.coherencycoin.com/api/graph/health/signals?type=SPLIT_CANDIDATE" \
  | jq '[.signals[] | select(.target_id=="hub-concept")] | .[0].suppressed'
```
Returns `true`. Signal still appears but `suppressed=true` and `suppression_reason` explains why.

**Edge case — filter by severity**:
```bash
curl -s "https://api.coherencycoin.com/api/graph/health/signals?severity=critical" \
  | jq '[.signals[] | select(.severity != "critical")] | length'
```
Returns `0` — filter is respected exactly.

---

### Scenario 3: History Trend Proves Improvement

**Setup**: Two snapshots exist in `graph_health_snapshots` — one from 7 days ago with OHS=0.50, one from today with OHS=0.68.

**Action**:
```bash
curl -s "https://api.coherencycoin.com/api/graph/health/history?interval=daily" \
  | jq '{trend, point_count: (.points | length), first_score: .points[0].overall_health_score, last_score: .points[-1].overall_health_score}'
```

**Expected**: HTTP 200. `trend="improving"`. `point_count >= 2`. `last_score > first_score`. Each point has `overall_health_score`, `energy_concentration_index`, `orphan_ratio`, `node_count`, `signal_count`.

**Edge case — insufficient data**:
```bash
curl -s "https://api.coherencycoin.com/api/graph/health/history?since=2030-01-01T00:00:00Z" \
  | jq '.trend'
```
Returns `"insufficient_data"` (no points in range). `points` is an empty array. HTTP 200, not 404.

**Edge case — invalid date format**:
```bash
curl -s "https://api.coherencycoin.com/api/graph/health/history?since=not-a-date" \
  -o /dev/null -w "%{http_code}"
```
Returns `422` (validation error), not `500`.

---

### Scenario 4: Neglected Branch Signal Identifies High-Potential Orphan

**Setup**: Concept `"distributed-cognition"` has `potential_score=0.81` (computed from resonance + link quality) but ranks in the bottom 20% of ideas by recent activity score.

**Action**:
```bash
curl -s "https://api.coherencycoin.com/api/graph/health/signals?type=NEGLECTED_BRANCH" \
  | jq '[.signals[] | select(.target_id=="distributed-cognition")] | .[0] | {type, potential_score, activity_percentile, recommendation}'
```

**Expected**: HTTP 200. Returns signal with `type="NEGLECTED_BRANCH"`, `potential_score >= 0.80`, `activity_percentile <= 20`, `recommendation` contains the concept name and a concrete action ("invest attention" or "connect to related concepts").

**Edge case — no neglected branches**:
If all high-potential ideas are also high-activity:
```bash
curl -s "https://api.coherencycoin.com/api/graph/health/signals?type=NEGLECTED_BRANCH" | jq '.total_signals'
```
Returns `0`. HTTP 200, not 404.

---

### Scenario 5: Full Observe-Act-Verify Cycle

**Setup**: Start with graph OHS = 0.55 (watch state). Manually add 5 edges connecting orphan nodes to their nearest semantic neighbors (simulating acting on MERGE_CANDIDATE signals).

**Action**:
```bash
# Step 1: Check initial health
BEFORE=$(curl -s https://api.coherencycoin.com/api/graph/health | jq '.overall_health_score')

# Step 2: Add edges (use the graph/concepts edge API from spec 008)
for ORPHAN_ID in "concept-a" "concept-b" "concept-c" "concept-d" "concept-e"; do
  curl -s -X POST https://api.coherencycoin.com/api/graph/edges \
    -H "Content-Type: application/json" \
    -d "{\"from_id\":\"$ORPHAN_ID\",\"to_id\":\"its-nearest-neighbor\",\"type\":\"resonates-with\"}"
done

# Step 3: Force refresh and check improvement
AFTER=$(curl -s "https://api.coherencycoin.com/api/graph/health?force_refresh=true" | jq '.overall_health_score')

echo "Before: $BEFORE  After: $AFTER"

# Step 4: Verify history trend
curl -s "https://api.coherencycoin.com/api/graph/health/history?interval=daily" | jq '.trend'
```

**Expected**: `AFTER > BEFORE`. History shows at least two data points. `orphan_ratio` decreased. `trend` is `"improving"` or `"stable"`. MERGE_CANDIDATE signals for the connected nodes are no longer in the signal list.

**Edge case — duplicate snapshot trigger**:
```bash
curl -s -X POST https://api.coherencycoin.com/api/graph/health/snapshot
curl -s -X POST https://api.coherencycoin.com/api/graph/health/snapshot
```
Second call either waits for the first to finish (202 with same `snapshot_id`) or returns a fresh computation. Does NOT create duplicate database rows for the same second.

---

## Web: `/graph/health` Page

**Route**: `web/app/graph/health/page.tsx`

### Features

1. **Health Score Dial** — prominent 0–100 gauge showing OHS. Color: green (≥70), amber (50–69), red (<50).
2. **Metrics Panel** — cards for ECI, TKC, Orphan Ratio, Depth Variance. Each shows value + healthy range indicator.
3. **Signal Feed** — ranked list of signals, filterable by severity and type. Each signal links to the relevant concept page.
4. **Trend Sparkline** — 7-day OHS trend chart. Shows whether balance is improving.
5. **Suppressed Signals** — collapsed section showing suppressed signals (genuine convergence detected). Transparent — shows the system is not over-correcting.

---

## CLI: `cc graph health`

```
$ cc graph health

Graph Health — 2026-03-28T14:00Z
Overall Score: 0.68  [WATCH]

Metrics:
  Energy Concentration (ECI): 0.61  [ok]
  Top-3 Concentration:        0.74  [warning]
  Orphan Ratio:               0.12  [ok]
  Depth Variance:             2.1   [ok]
  Avg Children/Node:          2.57

Signals (4):
  [WARNING] artificial-intelligence — SPLIT_CANDIDATE (CPS: 12.1, children: 31)
  [WARNING] distributed-cognition  — NEGLECTED_BRANCH (potential: 0.81, activity: 8th pct)
  [INFO]    ...

Run `cc graph health --signals` for full signal list.
Run `cc graph health --history` for 7-day trend.
```

---

## Implementation Plan

### Phase 1 — Core API (this spec)

1. `api/app/models/graph_health.py` — Pydantic models.
2. `api/app/services/graph_health_service.py` — metric computation using Neo4j queries and Postgres idea energy.
3. `api/migrations/add_graph_health_snapshots.sql` — DDL.
4. `api/app/routers/graph_health.py` — four endpoints.
5. Register in `main.py`.
6. `api/tests/test_graph_health.py` — pytest tests.

### Phase 2 — Web Dashboard (follow-up spec)

7. `web/app/graph/health/page.tsx` — health dashboard.

### Phase 3 — CLI (follow-up spec)

8. `cc graph health` command in MCP server or CLI handler.

### Phase 4 — Scheduled Snapshots (follow-up spec)

9. Cron job: compute snapshot every 30 minutes, alert if OHS drops below 0.50.

---

## Acceptance Criteria

- [ ] `GET /api/graph/health` returns HTTP 200 with `snapshot_id`, `overall_health_score` (0.0–1.0), `health_status`, and `metrics` object.
- [ ] `GET /api/graph/health/signals` returns ranked signals with `type`, `severity`, `target_id`, `recommendation`, `suppressed`.
- [ ] `SPLIT_CANDIDATE` signals are suppressed (not removed) when `resonance_coherence_score > 0.80`.
- [ ] `GET /api/graph/health/history` returns `points` array and `trend` field.
- [ ] `trend` is `"improving"` when last OHS > first OHS in the time window.
- [ ] `POST /api/graph/health/snapshot` returns 202 and eventually a completed snapshot.
- [ ] `graph_health_snapshots` table exists in Postgres with all defined columns.
- [ ] Graph unavailability returns 503 with `retry_after`, not 500.
- [ ] Empty graph (0 nodes) returns OHS = 1.0, not an error.
- [ ] All 5 verification scenarios pass in production.
- [ ] OHS is always clamped to [0.0, 1.0] regardless of input anomalies.

---

## Concurrency Behavior

- **Snapshot reads**: Safe for concurrent access; return cached snapshot if within `max_age_seconds`.
- **Snapshot writes**: Single writer per snapshot ID. Parallel `POST /snapshot` calls: second waits or gets existing in-progress snapshot.
- **History reads**: Read-only Postgres query; no locking needed.

---

## Risks and Assumptions

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Neo4j query for Gini coefficient is slow on large graphs | Medium | Compute on sampled subgraph (≤5000 nodes); full graph in background |
| Energy score definition not standardized across the codebase | High | Use `activity_score` from ideas table + edge count as proxy; document the formula |
| Suppression logic suppresses too aggressively, hiding real problems | Medium | Suppressed signals remain visible in response (`suppressed=true`); reviewable |
| OHS degrading despite genuine growth (more nodes = more orphans) | Medium | Normalize orphan_ratio by growth rate, not absolute count |
| `potential_score` not yet defined as a concept property | High | Phase 1 uses `resonance_score` as proxy; `potential_score` spec TBD (follow-up) |
| Graph diameter query is O(V*E) on naive implementation | High | Use approximation (BFS from random sample of 50 nodes); flag as estimate |

---

## Known Gaps and Follow-up Tasks

1. **`potential_score` field** — Phase 1 uses `resonance_score` as proxy. A dedicated spec should define `potential_score` as a first-class idea attribute incorporating: resonance breadth, contribution velocity, and cross-domain link count.
2. **Scheduled snapshot job** — Phase 4 spec needed to schedule OHS computation every 30 minutes.
3. **Alert on OHS drop** — When OHS crosses below 0.50, notify operators (runner message or email). Spec TBD.
4. **Web dashboard** — `/graph/health` page is Phase 2; not in this implementation scope.
5. **CLI commands** — `cc graph health` is Phase 3.
6. **Energy score standardization** — The definition of "energy" (activity_score, edge weight, recency) must be formalized in a separate data-model spec before Phase 2.
7. **`POST /api/graph/health/snapshot` async behavior** — Phase 1 may return synchronously (blocking for up to 5s). True async (202 + polling) is Phase 2.

---

## Failure/Retry Reflection

- **Failure mode**: Neo4j unavailable during snapshot computation.
  - **Blind spot**: The graph DB is a hard dependency; the service has no fallback.
  - **Next action**: Return 503 with `retry_after: 30`. Log the failure. Return last known snapshot if it is < 1 hour old with `stale: true` flag.

- **Failure mode**: ECI computation with all-zero energy scores produces NaN/Inf.
  - **Blind spot**: Division by zero in Gini formula when all activity_scores are 0.
  - **Next action**: Guard: if `sum(energy) == 0`, return `ECI = 0.0` (perfectly balanced by vacuity).

- **Failure mode**: `COLLAPSE_RISK` fires on a legitimately young/small graph with 5 nodes where 2 are dominant.
  - **Blind spot**: Small-graph statistics are unreliable.
  - **Next action**: Suppress all signals when `node_count < 20`. Return `health_status: "insufficient_data"` instead.

---

## Decision Gates

- **[NEEDS DECISION]** Should `POST /api/graph/health/snapshot` be synchronous (blocks for up to 5s) or truly async (202 + separate GET to poll)? MVP proposes synchronous for simplicity. Mark as `needs-decision` if graph query time exceeds 5s in staging.
- **[NEEDS DECISION]** Should suppressed signals be hidden from the default response or always visible? Spec proposes always visible with `suppressed=true`. Change requires product decision if UX feedback says suppressed signals cause confusion.

---

## Research Inputs

- `2026-03-28` — Living-Codex-CSharp architecture (internal reference, `reference_living_codex.md`) — U-Core breath/water states, resonance, belief systems inform the concept of graph entropy and convergence detection.
- `2026-03-28` — Spec 162 (Meta Self-Discovery) — Pattern for self-observing system endpoints.
- `2026-03-28` — Spec 179 (Cross-Domain Resonance) — `resonance_coherence_score` and structural similarity metrics reused in suppression logic.
- `2026-03-28` — Spec 176 (Idea Lifecycle Closure) — Energy and activity scoring approach for ideas.
