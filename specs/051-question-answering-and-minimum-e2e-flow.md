# Spec: Question Answering and Minimum E2E Flow

## Purpose

Enable direct answering of idea questions in the portfolio and expose a runnable minimum E2E flow endpoint for interface-integrity validation.

## Requirements

- [ ] API supports answering a specific question for an idea and persisting answer/measured delta.
- [ ] API returns 404 when question does not belong to the target idea.
- [ ] API exposes a minimum value-lineage E2E flow endpoint that creates lineage, usage event, valuation, and payout preview in one call.

## API Contract

### `POST /api/ideas/{idea_id}/questions/answer`

Request:
```json
{
  "question": "Which route set is canonical for current milestone?",
  "answer": "Canonical route set is exposed at /api/inventory/routes/canonical.",
  "measured_delta": 3.5
}
```

### `POST /api/value-lineage/minimum-e2e-flow`

Runs a full minimum E2E flow and returns generated lineage id, usage event id, valuation, payout preview, and invariant checks.

## Validation Contract

- `api/tests/test_ideas.py::test_answer_idea_question_persists_answer`
- `api/tests/test_value_lineage.py::test_minimum_e2e_flow_endpoint`

## Files

- `api/app/models/idea.py`
- `api/app/services/idea_service.py`
- `api/app/routers/ideas.py`
- `api/app/models/value_lineage.py`
- `api/app/services/value_lineage_service.py`
- `api/app/routers/value_lineage.py`
- `api/tests/test_ideas.py`
- `api/tests/test_value_lineage.py`

