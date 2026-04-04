---
idea_id: idea-realization-engine
status: done
source:
  - file: api/app/services/idea_service.py
    symbols: [_ensure_standing_questions(), add_question(), answer_question()]
  - file: api/app/routers/inventory.py
    symbols: [next_highest_roi_task()]
  - file: api/app/services/inventory_service.py
    symbols: [next_highest_roi_task_from_answered_questions()]
  - file: api/app/models/idea.py
    symbols: [IdeaQuestion, IdeaQuestionCreate]
requirements:
  - "Every idea includes the standing improvement/measurement question."
  - "Inventory exposes `question_roi` and `answer_roi` for question rows."
  - "API can suggest and optionally create the next highest-ROI task from answered questions."
done_when:
  - "Every idea includes the standing improvement/measurement question."
  - "Inventory exposes `question_roi` and `answer_roi` for question rows."
  - "API can suggest and optionally create the next highest-ROI task from answered questions."
test: "python3 -m pytest api/tests/test_ideas.py -x -v"
constraints:
  - "changes scoped to listed files only"
  - "no schema migrations without explicit approval"
---

> **Parent idea**: [idea-realization-engine](../ideas/idea-realization-engine.md)
> **Source**: [`api/app/services/idea_service.py`](../api/app/services/idea_service.py) | [`api/app/routers/inventory.py`](../api/app/routers/inventory.py) | [`api/app/services/inventory_service.py`](../api/app/services/inventory_service.py) | [`api/app/models/idea.py`](../api/app/models/idea.py)

# Spec: Standing Questions, ROI Fields, and Next-Task Generation

## Purpose

Enforce continuous ROI-driven discovery by ensuring each idea always has a standing improvement/measurement question, exposing ROI on questions and answers, and generating the next highest-ROI task from answered questions.

## Requirements

- [ ] Every idea includes the standing improvement/measurement question.
- [ ] Inventory exposes `question_roi` and `answer_roi` for question rows.
- [ ] API can suggest and optionally create the next highest-ROI task from answered questions.


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: 112, 115

## Task Card

```yaml
goal: Enforce continuous ROI-driven discovery by ensuring each idea always has a standing improvement/measurement question, exposing ROI on questions and answers, and generating the next highest-ROI task from answered questions.
files_allowed:
  - # TBD — determine from implementation
done_when:
  - Every idea includes the standing improvement/measurement question.
  - Inventory exposes `question_roi` and `answer_roi` for question rows.
  - API can suggest and optionally create the next highest-ROI task from answered questions.
commands:
  - python3 -m pytest api/tests/test_ideas.py -x -v
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

## API Contract

### `POST /api/inventory/questions/next-highest-roi-task?create_task=false`

Returns the highest-ROI answered question follow-up and task direction.

### `POST /api/inventory/questions/next-highest-roi-task?create_task=true`

Creates a task in the agent task store and returns task metadata.


### Input Validation

- All string fields: min_length=1, max_length=1000
- Numeric fields: appropriate min/max bounds
- Required fields validated; missing returns 422
- Unknown fields rejected (Pydantic extra="forbid" where applicable)

## Validation Contract

- `api/tests/test_inventory_api.py::test_standing_question_exists_for_every_idea`
- `api/tests/test_inventory_api.py::test_next_highest_roi_task_generation_from_answered_questions`
- `api/tests/test_inventory_api.py::test_system_lineage_inventory_includes_core_sections` (ROI fields present)

## Downstream Consumers

- **Spec 115** ([115-grounded-cost-value-measurement.md](115-grounded-cost-value-measurement.md)) — Reads `idea_service.get_idea()` to collect `actual_value` and `potential_value` for computing value realization percentage (`actual_value / potential_value`). This feeds into the grounded value formula as an economic signal. As specs 112-115 record real measurements, the ROI fields exposed by this spec become increasingly grounded rather than estimated.

## Files

- `api/app/services/idea_service.py`
- `api/app/services/inventory_service.py`
- `api/app/routers/inventory.py`
- `api/tests/test_inventory_api.py`

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

See `api/tests/test_standing_questions_roi_and_next_task_generation.py` for test cases covering this spec's requirements.


## Verification

```bash
python3 -m pytest api/tests/test_ideas.py -x -v
```

## Known Gaps and Follow-up Tasks

- No known gaps at time of writing.
- Follow-up: review after initial implementation for completeness.
