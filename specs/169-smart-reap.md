# Spec 169: Smart Reap — Diagnose, Capture, and Resume Stuck Tasks

*Format: [specs/TEMPLATE.md](TEMPLATE.md)*

## Purpose

The current reaper blindly marks stale tasks as `timed_out` with zero actionable diagnostics. It does
not distinguish between a runner that crashed, a slow provider that simply needs more time, and a truly
orphaned process. The result: silent data loss, duplicate retries that re-fail for the same reason, and
engineers left guessing what happened.

Smart Reap upgrades the reaper into a diagnostic-first system. Before killing a task it checks whether
the runner is still alive and whether the provider process is still active. If the provider is running
but slow, it extends the timeout instead of killing. If it has crashed, it captures partial output from
the on-disk log, records a structured diagnosis in the task context, creates a smart resume task that
includes the partial work, and tracks per-idea timeout history so repeated failures surface for human
attention instead of looping indefinitely.

## Requirements

- [ ] **R1 — Runner liveness check**: Before reaping a task, query the runner registry. If the runner
  that claimed the task is still online (`last_seen_at` within 3× the runner heartbeat interval, i.e.
  ≤ 270 s), the provider is presumed still running.
- [ ] **R2 — Timeout extension for live runners**: If R1 confirms the runner is alive (and the task
  has not exceeded `3 × max_age_minutes`), extend the reap deadline by `max_age_minutes` and emit a
  `reap_extended` event instead of marking `timed_out`. Max 2 extensions per task; after that, reap
  regardless.
- [ ] **R3 — Provider-crash capture**: If the runner is offline or never claimed the task
  (`claimed_by` is null), read the last 4 kB of the on-disk task log to extract stderr/partial output.
  Classify the crash type using the existing `failed_task_diagnostics_service.classify_error()`.
- [ ] **R4 — Structured diagnosis in task context**: On reap, write a `reap_diagnosis` sub-object into
  the task's `context` field:
  ```json
  {
    "reap_diagnosis": {
      "runner_alive": false,
      "provider": "claude",
      "error_class": "executor_crash",
      "partial_output_chars": 1840,
      "partial_output_pct": 34,
      "extensions_granted": 1,
      "reaped_at": "2026-03-28T06:00:00Z"
    }
  }
  ```
- [ ] **R5 — Resume task when partial output ≥ 20%**: If `partial_output_pct ≥ 20`, create a new
  task with the same `task_type` and `idea_id` whose direction includes the full partial output prefix:
  > "Previous attempt produced this partial work [attached]. Continue from where it left off.\n\n---\n{partial_output}"
- [ ] **R6 — Reap history tracking per idea**: Maintain a `reap_history` sub-object in the idea's
  task context. Each timeout increments `timeout_count`. When `timeout_count ≥ 3` for the same
  `idea_id + task_type` combination, mark the idea as `needs_human_attention` in the task context
  and stop creating automated retries.
- [ ] **R7 — `GET /api/agent/reap-history`**: New endpoint returning per-idea reap summary for the
  last 30 days: idea_id, idea_name, task_type, timeout_count, last_reaped_at, needs_human_attention.
- [ ] **R8 — Observable via existing Telegram alerts**: Reap events with structured diagnosis trigger
  a Telegram notification (using the existing `format_task_alert` mechanism) when `error_class` is
  `executor_crash` or `needs_human_attention` is newly set.
- [ ] **R9 — `GET /api/agent/tasks/{id}/reap-diagnosis`**: Convenience endpoint returning the
  `reap_diagnosis` sub-object for a single task. Returns 404 if the task was never reaped.
- [ ] **R10 — Idempotent on double-run**: If the reaper runs twice in the same window (e.g. two
  concurrent runners), only the first PATCH to `timed_out` succeeds; the second sees the task is no
  longer `running` and skips it gracefully.

## Research Inputs

- `2026-03-28` — Codebase analysis: `api/scripts/local_runner.py:_reap_stale_tasks()` — current
  blind reaper logic, 15-minute threshold, partial checkpoint reading exists but is incomplete
- `2026-03-28` — `api/app/services/failed_task_diagnostics_service.py` — `classify_error()` ready
  to classify crash type; can be reused in reaper
- `2026-03-28` — `api/app/services/agent_runner_registry_service.py` — runner registry stores
  `pid`, `status`, `last_seen_at`, `active_task_id`, `lease_expires_at`; queryable
- `2026-03-28` — `api/app/models/agent.py` — `AgentTask.context` is a free-form `Dict[str, Any]`;
  `error_summary` and `error_category` are first-class fields
- `2026-03-28` — `api/app/services/pipeline_advance_service.py` — checks `timed_out`/`failed`
  status; must remain compatible with new diagnosis fields
- `2026-03-28` — `api/app/services/federation_service.py:614` — already warns on >2 timeouts per
  idea; R6 extends this logic more deeply

## Task Card

```yaml
goal: >
  Upgrade the reaper to diagnose why tasks are stuck, capture partial work, extend timeout for live
  runners, and surface repeated failures for human review — eliminating blind timed_out entries.
files_allowed:
  - api/scripts/local_runner.py
  - api/app/services/smart_reap_service.py         # NEW
  - api/app/routers/agent_tasks_routes.py
  - api/app/routers/agent_run_state_routes.py
  - api/app/models/agent.py
  - api/app/services/agent_runner_registry_service.py
  - api/app/services/failed_task_diagnostics_service.py
  - api/tests/test_smart_reap.py                   # NEW
done_when:
  - _reap_stale_tasks() queries runner registry before marking timed_out
  - Runner alive → timeout extended (up to 2 times), task stays running
  - Runner dead → reap_diagnosis written to task context with error_class
  - Partial output ≥ 20% of expected → resume task created automatically
  - timeout_count ≥ 3 for same idea+type → needs_human_attention set, retries stop
  - GET /api/agent/reap-history returns per-idea timeout summary
  - GET /api/agent/tasks/{id}/reap-diagnosis returns 200 with diagnosis or 404
  - All 8 new tests pass in pytest
commands:
  - cd api && python -m pytest tests/test_smart_reap.py -v
  - cd api && python -m pytest tests/test_agent.py tests/test_agent_runner_registry_api.py -x
constraints:
  - Do not break existing timed_out / failed pipeline advance logic
  - Do not add DB migrations; use task context JSON for all new state
  - Extensions never exceed 2 per task — hard cap
  - Resume task must never have retry_count > max allowed
  - Reap history computed from task context records, not a new table
```

## API Contract

### `GET /api/agent/reap-history`

Returns a list of per-idea reap summaries for the last 30 days.

**Query Parameters**
- `idea_id` (optional string): filter to single idea
- `needs_attention` (optional bool): filter to only ideas with `needs_human_attention=true`
- `limit` (int, default 50, max 200)

**Response 200**
```json
{
  "items": [
    {
      "idea_id": "abc123",
      "idea_name": "Smart Reap",
      "task_type": "impl",
      "timeout_count": 3,
      "last_reaped_at": "2026-03-28T05:45:00Z",
      "needs_human_attention": true,
      "last_error_class": "executor_crash",
      "last_partial_output_pct": 34
    }
  ],
  "total": 1
}
```

**Response 200 (empty)**
```json
{ "items": [], "total": 0 }
```

### `GET /api/agent/tasks/{id}/reap-diagnosis`

Returns the `reap_diagnosis` sub-object for a previously reaped task.

**Response 200**
```json
{
  "task_id": "task_abc123",
  "runner_alive": false,
  "provider": "claude",
  "error_class": "executor_crash",
  "partial_output_chars": 1840,
  "partial_output_pct": 34,
  "extensions_granted": 1,
  "resume_task_id": "task_def456",
  "reaped_at": "2026-03-28T05:45:00Z"
}
```

**Response 404**
```json
{ "detail": "Task task_abc123 has no reap diagnosis (never reaped or not found)" }
```

### `PATCH /api/agent/tasks/{id}` — Extended context fields

No new fields added to the request schema. The `context` dict now carries a `reap_diagnosis`
sub-object that downstream consumers can read. Existing fields (`error_summary`, `error_category`)
continue to be used for compatibility.

## Data Model

New sub-object written to `AgentTask.context["reap_diagnosis"]` on reap:

```yaml
reap_diagnosis:
  runner_alive: bool         # True if runner was online at reap time
  provider: str              # Provider name from task context (e.g. "claude")
  error_class: str           # One of: executor_crash | timeout | provider_error | validation_failure | unknown
  partial_output_chars: int  # Characters in captured partial log
  partial_output_pct: int    # Estimated pct of expected output (0–100)
  extensions_granted: int    # How many timeout extensions were granted (0, 1, or 2)
  resume_task_id: str | null # ID of resume task created (null if not created)
  reaped_at: str             # ISO 8601 UTC timestamp

reap_history:               # Written to context["reap_history"] per task
  idea_id: str
  timeout_count: int
  needs_human_attention: bool
  last_reaped_at: str
```

Per-idea reap history is derived by scanning tasks with `status=timed_out` and grouping by
`context.idea_id`. No new DB table is required; the reap history endpoint computes on the fly
with a lightweight aggregation over the last 30 days.

## Files to Create/Modify

- `api/app/services/smart_reap_service.py` *(new)* — Core smart reap logic:
  - `is_runner_alive(task: dict) -> bool` — query runner registry
  - `maybe_extend_timeout(task: dict, extension_count: int) -> bool` — emit reap_extended and return True if extended
  - `capture_partial_output(task_id: str, log_dir: Path) -> tuple[str, int]` — read log, return (text, chars)
  - `estimate_partial_pct(partial_chars: int, task_type: str) -> int` — heuristic estimate
  - `build_resume_direction(original_direction: str, partial_output: str) -> str` — compose resume prompt
  - `get_idea_timeout_count(idea_id: str, task_type: str) -> int` — aggregate from API
  - `reap_idea_history(idea_id: str | None, needs_attention: bool, limit: int) -> list[dict]`
- `api/scripts/local_runner.py` *(modify)* — Replace `_reap_stale_tasks()` with smart version
- `api/app/routers/agent_tasks_routes.py` *(modify)* — Add reap-history and reap-diagnosis endpoints
- `api/tests/test_smart_reap.py` *(new)* — Pytest tests for R1–R9

## Acceptance Tests

- `api/tests/test_smart_reap.py::test_runner_alive_extends_timeout`
- `api/tests/test_smart_reap.py::test_runner_dead_reaps_with_diagnosis`
- `api/tests/test_smart_reap.py::test_partial_output_creates_resume_task`
- `api/tests/test_smart_reap.py::test_no_resume_below_20pct`
- `api/tests/test_smart_reap.py::test_reap_history_endpoint_empty`
- `api/tests/test_smart_reap.py::test_reap_history_endpoint_populated`
- `api/tests/test_smart_reap.py::test_reap_diagnosis_endpoint_200`
- `api/tests/test_smart_reap.py::test_reap_diagnosis_endpoint_404`
- `api/tests/test_smart_reap.py::test_needs_human_attention_after_3_timeouts`
- `api/tests/test_smart_reap.py::test_idempotent_double_reap`

## Verification Scenarios

### Scenario 1 — Live runner extends timeout, task keeps running

**Setup**: A task is in `running` status for 16 minutes (past the 15 min threshold). The runner
that claimed it has posted a heartbeat within the last 60 seconds and its registry entry has
`last_seen_at` less than 270 s ago.

**Action**:
```bash
# Trigger reaper cycle manually (or wait for 10-minute poll)
# Then inspect task status
curl -s https://api.coherencycoin.com/api/agent/tasks/<task_id> | jq '{status, context}'
```

**Expected**: Task status remains `"running"`. `context.reap_extensions` is `1`. No `reap_diagnosis`
written yet. Reaper log shows `REAPER: extended timeout for <task_id> (runner alive, ext 1/2)`.

**Edge case**: If the runner posts no heartbeat for 300 s after the extension, next reaper cycle
treats it as dead and proceeds to reap normally.

---

### Scenario 2 — Dead runner, crash captured, resume task created

**Setup**: A task is in `running` status for 20 minutes. The runner that claimed it is missing from
the registry (or last seen > 270 s ago). A log file `api/logs/tasks/task_<id>.log` exists with 2000
characters of partial Claude output (implementation code started but incomplete).

**Action**:
```bash
# After reaper runs:
curl -s https://api.coherencycoin.com/api/agent/tasks/<task_id> | jq '.status, .context.reap_diagnosis'
curl -s https://api.coherencycoin.com/api/agent/tasks/<task_id>/reap-diagnosis
```

**Expected**:
```json
{
  "status": "timed_out",
  "reap_diagnosis": {
    "runner_alive": false,
    "error_class": "executor_crash",
    "partial_output_chars": 2000,
    "partial_output_pct": 34,
    "resume_task_id": "task_<new_id>"
  }
}
```
A new resume task exists with direction starting with:
> "Previous attempt produced this partial work [attached]. Continue from where it left off."

**Edge case**: If the log file does not exist, `partial_output_chars = 0`, `partial_output_pct = 0`,
`resume_task_id = null`. No resume task is created.

---

### Scenario 3 — Partial output below 20%, no resume created

**Setup**: Task reaped with only 400 chars of partial output. Expected output for an `impl` task is
estimated at ~5000 chars. `partial_output_pct` = 8%.

**Action**:
```bash
curl -s https://api.coherencycoin.com/api/agent/tasks/<task_id>/reap-diagnosis | jq '{partial_output_pct, resume_task_id}'
```

**Expected**:
```json
{ "partial_output_pct": 8, "resume_task_id": null }
```
No resume task exists. Standard reaper retry (if retry count < limit) is created instead.

---

### Scenario 4 — Same idea times out 3 times: human attention flagged

**Setup**: Idea `idea_abc` has had the `impl` task time out twice already (context shows
`reap_history.timeout_count = 2`). A third task for the same idea+type times out.

**Action**:
```bash
# After third reap:
curl -s "https://api.coherencycoin.com/api/agent/reap-history?idea_id=idea_abc" | jq '.'
```

**Expected**:
```json
{
  "items": [
    {
      "idea_id": "idea_abc",
      "timeout_count": 3,
      "needs_human_attention": true,
      "last_error_class": "executor_crash"
    }
  ],
  "total": 1
}
```
No new automated retry task was created. Telegram alert was sent with `needs_human_attention`.

**Edge case**: Calling the same endpoint with `?needs_attention=false` returns the item;
`?needs_attention=true` also returns it. `?idea_id=nonexistent` returns `{ "items": [], "total": 0 }`.

---

### Scenario 5 — Reap diagnosis 404 for never-reaped task

**Setup**: A task in `completed` status that was never reaped.

**Action**:
```bash
curl -s -o /dev/null -w "%{http_code}" \
  https://api.coherencycoin.com/api/agent/tasks/<completed_task_id>/reap-diagnosis
```

**Expected**: HTTP `404`.
Response body:
```json
{ "detail": "Task task_<id> has no reap diagnosis (never reaped or not found)" }
```

---

### Scenario 6 — Idempotent double-reap

**Setup**: Two reaper processes run simultaneously (e.g. after a runner restart during the reap
window). Both see the same task as stale.

**Action**: First PATCH to `timed_out` succeeds. Second PATCH sees task is no longer `running`.

**Expected**: Only one `reap_diagnosis` is written. Only one resume task (if any) is created.
Second reaper logs `REAPER: task <id> already reaped, skipping`. No duplicate resume tasks.

## Concurrency Behavior

- **Reaper runs**: Serialized per task by checking current status before PATCH. If status ≠ `running`
  when the reaper tries to mark `timed_out`, it skips the task.
- **Extension vs. reap race**: Extension is written as a PATCH to `context.reap_extensions`. If two
  reapers race, both may try to extend. The second sees `reap_extensions = 1` already set and the task
  still `running`, so it evaluates the extended deadline and may skip again.
- **Resume task creation**: Protected by a short-circuit: if `resume_task_id` already exists in
  `reap_diagnosis`, skip creating another.

## Verification

```bash
# Run all smart reap tests
cd api && python -m pytest tests/test_smart_reap.py -v

# Run regression suite to ensure existing task pipeline still works
cd api && python -m pytest tests/test_agent.py tests/test_agent_runner_registry_api.py -x -q

# Check reap history endpoint (production)
curl -s https://api.coherencycoin.com/api/agent/reap-history | jq '.total'

# Confirm reap-diagnosis 404 for a non-reaped task
curl -s -o /dev/null -w "%{http_code}" \
  https://api.coherencycoin.com/api/agent/tasks/nonexistent_task/reap-diagnosis
# Expected: 404
```

## Out of Scope

- Automatic provider switching based on crash class (covered by existing retry logic in `agent_execution_retry.py`)
- UI surface for reap history (future: can read from `/api/agent/reap-history`)
- Process-level PID probing on the runner's host OS (requires SSH access; out of scope for this API-first design)
- Reap history persistence beyond what is derivable from task records (no new DB table)

## Risks and Assumptions

- **Risk**: Runner heartbeat interval varies; the 270 s liveness window may be too short for slow
  environments. Mitigation: make the liveness window configurable via env var
  `REAP_RUNNER_LIVENESS_SECONDS` with default 270.
- **Assumption**: Log files exist at a predictable path (`api/logs/tasks/task_<id>.log`). If the log
  directory is on a different host or volume, partial capture will return 0 chars (safe fallback).
- **Risk**: Estimating `partial_output_pct` without knowing expected output length is heuristic.
  Mitigation: use task-type-specific baselines (spec: 3000 chars, impl: 5000, test: 4000, review:
  2000). If `target_state` exists, use its length as a proxy for expected output.
- **Assumption**: `idea_id` is always present in task context for ideas worth resuming. Tasks without
  `idea_id` skip reap history tracking and resume task creation.
- **Risk**: Creating resume tasks consumes runner capacity. Mitigation: resume tasks count against
  the retry budget (`retry_count`) and are not created when `needs_human_attention` is true.

## Known Gaps and Follow-up Tasks

- **Gap**: Reap history endpoint scans all timed_out tasks (O(n)). For large deployments, add an
  index on `context->>'idea_id'` in PostgreSQL.  Follow-up: `task_spec_gap_169a`
- **Gap**: Telegram notification for `needs_human_attention` reuses `format_task_alert`; a dedicated
  "human required" alert format would be clearer. Follow-up: `task_spec_gap_169b`
- **Gap**: No automatic un-flagging when an idea eventually succeeds after human intervention.
  Follow-up: `task_spec_gap_169c` — clear `needs_human_attention` on `completed` status.

## Failure/Retry Reflection

- **Failure mode**: Runner registry is unavailable (DB down). Blind spot: liveness check throws an
  exception and the reaper doesn't know whether the runner is alive. Next action: treat registry
  unavailability as "assume alive" and defer reap by one cycle (safe default, prevents data loss).
- **Failure mode**: Log file is locked by the still-running provider process. Blind spot: read
  attempt fails silently. Next action: use non-blocking read with `errors="replace"` and a file
  size limit; partial data is better than no data.
- **Failure mode**: Resume task's direction exceeds the 5000-char limit. Blind spot: partial output
  appended verbatim may be very long. Next action: truncate partial output to 3000 chars in the
  resume direction, append "[truncated]" marker.

## Decision Gates

- **Liveness window (270 s)**: Can be tuned at deploy time. No code change required if the default
  is acceptable. If VPS heartbeat interval is > 90 s, increase accordingly.
- **Extension cap (2 extensions)**: Conservative; if slow providers regularly need more time, raise
  to 3. Requires changing constant `REAP_MAX_EXTENSIONS = 2` in `smart_reap_service.py`.
- **Human attention threshold (3 timeouts)**: Driven by operator tolerance. Can be changed via env
  var `REAP_HUMAN_ATTENTION_THRESHOLD` with default `3`.
