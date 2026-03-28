# Spec 037: POST /api/agent/tasks — Invalid task_type Returns 422

## Summary

When a client submits `POST /api/agent/tasks` with a `task_type` value that is not a member of the
`TaskType` enum, the API must respond with HTTP **422 Unprocessable Entity** and a structured
`detail` array so that callers receive predictable, machine-readable validation feedback.

This spec also requires that this contract is enforced by an explicit test in
`api/tests/test_agent.py` rather than relying on implicit Pydantic behavior alone.

---

## Goal

Ensure the `POST /api/agent/tasks` endpoint rejects unknown `task_type` values with HTTP 422
carrying a Pydantic-style `detail` array.  A dedicated pytest test must verify this contract and
must remain green across all CI runs.

---

## Context / Related Specs

| Spec | Relevance |
|------|-----------|
| [002-agent-orchestration-api.md](002-agent-orchestration-api.md) | Defines `POST /api/agent/tasks` contract and allowed `task_type` values |
| [009-api-error-handling.md](009-api-error-handling.md) | 422 response format (`detail` as array of `{loc, msg, type}`) |
| [010-request-validation.md](010-request-validation.md) | `TaskType` enum, per-field validation rules, test naming conventions |

---

## Requirements

- [ ] **Test exists** — `api/tests/test_agent.py` contains a test named
  `test_post_task_invalid_task_type_returns_422` (or equivalent) that:
  - Sends `POST /api/agent/tasks` with an invalid `task_type` (e.g. `"invalid"`, `"foo"`, or
    `"UNKNOWN"`).
  - Asserts the response HTTP status code is **422**.
  - Asserts the response body has a top-level `detail` key whose value is a **list**.
  - Asserts at least one item in `detail` has `loc` containing `"task_type"`.

- [ ] **Enum enforcement** — The `AgentTaskCreate` Pydantic model (in `api/app/models/agent.py`)
  rejects any value for `task_type` that is not one of:
  `spec | test | impl | review | heal | code-review | merge | deploy | verify | reflect`.
  Rejection must raise a `ValueError` that FastAPI surfaces as 422 (not 400, not 500).

- [ ] **Router documents 422** — `POST /agent/tasks` router decorator includes
  `responses={422: {"description": "..."}}`.  This is already present; do not remove it.

---

## API Contract

### `POST /api/agent/tasks`

**Request — happy-path (for contrast)**

```json
{
  "direction": "Write a spec for feature X",
  "task_type": "spec"
}
```

→ HTTP 201 with the created `AgentTask` object.

---

**Request — invalid `task_type`**

```json
{
  "direction": "Write a spec for feature X",
  "task_type": "invalid"
}
```

**Response 422**

```json
{
  "detail": [
    {
      "loc": ["body", "task_type"],
      "msg": "Value error, task_type must be one of [...]; got 'invalid'",
      "type": "value_error"
    }
  ]
}
```

- `detail` is always a list (Pydantic v2 validation-error format).
- At least one item has `loc` referencing `task_type`.
- `msg` is human-readable and identifies the offending value.
- `type` is `"value_error"` (Pydantic v2) or `"type_error.enum"` (Pydantic v1).

---

### Allowed `task_type` Values

Defined in `TaskType` enum (`api/app/models/agent.py`):

| String value | Enum member |
|---|---|
| `spec` | `TaskType.SPEC` |
| `test` | `TaskType.TEST` |
| `impl` | `TaskType.IMPL` |
| `review` | `TaskType.REVIEW` |
| `heal` | `TaskType.HEAL` |
| `code-review` | `TaskType.CODE_REVIEW` |
| `merge` | `TaskType.MERGE` |
| `deploy` | `TaskType.DEPLOY` |
| `verify` | `TaskType.VERIFY` |
| `reflect` | `TaskType.REFLECT` |

Any value outside this set must return 422.

---

## Data Model

No schema migration required.  Validation is enforced by the `AgentTaskCreate` Pydantic model
(`api/app/models/agent.py`) using the `task_type_must_be_enum` field validator.

Relevant model excerpt:

```python
class AgentTaskCreate(BaseModel):
    direction: str = Field(..., min_length=1, max_length=5000)
    task_type: TaskType

    @field_validator("task_type", mode="before")
    @classmethod
    def task_type_must_be_enum(cls, v: object) -> TaskType:
        if isinstance(v, TaskType):
            return v
        if isinstance(v, str) and v in (e.value for e in TaskType):
            return TaskType(v)
        raise ValueError(
            f"task_type must be one of {[e.value for e in TaskType]}; got {v!r}"
        )
```

---

## Files to Create / Modify

| File | Change |
|---|---|
| `api/tests/test_agent.py` | Add or retain `test_post_task_invalid_task_type_returns_422` |
| `api/app/models/agent.py` | Ensure `task_type_must_be_enum` validator exists (no change expected) |
| `api/app/routers/agent_tasks_routes.py` | Ensure `responses={422: ...}` is present (no change expected) |

Implementation of validation is owned by specs 002 and 010.  This spec owns the **test**.

---

## Acceptance Criteria

1. `POST /api/agent/tasks` with `task_type: "invalid"` returns HTTP **422** (not 400, 500, or 201).
2. Response body has `detail` as a non-empty list.
3. At least one `detail` item has `loc` containing `"task_type"`.
4. `POST /api/agent/tasks` with a valid `task_type: "spec"` and valid `direction` still returns 201.
5. The test `test_post_task_invalid_task_type_returns_422` in `api/tests/test_agent.py` passes with
   `pytest api/tests/test_agent.py -x -v`.

---

## Verification Scenarios

### Scenario 1 — Core: Invalid task_type rejects with 422

**Setup:** API is running (local test client or production at `https://api.coherencycoin.com`).

**Action:**
```bash
curl -s -X POST https://api.coherencycoin.com/api/agent/tasks \
  -H "Content-Type: application/json" \
  -d '{"direction": "Test direction", "task_type": "invalid"}' | python3 -m json.tool
```

**Expected result:**
- HTTP status: `422`
- Body contains `"detail"` key whose value is a list.
- At least one list item has `"task_type"` somewhere in the `"loc"` array.

**Edge case:** Using `task_type: "SPEC"` (uppercase) also returns 422, because the enum values are
lowercase strings and case-sensitive matching is enforced.

---

### Scenario 2 — Happy path: Valid task_type creates task

**Setup:** API is running.

**Action:**
```bash
TASK_ID=$(curl -s -X POST https://api.coherencycoin.com/api/agent/tasks \
  -H "Content-Type: application/json" \
  -d '{"direction": "Verify 422 spec is implemented", "task_type": "spec"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "Created task: $TASK_ID"
```

**Expected result:**
- HTTP status: `201`
- Response body contains `"id"` (UUID), `"task_type": "spec"`, `"status": "pending"`.
- `$TASK_ID` is a non-empty UUID string.

**Follow-up read:**
```bash
curl -s https://api.coherencycoin.com/api/agent/tasks/$TASK_ID | python3 -m json.tool
```
- Returns HTTP 200 with the same task object (create-read cycle confirmed).

---

### Scenario 3 — Boundary: Every invalid value rejects

**Setup:** API is running.

**Action (run for each invalid value):**
```bash
for bad in "foo" "SPEC" "Spec" "" "null" "123" "spec " " spec" "unknown"; do
  CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
    https://api.coherencycoin.com/api/agent/tasks \
    -H "Content-Type: application/json" \
    -d "{\"direction\": \"test\", \"task_type\": \"$bad\"}")
  echo "$bad -> $CODE"
done
```

**Expected result:** Every line outputs `-> 422` (or `-> 422`/`-> 422`).  None returns 201.

**Edge case:** An empty string `""` for `task_type` returns 422, not 400.

---

### Scenario 4 — Response shape: detail array is machine-readable

**Setup:** API is running.

**Action:**
```bash
BODY=$(curl -s -X POST https://api.coherencycoin.com/api/agent/tasks \
  -H "Content-Type: application/json" \
  -d '{"direction": "Test direction", "task_type": "bogus"}')
echo $BODY | python3 -c "
import sys, json
body = json.load(sys.stdin)
assert 'detail' in body, 'Missing detail key'
assert isinstance(body['detail'], list), 'detail must be a list'
assert len(body['detail']) > 0, 'detail must be non-empty'
item = body['detail'][0]
assert 'loc' in item, 'Missing loc in detail item'
assert 'msg' in item, 'Missing msg in detail item'
assert 'type' in item, 'Missing type in detail item'
locs = ' '.join(str(x) for x in item['loc'])
assert 'task_type' in locs, f'task_type not in loc: {item[\"loc\"]}'
print('PASS: detail shape is correct')
"
```

**Expected result:** Script prints `PASS: detail shape is correct` with exit code 0.

---

### Scenario 5 — pytest: Test suite passes

**Setup:** Clone or worktree of the repository; virtual environment with dependencies installed.

**Action:**
```bash
cd api
python3 -m pytest tests/test_agent.py -x -v -k "invalid_task_type"
```

**Expected result:**
```
PASSED tests/test_agent.py::test_post_task_invalid_task_type_returns_422
1 passed in ...s
```

**Edge case:** Running the full agent test file `pytest tests/test_agent.py -x -v` must also pass
without failures introduced or masked by this change.

---

## Out of Scope

- Other 422 causes on `POST /api/agent/tasks` (missing `direction`, `direction` too long,
  `direction` whitespace-only) — covered by specs 009 and 010.
- Changing the `TaskType` enum values — requires spec 002 / 010 decision gate.
- Auth or rate-limiting — separate cross-cutting concerns.

---

## Decision Gates

None.  Adding this test does not require new dependencies, schema changes, or API contract changes.

---

## Risks and Assumptions

| Risk | Mitigation |
|---|---|
| Pydantic v2 ships `"value_error"` type; v1 ships `"type_error.enum"` | Test asserts `loc` contains `task_type`, not `type` string — avoids Pydantic version brittleness |
| Enum values may expand in future | Test only checks the invalid value path; valid enum additions do not break it |
| No auth gate on this endpoint | Acceptable for MVP; auth middleware tracked under separate spec |
| Concurrent write races | Not applicable; validation rejects before DB write |

---

## Known Gaps and Follow-up Tasks

- Add explicit 422 tests for missing `direction`, empty `direction`, and `direction` exceeding
  `max_length` (covered by spec 010 but no dedicated test exists as of this writing).
- Consider adding a schema-level `examples` block to the OpenAPI spec for this endpoint to make
  the 422 case visible in the Swagger UI.

---

## Concurrency Behavior

Not applicable; request validation occurs synchronously before any DB interaction.

---

## Failure and Retry Behavior

- Validation failure (422) is deterministic for a given request body.  Retrying the same invalid
  body will always return 422.
- Clients should not retry 422 responses without first fixing the request payload.

---

## Verification Command (CI)

```bash
python3 -m pytest api/tests/test_agent.py api/tests/test_agent_task_persistence.py -x -v
```

Both files must pass with zero failures.

---

*Spec authored for idea `037-post-tasks-invalid-task-type-422`.*
