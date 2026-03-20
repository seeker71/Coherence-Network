# Spec 116: Grounded Idea Portfolio Metrics

**Idea**: `agent-grounded-idea-metrics` (sub-idea of `coherence-signal-depth`)
**Depends on**: Spec 115 (grounded measurement), Spec 049 (runtime telemetry), Spec 048 (value lineage)
**Integrates with**:
- `spec_registry_service` (actual_cost, actual_value per spec, linked by idea_id)
- `runtime_service` (usage adoption counts, runtime cost per idea)
- `value_lineage_service` (measured value from usage events per idea)
- `telemetry_persistence_service` (friction cost_of_delay per idea)
- `commit_evidence_service` (commit-level cost evidence per idea)

## Status: Implemented

## Problem

The idea portfolio (DEFAULT_IDEAS, DERIVED_IDEA_METADATA in `idea_service.py`) drives
every prioritization decision. Currently these numbers are all hand-typed:

| Field | Example | Source | Grounded? |
|-------|---------|--------|-----------|
| `potential_value` | 90.0 | Human guess | **No** |
| `actual_value` | 10.0 | Human guess | **No** |
| `estimated_cost` | 18.0 | Human guess | **No** |
| `actual_cost` | 0.0 | Not measured | **No** |
| `confidence` | 0.7 | Human guess | **No** |
| `resistance_risk` | 4.0 | Human guess | **No** |

If these numbers are wrong, we optimize the wrong things. We already have real data
flowing through 5+ services that can replace these guesses.

## Design

### Computed Metrics (all from observable data)

```
computed_actual_cost = sum(spec.actual_cost for specs linked to idea)
                    + runtime_cost_estimate (from runtime_service)
                    + sum(commit_cost for commits linked to idea)

computed_actual_value = max(
    lineage_measured_value,         # From value_lineage usage events
    usage_revenue,                  # From runtime event_count × $0.001
    spec_actual_value_sum,          # From spec_registry actual_value
)

computed_confidence = weighted_average(
    has_specs_with_tests    × 0.3,  # Observable: spec exists + tests pass
    has_runtime_data        × 0.25, # Observable: API calls recorded
    has_lineage_valuation   × 0.25, # Observable: usage events recorded
    has_commit_evidence     × 0.1,  # Observable: commits tracked
    has_friction_data       × 0.1,  # Observable: friction events exist
)

computed_estimated_cost = sum(spec.estimated_cost for specs linked to idea)
                        or original_estimate  # Keep human estimate as floor
```

### What stays human-supplied

- `potential_value`: Inherently a forecast. Keep as human target, but track
  `value_realization_pct = actual_value / potential_value` to flag over-optimistic forecasts.
- `resistance_risk`: Can be partially grounded later from PR review friction and CI failure rates.

### Transparency: raw signals alongside computed values

Every computed metric includes a `grounding_sources` dict so you can see exactly
what real data contributed:

```json
{
  "idea_id": "coherence-network-agent-pipeline",
  "computed_actual_cost": 12.5,
  "computed_actual_value": 35.2,
  "computed_confidence": 0.78,
  "value_realization_pct": 0.40,
  "grounding_sources": {
    "spec_count": 4,
    "spec_actual_cost_sum": 10.0,
    "spec_actual_value_sum": 22.0,
    "runtime_event_count": 142,
    "runtime_cost_estimate": 2.5,
    "usage_revenue_usd": 0.142,
    "lineage_measured_value": 35.2,
    "lineage_link_count": 3,
    "commit_count": 12,
    "commit_cost_sum": 1.8,
    "friction_cost_of_delay": 5.0,
    "data_freshness_hours": 24
  }
}
```

## Integration Point

New service `grounded_idea_metrics_service.py` with:

```python
def compute_idea_metrics(idea_id: str) -> dict[str, Any]
```

This function calls only existing service APIs — no new DB queries, no external fetches.

New endpoint `GET /api/ideas/{idea_id}/grounded-metrics` returns the computed metrics
with raw grounding sources.

Bulk endpoint `GET /api/ideas/grounded-metrics` returns metrics for all ideas.

## Acceptance Criteria

1. `compute_idea_metrics()` returns `computed_actual_cost` aggregated from spec registry
   + runtime + commit evidence. Never returns a hand-typed number.
2. `compute_idea_metrics()` returns `computed_actual_value` as the strongest signal from
   lineage measured value, usage revenue, or spec actual value.
3. `computed_confidence` reflects data coverage — ideas with more real signals score higher.
4. `grounding_sources` dict contains all raw inputs for audit.
5. Works with zero data (new idea with no specs/runtime/lineage) — returns 0.0 for
   computed values and low confidence.
6. Tests verify exact computed values from known inputs — no mocks for service APIs,
   only real service method contracts.

## Failure and Retry Behavior

- **Task failure**: Log error, mark task failed, advance to next item or pause for human review.
- **Retry logic**: Failed tasks retry up to 3 times with exponential backoff (initial 2s, max 60s).
- **Partial completion**: State persisted after each phase; resume from last checkpoint on restart.
- **External dependency down**: Pause pipeline, alert operator, resume when dependency recovers.
- **Timeout**: Individual task phases timeout after 300s; safe to retry from last phase.

## Acceptance Tests

See `api/tests/test_grounded_idea_portfolio_metrics.py` for test cases covering this spec's requirements.




## Verification

- Unit tests with exact assertions on all metric computations
- Contract tests verifying all upstream service methods exist with correct signatures
- Integration test: compute_idea_metrics for an idea with known spec/runtime/lineage data

## Risks and Assumptions

- **Risk**: Service APIs may return empty data for newly created ideas. Mitigation:
  graceful degradation to 0.0 with low confidence.
- **Risk**: Spec registry actual_cost may itself be estimated (from contribution_cost_service
  heuristics). Mitigation: track provenance; mark spec-derived costs as "semi-grounded".
- **Assumption**: spec_registry entries have `idea_id` populated. If null, specs are
  not attributed to any idea.

## Known Gaps and Follow-up Tasks

- [ ] Replace DEFAULT_IDEAS hardcoded values with computed metrics on read
- [ ] Ground `resistance_risk` from PR review friction and CI failure rates
- [ ] Ground `potential_value` from comparable-idea benchmarking
- [ ] Add time-series tracking of computed metrics for trend analysis
- [ ] Calibrate confidence weights (0.3/0.25/0.25/0.1/0.1) from actual prediction accuracy
