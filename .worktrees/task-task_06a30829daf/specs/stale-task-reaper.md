# Spec: Stale-Task Reaper

## Purpose

Phantom "running" tasks that never finish block pipeline capacity and degrade the overall task
success rate (currently ~52%). Without an active cleanup mechanism, a single hung worker can
hold an idea slot indefinitely — preventing retries, starving the seeder, and masking real
failure rates in metrics. The stale-task reaper exists to detect tasks that have exceeded a
reasonable execution ceiling, preserve whatever partial work they produced, and immediately
re-queue a retry so the pipeline stays moving.

## What Exists Today

The reaper is fully operational as of 2026-03-28. The key code lives entirely in
`api/scripts/local_runner.py` and `api/app/services/smart_reap_service.py`.

### Entry points in `api/scripts/local_runner.py`

| Function | Line (approx.) | Role |
|---|---|---|
| `_reap_stale_tasks(max_age_minutes=15)` | ~3383 | Public dispatcher; tries smart path, falls back to legacy |
| `_smart_reap_stale_tasks()` | body of above | Imports `smart_reap_service.smart_reap_task`; applies liveness checks |
| `_legacy_reap_stale_tasks(max_age_minutes=15)` | ~3502 | Fallback reaper; no liveness checks, blind timeout |
| `_recover_in_flight_tasks()` | ~5393 | On startup, re-counts tasks already claimed by this node |

### Periodic scheduling

`_reap_stale_tasks` is called from the main poll loop at `reap_interval = 600` seconds
(every 10 minutes), guarded by the `last_reap` timer (~line 5799). The threshold passed to
the function is `max_age_minutes=15` — a fixed constant, not derived from provider timeout.

### STARTUP_REAP block (~line 5692)

On startup, the runner queries `/api/agent/tasks?status=running` and marks any task whose
`claimed_by` matches its own `WORKER_ID` prefix as `timed_out` with the reason
`"Reaped on startup: runner restarted while task was running."`. This handles the case where
the runner crashed mid-task.

### Reap outcome on a task

When a task is reaped it receives:

- `status`: `"timed_out"`
- `error_category`: `"stale_task_reaped"`
- `error_summary`: diagnosis string truncated to 500 characters
- `output`: partial output or a plain reap reason string
- `context.smart_reap_diagnosis`: structured diagnosis block (smart path only)

If `idea_id` is present and `retry_count < _MAX_RETRIES_PER_IDEA_PHASE` (currently 2), a
retry task is posted to `POST /api/agent/tasks` with:

- `context.seed_source`: `"reaper_retry"`
- `context.retry_count`: incremented
- `context.retried_from`: original task ID
- `context.failed_provider`: provider that timed out
- `context.resume_patch_path`: path to the saved `.patch` file (smart path only)

If retry limit is exhausted, a friction event is posted to `POST /api/friction/events` with
`block_type: "repeated_timeout"` and `severity: "high"`.

### Smart reap service (`api/app/services/smart_reap_service.py`)

Implements Spec 169 diagnostics:

- `is_runner_alive()` — checks runner's `last_seen_at` against `REAP_RUNNER_LIVENESS_SECONDS`
  (default 270 s) before reaping
- Up to `REAP_MAX_EXTENSIONS = 2` timeout extensions for live runners
- `REAP_HUMAN_ATTENTION_THRESHOLD = 3` repeated failures flags `needs_human_attention`
- Partial resume when output completion estimate >= `PARTIAL_RESUME_THRESHOLD_PCT = 20 %`

### API-side routes (`api/app/routers/agent_smart_reap_routes.py`)

- `POST /api/agent/smart-reap/run` — trigger a reap cycle on demand
- `GET /api/agent/smart-reap/preview` — dry-run preview of which tasks would be reaped

---

## Gaps Still Open

These are known deficiencies in the current implementation that this spec tracks for closure.

### Gap 1 — Silent fallback on import failure

`_reap_stale_tasks` catches `ImportError` from `smart_reap_service` and falls back to
`_legacy_reap_stale_tasks` with only a `log.warning`. The legacy path omits liveness checks
and resume-patch logic entirely. There is no observable signal to operators that the smart
path is unavailable. A failed import (e.g., missing `failed_task_diagnostics_service`
dependency) will silently degrade reap quality for the entire session.

**Gap owner**: Implementation  
**Follow-up task**: `stale-task-reaper-gap-1` — surface import failure as a runner health
metric and expose it through the `/api/health` endpoint.

### Gap 2 — No session-level reap count exposed to API

`_reap_stale_tasks` returns an `int` count but the count is only logged locally. No metric is
pushed to `push_measurements()`, no API endpoint exposes "tasks reaped this session", and the
federation dashboard has no visibility into reaper activity.

**Follow-up task**: `stale-task-reaper-gap-2` — add `tasks_reaped_total` counter to the
runner's measurement payload.

### Gap 3 — STARTUP_REAP does not cover other nodes' orphaned tasks

The startup reap block filters strictly to tasks whose `claimed_by` contains the current
node's `WORKER_ID` prefix. Tasks left running by a different node that has been dead for more
than 30 minutes are not touched at startup — they must wait for the next periodic reap cycle
(up to 10 minutes). In a multi-node setup with a sudden node loss, this creates a ~10-minute
gap where dead tasks hold capacity across the cluster.

**Follow-up task**: `stale-task-reaper-gap-3` — extend STARTUP_REAP to also reap tasks from
any runner whose `last_seen_at` is older than 30 minutes and whose status is still `running`.

### Gap 4 — No observable API signal when reaper fires

The reap cycle runs entirely inside the runner process. When it fires there is no API event,
no webhook, and no polling endpoint that a monitoring dashboard can subscribe to. The only
record is a `log.info` line in the runner's stdout. This makes it impossible to build
automated alerting on reap spikes without log scraping.

**Follow-up task**: `stale-task-reaper-gap-4` — post a `POST /api/friction/events` record
(or a dedicated `POST /api/agent/reap-events` record) each time the reaper fires, capturing
`reaped_count`, `extended_count`, and `skipped_live_count` for that cycle.

---

## Requirements

- [ ] Tasks running beyond `max_age_minutes=15` (fixed threshold, not provider-derived) are
      detected by `_reap_stale_tasks` every 600 seconds.
- [ ] Smart path (`smart_reap_service.smart_reap_task`) is attempted first; legacy path is
      the fallback only if the import fails.
- [ ] Reaped tasks receive `status=timed_out`, `error_category="stale_task_reaped"`, and a
      truncated `error_summary` (max 500 chars).
- [ ] A retry task is created for any reaped task that has `idea_id` and
      `retry_count < _MAX_RETRIES_PER_IDEA_PHASE`.
- [ ] The retry task carries `seed_source="reaper_retry"`, incremented `retry_count`, and
      `retried_from` pointing to the original task ID.
- [ ] Smart path saves a `.patch` file to `api/task_patches/task_{id}.patch` when a worktree
      diff exists, and stores `resume_patch_path` in the retry task's context.
- [ ] Startup reap marks own stale tasks (`claimed_by` matches current node) as `timed_out`
      before workers begin claiming new tasks.
- [ ] Already-timed-out tasks are never re-reaped (reaper queries `status=running` only).
- [ ] After `_MAX_RETRIES_PER_IDEA_PHASE` exhausted, a friction event with
      `block_type="repeated_timeout"` and `severity="high"` is posted.
- [ ] The smart path checks runner liveness before reaping; live runners receive up to 2
      timeout extensions before being force-reaped.

## Research Inputs (Required)

- `2026-03-28` - `api/scripts/local_runner.py` lines 3383–3576, 5393–5427, 5692–5709, 5799–5801 — current reaper implementation
- `2026-03-28` - `api/app/services/smart_reap_service.py` — Spec 169 smart reap service
- `2026-03-28` - `api/app/routers/agent_smart_reap_routes.py` — API trigger routes for smart reap
- `2026-03-28` - `api/app/models/agent.py` — `error_category`, `error_summary` fields on task models

## Task Card (Required)

```yaml
goal: close Gap 1 (surface smart_reap import failure), Gap 2 (expose reap count to API),
      Gap 3 (extend startup reap to cover dead-node orphans), Gap 4 (emit observable event
      per reap cycle)
files_allowed:
  - api/scripts/local_runner.py
  - api/app/services/smart_reap_service.py
  - api/app/routers/agent_smart_reap_routes.py
  - api/app/models/agent.py
  - api/app/services/agent_task_store_service.py
done_when:
  - smart_reap import failure is recorded in runner health metric, visible at /api/health
  - tasks_reaped_total is included in push_measurements() payload
  - startup reap covers tasks from any runner with last_seen_at > 30 min old
  - a friction event (or dedicated reap event) is posted each time the reap cycle fires
  - all five verification scenarios below pass against production API
commands:
  - pytest -q api/tests/ -k reaper
  - curl -s https://api.coherencycoin.com/api/agent/smart-reap/preview | jq .
constraints:
  - do not change the 15-minute age threshold without a separate spec approval
  - do not change _MAX_RETRIES_PER_IDEA_PHASE without a separate spec approval
  - legacy fallback path must remain; do not remove it
```

## API Contract (if applicable)

### Existing: `POST /api/agent/smart-reap/run`

No changes required. Already returns a summary of reaped/extended/skipped counts.

### Existing: `GET /api/agent/smart-reap/preview`

No changes required.

### Gap 4 target: friction event emitted per reap cycle

Each time `_reap_stale_tasks` fires and the count is >= 1, the reaper posts:

```json
{
  "stage": "reaper",
  "block_type": "reap_cycle",
  "severity": "info",
  "owner": "reaper",
  "notes": "Reaped 3 tasks; extended 1; skipped 0 (live runner). smart_path=true"
}
```

This uses the existing `POST /api/friction/events` endpoint and requires no schema change.

## Data Model (if applicable)

No new models. Existing fields used by the reaper:

```yaml
AgentTask (api/app/models/agent.py):
  status:         { type: string, enum: [running, timed_out, pending, ...] }
  error_summary:  { type: string, max_length: 500 }
  error_category: { type: string, example: "stale_task_reaped" }
  context:
    seed_source:        { type: string, example: "reaper_retry" }
    retry_count:        { type: integer }
    retried_from:       { type: string }
    failed_provider:    { type: string }
    resume_patch_path:  { type: string }
    reap_extensions:    { type: integer }
    reaped_on_startup:  { type: boolean }
    smart_reap_diagnosis: { type: object }
```

## Files to Create/Modify

- `api/scripts/local_runner.py` — `_reap_stale_tasks`, `_legacy_reap_stale_tasks`,
  `_recover_in_flight_tasks`, STARTUP_REAP block, main poll loop (Gap 1, 2, 3, 4)
- `api/app/services/smart_reap_service.py` — no changes required unless Gap 1 surface logic
  moves here
- `api/app/routers/agent_smart_reap_routes.py` — no changes required for gaps
- `api/app/services/agent_task_store_service.py` — verify `error_category` is persisted on
  PATCH (no schema change expected)

## Acceptance Tests

- `api/tests/test_stale_task_reaper.py::test_reap_marks_timed_out`
- `api/tests/test_stale_task_reaper.py::test_reap_creates_retry_with_seed_source`
- `api/tests/test_stale_task_reaper.py::test_reap_sets_error_category`
- `api/tests/test_stale_task_reaper.py::test_startup_reap_own_tasks`
- `api/tests/test_stale_task_reaper.py::test_no_double_reap_on_timed_out`
- `api/tests/test_smart_reap_service.py::test_is_runner_alive_returns_false_for_stale_runner`
- `api/tests/test_smart_reap_service.py::test_extension_granted_for_live_runner`

## Concurrency Behavior

- The reaper runs in the main poll thread (not a worker thread), so there is no concurrent
  reap. Two runners on separate nodes can race to reap the same task; the last PATCH wins.
  This is safe because both writes set `status=timed_out` — the outcome is idempotent.
- Worker threads that hold `_active_idea_ids` for a task being reaped externally will
  encounter a 409 or stale state on their next PATCH; the worker's error handler will log and
  continue without crashing.

## Verification

Five concrete scenarios, executable against production.

### Scenario 1 — Reaped task receives `timed_out` status

```bash
# 1. Create a task and immediately claim it (simulate stuck runner)
TASK=$(curl -s -X POST https://api.coherencycoin.com/api/agent/tasks \
  -H 'Content-Type: application/json' \
  -d '{"direction":"reaper test","task_type":"spec","context":{"idea_id":"test-idea-1"}}' \
  | jq -r .id)

curl -s -X PATCH "https://api.coherencycoin.com/api/agent/tasks/$TASK" \
  -H 'Content-Type: application/json' \
  -d '{"status":"running","claimed_by":"test-worker-001","worker_id":"test-worker-001"}'

# 2. Wait for reaper cycle (up to 10 min in production) OR trigger it manually
curl -s -X POST "https://api.coherencycoin.com/api/agent/smart-reap/run" \
  -H 'Content-Type: application/json' \
  -d '{"max_age_minutes":0}'

# 3. Verify status
curl -s "https://api.coherencycoin.com/api/agent/tasks/$TASK" | jq '{status, error_category}'
# Expected: {"status": "timed_out", "error_category": "stale_task_reaped"}
```

### Scenario 2 — Reaped task spawns a retry with resume context

```bash
# Continue from Scenario 1 — $TASK is now timed_out
# Look for a retry task with seed_source=reaper_retry and retried_from=$TASK
curl -s "https://api.coherencycoin.com/api/agent/tasks?status=pending&limit=50" \
  | jq --arg orig "$TASK" \
    '[.tasks[] | select(.context.retried_from == $orig and .context.seed_source == "reaper_retry")]'
# Expected: array with at least one entry; retry_count == 1
```

### Scenario 3 — Reaped task has `error_category == "stale_task_reaped"`

```bash
curl -s "https://api.coherencycoin.com/api/agent/tasks/$TASK" \
  | jq '{error_category, error_summary}'
# Expected:
# {
#   "error_category": "stale_task_reaped",
#   "error_summary": "<non-null string, max 500 chars>"
# }
```

### Scenario 4 — Startup reap marks own node's stale tasks

```bash
# Simulate: create a task claimed by a known worker prefix, restart the runner
# In production, inspect runner logs for the STARTUP_REAP line:
#   STARTUP_REAP: marked N own stale tasks as timed_out

# Then verify via API that the task has reaped_on_startup in context:
curl -s "https://api.coherencycoin.com/api/agent/tasks/$TASK" \
  | jq '.context.reaped_on_startup'
# Expected: true
```

### Scenario 5 — Reaper does not double-reap already-timed-out tasks

```bash
# $TASK is already timed_out from Scenario 1.
# Trigger reaper again.
curl -s -X POST "https://api.coherencycoin.com/api/agent/smart-reap/run" \
  -H 'Content-Type: application/json' \
  -d '{"max_age_minutes":0}'

# Reaper queries status=running only — timed_out tasks are excluded from the candidate list.
# Verify the task's updated_at has not changed since Scenario 1's reap:
curl -s "https://api.coherencycoin.com/api/agent/tasks/$TASK" | jq .updated_at
# Expected: timestamp identical to the one captured after Scenario 1
```

## Out of Scope

- Changing the `max_age_minutes=15` threshold (requires its own spec with provider-timeout data)
- Changing `_MAX_RETRIES_PER_IDEA_PHASE` from 2
- Any UI surface for reaper events (dashboard work is a separate spec)
- Reaper coverage of `pending` tasks (only `running` tasks are candidates)
- Automatic patch application on retry (resume-patch-path is advisory; the retry agent decides
  whether to apply it)

## Risks and Assumptions

- **Risk**: Two runner nodes race on the same stale task. Both write `timed_out`; both may
  create a retry. Mitigation: the second retry will be detected as a duplicate by the seeder's
  `active_idea_ids` check and dropped without executing.
- **Risk**: `smart_reap_service` import fails silently in production, degrading to legacy path
  permanently. Mitigation: Gap 1 closure will surface this in `/api/health`.
- **Assumption**: The API's `PATCH /api/agent/tasks/{id}` endpoint accepts `error_category`
  and `error_summary` fields without requiring a schema migration. Verified against
  `api/app/models/agent.py` — both fields are optional on the update model.
- **Assumption**: `POST /api/agent/smart-reap/run` with `max_age_minutes=0` reaps any
  currently-running task regardless of age, making it usable for integration testing.
- **Assumption**: Tasks created without `idea_id` in context are reaped but never retried
  (current behavior is correct — retry logic is gated on `idea_id` presence).

## Known Gaps and Follow-up Tasks

- `stale-task-reaper-gap-1`: Surface `smart_reap_service` import failure as a runner health
  metric visible at `GET /api/health`. Priority: high.
- `stale-task-reaper-gap-2`: Add `tasks_reaped_total` counter to `push_measurements()` payload
  so the federation dashboard can track reap rate over time. Priority: medium.
- `stale-task-reaper-gap-3`: Extend STARTUP_REAP to also cover tasks claimed by runners with
  `last_seen_at` older than 30 minutes (cross-node orphan recovery). Priority: medium.
- `stale-task-reaper-gap-4`: Emit a `POST /api/friction/events` record each time the reap
  cycle fires, capturing `reaped_count`, `extended_count`, and `skipped_live_count`. Priority:
  low (observability improvement only).

## Failure/Retry Reflection

- **Failure mode**: Reaper fires but `PATCH /api/agent/tasks/{id}` returns 404 (task deleted
  between query and patch).
  - **Blind spot**: The reaper does not handle 404 explicitly; it treats any falsy API
    response as a skip.
  - **Next action**: Add explicit 404 check in `_legacy_reap_stale_tasks` and log at
    `info` level rather than silently skipping.

- **Failure mode**: Smart reap creates a retry but the retry inherits a broken `context` dict
  that causes the next worker to crash immediately.
  - **Blind spot**: `retry_ctx` is a shallow dict copy; nested mutable values are shared.
  - **Next action**: Use `copy.deepcopy(ctx)` when building `retry_ctx`.

- **Failure mode**: Reaper runs every 10 minutes but `max_age_minutes=15`, creating a 5-minute
  window where tasks beyond the threshold are not yet reaped.
  - **Blind spot**: Acknowledged design gap — not a bug, but means worst-case stuck-task
    lifetime is ~25 minutes (15 min threshold + up to 10 min until next cycle).
  - **Next action**: Document this in RUNBOOK.md; lower `reap_interval` to 300 s if pipeline
    success rate data justifies it.

## Decision Gates (if any)

- **Threshold changes** (both `max_age_minutes` and `reap_interval`) require a separate spec
  with empirical data on provider P95 execution times. Do not adjust these values as part of
  gap closure.
- **Cross-node orphan reap** (Gap 3) touches task ownership semantics and must be reviewed by
  the infrastructure owner before implementation, as it can cause races if two nodes both try
  to recover the same orphaned task.
