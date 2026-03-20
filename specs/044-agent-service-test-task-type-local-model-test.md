# Spec: Agent Service Routes test task_type to Local Model — Test

## Purpose

Ensure that the agent service routes the `test` task_type to a local model (Ollama) so the pipeline and API contract (spec 002, 005) are enforced by an explicit test. This validates routing for test-phase work without relying on cloud models.

## Requirements

- [ ] **Test exists**: A test in `api/tests/test_agent.py` calls `GET /api/agent/route?task_type=test` and asserts response status code is 200 and that the returned `model` indicates a local model (e.g. contains "ollama", "glm", or "qwen" in the model string, or response includes `tier: "local"`).
- [ ] **Contract**: The test documents that `test` task_type is routed to local tier per the routing table in [002-agent-orchestration-api.md](002-agent-orchestration-api.md) (spec | test | impl | review → local; heal → claude).


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: 002, 005, 006, 010, 043

## Task Card

```yaml
goal: Ensure that the agent service routes the `test` task_type to a local model (Ollama) so the pipeline and API contract (spec 002, 005) are enforced by an explicit test.
files_allowed:
  - api/tests/test_agent.py
done_when:
  - Test exists: A test in `api/tests/test_agent.py` calls `GET /api/agent/route?task_type=test` and asserts response sta...
  - Contract: The test documents that `test` task_type is routed to local tier per the routing table in [002-agent-orches...
commands:
  - python3 -m pytest api/tests/test_agent_execution_model_resolution.py -x -v
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

## API Contract (if applicable)

### `GET /api/agent/route?task_type=test`

**Request**

- Query param: `task_type=test` (required). Optional: `executor` (default "claude": claude | cursor).

**Response 200**

```json
{
  "task_type": "test",
  "model": "ollama/glm-4.7-flash:latest",
  "command_template": "...",
  "tier": "local",
  "executor": "claude"
}
```

The `model` field must identify a local model (e.g. ollama/..., glm-..., qwen...). The test may assert on `tier === "local"` or on model string containing local indicators (ollama, glm, qwen).

**Response 422** — Missing or invalid task_type (covered by other specs).


### Input Validation

- All string fields: min_length=1, max_length=1000
- Numeric fields: appropriate min/max bounds
- Required fields validated; missing returns 422
- Unknown fields rejected (Pydantic extra="forbid" where applicable)

## Data Model (if applicable)

Routing is implemented in `api/app/services/agent_service.py`; task_type → model mapping is defined in [002-agent-orchestration-api.md](002-agent-orchestration-api.md) and docs/MODEL-ROUTING.md. No new data model; test only.

## Files to Create/Modify

- `api/tests/test_agent.py` — add or retain test: `GET /api/agent/route?task_type=test` returns 200 with model indicating local (e.g. `test_test_tasks_route_to_local`).

Implementation of routing is already in scope of spec 002 (`api/app/services/agent_service.py`, `api/app/routers/agent.py`); this spec focuses on the test.

## Acceptance Tests

- **test → local**: `GET /api/agent/route?task_type=test` returns 200 and the response body has a `model` that indicates a local model (e.g. contains "ollama", "glm", or "qwen") and/or `tier` is "local". The corresponding test in `api/tests/test_agent.py` must pass.

See `api/tests/test_agent.py` — the test named for this behavior (e.g. `test_test_tasks_route_to_local`) must pass.

## Out of Scope

- Routing for other task_types (spec, impl, review → local; heal → claude) — covered by parallel specs (e.g. [043-agent-service-spec-task-type-local-model-test.md](043-agent-service-spec-task-type-local-model-test.md)) and spec 002.
- Changing the routing implementation or model names (decision gate in 002 / MODEL-ROUTING).

## Decision Gates (if any)

None. Adding or expanding this test does not require new dependencies or API contract changes.

## See also

- [002-agent-orchestration-api.md](002-agent-orchestration-api.md) — routing table, GET /api/agent/route contract, test list
- [006-overnight-backlog.md](006-overnight-backlog.md) — item 26: Add test: agent_service routes test task_type to local model
- [005-project-manager-pipeline.md](005-project-manager-pipeline.md) — spec/test/impl/review use local models
- [010-request-validation.md](010-request-validation.md) — task_type enum
- [043-agent-service-spec-task-type-local-model-test.md](043-agent-service-spec-task-type-local-model-test.md) — parallel spec for spec task_type → local

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
python3 -m pytest api/tests/test_agent_execution_model_resolution.py -x -v
```
