# Spec: Agent Service Routes spec task_type to Local Model — Test

## Purpose

Ensure that the agent service routes the `spec` task_type to a local model (Ollama) so the pipeline and API contract (spec 002, 005) are enforced by an explicit test. This validates routing for spec-phase work without relying on cloud models.

## Requirements

- [ ] **Test exists**: A test in `api/tests/test_agent.py` calls `GET /api/agent/route?task_type=spec` and asserts response status code is 200 and that the returned `model` indicates a local model (e.g. contains "ollama", "glm", or "qwen" in the model string, or response includes `tier: "local"`).
- [ ] **Contract**: The test documents that `spec` task_type is routed to local tier per the routing table in [002-agent-orchestration-api.md](002-agent-orchestration-api.md) (spec | test | impl | review → local; heal → claude).

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

## Data Model (if applicable)

Routing is implemented in `api/app/services/agent_service.py`; task_type → model mapping is defined in [002-agent-orchestration-api.md](002-agent-orchestration-api.md) and docs/MODEL-ROUTING.md. No new data model; test only.

## Files to Create/Modify

- `api/tests/test_agent.py` — add or retain test: `GET /api/agent/route?task_type=spec` returns 200 with model indicating local (e.g. `test_spec_tasks_route_to_local`).

Implementation of routing is already in scope of spec 002 (`api/app/services/agent_service.py`, `api/app/routers/agent.py`); this spec focuses on the test.

## Acceptance Tests

- **spec → local**: `GET /api/agent/route?task_type=spec` returns 200 and the response body has a `model` that indicates a local model (e.g. contains "ollama", "glm", or "qwen") and/or `tier` is "local". The corresponding test in `api/tests/test_agent.py` must pass.

See `api/tests/test_agent.py` — the test named for this behavior (e.g. `test_spec_tasks_route_to_local`) must pass.

## Out of Scope

- Routing for other task_types (test, impl, review → local; heal → claude) — covered by parallel tests and spec 002.
- Changing the routing implementation or model names (decision gate in 002 / MODEL-ROUTING).

## Decision Gates (if any)

None. Adding or expanding this test does not require new dependencies or API contract changes.

## See also

- [002-agent-orchestration-api.md](002-agent-orchestration-api.md) — routing table, GET /api/agent/route contract, test list
- [006-overnight-backlog.md](006-overnight-backlog.md) — item 25: Add test: agent_service routes spec task_type to local model
- [005-project-manager-pipeline.md](005-project-manager-pipeline.md) — spec/test/impl/review use local models
- [010-request-validation.md](010-request-validation.md) — task_type enum
- [044-agent-service-test-task-type-local-model-test.md](044-agent-service-test-task-type-local-model-test.md) — parallel spec for test task_type → local
