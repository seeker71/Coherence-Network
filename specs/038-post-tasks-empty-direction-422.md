# Spec: POST /api/agent/tasks Empty direction Returns 422

## Purpose

Ensure that creating an agent task with an empty `direction` is rejected with 422 so clients receive predictable validation behavior and the API contract (spec 009, 010) is enforced by an explicit test.

## Requirements

- [ ] **Test exists**: A test in `api/tests/test_agent.py` sends `POST /api/agent/tasks` with a body that includes `direction: ""` (empty string) and asserts response status code is 422.
- [ ] **Response shape**: The test asserts that the 422 response body has a `detail` key; when using Pydantic validation, `detail` is an array of validation items (per [009-api-error-handling.md](009-api-error-handling.md)), and each item has `loc`, `msg`, and `type`.

## API Contract (if applicable)

### `POST /api/agent/tasks`

**Request (invalid case)**

- Body: `direction` set to empty string `""`.
- Other required fields (e.g. `task_type`) may be valid (e.g. `task_type: "impl"`).

**Response 422**

Validation error (FastAPI/Pydantic default). `detail` is an array of objects with at least `loc`, `msg`, `type`; one item should reference `direction` (e.g. `loc: ["body", "direction"]`).

```json
{
  "detail": [
    {
      "loc": ["body", "direction"],
      "msg": "ensure this value has at least 1 characters",
      "type": "value_error.any_str.min_length"
    }
  ]
}
```

Exact `msg`/`type` may vary by Pydantic version; the test must assert status 422, presence of `detail`, and that each element has `loc`, `msg`, `type`.

Direction length constraints are defined in [010-request-validation.md](010-request-validation.md) and [002-agent-orchestration-api.md](002-agent-orchestration-api.md) (min length 1, max 5000).

## Data Model (if applicable)

Not applicable; request validation is defined on `AgentTaskCreate` in `api/app/models/agent.py` (`direction: str = Field(..., min_length=1, max_length=5000)`). See spec 010.

## Files to Create/Modify

- `api/tests/test_agent.py` — add or retain test: `POST /api/agent/tasks` with empty `direction` returns 422 (e.g. `test_post_task_empty_direction_returns_422`).

Implementation of validation is already in scope of specs 002 and 010 (`api/app/models/agent.py`, `api/app/routers/agent.py`); this spec focuses on the test.

## Acceptance Tests

- **POST empty direction**: `POST /api/agent/tasks` with `direction: ""` (and valid `task_type`) returns 422. The corresponding test in `api/tests/test_agent.py` must pass.

See `api/tests/test_agent.py` — the test named for this behavior (e.g. `test_post_task_empty_direction_returns_422`) must pass.

## Out of Scope

- Other 422 cases for `POST /api/agent/tasks` (invalid task_type, missing direction, missing task_type, direction too long) — covered by 009/010 and other specs (e.g. [037-post-tasks-invalid-task-type-422.md](037-post-tasks-invalid-task-type-422.md)).
- Changing the validation implementation or min_length (decision gate in 002/010).

## Decision Gates (if any)

None. Adding or expanding this test does not require new dependencies or API contract changes.

## See also

- [009-api-error-handling.md](009-api-error-handling.md) — 422 format, acceptance tests for 422 on empty direction
- [010-request-validation.md](010-request-validation.md) — direction min_length, validation rules, test names
- [002-agent-orchestration-api.md](002-agent-orchestration-api.md) — POST /api/agent/tasks contract and test list
- [037-post-tasks-invalid-task-type-422.md](037-post-tasks-invalid-task-type-422.md) — parallel spec for invalid task_type 422
