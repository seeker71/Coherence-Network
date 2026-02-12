# Spec: API Error Handling

## Purpose

Ensure consistent error response format across the API for client reliability and debugging. All error responses use a predictable schema. Clients can depend on 422 for validation, 404 for missing resources, and a single error envelope for simple errors.

## Requirements

- [x] **Error schema**: Simple errors (400, 404, 500) use `{ "detail": "human-readable message" }` (detail is a string).
- [x] **422 validation**: Pydantic/request validation failures use FastAPI default format — keep as-is; `detail` is an array of validation items.
- [x] **404 consistency**: Every 404 response has the same shape (`{ "detail": string }`); message is resource-specific but consistent (e.g. "Task not found", "Project not found").
- [x] **400 bad request**: `{ "detail": "human-readable message" }`.
- [x] Unhandled exceptions return 500 with `{ "detail": "Internal server error" }` (no stack trace or internal details).

## API Contract

### Error Response Schema

**Simple error (400, 404, 500)**  
Single top-level field `detail` as a string. No extra fields.

```json
{ "detail": "Task not found" }
```

**422 Unprocessable Entity (validation)**  
Used for Pydantic request body/query/path validation failures. Do not override FastAPI’s default. `detail` is an array of objects with at least `loc`, `msg`, `type`; optional `ctx`, etc.

```json
{
  "detail": [
    {
      "loc": ["body", "task_type"],
      "msg": "value is not a valid enumeration member",
      "type": "type_error.enum"
    },
    {
      "loc": ["body", "direction"],
      "msg": "ensure this value has at least 1 characters",
      "type": "value_error.any_str.min_length"
    }
  ]
}
```

- `loc`: array of strings (e.g. `["body", "field"]`, `["query", "param"]`).
- `msg`: string, human-readable message.
- `type`: string, error type (e.g. `type_error.enum`, `value_error.any_str.min_length`).

### Per-status examples

**404 Not Found** (consistent shape across all resources)

```json
{ "detail": "Task not found" }
```

```json
{ "detail": "Project not found" }
```

**400 Bad Request**

```json
{ "detail": "At least one field required" }
```

**500 Internal Server Error**

```json
{ "detail": "Internal server error" }
```

## Data Model

```yaml
# Simple error response (400, 404, 500)
ErrorDetail:
  detail: string

# 422 validation response (FastAPI default; do not change)
ValidationErrorDetail:
  detail:
    type: array
    items:
      loc: array of string
      msg: string
      type: string
      # optional: ctx, etc.
```

## Files to Create/Modify

- `api/app/main.py` — exception handler for unhandled exceptions (return 500 with generic message)
- `api/app/models/error.py` — `ErrorDetail` schema (detail: string) for OpenAPI 400/404/500
- `api/app/routers/agent.py` — all HTTPException use `detail` string; 404 "Task not found"; `responses` for 400/404
- `api/app/routers/projects.py` — 404 use `detail` string "Project not found"; `responses` for 404
- `api/app/routers/import_stack.py` — 400/422 use `detail` string or FastAPI default
- `api/tests/test_agent.py` — tests: 404 format, 422 on invalid task_type, 422 on empty direction

## Acceptance Tests

- GET /api/agent/tasks/nonexistent returns 404 with body `{ "detail": "Task not found" }`.
- POST /api/agent/tasks with invalid `task_type` returns 422 with `detail` array of validation items.
- POST /api/agent/tasks with empty `direction` returns 422.
- PATCH with invalid `status` returns 422.
- Unhandled exception returns 500 with `{ "detail": "Internal server error" }`.
- 404 responses have no extra top-level keys (only `detail`).

See `api/tests/test_agent.py` and `api/tests/test_health.py` (where 009-related tests may live); all must pass.

## Verification (iteration 2)

- **422 validation**: Do not override FastAPI’s validation exception handler. Pydantic failures produce `detail` as an array of `{ loc, msg, type }`; no custom handler.
- **404 consistency**: Every 404 response has exactly one top-level key `detail` (string). No extra keys. Message is resource-specific: "Task not found", "Project not found".
- **Error schema**: 400, 404, 500 use `ErrorDetail` (single field `detail: string`). OpenAPI documents this via `responses` on routes and optional `api/app/models/error.py`.

## Out of Scope

- Custom exception middleware for logging (separate spec).
- Rate limit 429 responses.
- Changing FastAPI’s 422 response structure.

## See also

- [010-request-validation.md](010-request-validation.md) — validation constraints (422 triggers)
- [014-deploy-readiness.md](014-deploy-readiness.md) — deploy checklist

## Decision Gates

None.
