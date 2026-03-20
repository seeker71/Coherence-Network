# Spec: Question Answering and Minimum E2E Flow

## Purpose

Enable direct answering of idea questions in the portfolio and expose a runnable minimum E2E flow endpoint for interface-integrity validation.

## Requirements

- [ ] API supports answering a specific question for an idea and persisting answer/measured delta.
- [ ] API returns 404 when question does not belong to the target idea.
- [ ] API exposes a minimum value-lineage E2E flow endpoint that creates lineage, usage event, valuation, and payout preview in one call.


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: none

## Task Card

```yaml
goal: Enable direct answering of idea questions in the portfolio and expose a runnable minimum E2E flow endpoint for interface-integrity validation.
files_allowed:
  - # TBD — determine from implementation
done_when:
  - API supports answering a specific question for an idea and persisting answer/measured delta.
  - API returns 404 when question does not belong to the target idea.
  - API exposes a minimum value-lineage E2E flow endpoint that creates lineage, usage event, valuation, and payout previe...
commands:
  - python3 -m pytest api/tests/test_cursor_e2e.py -x -v
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

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


### Input Validation

- All string fields: min_length=1, max_length=1000
- Numeric fields: appropriate min/max bounds
- Required fields validated; missing returns 422
- Unknown fields rejected (Pydantic extra="forbid" where applicable)

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

## Concurrency Behavior

- **Read operations**: Safe for concurrent access; no locking required.
- **Write operations**: Last-write-wins semantics; no optimistic locking for MVP.
- **Recommendation**: Clients should not assume atomic read-modify-write without explicit ETag support.

## Failure and Retry Behavior

- **Invalid input**: Return 422 with field-level validation errors.
- **Resource not found**: Return 404 with descriptive message.
- **Database unavailable**: Return 503; client should retry with exponential backoff (initial 1s, max 30s).
- **Concurrent modification**: Last write wins; no optimistic locking required for MVP.
- **Timeout**: Operations exceeding 30s return 504; safe to retry.

## Risks and Known Gaps

- **No auth gate**: Endpoints unprotected until C1 auth middleware applied.
- **No rate limiting**: Subject to abuse until M1 rate limiter active.
- **Single-node only**: No distributed locking; concurrent access may race.
- **Follow-up**: Add integration tests for error edge cases.

## Acceptance Tests

See `api/tests/test_question_answering_and_minimum_e2e_flow.py` for test cases covering this spec's requirements.


## Verification

```bash
python3 -m pytest api/tests/test_cursor_e2e.py -x -v
```
