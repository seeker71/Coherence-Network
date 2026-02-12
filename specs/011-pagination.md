# Spec: Pagination for Task List

## Purpose

Add explicit pagination (limit/offset) to GET /api/agent/tasks so clients can page through large task lists. Limit already exists; add offset and document default page size.

## Requirements

- [x] `limit`: int, default 20, min 1, max 100 (already exists)
- [x] `offset`: int, default 0, min 0 — skip N tasks
- [x] Response includes `total` (total matching count before pagination)
- [x] Tasks returned in descending order by created_at (newest first)

## API Contract

### GET /api/agent/tasks

**Query params:**
- `status`: optional filter
- `task_type`: optional filter
- `limit`: int, default 20, ge=1, le=100
- `offset`: int, default 0, ge=0

**Response 200**
```json
{
  "tasks": [...],
  "total": 42
}
```

## Files to Create/Modify

- `api/app/routers/agent.py` — add `offset` query param
- `api/app/services/agent_service.py` — list_tasks accepts offset, applies to slice
- `api/tests/test_agent.py` — test offset returns correct slice

## Acceptance Tests

- GET with offset=0 limit=5 returns first 5 tasks
- GET with offset=5 limit=5 returns next 5 tasks
- total is same regardless of limit/offset

## Out of Scope

- Cursor-based pagination (future)
- Sorting options (always newest first)

## See also

- [002-agent-orchestration-api.md](002-agent-orchestration-api.md) — GET /api/agent/tasks
- [010-request-validation.md](010-request-validation.md) — validation constraints

## Decision Gates

None.
