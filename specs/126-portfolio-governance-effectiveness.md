---
idea_id: coherence-credit
status: done
source:
  - file: api/app/routers/ideas.py
    symbols: [compute_governance_health()]
  - file: api/app/services/idea_service.py
    symbols: [compute_governance_health()]
  - file: api/app/models/idea.py
    symbols: [GovernanceHealth]
requirements:
  - "R1: New `GET /api/ideas/health` endpoint returns a `GovernanceHealth` response with the metrics defined in the Data Mode"
  - "R2: `throughput_rate` is calculated as the count of ideas whose `manifestation_status` changed to `validated` in the las"
  - "R3: `value_gap_trend` compares the sum of all `value_gap` values now vs. 30 days ago (negative means gaps are closing)."
  - "R4: `question_answer_rate` is the ratio of answered open questions (non-null `answer`) to total open questions across al"
  - "R5: `stale_ideas` lists idea IDs that have `manifestation_status != validated` and no field update in the last 14 days."
  - "R6: `governance_score` is a composite 0.0–1.0 score: `(throughput_rate * 0.3) + (question_answer_rate * 0.3) + (1 - len("
  - "R7: Response includes `snapshot_at` (ISO 8601 UTC timestamp) and `window_days` (default 30)."
done_when:
  - "GET /api/ideas/health returns GovernanceHealth JSON with all seven metrics"
  - "All tests in api/tests/test_governance_health.py pass"
  - "governance_score is between 0.0 and 1.0 inclusive"
test: "cd api && python -m pytest tests/test_governance_health.py -x -v"
constraints:
  - "Do not modify existing idea endpoints or their response schemas"
  - "Do not add new database tables; compute from existing idea state"
  - "Coherence scores remain 0.0–1.0"
---

> **Parent idea**: [coherence-credit](../ideas/coherence-credit.md)
> **Source**: [`api/app/routers/ideas.py`](../api/app/routers/ideas.py) | [`api/app/services/idea_service.py`](../api/app/services/idea_service.py) | [`api/app/models/idea.py`](../api/app/models/idea.py)

# Spec 126: Portfolio Governance Effectiveness Metrics

## Purpose

Portfolio governance exists to ensure ideas move from promise to real results. Today there is no automated way to tell whether governance itself is working — operators must manually inspect each idea. This spec adds a `/api/ideas/health` endpoint that computes and returns effectiveness metrics so operators and the cockpit UI can answer: "Is governance producing results, and where is it stuck?" Without this, the portfolio-governance super-idea cannot prove its own value, leaving its second open question permanently unanswered.

## Requirements

- [ ] R1: New `GET /api/ideas/health` endpoint returns a `GovernanceHealth` response with the metrics defined in the Data Model section.
- [ ] R2: `throughput_rate` is calculated as the count of ideas whose `manifestation_status` changed to `validated` in the last 30 days divided by total idea count.
- [ ] R3: `value_gap_trend` compares the sum of all `value_gap` values now vs. 30 days ago (negative means gaps are closing).
- [ ] R4: `question_answer_rate` is the ratio of answered open questions (non-null `answer`) to total open questions across all ideas.
- [ ] R5: `stale_ideas` lists idea IDs that have `manifestation_status != validated` and no field update in the last 14 days.
- [ ] R6: `governance_score` is a composite 0.0–1.0 score: `(throughput_rate * 0.3) + (question_answer_rate * 0.3) + (1 - len(stale_ideas)/total_ideas) * 0.4`.
- [ ] R7: Response includes `snapshot_at` (ISO 8601 UTC timestamp) and `window_days` (default 30).

## Research Inputs

- `2026-03-06` - [Spec 053: Ideas Prioritization](specs/053-ideas-prioritization.md) - defines the existing idea model, scoring, and portfolio API that this spec extends
- `2026-03-06` - [Spec 120: Super-Idea Rollup Criteria](specs/120-super-idea-rollup-criteria.md) - defines rollup validation for portfolio-governance; this spec provides the data to evaluate that rollup
- `2026-03-15` - [Spec 115: Grounded Idea Metrics](specs/115-grounded-idea-metrics.md) - establishes the pattern of computing derived metrics from idea state

## Task Card

```yaml
goal: Add a governance health endpoint that computes effectiveness metrics from idea portfolio state.
files_allowed:
  - api/app/routers/ideas.py
  - api/app/services/idea_service.py
  - api/app/models/idea.py
  - api/tests/test_governance_health.py
done_when:
  - GET /api/ideas/health returns GovernanceHealth JSON with all seven metrics
  - All tests in api/tests/test_governance_health.py pass
  - governance_score is between 0.0 and 1.0 inclusive
commands:
  - cd api && python -m pytest tests/test_governance_health.py -x -v
constraints:
  - Do not modify existing idea endpoints or their response schemas
  - Do not add new database tables; compute from existing idea state
  - Coherence scores remain 0.0–1.0
```

## API Contract

### `GET /api/ideas/health`

**Request**
- No parameters required.
- Optional query: `window_days` (int, default 30) — lookback window for trend calculations.

**Response 200**
```json
{
  "governance_score": 0.72,
  "throughput_rate": 0.15,
  "value_gap_trend": -3.2,
  "question_answer_rate": 0.65,
  "stale_ideas": ["coherence-network-value-attribution"],
  "total_ideas": 8,
  "validated_ideas": 3,
  "snapshot_at": "2026-03-21T12:00:00Z",
  "window_days": 30
}
```

**Response 500**
```json
{ "detail": "Failed to compute governance health" }
```

## Data Model

```yaml
GovernanceHealth:
  properties:
    governance_score: { type: float, description: "Composite 0.0-1.0 effectiveness score" }
    throughput_rate: { type: float, description: "Fraction of ideas validated in window" }
    value_gap_trend: { type: float, description: "Change in total value gap over window (negative = improving)" }
    question_answer_rate: { type: float, description: "Fraction of open questions answered" }
    stale_ideas: { type: list[str], description: "IDs of ideas with no update in 14 days and not validated" }
    total_ideas: { type: int, description: "Total idea count" }
    validated_ideas: { type: int, description: "Count of ideas with manifestation_status=validated" }
    snapshot_at: { type: datetime, description: "ISO 8601 UTC timestamp of computation" }
    window_days: { type: int, description: "Lookback window used for trend calculations" }
```

## Files to Create/Modify

- `api/app/models/idea.py` — add `GovernanceHealth` Pydantic model
- `api/app/services/idea_service.py` — add `compute_governance_health()` function
- `api/app/routers/ideas.py` — add `GET /api/ideas/health` route
- `api/tests/test_governance_health.py` — new test file with acceptance tests

## Acceptance Tests

- `api/tests/test_governance_health.py::test_health_returns_200_with_all_fields`
- `api/tests/test_governance_health.py::test_governance_score_bounded_0_to_1`
- `api/tests/test_governance_health.py::test_stale_ideas_excludes_validated`
- `api/tests/test_governance_health.py::test_question_answer_rate_correct`
- `api/tests/test_governance_health.py::test_custom_window_days`

## Concurrency Behavior

- **Read operations**: Safe for concurrent access; health is computed from a read-only scan of idea state.
- **Write operations**: None — this endpoint is read-only.
- **Recommendation**: Clients may cache responses for up to 5 minutes since metrics are aggregate and not latency-sensitive.

## Verification

```bash
cd api && python -m pytest tests/test_governance_health.py -x -v
curl -s http://localhost:8000/api/ideas/health | python -m json.tool
```

## Out of Scope

- Historical health snapshots or time-series storage (compute is live per-request)
- Alerting or notifications when governance_score drops below a threshold
- UI rendering of health metrics (separate cockpit spec)
- Modifying the free_energy_score algorithm

## Risks and Assumptions

- **Assumption**: Idea `updated_at` or equivalent timestamp exists or can be derived from the portfolio snapshot. If no timestamp tracking exists, `stale_ideas` detection will require adding a lightweight `last_updated` field to the idea model (low risk, additive change).
- **Risk**: With few ideas (currently ~8), percentage-based metrics can swing dramatically on a single status change. Mitigation: document that governance_score is most meaningful once the portfolio has 10+ ideas.
- **Assumption**: The current JSON-file-based storage retains enough history to compute 30-day trends. If not, `value_gap_trend` should return `null` with a note that historical data is insufficient.

## Known Gaps and Follow-up Tasks

- Follow-up task: `task_health_history_snapshots` — persist periodic health snapshots to enable trend visualization over time.
- Follow-up task: `task_cockpit_health_widget` — add governance health card to the portfolio cockpit UI (spec 052).
- Follow-up task: Update `portfolio-governance` open question answer field with the `/api/ideas/health` endpoint URL once implemented.

## Failure/Retry Reflection

- Failure mode: No historical data available for trend calculation
- Blind spot: Assuming JSON snapshot preserves prior state; it may be overwritten each run
- Next action: Return `null` for `value_gap_trend` when historical data is missing rather than failing the entire endpoint

- Failure mode: Division by zero when portfolio is empty
- Blind spot: Edge case with zero ideas or zero questions
- Next action: Return `governance_score: 0.0` and empty `stale_ideas` when portfolio is empty

## Decision Gates

- If no timestamp tracking exists on ideas, a lightweight `last_updated` field must be approved before `stale_ideas` can function. This is an additive-only schema change.
