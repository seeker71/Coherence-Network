# Spec: Open Responses Interoperability Layer

## Purpose

Reduce provider lock-in and simplify model routing by introducing a normalized Open Responses interface in the agent execution path, so task execution can move across providers without per-provider payload rewrites.

## Requirements

- [ ] Add a provider-agnostic request/response adapter that can map current task execution payloads to Open Responses-compatible structures.
- [ ] Ensure at least two providers can execute through the same normalized interface without task-level prompt rewrites.
- [ ] Persist route and model evidence for each normalized call so operator audits can verify actual execution path.

## API Contract (if applicable)

N/A - no external API route changes required for initial adapter rollout.

## Data Model (if applicable)

```yaml
NormalizedResponseCall:
  properties:
    task_id: { type: string }
    provider: { type: string }
    model: { type: string }
    request_schema: { type: string, enum: [open_responses_v1] }
    output_text: { type: string }
```

## Files to Create/Modify

- `api/app/services/agent_service.py` - insert normalization path before provider execution.
- `api/app/services/provider_usage_service.py` - persist normalized request schema + route evidence.
- `api/app/models/schemas.py` - add normalized response call model.
- `api/tests/test_agent.py` - add provider-agnostic routing assertions.

## Acceptance Tests

- `cd api && pytest -v tests/test_agent.py -k \"route or provider\"`
- `cd api && pytest -v tests/test_inventory_api.py -k endpoint_traceability`
- Manual validation: create two tasks with different providers and confirm normalized schema markers in runtime evidence output.

## Verification

```bash
python3 scripts/validate_spec_quality.py --file specs/109-open-responses-interoperability-layer.md
```

## Out of Scope

- Full migration of every legacy provider integration in one pass.
- Changes to UI rendering for task output display.

## Risks and Assumptions

- Risk: provider-specific capabilities may not map 1:1; mitigation is additive provider extension fields.
- Assumption: current agent execution contracts can be wrapped without breaking existing endpoint behavior.

## Known Gaps and Follow-up Tasks

- Follow-up task: `task_open_responses_tool_schema_parity_001` to normalize tool-call schema parity across providers.

## Decision Gates (if any)

- Decide whether normalization is required for all task types (`spec`, `test`, `impl`, `review`, `heal`) or phased by task type.
