# Spec: Parallel-by-Phase Pipeline

## Purpose

Run at least one task in each phase (spec, impl, test, review) simultaneously, with multiple specs buffered, and a constantly-running monitor that ensures coverage and issues fix actions.

## Requirements

- [ ] **Parallel workers**: agent_runner runs with `--workers 5` (4 phases + buffer)
- [ ] **Phase coverage**: At least one task in spec, impl, test, review running when backlog allows
- [ ] **Spec buffer**: 2+ specs ready so design/test/impl/review are fed
- [ ] **Monitor constant**: Monitor runs every 60s (or 30s), detects low phase coverage, creates heal/action tasks
- [ ] **Pipeline status**: Extend with `running_by_phase` for visibility

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
