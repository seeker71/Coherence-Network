# Spec 172: Fractal Self Balance

**Spec ID**: 172-fractal-self-balance
**Idea ID**: fractal-self-balance
**Task ID**: task_7d32a1472d85f7f4
**Status**: draft
**Priority**: high
**Author**: product-manager agent
**Date**: 2026-03-28
**Depends on**: Spec 008 (Graph Foundation), Spec 166 (Universal Node + Edge Data Layer), Spec 169 (Fractal Node + Edge Primitives)

## Purpose

Define the minimum viable self-balancing layer for the Coherence graph. The goal is not to let the system mutate itself yet; the goal is to make graph shape visible, detect the simplest collapse patterns early, and produce advisory actions that help the network keep expanding without becoming a hub-and-spoke monoculture or a field of disconnected fragments.

## Summary

This spec adds a read-only graph health capability focused on three core failure modes: concentration collapse, orphan drift, and entropy loss. The MVP computes a fresh structural snapshot from the current concept graph, returns a normalized `balance_score`, and emits small advisory signals rather than automatic graph edits. Anti-collapse is covered by gravity-well detection when one concept accumulates too many children. Organic expansion is covered by surfacing under-linked branches that should receive attention. Entropy management is covered by concentration and entropy metrics that show whether graph energy is spreading across the network or collapsing into a few dominant nodes. Everything beyond that, including automatic split or merge actions and ROI dashboards, is out of scope for this retry.

## Requirements

- [ ] `GET /api/graph/health` returns HTTP 200 with a stable snapshot schema containing `balance_score`, `entropy_score`, `concentration_ratio`, `gravity_wells`, `orphan_clusters`, `surface_candidates`, and `computed_at`
- [ ] `POST /api/graph/health/compute` recomputes the snapshot from the current concept graph and returns the same schema; an empty graph returns zeros and empty arrays instead of failing
- [ ] A concept whose outgoing child count is greater than or equal to `SPLIT_THRESHOLD` is listed in `gravity_wells` with severity `warning` or `critical`
- [ ] A disconnected component with size less than or equal to `ORPHAN_CLUSTER_MAX_SIZE` is listed in `orphan_clusters` and emits a `merge_signal`
- [ ] When the top three concepts account for 80% or more of measured graph energy, the response includes `surface_candidates` drawn from under-linked non-orphan concepts
- [ ] The MVP is advisory only: no endpoint in this spec may split, merge, or rewrite concepts or edges automatically

## Research Inputs

- `2026-03-28` - [api/tests/test_fractal_self_balance.py](../api/tests/test_fractal_self_balance.py) - existing conceptual acceptance criteria already describe the intended anti-collapse and entropy behavior
- `2026-03-28` - [specs/166-universal-node-edge-layer.md](./166-universal-node-edge-layer.md) - establishes the graph layer this health pass should observe instead of bypassing
- `2026-03-28` - [specs/169-fractal-node-edge-primitives.md](./169-fractal-node-edge-primitives.md) - defines typed graph semantics and lifecycle context that make balancing signals interpretable

## Task Card

```yaml
goal: Write the minimal self-balancing graph spec for health computation and advisory anti-collapse signals.
files_allowed:
  - specs/172-fractal-self-balance.md
  - .gitignore
  - .task-checkpoint.md
  - docs/system_audit/commit_evidence_2026-03-28_fractal-self-balance-spec.json
  - docs/system_audit/model_executor_runs.jsonl
done_when:
  - specs/172-fractal-self-balance.md exists and includes Summary, Requirements, API Changes, Data Model, Verification criteria, and Risks
  - python scripts/validate_spec_quality.py --file specs/172-fractal-self-balance.md exits 0
  - required git add/diff/commit commands run successfully for the staged task files
commands:
  - python scripts/validate_spec_quality.py --file specs/172-fractal-self-balance.md
  - git diff --cached --stat
constraints:
  - spec only; no runtime code changes in this task
  - keep scope to read-only health computation and advisory signals
  - do not add automatic balancing, ROI tracking, or convergence overrides in this retry
```

## API Changes

### `GET /api/graph/health`

Returns the latest computed self-balance snapshot. If no snapshot has been computed yet in the current process, the service may compute one on demand or return an empty baseline snapshot; either path must return HTTP 200 with the same response model.

**Response 200**
```json
{
  "balance_score": 0.74,
  "entropy_score": 0.68,
  "concentration_ratio": 0.41,
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
      "node_ids": ["iso-0", "iso-1", "iso-2"],
      "size": 3
    }
  ],
  "surface_candidates": [
    {
      "concept_id": "concept-22",
      "reason": "low connectivity but high diversification value"
    }
  ],
  "signals": [
    {
      "type": "split_signal",
      "severity": "warning",
      "concept_id": "concept-0"
    },
    {
      "type": "merge_signal",
      "severity": "warning",
      "cluster_id": "cluster-1"
    }
  ],
  "computed_at": "2026-03-28T18:00:00Z"
}
```

### `POST /api/graph/health/compute`

Forces a fresh recomputation from the current concept graph and returns the new snapshot immediately.

**Request**
```json
{}
```

**Response 200**

Returns the same schema as `GET /api/graph/health`.

**Response behavior**
- Empty graph: `balance_score` may default to `1.0` or another documented neutral value, but it must stay within `0.0..1.0` and must not return 500
- Missing concept fields: skip malformed entries instead of crashing the whole computation

## Data Model

MVP requires no database migration. The balancing layer reads the existing concept graph and produces a process-local snapshot plus typed response models.

```yaml
GraphHealthSnapshot:
  balance_score: float
  entropy_score: float
  concentration_ratio: float
  gravity_wells: GravityWell[]
  orphan_clusters: OrphanCluster[]
  surface_candidates: SurfaceCandidate[]
  signals: GraphSignal[]
  computed_at: datetime

GravityWell:
  concept_id: string
  child_count: integer
  severity: string
  reason: string

OrphanCluster:
  cluster_id: string
  node_ids: string[]
  size: integer

SurfaceCandidate:
  concept_id: string
  reason: string

GraphSignal:
  type: string
  severity: string
  concept_id: string|null
  cluster_id: string|null
```

**Computation notes**
- `entropy_score` is derived from a normalized Shannon entropy over concept energy distribution
- `concentration_ratio` measures the share of total energy held by the top three concepts
- `balance_score` combines entropy, concentration, orphan pressure, and gravity-well pressure into one bounded health number

## Files to Create/Modify

- `api/app/models/graph_health.py` - response and signal models for health snapshots
- `api/app/services/graph_health_service.py` - graph-shape computation, entropy math, and advisory signal generation
- `api/app/routers/graph_health.py` - `GET /api/graph/health` and `POST /api/graph/health/compute`
- `api/tests/test_172_graph_health.py` - endpoint and metric acceptance tests for the MVP contract
- `specs/172-fractal-self-balance.md` - this spec

## Acceptance Tests

- `api/tests/test_172_graph_health.py::test_get_health_returns_shape_metrics`
- `api/tests/test_172_graph_health.py::test_compute_health_returns_empty_snapshot_for_empty_graph`
- `api/tests/test_172_graph_health.py::test_compute_health_flags_gravity_well_at_split_threshold`
- `api/tests/test_172_graph_health.py::test_compute_health_flags_small_orphan_cluster`
- `api/tests/test_172_graph_health.py::test_compute_health_surfaces_candidates_when_concentration_exceeds_80_percent`
- `api/tests/test_172_graph_health.py::test_balance_score_is_bounded_between_zero_and_one`

## Verification

```bash
python scripts/validate_spec_quality.py --file specs/172-fractal-self-balance.md
rg -n "^## (Summary|Requirements|API Changes|Data Model|Verification|Risks and Assumptions)$" specs/172-fractal-self-balance.md
git diff --cached --stat
```

## Verification Criteria

The spec is complete when:

1. The scope is limited to read-only health computation plus advisory signals.
2. The response contract is specific enough for router, model, and service implementation without inventing new behavior.
3. Optional ideas from the conceptual test file that are not core to anti-collapse, organic expansion, or entropy management are explicitly deferred.

## Out of Scope

- Automatic split, merge, or edge-rewrite operations
- Convergence guard endpoints and override workflow
- ROI/history endpoints that compare before-and-after balancing performance
- Scheduled background recomputation, persistence, or cross-worker snapshot sharing
- UI dashboards or alerting surfaces

## Risks and Assumptions

- **Risk**: Degree-based heuristics may flag intentional hubs as unhealthy.  
  **Mitigation**: MVP is advisory only; no graph mutation occurs from these signals.
- **Risk**: If the concept graph lacks reliable activity or weight data, entropy may overfit structural degree.  
  **Mitigation**: Start with simple structural metrics and document weight-aware balancing as follow-up work.
- **Risk**: Process-local snapshots may differ across workers.  
  **Mitigation**: Treat this MVP as local computation; persistence is explicitly deferred.

**Assumptions**
- Existing concept graph data can be read from the current service layer without schema changes.
- Child counts and component sizes are enough for the first anti-collapse pass.
- Reviewers prefer a narrow, implementable slice over a broad autonomous balancing system.

## Known Gaps and Follow-up Tasks

- Follow-up: add convergence guard support so intentionally dense concepts can be exempted from split signals.
- Follow-up: add `GET /api/graph/health/roi` once action history exists and the system can prove that balancing advice improved graph shape.
- Follow-up: persist snapshots and signals if multi-worker consistency becomes necessary.
- Follow-up: incorporate typed edges and lifecycle weighting from Spec 169 so balance scoring reflects more than raw structure.
