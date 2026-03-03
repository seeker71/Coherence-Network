# Spec: POST /api/agent/tasks Invalid task_type Returns 422

## Purpose

Ensure that creating an agent task with an invalid `task_type` is rejected with 422 so clients receive predictable validation behavior and the API contract (spec 009, 010) is enforced by an explicit test.

## Requirements

- [ ] **Test exists**: A test in `api/tests/test_agent.py` sends `POST /api/agent/tasks` with a body that includes an invalid `task_type` (e.g. `"invalid"` or `"foo"`) and asserts response status code is 422.
- [ ] **Response shape**: The test asserts that the 422 response body has a `detail` key; when using Pydantic validation, `detail` is an array of validation items (per [009-api-error-handling.md](009-api-error-handling.md)).

## API Contract (if applicable)

### `POST /api/agent/tasks`

**Request (invalid case)**

- Body: `task_type` set to a value not in the allowed enum (`spec` | `test` | `impl` | `review` | `heal`), e.g. `"invalid"` or `"foo"`.
- Other required fields (e.g. `direction`) may be valid.

**Response 422**

Validation error (FastAPI/Pydantic default). `detail` is an array of objects with at least `loc`, `msg`, `type`; one item should reference `task_type` (e.g. `loc: ["body", "task_type"]`).

```json
{
  "detail": [
    {
      "loc": ["body", "task_type"],
      "msg": "value is not a valid enumeration member",
      "type": "type_error.enum"
    }
  ]
}
```

Allowed `task_type` values are defined in [010-request-validation.md](010-request-validation.md) and [002-agent-orchestration-api.md](002-agent-orchestration-api.md).

## Data Model (if applicable)

Not applicable; request validation is defined on `AgentTaskCreate` in `api/app/models/agent.py` (TaskType enum). See spec 010.

## Files to Create/Modify

- `api/tests/test_agent.py` — add or retain test: `POST /api/agent/tasks` with invalid `task_type` returns 422 (e.g. `test_post_task_invalid_task_type_returns_422`).

Implementation of validation is already in scope of specs 002 and 010 (`api/app/models/agent.py`, `api/app/routers/agent.py`); this spec focuses on the test.

## Acceptance Tests

- **POST invalid task_type**: `POST /api/agent/tasks` with `task_type` not in `{ spec, test, impl, review, heal }` returns 422. The corresponding test in `api/tests/test_agent.py` must pass.

See `api/tests/test_agent.py` — the test named for this behavior (e.g. `test_post_task_invalid_task_type_returns_422`) must pass.

## Out of Scope

- Other 422 cases for `POST /api/agent/tasks` (empty direction, missing direction, missing task_type, direction too long) — covered by 009/010 and other tests.
- Changing the validation implementation or enum values (decision gate in 002/010).

## Decision Gates (if any)

None. Adding or expanding this test does not require new dependencies or API contract changes.

## See also

- [009-api-error-handling.md](009-api-error-handling.md) — 422 format, acceptance tests for 422 on invalid task_type
- [010-request-validation.md](010-request-validation.md) — task_type enum, validation rules, test names
- [002-agent-orchestration-api.md](002-agent-orchestration-api.md) — POST /api/agent/tasks contract and test list
