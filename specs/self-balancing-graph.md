# Spec: Self-Balancing Graph — Operational Proof

**Spec ID**: self-balancing-graph
**Idea ID**: `self-balancing-graph`
**Parent Idea**: `fractal-ontology-core`
**Sister Ideas**: `edge-navigation`, `concept-translation-views`, `belief-system-interface`, `source-to-idea-lineage`, `full-traceability-chain`, `metadata-self-discovery`
**Task ID**: `task_34eb435c3873f117`
**Status**: draft
**Date**: `2026-03-30`
**Depends on**: `specs/172-fractal-self-balance.md`, `specs/fractal-self-balance.md`

---

## Summary

The self-balancing graph layer already computes health snapshots that detect gravity wells (overloaded concepts), orphan clusters (disconnected fragments), and surface candidates (neglected high-potential branches). This spec extends that foundation with three missing pieces that answer the question "is it working?":

1. **Anti-collapse trigger at 80% concentration** — when the top 3 concepts capture ≥80% of graph energy, the system MUST surface candidates and emit `surface_signal` events. The 80% threshold is the operational definition of "energy collapse into 3 ideas."
2. **Proof ledger** — a time-series of health snapshots that proves the graph's shape is improving or degrading over time, with trend classification (improving / degrading / stable).
3. **Convergence validation** — after a reviewer marks a concept as intentionally dense (via convergence guard), subsequent snapshots must show that concept excluded from `split_signal` generation, and the ROI delta must reflect the reviewer's intervention.

This spec does NOT add automatic split/merge execution. The system advises; reviewers decide.

---

## Purpose

Existing graph-health specs (`spec-172`, `fractal-self-balance`) define what metrics the system computes. This spec answers the operational question: **given those metrics, how does the system prove it is self-balancing?**

The core open question in the idea description was: *"How can we improve this idea, show whether it is working yet, and make that proof clearer over time?"* This spec answers that with a structured proof ledger, a trend classification engine, and explicit validation endpoints that reviewers can audit.

---

## Requirements

- [ ] `GET /api/graph/health/trend` returns the last N snapshots (default 10) with `balance_score` series, `entropy_score` series, `concentration_ratio` series, and a `trend_classification` enum: `improving`, `degrading`, or `stable`.
- [ ] `trend_classification` is computed as: if the slope of `balance_score` over the snapshot window is positive → `improving`; negative → `degrading`; else `stable`. The window size is configurable via `?window=N` (max 100).
- [ ] `GET /api/graph/health/proof` returns a machine-readable proof record with: `first_computed_at`, `latest_computed_at`, `snapshot_count`, `balance_score_start`, `balance_score_latest`, `balance_score_delta`, `entropy_score_start`, `entropy_score_latest`, `concentration_ratio_start`, `concentration_ratio_latest`, `total_split_signals_emitted`, `total_merge_signals_emitted`, `total_surface_signals_emitted`, `split_signals_suppressed_by_guard`, and `spec_ref`.
- [ ] The `surface_signal` emission trigger is tightened so that any `concentration_ratio >= 0.80` (80%) MUST produce at least one `surface_signal`. The previous threshold of `0.55` is raised; the new 80% trigger is the explicit anti-collapse operational threshold matching the idea description.
- [ ] `POST /api/graph/health/compute` on a graph where top-3 concentration exceeds 80% MUST return non-empty `surface_candidates` and emit `surface_signal` events. This is a regression guard: if no candidates are surfaced at 80% concentration, the compute is considered failed.
- [ ] `GET /api/graph/health/convergence/{concept_id}` returns whether a convergence guard is active for that concept, how many times it suppressed a `split_signal`, and the guard's `reason` and `set_by`.
- [ ] Snapshots are persisted in `graph_health_repo` with a maximum window of 200 entries (older entries are evicted oldest-first) so the proof ledger is always bounded.
- [ ] `GET /api/graph/health/trend` returns HTTP 200 with the full trend record even when fewer than 2 snapshots exist (returns a `stable` classification and empty series with `snapshot_count: 0`).
- [ ] `balance_score_delta` in the proof record equals `balance_score_latest - balance_score_start`. Delta can be negative, zero, or positive.

---

## Research Inputs

- `2026-03-28` - `specs/172-fractal-self-balance.md` — baseline health computation (entropy, concentration, balance score, gravity wells, orphan clusters, surface candidates)
- `2026-03-28` - `specs/fractal-self-balance.md` — convergence guard extension with reviewer override workflow
- `2026-03-28` - `api/tests/test_172_graph_health.py` — existing endpoint and metric acceptance tests for the health computation layer
- `2026-03-28` - `api/app/services/graph_health_service.py` — current implementation with SPLIT_THRESHOLD=10, SPLIT_CRITICAL=15, and `_surface_candidates` threshold at 0.55

---

## Task Card

```yaml
goal: Write the self-balancing-graph operational proof spec that answers "is it working?" with a proof ledger, trend classification, and 80% concentration trigger.
files_allowed:
  - specs/self-balancing-graph.md
  - .gitignore
  - .task-checkpoint.md
  - .idea-progress.md
  - docs/system_audit/commit_evidence_2026-03-30_self-balancing-graph.json
  - docs/system_audit/model_executor_runs.jsonl
done_when:
  - specs/self-balancing-graph.md exists with all required sections (Summary, Requirements, API Changes, Data Model, Verification Scenarios, Risks and Assumptions, Known Gaps)
  - python scripts/validate_spec_quality.py --file specs/self-balancing-graph.md exits 0
  - git commit created
  - all checklist items in the spec header verified
commands:
  - python scripts/validate_spec_quality.py --file specs/self-balancing-graph.md
  - git diff --cached --stat
constraints:
  - spec only — no implementation changes in this task
  - do not modify existing test files
  - scope limited to proof ledger, trend classification, 80% concentration trigger, and convergence validation
```

---

## API Changes

### `GET /api/graph/health/trend`

Returns the health snapshot trend over the configured window.

**Query parameters**
- `window` (int, optional, default=10, max=100): number of snapshots to include in the trend.

**Response 200**
```json
{
  "snapshot_count": 7,
  "window": 10,
  "balance_score_series": [0.65, 0.68, 0.70, 0.72, 0.71, 0.74, 0.76],
  "entropy_score_series": [0.55, 0.57, 0.60, 0.62, 0.61, 0.64, 0.67],
  "concentration_ratio_series": [0.82, 0.80, 0.78, 0.76, 0.75, 0.73, 0.71],
  "trend_classification": "improving",
  "balance_score_slope": 0.018,
  "first_computed_at": "2026-03-28T00:00:00Z",
  "latest_computed_at": "2026-03-30T12:00:00Z"
}
```

**Response when fewer than 2 snapshots**
```json
{
  "snapshot_count": 1,
  "window": 10,
  "balance_score_series": [0.74],
  "entropy_score_series": [0.68],
  "concentration_ratio_series": [0.41],
  "trend_classification": "stable",
  "balance_score_slope": 0.0,
  "first_computed_at": "2026-03-30T10:00:00Z",
  "latest_computed_at": "2026-03-30T10:00:00Z"
}
```

### `GET /api/graph/health/proof`

Returns a machine-readable proof record proving whether the self-balancing graph is working.

**Response 200**
```json
{
  "first_computed_at": "2026-03-28T00:00:00Z",
  "latest_computed_at": "2026-03-30T12:00:00Z",
  "snapshot_count": 47,
  "balance_score_start": 0.52,
  "balance_score_latest": 0.74,
  "balance_score_delta": 0.22,
  "entropy_score_start": 0.41,
  "entropy_score_latest": 0.68,
  "concentration_ratio_start": 0.85,
  "concentration_ratio_latest": 0.71,
  "total_split_signals_emitted": 12,
  "total_merge_signals_emitted": 3,
  "total_surface_signals_emitted": 19,
  "split_signals_suppressed_by_guard": 2,
  "spec_ref": "self-balancing-graph"
}
```

**Edge: no snapshots yet**
```json
{
  "first_computed_at": null,
  "latest_computed_at": null,
  "snapshot_count": 0,
  "balance_score_start": null,
  "balance_score_latest": null,
  "balance_score_delta": null,
  "entropy_score_start": null,
  "entropy_score_latest": null,
  "concentration_ratio_start": null,
  "concentration_ratio_latest": null,
  "total_split_signals_emitted": 0,
  "total_merge_signals_emitted": 0,
  "total_surface_signals_emitted": 0,
  "split_signals_suppressed_by_guard": 0,
  "spec_ref": "self-balancing-graph"
}
```

### `GET /api/graph/health/convergence/{concept_id}`

Returns convergence guard status and signal suppression count for a specific concept.

**Response 200**
```json
{
  "concept_id": "concept-0",
  "guard_active": true,
  "reason": "Intentional fractal depth",
  "set_by": "reviewer",
  "set_at": "2026-03-29T10:00:00Z",
  "split_signals_suppressed": 5
}
```

**Response 404 (no guard active)**
```json
{
  "concept_id": "concept-0",
  "guard_active": false,
  "reason": null,
  "set_by": null,
  "set_at": null,
  "split_signals_suppressed": 0
}
```

### `POST /api/graph/health/compute` — Updated Behavior

When `concentration_ratio >= 0.80` after computation, the response MUST contain:
- At least one entry in `surface_candidates`
- At least one signal of type `surface_signal` in `signals`

**If `concentration_ratio >= 0.80` and `surface_candidates` is empty**, the compute is considered a failure condition. The service should return HTTP 200 with the full snapshot but log a warning that the 80% anti-collapse trigger failed to surface candidates.

---

## Data Model

```yaml
HealthTrend:
  snapshot_count: integer
  window: integer
  balance_score_series: float[]
  entropy_score_series: float[]
  concentration_ratio_series: float[]
  trend_classification: enum[improving, degrading, stable]
  balance_score_slope: float
  first_computed_at: datetime | null
  latest_computed_at: datetime | null

HealthProof:
  first_computed_at: datetime | null
  latest_computed_at: datetime | null
  snapshot_count: integer
  balance_score_start: float | null
  balance_score_latest: float | null
  balance_score_delta: float | null
  entropy_score_start: float | null
  entropy_score_latest: float | null
  concentration_ratio_start: float | null
  concentration_ratio_latest: float | null
  total_split_signals_emitted: integer
  total_merge_signals_emitted: integer
  total_surface_signals_emitted: integer
  split_signals_suppressed_by_guard: integer
  spec_ref: string

ConvergenceStatus:
  concept_id: string
  guard_active: boolean
  reason: string | null
  set_by: string | null
  set_at: datetime | null
  split_signals_suppressed: integer
```

**Snapshot history entry (internal)**

```yaml
SnapshotRecord:
  id: string
  balance_score: float
  entropy_score: float
  concentration_ratio: float
  gravity_wells: GravityWell[]
  orphan_clusters: OrphanCluster[]
  surface_candidates: SurfaceCandidate[]
  signals: GraphSignal[]
  computed_at: datetime
  split_signals_suppressed_count: integer
```

---

## Files to Create/Modify

- `api/app/routers/graph_health.py` — add `GET /api/graph/health/trend`, `GET /api/graph/health/proof`, `GET /api/graph/health/convergence/{concept_id}` routes
- `api/app/services/graph_health_service.py` — add `get_trend(window: int)`, `get_proof()`, `convergence_status(concept_id: str)`, update `_surface_candidates` threshold from `0.55` to `0.80`, update `_surface_candidates` to always emit `surface_signal` when concentration >= 0.80
- `api/app/db/graph_health_repo.py` — add snapshot history storage (bounded to 200 entries), add `get_snapshot_history(window: int)`, add `get_proof_record()`, add `increment_guard_suppression_count(concept_id: str)`
- `api/tests/test_self_balancing_graph_proof.py` — new test file for trend, proof, and convergence endpoints

---

## Acceptance Tests

The following test commands (manual validation) and integration test references prove the spec is implemented:

```bash
# Trend endpoint — empty graph returns stable classification
curl -s http://localhost:8000/api/graph/health/trend | jq '.trend_classification'
# Expected: "stable"

# Proof endpoint — returns spec_ref
curl -s http://localhost:8000/api/graph/health/proof | jq '.spec_ref'
# Expected: "self-balancing-graph"

# Convergence status endpoint
curl -s http://localhost:8000/api/graph/health/convergence/concept-0 | jq '.guard_active'
# Expected: false (no guard yet)

# Integration tests:
python -m pytest api/tests/test_self_balancing_graph_proof.py -q
```

## Verification Scenarios

### Scenario 1: Empty graph — trend returns stable classification

**Setup**: No concepts or edges exist; no health snapshots have been computed.
**Action**: `curl -s http://localhost:8000/api/graph/health/trend`
**Expected**: HTTP 200, `trend_classification: "stable"`, `snapshot_count: 0`, all series arrays are empty.
**Edge**: Request with `?window=50` returns the same stable response with `window: 50`.

### Scenario 2: High-concentration graph triggers surface candidates at 80%

**Setup**: Build a graph where top-3 concepts hold ≥80% of engagement (e.g., 20 children under concept-0, 5 orphan nodes elsewhere).
**Action**: `curl -s -X POST http://localhost:8000/api/graph/health/compute`
**Expected**: HTTP 200, `concentration_ratio >= 0.80`, `surface_candidates` is a non-empty list, `signals` contains at least one `surface_signal`.
**Edge**: Immediately call `POST /api/graph/health/compute` again on the same graph — `computed_at` must be newer, `surface_candidates` may be the same or different but cannot be empty if concentration is still ≥0.80.

### Scenario 3: Convergence guard suppresses split signal

**Setup**: Graph with a concept (concept-0) having ≥10 children (SPLIT_THRESHOLD=10).
**Action 1**: `curl -s -X POST http://localhost:8000/api/graph/health/compute` — verify `split_signal` is present for concept-0.
**Action 2**: `curl -s -X POST http://localhost:8000/api/graph/concepts/concept-0/convergence-guard -d '{"reason":"intentional depth","set_by":"reviewer"}'` — verify HTTP 200 with `guard_active: true`.
**Action 3**: `curl -s -X POST http://localhost:8000/api/graph/health/compute` — verify `split_signal` is absent for concept-0 and `signals` contains `convergence_ok` instead.
**Action 4**: `curl -s http://localhost:8000/api/graph/health/convergence/concept-0` — verify `guard_active: true`, `split_signals_suppressed >= 1`.

### Scenario 4: Proof record shows delta improvement over time

**Setup**: Run compute at least 3 times with different graph states so balance_score changes.
**Action**: `curl -s http://localhost:8000/api/graph/health/proof`
**Expected**: HTTP 200, `snapshot_count >= 3`, `balance_score_start` and `balance_score_latest` are both non-null, `balance_score_delta = balance_score_latest - balance_score_start`.
**Edge**: If no snapshots exist, all numeric fields are null, `snapshot_count: 0`, `spec_ref: "self-balancing-graph"`.

### Scenario 5: Trend classification is improving

**Setup**: Run compute 5 times with progressively improving balance_score (e.g., reduce concentration, add surface candidates).
**Action**: `curl -s "http://localhost:8000/api/graph/health/trend?window=5"`
**Expected**: HTTP 200, `trend_classification: "improving"`, `balance_score_slope > 0`, `balance_score_series` shows monotonic increase.
**Edge**: Request with `?window=1000` when fewer than 1000 snapshots exist returns available snapshots with `window` reflecting actual count (not capped to 100).

---

## Out of Scope

- Automatic split or merge execution based on signals.
- Graph rewrite operations or edge mutations triggered by health computation.
- UI dashboards or visualization of the trend or proof data.
- Background schedulers that auto-compute snapshots.
- Persistence of the snapshot history beyond the 200-entry rolling window.
- Financial or payout logic based on balance scores.

---

## Risks and Assumptions

- **Risk**: The 80% threshold for `surface_signal` emission may be too lenient for small graphs (where 3 nodes with equal energy trivially meet 80% concentration).  
  **Mitigation**: The threshold applies to engagement-weighted counts, not raw node counts. Small graphs with diverse engagement will not falsely trigger. Document that graphs with fewer than 5 total concepts may produce noisy concentration readings.
- **Risk**: The trend slope is sensitive to the most recent snapshot; a single bad compute can flip `improving` to `degrading`.  
  **Mitigation**: Require at least 3 snapshots before reporting a non-`stable` classification. With fewer than 3 snapshots, always return `stable`.
- **Risk**: Suppression count for convergence guards resets on process restart because it is stored in-memory.  
  **Mitigation**: Persist the suppression count in `graph_health_repo` so it survives restarts.
- **Assumption**: The existing graph-health service (`graph_health_service.py`) can be extended with a snapshot history ring buffer without requiring a database migration.
- **Assumption**: Signal counts (`total_split_signals_emitted`, etc.) can be derived by scanning the persisted snapshot history without needing a separate counter store.

---

## Known Gaps and Follow-up Tasks

- Follow-up: Add a `GET /api/graph/health/history?from=ISO&to=ISO` endpoint for time-range queries if the rolling window proof is insufficient for reviewers.
- Follow-up: Persist snapshot history to PostgreSQL/Neo4j if the 200-entry in-memory window is insufficient for long-running deployments.
- Follow-up: Add a `balance_score_goal` field so reviewers can set a target and the proof record can report goal achievement percentage.
- Follow-up: Add signal resolution tracking so `split_signals_actioned` and `merge_signals_actioned` in the ROI endpoint reflect actual reviewer decisions, not just signal counts.
- Follow-up: Calibrate the 80% threshold based on empirical data from production graphs once sufficient snapshot history exists.
