# Idea Progress: pipeline-data-flow-fixes

## Current task
- **Phase:** impl
- **Task ID:** task_6660162039c27ef0
- **Status:** Complete — all spec requirements implemented

## Completed phases
- **spec** (2026-03-30): Comprehensive spec written at `specs/pipeline-data-flow-fixes.md`. Documents 2 core gaps (now closed) and 5 remaining hardening items. Includes 5 verification scenarios and observability plan.
- **impl** (2026-03-30): Closed remaining data-flow gaps in `api/scripts/local_runner.py`:
  - R-7a: `complete_task()` now accepts `error_category` parameter (backward-compatible default)
  - R-4b supplement: timeout-with-code push failure path uses `error_category="push_failed"`
  - R-1-obs: fetch errors propagated from `_create_worktree` to task context via `_fetch_warnings` dict
  - Bonus: worktree creation failure uses `error_category="worktree_failed"` for triage

## Key decisions
- Core gaps (premature phase advance + hardcoded execution_error) already fixed in DG-012/DG-017 commits. Spec focuses on hardening and observability.
- Scope limited to 3 files: `api/scripts/local_runner.py`, `api/tests/test_pipeline_data_flow_fixes.py`, `docs/PIPELINE_DESIGN.md`
- New error category `timeout_with_code` added for timeout-with-salvaged-code path
- `complete_task()` to be unified with `_complete_task_with_status()` for consistent error categorization
- Added `error_category` as optional kwarg to `complete_task()` — backward-compatible, no signature break

## Blockers
- None
