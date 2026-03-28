# Spec 172 — Self-Balancing Graph: Anti-Collapse, Organic Expansion, Entropy Management

## Goal

The Coherence Network must monitor its own shape. When a concept accumulates too many children it
signals for splitting. When orphan nodes cluster they are surfaced for merging. When energy
concentrates in too few ideas, neglected but high-potential branches are made visible. Balance is
not static — it is **dynamic equilibrium** that adapts as the network grows, preventing
intellectual collapse while never suppressing genuine convergence.

---

## Problem

- Concepts in the graph currently have no upper bound on child connections; "gravity wells" form
  around popular ideas and suffocate adjacent, potentially superior branches.
- Orphan and near-orphan nodes accumulate silently — the graph has no mechanism to notice
  isolated clusters and propose merges or re-attachments.
- Energy concentration is unmeasured: if 80 % of interaction volume flows to 3 concepts, the
  remaining ideas degrade invisibly toward zero coherence, a form of **graph collapse**.
- There is no distinction between healthy convergence (two ideas merging because they are
  genuinely equivalent) and pathological collapse (one idea swallowing others by inertia).
- Without continuous entropy metrics, the graph cannot prove it is healthy, nor can contributors
  or operators intervene before collapse is irreversible.

---

## Solution

A **Graph Health Monitor** layer that runs on a configurable schedule (and on-demand), computes
structural and energetic shape metrics, emits signals for splitting/merging/surfacing, and
exposes those signals through the API and CLI so agents and humans can act on them.

### Core Concepts

| Term | Definition |
|------|-----------|
| **Gravity well** | A concept node with child count ≥ `split_threshold` (default 15) |
| **Orphan cluster** | A connected component of size ≥ 2 and ≤ `orphan_max_size` (default 5) with no edges to the main component |
| **Concentration ratio** | Fraction of total interaction energy absorbed by the top-N concepts (default N=3) |
| **Entropy score** | Shannon entropy of the interaction-energy distribution across all concept nodes, normalised to [0.0, 1.0] |
| **Balance score** | Composite 0.0–1.0 signal: 1.0 = perfectly balanced, < 0.4 = unhealthy |
| **Convergence guard** | A flag set by contributors or automatically to exempt a node from split signals when genuine intellectual convergence is occurring |

### Health Metric Thresholds

| Metric | Healthy | Warning | Critical |
|--------|---------|---------|----------|
| Child count per concept | ≤ 14 | 15–24 | ≥ 25 |
| Concentration ratio (top-3) | ≤ 0.50 | 0.51–0.79 | ≥ 0.80 |
| Entropy score | ≥ 0.65 | 0.40–0.64 | < 0.40 |
| Orphan cluster count | 0 | 1–3 | ≥ 4 |
| Balance score (composite) | ≥ 0.65 | 0.40–0.64 | < 0.40 |

### Signals Emitted

1. **`split_signal`** — concept has too many children; suggests splitting into sub-themes.
2. **`merge_signal`** — two or more orphan clusters are semantically adjacent and should merge.
3. **`surface_signal`** — a low-energy concept has high potential score but is receiving < 1 %
   of interaction volume; the system surfaces it to contributors.
4. **`convergence_ok`** — a node is concentrating energy but has `convergence_guard = true`;
   no action needed.
5. **`health_report`** — periodic full snapshot of all metrics.

---

## API Endpoints

### `GET /api/graph/health`

Returns the current health snapshot including all metrics and active signals.

**Response 200**
```json
{
  "computed_at": "2026-03-28T12:00:00Z",
  "balance_score": 0.71,
  "entropy_score": 0.68,
  "concentration_ratio": 0.43,
  "concept_count": 142,
  "edge_count": 891,
  "gravity_wells": [
    { "concept_id": "ai-alignment", "child_count": 22, "severity": "warning" }
  ],
  "orphan_clusters": [
    { "cluster_id": "cluster_7f3a", "size": 3, "members": ["node-a","node-b","node-c"] }
  ],
  "surface_candidates": [
    { "concept_id": "formal-verification", "potential_score": 0.87, "interaction_pct": 0.008 }
  ],
  "signals": [
    { "type": "split_signal",   "concept_id": "ai-alignment",      "severity": "warning" },
    { "type": "surface_signal", "concept_id": "formal-verification","severity": "info"    }
  ],
  "spec_ref": "spec-172"
}
```

**Response 503** if graph DB is unreachable:
```json
{ "detail": "Graph database unavailable", "spec_ref": "spec-172" }
```

---

### `GET /api/graph/health/history`

Returns the last N health snapshots (default 10, max 100) in reverse-chronological order.

**Query params**: `?limit=10`, `?since=<ISO-8601>`

**Response 200**
```json
{
  "items": [ { "computed_at": "...", "balance_score": 0.71, ... } ],
  "total": 47,
  "spec_ref": "spec-172"
}
```

---

### `POST /api/graph/health/compute`

Triggers an immediate (synchronous, ≤ 10 s) health computation outside the normal schedule.
Returns the same schema as `GET /api/graph/health`.

**Response 200** — freshly computed snapshot.
**Response 429** — another computation is already in flight (cooldown 30 s).

---

### `GET /api/graph/signals`

Returns all active (un-resolved) signals.

**Query params**: `?type=split_signal|merge_signal|surface_signal`, `?severity=warning|critical|info`

**Response 200**
```json
{
  "signals": [
    {
      "id": "sig_abc123",
      "type": "split_signal",
      "concept_id": "ai-alignment",
      "severity": "warning",
      "created_at": "2026-03-28T11:55:00Z",
      "resolved": false
    }
  ],
  "total": 1,
  "spec_ref": "spec-172"
}
```

---

### `POST /api/graph/signals/{signal_id}/resolve`

Marks a signal as resolved (human or agent acted on it).

**Body**
```json
{ "resolution": "split completed — created 3 child concepts", "resolved_by": "contributor_id" }
```

**Response 200** — updated signal with `resolved: true`, `resolved_at`, `resolution`.
**Response 404** — signal not found.
**Response 409** — signal already resolved.

---

### `POST /api/graph/concepts/{concept_id}/convergence-guard`

Sets `convergence_guard = true` on a concept, suppressing split signals for it.

**Body**
```json
{ "reason": "These sub-topics are genuinely converging toward a unified theory", "set_by": "contributor_id" }
```

**Response 200** — `{ "concept_id": "...", "convergence_guard": true, "reason": "...", "set_at": "..." }`
**Response 404** — concept not found.

**`DELETE /api/graph/concepts/{concept_id}/convergence-guard`**
Removes the guard, re-enabling balance signals for the concept.
**Response 200** or **404**.

---

### `GET /api/graph/health/roi`

Proof that the balancing algorithm is working over time.

**Response 200**
```json
{
  "period_days": 30,
  "balance_score_delta": +0.12,
  "entropy_score_delta": +0.08,
  "split_signals_actioned": 4,
  "merge_signals_actioned": 2,
  "surface_signals_actioned": 7,
  "false_positive_rate": 0.05,
  "convergence_guards_active": 2,
  "spec_ref": "spec-172"
}
```

---

## Data Model

```yaml
GraphHealthSnapshot:
  id:              { type: string, format: uuid }
  computed_at:     { type: string, format: iso8601 }
  balance_score:   { type: float, range: [0.0, 1.0] }
  entropy_score:   { type: float, range: [0.0, 1.0] }
  concentration_ratio: { type: float, range: [0.0, 1.0] }
  concept_count:   { type: integer }
  edge_count:      { type: integer }
  gravity_wells:   { type: list[GravityWell] }
  orphan_clusters: { type: list[OrphanCluster] }
  surface_candidates: { type: list[SurfaceCandidate] }
  signals:         { type: list[GraphSignal] }
  spec_ref:        { type: string, const: "spec-172" }

GravityWell:
  concept_id:  { type: string }
  child_count: { type: integer }
  severity:    { type: enum, values: [warning, critical] }

OrphanCluster:
  cluster_id: { type: string }
  size:        { type: integer }
  members:     { type: list[string] }  # concept_ids

SurfaceCandidate:
  concept_id:      { type: string }
  potential_score: { type: float, range: [0.0, 1.0] }
  interaction_pct: { type: float }     # fraction of total volume

GraphSignal:
  id:           { type: string }
  type:         { type: enum, values: [split_signal, merge_signal, surface_signal, convergence_ok, health_report] }
  concept_id:   { type: string, nullable: true }
  cluster_id:   { type: string, nullable: true }
  severity:     { type: enum, values: [info, warning, critical] }
  created_at:   { type: string, format: iso8601 }
  resolved:     { type: boolean }
  resolved_at:  { type: string, format: iso8601, nullable: true }
  resolution:   { type: string, nullable: true }
  resolved_by:  { type: string, nullable: true }

ConceptConvergenceGuard:
  concept_id:  { type: string }
  reason:      { type: string }
  set_by:      { type: string }
  set_at:      { type: string, format: iso8601 }
```

Storage: snapshots and signals persisted in PostgreSQL. Computation draws from Neo4j (graph
structure) and PostgreSQL (interaction event counts).

---

## Scheduler Integration

The health computation runs automatically on a configurable cron interval (default: every
`GRAPH_HEALTH_INTERVAL_MINUTES=60`). The scheduler calls the same logic as
`POST /api/graph/health/compute`. Each run persists a `GraphHealthSnapshot` and emits new
signals only for conditions not already signalled-and-unresolved.

---

## Convergence Guard — Design Rationale

The hardest problem in self-balancing graphs is distinguishing **pathological collapse** (one
dominant idea by inertia) from **genuine convergence** (multiple ideas that are truly equivalent
or subsumable). The `convergence_guard` solves this by requiring **explicit human or agent
intent**. A concept flagged with `convergence_guard = true` will:

- Not generate `split_signal` regardless of child count.
- Still appear in `health_report` with a `convergence_ok` signal so observers can see the
  exemption.
- Still be tracked in the `roi` endpoint to measure how often guards are set vs. reversed
  (a high reversal rate indicates over-protection).

Guards expire after 90 days unless renewed, preventing stale exemptions.

---

## Acceptance Criteria

1. `GET /api/graph/health` returns HTTP 200 with all required fields including `balance_score`,
   `entropy_score`, `concentration_ratio`, `gravity_wells`, `orphan_clusters`,
   `surface_candidates`, `signals`, and `spec_ref: "spec-172"`.
2. `POST /api/graph/health/compute` returns HTTP 200 with a freshly computed snapshot;
   a second call within 30 s returns HTTP 429.
3. `GET /api/graph/health/history` returns paginated snapshots; `?limit=2` returns exactly 2
   items with `total` reflecting the full count.
4. `GET /api/graph/signals` returns only un-resolved signals by default; `?type=split_signal`
   filters correctly; `?severity=critical` returns only critical-severity signals.
5. `POST /api/graph/signals/{signal_id}/resolve` with a valid body returns HTTP 200, sets
   `resolved: true`, `resolved_at`, `resolution`; a second resolve on the same signal returns
   HTTP 409.
6. `POST /api/graph/concepts/{concept_id}/convergence-guard` sets the guard; subsequent
   `GET /api/graph/health` does NOT emit a `split_signal` for that concept even if its
   child count is above threshold.
7. `DELETE /api/graph/concepts/{concept_id}/convergence-guard` removes the guard; the next
   health computation re-evaluates and may re-emit `split_signal`.
8. `GET /api/graph/health/roi` returns HTTP 200 with `balance_score_delta`,
   `entropy_score_delta`, `split_signals_actioned`, and `spec_ref: "spec-172"`.
9. A concept with `child_count ≥ 25` (critical threshold) always appears in `gravity_wells`
   with `severity: "critical"` in `GET /api/graph/health`.
10. A concept with `interaction_pct < 0.01` and `potential_score > 0.75` appears in
    `surface_candidates`.
11. All 15 integration tests in `api/tests/test_graph_health.py` pass.
12. `cc graph-health` CLI command prints a one-line status:
    `Graph: balance=<score> entropy=<score> signals=<N> [HEALTHY|WARNING|CRITICAL]`.

---

## Files to Create/Modify

| File | Action |
|------|--------|
| `api/app/routers/graph_health.py` | New — all `/api/graph/health` and `/api/graph/signals` routes |
| `api/app/services/graph_health_service.py` | New — computation logic, metric calculators |
| `api/app/models/graph_health.py` | New — Pydantic models for all response schemas |
| `api/app/db/graph_health_repo.py` | New — PostgreSQL persistence for snapshots and signals |
| `api/app/main.py` | Modify — register `graph_health` router |
| `api/app/routers/graph.py` | Modify (if exists) — cross-link health endpoint from graph router |
| `api/tests/test_graph_health.py` | New — 15 integration tests |
| `docs/graph-health-runbook.md` | New — operational runbook for interpreting signals |

---

## Verification Scenarios

### Scenario 1 — Health snapshot returns all required fields

**Setup**: A running API with at least 5 concept nodes and at least 1 edge in Neo4j.

**Action**:
```bash
curl -s https://api.coherencycoin.com/api/graph/health | python3 -m json.tool
```

**Expected**: HTTP 200. Response contains keys `balance_score` (float 0.0–1.0),
`entropy_score` (float 0.0–1.0), `concentration_ratio` (float 0.0–1.0), `concept_count`
(int ≥ 5), `gravity_wells` (list), `orphan_clusters` (list), `surface_candidates` (list),
`signals` (list), `computed_at` (ISO 8601 string), `spec_ref: "spec-172"`.

**Edge case**: If Neo4j is unreachable, response is HTTP 503 with
`{ "detail": "Graph database unavailable", "spec_ref": "spec-172" }` — not 500.

---

### Scenario 2 — Gravity well detection and split signal

**Setup**: Create a concept with 20 child edges (above the 15-node warning threshold):
```bash
# Create parent concept
curl -s -X POST https://api.coherencycoin.com/api/concepts \
  -H 'Content-Type: application/json' \
  -d '{"id":"test-gravity-well","name":"Test Gravity Well"}'

# Create 20 children and link them
for i in $(seq 1 20); do
  curl -s -X POST https://api.coherencycoin.com/api/concepts \
    -H 'Content-Type: application/json' \
    -d "{\"id\":\"child-$i\",\"name\":\"Child $i\"}"
  curl -s -X POST https://api.coherencycoin.com/api/edges \
    -H 'Content-Type: application/json' \
    -d "{\"from\":\"test-gravity-well\",\"to\":\"child-$i\",\"type\":\"has_child\"}"
done

# Trigger health computation
curl -s -X POST https://api.coherencycoin.com/api/graph/health/compute
```

**Action**:
```bash
curl -s https://api.coherencycoin.com/api/graph/signals?type=split_signal
```

**Expected**: Response contains at least one signal with `type: "split_signal"`,
`concept_id: "test-gravity-well"`, `severity: "warning"`, `resolved: false`.

**Edge case**: Calling `POST /api/graph/health/compute` again within 30 s returns HTTP 429
with `{ "detail": "Computation already in flight or cooling down" }`.

---

### Scenario 3 — Convergence guard suppresses split signal

**Setup**: Concept `test-gravity-well` from Scenario 2 exists with 20 children and an
active `split_signal`.

**Action**:
```bash
# Set convergence guard
curl -s -X POST https://api.coherencycoin.com/api/graph/concepts/test-gravity-well/convergence-guard \
  -H 'Content-Type: application/json' \
  -d '{"reason":"Genuine convergence in progress","set_by":"operator-1"}'

# Trigger recompute
curl -s -X POST https://api.coherencycoin.com/api/graph/health/compute

# Check signals
curl -s "https://api.coherencycoin.com/api/graph/signals?type=split_signal"
```

**Expected**:
- Guard POST returns HTTP 200 with `convergence_guard: true`.
- After recompute, `GET /api/graph/signals?type=split_signal` returns 0 unresolved split
  signals for `test-gravity-well`.
- `GET /api/graph/health` response contains `signals` with a `convergence_ok` entry for
  `test-gravity-well`.

**Edge case**: Attempting to set a guard on a non-existent concept returns HTTP 404.

---

### Scenario 4 — Surface signal for neglected high-potential concept

**Setup**: A concept `formal-verification` exists but has received < 1 % of interaction volume
over the last 30 days, while its `potential_score` (computed from edge richness and semantic
weight) is ≥ 0.75.

**Action**:
```bash
curl -s https://api.coherencycoin.com/api/graph/health | \
  python3 -c "import sys,json; h=json.load(sys.stdin); \
  print([c for c in h['surface_candidates'] if c['concept_id']=='formal-verification'])"
```

**Expected**: Output is a non-empty list containing an entry with
`concept_id: "formal-verification"`, `potential_score ≥ 0.75`, `interaction_pct < 0.01`.
`GET /api/graph/signals?type=surface_signal` also contains a signal for this concept.

**Edge case**: If no concept meets the surface criteria, `surface_candidates` is an empty
list `[]` (not null, not 404).

---

### Scenario 5 — Signal resolution lifecycle and ROI endpoint

**Setup**: At least one `split_signal` exists in an unresolved state (from Scenario 2).

**Action**:
```bash
# Get signal id
SIG_ID=$(curl -s "https://api.coherencycoin.com/api/graph/signals?type=split_signal" | \
  python3 -c "import sys,json; sigs=json.load(sys.stdin)['signals']; print(sigs[0]['id'])")

# Resolve it
curl -s -X POST "https://api.coherencycoin.com/api/graph/signals/$SIG_ID/resolve" \
  -H 'Content-Type: application/json' \
  -d '{"resolution":"Split into 3 sub-concepts: A, B, C","resolved_by":"operator-1"}'

# Try to resolve again (should fail)
curl -s -X POST "https://api.coherencycoin.com/api/graph/signals/$SIG_ID/resolve" \
  -H 'Content-Type: application/json' \
  -d '{"resolution":"duplicate","resolved_by":"operator-1"}'

# Check ROI
curl -s https://api.coherencycoin.com/api/graph/health/roi
```

**Expected**:
- First resolve: HTTP 200, `resolved: true`, `resolved_at` present.
- Second resolve: HTTP 409 `{ "detail": "Signal already resolved" }`.
- ROI endpoint: HTTP 200, `split_signals_actioned ≥ 1`, `spec_ref: "spec-172"`,
  all numeric fields are finite floats or integers (not null).

**Edge case**: Resolving a non-existent signal ID returns HTTP 404.

---

## Out of Scope

- Automatic splitting or merging of concepts — the spec emits **signals only**; humans or
  agents act on them. Automated structural mutation is a follow-up task.
- ML-based potential score computation — `potential_score` in v1 uses a deterministic formula
  (edge count × recency weight × connection diversity). ML scoring is a follow-up.
- UI components — no web front-end changes in this spec; signals are readable via the API
  and CLI only.
- Per-contributor health attribution — identifying which contributor caused a gravity well
  is a follow-up (spec-173 candidate).

---

## Risks and Assumptions

- **Risk**: Graph traversal for entropy computation is O(N·E) and may be slow on large graphs.
  Mitigation: cache the last snapshot and only recompute on the scheduled interval (or on
  explicit `POST /compute`); add a 10 s timeout.
- **Risk**: Convergence guards are set and never removed, creating permanent blind spots.
  Mitigation: guards expire after 90 days and appear prominently in `health_report` and the
  `roi` endpoint.
- **Risk**: The entropy formula penalises genuine topic leaders (e.g. a breakthrough idea
  legitimately dominating the network). Mitigation: the `concentration_ratio` threshold of
  0.80 is deliberately high; 3 ideas at 26 % each (balanced dominance) would score 0.78 —
  under the critical threshold.
- **Assumption**: Neo4j is accessible from the API service. If not, `GET /api/graph/health`
  returns 503, not 500 (graceful degradation).
- **Assumption**: Interaction event counts are available in PostgreSQL (written by existing
  pipeline). If the table is empty, `concentration_ratio` defaults to 0.0 and a warning
  is added to the snapshot.

---

## Known Gaps and Follow-up Tasks

- `spec-173-auto-split-merge`: Implement automatic structural mutations triggered by critical
  signals after a cooldown period and human-in-the-loop confirmation.
- `spec-174-graph-health-dashboard`: Web UI panel showing live balance score, entropy
  history chart, and active signals with one-click resolve.
- `spec-175-ml-potential-score`: Replace deterministic `potential_score` with an embedding-
  based model trained on historical concept trajectories.
- `Follow-up task`: Define `potential_score` weighting coefficients with the community before
  implementation; current deterministic formula is a placeholder.

---

## Task Card

```yaml
goal: Implement graph health monitoring with shape metrics, balance signals, and convergence guard
files_allowed:
  - api/app/routers/graph_health.py
  - api/app/services/graph_health_service.py
  - api/app/models/graph_health.py
  - api/app/db/graph_health_repo.py
  - api/app/main.py
  - api/tests/test_graph_health.py
  - docs/graph-health-runbook.md
done_when:
  - GET /api/graph/health returns 200 with balance_score, entropy_score, spec_ref
  - POST /api/graph/health/compute returns 200, second call within 30s returns 429
  - convergence-guard POST suppresses split_signal in subsequent health snapshot
  - GET /api/graph/health/roi returns 200 with spec_ref: "spec-172"
  - all 15 tests in api/tests/test_graph_health.py pass
commands:
  - cd api && pytest -q tests/test_graph_health.py
  - curl -s https://api.coherencycoin.com/api/graph/health | python3 -m json.tool
constraints:
  - Do not auto-mutate graph structure; emit signals only
  - convergence_guard must expire after 90 days
  - health computation must time out at 10 s with 503 on timeout
  - All response models are Pydantic; no raw dicts returned from routes
```

---

## Failure/Retry Reflection

- **Failure mode**: entropy computation hangs on deeply recursive Neo4j traversal.
  **Blind spot**: forgot that some graph topologies have very long chains.
  **Next action**: add explicit traversal depth limit (max 8 hops) and a 10 s query timeout.

- **Failure mode**: `convergence_guard` is set but the recompute still emits split_signal.
  **Blind spot**: guard check not applied before signal generation, only after.
  **Next action**: ensure guard is checked in `should_emit_split_signal()` before appending to signals list.

- **Failure mode**: ROI endpoint shows `0` for all actioned counts on first deploy.
  **Blind spot**: ROI looks back 30 days but system has no history yet.
  **Next action**: ROI endpoint must handle zero-history gracefully: return 0 counts with a
  `"note": "Insufficient history — check back after first full measurement period"` field.

---

## Concurrency Behavior

- **Read operations** (`GET /health`, `GET /signals`): safe for concurrent access; no locking.
- **Compute operation** (`POST /compute`): single-flight enforced via an in-memory lock with
  30 s cooldown. Concurrent requests return 429.
- **Signal resolution** (`POST /resolve`): last-write-wins is insufficient; use a `resolved`
  boolean check before update and return 409 on conflict.

---

## Decision Gates

- Community or operator must confirm `split_threshold` (default 15) and `orphan_max_size`
  (default 5) before the scheduler is enabled in production. These values should be
  configurable via environment variables `GRAPH_SPLIT_THRESHOLD` and `GRAPH_ORPHAN_MAX_SIZE`.
- The `potential_score` formula must be reviewed and agreed upon before v1 ships — even a
  deterministic formula has implicit value judgements about what makes a concept "high potential".
