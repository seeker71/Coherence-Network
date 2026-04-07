---
idea_id: agent-pipeline
status: done
source:
  - file: api/app/services/agent_execution_metrics.py
    symbols: [resolve_cost_controls(), attribution_values_from_output()]
  - file: api/app/services/agent_execution_hooks.py
    symbols: [register_lifecycle_hook(), dispatch_lifecycle_event()]
  - file: api/app/routers/agent_status_routes.py
    symbols: [pipeline status endpoints]
requirements:
  - "Execution time: Per-task duration in agent_runner logs and task log footer (done: `duration_seconds` in task log)"
  - "Task success rate: Aggregate completed vs failed by task_type, model, executor; store in metrics (JSON/SQLite)"
  - "Usage per task: Token/cost proxy or API call count per task (when providers expose it)"
  - "Pipeline metrics endpoint: `GET /api/agent/metrics` returning execution time P50/P95, success rate, usage summary"
  - "Prompt variants: Support `context.prompt_variant` or prompt ID in task; log which variant was used"
  - "Skill variants: Test different .cursor/skills or agent configs; tag tasks with skill_version"
  - "Model variants: Compare `cursor/auto` vs `cursor/composer-1` vs `claude`; attribute outcome to model"
  - "A/B result aggregation: Success rate and avg duration by variant; simple statistical comparison"
  - "Overall goal tracking: Define goals (e.g. “10 specs done”, “web app live”); track progress from backlog completion"
  - "Goal→backlog linkage: Map backlog items to goals; compute progress %"
  # ... 13 more in Requirements section below
done_when:
  - "Execution time — Per-task duration in agent_runner logs and task log footer (done: `duration_seconds` in task log)"
  - "Task success rate — Aggregate completed vs failed by task_type, model, executor; store in metrics (JSON/SQLite)"
  - "Usage per task — Token/cost proxy or API call count per task (when providers expose it)"
  - "Pipeline metrics endpoint — `GET /api/agent/metrics` returning execution time P50/P95, success rate, usage summary"
  - "Prompt variants — Support `context.prompt_variant` or prompt ID in task; log which variant was used"
test: "python3 -m pytest api/tests/test_monitor_pipeline_stale_running.py -x -v"
constraints:
  - "changes scoped to listed files only"
  - "no schema migrations without explicit approval"
---

> **Parent idea**: [agent-pipeline](../ideas/agent-pipeline.md)
> **Source**: [`api/app/services/agent_execution_metrics.py`](../api/app/services/agent_execution_metrics.py) | [`api/app/services/agent_execution_hooks.py`](../api/app/services/agent_execution_hooks.py) | [`api/app/routers/agent_status_routes.py`](../api/app/routers/agent_status_routes.py)

# Spec: Pipeline Observability and Auto-Review

## Purpose

Enable measurement, optimization, and self-improvement of the agent pipeline. Capture execution metrics, success rates, usage per task; support A/B testing of prompts, skills, and models; and add automated review of queue, priorities, pipeline health, specs, implementation, and testing. Supports goal tracking and auto-scheduling of improvements.

## Requirements

### Phase 1: Core Metrics (implement first)
- [ ] **Execution time** — Per-task duration in agent_runner logs and task log footer (done: `duration_seconds` in task log)
- [ ] **Task success rate** — Aggregate completed vs failed by task_type, model, executor; store in metrics (JSON/SQLite)
- [ ] **Usage per task** — Token/cost proxy or API call count per task (when providers expose it)
- [ ] **Pipeline metrics endpoint** — `GET /api/agent/metrics` returning execution time P50/P95, success rate, usage summary

### Phase 2: A/B Testing
- [ ] **Prompt variants** — Support `context.prompt_variant` or prompt ID in task; log which variant was used
- [ ] **Skill variants** — Test different .cursor/skills or agent configs; tag tasks with skill_version
- [ ] **Model variants** — Compare `cursor/auto` vs `cursor/composer-1` vs `claude`; attribute outcome to model
- [ ] **A/B result aggregation** — Success rate and avg duration by variant; simple statistical comparison

### Phase 3: Goal Tracking
- [ ] **Overall goal tracking** — Define goals (e.g. “10 specs done”, “web app live”); track progress from backlog completion
- [ ] **Goal→backlog linkage** — Map backlog items to goals; compute progress %
- [ ] **Dashboard/API** — Expose goal status via API or check_pipeline enhancement

### Phase 4: Auto-Review (queue, priorities, pipeline, usage)
- [ ] **Auto-review queue** — Periodic job to inspect pending tasks; flag stale, duplicate, or low-priority
- [ ] **Auto-review priorities** — Suggest reordering based on dependencies, impact, or goal alignment
- [ ] **Auto-review pipeline** — Detect stuck phases, timeout patterns, repeated failures; suggest actions
- [ ] **Auto-review usage** — Detect usage spikes, cost anomalies; alert or throttle

### Phase 5: Auto-Review (spec, implementation, review, testing)
- [ ] **Auto-review spec** — After spec task completes, run lightweight checks: template compliance, testable requirements
- [ ] **Auto-review implementation** — After impl: run tests, check spec file list, flag drift
- [ ] **Auto-review review** — After review: ensure pass/fail consistency, decision audit
- [ ] **Auto-review testing** — Test coverage, flakiness, holdout exclusions

### Phase 6: Auto-Scheduling of Improvements
- [ ] **Auto-schedule goal improvements** — When goal stalled, create tasks to unblock (e.g. “Investigate failed impl”)
- [ ] **Auto-schedule pipeline improvements** — When pipeline stuck, create heal or diagnostic tasks
- [ ] **Auto-schedule task description improvements** — Suggest clearer directions based on failure analysis
- [ ] **Auto-schedule backlog improvements** — Split large items, add acceptance criteria, reorder


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: 005, 112, 115

## Task Card

```yaml
goal: Enable measurement, optimization, and self-improvement of the agent pipeline.
files_allowed:
  - api/app/services/metrics_service.py
  - api/app/routers/agent.py
  - api/scripts/agent_runner.py
  - api/app/models/metrics.py
  - specs/pipeline-observability-and-auto-review.md
done_when:
  - Execution time — Per-task duration in agent_runner logs and task log footer (done: `duration_seconds` in task log)
  - Task success rate — Aggregate completed vs failed by task_type, model, executor; store in metrics (JSON/SQLite)
  - Usage per task — Token/cost proxy or API call count per task (when providers expose it)
  - Pipeline metrics endpoint — `GET /api/agent/metrics` returning execution time P50/P95, success rate, usage summary
  - Prompt variants — Support `context.prompt_variant` or prompt ID in task; log which variant was used
commands:
  - python3 -m pytest api/tests/test_monitor_pipeline_stale_running.py -x -v
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

## API Contract (Phase 1)

### `GET /api/agent/metrics`

**Response 200**
```json
{
  "execution_time": { "p50_seconds": 45, "p95_seconds": 120 },
  "success_rate": { "completed": 80, "failed": 5, "total": 85 },
  "by_task_type": { "spec": { "success_rate": 0.9 }, "impl": { "success_rate": 0.85 } },
  "by_model": { "cursor/auto": { "count": 60, "avg_duration": 52 } }
}
```


### Input Validation

- All string fields: min_length=1, max_length=1000
- Numeric fields: appropriate min/max bounds
- Required fields validated; missing returns 422
- Unknown fields rejected (Pydantic extra="forbid" where applicable)

## Data Model

```yaml
TaskMetric:
  task_id: string
  task_type: string
  model: string
  executor: string
  duration_seconds: float
  status: completed | failed
  created_at: datetime
  prompt_variant?: string   # Phase 2
  skill_version?: string   # Phase 2
```

## Files to Create/Modify

- `api/app/services/metrics_service.py` — Persist and aggregate metrics
- `api/app/routers/agent.py` — Wire metrics on task completion (or agent_runner POSTs metrics)
- `api/scripts/agent_runner.py` — POST duration, status to metrics endpoint (or write to metrics store)
- `api/app/models/metrics.py` — Pydantic models for metrics API
- `specs/pipeline-observability-and-auto-review.md` — This spec

## Acceptance Tests

- Create task, run agent_runner, verify metrics include duration and status
- GET /api/agent/metrics returns success_rate and execution_time when tasks exist
- A/B variant tagging (Phase 2) stores and aggregates by variant

## Out of Scope (for this spec)

- Full ML-based prompt optimization
- Real-time streaming dashboards
- Multi-tenant usage quotas

## Decision Gates

- **Metrics storage** — SQLite vs JSON file vs PostgreSQL (align with existing DB choice)
- **A/B assignment** — Random vs deterministic (e.g. hash of task_id)
- **Auto-scheduling** — Human-in-loop vs fully autonomous task creation

## Downstream Implementations

- **Spec 112** ([112-prompt-ab-roi-measurement.md](112-prompt-ab-roi-measurement.md)) — Implements Phase 2 prompt variant A/B testing with Thompson Sampling selection, ROI measurement per variant, and exploration/exploitation policy. Closes the `context.prompt_variant` gap identified in Phase 2.
- **Spec 115** ([115-grounded-cost-value-measurement.md](115-grounded-cost-value-measurement.md)) — Provides grounded cost (provider billing, runtime estimates) and value (observable outcomes) to replace placeholder `value_score`/`resource_cost` in the ROI service. Feeds real numbers into the A/B measurement layer.

## See Also

- [026-phase-1-task-metrics.md](026-phase-1-task-metrics.md) — Expanded Phase 1 spec: persist task metrics; GET /api/agent/metrics
- [docs/AGENT-DEBUGGING.md](../docs/AGENT-DEBUGGING.md) — Pipeline troubleshooting
- [docs/SPEC-COVERAGE.md](../docs/SPEC-COVERAGE.md) — Spec→impl mapping
- [005-project-manager-pipeline.md](005-project-manager-pipeline.md) — Pipeline phases

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
python3 -m pytest api/tests/test_monitor_pipeline_stale_running.py -x -v
```

## Known Gaps and Follow-up Tasks

- No known gaps at time of writing.
- Follow-up: review after initial implementation for completeness.
