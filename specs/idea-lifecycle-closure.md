---
idea_id: idea-realization-engine
status: partial
source:
  - file: api/app/services/idea_service.py
    symbols: [_sync_manifestation_status()]
  - file: api/app/models/idea.py
    symbols: [IdeaStage.COMPLETE, IdeaLifecycle]
requirements:
  - Fix stage string comparisons in idea_to_task_bridge to match IdeaStage enum
  - Task history guard prevents duplicate tasks for same idea and phase
  - Review completion advances idea from reviewing to complete
  - Closed ideas (complete + validated) exit task-generation pool
  - GET /api/ideas/{idea_id}/lifecycle returns closure state and blockers
  - Emit friction event when bridge skips a closed idea
done_when:
  - determine_task_type uses correct IdeaStage enum values
  - Bridge skips ideas with existing task in pending/running/completed/done
  - pytest api/tests/test_idea_lifecycle_closure.py passes
---

> **Parent idea**: [idea-realization-engine](../ideas/idea-realization-engine.md)
> **Source**: [`api/app/services/idea_service.py`](../api/app/services/idea_service.py) | [`api/app/models/idea.py`](../api/app/models/idea.py)

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

## Files to Create/Modify

- `scripts/idea_to_task_bridge.py` — Fix stage string comparisons (R1); add task history guard (R2); add friction event on skip (R7)
- `api/app/services/idea_service.py` — Fix `auto_advance_for_task("review")` to advance one more step to `complete` (R3)
- `api/app/routers/ideas.py` — Add `GET /api/ideas/{idea_id}/lifecycle` endpoint (R6)
- `api/tests/test_idea_lifecycle_closure.py` — New test file with 5 test cases (see Verification Scenarios)

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

## Acceptance Tests

- `api/tests/test_idea_lifecycle_closure.py::test_determine_task_type_uses_correct_stage_values`
- `api/tests/test_idea_lifecycle_closure.py::test_determine_task_type_skips_closed_stages`
- `api/tests/test_idea_lifecycle_closure.py::test_bridge_skips_idea_with_existing_task`
- `api/tests/test_idea_lifecycle_closure.py::test_auto_advance_review_closes_idea`
- `api/tests/test_idea_lifecycle_closure.py::test_lifecycle_endpoint_returns_closure_state`

## Out of Scope

- Reprocessing historical ideas to retroactively apply lifecycle closure (can be done manually
  via `POST /api/ideas/{id}/stage` with `stage=complete`)
- UI changes to display lifecycle closure on the ideas dashboard
- Automatic re-opening of a closed idea if a regression is detected
- Tracking which specific task caused closure (lineage attribution — see spec-175)

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

## Decision Gates

- **Architecture decision**: Should `determine_task_type()` be moved into the API (server-side)
  to make it consistent for all clients, or remain in the bridge script? Current spec leaves it
  in the script for minimal change radius. Escalate to `needs-decision` if multiple clients need
  this logic.
- **Review required**: The backfill of existing `reviewing`-stage ideas to `complete` — this is
  a data mutation and should be reviewed before execution.
