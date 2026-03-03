# Spec: Agent Execution Lifecycle Hooks

## Purpose

Adopt a hook-first execution pattern for Coherence agent tasks so task lifecycle transitions are emitted through a consistent internal interface. This brings the same orchestration clarity seen in oh-my-opencode (centralized lifecycle events + safe listeners) while keeping Coherence execution deterministic and observable.

## Requirements

- [ ] Add an execution lifecycle hook surface that can dispatch named lifecycle events for a task.
- [ ] Ensure hook listener failures never break task execution or change task terminal status.
- [ ] Emit lifecycle telemetry events during task execution (`claimed`, `execution_started`, `finalized`, plus block/validation failures).
- [ ] Add configurable lifecycle subscribers (`runtime` and `jsonl`) that can be enabled/disabled via environment setting.
- [ ] Add a compact lifecycle summary query endpoint for recent lifecycle events.
- [ ] Support lifecycle summary source selection (`auto`, `runtime`, `jsonl`) so operators can force a backend when both subscribers are enabled.
- [ ] Add JSONL retention control to cap lifecycle audit growth.
- [ ] Include actionable lifecycle guidance in summary output (for example: no subscribers enabled, paid guard blocks, high failure ratio).

## API Contract (if applicable)

N/A - no public API route changes in this spec.

## Data Model (if applicable)

```yaml
AgentExecutionLifecycleEvent:
  properties:
    tracking_kind: { type: string, enum: [agent_task_lifecycle] }
    lifecycle_event: { type: string }
    task_id: { type: string }
    task_status: { type: string }
    worker_id: { type: string }
    model: { type: string }
```

## Files to Create/Modify

- `api/app/services/agent_execution_hooks.py` - lifecycle hook registry and default telemetry emitter.
- `api/app/services/agent_execution_task_flow.py` - emit lifecycle events during execution flow.
- `api/app/routers/agent.py` - lifecycle summary route.
- `api/tests/test_agent_execute_endpoint.py` - lifecycle emission and hook-failure resilience tests.

## Acceptance Tests

- `cd api && pytest -q tests/test_agent_execute_endpoint.py -k "lifecycle"`
- `cd api && pytest -q tests/test_agent_execute_endpoint.py -k "hook_error"`
- `cd api && pytest -q tests/test_agent_execute_endpoint.py -k "lifecycle_summary"`
- `cd api && pytest -q tests/test_agent_execute_endpoint.py -k "lifecycle_jsonl"`
- `cd api && pytest -q tests/test_agent_execute_endpoint.py -k "lifecycle_source_override or lifecycle_jsonl_retention"`
- `cd api && pytest -q tests/test_agent_execute_endpoint.py -k "lifecycle_guidance"`

## Verification

```bash
python3 scripts/validate_spec_quality.py --file specs/111-agent-execution-lifecycle-hooks.md
cd api && pytest -q tests/test_agent_execute_endpoint.py -k "lifecycle or hook_error or lifecycle_summary"
cd api && pytest -q tests/test_agent_execute_endpoint.py -k "lifecycle_jsonl"
cd api && pytest -q tests/test_agent_execute_endpoint.py -k "lifecycle_source_override or lifecycle_jsonl_retention"
cd api && pytest -q tests/test_agent_execute_endpoint.py -k "lifecycle_guidance"
```

## Out of Scope

- Dynamic hook loading from external plugins.
- Replacing existing task execution summary/tool-call telemetry.
- Workflow engine abstraction changes.
- UI/dashboard rendering changes in the web app.

## Risks and Assumptions

- Risk: duplicative telemetry noise if lifecycle events are too verbose; mitigate by using a distinct `tracking_kind` and compact metadata.
- Assumption: runtime event store capacity is sufficient for additional lifecycle events in current execution volume.

## Known Gaps and Follow-up Tasks

- Follow-up task: `task_lifecycle_hooks_external_registration_001` for configuration-driven third-party hook registration.

## Decision Gates (if any)

- Decide whether lifecycle hook emission should be environment-gated in production (always-on vs toggle).
