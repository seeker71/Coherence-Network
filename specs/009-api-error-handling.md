# Spec: API Error Handling

## Purpose

Ensure consistent error response format across the API for client reliability and debugging. All error responses use a predictable schema.

## Requirements

- [x] 404 responses: `{ "detail": "human-readable message" }` (string)
- [x] 422 validation errors: FastAPI default format — keep as-is
- [x] 400 bad request: `{ "detail": "human-readable message" }`
- [x] Unhandled exceptions return 500 with `{ "detail": "Internal server error" }` (no stack trace)

## API Contract

### Error Response Schema

**404 Not Found**
```json
{ "detail": "Task not found" }
```

**400 Bad Request**
```json
{ "detail": "At least one field required" }
```

**422 Unprocessable Entity** (Pydantic validation)
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

**500 Internal Server Error**
```json
{ "detail": "Internal server error" }
```

## Files to Create/Modify

- `api/app/main.py` — add exception handler for unhandled exceptions (return 500 with generic message)
- `api/app/routers/agent.py` — verify all HTTPException use `detail` string consistently
- `api/tests/test_agent.py` — add tests: 404 format, 422 on invalid task_type, 422 on empty direction

## Acceptance Tests

- GET /api/agent/tasks/nonexistent returns 404 with `{ "detail": "Task not found" }`
- POST /api/agent/tasks with invalid task_type returns 422 with detail array
- POST /api/agent/tasks with empty direction returns 422
- PATCH with invalid status returns 422
- Unhandled exception returns 500 with `{ "detail": "Internal server error" }`

## Out of Scope

- Custom exception middleware for logging (separate spec)
- Rate limit 429 responses

## See also

- [010-request-validation.md](010-request-validation.md) — validation constraints (422)
- [014-deploy-readiness.md](014-deploy-readiness.md) — deploy checklist

## Decision Gates

None.
