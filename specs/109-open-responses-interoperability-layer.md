# Spec 109: Open Responses Interoperability Layer

**Idea ID**: `109-open-responses-interoperability-layer`
**Status**: Approved
**Author**: Product Manager Agent
**Date**: 2026-03-28

---

## Summary

Introduce a normalized **Open Responses** adapter in the agent execution path so that tasks can move across providers (Claude, Cursor, Codex, Gemini, OpenRouter) without per-provider prompt rewrites. Every task execution is wrapped in an `open_responses_v1` envelope that captures provider, model, and input in a stable, auditable schema — regardless of which executor actually runs the task.

This reduces provider lock-in, enables operator audit trails, and makes multi-provider A/B routing possible without modifying task-level prompt logic.

---

## Goal

Every task creation in `agent_service.create_task()` must produce a `normalized_response_call` entry in the task context that follows the Open Responses v1 schema. The same task direction string must appear verbatim in the normalized call regardless of the executor chosen. Route decisions must also carry `request_schema: open_responses_v1` as a top-level field.

---

## Requirements

### Functional

- **REQ-1**: Every `AgentTask` created via `agent_service.create_task()` must include a `normalized_response_call` key in its `context` dict.
- **REQ-2**: The `normalized_response_call` must conform to the `NormalizedResponseCall` Pydantic model (fields: `task_id`, `executor`, `provider`, `model`, `request_schema`, `input`).
- **REQ-3**: `request_schema` must equal `"open_responses_v1"` for all executors (cursor, codex, claude, gemini, openrouter, openclaw).
- **REQ-4**: The `input` list must contain exactly one item: `{"role": "user", "content": [{"type": "input_text", "text": <direction>}]}`.
- **REQ-5**: The direction text in `input[0].content[0].text` must be identical across executors for the same logical task.
- **REQ-6**: `model` in the normalized call must be stripped of provider prefixes (e.g., `"cursor/gpt-4o"` becomes `"gpt-4o"`).
- **REQ-7**: The `route_decision` dict (also in task context) must include `request_schema: "open_responses_v1"`.
- **REQ-8**: When `provider_usage_service` persists a task's execution evidence, it must include the `request_schema` field from the normalized call.
- **REQ-9**: The adapter must not alter the task `direction` string — normalization is envelope-only; no prompt rewriting.
- **REQ-10**: Invalid or missing executor values must fall back to `"claude"` without raising.

### Non-Functional

- **PERF**: Normalization adds less than 1 ms to task creation (in-process dict construction, no I/O).
- **COMPAT**: Existing task fields (`id`, `direction`, `task_type`, `status`, etc.) must be unaffected.
- **OBSERVABILITY**: `normalized_response_call` is persisted in the task store so operator audit queries can verify actual execution path.

---

## Data Model

### `NormalizedResponseCall` — `api/app/models/agent.py:254`

```python
class NormalizedResponseCall(BaseModel):
    """Provider-agnostic Open Responses-compatible task call envelope."""
    task_id: str
    executor: str
    provider: str
    model: str
    request_schema: str = "open_responses_v1"
    input: List[Dict[str, Any]]
```

### `input` field structure

```json
[
  {
    "role": "user",
    "content": [
      {
        "type": "input_text",
        "text": "<task direction verbatim>"
      }
    ]
  }
]
```

### Route decision field extension

```json
{
  "executor": "cursor",
  "model": "cursor/auto",
  "command": "agent -p ...",
  "request_schema": "open_responses_v1"
}
```

---

## Files to Create / Modify

| File | Change |
|---|---|
| `api/app/models/agent.py` | `NormalizedResponseCall` model (present at line 254) |
| `api/app/services/agent_routing_service.py` | `build_normalized_response_call()`, `normalize_open_responses_model()` (present at line 123) |
| `api/app/services/agent_service_crud.py` | Inject `normalized_response_call` into task context on creation (line ~165) |
| `api/app/services/agent_service_completion_tracking.py` | Read `request_schema` from task context for persistence (line ~201) |
| `api/tests/test_agent_executor_policy.py` | `test_open_responses_normalization_is_shared_across_executors` (line 338) |

---

## API Contract

No new external API routes are added for initial rollout. The normalized call is an internal adapter that is persisted in the task store and visible via the existing task detail endpoint.

### Existing endpoint: `GET /api/agent/tasks/{task_id}`

**Response** (relevant new field in `context`):

```json
{
  "id": "task_abc123",
  "direction": "Implement feature X",
  "context": {
    "executor": "cursor",
    "normalized_response_call": {
      "task_id": "task_abc123",
      "executor": "cursor",
      "provider": "openai",
      "model": "gpt-4o",
      "request_schema": "open_responses_v1",
      "input": [
        {
          "role": "user",
          "content": [{"type": "input_text", "text": "Implement feature X"}]
        }
      ]
    },
    "route_decision": {
      "executor": "cursor",
      "model": "cursor/gpt-4o",
      "request_schema": "open_responses_v1"
    }
  }
}
```

### Input Validation

- `executor`: string, normalized to known set (`cursor`, `codex`, `claude`, `gemini`, `openrouter`, `openclaw`); unknown values fall back to `"claude"`.
- `model`: string, provider prefix stripped during normalization; empty model uses executor default.
- `direction`: string, passed verbatim into normalized input; must be non-empty (validated upstream at task creation).
- Missing `executor` in context: treated as `"claude"`.

---

## Implementation Notes

### `build_normalized_response_call()` — `api/app/services/agent_routing_service.py:131`

Constructs the `open_responses_v1` envelope by:
1. Calling `normalize_executor(executor, default="claude")` to canonicalize the executor name.
2. Calling `normalize_open_responses_model(model)` to strip executor prefix from model string.
3. Wrapping the task direction verbatim in the `input` array following the OpenAI Responses API input format.

### `normalize_open_responses_model()` — `api/app/services/agent_routing_service.py:123`

Strips executor prefix from model names:
- `"cursor/gpt-4o"` becomes `"gpt-4o"`
- `"claude-sonnet-4-6"` passes through unchanged (no `/`)
- `""` passes through as empty string

---

## Verification Scenarios

These scenarios are concrete and runnable. The reviewer will execute them against the live API or test suite.

### Scenario 1 — Normalized call present on task creation (core contract)

**Setup**: API running with `AGENT_TASKS_PERSIST=0` (in-memory, no DB required)

**Action**:
```bash
curl -s -X POST https://api.coherencycoin.com/api/agent/tasks \
  -H "Content-Type: application/json" \
  -d '{"direction":"Test open responses","task_type":"impl","context":{"executor":"cursor"}}'
```

**Expected**:
- HTTP 200 or 201
- `context.normalized_response_call.request_schema == "open_responses_v1"`
- `context.normalized_response_call.input[0].content[0].type == "input_text"`
- `context.normalized_response_call.input[0].content[0].text == "Test open responses"`
- `context.route_decision.request_schema == "open_responses_v1"`

**Edge — missing executor**:
```bash
curl -s -X POST https://api.coherencycoin.com/api/agent/tasks \
  -H "Content-Type: application/json" \
  -d '{"direction":"Edge test","task_type":"impl","context":{}}'
```
- Normalized call still present; `executor` defaults to `"claude"` or configured default.

---

### Scenario 2 — Identical direction across two executors (provider-agnostic contract)

**Setup**: Local test environment

**Action (pytest)**:
```bash
cd api && python -m pytest tests/test_agent_executor_policy.py::test_open_responses_normalization_is_shared_across_executors -v
```

**Expected**:
- Test passes (defined at line 338)
- Both `cursor` and `codex` tasks have `request_schema == "open_responses_v1"`
- `cursor_call["input"][0]["content"][0]["text"] == claw_call["input"][0]["content"][0]["text"]`
- `route_decision["request_schema"] == "open_responses_v1"` for both

**Edge — unknown executor**:
```python
task = agent_service.create_task(AgentTaskCreate(
    direction="Unknown executor", task_type=TaskType.IMPL,
    context={"executor": "foobar"}
))
assert task["context"]["normalized_response_call"]["executor"] == "claude"
assert task["context"]["normalized_response_call"]["request_schema"] == "open_responses_v1"
```

---

### Scenario 3 — Model prefix stripping

**Setup**: API running normally

**Action**:
```bash
curl -s -X POST https://api.coherencycoin.com/api/agent/tasks \
  -H "Content-Type: application/json" \
  -d '{"direction":"Strip prefix test","task_type":"impl","context":{"executor":"cursor","model":"cursor/gpt-4o"}}'
```

**Expected**:
- `context.normalized_response_call.model == "gpt-4o"` (prefix stripped)
- `context.normalized_response_call.executor == "cursor"` (unchanged)
- `context.route_decision.request_schema == "open_responses_v1"`

**Edge — bare model name** (`"gpt-4o"`, no prefix):
- `normalized_response_call.model == "gpt-4o"` (pass-through, unchanged)

---

### Scenario 4 — Full create-read audit cycle

**Setup**: API running normally (persistence enabled)

**Action**:
```bash
# Create task and capture ID
TASK_RESP=$(curl -s -X POST https://api.coherencycoin.com/api/agent/tasks \
  -H "Content-Type: application/json" \
  -d '{"direction":"Audit trail test","task_type":"spec","context":{"executor":"claude"}}')
TASK_ID=$(echo $TASK_RESP | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# Read back task detail
curl -s https://api.coherencycoin.com/api/agent/tasks/$TASK_ID
```

**Expected**:
- GET returns task with `id == $TASK_ID`
- `context.normalized_response_call.task_id == $TASK_ID`
- `context.normalized_response_call.provider` is non-empty string
- `context.normalized_response_call.request_schema == "open_responses_v1"`
- `context.normalized_response_call.input[0].content[0].text == "Audit trail test"`

**Edge — nonexistent task**:
```bash
curl -s -o /dev/null -w "%{http_code}" https://api.coherencycoin.com/api/agent/tasks/task_nonexistent_xyz_000
```
- Returns HTTP 404, not 500

---

### Scenario 5 — Pytest suite: all open-responses tests pass

**Setup**: Local API test environment

**Action**:
```bash
cd api && AGENT_TASKS_PERSIST=0 python -m pytest tests/test_agent_executor_policy.py -q -k "open_responses or route"
```

**Expected**:
- All matching tests pass (0 failures, 0 errors)
- Output includes `test_open_responses_normalization_is_shared_across_executors PASSED`

**Edge — full policy suite regression**:
```bash
cd api && python -m pytest tests/test_agent_executor_policy.py -q
```
- All tests pass; no regressions from the normalization layer addition

---

## Acceptance Tests

```bash
# Core normalization test
cd api && python -m pytest tests/test_agent_executor_policy.py::test_open_responses_normalization_is_shared_across_executors -v

# Full executor policy suite
cd api && python -m pytest tests/test_agent_executor_policy.py -q

# Route filter
cd api && python -m pytest tests/test_agent_executor_policy.py -q -k "open_responses or route"

# Spec quality validation
python3 scripts/validate_spec_quality.py --file specs/109-open-responses-interoperability-layer.md
```

---

## Concurrency Behavior

- **Normalization** is a pure in-process transformation with no shared state; concurrent task creation is safe.
- **Persistence** of `normalized_response_call` in task store uses the same last-write-wins semantics as other task context fields.
- No additional locking required for MVP.

---

## Failure and Retry Behavior

| Failure Mode | Behavior |
|---|---|
| `executor` not recognized | Falls back to `"claude"`; normalization proceeds |
| `model` is empty string | `normalize_open_responses_model("")` returns `""`; task created with empty model |
| `direction` is whitespace-only | Stripped to `""`; upstream validation at task creation catches this before normalization |
| Task store unavailable | Returns 503; safe to retry |
| Malformed POST body | Returns 422 with field-level errors |
| Database unavailable | Returns 503; client should retry with exponential backoff (initial 1s, max 30s) |

---

## Out of Scope

- Full migration of every legacy provider integration in one pass.
- Changes to UI rendering for task output display.
- Tool-call schema parity across providers (tracked as follow-up).
- Streaming response normalization.
- Authentication/authorization changes.

---

## Risks and Assumptions

| Risk | Likelihood | Mitigation |
|---|---|---|
| Provider-specific capabilities don't map 1:1 to `open_responses_v1` | Medium | Additive provider extension fields; core schema is minimal |
| Normalization layer introduces latency regression | Low | In-process dict construction; no I/O; benchmarked well under 1 ms |
| `direction` content contains provider-specific syntax | Medium | REQ-9: adapter is envelope-only; no prompt rewriting |
| Existing task context shape changes break consumers | Low | Normalization only adds new keys; no existing keys removed or renamed |

**Assumption**: Current agent execution contracts can be wrapped without breaking existing endpoint behavior (validated by existing test suite passing).

---

## Known Gaps and Follow-up Tasks

- `task_open_responses_tool_schema_parity_001`: Normalize tool-call schema parity across providers (function-calling, structured outputs).
- `task_open_responses_streaming_001`: Extend `open_responses_v1` to cover streaming delta events.
- `task_open_responses_audit_api_001`: Expose a dedicated `GET /api/agent/tasks/{id}/normalized-call` endpoint for operator audit UIs.
- `task_open_responses_validation_001`: Add strict Pydantic validation for `NormalizedResponseCall.input` schema so malformed envelopes are caught at construction time.

---

## Decision Gates

- **Gate 1**: Decide whether normalization is required for all task types (`spec`, `test`, `impl`, `review`, `heal`) or phased by task type. Current implementation applies to all.
- **Gate 2**: Decide whether to expose `normalized_response_call` via a dedicated API endpoint or keep it internal to the task context store only.
