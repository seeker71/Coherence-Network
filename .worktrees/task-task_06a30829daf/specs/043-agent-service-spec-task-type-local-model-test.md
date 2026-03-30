# Spec: Agent Service Routes task_type (spec, test) to Local Model — Test

*Format: [specs/TEMPLATE.md](TEMPLATE.md)*

## Purpose

Ensure that the agent service routes the `spec` and `test` task_types to a local model (Ollama) so the pipeline and API contract (spec 002, 005) are enforced by explicit tests. This validates routing for spec-phase and test-phase work without relying on cloud models.

## Requirements

- [ ] **Spec → local test**: A test in `api/tests/test_agent.py` calls `GET /api/agent/route?task_type=spec` and asserts response status code is 200 and that the returned `model` indicates a local model (e.g. contains "ollama", "glm", or "qwen") and/or `tier` is "local". Test name: `test_spec_tasks_route_to_local`.
- [ ] **Test → local test**: A test in `api/tests/test_agent.py` calls `GET /api/agent/route?task_type=test` and asserts response status code is 200 and that the returned `model` indicates a local model (e.g. contains "ollama", "glm", or "qwen"). Test name: `test_test_tasks_route_to_local`.
- [ ] **Contract**: Both tests document that `spec` and `test` task_types are routed to local tier per the routing table in [002-agent-orchestration-api.md](002-agent-orchestration-api.md) (spec | test | impl | review → local; heal → claude).


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: 002, 005, 006, 010, 044

## Task Card

```yaml
goal: Ensure that the agent service routes the `spec` and `test` task_types to a local model (Ollama) so the pipeline and API contract (spec 002, 005) are enforced by explicit tests.
files_allowed:
  - api/tests/test_agent.py
done_when:
  - Spec → local test: A test in `api/tests/test_agent.py` calls `GET /api/agent/route?task_type=spec` and asserts respon...
  - Test → local test: A test in `api/tests/test_agent.py` calls `GET /api/agent/route?task_type=test` and asserts respon...
  - Contract: Both tests document that `spec` and `test` task_types are routed to local tier per the routing table in [00...
commands:
  - python3 -m pytest api/tests/test_agent_execution_model_resolution.py -x -v
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

## API Contract (if applicable)

### `GET /api/agent/route?task_type=spec`

**Request**

- Query param: `task_type=spec` (required). Optional: `executor` (default "claude": claude | cursor).

**Response 200**

```json
{
  "task_type": "spec",
  "model": "ollama/glm-4.7-flash:latest",
  "command_template": "...",
  "tier": "local",
  "executor": "claude"
}
```

The `model` field must identify a local model (e.g. ollama/..., glm-..., qwen...). The test may assert on `tier === "local"` or on model string containing local indicators (ollama, glm, qwen).

**Response 422** — Missing or invalid task_type (covered by other specs).

### `GET /api/agent/route?task_type=test`

**Request**

- Query param: `task_type=test` (required). Optional: `executor` (default "claude": claude | cursor).

**Response 200**

Same shape as above: `task_type`, `model`, `command_template`, `tier`, `executor`. The `model` field must identify a local model; `tier` must be `"local"` per routing table (002).

**Response 422** — Missing or invalid task_type (covered by other specs).


### Input Validation

- All string fields: min_length=1, max_length=1000
- Numeric fields: appropriate min/max bounds
- Required fields validated; missing returns 422
- Unknown fields rejected (Pydantic extra="forbid" where applicable)

## Data Model (if applicable)

Routing is implemented in `api/app/services/agent_service.py`; task_type → model mapping is defined in [002-agent-orchestration-api.md](002-agent-orchestration-api.md) and docs/MODEL-ROUTING.md. No new data model; test only.

## Files to Create/Modify

- `api/tests/test_agent.py` — add or retain: (1) `test_spec_tasks_route_to_local` for `GET /api/agent/route?task_type=spec`; (2) `test_test_tasks_route_to_local` for `GET /api/agent/route?task_type=test`. Both must assert 200 and model indicating local (ollama/glm/qwen) and/or tier local.

Implementation of routing is already in scope of spec 002 (`api/app/services/agent_service.py`, `api/app/routers/agent.py`); this spec focuses on the tests.

## Acceptance Tests

- **spec → local**: `GET /api/agent/route?task_type=spec` returns 200 and the response body has a `model` that indicates a local model (e.g. contains "ollama", "glm", or "qwen") and/or `tier` is "local". `test_spec_tasks_route_to_local` must pass.
- **test → local**: `GET /api/agent/route?task_type=test` returns 200 and the response body has a `model` that indicates a local model (e.g. contains "ollama", "glm", or "qwen"). `test_test_tasks_route_to_local` must pass.

See `api/tests/test_agent.py` — both tests named above must pass.

## Out of Scope

- Routing for other task_types (impl, review → local; heal → claude) — covered by parallel tests and spec 002.
- Changing the routing implementation or model names (decision gate in 002 / MODEL-ROUTING).

## Decision Gates (if any)

None. Adding or expanding these tests does not require new dependencies or API contract changes.

## See also

- [002-agent-orchestration-api.md](002-agent-orchestration-api.md) — routing table, GET /api/agent/route contract, test list
- [006-overnight-backlog.md](006-overnight-backlog.md) — item 25: Add test: agent_service routes spec task_type to local model
- [005-project-manager-pipeline.md](005-project-manager-pipeline.md) — spec/test/impl/review use local models
- [010-request-validation.md](010-request-validation.md) — task_type enum
- [044-agent-service-test-task-type-local-model-test.md](044-agent-service-test-task-type-local-model-test.md) — parallel spec for test task_type → local

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
