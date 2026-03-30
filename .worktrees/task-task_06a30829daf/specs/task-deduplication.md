# Spec: Task Deduplication in the Pipeline Seeder

## Purpose

The pipeline seeder is creating an average of 5.4 spec tasks per idea against an expected ratio
of 1. With 799 spec tasks for 147 ideas, roughly 52% of pipeline capacity is being burned on
duplicate work that produces no additional signal. Three root causes combine: the seed check only
skips ideas that have *active* (pending/running) tasks — not completed ones — so a successfully
completed spec phase immediately becomes eligible to receive a second spec task on the next poll;
when a spec task completes with hollow output and the phase does not advance, the condition above
triggers again; and two concurrent workers can both observe the same pending task as unclaimed
before either acquires the lock, resulting in a double-claim. This spec closes all three gaps by
adding a completed-phase guard, a per-phase task cap, and a cross-session stuck-detection
escalation path.

## Requirements

- [ ] R1 — Before seeding any new task for a phase, call `_phase_fully_completed` against the
      fetched `idea_tasks_payload`. If it returns `True`, skip seeding that phase for this idea
      during this poll cycle. Log at `INFO` level: `SEED: skipping <phase> for <idea_id> — already completed`.
- [ ] R2 — Introduce a module-level constant `MAX_TASKS_PER_PHASE = 3`. Before seeding, count all
      tasks for the target phase (all statuses). If the count is `>= MAX_TASKS_PER_PHASE`, skip
      seeding and log at `WARNING` level:
      `SEED: capping <phase> for <idea_id> (<N> tasks exist, limit <MAX>)`.
- [ ] R3 — Change the stuck-detection threshold from `>= 10` (session-only skip) to `>= MAX_TASKS_PER_PHASE`.
      Permanently add the idea to `_SEEDER_SKIP_CACHE` for the session when the cap is hit, so it
      is not retried within the same runner process. Log at `WARNING` level:
      `SEED: idea '<name>' phase-capped — will not retry this session`.
- [ ] R4 — The `MAX_TASKS_PER_PHASE` constant must be defined near the top of the seeder section
      (above `_seed_task_from_open_idea`) so it is easy to locate and tune without searching.
- [ ] R5 — The completed-phase guard (R1) must execute *before* the per-phase cap guard (R2) in
      code order, so a legitimately completed phase is reported as "already completed" rather than
      "capped". This distinction matters for log triage.
- [ ] R6 — No existing behaviour for ideas that have *zero* tasks for a phase may be broken:
      ideas at their first poll must still receive a spec task normally.
- [ ] R7 — The hollow-output path (task completes but phase does not advance) must be covered by
      the cap guard (R2): after `MAX_TASKS_PER_PHASE` hollow attempts the idea is session-skipped
      so a human can investigate rather than the pipeline spinning indefinitely.

## Research Inputs (Required)

- `2026-03-28` - Live task database (799 spec tasks / 147 ideas) — direct evidence of 5.4x
  multiplication confirming the bug scope
- `2026-03-28` - `api/scripts/local_runner.py` lines 1401-1413 — `_phase_fully_completed`
  implementation; confirmed it returns `True` only when `completed > 0` and no pending/running/
  failed/needs_decision tasks remain
- `2026-03-28` - `api/scripts/local_runner.py` lines 3584-3683 — `_seed_task_from_open_idea`
  implementation; confirmed the seeder does not call `_phase_fully_completed` before emitting a
  new spec task; confirmed `_SEEDER_SKIP_CACHE` is session-scoped only; confirmed stuck threshold
  is hardcoded at `>= 10` separate from any cap constant

## Task Card (Required)

```yaml
goal: >
  Prevent the seeder from creating duplicate tasks for a phase that has already completed or
  has reached the MAX_TASKS_PER_PHASE cap, eliminating the 5.4x spec multiplication.
files_allowed:
  - api/scripts/local_runner.py
done_when:
  - MAX_TASKS_PER_PHASE = 3 constant is defined above _seed_task_from_open_idea
  - _phase_fully_completed is called before seeding; matching log line emitted when True
  - per-phase task count is checked against MAX_TASKS_PER_PHASE; capping log emitted when hit
  - stuck-detection threshold changed from >= 10 to >= MAX_TASKS_PER_PHASE
  - existing ideas with zero tasks for a phase still receive a spec task on first poll
  - all five verification scenarios in this spec pass without manual intervention
commands:
  - grep -n "MAX_TASKS_PER_PHASE" api/scripts/local_runner.py
  - grep -n "_phase_fully_completed" api/scripts/local_runner.py
  - python3 -c "import ast, sys; ast.parse(open('api/scripts/local_runner.py').read()); print('syntax OK')"
constraints:
  - Do NOT modify _phase_fully_completed logic — the function is correct, only its call site is missing
  - Do NOT change task statuses or outputs
  - Do NOT alter any other seeder logic outside lines 3650-3690 and the new constant definition
  - MAX_TASKS_PER_PHASE must be a single integer constant, not computed dynamically
```

## API Contract

N/A - no API contract changes in this spec.

## Data Model

N/A - no model changes in this spec.

## Files to Create/Modify

- `api/scripts/local_runner.py` — two change sites:
  1. New constant `MAX_TASKS_PER_PHASE = 3` inserted above the `_seed_task_from_open_idea`
     function definition (near line 3583).
  2. Seeder body (~lines 3654-3684): add completed-phase guard (R1) and per-phase cap guard (R2)
     immediately after the `idea_tasks` payload is fetched and `phase_counts` is populated, before
     the `task_type` assignment block. Replace the hardcoded `>= 10` stuck threshold with
     `>= MAX_TASKS_PER_PHASE`.

## Acceptance Tests

The following scenarios are concrete and independently executable. "Poll" means one full execution
of `_seed_task_from_open_idea`. `$API` is the base URL of the running API (e.g.,
`http://localhost:8000`). `$IDEA` is the UUID of the test idea created in setup.

### Scenario 1 — Completed spec phase is not re-seeded

Setup: One idea exists with exactly one spec task in `completed` status and no other tasks.

Action: Trigger one seeder poll that selects this idea.

Expected:
- No new task is created for the idea.
- Log contains: `SEED: skipping spec for <IDEA_ID> — already completed`
- `GET $API/api/ideas/$IDEA/tasks` returns a total task count of 1 (unchanged).

Edge: If the completed task's output is later deleted (task count drops to 0), the idea must
become eligible again on the next poll (existing orphan-reset logic handles this).

### Scenario 2 — Per-phase cap prevents a fourth spec task

Setup: One idea exists with exactly 3 spec tasks in any mix of `pending`, `failed`, and
`completed` statuses, none of which satisfy `_phase_fully_completed` (e.g., 2 failed + 1 pending).

Action: Trigger one seeder poll that selects this idea.

Expected:
- No new task is created.
- Log contains: `SEED: capping spec for <IDEA_ID> (3 tasks exist, limit 3)`
- `GET $API/api/ideas/$IDEA/tasks` still shows total = 3.

Edge: An idea with only 2 spec tasks (all failed) must still be eligible to receive a third task
on the next poll.

### Scenario 3 — Hollow output does not produce unbounded retries

Setup: One idea has `MAX_TASKS_PER_PHASE` (3) spec tasks all in `completed` status but with
outputs shorter than the minimum meaningful length (hollow), so `_phase_fully_completed` returns
`False` due to business-logic output validation being absent from that function. Phase has not
advanced to `test`.

Action: Trigger one seeder poll that selects this idea.

Expected:
- The per-phase cap guard fires before a 4th task is created.
- The idea is added to `_SEEDER_SKIP_CACHE`.
- Log contains the capping warning for this idea.
- On the *next* seeder poll in the same runner process, the idea is not selected (it is in the
  skip cache).

### Scenario 4 — New ideas are unaffected (first poll creates spec task normally)

Setup: One idea exists with zero tasks (just created via `POST /api/ideas`).

Action: Trigger one seeder poll that selects this idea.

Expected:
- Exactly one spec task is created.
- `GET $API/api/ideas/$IDEA/tasks` returns total = 1, task_type = `spec`, status = `pending`.
- No capping or skipping log line is emitted for this idea.

### Scenario 5 — Task list cap is observable via the API

Setup: After running enough polls to exercise the cap, query task history for any idea that
triggered the cap guard during this session.

Action:
```
curl -s "$API/api/ideas/$IDEA/tasks" | jq '.groups[] | select(.task_type=="spec") | .count'
```

Expected:
- The returned count is `<= MAX_TASKS_PER_PHASE` (3).
- The count is never 4 or higher for any single phase across any idea in the database after
  this fix is deployed.

## Concurrency Behavior

- The completed-phase guard and cap guard both read from the `GET /api/ideas/{id}/tasks` payload
  fetched once per seeder poll. This is a single point-in-time read; two workers may both pass
  the guard if they fetch simultaneously and each sees a count of 2 against a cap of 3.
- This spec does not introduce a distributed lock. The cap of 3 is chosen to be tolerant of one
  race collision per phase: even if two workers both create a task simultaneously when count = 2,
  the resulting count of 4 is bounded and far below the previous unbounded growth.
- True atomic claim prevention (advisory locking at the DB layer) is out of scope for this spec
  and tracked as a follow-up.

## Verification

Before marking this spec implemented, run the following:

```bash
# 1. Syntax check — no regressions introduced
python3 -c "import ast, sys; ast.parse(open('api/scripts/local_runner.py').read()); print('syntax OK')"

# 2. Constant exists
grep -n "MAX_TASKS_PER_PHASE" api/scripts/local_runner.py

# 3. _phase_fully_completed is called in the seeder (must show >= 2 lines: definition + call site)
grep -n "_phase_fully_completed" api/scripts/local_runner.py

# 4. Old hardcoded threshold is gone
grep -n ">= 10" api/scripts/local_runner.py
# Expected: no matches inside _seed_task_from_open_idea (only outside if used elsewhere)
```

For Scenario 1 and Scenario 4, use the staging environment or a local runner invocation with a
test idea. Verify via API call and runner log tail (`tail -f runner.log | grep SEED`).

## Out of Scope

- Distributed advisory locking to prevent true simultaneous double-claim across two parallel
  workers — follow-up task.
- Purging or archiving existing duplicate tasks already in the database — separate ops task.
- Tuning `MAX_TASKS_PER_PHASE` dynamically per idea type or work type — future enhancement.
- Changes to `_phase_fully_completed` logic — the function is correct as written.
- Changes to the `review`, `impl`, `test`, or `merge` phase seeding paths beyond the new guards
  which apply uniformly to all phases.
- Any web UI or API surface changes.

## Risks and Assumptions

- **Risk — false cap on legitimately retried phases**: If a phase genuinely needs more than 3
  attempts (e.g., 3 sequential provider failures followed by a real attempt), the cap blocks it.
  Mitigation: the session-skip is process-scoped only; restarting the runner resets the skip
  cache, allowing manual re-enable. The cap of 3 can be raised via the constant with a single
  commit if evidence emerges that 3 is too low.
- **Risk — `_phase_fully_completed` returns `False` for hollow completions**: The function checks
  status fields but not output quality. A phase with 3 hollow-completed tasks passes the status
  check (`completed > 0`, others zero) and would return `True`, causing the seeder to skip rather
  than flag as stuck. This is actually the correct behaviour — the phase is "done" even if poorly.
  If output quality gating is needed, it is a separate spec.
- **Assumption — `idea_tasks_payload` returned by `GET /api/ideas/{id}/tasks` is the canonical
  source of truth for phase state**: If the endpoint caches stale data, guards based on it will
  make decisions on stale state. Assumed to be live as of the current codebase.
- **Assumption — the seeder runs as a single process per environment**: If multiple runner
  processes share the same API, `_SEEDER_SKIP_CACHE` is not shared between them. The cap guard
  still bounds total tasks; only the session-skip optimisation is lost. Acceptable for current
  single-runner deployment.
- **Assumption — `MAX_TASKS_PER_PHASE = 3` is sufficient headroom**: Based on observed pipeline
  behaviour where a spec phase rarely needs more than one successful attempt and failures are
  retried at most once or twice before human review is warranted.

## Known Gaps and Follow-up Tasks

- **Follow-up**: Implement a distributed advisory lock (PostgreSQL `pg_try_advisory_lock` or
  equivalent) to prevent the race window identified in the Concurrency Behavior section. This
  eliminates the residual 4-task edge case under concurrent workers.
- **Follow-up**: Write an ops script (`scripts/dedup_tasks.py`) to collapse the existing 799
  duplicate spec tasks down to the canonical one per idea. The fix only prevents future
  duplication; historical duplicates remain.
- **Follow-up**: Add a Prometheus / structured-log metric counter `seeder_phase_capped_total`
  labelled by `phase` so the ops dashboard surfaces cap events without log scraping.
- **Gap**: `MAX_TASKS_PER_PHASE` applies equally to all phases. Some phases (e.g., `merge`) are
  by nature one-shot and could warrant a cap of 1. A per-phase cap map is deferred pending
  evidence of merge duplication.

## Failure/Retry Reflection

- **Failure mode**: Runner log shows `SEED: skipping spec for X — already completed` but the
  idea never advances to `test`.
- **Blind spot**: `_phase_fully_completed` returned `True` for a task whose output did not meet
  the quality bar for phase advancement; the auto-advance hook never fired; now the seeder also
  won't re-try because it sees "completed".
- **Next action**: Inspect the completed spec task output via
  `GET /api/agent/tasks?idea_id=<X>&status=completed`. If output is hollow, manually PATCH the
  task status to `failed` and restart the runner — the seeder will see no completed tasks and
  re-seed.

- **Failure mode**: Per-phase cap fires on an idea that legitimately needs a 4th attempt after
  3 infrastructure failures.
- **Blind spot**: The cap is applied regardless of failure reason; provider outages count against
  the budget.
- **Next action**: Raise `MAX_TASKS_PER_PHASE` to 5 in a one-line commit, or manually add the
  idea to `_SEEDER_SKIP_CACHE` reset by restarting the runner.

## Decision Gates (if any)

- **Threshold value**: `MAX_TASKS_PER_PHASE = 3` was chosen based on current observed data (5.4x
  duplication). If the pipeline team believes 3 is too restrictive for any active work type,
  raise to 5 before implementation. No architectural changes required — just the constant value.
  Owner: pipeline lead. Must be decided before implementation begins.
