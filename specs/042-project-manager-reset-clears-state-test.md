# Spec: Project Manager --reset Clears State and Starts from Index 0 (Test)

## Purpose

Ensure the project manager's `--reset` CLI flag is covered by a test that verifies the script clears persisted state and the run proceeds from backlog index 0. This guards against regressions when changing reset behavior or state handling.

## Requirements

- [ ] A test exists that runs `project_manager.py` with `--reset` (and optionally `--dry-run`) such that any existing state is cleared and the run starts from index 0.
- [ ] The test asserts that after a run with `--reset`, state reflects "start from beginning": e.g. `backlog_index` is 0 and `phase` is the default (e.g. `"spec"`), either by reading the state file or by exercising `load_state()` after the reset path.
- [ ] The test uses a dedicated state path (e.g. `--state-file` to a temporary path) so it does not depend on or overwrite the default project manager state file.

## API Contract (if applicable)

N/A — script CLI behavior only. The script already accepts `--reset` (see `api/scripts/project_manager.py`); this spec adds test coverage.

## Data Model (if applicable)

State file format (unchanged): JSON with keys `backlog_index`, `phase`, `current_task_id`, `iteration`, `blocked` (see spec 005). After reset, state is either absent (file removed) or defaults: `backlog_index` 0, `phase` "spec", etc.

## Files to Create/Modify

- `api/tests/test_project_manager.py` — add a test that verifies `--reset` clears state and the run starts from index 0 (e.g. write state with `backlog_index` > 0 to a tmp state file, run script with `--reset --dry-run --state-file <tmp_path>`, then assert state at that path has `backlog_index` 0 or that the file was removed and a subsequent load yields index 0), **or**
- `api/tests/test_project_manager_pipeline.py` — add or expand a subprocess test that runs the script with `--reset` and `--state-file <path>` and asserts state is cleared and index is 0.

Prefer adding to `api/tests/test_project_manager.py` to mirror other CLI-flag tests (`test_load_backlog_alternate_file`, state-file flag test). The test must not rely on mocks for the reset behavior; use real file I/O and script invocation (subprocess or in-process with `STATE_FILE` set to a tmp path).

## Acceptance Tests

- [ ] New or expanded test: when the script is run with `--reset` and `--state-file <tmp_path>` (and e.g. `--dry-run`), after run either (1) the state file at that path no longer exists and a subsequent load_state from that path yields `backlog_index` 0, or (2) the state file at that path exists and contains `backlog_index` 0 and default phase. If the test pre-populates state with `backlog_index` > 0 before running with `--reset`, it must assert that post-run state is cleared to index 0.
- [ ] `pytest api/tests/test_project_manager.py -v` (and, if modified, `pytest api/tests/test_project_manager_pipeline.py -v`) passes.

## Out of Scope

- Changing `--reset` behavior (implementation already removes state file when present; this spec adds test coverage).
- Testing `--state-file`, `--backlog`, or other flags (covered by other specs).
- E2E runs that require live API (use `--dry-run` and tmp state file).

## See also

- [005-project-manager-pipeline.md](005-project-manager-pipeline.md) — project manager orchestrator, state file
- [006-overnight-backlog.md](006-overnight-backlog.md) — backlog item 24
- [041-project-manager-state-file-flag-test.md](041-project-manager-state-file-flag-test.md) — test for `--state-file` (use tmp path for reset test)

## Decision Gates (if any)

None.
