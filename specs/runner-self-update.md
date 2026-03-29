# Spec: Runner Self-Update

## Purpose

Stale runners execute tasks with outdated prompts, model routing tables, and project conventions.
Because runners are long-lived processes on contributor machines, any code change merged to `main`
is invisible to active runners until they restart. The self-update mechanism closes that gap by
detecting new commits on `origin/main` each poll cycle and performing an in-place git pull followed
by a process re-exec — all without requiring manual operator intervention. The feature ensures
every task claimed after a merge runs against the latest version of the runner.

## Current Implementation

`_check_for_updates_and_restart()` (`api/scripts/local_runner.py`, ~line 5454) is called once per
poll cycle when `--no-self-update` is not passed on the CLI. The sequence is:

1. `git fetch origin main --quiet` — refreshes the remote ref without merging (15 s timeout).
2. `git rev-parse HEAD` and `git rev-parse origin/main` — compares local SHA to remote SHA.
3. If they differ, sets `_update_pending` (`threading.Event`) — workers that check this flag
   (in `_worker_loop`, ~line 5233) stop claiming new tasks.
4. `git status --porcelain` — if the working tree is dirty, stashes changes with
   `git stash --include-untracked`.
5. If the current branch is not `main`, runs `git checkout main` (fallback:
   `git checkout -B main origin/main`).
6. `git pull origin main --ff-only` — falls back to `git reset --hard origin/main` if the
   fast-forward pull fails.
7. Posts a `status: "updating"` heartbeat to `/api/federation/nodes/{id}/heartbeat`.
8. Terminates child processes (codex, claude, cursor, etc.) via `psutil` SIGTERM then SIGKILL.
9. `subprocess.Popen([sys.executable] + sys.argv, start_new_session=True)` — spawns a fresh
   runner inheriting the original argv before calling `os._exit(0)`.

`--no-self-update` CLI flag sets `self_update.enabled = False`; the check is skipped entirely.

## Gaps

- **No restart cooldown.** If `git pull` or `git reset` leaves the repo in a bad state and the
  re-exec loop re-enters `_check_for_updates_and_restart()` on the very next poll cycle, the
  process can thrash in rapid restart loops with no back-off.
- **In-flight task state is dropped.** `_update_pending` signals workers to stop claiming, but
  workers already mid-execution are killed abruptly by `os._exit(0)`. The API task record is
  left in `in_progress` status with no log entry explaining the interruption.
- **No wait timeout on `_update_pending`.** Workers that are mid-task are given no bounded
  window to finish. If a worker hangs indefinitely, restart is permanently blocked because
  `_shutdown_event.set()` is called after the spawn but the old process has already exited;
  in practice the restart proceeds but running tasks are abandoned silently.
- **No API task record for interrupted tasks.** When the runner restarts while a task is
  executing, no failure or interrupted status is written to the task record. Observers cannot
  distinguish a completed task from a task that was abandoned mid-run.
- **`--no-self-update` is invisible in `cc nodes` output.** The flag is logged at startup but
  not included in the heartbeat payload, so operators have no way to confirm remotely that a
  node is running with self-update disabled.

## Requirements

- [ ] When `origin/main` advances, the runner detects the change within 2 poll cycles and
      restarts on the new SHA.
- [ ] After re-exec, the new process's `sys.argv` is identical to the original (workers count,
      dry-run, provider flags, and all other flags are preserved).
- [ ] When `--no-self-update` is passed, `_check_for_updates_and_restart()` is never called and
      no git fetch is performed.
- [ ] A restart cooldown of at least 120 seconds is enforced: if the runner restarted within
      the last 120 seconds due to a self-update, it skips further self-update checks until the
      cooldown expires (prevents thrash loops on broken pulls).
- [ ] When a restart is triggered while a task is in `in_progress` state, the runner writes a
      task log entry with a message such as
      `"Runner self-update interrupted task; re-queued as pending"` and resets the task status
      back to `pending` via the API before calling `os._exit(0)`.
- [ ] `_update_pending` triggers a bounded drain window: workers are given at most 60 seconds
      to finish in-flight tasks before the restart proceeds regardless.
- [ ] The heartbeat payload posted before restart includes `"self_update_enabled": true/false`
      so `cc nodes` can surface the flag.

## Research Inputs (Required)

- `2026-03-28` - Codebase review of `api/scripts/local_runner.py` lines 5454–5592 — primary
  source for current behavior, gap identification, and argv preservation confirmation.

## Task Card (Required)

```yaml
goal: Harden runner self-update with cooldown, in-flight task protection, and observability
files_allowed:
  - api/scripts/local_runner.py
done_when:
  - _check_for_updates_and_restart() skips the restart if last_restart_time is within 120 s
  - in-progress tasks have status reset to pending and a log entry written before os._exit(0)
  - _update_pending drain loop exits after 60 s even if workers are still running
  - heartbeat payload includes self_update_enabled field
  - all existing self-update log messages are preserved (SELF-UPDATE: prefix)
commands:
  - cd api && python3 -m pytest -q tests/ -k "self_update or runner"
constraints:
  - Do not change the --no-self-update CLI flag name or behavior
  - Do not alter git commands (fetch, pull, reset) or their timeouts
  - Do not add new dependencies beyond psutil (already used)
```

## API Contract

N/A - no API contract changes in this spec.

The heartbeat endpoint (`POST /api/federation/nodes/{id}/heartbeat`) already accepts arbitrary
`message` and status fields. The only addition is a `self_update_enabled` boolean field in the
request body, which the existing endpoint stores as-is.

## Data Model

N/A - no model changes in this spec.

## Files to Create/Modify

- `api/scripts/local_runner.py` — modify `_check_for_updates_and_restart()` to add cooldown
  logic and the in-flight task rescue write; modify `_worker_loop()` to respect the 60-second
  drain timeout on `_update_pending`; update the heartbeat call to include
  `self_update_enabled`.

## Acceptance Tests

- `api/tests/test_runner_self_update.py::test_restart_skipped_within_cooldown_window`
- `api/tests/test_runner_self_update.py::test_restart_proceeds_after_cooldown_expires`
- `api/tests/test_runner_self_update.py::test_in_flight_task_reset_to_pending_on_restart`
- `api/tests/test_runner_self_update.py::test_drain_window_expires_after_60s`
- `api/tests/test_runner_self_update.py::test_no_self_update_flag_skips_fetch`
- `api/tests/test_runner_self_update.py::test_argv_preserved_in_spawned_process`

## Concurrency Behavior

- `_update_pending` is a `threading.Event` — safe to set from the main poll loop and read from
  any worker thread without additional locking.
- The cooldown timestamp must be stored in a module-level variable and read/written under a
  short `threading.Lock` to avoid a TOCTOU race between the check and the update.
- The 60-second drain window uses `_shutdown_event.wait(timeout)` in the main thread after
  setting `_update_pending`; individual workers are not signalled separately.

## Verification

Scenario 1 — runner on old SHA restarts on new SHA within 2 poll cycles:
```
# On VPS or local, with default --interval 30
# 1. Note current SHA: git rev-parse HEAD
# 2. Push a commit to origin/main
# 3. Watch runner logs: within 60 s expect "SELF-UPDATE: new commits detected" then
#    "SELF-UPDATE: spawned new runner PID=..."
# 4. In new process startup log: sha line must show the new origin/main SHA
```

Scenario 2 — `cc nodes` shows SHA matching `git rev-parse origin/main`:
```bash
cc nodes
# SHA column for the node must equal:
git -C /path/to/repo rev-parse origin/main | cut -c1-10
```

Scenario 3 — `--no-self-update` flag suppresses updates:
```
# Start runner with --no-self-update
# Push a new commit to origin/main
# After 3 poll cycles: no "SELF-UPDATE" log lines appear
# Runner continues running on original SHA
```

Scenario 4 — re-exec preserves CLI flags:
```
# Start runner with: --loop --parallel 3 --dry-run --interval 60
# Trigger a self-update (push a commit)
# In new process startup log line "Coherence Network — Node Runner":
#   parallel must be 3, dry-run must be on, interval must be 60
```

## Out of Scope

- Automatic dependency installation (`pip install`) after pulling new code — runner assumes
  the environment is pre-provisioned.
- Rolling restart of multiple parallel runners on the same machine — each runner process
  manages its own update independently.
- Notification to human operators via email or Slack on restart.
- Rollback to a previous SHA if the new runner crashes on startup.

## Risks and Assumptions

- **Assumption: `sys.argv` is stable.** The spec assumes `sys.argv[0]` is the runner script
  path, not a `-c` string. If the runner is invoked via `python -m`, argv reconstruction
  requires testing. If this assumption is false, flag re-passing must be redesigned.
- **Risk: `psutil` unavailable.** Child process cleanup is skipped when `psutil` is missing.
  The new spawned process can then conflict with orphaned claude/codex subprocesses holding
  file locks. Mitigation: add a `psutil` availability check at startup and warn loudly.
- **Risk: git operations fail mid-sequence.** If `git pull` succeeds but `git rev-parse HEAD`
  still returns the old SHA (e.g., due to a detached HEAD), the runner will restart and
  immediately detect an "update" again, entering a loop. The cooldown requirement directly
  mitigates this.
- **Risk: task rescue write fails.** If the API is unreachable when the runner tries to reset
  in-progress tasks before restart, those tasks remain stuck in `in_progress`. Mitigation:
  attempt the write with a 5-second timeout and proceed with restart regardless — a stuck task
  is recoverable by an operator; a hung runner is not.

## Known Gaps and Follow-up Tasks

- `--no-self-update` is currently logged only at startup. Follow-up task: surface it in the
  `/api/federation/nodes/{id}` GET response so dashboards can show it without log scraping.
- There is no mechanism to force-update a runner remotely (e.g., via an API call setting a
  flag). Follow-up task: add a `force_update` field to the node heartbeat response that the
  runner checks alongside the git SHA comparison.
- Stashed changes are never popped after restart. If local modifications exist (e.g., a
  hotfix), they are silently buried. Follow-up task: emit a warning log with stash ref after
  the new process starts.

## Failure/Retry Reflection

- Failure mode: `git pull` fails with a merge conflict after stash.
  Blind spot: `git stash` does not guarantee a clean working tree if there are untracked files
  that conflict with incoming changes.
  Next action: after stash, verify `git status --porcelain` is empty before proceeding to pull;
  if not empty, abort the update cycle and log a `SELF-UPDATE: working tree dirty after stash`
  warning.

- Failure mode: spawned child process exits immediately (e.g., import error in new code).
  Blind spot: `subprocess.Popen` returns before the child has finished initializing; the old
  process has already called `os._exit(0)`.
  Next action: add a short `time.sleep(2)` after `Popen` and check `new_proc.poll()` — if the
  process has already terminated, log the error and continue running the old version.

## Decision Gates

- The 60-second drain window and 120-second cooldown values are chosen conservatively.
  If the team determines that task durations routinely exceed 60 seconds, the drain window
  should be raised or made configurable via CLI flag. Human approval required before changing
  default values.
- Resetting in-progress tasks back to `pending` on restart may cause duplicate work if another
  runner claims the same task before the restarted runner comes online. Confirm acceptable
  behavior with the team before implementing the rescue write.
