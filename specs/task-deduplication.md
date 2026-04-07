---
idea_id: pipeline-reliability
status: done
source:
  - file: api/app/services/agent_service_active_task.py
    symbols: [find_active_task_by_fingerprint(), find_active_task_by_session_key()]
requirements:
  - "R1 — Create `check_idea_phase_history(idea_id, phase)` in new `api/app/services/task_dedup_service.py`."
  - "R2 — In `local_runner.py:_seed_task_from_open_idea()`, after fetching `idea_tasks_payload`:"
  - "R3 — In `pipeline_advance_service.py:maybe_advance()`, before creating next-phase task:"
  - "R4 — In `pipeline_advance_service.py:_maybe_auto_retry()`, before creating retry task:"
  - "R5 — In `idea_to_task_bridge.py`, replace `determine_task_type()` to use live task history"
  - "R6 — Extend `GET /api/ideas/{id}/tasks` response to include `phase_summary` dict keyed"
  - "R7 — When skip-ahead occurs (R3), propagate context from the completed task of the"
  - "R8 — For auto-advance and auto-retry tasks, set `context.task_fingerprint` to"
---

> **Parent idea**: [pipeline-reliability](../ideas/pipeline-reliability.md)
> **Source**: [`api/app/services/agent_service_active_task.py`](../api/app/services/agent_service_active_task.py)

# Spec: Task Deduplication — Never Create Duplicate Tasks for the Same Idea+Phase

## Purpose

The pipeline creates far too many tasks per idea. With 799 spec tasks across 147 ideas
(5.4 per idea average), most ideas have redundant work burning ~52% of pipeline capacity.

**Root causes:**

1. **Seeder in `local_runner.py`** checks for active (pending/running) tasks but not completed
   ones. A successfully completed spec task makes the idea eligible for a *second* spec task on
   the next poll.

2. **Pipeline advance hook** (`pipeline_advance_service.py:maybe_advance()`) checks for
   pending/running tasks of the next phase but not completed tasks. If `impl` already completed,
   it can create a duplicate `impl` task when a redundant spec completes.

3. **Idea-to-task bridge** (`scripts/idea_to_task_bridge.py`) relies on `idea.stage` which may
   be stale, and has no task-history check at all.

4. **No per-phase retry cap.** A failing task can be retried indefinitely within the global retry
   budget, spawning many tasks for the same idea+phase.

This spec closes all four gaps with a unified dedup gate and a hard cap of 2 retries per
idea+phase combination.

## Current State

### Task creation entry points

| Entry Point | File | Dedup Today |
|---|---|---|
| Seeder | `api/scripts/local_runner.py` `_seed_task_from_open_idea()` | Checks active only, not completed |
| Auto-advance | `api/app/services/pipeline_advance_service.py:maybe_advance()` | Checks pending/running only |
| Auto-retry | `api/app/services/pipeline_advance_service.py:_maybe_auto_retry()` | Checks pending/running only |
| Bridge | `scripts/idea_to_task_bridge.py:run_cycle()` | None — only global capacity |
| Manual API | `POST /api/agent/tasks` | Fingerprint-only (optional) |

### Phase sequence (canonical)

`spec → impl → test → code-review → deploy → verify-production`

### Task statuses

`pending`, `running`, `completed`, `failed`, `timed_out`, `needs_decision`

## Requirements

- [ ] R1 — Create `check_idea_phase_history(idea_id, phase)` in new `api/app/services/task_dedup_service.py`.
      Returns `IdeaPhaseHistory` dataclass with `completed_count`, `failed_count`, `active_count`,
      `total_count`, `latest_completed_task`, `should_skip` (True if completed >= 1),
      `retry_budget_left` (max(0, MAX_RETRIES_PER_PHASE - failed_count)).
      Constants: `MAX_RETRIES_PER_PHASE = 2`, `MAX_TASKS_PER_PHASE = 3`.

- [ ] R2 — In `local_runner.py:_seed_task_from_open_idea()`, after fetching `idea_tasks_payload`:
      (a) Call `_phase_fully_completed()` — if True, skip with log `SEED: skipping <phase> for <idea_id> — already completed`.
      (b) Count total tasks for phase; if >= MAX_TASKS_PER_PHASE, skip with log `SEED: capping <phase> for <idea_id> (<N> tasks exist, limit <MAX>)` and add to `_SEEDER_SKIP_CACHE`.
      (c) Replace hardcoded `>= 10` stuck threshold with `>= MAX_TASKS_PER_PHASE`.
      (d) Define `MAX_TASKS_PER_PHASE = 3` as module-level constant above `_seed_task_from_open_idea`.
      (e) Completed-phase guard must execute before cap guard in code order.
      (f) Ideas with zero tasks must still receive a task normally.

- [ ] R3 — In `pipeline_advance_service.py:maybe_advance()`, before creating next-phase task:
      call `check_idea_phase_history(idea_id, next_phase)`. If `should_skip`, skip and check
      the phase after that (skip-ahead). If `active_count > 0`, return None. If
      `retry_budget_left <= 0` and `completed_count == 0`, escalate to `needs-decision`.

- [ ] R4 — In `pipeline_advance_service.py:_maybe_auto_retry()`, before creating retry task:
      call `check_idea_phase_history(idea_id, current_phase)`. If `should_skip`, do not retry.
      If `retry_budget_left <= 0`, escalate to `needs-decision`. If `active_count > 0`, skip.

- [ ] R5 — In `idea_to_task_bridge.py`, replace `determine_task_type()` to use live task history
      from `GET /api/ideas/{id}/tasks` instead of stale `idea.stage`. Walk the phase sequence
      forward, skipping completed phases. If all phases complete, skip idea entirely. If chosen
      phase has MAX_RETRIES_PER_PHASE+ failures with no completion, skip (needs human).

- [ ] R6 — Extend `GET /api/ideas/{id}/tasks` response to include `phase_summary` dict keyed
      by phase name, each value containing `completed`, `failed`, `active`, `should_skip`,
      `retry_budget_left`. Add `PhaseSummary` model to `api/app/models/idea.py`.

- [ ] R7 — When skip-ahead occurs (R3), propagate context from the completed task of the
      skipped phase: `impl_branch`, spec file path, `pr_number`. Create `build_skip_context()`
      in `task_dedup_service.py`.

- [ ] R8 — For auto-advance and auto-retry tasks, set `context.task_fingerprint` to
      `{idea_id}:{phase}:auto` to prevent concurrent duplicate creation via the existing
      fingerprint dedup in `agent_service_crud.py`.

## Files to Create/Modify

- `api/app/services/task_dedup_service.py` — **Create**: `check_idea_phase_history()`, `build_skip_context()`, `MAX_RETRIES_PER_PHASE`, `MAX_TASKS_PER_PHASE` constants
- `api/scripts/local_runner.py` — Modify: add completed-phase guard + cap guard to `_seed_task_from_open_idea()` (R2)
- `api/app/services/pipeline_advance_service.py` — Modify: gate `maybe_advance()` (R3) and `_maybe_auto_retry()` (R4) with dedup checks; add deterministic fingerprint (R8)
- `api/app/services/agent_service_list.py` — Modify: add `phase_summary` to `list_tasks_for_idea()` (R6)
- `api/app/models/idea.py` — Modify: add `PhaseSummary` model, update `IdeaTasksResponse` (R6)
- `scripts/idea_to_task_bridge.py` — Modify: add dedup gate, fix `determine_task_type()` to use task history (R5)
- `api/tests/test_task_dedup_service.py` — **Create**: unit tests for dedup gate and context propagation

## Data Model Changes

### New Pydantic model in `api/app/models/idea.py`

```python
class PhaseSummary(BaseModel):
    """Per-phase task summary for dedup visibility."""
    completed: int = 0
    failed: int = 0
    active: int = 0
    should_skip: bool = False
    retry_budget_left: int = 2
```

No database schema changes — dedup operates on the existing task store by querying task lists
filtered by `context.idea_id` and `task_type`.

## Acceptance Tests

### Scenario 1: Completed spec phase is not re-seeded

**Setup**: Idea `test-dedup-A` exists with one `spec` task in `completed` status, no other tasks.

**Action**:
```bash
curl -s "$API/api/ideas/test-dedup-A/tasks" | jq '.phase_summary.spec'
```
**Expected**: `{"completed": 1, "failed": 0, "active": 0, "should_skip": true, "retry_budget_left": 2}`

**Action**: Trigger one seeder poll selecting this idea.
**Expected**:
- No new spec task created.
- Log: `SEED: skipping spec for test-dedup-A — already completed`
- `GET $API/api/ideas/test-dedup-A/tasks` returns total = 1 (unchanged).

**Edge**: If the completed task is later patched to `failed`, the idea becomes eligible for
a new spec task on the next poll.

### Scenario 2: Auto-advance skips already-completed phase

**Setup**: Idea `test-dedup-B` has completed `spec` + completed `impl` tasks. A redundant
spec task completes.

**Action**:
```bash
curl -s -X PATCH "$API/api/agent/tasks/$TASK_ID" \
  -H "Content-Type: application/json" \
  -d '{"status": "completed", "output": "Spec written at specs/test-dedup-B.md"}'
```

**Expected**: The advance hook skips `impl` (already completed) and creates a `test` task
instead. Log: `AUTO_ADVANCE skip — impl already completed for test-dedup-B, advancing to test`

The new test task's context includes `impl_branch` from the completed impl task.

**Edge**: If all downstream phases are completed, advance does nothing and logs:
`AUTO_ADVANCE skip — all phases completed for test-dedup-B`

### Scenario 3: Retry budget exhausted after 2 failures

**Setup**: Idea `test-dedup-C` has 2 failed `impl` tasks (no completed impl, no active impl).

**Action**: A third `impl` task fails:
```bash
curl -s -X PATCH "$API/api/agent/tasks/$TASK_ID" \
  -H "Content-Type: application/json" \
  -d '{"status": "failed", "output": "Build error", "error_category": "execution_error"}'
```

**Expected**: Auto-retry does NOT create a 4th impl task. Log:
`AUTO_RETRY exhausted — impl for test-dedup-C has 2 prior failures, max retries reached`

**Verify**:
```bash
curl -s "$API/api/ideas/test-dedup-C/tasks" | jq '.phase_summary.impl'
```
Returns: `{"completed": 0, "failed": 3, "active": 0, "should_skip": false, "retry_budget_left": 0}`

**Edge**: `timed_out` status counts toward the retry budget equally with `failed`.

### Scenario 4: Per-phase cap prevents unbounded task creation

**Setup**: Idea `test-dedup-D` has 3 spec tasks (2 failed + 1 pending), none completed.

**Action**: Trigger seeder poll selecting this idea.

**Expected**:
- No new task created.
- Log: `SEED: capping spec for test-dedup-D (3 tasks exist, limit 3)`
- Idea added to `_SEEDER_SKIP_CACHE`.

**Verify**:
```bash
curl -s "$API/api/ideas/test-dedup-D/tasks" | jq '.groups[] | select(.task_type=="spec") | .count'
```
Returns: `3` (not 4+).

**Edge**: An idea with only 2 spec tasks (all failed) is still eligible for a 3rd task.

### Scenario 5: Bridge uses task history instead of stale stage

**Setup**: Idea `test-dedup-E` has `stage=none` (stale) but a completed spec task exists.

**Action**:
```bash
python scripts/idea_to_task_bridge.py --dry-run 2>&1 | grep -i "test-dedup-E"
```

**Expected**: If selected, bridge creates an `impl` task (not a second `spec`). Log includes:
`spec already completed for test-dedup-E, advancing to impl`

**Edge**: If both `spec` and `impl` are completed, bridge skips to `test`. If all phases done,
bridge skips this idea entirely.

### Scenario 6: Context propagation on skip-ahead (create-read cycle)

**Setup**: Idea `test-dedup-F` has:
- Completed `spec` task with `context.spec_file = "specs/test-dedup-F.md"`
- Completed `impl` task with `context.impl_branch = "feat/test-dedup-F"`

A new spec task completes, triggering advance.

**Action**: Advance hook skips `impl` and creates a `test` task.

**Verify**:
```bash
curl -s "$API/api/agent/tasks/$NEW_TEST_TASK_ID" | jq '.context'
```

**Expected**:
```json
{
  "idea_id": "test-dedup-F",
  "impl_branch": "feat/test-dedup-F",
  "auto_advance_source": "spec → test (skipped impl)"
}
```

**Edge**: If the completed impl task has no `impl_branch` in context, the test task is still
created but the log includes a warning: `"impl_branch missing from completed impl for test-dedup-F"`.

### Scenario 7: Error handling — non-existent idea

**Action**:
```bash
curl -s "$API/api/ideas/nonexistent-idea/tasks"
```

**Expected**: HTTP 404 with error message.

Internal call to `check_idea_phase_history("nonexistent-idea", "spec")` returns
`IdeaPhaseHistory` with all zeros — does not raise exception (fail-open for unknown ideas).

## Verification

Before marking this spec implemented, run:

```bash
# 1. Syntax check — new service module parses
python3 -c "import ast; ast.parse(open('api/app/services/task_dedup_service.py').read()); print('OK')"

# 2. Constants exist
grep -n "MAX_TASKS_PER_PHASE\|MAX_RETRIES_PER_PHASE" api/app/services/task_dedup_service.py

# 3. Dedup gate called in advance hook
grep -n "check_idea_phase_history" api/app/services/pipeline_advance_service.py

# 4. Dedup gate called in seeder
grep -n "MAX_TASKS_PER_PHASE\|_phase_fully_completed" api/scripts/local_runner.py

# 5. Phase summary in API response
curl -s "$API/api/ideas/test-dedup-A/tasks" | jq '.phase_summary'

# 6. Existing tests pass
cd api && python -m pytest tests/test_task_dedup_service.py -v
```

## Concurrency Behavior

- The dedup gate reads from `GET /api/ideas/{id}/tasks` (point-in-time snapshot). Two workers
  may both pass the check simultaneously.
- **R8 (fingerprint)** closes this gap: `task_fingerprint = "{idea_id}:{phase}:auto"` causes
  the second concurrent `create_task()` to return the existing task instead of creating a
  duplicate.
- `MAX_TASKS_PER_PHASE = 3` provides an additional backstop.
- True distributed locking is out of scope (follow-up).

## Out of Scope

- Distributed advisory locking (`pg_try_advisory_lock`) to prevent true simultaneous double-claim
  across parallel workers — follow-up task.
- Purging or archiving existing duplicate tasks already in the database — separate ops task.
- Tuning `MAX_TASKS_PER_PHASE` dynamically per idea type or work type — future enhancement.
- Changes to `_phase_fully_completed` logic — the function is correct as written.
- Any web UI changes (dashboard progress bars, etc.).
- Cross-idea semantic deduplication (detecting two ideas describing the same feature).

## Risks and Assumptions

### Risks

1. **False cap on retried phases**: If a phase genuinely needs 3+ attempts (e.g., sequential
   provider failures), the cap blocks it. Mitigation: `MAX_TASKS_PER_PHASE = 3` is a session-
   scoped backstop; restarting the runner resets `_SEEDER_SKIP_CACHE`. The retry budget of 2
   can be raised with a one-line constant change.

2. **Hollow completion trap**: A phase with a completed task whose output is hollow passes
   `should_skip = True`, preventing re-seeding even though advance never fired. Mitigation:
   this is correct behavior — the existing advance-hook output validation catches hollow
   completions separately. If a hollow task is stuck, operators can PATCH it to `failed` to
   re-enable seeding.

3. **Performance**: `check_idea_phase_history()` scans all tasks for an idea. Current task
   count (<1000) makes this negligible. At 10k+ tasks, add an index on `(idea_id, task_type)`.

4. **Skip-ahead context loss**: If the completed task for a skipped phase has incomplete
   context (e.g., missing `impl_branch`), downstream tasks may fail. Mitigation: log warning
   and proceed — the downstream task will fail at its own validation and escalate normally.

### Assumptions

- The task store is queryable by `idea_id` via `list_tasks_for_idea()`.
- `MAX_RETRIES_PER_PHASE = 2` and `MAX_TASKS_PER_PHASE = 3` are reasonable defaults.
- All task creation flows go through the five entry points listed above.
- Phase sequence is stable and will not change during implementation.
- The seeder runs as a single process per environment.

## Known Gaps and Follow-up Tasks

- **Distributed advisory lock**: `pg_try_advisory_lock` or equivalent to prevent the race window under concurrent workers. Eliminates the residual 4-task edge case.
- **Historical cleanup script**: `scripts/dedup_tasks.py` to collapse existing 799 duplicate spec tasks. This spec only prevents future duplication.
- **Dashboard integration**: `phase_summary` is API-only. A follow-up adds per-idea progress bars to the web UI.
- **Per-phase cap map**: Some phases (e.g., `merge`, `deploy`) are one-shot and could have `MAX_TASKS_PER_PHASE = 1`. Deferred pending evidence.
- **Metrics**: Add `seeder_phase_capped_total` and `advance_phase_skipped_total` counters for pipeline observability.

## Measuring Success

| Metric | Before (baseline) | Target | How to measure |
|---|---|---|---|
| Tasks per idea (mean) | 5.4 | < 2.0 | `GET /api/ideas` → sum tasks / count ideas |
| Duplicate spec tasks (new) | ~4/day | 0 | Count spec tasks per idea where completed > 1 |
| Retry-exhausted escalations | 0 (infinite retries) | > 0 visible | Count ideas with needs-decision + retry-exhausted |
| Phase skip-aheads | 0 | > 0 | Log grep: `"already completed.*advancing"` |

Track weekly for 2 weeks post-deploy. If tasks/idea drops below 2.0, feature is working.
