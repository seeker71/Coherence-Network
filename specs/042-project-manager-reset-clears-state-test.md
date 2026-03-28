# Spec 042: Project Manager `--reset` Clears State and Starts from Index 0 (Test)

## Summary

The `project_manager.py` script supports a `--reset` CLI flag that removes the persisted state file
before starting a run, ensuring the pipeline begins from backlog index 0 with all default state
values. This spec defines the required test coverage that proves `--reset` behaves correctly under
normal conditions, edge cases, and in combination with `--state-file`.

**Gap being addressed**: The `--reset` flag's behavior (deleting the state file) is already
implemented in `api/scripts/project_manager.py` (lines 1076–1077). This spec adds the missing
test coverage that verifies reset semantics end-to-end, guarding against regressions when state
handling or argument parsing changes.

## Goal

Add tests to `api/tests/test_project_manager.py` that verify:

1. `--reset` removes the state file if it exists.
2. After a reset run, `load_state()` returns `backlog_index=0` and default `phase`.
3. `--reset` combined with `--state-file <tmp_path>` operates on the alternate path, not the
   default `STATE_FILE`.
4. `--reset` is a no-op (does not error) when no state file exists.
5. `--reset --dry-run` prints `DRY-RUN: backlog index=0` on stdout.

## Requirements

- [ ] **R1**: A test named `test_reset_clears_state_file` that:
  - Pre-populates a tmp state file with `backlog_index=7, phase="impl"`.
  - Sets `pm.STATE_FILE` to that tmp path.
  - Calls the reset path: `pm.STATE_FILE = str(tmp_state); os.remove(pm.STATE_FILE)` mirroring
    the flag logic, then calls `pm.load_state()`.
  - Asserts that `load_state()` returns `backlog_index=0` and `phase="spec"` (default).

- [ ] **R2**: A test named `test_reset_flag_removes_state_file` that:
  - Writes a state file with `backlog_index=3` to a `tmp_path`.
  - Invokes `project_manager.py` via `subprocess.run` with `--reset --dry-run --state-file <path>`.
  - Asserts the subprocess exits 0.
  - Asserts the state file at `<path>` no longer exists **or** contains `backlog_index=0`.
  - Asserts stdout contains `DRY-RUN: backlog index=0`.

- [ ] **R3**: A test named `test_reset_noop_when_no_state_file` that:
  - Ensures the tmp state file does NOT exist.
  - Runs `project_manager.py --reset --dry-run --state-file <path>` via subprocess.
  - Asserts exit code 0 (no crash or exception).

- [ ] **R4**: A test named `test_reset_uses_state_file_arg` that:
  - Writes state with `backlog_index=5` to `tmp_path/alt_state.json`.
  - Runs `project_manager.py --reset --dry-run --state-file <alt_state.json path>`.
  - Asserts exit code 0.
  - Asserts the file at `<alt_state.json path>` no longer exists (deleted by reset).
  - Asserts the default `STATE_FILE` was NOT touched.

- [ ] **R5**: All tests use a dedicated `--state-file` argument (tmp path) to avoid polluting
  or depending on the default `api/logs/project_manager_state.json`.

- [ ] **R6**: `pytest api/tests/test_project_manager.py -x -v` passes with all new tests included.

## API Contract

N/A — this is script/CLI behavior only. No HTTP endpoints are added or changed.

The script CLI interface (already implemented):
```
python3 api/scripts/project_manager.py --reset [--dry-run] [--state-file PATH]
```

| Flag | Type | Effect |
|------|------|--------|
| `--reset` | bool flag | Delete `STATE_FILE` before loading state; starts pipeline from index 0 |
| `--dry-run` | bool flag | No HTTP calls; print preview to stdout; exit 0 |
| `--state-file PATH` | string | Override `STATE_FILE` global to `PATH` |

Reset logic (lines 1074–1077 of `api/scripts/project_manager.py`):
```python
if args.state_file:
    STATE_FILE = os.path.normpath(os.path.abspath(args.state_file))
if args.reset and os.path.isfile(STATE_FILE):
    os.remove(STATE_FILE)
```

## Data Model

State file format (JSON), unchanged by this spec:

```json
{
  "backlog_index": 0,
  "phase": "spec",
  "current_task_id": null,
  "iteration": 1,
  "blocked": false,
  "in_flight": [],
  "split_parent": null
}
```

After `--reset`:
- If `STATE_FILE` existed: the file is deleted; subsequent `load_state()` returns all defaults.
- If `STATE_FILE` did not exist: no-op; `load_state()` still returns all defaults.

Default values returned by `load_state()` when file is absent:
- `backlog_index`: `0`
- `phase`: `"spec"`
- `iteration`: `1`
- `blocked`: `False`

## Files to Create / Modify

| File | Action |
|------|--------|
| `api/tests/test_project_manager.py` | **Modify** — add 4 new test functions (R1–R4 above) |

No other files are modified. Do not change `api/scripts/project_manager.py` (reset logic is
already correct; this spec only adds test coverage).

## Verification Scenarios

Each scenario below must pass when run against the actual script invocation.

---

### Scenario 1: Reset removes existing state file and load_state returns index 0

**Setup**: A JSON file at `tmp_path/state.json` exists with content:
```json
{"backlog_index": 7, "phase": "impl", "iteration": 3, "blocked": false}
```

**Action** (in-process, mirroring the flag):
```python
import api.scripts.project_manager as pm
pm.STATE_FILE = str(tmp_path / "state.json")
# The reset path:
import os
if os.path.isfile(pm.STATE_FILE):
    os.remove(pm.STATE_FILE)
state = pm.load_state()
assert state["backlog_index"] == 0
assert state["phase"] == "spec"
```

**Expected result**: `load_state()` returns `{"backlog_index": 0, "phase": "spec", ...}`.
The file `tmp_path/state.json` does not exist after reset.

**Edge case**: If the file had already been deleted before reset, `load_state()` must still
return defaults without raising `FileNotFoundError`.

---

### Scenario 2: --reset --dry-run subprocess prints index=0 and exits 0

**Setup**: A state file at `tmp_path/pm_state.json` exists with `backlog_index=3`.

**Action**:
```bash
python3 api/scripts/project_manager.py \
  --reset --dry-run --state-file /tmp/pytest_XXXX/pm_state.json
```
Or in pytest:
```python
result = subprocess.run(
    [sys.executable, script, "--reset", "--dry-run", "--state-file", str(state_path)],
    cwd=str(project_root),
    capture_output=True, text=True, timeout=15,
)
```

**Expected result**:
- `result.returncode == 0`
- `result.stdout` contains `"DRY-RUN: backlog index=0"` (exact string from line 1104 of script)
- The state file at `state_path` either does not exist or has `backlog_index=0`

**Edge case**: If the state file contained `backlog_index=0` already (no reset needed),
the dry-run must still print `"DRY-RUN: backlog index=0"` (idempotent).

---

### Scenario 3: --reset is a no-op when no state file exists

**Setup**: The tmp state file path does NOT exist on disk.

**Action**:
```bash
python3 api/scripts/project_manager.py \
  --reset --dry-run --state-file /tmp/pytest_XXXX/nonexistent_state.json
```

**Expected result**:
- `result.returncode == 0` (no crash, no `FileNotFoundError`)
- `result.stdout` contains `"DRY-RUN: backlog index=0"`
- No traceback in `result.stderr`

**Edge case**: Passing a `--state-file` path in a directory that does not yet exist must not
crash (the reset only does `os.remove` if `os.path.isfile()` is True, so a missing path is safe).

---

### Scenario 4: --reset uses --state-file path, not the default STATE_FILE

**Setup**:
- `tmp_path/alt_state.json` exists with `backlog_index=5`.
- Default `STATE_FILE` (`api/logs/project_manager_state.json`) is untouched (may or may not exist).

**Action**:
```bash
python3 api/scripts/project_manager.py \
  --reset --dry-run --state-file /tmp/pytest_XXXX/alt_state.json
```

**Expected result**:
- `result.returncode == 0`
- `tmp_path/alt_state.json` no longer exists (deleted by reset).
- Default `api/logs/project_manager_state.json` is unchanged (its mtime and content are the same
  before and after the subprocess runs).
- `result.stdout` contains `"DRY-RUN: backlog index=0"`.

**Edge case**: If `--state-file` is not given alongside `--reset`, the default path is used.
The test must NOT skip the `--state-file` arg (to avoid side-effects on the default state).

---

### Scenario 5: load_state after reset returns all expected default keys

**Setup**: State file deleted (or never written) at `tmp_path/state.json`.

**Action** (in-process):
```python
pm.STATE_FILE = str(tmp_path / "state.json")
state = pm.load_state()
```

**Expected result**:
```python
assert state["backlog_index"] == 0
assert state["phase"] == "spec"
assert state["iteration"] == 1
assert state["blocked"] == False
assert "in_flight" in state          # list, may be [] or present
assert "split_parent" in state       # backward-compat key (spec 042 test_backward_compatible_state_load)
```

**Edge case**: If the state file contains only some keys (e.g. `{"backlog_index": 0}`),
`load_state()` must merge with defaults and not raise `KeyError` for missing keys.

---

## Acceptance Tests

- [ ] `pytest api/tests/test_project_manager.py::test_reset_clears_state_file -v` passes.
- [ ] `pytest api/tests/test_project_manager.py::test_reset_flag_removes_state_file -v` passes.
- [ ] `pytest api/tests/test_project_manager.py::test_reset_noop_when_no_state_file -v` passes.
- [ ] `pytest api/tests/test_project_manager.py::test_reset_uses_state_file_arg -v` passes.
- [ ] `pytest api/tests/test_project_manager.py -x -v` passes (all existing + new tests).
- [ ] No test writes to or reads from the default `api/logs/project_manager_state.json`.

## Out of Scope

- Changing `--reset` implementation (already correct; no implementation changes).
- Testing `--state-file` in isolation without `--reset` (covered by spec 041).
- Testing `--backlog` or other flags (covered by specs 040, 005).
- E2E runs requiring live API or database access (use `--dry-run` + tmp state file only).
- Distributed or concurrent reset behavior.

## See Also

- [005-project-manager-pipeline.md](005-project-manager-pipeline.md) — orchestrator, state file location, `load_state`/`save_state`
- [040-project-manager-load-backlog-malformed-test.md](040-project-manager-load-backlog-malformed-test.md) — analogous test spec for backlog parsing
- [041-project-manager-state-file-flag-test.md](041-project-manager-state-file-flag-test.md) — test for `--state-file` alternate path

## Verification

```bash
python3 -m pytest api/tests/test_project_manager.py -x -v -k "reset"
```

Expected output (all 4 new tests):
```
PASSED api/tests/test_project_manager.py::test_reset_clears_state_file
PASSED api/tests/test_project_manager.py::test_reset_flag_removes_state_file
PASSED api/tests/test_project_manager.py::test_reset_noop_when_no_state_file
PASSED api/tests/test_project_manager.py::test_reset_uses_state_file_arg
```

## Risks and Known Gaps

| Risk | Mitigation |
|------|-----------|
| Default STATE_FILE contamination in tests | All tests MUST pass `--state-file <tmp_path>` |
| Script cwd assumption | `subprocess.run` must set `cwd` to project root (not `api/`) |
| Slow subprocess startup | Use `timeout=15` per subprocess call |
| `--dry-run` stdout format change | Tests assert substring `"DRY-RUN: backlog index=0"` (from line 1104 of script); update if format changes |
| `load_state()` default key changes | If new default keys are added to `load_state`, Scenario 5 may need updating |

## Concurrency Behavior

- **Read operations**: `load_state()` is safe for concurrent access (read-only).
- **Write / delete operations**: `--reset` deletes the state file; tests must use isolated tmp paths to avoid race conditions between parallel test processes.
- **Recommendation**: Each test function receives its own `tmp_path` fixture; no shared state files.

## Failure and Retry Behavior

- Individual test failures do not affect other tests (each uses isolated `tmp_path`).
- If the subprocess invocation times out (`timeout=15`), the test fails with a clear message.
- No retry logic is needed for test invocations.
