# Spec 037 — POST /api/agent/tasks: Invalid `task_type` Returns 422

## Summary

When a client submits `POST /api/agent/tasks` with a `task_type` value that is not a member of the
allowed `TaskType` enum, the API must respond with HTTP **422 Unprocessable Entity**. The response
body must contain a `detail` array following FastAPI/Pydantic conventions so that clients can
programmatically identify the offending field.

This spec codifies the validation contract and mandates a dedicated test to lock it in as a
regression guard. The implementation is already present in `api/app/models/agent.py`
(`AgentTaskCreate.task_type_must_be_enum`); this spec formalises the requirements, verification
scenarios, and traceability.

---

## Goal

Ensure predictable, machine-parseable error responses when clients supply invalid `task_type`
values, in accordance with the error-handling standard defined in specs 009 and 010.

---

## Requirements

### Functional

| ID | Requirement |
|----|-------------|
| R1 | `POST /api/agent/tasks` with `task_type` outside `{ spec, test, impl, review, heal, code-review, merge, deploy, verify, reflect }` MUST return HTTP 422. |
| R2 | The 422 response body MUST contain a top-level `detail` key whose value is an array of one or more validation-error objects. |
| R3 | At least one error object in `detail` MUST reference `task_type` in its `loc` array (e.g. `["body","task_type"]`). |
| R4 | The `msg` field of the matching error object MUST be a non-empty human-readable string. |
| R5 | Valid `task_type` values MUST continue to be accepted (no regression on happy path). |
| R6 | A dedicated pytest test named `test_post_task_invalid_task_type_returns_422` MUST exist in `api/tests/test_agent.py` and must pass in CI. |

### Non-Functional

- Validation occurs at the Pydantic model layer (before any database write).
- No partial task record is created for rejected requests.
- Response time for a 422 rejection is < 200 ms (validation-only code path).

---

## API Contract

### Endpoint

```
POST /api/agent/tasks
Content-Type: application/json
```

### Request — invalid case

```json
{
  "direction": "Do something useful",
  "task_type": "invalid"
}
```

`task_type` may be any string that does not exactly match a member of `TaskType`:
`spec | test | impl | review | heal | code-review | merge | deploy | verify | reflect`.

### Response — 422

```json
{
  "detail": [
    {
      "loc": ["body", "task_type"],
      "msg": "task_type must be one of ['spec', 'test', 'impl', 'review', 'heal', 'code-review', 'merge', 'deploy', 'verify', 'reflect']; got 'invalid'",
      "type": "value_error"
    }
  ]
}
```

> The exact `msg` wording and `type` string may vary with Pydantic version; tests MUST assert on
> structure (`detail` is a list, `loc` contains `task_type`) rather than exact wording.

### Response — 201 (happy path, no regression)

```json
{
  "id": "...",
  "direction": "Do something useful",
  "task_type": "impl",
  "status": "pending",
  ...
}
```

---

## Data Model

Validation is enforced by `AgentTaskCreate` in `api/app/models/agent.py`:

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
    def task_type_must_be_enum(cls, v):
        if isinstance(v, TaskType):
            return v
        if isinstance(v, str) and v in (e.value for e in TaskType):
            return TaskType(v)
        raise ValueError(
            f"task_type must be one of {[e.value for e in TaskType]}; got {v!r}"
        )
```

No schema migration is needed. This validation is a pure in-memory Pydantic check.

---

## Files to Create / Modify

| File | Change |
|------|--------|
| `api/tests/test_agent.py` | Add `test_post_task_invalid_task_type_returns_422` (and companion happy-path assertion if not already present). |
| `api/app/models/agent.py` | **Read-only** for this spec. Validator already exists; do not modify unless R1–R4 require a fix. |
| `api/app/routers/agent_tasks_routes.py` | **Read-only**. Route `responses` already document 422; no change required. |

---

## Verification Scenarios

### Scenario 1 — Canonical invalid `task_type` string

**Setup:** API is running and the task queue is empty (or at any state — validation fires before DB write).

**Action:**
```bash
API=http://localhost:8000
curl -s -w "\n%{http_code}" -X POST "$API/api/agent/tasks" \
  -H "Content-Type: application/json" \
  -d '{"direction": "Do something", "task_type": "invalid"}'
```

**Expected result:**
- HTTP status `422`
- Body is JSON with top-level `detail` array
- At least one element in `detail` has `loc` containing `"task_type"`
- `msg` is a non-empty string

**Edge:** The task queue length does not increase after this request (no phantom record).

---

### Scenario 2 — Completely absent `task_type`

**Setup:** Same as Scenario 1.

**Action:**
```bash
curl -s -w "\n%{http_code}" -X POST "$API/api/agent/tasks" \
  -H "Content-Type: application/json" \
  -d '{"direction": "Do something"}'
```

**Expected result:**
- HTTP status `422`
- `detail` array references `task_type` (missing required field)

**Edge:** Missing field error is distinct from invalid-value error; the `type` key differs (`missing` vs `value_error`).

---

### Scenario 3 — Numeric `task_type`

**Setup:** Same as Scenario 1.

**Action:**
```bash
curl -s -w "\n%{http_code}" -X POST "$API/api/agent/tasks" \
  -H "Content-Type: application/json" \
  -d '{"direction": "Do something", "task_type": 42}'
```

**Expected result:**
- HTTP status `422`
- `detail` array references `task_type`

**Edge:** Integer values are not coerced to strings; must be rejected cleanly.

---

### Scenario 4 — Case-sensitive mismatch (`"SPEC"` instead of `"spec"`)

**Setup:** Same as Scenario 1.

**Action:**
```bash
curl -s -w "\n%{http_code}" -X POST "$API/api/agent/tasks" \
  -H "Content-Type: application/json" \
  -d '{"direction": "Do something", "task_type": "SPEC"}'
```

**Expected result:**
- HTTP status `422`
- `detail` references `task_type`

**Rationale:** `TaskType` is case-sensitive; `"SPEC"` ≠ `"spec"`. Clients must use lowercase.

---

### Scenario 5 — Happy path: valid `task_type` (regression guard)

**Setup:** Same as Scenario 1.

**Action:**
```bash
curl -s -w "\n%{http_code}" -X POST "$API/api/agent/tasks" \
  -H "Content-Type: application/json" \
  -d '{"direction": "Implement feature X", "task_type": "impl"}'
```

**Expected result:**
- HTTP status `201`
- Response JSON contains `"task_type": "impl"` and `"status": "pending"`
- A task record exists: `GET /api/agent/tasks` returns list including the new task ID

---

## Acceptance Tests

```
PASS: test_post_task_invalid_task_type_returns_422
  - POST with task_type="invalid" → 422
  - response.json()["detail"] is a list
  - any(item for item in detail if "task_type" in str(item.get("loc", [])))

PASS: test_post_task_valid_task_type_returns_201  (regression guard, existing or new)
  - POST with task_type="impl" → 201
```

Run command:
```bash
python3 -m pytest api/tests/test_agent.py -k "task_type" -v
```

Full test suite (broader regression):
```bash
python3 -m pytest api/tests/test_agent_task_persistence.py -x -v
```

---

## Out of Scope

- Other 422 cases for `POST /api/agent/tasks` (empty `direction`, missing `direction`, `direction` too long) — covered by specs 009/010 and separate tests.
- Changing the `TaskType` enum values — gated by spec 002.
- Auth/RBAC on the endpoint — gated by the C1 auth milestone.

---

## Risks and Assumptions

| ID | Risk | Likelihood | Impact | Mitigation |
|----|------|-----------|--------|------------|
| RA1 | Pydantic v2 `type_error` strings differ from v1 | Medium | Low | Tests assert on `loc` structure only, not exact `msg` or `type` wording. |
| RA2 | Future `TaskType` enum expansion silently accepts previously-invalid values | Low | Medium | Update this test whenever new members are added to `TaskType`. |
| RA3 | No auth gate — endpoint is publicly writable | High | Medium | Intentional for MVP; auth deferred to C1 milestone. |
| RA4 | Rate-limiting absent; adversary can flood with invalid requests | Medium | Low | Deferred to M1 rate-limiter milestone. |

**Assumptions:**
- The API runs FastAPI ≥ 0.95 with Pydantic v2; validation pipeline is standard.
- `AgentTaskCreate` field validator fires before any service/DB call.
- `test_agent.py` is the canonical location for POST /api/agent/tasks validation tests.

---

## Known Gaps and Follow-up Tasks

| ID | Gap | Follow-up |
|----|-----|-----------|
| KG1 | No test covers `null` as `task_type` value | Add `test_post_task_null_task_type_returns_422` in a follow-up. |
| KG2 | Case-insensitive normalization might be desirable UX in future | Decide in spec 002 revision; for now spec 037 mandates rejection. |
| KG3 | Integration-level test against production endpoint (not just unit/httpx) | Add as part of smoke-test suite in spec 014. |

---

## Traceability

| Reference | Detail |
|-----------|--------|
| Spec 002 | POST /api/agent/tasks full contract, TaskType enum |
| Spec 009 | API error handling, 422 format |
| Spec 010 | Request validation rules, test naming conventions |
| Model | `api/app/models/agent.py` — `AgentTaskCreate`, `TaskType` |
| Route | `api/app/routers/agent_tasks_routes.py` — `create_task` |
| Tests | `api/tests/test_agent.py`, `api/tests/test_agent_task_persistence.py` |
