# Spec: Project Manager --reset Clears State and Starts from Index 0 (Test)

## Purpose

Ensure the project manager's `--reset` CLI flag is covered by a test that verifies the script clears persisted state and the run proceeds from backlog index 0. This guards against regressions when changing reset behavior or state handling.

## Requirements

- [ ] A test exists that runs `project_manager.py` with `--reset` (and optionally `--dry-run`) such that any existing state is cleared and the run starts from index 0.
- [ ] The test asserts that after a run with `--reset`, state reflects "start from beginning": e.g. `backlog_index` is 0 and `phase` is the default (e.g. `"spec"`), either by reading the state file or by exercising `load_state()` after the reset path.
- [ ] The test uses a dedicated state path (e.g. `--state-file` to a temporary path) so it does not depend on or overwrite the default project manager state file.


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: 005, 006, 041

## Task Card

```yaml
goal: Ensure the project manager's `--reset` CLI flag is covered by a test that verifies the script clears persisted state and the run proceeds from backlog index 0.
files_allowed:
  - api/tests/test_project_manager.py
  - api/tests/test_project_manager_pipeline.py
done_when:
  - A test exists that runs `project_manager.py` with `--reset` (and optionally `--dry-run`) such that any existing state...
  - The test asserts that after a run with `--reset`, state reflects "start from beginning": e.g. `backlog_index` is 0 an...
  - The test uses a dedicated state path (e.g. `--state-file` to a temporary path) so it does not depend on or overwrite ...
commands:
  - python3 -m pytest api/tests/test_project_manager.py -x -v
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

## API Contract (if applicable)

N/A — script CLI behavior only. The script already accepts `--reset` (see `api/scripts/project_manager.py`); this spec adds test coverage.


### Input Validation

- All string fields: min_length=1, max_length=1000
- Numeric fields: appropriate min/max bounds
- Required fields validated; missing returns 422
- Unknown fields rejected (Pydantic extra="forbid" where applicable)

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


## Verification Scenarios

The reviewer will run these scenarios against the repo to confirm the feature is implemented and correct.

---

### Scenario 1: Reset removes a pre-existing state file and run starts from index 0

**Setup:**
```bash
TMPDIR=$(mktemp -d)
STATEFILE="$TMPDIR/state.json"
# Pre-populate state with backlog_index > 0
echo '{"backlog_index": 5, "phase": "impl", "current_task_id": "task_abc", "iteration": 2, "blocked": false}' > "$STATEFILE"
```

**Action:**
```bash
python3 api/scripts/project_manager.py --dry-run --reset --state-file "$STATEFILE"
```

**Expected result:**
- Exit code 0
- The state file at `$STATEFILE` is either absent (removed by `--reset`) **or** present with `backlog_index` == 0 and `phase` == `"spec"` (i.e., reset to defaults).
- Stdout contains `DRY-RUN` or `dry-run` (case-insensitive) confirming dry-run mode ran.
- Previous values (`backlog_index: 5`, `phase: impl`) are NOT reflected in any output or the post-run state file.

**Edge case:**
- Run with `--reset` when the state file does **not** exist: script must exit 0 without error (no `FileNotFoundError`). The `os.remove` call is guarded by `os.path.isfile(STATE_FILE)`.

---

### Scenario 2: Reset with in-process `load_state()` after reset yields default values

**Setup:**
```python
import json, os, tempfile, importlib, sys
sys.path.insert(0, "api/scripts")
import project_manager as pm

tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
# Write stale state
json.dump({"backlog_index": 7, "phase": "review", "iteration": 3, "blocked": True}, tmp)
tmp.close()
pm.STATE_FILE = tmp.name
```

**Action:**
```python
# Simulate --reset: remove file if present
if os.path.isfile(pm.STATE_FILE):
    os.remove(pm.STATE_FILE)

state = pm.load_state()
```

**Expected result:**
- `state["backlog_index"]` == 0
- `state["phase"]` == `"spec"`
- `state["iteration"]` == 1
- `state["blocked"]` == False
- `state["current_task_id"]` is None

**Edge case:**
- If state file contains invalid JSON (e.g., `echo "CORRUPT" > $STATEFILE`) before reset, `load_state()` after removal still returns defaults without raising an exception.

---

### Scenario 3: pytest test for `--reset` flag passes in CI

**Setup:**
```bash
cd /path/to/repo
```

**Action:**
```bash
python3 -m pytest api/tests/test_project_manager.py -x -v -k "reset"
```

**Expected result:**
- At least one test matching `reset` is collected and passes (e.g., `test_reset_clears_state` or `test_dry_run_reset_starts_from_zero`).
- Output line: `PASSED api/tests/test_project_manager.py::test_reset_clears_state` (or similarly named).
- Overall exit code 0.

**Edge case:**
- Running without `-k reset` (`pytest api/tests/test_project_manager.py -x -v`) must also pass — the reset test must not break existing tests or leave temporary files behind.

---

### Scenario 4: Reset does not affect a different state file path (isolation)

**Setup:**
```bash
DEFAULT_STATE="api/logs/project_manager_state.json"
# Pre-populate default state to a known value
mkdir -p api/logs
echo '{"backlog_index": 9, "phase": "test"}' > "$DEFAULT_STATE"

TMPFILE=$(mktemp /tmp/pm_state_XXXX.json)
echo '{"backlog_index": 3, "phase": "impl"}' > "$TMPFILE"
```

**Action:**
```bash
python3 api/scripts/project_manager.py --dry-run --reset --state-file "$TMPFILE"
```

**Expected result:**
- The temp state file `$TMPFILE` is removed (or reset to index 0).
- The **default** state file `api/logs/project_manager_state.json` is **unchanged** — still contains `backlog_index: 9`.
- Exit code 0; no error output.

**Edge case:**
- If `--state-file` is omitted but `--reset` is passed, the **default** path is reset (not an arbitrary file). The test must use `--state-file` to avoid stomping on live state during CI.

---

### Scenario 5: Full test suite passes after adding the reset test

**Setup:** Fresh checkout, no state files present.

**Action:**
```bash
python3 -m pytest api/tests/test_project_manager.py -v --tb=short 2>&1 | tail -20
```

**Expected result:**
- All existing tests pass (no regressions).
- The new reset test (`test_reset_clears_state` or equivalent) appears as `PASSED`.
- No `ERROR` or `FAILED` lines in output.
- Final summary line: `X passed` (where X ≥ prior count + 1).

**Edge case:**
- If the test creates temporary files, they must be cleaned up via `tmp_path` fixture or `tempfile.mkdtemp` + `shutil.rmtree` in teardown — no leftover `/tmp/pm_state_*.json` files after the test run.

---

## Verification

```bash
python3 -m pytest api/tests/test_project_manager.py -x -v
```
