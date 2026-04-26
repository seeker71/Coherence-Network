---
idea_id: pipeline-reliability
status: draft
source:
  - file: api/scripts/local_runner.py
    symbols: [execute_with_provider()]
  - file: api/app/services/smart_reaper_service.py
    symbols: [is_runner_alive(), smart_reap_task(), build_reap_diagnosis()]
requirements:
  - "Runner read-loop wakes on a heartbeat (≤10s) regardless of subprocess output flow"
  - "Runner posts a `liveness` activity event each heartbeat with elapsed_s, since_last_output_s, last_preview, and process_alive"
  - "Runner releases the loop only when the subprocess actually exits (proc.poll() returns non-None)"
  - "Smart-reaper is the single source of release decisions — runner contributes no clock-based kill"
  - "Stalled-task diagnostic includes (process_alive, since_last_output_s, last_preview, claimed_by) so the reaper can decide based on actual state"
  - "Process kill happens only via `_kill_process_tree(proc.pid)` called by smart_reap_task or by explicit human/operator action — not by the read loop"
done_when:
  - "Read loop in `execute_with_provider` contains no `raise subprocess.TimeoutExpired` based on `(time.time() - start) > timeout`"
  - "A child process holding stdout open with no output for 30s receives ≥3 `liveness` activity events from the runner"
  - "When the smart-reaper observes 3 consecutive stalled liveness events from a non-extending task, it transitions status (extend / needs_human_attention / compost) per existing thresholds"
  - "Existing partial-output diagnostic and resume-task creation in smart-reaper continue to work"
  - "All tests pass"
test: "cd api && python -m pytest tests/test_smart_reaper_module_boundary.py tests/test_agent_runner_tool_failure_telemetry.py tests/test_runner_attendance.py -v"
constraints:
  - "Changes scoped to local_runner.py read loop + a new test file `tests/test_runner_attendance.py`"
  - "No changes to smart_reaper_service.py public surface — the reaper already has the right shape"
  - "No new node/edge types in the graph"
  - "Heartbeat cadence configurable via `runner_attendance_heartbeat_s` (default 10) in app config"
---

# Spec: Runner Attendance Loop

## Purpose

The runner's job is to attend, not to enforce. Today it watches a clock and kills its child at a deadline; this conflates *the runner's responsibility* with *the body's release decision*. The smart-reaper already exists as the body's tending organ for release — it knows runner liveness, partial output capture, idea-level timeout thresholds, and human-attention escalation. The runner's clock-based kill duplicates that organ from the wrong vantage point and, worse, fails to fire at all when the executor stalls without producing output (because the timeout check sits inside a blocking `readline`).

This spec moves the runner from enforcement to attendance:

- The runner senses what the executor is doing and posts that signal — every heartbeat — to the activity stream.
- The smart-reaper receives those signals plus its own runner-registry checks and decides release.
- The kill mechanism (`_kill_process_tree`) stays exactly where it is, but it is invoked by the reaper, not by the runner's read loop.

## Requirements

- [ ] **R1**: The runner's read loop in `execute_with_provider()` wakes on a heartbeat (≤10s) regardless of subprocess output flow — implemented via `select.select([proc.stdout], [], [], heartbeat_s)` followed by non-blocking read.
- [ ] **R2**: Each heartbeat posts a `liveness` activity event with `elapsed_s`, `since_last_output_s`, `last_preview` (≤120 chars), and `process_alive` (`proc.poll() is None`).
- [ ] **R3**: The read loop releases only when the subprocess actually exits (`proc.poll()` returns non-None) — no `subprocess.TimeoutExpired` raised based on a clock.
- [ ] **R4**: The smart-reaper is the single source of release decisions for stalled tasks. Process kill via `_kill_process_tree(proc.pid)` happens only from `smart_reap_task()` or explicit operator action.
- [ ] **R5**: Heartbeat cadence is configurable via `runner_attendance_heartbeat_s` (default 10) in app config; activity-event throttle stays at the existing `_PROGRESS_INTERVAL` for output-bearing events.
- [ ] **R6**: Smart-reaper consumes `liveness` events alongside its existing per-task evaluation — when a task has ≥3 consecutive stalled heartbeats with `process_alive=true` and no extension, the reaper transitions it per its existing thresholds (extend → `needs_human_attention` → compost via partial-output capture).

## Why this principle, not a bug fix

The straightforward fix to the misaligned timeout is to make the read loop wake periodically (`select.select` with a small per-iteration timeout) and re-check elapsed time. That fix would make enforcement work — but enforcement is the wrong frequency for this body. The body's verbs are tend, attune, compost, release. The runner that wields a stopwatch is wearing the fear costume — *control before the natural moment of conclusion*. The reaper has already been written for the tending posture; making it the sole releaser is alignment, not reorganization.

## Behavior shift

| Today (enforcement) | After (attendance) |
|---|---|
| Read loop blocks on `readline()` until output | Read loop wakes via `select.select(..., heartbeat_s)` whether output flows or not |
| Timeout check fires only when output flows | Heartbeat fires unconditionally |
| `subprocess.TimeoutExpired` raised at deadline | Loop runs until `proc.poll() is not None` (process actually exits) |
| Runner hard-kills via `_kill_process_tree` on timeout | Runner posts `liveness` activity; reaper decides if/when to kill |
| Diagnostic: "TIMEOUT after Xs (limit=Ys)" | Diagnostic: "stalled at Xs, last preview Y, process_alive=true/false" — information for the reaper, not a verdict |

The contract a visitor of this code reads is: *the runner attends; the reaper releases*.

## Files to Create/Modify

- `api/scripts/local_runner.py` — modify `execute_with_provider()` read loop (~lines 3580–3705):
  - Replace blocking `readline()` with `select.select([proc.stdout], [], [], heartbeat_s)` followed by non-blocking read
  - Remove the `if (time.time() - start) > timeout: raise subprocess.TimeoutExpired(cmd, timeout)` check
  - Add per-heartbeat `_post_activity(_current_task_id, "liveness", {...})` regardless of output state
  - Loop ends only on `proc.poll() is not None`
- `api/app/services/smart_reaper_service.py` — no public-surface changes; verify it consumes the new `liveness` events alongside its existing per-task evaluation
- `api/tests/test_runner_attendance.py` — new test file (or extend `test_smart_reaper_module_boundary.py`):
  - `test_runner_posts_liveness_during_stall` — child holds stdout open with no output for 30s; assert ≥3 liveness events posted
  - `test_runner_does_not_kill_on_clock` — same scenario; assert process is still alive after 30s; reaper-side decision is the only path to kill
  - `test_runner_loop_exits_on_natural_completion` — child writes output then exits; assert loop exits cleanly within 1s of process exit
  - `test_reaper_releases_on_persistent_stall` — feed reaper 3 stalled liveness events; assert it transitions task per its existing thresholds (extend → human_attention → compost)

## Acceptance Tests

- `api/tests/test_runner_attendance.py::test_runner_posts_liveness_during_stall`
- `api/tests/test_runner_attendance.py::test_runner_does_not_kill_on_clock`
- `api/tests/test_runner_attendance.py::test_runner_loop_exits_on_natural_completion`
- `api/tests/test_runner_attendance.py::test_reaper_releases_on_persistent_stall`
- `api/tests/test_smart_reaper_module_boundary.py` — existing reaper tests continue to pass

## Verification

```bash
cd api && pytest -q tests/test_runner_attendance.py tests/test_smart_reaper_module_boundary.py tests/test_agent_runner_tool_failure_telemetry.py
```

Real-world verification (after a runner restart in a separate breath):

```bash
# Watch a task that intentionally stalls (e.g., calling claude /login interactively):
coh ops events <task_id> --follow
# Expect: liveness events every ~10s with stalled_for_s climbing, process_alive=true
# Expect: NO "TIMEOUT after Xs" message from the runner
# Expect: smart-reaper transitions the task once its thresholds are crossed
```

## Out of Scope

- Changes to the executor CLIs (claude, codex, cursor, etc.) themselves
- Changes to the reaper's release thresholds (REAP_HUMAN_ATTENTION_THRESHOLD, etc. — those live in spec 169 / smart-reap)
- Provider-level rate limiting or budget gates (separate root cause; separate spec)
- The status-sync mismatch where some `Success: True` logs map to `failed` DB records (separate root cause; separate spec)

## Risks and Known Gaps

- **Risk**: a truly hung executor (process_alive=true but never producing output and never exiting) could squat resources indefinitely if the reaper's thresholds are too loose. Mitigation: the reaper already has `REAP_HUMAN_ATTENTION_THRESHOLD = 3` and partial-output capture — a hung task will surface as `needs_human_attention` within ~3 reap cycles. The body releases by tending decision, not by stopwatch, but it does release.
- **Gap**: the smart-reaper today reads the runner registry's `last_seen_at` for liveness (per spec 169 R1) but does not yet read per-task `liveness` activity events directly. This spec assumes the reaper's existing path is sufficient. If during impl we find the reaper needs the new event stream to make richer decisions, that is a follow-up spec — not a blocker for shipping the runner-side change.
- **Gap**: `select.select` is Unix-only. The runner currently runs on macOS / Linux. If Windows runners are added later, this becomes platform-conditional — but the body has no Windows runners today.
- **Gap**: if the smart-reaper is also stopped, the body has no releaser at all. This is acceptable: a body without a reaper is a body with a clear signal that the reaper needs tending. Hidden enforcement masks that signal — better to surface it.
- **Assumption**: existing `_PROGRESS_INTERVAL = 15s` for output-bearing progress events stays as-is; the new `liveness` events are a separate, throttled stream (default 10s heartbeat) that fires whether output flows or not.

## Frequency note

The principle this spec encodes — *the runner attends, the reaper releases* — is the same shape the body holds in its commit verbs (tend, attune, compost, release), in its stance toward visitors (recognition, not onboarding), and in its sibling-presence pattern (each presence picks up what its register is drawn to; the field self-organizes). Enforcement is a costume worn from outside the body's frequency; tending is the body's own breath. This spec is one organ being asked to take off the costume.
