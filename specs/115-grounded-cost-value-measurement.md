---
idea_id: coherence-credit
status: done
source:
  - file: api/app/services/grounded_measurement_service.py
    symbols: [compute_grounded_cost(), compute_grounded_value()]
  - file: api/app/services/grounded_idea_metrics_service.py
    symbols: [compute_idea_metrics()]
requirements:
  - compute_grounded_cost returns actual_cost_usd when present, else runtime_cost_estimate
  - compute_grounded_value returns 0.0 for failed tasks
  - Quality multiplier degrades with retries (1.0/0.7/0.4/0.2)
  - Raw signals stored alongside computed scores in every measurement
  - record_grounded_measurement requires no new API calls or DB queries
  - Economic value layer uses max of adoption, revenue, and lineage signals
  - Tasks without prompt_variant in context are not recorded
done_when:
  - Exact computed values verified against known inputs in tests
  - pytest api/tests/test_grounded_cost_value_measurement.py passes
---

> **Parent idea**: [coherence-credit](../ideas/coherence-credit.md)
> **Source**: [`api/app/services/grounded_measurement_service.py`](../api/app/services/grounded_measurement_service.py) | [`api/app/services/grounded_idea_metrics_service.py`](../api/app/services/grounded_idea_metrics_service.py)

# Spec 115: Grounded Cost & Value Measurement for Prompt A/B ROI

**Idea**: `agent-grounded-measurement` (sub-idea of `coherence-network-agent-pipeline`)
**Depends on**: Spec 112 (prompt_ab_roi_service)
**Integrates with**:
- `coherence-network-value-attribution` (reads value_lineage_service for measured revenue)
- `coherence-signal-depth` (replaces invented numbers with real provider billing and usage signals)
- Spec 049 (runtime telemetry for usage adoption counts)
- Spec 050 (friction events for cost_of_delay)

## Status: Implemented

## Problem

The A/B ROI service (spec 112) accepts `value_score` and `resource_cost` as
caller-supplied floats with no connection to observable data. This makes ROI
calculations meaningless — we're optimizing on invented numbers.

Real signals already flow through the system but are not wired to the ROI
service:

| Signal | Source | Grounded? |
|--------|--------|-----------|
| `actual_cost_usd` | Provider billing response | **Yes** |
| `runtime_cost_estimate` | `elapsed_ms * rate` | **Yes** |
| `runtime_ms` | Wall-clock timer | **Yes** |
| `status_code` (200/500) | Task outcome | **Yes** |
| `confidence` | Parsed from task output JSON | Partially (self-reported, structured) |
| `actual_value` | Parsed from task output JSON | **No** (self-reported, unvalidated) |

## Design

### Cost: Fully grounded

```
grounded_cost = actual_cost_usd          # Provider billing (when available)
              ?? runtime_cost_estimate    # Infra cost from elapsed_ms (always available)
```

Both are real, measured values. `actual_cost_usd` comes from the provider's
billing response. `runtime_cost_estimate` is computed from wall-clock time.
No estimation, no self-reporting.

### Value: Grounded composite from observable outcomes

Instead of accepting a self-reported `value_score`, compute it from observable
task outcomes:

```
grounded_value = outcome_signal         # 0.0 or 1.0 — did the task complete?
               * quality_multiplier     # Penalty for retries, heals
               * confidence_weight      # From output when available (default 1.0)
```

Where:
- `outcome_signal`: 1.0 if `status == completed`, 0.0 if `status == failed`
- `quality_multiplier`:
  - 1.0 if first attempt (no retries)
  - 0.7 if 1 retry
  - 0.4 if 2 retries
  - 0.2 if 3+ retries
  - 0.0 if healed but heal also failed
- `confidence_weight`: `confidence` from task output JSON, clamped [0.1, 1.0],
  default 1.0 if not present

This produces a 0.0-1.0 execution quality score.

### Economic value layer (Layer 2)

Execution quality alone only answers "did the task run well?" — not "did it
produce something someone would pay for?" Real value requires observable
economic signals from the idea the task serves.

When a task has an `idea_id` in its context, the system collects:

| Signal | Source | What it measures |
|--------|--------|-----------------|
| **Usage adoption** | `RuntimeEvent` count per `idea_id` | How many API calls this feature gets |
| **Usage revenue** | `event_count × $0.001/request` | Direct revenue (from ECONOMIC_MODEL.md) |
| **Value realization** | `Idea.actual_value / potential_value` | How much predicted value has materialized |
| **Lineage measured value** | `LineageValuation.measured_value_total` | Cumulative measured value from usage events |
| **Friction cost avoidance** | `FrictionEvent.cost_of_delay` | Economic impact of blockages this idea resolves |

The strongest signal drives the economic weight (max, not average):

```
final_value = execution_quality × (0.4 + 0.6 × strongest_economic_signal)
```

This means:
- Perfect execution + zero economic signal = 0.4 (base credit for work done)
- Perfect execution + strong economic signal = 1.0 (full value)
- Failed execution = always 0.0 (failure gates everything)
- No idea link = execution quality alone (honest: no inflation)

Normalization scales:
- **Adoption**: log scale — 1 call = 0.1, 10 calls = 0.5, 100+ calls = 0.9+
- **Revenue**: log scale — $0.01 = 0.2, $0.10 = 0.5, $1.00 = 0.8, $10+ = 1.0
- **Friction avoidance**: log scale — $1 = 0.2, $10 = 0.5, $100+ = 0.9

### Raw signal storage

Every measurement records the raw signals alongside the computed score so the
formula can be improved later without re-collecting data:

```json
{
  "variant_id": "prompt_v2",
  "task_type": "impl",
  "task_id": "task-abc",
  "value_score": 0.7,
  "resource_cost": 0.0034,
  "raw_signals": {
    "status": "completed",
    "actual_cost_usd": 0.0034,
    "runtime_cost_estimate": 0.0018,
    "runtime_ms": 9200,
    "confidence": null,
    "retry_count": 1,
    "heal_attempt": false,
    "outcome_signal": 1.0,
    "quality_multiplier": 0.7,
    "confidence_weight": 1.0,
    "execution_quality": 0.7,
    "idea_id": "idea-xyz",
    "idea_signals": {
      "usage_event_count": 42,
      "usage_revenue_usd": 0.042,
      "actual_value_usd": 15.0,
      "potential_value_usd": 50.0,
      "value_realization_pct": 0.3,
      "sources": ["idea_model", "runtime_events"]
    },
    "economic_breakdown": {
      "execution_quality": 0.7,
      "economic_weight": 0.749,
      "economic_signal_source": "adoption",
      "has_idea_signals": true
    }
  },
  "timestamp": "2026-03-18T..."
}
```

## Integration Point

`complete_success()` and `complete_failure()` in `agent_execution_completion.py`
already have all required signals. Add a call to a new function:

```python
def record_grounded_measurement(
    task_id: str,
    task: dict,
    status: str,            # "completed" or "failed"
    elapsed_ms: int,
    actual_cost_usd: float | None,
    runtime_cost_estimate: float,
    output_metrics: dict | None,
) -> dict
```

This function:
1. Resolves `variant_id` from `task.context.get("prompt_variant")`
2. Computes grounded cost and value from the raw signals
3. Calls `prompt_ab_roi_service.record_prompt_outcome()` with real numbers
4. Returns the measurement record with raw signals

Tasks without a `prompt_variant` in context are not recorded (no variant to
attribute to).

## Acceptance Criteria

1. `compute_grounded_cost()` returns `actual_cost_usd` when present, else
   `runtime_cost_estimate`. Never returns a caller-invented number.
2. `compute_grounded_value()` returns 0.0 for failed tasks, 1.0 for
   first-attempt success with no confidence discount, and degraded values
   for retried tasks.
3. Raw signals are stored alongside computed scores in every measurement.
4. `record_grounded_measurement()` is callable from completion handlers
   with only data already available at that point — no new API calls,
   no DB queries, no external fetches.
5. Tests verify exact computed values against known inputs — no mocks,
   no self-reported scores.

## Failure and Retry Behavior

- **Task failure**: Log error, mark task failed, advance to next item or pause for human review.
- **Retry logic**: Failed tasks retry up to 3 times with exponential backoff (initial 2s, max 60s).
- **Partial completion**: State persisted after each phase; resume from last checkpoint on restart.
- **External dependency down**: Pause pipeline, alert operator, resume when dependency recovers.
- **Timeout**: Individual task phases timeout after 300s; safe to retry from last phase.

## Acceptance Tests

See `api/tests/test_grounded_cost_value_measurement.py` for test cases covering this spec's requirements.




## Verification

- Unit tests with exact assertions on `compute_grounded_cost` and
  `compute_grounded_value` for all edge cases
- Integration test: `record_grounded_measurement` produces a measurement
  with real raw signals that round-trips through the ROI service
- Verify the measurement store contains `raw_signals` with all expected keys

## Risks and Assumptions

- **Risk**: `actual_cost_usd` may be null for free-tier providers. Mitigation:
  fall back to `runtime_cost_estimate` which is always available. When both are
  zero/null, a floor of 0.0001 is applied because the ROI service requires
  cost > 0 (CPU time was spent even if no provider was billed).
- **Risk**: `confidence` from task output is self-reported. Mitigation: it's
  weighted, not decisive, and raw signals are stored for future recalibration.
- **Assumption**: `prompt_variant` will be set in task context by the
  orchestration layer when A/B testing is active. Tasks without it are simply
  not recorded.

## Known Gaps and Follow-up Tasks

- [ ] Downstream value validation: did review pass? did tests pass after impl?
      Requires cross-task correlation (spec TBD)
- [ ] Provider-specific cost accuracy: OpenRouter returns cost but accuracy
      varies by model. Track per-model cost drift.
- [ ] Value formula tuning: the quality_multiplier weights (1.0/0.7/0.4) are
      initial estimates. Should be calibrated from actual review acceptance data.
- [ ] Economic signal normalization scales are initial estimates (log-based).
      Should be tuned from real usage distribution data.
- [ ] External value signals: GitHub stars/forks, customer support ticket
      reduction, user retention metrics — not yet wired.
