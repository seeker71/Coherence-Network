---
idea_id: coherence-credit
status: done
source:
  - file: api/app/services/execution_value_proof_service.py
    symbols: [build_execution_value_proof(), summarize_grounded_value(), summarize_income()]
  - file: api/app/routers/execution_value.py
    symbols: [get_execution_value_proof()]
  - file: api/app/models/execution_value.py
    symbols: [ExecutionValueProofResponse]
requirements:
  - "GET /api/execution/value-proof composes execution, grounded idea value, paid-read income, and nutrition coverage into one response"
  - "The response separates measured value, estimated CC-to-USD value, CC-denominated income, and spendable fiat"
  - "Nutrition coverage is true only from observed spendable fiat, not projected value or CC estimates"
  - "Source statuses name which signals were measured, estimated, empty, unavailable, or errored"
done_when:
  - "cd api && python3 -m pytest -q tests/test_execution_value_proof.py"
  - "GET /api/execution/value-proof returns answer, execution, value, income, nutrition, and sources"
  - "Paid CC income does not set spendable_fiat_usd above zero without off-ramp evidence"
test: "cd api && python3 -m pytest -q tests/test_execution_value_proof.py"
---

# Execution Value Income Proof

## Purpose

This surface answers the operational question: can execution generate measurable value, and can that value become income that pays for real needs? It gives one curlable proof route that composes existing execution metrics, grounded idea portfolio value, paid read events, settlement batches, and CC exchange estimates without inventing a new ledger.

The route is intentionally strict about money. Grounded value and CC-denominated paid reads can show that execution is creating value and attracting payment, while nutrition coverage is proven only by spendable fiat evidence.

## Requirements

- [x] **R1**: `GET /api/execution/value-proof` returns a single response with `answer`, `execution`, `value`, `income`, `nutrition`, and `sources`.
- [x] **R2**: Execution proof uses existing task metrics and agent task state; missing timing remains absent instead of being filled with a placeholder.
- [x] **R3**: Grounded value uses `grounded_idea_metrics_service` so measured cost and value stay tied to specs, runtime events, lineage, commits, and friction signals.
- [x] **R4**: Paid-read income uses `value_lineage_service.query_read_events` and treats paid read CC as measured CC income.
- [x] **R5**: CC-to-USD output is labeled as an estimate from the CC oracle midpoint when available.
- [x] **R6**: `spendable_fiat_usd` remains `0.0` unless an observed off-ramp or spendable fiat settlement source is connected.
- [x] **R7**: Nutrition coverage uses spendable fiat only; estimated CC value can show an adjacent signal but cannot set `can_cover_nutrition=true`.

## Research Inputs

- `specs/grounded-cost-value-measurement.md` — existing rules for measured execution cost and value.
- `specs/grounded-idea-portfolio-metrics.md` — existing portfolio rollup for idea-level value.
- `specs/story-protocol-integration.md` — existing paid read and settlement flow.
- `specs/cc-economics-and-value-coherence.md` — existing CC exchange-rate estimate surface.

## API Contract

### `GET /api/execution/value-proof`

Query parameters:

- `window_days`: integer, 1 to 90, default `30`
- `daily_nutrition_usd`: optional non-negative number

Response 200:

```json
{
  "answer": {
    "can_generate_value_with_execution": true,
    "can_prove_income": true,
    "can_cover_nutrition": false,
    "status": "paid_cc_income_proven_offramp_needed",
    "healthiest_next_execution": "close one CC-to-spendable-fiat settlement record before treating it as nutrition funding"
  },
  "execution": {
    "tasks_total": 4,
    "terminal_tasks": 4,
    "completed": 3,
    "failed": 1,
    "running": 0,
    "pending": 0,
    "success_rate": 0.75,
    "p50_seconds": 11,
    "p95_seconds": 24,
    "runtime_backfill_count": 0
  },
  "value": {
    "ideas_count": 1,
    "measured_value_usd": 6.0,
    "measured_cost_usd": 1.5,
    "net_value_usd": 4.5
  },
  "income": {
    "paid_read_count": 1,
    "paid_read_cc": 8.0,
    "estimated_paid_read_usd": 2.0,
    "spendable_fiat_usd": 0.0,
    "proof_level": "paid_read_cc_measured"
  },
  "nutrition": {
    "daily_nutrition_usd": 2.0,
    "covered_days_by_spendable_fiat": 0.0,
    "covered_days_by_estimated_cc": 1.0,
    "can_cover_nutrition": false
  },
  "sources": []
}
```

## Files Created

- `api/app/models/execution_value.py` — typed response model.
- `api/app/services/execution_value_proof_service.py` — composition and classification logic.
- `api/app/routers/execution_value.py` — public route.
- `api/tests/test_execution_value_proof.py` — focused route and classification tests.

## Acceptance Tests

- `api/tests/test_execution_value_proof.py::test_grounded_value_summary_uses_measured_metrics`
- `api/tests/test_execution_value_proof.py::test_paid_read_cc_is_income_but_not_spendable_fiat`
- `api/tests/test_execution_value_proof.py::test_execution_value_proof_route_composes_measured_sources`

## Verification

```bash
cd api && python3 -m pytest -q tests/test_execution_value_proof.py
```

## Out of Scope

- New payment rails.
- Claiming CC as spendable fiat without an observed off-ramp source.
- Replacing grounded metric formulas outside this proof composition layer.

## Known Gaps and Follow-up Tasks

- Follow-up task: connect an observed off-ramp or fiat settlement source so `spendable_fiat_usd` can become measured instead of zero.
- Follow-up task: wire the web interface to this route where execution value and creator economy proof are displayed.

## Risks and Assumptions

- The current CC exchange rate is an estimate, not a cash settlement.
- Settlement batches distribute CC and do not prove fiat nutrition coverage on their own.
- A follow-up shall connect an observed off-ramp or fiat settlement source before the route can prove spendable income.
