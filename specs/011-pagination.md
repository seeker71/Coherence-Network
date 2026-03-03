# Spec: Pagination for Task List

*Format: [specs/TEMPLATE.md](TEMPLATE.md)*

## Purpose

Add explicit pagination (limit/offset) to GET /api/agent/tasks so clients can page through large task lists. Default page size is 20; limit and offset allow slicing the list. Limit already existed in spec 002; this spec adds offset, documents default page size, and consolidates pagination behavior.

## Requirements

- [x] `limit`: int, default 20, min 1, max 100 (already exists)
- [x] `offset`: int, default 0, min 0 — skip N tasks
- [x] Response includes `total` (total matching count before pagination)
- [x] Tasks returned in descending order by created_at (newest first)
- [x] Invalid limit (e.g. 0 or >100) or offset (e.g. <0) returns 422

## API Contract (if applicable)

### `GET /api/agent/tasks`

**Request**
- Query params: `status` (optional), `task_type` (optional), `limit` (optional), `offset` (optional)

| Param    | Type | Default | Constraints | Description        |
|----------|------|---------|-------------|--------------------|
| status   | str  | —       | optional    | Filter by status   |
| task_type| str  | —       | optional    | Filter by task_type|
| limit    | int  | 20      | ge=1, le=100| Page size          |
| offset   | int  | 0       | ge=0        | Number of tasks to skip |

**Response 200**
```json
{
  "tasks": [
    {
      "id": "task_abc123",
      "direction": "...",
      "task_type": "impl",
      "status": "pending",
      "model": "...",
      "progress_pct": null,
      "current_step": null,
      "decision_prompt": null,
      "decision": null,
      "created_at": "2026-02-12T12:00:00Z",
      "updated_at": null
    }
  ],
  "total": 42
}
```

**Response 422** — Invalid query params (e.g. limit=0, limit=101, offset=-1). See [010-request-validation.md](010-request-validation.md).

## Data Model (if applicable)

Response shape for list endpoint:

```yaml
TaskListResponse:
  tasks: list[TaskSummary]   # paginated slice
  total: int                 # total matching count (unchanged by limit/offset)
```

Query params (validated):

```yaml
limit: int, default 20, ge=1, le=100
offset: int, default 0, ge=0
```

## Files to Create/Modify

- `api/app/routers/agent.py` — GET /api/agent/tasks: limit/offset query params, pass to service
- `api/app/services/agent_service.py` — list_tasks(..., limit, offset): apply offset then limit to slice
- `api/tests/test_agent.py` — tests for offset slice, limit/offset validation, total consistency

## Acceptance Tests

See `api/tests/test_agent.py`. All of the following must pass:

- GET with offset=0 limit=5 returns first 5 tasks (newest first)
- GET with offset=5 limit=5 returns next 5 tasks
- `total` is the same regardless of limit/offset (total matching count)
- GET with limit=0 returns 422
- GET with limit=101 returns 422
- GET with offset=-1 returns 422
- GET with no params uses default limit=20, offset=0

## Out of Scope

- Cursor-based pagination (future)
- Sorting options (order is always newest first per spec 002)
- Pagination for GET /api/agent/tasks/attention (has limit only; offset can be added later if needed)

## See also

- [002-agent-orchestration-api.md](002-agent-orchestration-api.md) — GET /api/agent/tasks, list shape
- [010-request-validation.md](010-request-validation.md) — limit/offset validation constraints

## Decision Gates (if any)

None.
