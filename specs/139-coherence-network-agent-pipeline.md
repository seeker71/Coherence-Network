# Spec 139: Coherence Network Agent Pipeline

## Purpose

The project currently requires manual orchestration to move ideas through the development pipeline — an operator must identify which ideas are highest-ROI, create tasks, monitor execution, and advance idea stages. This spec defines a persistent background loop ("agent pipeline") that continuously selects the highest-ROI pending ideas from the portfolio, generates and executes tasks via `local_runner.py`, and auto-advances ideas through lifecycle stages (none → specced → implementing → testing → reviewing → complete). This eliminates operator toil, maximizes throughput on high-value work, and keeps the portfolio moving 24/7.

## Requirements

- [ ] R1: A new `api/scripts/agent_pipeline.py` script implements a persistent background loop that polls the idea portfolio at a configurable interval (default 60s, env: `PIPELINE_POLL_INTERVAL`).
- [ ] R2: Each poll cycle builds a pending-task candidate set from idea stages and ranks candidates by ROI score (coherence_score × urgency_weight, descending), selecting highest-ROI work first (default N=1, env: `PIPELINE_CONCURRENCY`).
- [ ] R3: For each selected idea, the pipeline determines the next required task type based on the idea's current stage: `none` → spec task, `specced` → impl task, `implementing` → test task, `testing` → review task.
- [ ] R4: The pipeline creates an `AgentTask` via the agent API (`POST /api/agent/tasks`) with the idea's context, then delegates execution to `local_runner.py` (subprocess or direct import) without duplicating provider execution logic.
- [ ] R5: On successful task completion, the pipeline calls the idea auto-advance endpoint (`POST /api/ideas/{idea_id}/advance`) to move the idea to the next stage per spec 138.
- [ ] R6: On task failure, the pipeline logs the failure, records the error classification (timeout, auth, rate_limit, etc.), and applies a configurable retry policy: up to 3 retries with exponential backoff (2s, 8s, 32s). After max retries, the idea is marked with `needs_attention: true` and skipped until manual intervention.
- [ ] R6a: Slot allocation for each selected task uses the existing `SlotSelector` integration path so pipeline execution shares the same capacity and claim semantics as other local runs.
- [ ] R7: The pipeline exposes a `GET /api/pipeline/status` endpoint returning: `{ running: bool, uptime_seconds: int, current_idea_id: str|null, cycle_count: int, ideas_advanced: int, tasks_completed: int, tasks_failed: int, last_cycle_at: str }`.
- [ ] R8: The pipeline supports graceful shutdown via SIGINT/SIGTERM — it finishes the current task before exiting and persists state to `api/logs/agent_pipeline_state.json`.
- [ ] R9: The pipeline skips ideas that already have a RUNNING or PENDING task (prevents duplicate work).
- [ ] R10: The pipeline logs each cycle to `api/logs/agent_pipeline.log` with structured JSON entries: `{ timestamp, cycle, idea_id, task_type, provider, status, duration_ms }`.
- [ ] R10a: The pipeline records per-task outcomes (status, error_classification, retry_count, duration_ms, selected_slot, executed_command) in a persisted outcome journal (`api/logs/agent_pipeline_outcomes.jsonl`) to support audit and ROI tuning.
- [ ] R11: CLI interface supports `--once` (single cycle), `--dry-run` (log what would run without executing), and `--interval N` flags.
- [ ] R12: Ideas at stage `reviewing` that pass review are advanced to `complete` and their `manifestation_status` is set to `validated` per spec 138 R9.

## Research Inputs (Required)

- `2026-03-15` - [Spec 138: Idea Lifecycle Management](specs/138-idea-lifecycle-management.md) - defines idea stages and auto-advance endpoints this pipeline drives
- `2026-03-06` - [Spec 005: Project Manager Pipeline](specs/005-project-manager-pipeline.md) - existing orchestrator pattern (spec→impl→test→review loop) that this spec generalizes to idea-driven scheduling
- `2026-03-06` - [Spec 002: Agent Orchestration API](specs/002-agent-orchestration-api.md) - task API contract used for task creation and status tracking
- `2026-03-15` - [local_runner.py](api/scripts/local_runner.py) - existing provider-based task executor with error classification; pipeline must call this path rather than reimplement execution logic
- `2026-03-20` - [SlotSelector service](api/app/services/slot_selector.py) - existing slot/capacity selector used by local execution flows; pipeline must integrate this mechanism for consistent task claims

## Task Card (Required)

```yaml
goal: Implement a persistent background agent pipeline that selects highest-ROI ideas, executes tasks via local_runner.py, and auto-advances ideas through lifecycle stages.
files_allowed:
  - api/scripts/agent_pipeline.py
  - api/app/routers/pipeline.py
  - api/app/services/pipeline_service.py
  - api/tests/test_agent_pipeline.py
  - api/tests/test_pipeline_router.py
done_when:
  - agent_pipeline.py runs as persistent loop polling and ranking pending-task candidates by ROI
  - Tasks are created and delegated to local_runner.py per idea stage without provider-logic duplication
  - SlotSelector is used for slot/capacity assignment before execution
  - Ideas auto-advance on task completion via spec 138 endpoints
  - Retry policy handles failures with exponential backoff
  - Outcome journal persists status/error/retry/slot metadata for each executed task
  - GET /api/pipeline/status returns live pipeline metrics
  - --once, --dry-run, and --interval flags work correctly
  - All tests pass
commands:
  - cd api && python -m pytest tests/test_agent_pipeline.py tests/test_pipeline_router.py -q
  - cd api && python scripts/agent_pipeline.py --dry-run
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
  - must not duplicate provider selection/execution logic already in local_runner.py
  - must reuse existing SlotSelector integration path for task slot assignment
```

## API Contract (if applicable)

### `GET /api/pipeline/status`

**Request**
- No parameters.

**Response 200**
```json
{
  "running": true,
  "uptime_seconds": 3621,
  "current_idea_id": "idea_abc123",
  "current_task_type": "impl",
  "current_slot": "slot_local_1",
  "cycle_count": 42,
  "ideas_advanced": 12,
  "tasks_completed": 38,
  "tasks_failed": 4,
  "last_cycle_at": "2026-03-21T14:30:00Z",
  "last_outcome_id": "outcome_20260321_143000_idea_abc123"
}
```

**Response 503** (pipeline not running)
```json
{
  "running": false,
  "uptime_seconds": 0,
  "current_idea_id": null,
  "current_task_type": null,
  "current_slot": null,
  "cycle_count": 0,
  "ideas_advanced": 0,
  "tasks_completed": 0,
  "tasks_failed": 0,
  "last_cycle_at": null,
  "last_outcome_id": null
}
```

## Data Model (if applicable)

```yaml
PipelineState:
  properties:
    running: { type: boolean }
    uptime_seconds: { type: integer }
    current_idea_id: { type: string, nullable: true }
    current_task_type: { type: string, enum: [spec, impl, test, review], nullable: true }
    current_slot: { type: string, nullable: true }
    cycle_count: { type: integer }
    ideas_advanced: { type: integer }
    tasks_completed: { type: integer }
    tasks_failed: { type: integer }
    last_cycle_at: { type: string, format: date-time, nullable: true }
    last_outcome_id: { type: string, nullable: true }

PipelineCycleLog:
  properties:
    timestamp: { type: string, format: date-time }
    cycle: { type: integer }
    idea_id: { type: string }
    task_type: { type: string, enum: [spec, impl, test, review] }
    provider: { type: string }
    status: { type: string, enum: [completed, failed, skipped] }
    duration_ms: { type: integer }

PipelineOutcome:
  properties:
    id: { type: string }
    timestamp: { type: string, format: date-time }
    idea_id: { type: string }
    task_id: { type: string }
    task_type: { type: string, enum: [spec, impl, test, review] }
    status: { type: string, enum: [completed, failed] }
    error_classification: { type: string, nullable: true }
    retry_count: { type: integer }
    selected_slot: { type: string, nullable: true }
    executed_command: { type: string }
    duration_ms: { type: integer }
```

## Files to Create/Modify

- `api/scripts/agent_pipeline.py` — persistent background loop: pending-task ROI ranking, SlotSelector-based slot assignment, local_runner delegation, auto-advance, state persistence
- `api/app/routers/pipeline.py` — `GET /api/pipeline/status` route handler
- `api/app/services/pipeline_service.py` — shared pipeline state, metrics tracking, ROI scoring logic, outcome journal recording
- `api/tests/test_agent_pipeline.py` — unit tests for pipeline loop, ROI ranking, SlotSelector usage, retry logic, outcome recording, state persistence
- `api/tests/test_pipeline_router.py` — integration tests for pipeline status endpoint

## Acceptance Tests

- `api/tests/test_agent_pipeline.py::test_roi_ranking_selects_highest_score`
- `api/tests/test_agent_pipeline.py::test_stage_to_task_type_mapping`
- `api/tests/test_agent_pipeline.py::test_pending_task_ranking_selects_highest_roi`
- `api/tests/test_agent_pipeline.py::test_slot_selector_used_for_selected_task`
- `api/tests/test_agent_pipeline.py::test_skip_idea_with_running_task`
- `api/tests/test_agent_pipeline.py::test_retry_on_failure_with_backoff`
- `api/tests/test_agent_pipeline.py::test_max_retries_marks_needs_attention`
- `api/tests/test_agent_pipeline.py::test_outcome_journal_records_success_and_failure`
- `api/tests/test_agent_pipeline.py::test_dry_run_no_side_effects`
- `api/tests/test_agent_pipeline.py::test_once_mode_single_cycle`
- `api/tests/test_agent_pipeline.py::test_state_persistence_on_shutdown`
- `api/tests/test_pipeline_router.py::test_pipeline_status_200`
- `api/tests/test_pipeline_router.py::test_pipeline_status_503_not_running`

## Concurrency Behavior

- **Read operations**: ROI ranking reads idea portfolio — safe for concurrent access, no locking.
- **Write operations**: Task creation uses API — agent service handles claim conflicts via `TaskClaimConflictError`. Pipeline state and outcome journal writes use atomic append/write semantics.
- **Multi-worker**: `PIPELINE_CONCURRENCY > 1` processes ideas in parallel via ThreadPoolExecutor. Each idea is independently locked by its in-flight task — no cross-idea contention.
- **Duplicate prevention**: R9 ensures an idea with an existing RUNNING/PENDING task is skipped, preventing concurrent work on the same idea.
- **Capacity coherence**: Slot selection is delegated to `SlotSelector` so this pipeline shares global local-runner slot constraints with other execution loops.

## Verification

```bash
cd api && python -m pytest tests/test_agent_pipeline.py tests/test_pipeline_router.py -q
cd api && python scripts/agent_pipeline.py --dry-run
cd api && python scripts/agent_pipeline.py --once
```

## Out of Scope

- Web UI for pipeline control (start/stop/configure) — follow-up spec.
- Telegram notifications for pipeline events — already covered by spec 003.
- Custom ROI scoring formulas beyond coherence_score × urgency_weight — follow-up if needed.
- Multi-node distributed pipeline coordination — single-node only for MVP.
- Auto-creation of new ideas — pipeline only advances existing ideas.
- Changes to `SlotSelector` behavior itself — this spec only consumes the existing selector.

## Risks and Assumptions

- **Risk**: `local_runner.py` provider availability varies — if no providers are detected, the pipeline stalls. **Mitigation**: Pipeline logs a warning and retries next cycle; status endpoint surfaces provider availability.
- **Risk**: Slot starvation if all slots are occupied can delay high-ROI work. **Mitigation**: Surface selected/blocked slot state in status/outcomes and allow next-cycle reselection.
- **Risk**: Rapid retry loops on persistent failures could waste API credits. **Mitigation**: Exponential backoff (2s→8s→32s) with max 3 retries, then skip-until-manual-intervention.
- **Assumption**: Spec 138 idea lifecycle endpoints are implemented and available. If not, auto-advance calls will fail gracefully (logged, not fatal).
- **Assumption**: The agent task API (`POST /api/agent/tasks`) is running and reachable on localhost. Pipeline requires the FastAPI server to be up.
- **Assumption**: `SlotSelector` exposes stable selection semantics for local runner consumers.

## Known Gaps and Follow-up Tasks

- Follow-up: Add pipeline control endpoints (`POST /api/pipeline/start`, `POST /api/pipeline/stop`) for remote management.
- Follow-up: Add Telegram alerts when pipeline marks an idea as `needs_attention` after max retries.
- Follow-up: Dashboard UI showing pipeline throughput, idea stage distribution, and provider performance over time.
- Follow-up: Add ROI feedback loop that updates urgency/priority weights from observed outcome quality and cycle-time.

## Failure/Retry Reflection

- **Failure mode**: Provider timeout during task execution.
  - **Blind spot**: Default timeout may be too short for large spec/impl tasks.
  - **Next action**: Inherit `AGENT_TASK_TIMEOUT` from agent_runner.py (default 3600s); log timeout duration for tuning.

- **Failure mode**: Slot unavailable for highest-ROI candidate.
  - **Blind spot**: Pipeline may repeatedly pick blocked work without executing lower-ranked runnable work.
  - **Next action**: Treat slot-unavailable as a classified skip outcome and continue with next ranked candidate in-cycle.

- **Failure mode**: Idea auto-advance endpoint returns 409 (already at target stage).
  - **Blind spot**: Race condition if another process advanced the idea.
  - **Next action**: Treat 409 as success (idempotent) — log and continue to next idea.

- **Failure mode**: Pipeline state file corrupted on crash.
  - **Blind spot**: Non-atomic write during SIGKILL.
  - **Next action**: Use atomic write pattern (write tmp file, fsync, rename). On corrupt read, reset to defaults and log warning.

## Decision Gates (if any)

- **ROI formula**: Current design uses `coherence_score × urgency_weight`. If stakeholders want a different formula (e.g., incorporating recency, dependency depth), this needs approval before implementation.
- **Concurrency default**: Default `PIPELINE_CONCURRENCY=1` is conservative. Increasing requires validation that provider rate limits and API throughput can handle parallel task execution.
