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

## Non-Goals
- Precise dollar accounting for all external resources.
- Full per-subcommand tracing inside an LLM tool.

## Implementation (Allowed Files)
- `specs/074-tool-failure-awareness.md`
- `api/scripts/agent_runner.py`
- `api/scripts/monitor_pipeline.py`
- `api/tests/test_agent_runner_tool_failure_telemetry.py`
- `docs/system_audit/commit_evidence_2026-02-15_tool-failure-awareness.json`

## Validation
- `cd api && /opt/homebrew/bin/python3.11 -m pytest -q tests/test_agent_runner_tool_failure_telemetry.py`
- `python3 scripts/validate_commit_evidence.py --file docs/system_audit/commit_evidence_2026-02-15_tool-failure-awareness.json`
