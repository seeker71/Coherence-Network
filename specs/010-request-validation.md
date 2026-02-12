# Spec: Request Validation

## Purpose

Tighten request validation so invalid input is rejected early with clear error messages. Extends Pydantic models used by the agent API.

## Requirements

- [x] `task_type`: enum `spec | test | impl | review | heal` — reject invalid values with 422
- [x] `direction`: string, min 1 char, max 5000 chars
- [x] `status` (PATCH): enum `pending | running | completed | failed | needs_decision`
- [x] Optional fields (progress_pct, context) validated: progress_pct 0-100 if present

## API Contract

### POST /api/agent/tasks

**Invalid request examples → 422:**

- `task_type: "invalid"` → 422
- `direction: ""` → 422
- `direction` missing → 422
- `direction` longer than 5000 chars → 422

### PATCH /api/agent/tasks/{id}

**Invalid request examples → 422:**

- `status: "invalid"` → 422
- `progress_pct: 150` → 422 (if progress_pct present, must be 0-100)

## Data Model

```yaml
AgentTaskCreate:
  direction: string (min_length=1, max_length=5000)
  task_type: Literal["spec", "test", "impl", "review", "heal"]
  context: object | null (optional)

AgentTaskUpdate:
  status: Literal["pending", "running", "completed", "failed", "needs_decision"] | null
  output: string | null
  progress_pct: int (0-100) | null
  current_step: string | null
  decision_prompt: string | null
  decision: string | null
```

## Files to Create/Modify

- `api/app/models/agent.py` — add Field constraints (min_length, max_length, ge, le)
- `api/tests/test_agent.py` — tests for each validation case

## Acceptance Tests

- POST with task_type "foo" returns 422
- POST with direction "" returns 422
- POST with direction 5001 chars returns 422
- PATCH with status "invalid" returns 422

## Out of Scope

- Query param validation (limit, etc.) — already validated
- Request body size limit (framework default)

## See also

- [009-api-error-handling.md](009-api-error-handling.md) — error response format
- [011-pagination.md](011-pagination.md) — limit/offset validation

## Decision Gates

None.
