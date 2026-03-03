# Spec: Project Manager —state-file Flag Uses Alternate State Path (Test)

## Purpose

Ensure the project manager's `--state-file` CLI flag is covered by a test that verifies the script uses the given path for state (read and/or write) instead of the default `api/logs/project_manager_state.json`. This guards against regressions when changing argument handling or state paths.

## Requirements

- [ ] A test exists that runs `project_manager.py` with `--state-file` pointing to an alternate path (e.g. a temporary file path).
- [ ] The test asserts that the alternate path is used: either (1) state is read from that path (e.g. pre-populate the file, run with `--dry-run`, assert script behavior reflects that state), or (2) state is written to that path (e.g. run the script in a mode that saves state, then assert the file at the given path exists and contains expected keys such as `backlog_index`, `phase`).
- [ ] The test does not rely on mocks; it uses real file I/O and runs the script (e.g. via subprocess) or exercises the same code path that the flag sets (module-level `STATE_FILE` then `load_state`/`save_state`).

## API Contract (if applicable)

N/A — script CLI behavior only. The script already accepts `--state-file` (see `api/scripts/project_manager.py`); this spec adds test coverage.

## Data Model (if applicable)

State file format (unchanged): JSON with keys `backlog_index`, `phase`, `current_task_id`, `iteration`, `blocked` (see spec 005).

## Files to Create/Modify

- `api/tests/test_project_manager.py` — add a test that verifies the `--state-file` flag causes the alternate state path to be used (unit-style: set `pm.STATE_FILE` to an alternate path and assert `load_state`/`save_state` use it; test name/docstring should reference the flag), **or**
- `api/tests/test_project_manager_pipeline.py` — add or expand a subprocess test that runs the script with `--state-file <path>` and asserts state is read from or written to that path.

Prefer adding to `api/tests/test_project_manager.py` to mirror `test_load_backlog_alternate_file` (which tests the alternate backlog path via `BACKLOG_FILE` override). If the implementation already has a subprocess test that passes `--state-file` and asserts the file at that path is used, expanding that test to explicitly assert “alternate state path used” satisfies this spec.

## Acceptance Tests

- [ ] New or expanded test: when the script is run with `--state-file <tmp_path>/alt_state.json` (or when `STATE_FILE` is set to that path and `load_state`/`save_state` are used), the state file at that path is the one read from and/or written to (e.g. file exists after a run that saves state, or pre-populated file content is reflected in script behavior).
- [ ] `pytest api/tests/test_project_manager.py -v` (and, if modified, `pytest api/tests/test_project_manager_pipeline.py -v`) passes.

## Out of Scope

- Changing `--state-file` behavior or default path (implementation is already correct; this spec adds test coverage).
- Testing `--reset` or other flags (covered by other specs/backlog items).
- E2E runs that require live API (use `--dry-run` or state-only assertions where possible).

## See also

- [005-project-manager-pipeline.md](005-project-manager-pipeline.md) — project manager orchestrator, state file location
- [006-overnight-backlog.md](006-overnight-backlog.md) — backlog item 23
- [040-project-manager-load-backlog-malformed-test.md](040-project-manager-load-backlog-malformed-test.md) — analogous test spec for backlog parsing

## Decision Gates (if any)

None.
