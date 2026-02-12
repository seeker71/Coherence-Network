# Spec: Request Validation

*Format: [specs/TEMPLATE.md](TEMPLATE.md)*

## Purpose

Tighten request validation so invalid input is rejected early with clear, consistent 422 (or 400) responses. Defines the **task_type** enum, **direction** length limits, and Pydantic refinements for the agent API (spec 002).

## Requirements

- [x] **task_type** — Enum: `spec` | `test` | `impl` | `review` | `heal`; any other value → 422
- [x] **direction** — String, min length 1, max length 5000; empty or missing or over limit → 422
- [x] **direction** — Optional refinement: strip leading/trailing whitespace before length check so that whitespace-only is rejected as too short
- [x] **status** (PATCH) — Enum: `pending` | `running` | `completed` | `failed` | `needs_decision`; invalid → 422
- [x] **progress_pct** (PATCH) — If present: integer only, 0–100 inclusive; wrong type or out of range → 422
- [x] **Pydantic** — Use `Field(..., min_length=..., max_length=...)` and `ge`/`le` where applicable; enums as `str` Enum for JSON schema
- [x] **PATCH body** — At least one field required; empty body or all optional fields null/absent → 400

## API Contract (if applicable)

### `POST /api/agent/tasks`

**Request (valid)**

- `direction`: string, 1–5000 chars (after optional strip of leading/trailing whitespace)
- `task_type`: string, one of `spec`, `test`, `impl`, `review`, `heal`
- `context`: object (optional)

**Response 422 — Validation error**

| Case | Example | Response |
|------|---------|----------|
| Invalid task_type | `task_type: "invalid"` or `"foo"` | 422, detail describes allowed enum values |
| Missing task_type | body without `task_type` | 422 |
| Missing direction | body without `direction` | 422 |
| direction null | `direction: null` | 422 |
| direction empty | `direction: ""` | 422 |
| direction whitespace-only | `direction: "   "` (if strip refinement applied) | 422 |
| direction too long | length &gt; 5000 | 422 |
| direction boundary valid | exactly 5000 chars | 201 |

### `PATCH /api/agent/tasks/{id}`

**Request (valid)** — At least one of: `status`, `output`, `progress_pct`, `current_step`, `decision_prompt`, `decision`

**Response 400**

- Empty body or all provided fields null/absent → 400, detail "At least one field required"

**Response 422 — Validation error**

| Case | Example | Response |
|------|---------|----------|
| Invalid status | `status: "invalid"` | 422 |
| progress_pct &lt; 0 | `progress_pct: -1` | 422 |
| progress_pct &gt; 100 | `progress_pct: 101` | 422 |
| progress_pct wrong type | `progress_pct: "50"` | 422 |
| progress_pct boundary | `progress_pct: 0` or `100` | 200, accepted |

### `GET /api/agent/route`

**Query params**

- `task_type`: required, same enum as POST; missing or invalid → 422

### List/attention endpoints

- `limit`: 1–100, default 20; `offset`: ≥ 0, default 0; invalid → 422 (already in spec 002).

## Data Model (if applicable)

**Enums (Pydantic / OpenAPI)**

- **TaskType**: `spec` | `test` | `impl` | `review` | `heal` — use `str` Enum so JSON accepts string values.
- **TaskStatus**: `pending` | `running` | `completed` | `failed` | `needs_decision`

**AgentTaskCreate**

```yaml
direction: string
  min_length: 1
  max_length: 5000
  # optional: strip whitespace before validation
task_type: TaskType  # enum above
context: object | null  # optional
```

**AgentTaskUpdate**

```yaml
status: TaskStatus | null
output: string | null
progress_pct: int (ge=0, le=100) | null  # integer only; reject string/float
current_step: string | null
decision_prompt: string | null
decision: string | null
# At least one field required (enforced in route or model)
```

**Pydantic refinements**

- Use `Field(..., min_length=1, max_length=5000)` for `direction`.
- Use `Field(None, ge=0, le=100)` for `progress_pct`.
- Use `field_validator` (or equivalent) for `progress_pct` to reject non-integer (e.g. string `"50"`) with a clear error.
- Enums: inherit from `str, Enum` so serialization and OpenAPI schema show string values.

## Files to Create/Modify

- `api/app/models/agent.py` — TaskType/TaskStatus enums, AgentTaskCreate (direction length, task_type), AgentTaskUpdate (status, progress_pct constraints and int-only validator)
- `api/app/routers/agent.py` — Ensure PATCH empty-body returns 400; rely on Pydantic for 422 on invalid payloads
- `api/tests/test_agent.py` — Tests for each validation case (no new file; tests already listed in spec 002; this spec does not add new test file)

## Acceptance Tests

Covered by `api/tests/test_agent.py` (see spec 002). Relevant cases:

- `test_post_task_invalid_task_type_returns_422`
- `test_post_task_empty_direction_returns_422`
- `test_post_task_direction_too_long_returns_422`
- `test_post_task_missing_direction_returns_422`
- `test_post_task_direction_null_returns_422`
- `test_post_task_missing_task_type_returns_422`
- `test_post_task_direction_5000_chars_returns_201`
- `test_patch_task_invalid_status_returns_422`
- `test_patch_task_progress_pct_out_of_range_returns_422`
- `test_patch_task_empty_body_returns_400`
- `test_patch_progress_pct_negative_returns_422`
- `test_patch_progress_pct_over_100_returns_422`
- `test_patch_progress_pct_boundary_0_and_100_succeed`
- `test_patch_progress_pct_string_returns_422`
- `test_route_without_task_type_returns_422`
- `test_route_invalid_task_type_returns_422`

All must pass; do not modify tests to make implementation pass.

## Out of Scope

- Query param validation (limit, offset, status filter) — already specified in spec 002
- Request body size limit (framework default)
- Max length for `output`, `current_step`, `decision_prompt`, `decision` (no limit in spec 002; can be added later if needed)

## Decision Gates

None.

## See also

- [002-agent-orchestration-api.md](002-agent-orchestration-api.md) — agent API and edge-case table
- [009-api-error-handling.md](009-api-error-handling.md) — error response format
- [011-pagination.md](011-pagination.md) — limit/offset validation
