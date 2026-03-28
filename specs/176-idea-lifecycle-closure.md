# Spec 176: Idea Lifecycle Closure — System Must Recognize When an Idea Is Done

## Purpose

The pipeline wastes compute on ideas that are already implemented. Two bugs cause this:

1. **Stage mismatch in the bridge**: `idea_to_task_bridge.py::determine_task_type()` compares
   against wrong string literals (`"spec"` vs the actual enum value `"specced"`,
   `"implementation"` vs `"implementing"`). Ideas at stage `reviewing` or `complete` fall through
   to the `else: return "spec"` branch — generating a new spec task for an idea that is already
   in review or done. This is the root cause of the 6+ spec tasks on homepage readability.

2. **No closure trigger**: When a `review` task completes, `auto_advance_for_task("review")`
   advances the idea to stage `reviewing` — but nothing advances it from `reviewing` to `complete`,
   and nothing sets `manifestation_status=validated`. The idea lingers as `partial` indefinitely,
   staying in the open pool and attracting more tasks.

This spec fixes both bugs and adds a lifecycle-closure guard so implemented ideas exit the
task-generation pool permanently.

---

## Requirements

### R1 — Fix stage string comparisons in the bridge

`determine_task_type()` must use the exact enum values defined in `IdeaStage`:

| Bridge currently checks | Correct value |
|---|---|
| `"spec"`, `"specification"` | `"specced"` |
| `"test"`, `"testing"` | `"testing"` |
| `"implementation"`, `"impl"` | `"implementing"` |
| *(missing)* `"reviewing"`, `"complete"` | these ideas are **closed** — return `None` |

When `determine_task_type()` returns `None`, `run_cycle()` must skip the idea and log
`"Idea '%s' is already at stage %s — skipping"`.

### R2 — Task history guard before task creation

Before creating any task, the bridge must call `GET /api/ideas/{idea_id}/tasks` and inspect
existing task groups. If a task of the same type (spec/test/impl/review) already exists with
`status` in `{running, pending, completed, done}`, the bridge must skip this idea and move to
the next candidate. Log `"Skipping '%s' — already has %s task in state %s"`.

### R3 — Auto-advance from reviewing → complete

When `auto_advance_for_task(idea_id, "review")` is called (a review task completed), if the
idea is currently at stage `reviewing`, advance it one more step to `complete`. The existing
`_sync_manifestation_status` already maps `complete → validated`. This closes the loop.

Alternative path: `POST /api/ideas/{idea_id}/advance` can be called explicitly after a review
task completes. The spec requires both to work.

### R4 — Phase advance hook sets manifestation_status=validated

When an idea reaches stage `complete` via any path (manual advance, `auto_advance_for_task`,
`set_idea_stage`), `_sync_manifestation_status` must emit the `validated` status. This is
already partially implemented (`COMPLETE → VALIDATED` is in `_STAGE_TO_MANIFESTATION`) but is
only triggered if `complete` is reached. R3 ensures it is reached.

### R5 — Closed ideas excluded from the open pool

`get_open_ideas()` in `idea_to_task_bridge.py` currently excludes `manifestation_status=validated`.
After R3/R4, ideas that complete the full lifecycle will be automatically excluded. No additional
filter change is needed — this is a verification requirement to confirm the existing filter works.

### R6 — Lifecycle status endpoint

A new read-only endpoint exposes the closure state of any idea:

```
GET /api/ideas/{idea_id}/lifecycle
```

Response includes: `stage`, `manifestation_status`, `is_closed`, `task_summary` (count per type,
latest status), and `closure_blockers` (list of what prevents the idea from being marked complete,
or empty list if already closed).

### R7 — Observability: warn on duplicate task creation attempts

When the bridge skips an idea due to R2, it must increment a counter in the API's friction event
log: `POST /api/friction` with `source=idea_bridge`, `event=duplicate_task_skipped`,
`idea_id=<id>`. This makes repeated near-misses visible in the friction dashboard.

---

## Research Inputs

- `2026-03-28` — `scripts/idea_to_task_bridge.py` — source of R1 bug; stage string literals
  do not match `IdeaStage` enum values; reviewed lines 97-119, 180-208
- `2026-03-28` — `api/app/services/idea_service.py` lines 1360–1469 — `_STAGE_TO_MANIFESTATION`,
  `_TASK_TYPE_TARGET_STAGE`, `auto_advance_for_task`, `_sync_manifestation_status`
- `2026-03-28` — `api/app/models/idea.py` lines 13-35 — `IdeaStage` enum, `IDEA_STAGE_ORDER`
- `2026-03-28` — `api/app/routers/ideas.py` lines 303-310 — `GET /api/ideas/{id}/tasks` endpoint
- Real production data: `stale-task-reaper` idea has 0 tasks despite being `manifestation_status=validated`
  — confirms ideas can be validated without task history, so task history check is needed per-phase
- Known incident: homepage readability idea received 6+ spec tasks (mentioned in task description)

---

## Task Card

```yaml
goal: Fix idea lifecycle closure so implemented ideas exit the task pipeline permanently
files_allowed:
  - scripts/idea_to_task_bridge.py
  - api/app/services/idea_service.py
  - api/app/routers/ideas.py
  - api/app/models/idea.py
  - api/tests/test_idea_lifecycle_closure.py
done_when:
  - determine_task_type() returns None for stage in {reviewing, complete}
  - bridge skips ideas that already have a task of the same type (any status)
  - auto_advance_for_task("review") advances reviewing → complete, triggering validated status
  - GET /api/ideas/{idea_id}/lifecycle returns is_closed=true for completed ideas
  - pytest api/tests/test_idea_lifecycle_closure.py passes with all 5 test cases
commands:
  - cd api && python -m pytest tests/test_idea_lifecycle_closure.py -v
  - python scripts/idea_to_task_bridge.py --dry-run
  - curl -s https://api.coherencycoin.com/api/ideas/stale-task-reaper/lifecycle
constraints:
  - Do not modify existing tests to force passing
  - Do not touch unrelated routers or services
  - Bridge changes must be backward-compatible (--dry-run still works)
  - No schema migrations required — lifecycle endpoint reads from existing fields
```

---

## API Contract

### `GET /api/ideas/{idea_id}/lifecycle`

**Request**
- `idea_id`: string (path) — idea identifier

**Response 200**
```json
{
  "idea_id": "homepage-readability",
  "stage": "complete",
  "manifestation_status": "validated",
  "is_closed": true,
  "task_summary": {
    "spec": {"count": 1, "latest_status": "done"},
    "test": {"count": 1, "latest_status": "done"},
    "impl": {"count": 1, "latest_status": "done"},
    "review": {"count": 1, "latest_status": "done"}
  },
  "closure_blockers": []
}
```

**Response 200 (open idea)**
```json
{
  "idea_id": "some-open-idea",
  "stage": "specced",
  "manifestation_status": "partial",
  "is_closed": false,
  "task_summary": {
    "spec": {"count": 1, "latest_status": "done"},
    "test": {"count": 0, "latest_status": null},
    "impl": {"count": 0, "latest_status": null},
    "review": {"count": 0, "latest_status": null}
  },
  "closure_blockers": ["test phase not started", "impl phase not started", "review phase not started"]
}
```

**Response 404**
```json
{ "detail": "Idea not found" }
```

---

## Data Model

No new tables or fields required. The lifecycle endpoint is derived from existing:
- `Idea.stage` (IdeaStage enum)
- `Idea.manifestation_status` (ManifestationStatus enum)
- Task groups from `agent_service.list_tasks_for_idea(idea_id)` (IdeaTasksResponse)

`is_closed` is computed as: `stage == IdeaStage.COMPLETE or manifestation_status == ManifestationStatus.VALIDATED`

`closure_blockers` is a derived list: for each phase in `[spec, test, impl, review]`, if no task
of that type exists with status `done` or `completed`, append `"{phase} phase not started"`.

---

## Files to Create/Modify

- `scripts/idea_to_task_bridge.py` — Fix stage string comparisons (R1); add task history guard (R2); add friction event on skip (R7)
- `api/app/services/idea_service.py` — Fix `auto_advance_for_task("review")` to advance one more step to `complete` (R3)
- `api/app/routers/ideas.py` — Add `GET /api/ideas/{idea_id}/lifecycle` endpoint (R6)
- `api/tests/test_idea_lifecycle_closure.py` — New test file with 5 test cases (see Verification Scenarios)

---

## Verification

### Verification Scenarios

#### Scenario 1 — Bridge skips reviewing/complete ideas (R1 fix)

**Setup**: An idea exists with `stage="reviewing"` (or `"complete"`).

**Action**:
```bash
python scripts/idea_to_task_bridge.py --dry-run 2>&1 | grep "skipping\|reviewing\|complete"
```

**Expected result**: Log line `"Idea '<name>' is already at stage reviewing — skipping"`. No task
creation log (`CREATED` or `would create`) for any idea at stage `reviewing` or `complete`.

**Edge case**: An idea at stage `implementing` should still get an `impl` task, not be skipped.

---

#### Scenario 2 — Task history guard prevents duplicate tasks (R2)

**Setup**: Idea `homepage-readability` exists with a `spec` task already in the system (any status).

**Action**:
```bash
curl -s https://api.coherencycoin.com/api/ideas/homepage-readability/tasks
# Confirms spec task exists
python scripts/idea_to_task_bridge.py --dry-run 2>&1
```

**Expected result**: Log line `"Skipping 'homepage-readability' — already has spec task in state done"`.
No new spec task is queued. The bridge moves on to a different idea.

**Edge case**: If the spec task is in state `failed`, a new spec task MAY be created (retry). The
guard only blocks on `pending`, `running`, `completed`, `done`.

---

#### Scenario 3 — auto_advance_for_task("review") closes the idea (R3 + R4)

**Setup**: Idea `test-closure-idea` is at stage `reviewing`, `manifestation_status=partial`.

**Action** (simulated via API):
```bash
# Set up test idea at reviewing stage
curl -s -X POST https://api.coherencycoin.com/api/ideas/test-closure-idea/advance \
  -H "X-API-Key: $API_KEY"
# Then trigger auto-advance as if review task completed
curl -s https://api.coherencycoin.com/api/ideas/test-closure-idea
```

**Expected result**: After calling auto_advance from reviewing, the idea shows:
```json
{"stage": "complete", "manifestation_status": "validated"}
```

**Edge case**: Calling advance again on a `complete` idea returns HTTP 409 `"Idea is already complete"`.

---

#### Scenario 4 — Lifecycle endpoint returns correct closure state (R6)

**Setup**: Idea `stale-task-reaper` exists with `manifestation_status=validated`.

**Action**:
```bash
curl -s https://api.coherencycoin.com/api/ideas/stale-task-reaper/lifecycle
```

**Expected result**:
```json
{
  "idea_id": "stale-task-reaper",
  "is_closed": true,
  "manifestation_status": "validated",
  "closure_blockers": []
}
```

**Edge case**: Non-existent idea returns HTTP 404:
```bash
curl -s https://api.coherencycoin.com/api/ideas/nonexistent-xyz-99999/lifecycle
# Expected: {"detail": "Idea not found"}, HTTP 404
```

---

#### Scenario 5 — Full lifecycle: idea goes from none → complete, exits open pool (end-to-end)

**Setup**: Fresh idea `e2e-closure-test` created at stage `none`.

**Actions** (sequential):
```bash
API="https://api.coherencycoin.com"
# Verify it appears in open ideas
curl -s "$API/api/ideas?limit=200" | grep e2e-closure-test

# Advance through all stages
curl -s -X POST "$API/api/ideas/e2e-closure-test/advance" -H "X-API-Key: $API_KEY"  # → specced
curl -s -X POST "$API/api/ideas/e2e-closure-test/advance" -H "X-API-Key: $API_KEY"  # → implementing
curl -s -X POST "$API/api/ideas/e2e-closure-test/advance" -H "X-API-Key: $API_KEY"  # → testing
curl -s -X POST "$API/api/ideas/e2e-closure-test/advance" -H "X-API-Key: $API_KEY"  # → reviewing
curl -s -X POST "$API/api/ideas/e2e-closure-test/advance" -H "X-API-Key: $API_KEY"  # → complete

# Verify lifecycle shows closed
curl -s "$API/api/ideas/e2e-closure-test/lifecycle"

# Verify it no longer appears in open ideas pool
curl -s "$API/api/ideas?limit=200&only_unvalidated=true" | grep e2e-closure-test
```

**Expected results**:
1. After 5 advances: `{"stage": "complete", "manifestation_status": "validated"}`
2. Lifecycle: `{"is_closed": true, "closure_blockers": []}`
3. `only_unvalidated=true` query does NOT include `e2e-closure-test`

**Edge case**: Advancing a `complete` idea returns HTTP 409, does not regress the stage.

---

## Acceptance Tests

- `api/tests/test_idea_lifecycle_closure.py::test_determine_task_type_uses_correct_stage_values`
- `api/tests/test_idea_lifecycle_closure.py::test_determine_task_type_skips_closed_stages`
- `api/tests/test_idea_lifecycle_closure.py::test_bridge_skips_idea_with_existing_task`
- `api/tests/test_idea_lifecycle_closure.py::test_auto_advance_review_closes_idea`
- `api/tests/test_idea_lifecycle_closure.py::test_lifecycle_endpoint_returns_closure_state`

---

## Concurrency Behavior

- **Read operations** (`GET /lifecycle`): Safe for concurrent access; reads from in-memory idea
  store + task list.
- **Write operations** (`auto_advance_for_task`): Existing single-file write semantics apply.
  Concurrent advance calls are idempotent: the guard `if current_index >= target_index: return`
  prevents regression.
- **Bridge cycle**: The bridge runs single-threaded per cycle. No distributed locking required.

---

## Out of Scope

- Reprocessing historical ideas to retroactively apply lifecycle closure (can be done manually
  via `POST /api/ideas/{id}/stage` with `stage=complete`)
- UI changes to display lifecycle closure on the ideas dashboard
- Automatic re-opening of a closed idea if a regression is detected
- Tracking which specific task caused closure (lineage attribution — see spec-175)

---

## Risks and Assumptions

- **Risk**: Some ideas have been manually set to `validated` without going through `complete` stage. Mitigation: R5 verification — the `only_unvalidated` filter already excludes `validated`, so these ideas are safe.
- **Risk**: `idea_to_task_bridge.py` is not the only code path that creates tasks. Mitigation: R2 guard is in the bridge only; if other orchestrators create tasks, they need separate guards (follow-up task).
- **Risk**: `auto_advance_for_task` is called from multiple code paths. Mitigation: Check callers; ensure "review" completion always results in `complete` stage.
- **Risk**: Idea at `reviewing` stage could be incorrectly skipped if review task failed. Mitigation: R2 guard only blocks on `pending`, `running`, `completed`, `done`; `failed` status allows retry.
- **Assumption**: Stage enum values are stable. If they change, R1 fix uses direct enum imports, not string literals, so it will fail loudly at import time rather than silently.

---

## Known Gaps and Follow-up Tasks

- **Gap**: Other task-creation code paths (if any) outside `idea_to_task_bridge.py` are not
  guarded by R2. Follow-up: audit all `POST /api/agent/tasks` call sites.
- **Gap**: The `determine_task_type()` lifecycle (`spec → test → impl → review`) does not match
  `_TASK_TYPE_TARGET_STAGE` ordering (`spec → implementing → testing → reviewing`). These need
  to be reconciled in implementation — use `IdeaStage` as the canonical source of ordering.
- **Gap**: No webhook or event emitted when an idea closes. Downstream consumers cannot subscribe
  to closure events. Follow-up: add `idea.closed` event to the friction/activity feed.
- **Follow-up task**: After R3 is implemented, run a one-time backfill to advance all ideas
  currently at `reviewing` stage with all 4 task types completed to `complete`.

---

## Failure/Retry Reflection

| Failure mode | Blind spot | Next action |
|---|---|---|
| Bridge still creates duplicate tasks after R2 | Task status naming is inconsistent (e.g., `done` vs `completed`) | Check `IdeaTaskGroup.status` enum; normalize in guard logic |
| Auto-advance from reviewing → complete breaks existing tests | Tests assert idea stays at `reviewing` after review task | Update test assertions; reviewing is no longer a terminal state |
| Lifecycle endpoint returns 500 on ideas with no tasks | `task_summary` building code doesn't handle missing groups | Add default `{"count": 0, "latest_status": null}` for missing phases |

---

## Decision Gates

- **Architecture decision**: Should `determine_task_type()` be moved into the API (server-side)
  to make it consistent for all clients, or remain in the bridge script? Current spec leaves it
  in the script for minimal change radius. Escalate to `needs-decision` if multiple clients need
  this logic.
- **Review required**: The backfill of existing `reviewing`-stage ideas to `complete` — this is
  a data mutation and should be reviewed before execution.
