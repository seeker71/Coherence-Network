# Spec: Fully Automated Self-Updating Pipeline

## Purpose

Maximize automation and autonomy: a pipeline that runs unattended, updates framework artifacts when tests pass, detects issues via monitor, and auto-fixes or creates heal tasks. Aligns with [EXECUTION-PLAN](../docs/EXECUTION-PLAN.md) and [PIPELINE-EFFICIENCY-PLAN](../docs/PIPELINE-EFFICIENCY-PLAN.md).

## Requirements

### Phase 1: Auto-Update (priority 1 — unblocks framework coherence)
- [x] Script `api/scripts/update_spec_coverage.py` runs after pytest; updates SPEC-COVERAGE.md when all tests pass
- [ ] Script is idempotent; only adds/updates status marks (✓); never removes rows or specs
- [ ] CI job runs script after `pytest` (non-blocking; script failure does not fail CI)
- [ ] Script accepts `--dry-run` to preview changes without writing

### Phase 2: Metrics Persistence (priority 2 — unblocks monitor)
- [x] Agent runner persists task metrics on completion: task_id, task_type, model, duration_seconds, status
- [x] Metrics store: JSONL at `api/logs/metrics.jsonl`
- [x] `GET /api/agent/metrics` returns aggregates: success_rate, p50/p95 duration, by task_type, by model
- [ ] Metrics endpoint returns 200 with empty aggregates when no data

### Phase 3: Monitor Attention (priority 3 — enables auto-detect)
- [x] `GET /api/agent/pipeline-status` includes `attention` object: flags for stuck, repeated_failures, low_success_rate
- [ ] Stuck: no task progress 10+ min and pending tasks exist
- [ ] Repeated failures: 3+ consecutive failed tasks same phase (from PM state)
- [ ] Low success rate: 7d success rate < 80% when 10+ tasks
- [ ] `check_pipeline.py --attention` prints attention flags

### Phase 4: Auto-Fix Triggers (priority 4 — enables autonomy)
- [ ] When monitor flags repeated_failures: optionally create heal task or needs_decision (configurable; default: log only)
- [ ] When monitor flags stuck: log + suggest restart; optional: create diagnostic task
- [ ] Env var `PIPELINE_AUTO_FIX_ENABLED=0|1` gates auto-fix (default 0)

### Phase 5: Combined Backlog (priority 5 — meta + product in one run)
- [ ] Script or config merges meta-pipeline backlog (007) with product backlog (006) at ratio (e.g. 1 meta per 4 product)
- [ ] project_manager can consume combined backlog so one run processes both
- [ ] Priority order: product items first; interleave meta when product block or at interval

### Phase 6: Unattended Run (priority 6 — full automation)
- [ ] `run_overnight_pipeline.sh` or equivalent runs project_manager + agent_runner indefinitely
- [ ] On exit 0 of agent_runner task: runner continues; on API unreachable: retry then exit
- [ ] CI can trigger pipeline run (e.g. on merge to main) — optional; document only
- [ ] Log rotation for task logs; cleanup_temp supports `--keep-days`


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: none

## Task Card

```yaml
goal: Maximize automation and autonomy: a pipeline that runs unattended, updates framework artifacts when tests pass, detects issues via monitor, and auto-fixes or creates heal tasks.
files_allowed:
  - api/scripts/update_spec_coverage.py
  - api/scripts/agent_runner.py
  - api/app/services/metrics_service.py
  - api/app/routers/agent.py
  - api/app/models/metrics.py
  - .github/workflows/test.yml
  - specs/027-fully-automated-pipeline.md
done_when:
  - Script `api/scripts/update_spec_coverage.py` runs after pytest; updates SPEC-COVERAGE.md when all tests pass
  - Script is idempotent; only adds/updates status marks (✓); never removes rows or specs
  - CI job runs script after `pytest` (non-blocking; script failure does not fail CI)
  - Script accepts `--dry-run` to preview changes without writing
  - Agent runner persists task metrics on completion: task_id, task_type, model, duration_seconds, status
commands:
  - python3 -m pytest api/tests/test_project_manager.py -x -v
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

## API Contract

### `GET /api/agent/metrics`

**Response 200**
```json
{
  "success_rate": { "completed": 80, "failed": 5, "total": 85, "rate": 0.94 },
  "execution_time": { "p50_seconds": 45, "p95_seconds": 120 },
  "by_task_type": { "spec": { "count": 20, "success_rate": 0.95 }, "impl": { "count": 18, "success_rate": 0.89 } },
  "by_model": { "cursor/auto": { "count": 60, "avg_duration": 52 } }
}
```

### `GET /api/agent/pipeline-status` (extended)

Add to existing response:
```json
{
  "attention": {
    "stuck": false,
    "repeated_failures": false,
    "low_success_rate": false,
    "flags": []
  }
}
```


### Input Validation

- All string fields: min_length=1, max_length=1000
- Numeric fields: appropriate min/max bounds
- Required fields validated; missing returns 422
- Unknown fields rejected (Pydantic extra="forbid" where applicable)

## Files to Create/Modify

- `api/scripts/update_spec_coverage.py` — new; auto-update SPEC-COVERAGE
- `api/scripts/agent_runner.py` — persist metrics on task completion
- `api/app/services/metrics_service.py` — new; read/write metrics, aggregate
- `api/app/routers/agent.py` — add GET /metrics; extend pipeline-status with attention
- `api/app/models/metrics.py` — new; Pydantic for metrics response
- `.github/workflows/test.yml` — add step to run update_spec_coverage (optional, non-blocking)
- `specs/027-fully-automated-pipeline.md` — this spec

## Acceptance Tests

- `update_spec_coverage.py --dry-run` exits 0 and prints preview; does not modify files
- `update_spec_coverage.py` (no dry-run) updates SPEC-COVERAGE when tests pass; run after pytest
- GET /api/agent/metrics returns 200 with structure; empty when no metrics
- GET /api/agent/pipeline-status includes attention object
- When 3 failed tasks in a row, attention.repeated_failures is true (or heuristics detect)
- pipeline_status_returns_200: assert "attention" in response

## Out of Scope

- Full A/B testing infrastructure (spec 026 Phase 2)
- Cost/token tracking (spec 026; requires provider APIs)
- GitHub Discussions setup (COMMUNITY-RESEARCH-PRIORITIES)
- Autonomous backlog creation (human approves meta items)

## Decision Gates

- **Auto-fix:** Default disabled; enable via PIPELINE_AUTO_FIX_ENABLED=1 after review
- **Combined backlog:** Human maintains 006 and 007; merge script is deterministic
- **CI integration:** update_spec_coverage runs in CI but does not block; can be separate job

## Concurrency Behavior

- **Read operations**: Safe for concurrent access; no locking required.
- **Write operations**: Last-write-wins semantics; no optimistic locking for MVP.
- **Recommendation**: Clients should not assume atomic read-modify-write without explicit ETag support.

## Failure and Retry Behavior

- **Gate failure**: CI gate blocks merge; author must fix and re-push.
- **Flaky test**: Re-run up to 2 times before marking as genuine failure.
- **Rollback behavior**: Failed deployments automatically roll back to last known-good state.
- **Infrastructure failure**: CI runner unavailable triggers alert; jobs re-queue on recovery.
- **Timeout**: CI jobs exceeding 15 minutes are killed and marked failed; safe to re-trigger.

## Risks and Known Gaps

- **No auth gate**: Endpoints unprotected until C1 auth middleware applied.
- **No rate limiting**: Subject to abuse until M1 rate limiter active.
- **Single-node only**: No distributed locking; concurrent access may race.
- **Follow-up**: Add deployment smoke tests post-release.


## Verification

```bash
python3 -m pytest api/tests/test_project_manager.py -x -v
```

## Known Gaps and Follow-up Tasks

- No known gaps at time of writing.
- Follow-up: review after initial implementation for completeness.
