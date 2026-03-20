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


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: 002, 010

## Task Card

```yaml
goal: Add explicit pagination (limit/offset) to GET /api/agent/tasks so clients can page through large task lists.
files_allowed:
  - api/app/routers/agent.py
  - api/app/services/agent_service.py
  - api/tests/test_agent.py
done_when:
  - `limit`: int, default 20, min 1, max 100 (already exists)
  - `offset`: int, default 0, min 0 — skip N tasks
  - Response includes `total` (total matching count before pagination)
  - Tasks returned in descending order by created_at (newest first)
  - Invalid limit (e.g. 0 or >100) or offset (e.g. <0) returns 422
commands:
  - python3 -m pytest api/tests/test_ideas.py -x -v
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

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


### Input Validation

- All string fields: min_length=1, max_length=1000
- Numeric fields: appropriate min/max bounds
- Required fields validated; missing returns 422
- Unknown fields rejected (Pydantic extra="forbid" where applicable)

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

## Concurrency Behavior

- **Read operations**: Safe for concurrent access; no locking required.
- **Write operations**: Last-write-wins semantics; no optimistic locking for MVP.
- **Recommendation**: Clients should not assume atomic read-modify-write without explicit ETag support.

## Failure and Retry Behavior

- **Task failure**: Log error, mark task failed, advance to next item or pause for human review.
- **Retry logic**: Failed tasks retry up to 3 times with exponential backoff (initial 2s, max 60s).
- **Partial completion**: State persisted after each phase; resume from last checkpoint on restart.
- **External dependency down**: Pause pipeline, alert operator, resume when dependency recovers.
- **Timeout**: Individual task phases timeout after 300s; safe to retry from last phase.

## Risks and Known Gaps

- **No auth gate**: Endpoints unprotected until C1 auth middleware applied.
- **No rate limiting**: Subject to abuse until M1 rate limiter active.
- **Single-node only**: No distributed locking; concurrent access may race.
- **Follow-up**: Add distributed locking for multi-worker pipelines.


## Verification

```bash
python3 -m pytest api/tests/test_ideas.py -x -v
```
