# Spec: LangGraph StateSchema Contract Adoption

## Purpose

Improve determinism and validation quality in graph-based agent orchestration by adopting explicit StateSchema/JSON Schema contracts for runtime state transitions.

## Requirements

- [ ] Define a canonical StateSchema for agent graph state with explicit required/optional fields.
- [ ] Validate graph state transitions against JSON Schema before and after critical nodes.
- [ ] Emit actionable error context when schema validation fails so retries/heal paths can trigger with clear causes.


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: none

## Task Card

```yaml
goal: Improve determinism and validation quality in graph-based agent orchestration by adopting explicit StateSchema/JSON Schema contracts for runtime state transitions.
files_allowed:
  - api/app/services/agent_service.py
  - api/app/models/schemas.py
  - api/tests/test_agent.py
  - docs/AGENT-ARCHITECTURE.md
done_when:
  - Define a canonical StateSchema for agent graph state with explicit required/optional fields.
  - Validate graph state transitions against JSON Schema before and after critical nodes.
  - Emit actionable error context when schema validation fails so retries/heal paths can trigger with clear causes.
commands:
  - cd api && python -m pytest api/tests/test_agent.py -q
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

## API Contract (if applicable)

N/A - no public API route changes in this spec.


### Input Validation

- All string fields: min_length=1, max_length=1000
- Numeric fields: appropriate min/max bounds
- Required fields validated; missing returns 422
- Unknown fields rejected (Pydantic extra="forbid" where applicable)

## Data Model (if applicable)

```yaml
AgentGraphState:
  required: [task_id, task_type, phase, direction]
  properties:
    task_id: { type: string }
    task_type: { type: string }
    phase: { type: string }
    direction: { type: string }
    attempt: { type: integer }
    model: { type: string }
    provider: { type: string }
    route_decision: { type: object }
```

## Files to Create/Modify

- `api/app/services/agent_service.py` - apply schema checkpoints in orchestration flow.
- `api/app/models/schemas.py` - add StateSchema-aligned graph state model.
- `api/tests/test_agent.py` - add schema validation pass/fail coverage.
- `docs/AGENT-ARCHITECTURE.md` - document graph-state contract and failure handling.

## Acceptance Tests

- `cd api && pytest -v tests/test_agent.py -k \"schema or state\"`
- Manual validation: execute one valid task and one intentionally malformed task context; verify deterministic schema-failure diagnostics.

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


## Verification

```bash
python3 scripts/validate_spec_quality.py --file specs/110-langgraph-stateschema-adoption.md
```

## Out of Scope

- Rewriting the full orchestration pipeline in LangGraph.
- UI-level visualization of graph state transitions.

## Risks and Assumptions

- Risk: strict schema checks may reject currently tolerated loose payloads; mitigate with phased strictness and migration logging.
- Assumption: existing task context fields can be normalized without loss of required behavior.

## Known Gaps and Follow-up Tasks

- Follow-up task: `task_graph_state_schema_versioning_001` for schema version migration support.

## Decision Gates (if any)

- Decide strict-fail vs warn-and-coerce behavior for non-critical schema mismatches in production.
