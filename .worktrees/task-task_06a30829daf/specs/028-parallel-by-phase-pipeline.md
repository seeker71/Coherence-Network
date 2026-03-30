# Spec: Parallel-by-Phase Pipeline

## Purpose

Run at least one task in each phase (spec, impl, test, review) simultaneously, with multiple specs buffered, and a constantly-running monitor that ensures coverage and issues fix actions.

## Requirements

- [ ] **Parallel workers**: agent_runner runs with `--workers 5` (4 phases + buffer)
- [ ] **Phase coverage**: At least one task in spec, impl, test, review running when backlog allows
- [ ] **Spec buffer**: 2+ specs ready so design/test/impl/review are fed
- [ ] **Monitor constant**: Monitor runs every 60s (or 30s), detects low phase coverage, creates heal/action tasks
- [ ] **Pipeline status**: Extend with `running_by_phase` for visibility


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: none

## Task Card

```yaml
goal: Run at least one task in each phase (spec, impl, test, review) simultaneously, with multiple specs buffered, and a constantly-running monitor that ensures coverage and issues fix actions.
files_allowed:
  - api/scripts/run_overnight_pipeline.sh
  - api/scripts/project_manager.py
  - api/scripts/monitor_pipeline.py
  - api/app/services/agent_service.py
  - specs/028-parallel-by-phase-pipeline.md
done_when:
  - Parallel workers: agent_runner runs with `--workers 5` (4 phases + buffer)
  - Phase coverage: At least one task in spec, impl, test, review running when backlog allows
  - Spec buffer: 2+ specs ready so design/test/impl/review are fed
  - Monitor constant: Monitor runs every 60s (or 30s), detects low phase coverage, creates heal/action tasks
  - Pipeline status: Extend with `running_by_phase` for visibility
commands:
  - python3 -m pytest api/tests/test_parallel_state_writes.py -x -v
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

## Architecture

### Slot Model
- Maintain 4 slots: spec, impl, test, review
- Each slot can hold one (item_idx, phase) with an active task
- Fill slots from backlog: spec from next item; impl from item whose spec is done; etc.
- When slot frees (task completes), fill from next ready item

### State (parallel mode)
```json
{
  "slots": {
    "spec": { "item_idx": 2, "task_id": "task_xxx" },
    "impl": { "item_idx": 1, "task_id": "task_yyy" },
    "test": { "item_idx": 0, "task_id": "task_zzz" },
    "review": null
  },
  "item_phase": { "0": "review", "1": "impl", "2": "spec" }
}
```

### Monitor Rules (add)
- `low_phase_coverage`: Running tasks < 2 when pending exist; or no task in a phase for 5+ min when backlog has work for that phase
- Monitor creates heal task: "Ensure PM creates tasks for all phases; check parallel mode and backlog"

## Files to Create/Modify

- `api/scripts/run_overnight_pipeline.sh` — add `--workers 5` to agent_runner
- `api/scripts/project_manager.py` — add `--parallel` mode with slot-based task creation
- `api/scripts/monitor_pipeline.py` — add low_phase_coverage rule; reduce interval to 60s
- `api/app/services/agent_service.py` — optional: add `running_by_phase` to pipeline-status
- `specs/028-parallel-by-phase-pipeline.md` — this spec

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

See `api/tests/test_parallel_by_phase_pipeline.py` for test cases covering this spec's requirements.


## Verification

```bash
python3 -m pytest api/tests/test_parallel_state_writes.py -x -v
```
