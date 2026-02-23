# Spec: LangGraph StateSchema Contract Adoption

## Purpose

Improve determinism and validation quality in graph-based agent orchestration by adopting explicit StateSchema/JSON Schema contracts for runtime state transitions.

## Requirements

- [ ] Define a canonical StateSchema for agent graph state with explicit required/optional fields.
- [ ] Validate graph state transitions against JSON Schema before and after critical nodes.
- [ ] Emit actionable error context when schema validation fails so retries/heal paths can trigger with clear causes.

## API Contract (if applicable)

N/A - no public API route changes in this spec.

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
