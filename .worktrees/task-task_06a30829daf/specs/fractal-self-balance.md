# Spec: Self-Balancing Graph

**Spec Ref**: `spec-172`  
**Idea ID**: `fractal-self-balance`  
**Task ID**: `task_93ab401c8b844b6d`  
**Status**: draft  
**Date**: `2026-03-28`

## Summary

Coherence Network needs a minimal graph-health layer that can detect when the intelligence graph is collapsing into a few oversized hubs or scattering into disconnected fragments. The core requirement is diagnostic, not autonomous mutation: the system must measure shape health, expose balancing signals, and preserve intentional convergence when a reviewer marks it as valid. This scope intentionally excludes any automatic graph rewrites, workflow orchestration, or UI work. The deliverable is a stable API and data contract for health snapshots, balancing signals, and a manual convergence guard.

## Purpose

This spec exists so the graph can describe its own structural health before the project attempts autonomous rebalancing. It gives implementation a narrow, testable contract for diagnosing collapse, fragmentation, and neglected branches without allowing the system to silently mutate the graph. The immediate beneficiary is the graph-health service layer, but the real protection is product-level: operators get visible signals, while genuine convergence patterns remain protected through an explicit reviewer override.

## Requirements

- [ ] `GET /api/graph/health` returns HTTP 200 at all times, including an empty graph, and includes `balance_score`, `entropy_score`, `concentration_ratio`, `gravity_wells`, `orphan_clusters`, `surface_candidates`, `signals`, and `computed_at`.
- [ ] `POST /api/graph/health/compute` recomputes the snapshot from the latest concept graph state and returns a fresh `computed_at` timestamp on every successful call.
- [ ] A concept whose outgoing child count is greater than or equal to `SPLIT_THRESHOLD` is reported as a gravity well and emits a `split_signal` unless the concept is protected by a convergence guard.
- [ ] A concept whose outgoing child count is greater than or equal to `SPLIT_CRITICAL` is marked with severity `critical`; otherwise threshold crossings use severity `warning`.
- [ ] Small disconnected clusters are reported as `orphan_clusters` and emit `merge_signal` records so operators can decide whether they should be merged, linked, or retired.
- [ ] Diversity is measured with a normalized Shannon entropy score over concept engagement counts, and concentration is measured as the share of engagement captured by the top three concepts.
- [ ] `surface_candidates` must always be present as a list and should contain neglected but structurally promising branches when concentration is high.
- [ ] `balance_score` is a bounded value in `[0, 1]` using the minimal weighted formula: `0.4 * entropy + 0.3 * (1 - concentration) + 0.2 * orphan_health + 0.1 * (1 - gravity_pressure)`.
- [ ] `POST /api/graph/concepts/{concept_id}/convergence-guard` stores a reviewer-authored override with `reason` and `set_by`, suppresses `split_signal` generation for that concept, and emits a `convergence_ok` signal instead.
- [ ] `DELETE /api/graph/concepts/{concept_id}/convergence-guard` removes the override and makes the concept eligible for normal gravity-well detection again.
- [ ] `GET /api/graph/health/roi` returns `balance_score_delta`, `split_signals_actioned`, `merge_signals_actioned`, `surface_signals_actioned`, and a stable `spec_ref` of `spec-172`.
- [ ] Out of scope for this spec: automatic split/merge execution, background schedulers, graph rewrites, ranking UI, authentication changes, and non-core analytics.

## Research Inputs

- `2026-03-28` - `api/tests/test_fractal_self_balance.py` - Existing acceptance criteria for graph-health behavior, threshold rules, and signal semantics.
- `2026-03-28` - `specs/169-fractal-node-edge-primitives.md` - Graph vocabulary and adjacent graph-proof concepts that this feature must remain compatible with.

## Task Card

```yaml
goal: Define the minimal graph-health specification for self-balancing graph diagnostics and manual overrides.
files_allowed:
  - specs/fractal-self-balance.md
  - docs/system_audit/commit_evidence_2026-03-28_fractal-self-balance.json
  - docs/system_audit/model_executor_runs.jsonl
  - .gitignore
  - .task-checkpoint.md
done_when:
  - specs/fractal-self-balance.md exists and includes Summary, Requirements, API changes, Data model, Verification criteria, and Risks
  - docs/system_audit/commit_evidence_2026-03-28_fractal-self-balance.json validates with scripts/validate_commit_evidence.py
  - the required git add, diff, and commit commands complete without committing unrelated in-flight work
commands:
  - python scripts/validate_commit_evidence.py --file docs/system_audit/commit_evidence_2026-03-28_fractal-self-balance.json
  - python scripts/validate_spec_quality.py --file specs/fractal-self-balance.md
constraints:
  - no implementation changes
  - no test changes
  - no extra files beyond the listed scope
```

## API changes

### `GET /api/graph/health`

Returns the latest graph-health snapshot. If no compute has run yet, the endpoint returns an empty-but-valid snapshot with zeroed metrics and empty lists.

**Response 200**

```json
{
  "balance_score": 0.0,
  "entropy_score": 0.0,
  "concentration_ratio": 0.0,
  "gravity_wells": [],
  "orphan_clusters": [],
  "surface_candidates": [],
  "signals": [],
  "computed_at": "2026-03-28T00:00:00Z"
}
```

### `POST /api/graph/health/compute`

Recomputes graph-health metrics from the current concept and edge graph.

**Response 200**

```json
{
  "balance_score": 0.78,
  "entropy_score": 0.84,
  "concentration_ratio": 0.31,
  "gravity_wells": [
    { "concept_id": "concept-0", "child_count": 12, "severity": "warning" }
  ],
  "orphan_clusters": [],
  "surface_candidates": [
    { "concept_id": "concept-17", "reason": "low engagement but connected branch", "score": 0.67 }
  ],
  "signals": [
    { "id": "sig_123", "type": "split_signal", "concept_id": "concept-0", "severity": "warning" }
  ],
  "computed_at": "2026-03-28T00:05:00Z"
}
```

### `POST /api/graph/concepts/{concept_id}/convergence-guard`

Marks an intentionally convergent concept so that future compute runs do not treat it as an unhealthy gravity well.

**Request**

```json
{
  "reason": "Intentional fractal depth",
  "set_by": "reviewer"
}
```

**Response 200**

```json
{
  "concept_id": "concept-0",
  "convergence_guard": true,
  "reason": "Intentional fractal depth",
  "set_by": "reviewer"
}
```

### `DELETE /api/graph/concepts/{concept_id}/convergence-guard`

Removes the guard and restores normal split detection for the concept.

**Response 200**

```json
{
  "concept_id": "concept-0",
  "convergence_guard": false
}
```

### `GET /api/graph/health/roi`

Returns whether balancing actions are improving the graph over time.

**Response 200**

```json
{
  "balance_score_delta": 0.12,
  "split_signals_actioned": 3,
  "merge_signals_actioned": 1,
  "surface_signals_actioned": 4,
  "spec_ref": "spec-172"
}
```

## Data model

```yaml
GraphHealthSnapshot:
  properties:
    balance_score: { type: float, minimum: 0.0, maximum: 1.0 }
    entropy_score: { type: float, minimum: 0.0, maximum: 1.0 }
    concentration_ratio: { type: float, minimum: 0.0, maximum: 1.0 }
    gravity_wells: { type: list[GravityWell] }
    orphan_clusters: { type: list[OrphanCluster] }
    surface_candidates: { type: list[SurfaceCandidate] }
    signals: { type: list[GraphSignal] }
    computed_at: { type: datetime }

GravityWell:
  properties:
    concept_id: { type: string }
    child_count: { type: integer, minimum: 0 }
    severity: { type: enum[warning, critical] }

OrphanCluster:
  properties:
    cluster_id: { type: string }
    concept_ids: { type: list[string] }
    size: { type: integer, minimum: 1 }
    severity: { type: enum[warning, critical] }

SurfaceCandidate:
  properties:
    concept_id: { type: string }
    reason: { type: string }
    score: { type: float, minimum: 0.0, maximum: 1.0 }

GraphSignal:
  properties:
    id: { type: string }
    type: { type: enum[split_signal, merge_signal, surface_signal, convergence_ok] }
    concept_id: { type: string, nullable: true }
    cluster_id: { type: string, nullable: true }
    severity: { type: enum[info, warning, critical] }
    created_at: { type: datetime }
    resolved: { type: boolean }

ConvergenceGuard:
  properties:
    concept_id: { type: string }
    reason: { type: string }
    set_by: { type: string }
    created_at: { type: datetime }

GraphHealthROI:
  properties:
    balance_score_delta: { type: float }
    split_signals_actioned: { type: integer, minimum: 0 }
    merge_signals_actioned: { type: integer, minimum: 0 }
    surface_signals_actioned: { type: integer, minimum: 0 }
    spec_ref: { type: string }
```

Minimal persistence is acceptable. The feature may use the existing in-memory or lightweight repository layer for snapshots, signals, and guards. This spec does not require a new graph storage engine or a graph rewrite pipeline.

## Files to Create/Modify

- `api/app/routers/graph_health.py` - exposes health, compute, convergence-guard, and ROI endpoints.
- `api/app/services/graph_health_service.py` - computes entropy, concentration, balance score, and balancing signals.
- `api/app/models/graph_health.py` - defines snapshot, signal, guard, and ROI response models.
- `api/app/db/graph_health_repo.py` - stores the latest snapshot, signal state, and convergence guards for the minimal persistence path.
- `api/tests/test_fractal_self_balance.py` - concept-level acceptance coverage for the balancing contract.

## Acceptance Tests

- `python -m pytest api/tests/test_fractal_self_balance.py -q`
- Manual validation: seed a concentrated graph, call `POST /api/graph/health/compute`, and confirm the response contains a gravity well, a lowered `balance_score`, and at least one `surface_candidate`.
- Manual validation: apply `POST /api/graph/concepts/{concept_id}/convergence-guard`, rerun compute, and confirm the concept no longer emits `split_signal`.

## Verification criteria

- `python -m pytest api/tests/test_fractal_self_balance.py -q` passes.
- A compute call against an empty graph returns HTTP 200 with bounded numeric scores and list fields present.
- A compute call against a graph with `SPLIT_THRESHOLD` children under one concept returns a gravity well plus a `split_signal`.
- After adding a convergence guard to that same concept, the next compute call suppresses `split_signal` and emits `convergence_ok`.
- `GET /api/graph/health/roi` returns non-negative action counts and `spec_ref == "spec-172"`.
- `python scripts/validate_spec_quality.py --file specs/fractal-self-balance.md` passes.

## Out of Scope

- Automatic split, merge, or reparent operations on graph nodes.
- Background workers or scheduled recomputation jobs.
- Any UI surface for graph-health visualization.
- Ranking, payout, or moderation decisions driven directly by the health score.

## Risks

- A simple degree-based engagement model may mistake healthy convergence for collapse. Mitigation: convergence guard is part of the MVP and no automatic balancing action is allowed.
- Entropy and concentration are useful diagnostics, but they are not proof of idea quality. Mitigation: these metrics inform operator review only and must not directly delete or demote graph nodes.
- Snapshot freshness depends on explicit compute calls in this minimal scope. Mitigation: `GET /api/graph/health` remains stable and `POST /api/graph/health/compute` provides the authoritative refresh path.
- ROI counts may be noisy until action-resolution workflows are standardized. Mitigation: keep ROI to simple counters and a balance delta, not financial or ranking claims.

## Known Gaps and Follow-up Tasks

- None at spec time. Future tuning of thresholds and candidate-ranking heuristics should be handled in a separate implementation or calibration task.
