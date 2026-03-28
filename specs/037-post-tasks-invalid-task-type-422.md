# Spec 037: POST /api/agent/tasks — Invalid `task_type` Returns 422

**Status**: Implemented
**Idea ID**: `037-post-tasks-invalid-task-type-422`
**Related**: [009-api-error-handling.md](009-api-error-handling.md), [010-request-validation.md](010-request-validation.md), [002-agent-orchestration-api.md](002-agent-orchestration-api.md)

---

## Summary

`POST /api/agent/tasks` must reject requests that supply an invalid `task_type` value with an HTTP 422 Unprocessable Entity response. The response body must be a structured validation error with a `detail` array where each element contains `loc`, `msg`, and `type` fields, consistent with Pydantic's standard validation error contract.

This spec ensures the validation is not accidentally removed, that the shape is machine-readable for clients, and that the behavior is covered by an explicit regression test.

---

## Goal

Ensure that:

1. `POST /api/agent/tasks` with an unrecognized `task_type` string (e.g. `"invalid"`, `"foo"`, `"SPEC"`) returns **HTTP 422**.
2. The 422 response body contains a `detail` key whose value is a **list** of validation error objects.
3. Each error object contains at minimum: `loc` (location array), `msg` (human-readable message), `type` (machine-readable error code).
4. The validation error references `task_type` in its `loc` field so clients can map the error to the offending field.
5. A dedicated test in `api/tests/` exercises this path and must continue to pass.

---

## Background & Motivation

The Coherence Network API is consumed by autonomous agent nodes that POST tasks programmatically. If an agent node is misconfigured or uses an outdated task type string, it must get a deterministic, machine-readable 422 — not a 500 server crash, a silent swallow, or an ambiguous generic error. This contract:

- Allows agent nodes to detect misconfiguration quickly.
- Protects the task queue from garbage entries.
- Gives the pipeline a reliable error class to route to `failed` + `needs_decision`.

---

## Requirements

### R1 — HTTP Status Code

`POST /api/agent/tasks` with an invalid `task_type` value **MUST** return `HTTP 422`.

- Invalid values include: any string not in the `TaskType` enum, integer values, `null`, missing field.
- Valid values (no 422): `"spec"`, `"test"`, `"impl"`, `"review"`, `"heal"`, `"code-review"`, `"merge"`, `"deploy"`, `"verify"`, `"reflect"`.

### R2 — Response Shape

The 422 response body **MUST** be:

```json
{
  "detail": [
    {
      "loc": ["body", "task_type"],
      "msg": "<human-readable message>",
      "type": "<machine-readable type string>"
    }
  ]
}
```

- `detail` is a list (even for a single error).
- Each item has `loc` (array), `msg` (string), `type` (string).
- At least one item in `detail` must have `"task_type"` within its `loc` array.

### R3 — No Task Created

No task entry must be created in the store when the request fails with 422. The task count before and after must be equal.

### R4 — Valid `task_type` Succeeds

`POST /api/agent/tasks` with a valid `task_type` (e.g. `"impl"`) and a valid `direction` **MUST** return `HTTP 201` with the created task.

### R5 — Test Coverage

A test in `api/tests/test_api_error_handling.py` named `test_422_on_invalid_task_type` (or equivalent) must:
- Send `POST /api/agent/tasks` with `task_type` set to an invalid value.
- Assert `response.status_code == 422`.
- Assert `response.json()["detail"]` is a list.
- Assert each item in the list has `loc`, `msg`, `type`.

---

## API Contract

### Endpoint

```
POST /api/agent/tasks
```

### Request Body (invalid case)

```json
{
  "task_type": "INVALID_TYPE",
  "direction": "test direction that is otherwise valid"
}
```

### Response — 422 Unprocessable Entity

```json
{
  "detail": [
    {
      "loc": ["body", "task_type"],
      "msg": "task_type must be one of ['spec', 'test', 'impl', 'review', 'heal', 'code-review', 'merge', 'deploy', 'verify', 'reflect']; got 'INVALID_TYPE'",
      "type": "value_error"
    }
  ]
}
```

### Request Body (valid case)

```json
{
  "task_type": "impl",
  "direction": "Implement the feature described in spec 037."
}
```

### Response — 201 Created

```json
{
  "id": "<uuid>",
  "task_type": "impl",
  "direction": "Implement the feature described in spec 037.",
  "status": "pending",
  "created_at": "<ISO 8601 UTC>",
  "updated_at": "<ISO 8601 UTC>"
}
```

---

## Data Model

Validation is enforced on `AgentTaskCreate` in `api/app/models/agent.py`:

```python
class TaskType(str, Enum):
    SPEC = "spec"
    TEST = "test"
    IMPL = "impl"
    REVIEW = "review"
    HEAL = "heal"
    CODE_REVIEW = "code-review"
    MERGE = "merge"
    DEPLOY = "deploy"
    VERIFY = "verify"
    REFLECT = "reflect"

class AgentTaskCreate(BaseModel):
    direction: str = Field(..., min_length=1, max_length=5000)
    task_type: TaskType
    ...

    @field_validator("task_type", mode="before")
    @classmethod
    def task_type_must_be_enum(cls, v: object) -> TaskType:
        """Reject invalid task_type so POST returns 422 with detail array (spec 037, 009)."""
        if isinstance(v, TaskType):
            return v
        if isinstance(v, str) and v in (e.value for e in TaskType):
            return TaskType(v)
        raise ValueError(
            f"task_type must be one of {[e.value for e in TaskType]}; got {v!r}"
        )
```

No database schema change is required. Validation is pure request-level.

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `api/app/models/agent.py` | Already implemented | `TaskType` enum + `task_type_must_be_enum` validator |
| `api/tests/test_api_error_handling.py` | Already implemented | `test_422_on_invalid_task_type` regression test |

No additional files are required. The spec documents the existing contract and test.

---

## Verification Scenarios

The reviewer will run these scenarios against the live API at `https://api.coherencycoin.com`. All must pass for the feature to be considered complete.

### Scenario 1 — Invalid string value returns 422

**Setup**: No prior state needed. API is running.

**Action**:
```bash
curl -s -X POST https://api.coherencycoin.com/api/agent/tasks \
  -H "Content-Type: application/json" \
  -d '{"task_type": "INVALID_TYPE", "direction": "test direction"}'
```

**Expected result**:
- HTTP status: `422`
- Body: `{"detail": [...]}` where `detail` is a non-empty array
- Each array item has keys `loc`, `msg`, `type`
- At least one item has `"task_type"` in its `loc` list

**Edge case**: Sending `task_type: "SPEC"` (uppercase) also returns 422, because the enum is case-sensitive (`"spec"` is valid, `"SPEC"` is not).

---

### Scenario 2 — Valid task_type creates task (regression guard)

**Setup**: API is running.

**Action**:
```bash
curl -s -X POST https://api.coherencycoin.com/api/agent/tasks \
  -H "Content-Type: application/json" \
  -d '{"task_type": "impl", "direction": "Spec 037 regression: verify valid task_type creates task"}'
```

**Expected result**:
- HTTP status: `201`
- Body contains `"id"`, `"task_type": "impl"`, `"status": "pending"`

**Then cleanup** (optional):
```bash
TASK_ID=$(curl -s -X POST https://api.coherencycoin.com/api/agent/tasks \
  -H "Content-Type: application/json" \
  -d '{"task_type": "impl", "direction": "cleanup task"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
```

---

### Scenario 3 — No task created on 422

**Setup**: Get baseline task count.
```bash
BEFORE=$(curl -s https://api.coherencycoin.com/api/agent/tasks/count | python3 -c "import sys,json; print(json.load(sys.stdin)['total'])")
```

**Action**: Send invalid task_type.
```bash
curl -s -X POST https://api.coherencycoin.com/api/agent/tasks \
  -H "Content-Type: application/json" \
  -d '{"task_type": "notreal", "direction": "should not persist"}'
```

**Then**: Check count again.
```bash
AFTER=$(curl -s https://api.coherencycoin.com/api/agent/tasks/count | python3 -c "import sys,json; print(json.load(sys.stdin)['total'])")
echo "Before=$BEFORE After=$AFTER"
```

**Expected result**: `BEFORE == AFTER` — no task was persisted.

---

### Scenario 4 — Numeric task_type returns 422

**Setup**: API is running.

**Action**:
```bash
curl -s -X POST https://api.coherencycoin.com/api/agent/tasks \
  -H "Content-Type: application/json" \
  -d '{"task_type": 42, "direction": "numeric task_type"}'
```

**Expected result**:
- HTTP status: `422`
- `detail` is a list with at least one error referencing `task_type`
- No 500 server error

---

### Scenario 5 — Missing task_type field returns 422

**Setup**: API is running.

**Action**:
```bash
curl -s -X POST https://api.coherencycoin.com/api/agent/tasks \
  -H "Content-Type: application/json" \
  -d '{"direction": "missing task_type field"}'
```

**Expected result**:
- HTTP status: `422`
- `detail` contains an error with `"task_type"` in `loc` (field required error)
- Error `msg` references missing or required field

---

### Scenario 6 — Pytest regression test passes

**Setup**: Test environment with `api/` dependencies installed.

**Action**:
```bash
cd api && python3 -m pytest tests/test_api_error_handling.py::test_422_on_invalid_task_type -v
```

**Expected result**:
```
PASSED tests/test_api_error_handling.py::test_422_on_invalid_task_type
```

No errors, no skips, exit code 0.

---

## Acceptance Tests (CI Gate)

- [ ] `python3 -m pytest api/tests/test_api_error_handling.py::test_422_on_invalid_task_type -x -v` passes.
- [ ] All six verification scenarios above produce the stated results.
- [ ] `GET /api/agent/tasks/count` is unchanged after a 422 rejection (Scenario 3).
- [ ] `POST /api/agent/tasks` with `task_type: "impl"` still returns 201 (Scenario 2).

---

## Out of Scope

- Other 422 cases for `POST /api/agent/tasks` (empty `direction`, whitespace-only `direction`, missing `direction`, direction too long) — covered by specs 009 and 010.
- Changing the `TaskType` enum values (decision gate in spec 002/010).
- Adding new `task_type` variants — requires separate spec and enum update.
- Authentication / authorization on this endpoint — separate spec.

---

## Risks and Assumptions

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Enum values are extended without updating this spec | Low | Spec references `api/app/models/agent.py` TaskType as source of truth |
| Pydantic version upgrade changes error shape | Medium | Test asserts `loc`, `msg`, `type` exist — generic enough to survive minor changes |
| Case-insensitive matching added later | Low | Current spec is case-sensitive; any change requires a spec amendment |
| No authentication means anyone can send garbage | High | Accepted for MVP; rate limiting mitigates abuse; auth is separate spec |

---

## Known Gaps and Follow-up Tasks

- **Auth gate**: Endpoint is unauthenticated. `POST /api/agent/tasks` can be called by anyone. Tracked separately.
- **Rate limiting**: No per-IP rate limit on task creation. Tracked separately.
- **422 message stability**: The exact `msg` string in the 422 response is implementation-specific and could change between Pydantic versions. Tests should not assert exact message text, only structure.
- **`null` task_type**: Sending `task_type: null` (JSON null) behavior not explicitly tested; should also return 422.

---

## Concurrency Behavior

Validation is stateless and runs before any database/store write. Concurrent invalid requests are safe — each fails independently with 422 and no shared state is modified.

---

## Failure and Retry Behavior

If `POST /api/agent/tasks` returns 422 due to invalid `task_type`, the calling agent node should:
1. Log the 422 with the full `detail` array.
2. Mark the attempt as a configuration error (not a transient failure).
3. **Not retry** — the same request will always fail 422 until `task_type` is corrected.
4. Escalate to `needs_decision` or alert operators if the misconfiguration is unexpected.

---

## See Also

- [002-agent-orchestration-api.md](002-agent-orchestration-api.md) — Full `POST /api/agent/tasks` contract
- [009-api-error-handling.md](009-api-error-handling.md) — 422 response format contract
- [010-request-validation.md](010-request-validation.md) — Validation rules, `task_type` enum, field constraints
- [038-post-tasks-empty-direction-422.md](038-post-tasks-empty-direction-422.md) — Sibling spec: 422 for empty direction
