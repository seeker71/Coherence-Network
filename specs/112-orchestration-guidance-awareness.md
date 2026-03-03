# Spec: Orchestration Guidance Awareness

## Purpose

Add a guidance-first orchestration summary that makes model/tool routing decisions easier to understand and apply without introducing new hard-blocking behavior.

## Requirements

- [ ] Add an API endpoint that returns orchestration guidance as advisory output.
- [ ] Include default executor policy (cheap, escalation, repo-question, open-question).
- [ ] Include per-task-type route recommendations for cheap and escalation paths.
- [ ] Include awareness metrics from runtime/lifecycle/friction signals.
- [ ] Include actionable guidance items that prioritize alignment/coherence over force.
- [ ] Keep enforcement explicitly non-blocking (`mode=guidance`, advisory semantics).

## API Contract (if applicable)

`GET /api/agent/orchestration/guidance`

Response must include:

- `generated_at`
- `mode` (`guidance`)
- `enforcement` (`advisory`)
- `defaults`
- `recommended_routes`
- `awareness`
- `guidance`

## Files to Create/Modify

- `api/app/services/agent_service.py` - build orchestration guidance summary payload.
- `api/app/routers/agent.py` - expose orchestration guidance endpoint.
- `api/tests/test_agent_visibility_api.py` - endpoint shape and awareness guidance tests.

## Acceptance Tests

- `cd api && pytest -q tests/test_agent_visibility_api.py -k "orchestration_guidance"`
- `cd api && ruff check app/services/agent_service.py app/routers/agent.py tests/test_agent_visibility_api.py`

## Verification

```bash
python3 scripts/validate_spec_quality.py --file specs/112-orchestration-guidance-awareness.md
cd api && pytest -q tests/test_agent_visibility_api.py -k "orchestration_guidance"
cd api && ruff check app/services/agent_service.py app/routers/agent.py tests/test_agent_visibility_api.py
```

## Out of Scope

- Any new task-execution hard gates or blocking enforcement.
- Model/provider billing policy changes.
- UI/dashboard rendering changes.

## Risks and Assumptions

- Risk: Guidance output can become noisy if too many hints are emitted; mitigate with short prioritized lists.
- Assumption: Existing runtime/lifecycle/friction telemetry is available often enough to produce useful guidance.

## Known Gaps and Follow-up Tasks

- Gap: Guidance currently uses internal telemetry only; it does not yet include UI-facing recommendation ordering by business impact.
- Follow-up task: add optional weighting that prioritizes guidance items by recent repeat-frequency and energy-loss impact.
