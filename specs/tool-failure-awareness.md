---
idea_id: pipeline-optimization
status: partial
source:
  - file: api/app/services/failure_taxonomy_service.py
    symbols: [failure pattern recognition]
  - file: api/app/services/agent_execution_retry.py
    symbols: [failure analysis]
done_when:
  - "For every agent task command execution, record a runtime event:"
  - "When a command fails (non-zero exit OR timeout OR suspicious zero-output success), write a friction event via API:"
  - "Monitor should raise a `expensive_failed_task` issue when recent failed tasks exceed a cost threshold:"
test: "python3 -m pytest api/tests/test_agent_runner_tool_failure_telemetry.py -x -v"
constraints:
  - "changes scoped to listed files only"
  - "no schema migrations without explicit approval"
---

> **Parent idea**: [pipeline-optimization](../ideas/pipeline-optimization.md)
> **Source**: [`api/app/services/failure_taxonomy_service.py`](../api/app/services/failure_taxonomy_service.py) | [`api/app/services/agent_execution_retry.py`](../api/app/services/agent_execution_retry.py)

# Spec 074: Tool Failure Awareness (Cost Without Gain)

## Goal
Detect and surface expensive tool failures (time/cost spent without value) automatically.

## Motivation
Tool failures are pure friction: they burn time (cost) and often block progress. We need:
- machine-readable telemetry for each task command execution
- automatic friction events when a command fails after consuming time
- monitor issues that elevate expensive failures to operators

## Requirements
### Runtime Telemetry (Machine)
1. For every agent task command execution, record a runtime event:
   - `source=worker`
   - `endpoint=tool:<tool_name>` (derived from the command token)
   - `runtime_ms` = wall time
   - `status_code` = 200 on success, 500 on non-zero exit, 504 on timeout
   - `idea_id` = `coherence-network-agent-pipeline`
   - `metadata` includes: `task_id`, `task_type`, `model`, `returncode`, `output_len`

### Friction Event (Machine + Human)
2. When a command fails (non-zero exit OR timeout OR suspicious zero-output success), write a friction event via API:
   - `stage=agent_runner`
   - `block_type=tool_failure`
   - `energy_loss_estimate` derived from wall time (`PIPELINE_TIME_COST_PER_SECOND`, default reasonable)
   - `status=resolved` with `resolved_at` set (event is historical, not an open block)
   - notes include a scrubbed command summary + return code

### Monitor Awareness
3. Monitor should raise a `expensive_failed_task` issue when recent failed tasks exceed a cost threshold:
   - based on local `api/logs/metrics.jsonl` (durations + status)
   - include top failing task ids and wasted seconds


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: none

## Task Card

```yaml
goal: Implement the functionality described in this spec
files_allowed:
  - # TBD — determine from implementation
done_when:
  - For every agent task command execution, record a runtime event:
  - When a command fails (non-zero exit OR timeout OR suspicious zero-output success), write a friction event via API:
  - Monitor should raise a `expensive_failed_task` issue when recent failed tasks exceed a cost threshold:
commands:
  - python3 -m pytest api/tests/test_agent_runner_tool_failure_telemetry.py -x -v
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

## Non-Goals
- Precise dollar accounting for all external resources.
- Full per-subcommand tracing inside an LLM tool.

## Implementation (Allowed Files)
- `specs/tool-failure-awareness.md`
- `api/scripts/agent_runner.py`
- `api/scripts/monitor_pipeline.py`
- `api/tests/test_agent_runner_tool_failure_telemetry.py`
- `docs/system_audit/commit_evidence_2026-02-15_tool-failure-awareness.json`

## Validation
- `cd api && /opt/homebrew/bin/python3.11 -m pytest -q tests/test_agent_runner_tool_failure_telemetry.py`
- `python3 scripts/validate_commit_evidence.py --file docs/system_audit/commit_evidence_2026-02-15_tool-failure-awareness.json`

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

## Acceptance Tests

See `api/tests/test_tool_failure_awareness.py` for test cases covering this spec's requirements.


## Verification

```bash
python3 -m pytest api/tests/test_agent_runner_tool_failure_telemetry.py -x -v
```

## Known Gaps and Follow-up Tasks

- No known gaps at time of writing.
- Follow-up: review after initial implementation for completeness.
