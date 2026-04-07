---
idea_id: idea-realization-engine
status: done
source:
  - file: api/app/routers/ideas.py
    symbols: [set_idea_stage(), advance_idea_stage()]
  - file: api/app/services/idea_service.py
    symbols: [advance_idea_stage(), set_idea_stage(), auto_advance_for_task(), compute_progress_dashboard()]
  - file: api/app/models/idea.py
    symbols: [IdeaStage, IDEA_STAGE_ORDER, ProgressDashboard, StageBucket]
requirements:
  - "R1: Add an `IdeaStage` enum with ordered values: `none`, `specced`, `implementing`, `testing`, `reviewing`, `complete`."
  - "R2: Add a `stage` field (default `none`) to the `Idea` model and a `stage` field to `IdeaCreate` / `IdeaUpdate`."
  - "R3: New `POST /api/ideas/{idea_id}/advance` endpoint transitions an idea to the next stage. Returns 200 with updated ide"
  - "R4: Stage transitions must be sequential — an idea can only advance to the immediately next stage (none→specced→implemen"
  - "R5: New `POST /api/ideas/{idea_id}/stage` endpoint allows setting an explicit stage (for corrections/admin override). Ac"
  - "R6: Auto-advance logic: when a pipeline task of type `spec` completes for an idea, advance from `none` to `specced`; whe"
  - "R7: New `GET /api/ideas/progress` endpoint returns a `ProgressDashboard` response with per-stage counts, a list of ideas"
  - "R8: The `IdeaWithScore` response includes the new `stage` field so existing consumers see it without extra calls."
  - "R9: Stage transitions update the `manifestation_status` field for backward compatibility: `specced`/`implementing` → `pa"
done_when:
  - "IdeaStage enum exists with six ordered values"
  - "POST /api/ideas/{idea_id}/advance transitions to next stage and returns updated idea"
  - "POST /api/ideas/{idea_id}/stage sets an explicit stage"
  - "GET /api/ideas/progress returns per-stage counts and completion percentage"
  - "Auto-advance function exists and is callable from task-completion hooks"
  - "All tests in api/tests/test_idea_lifecycle.py pass"
test: "cd api && python -m pytest tests/test_idea_lifecycle.py -x -v"
constraints:
  - "Do not modify existing endpoint response schemas (additive stage field only)"
  - "Do not break backward compatibility with manifestation_status consumers"
  - "Coherence scores remain 0.0–1.0"
  - "Stage ordering is immutable at the enum level"
---

> **Parent idea**: [idea-realization-engine](../ideas/idea-realization-engine.md)
> **Source**: [`api/app/routers/ideas.py`](../api/app/routers/ideas.py) | [`api/app/services/idea_service.py`](../api/app/services/idea_service.py) | [`api/app/models/idea.py`](../api/app/models/idea.py)

# Idea Lifecycle Management

## Purpose

Ideas in the portfolio currently have a coarse `manifestation_status` (none/partial/validated) that cannot express where an idea actually sits in the development pipeline. Operators and the automation layer have no way to see whether an idea has a spec written, is being implemented, or is in review — forcing manual inspection of git history and task logs. This spec adds explicit lifecycle stages to ideas, auto-advancement rules triggered by task completion, and a progress dashboard endpoint so the cockpit UI can render a Kanban-style view of the entire portfolio pipeline.

## Requirements

- [ ] R1: Add an `IdeaStage` enum with ordered values: `none`, `specced`, `implementing`, `testing`, `reviewing`, `complete`.
- [ ] R2: Add a `stage` field (default `none`) to the `Idea` model and a `stage` field to `IdeaCreate` / `IdeaUpdate`.
- [ ] R3: New `POST /api/ideas/{idea_id}/advance` endpoint transitions an idea to the next stage. Returns 200 with updated idea on success, 409 if already `complete`, 404 if idea not found.
- [ ] R4: Stage transitions must be sequential — an idea can only advance to the immediately next stage (none→specced→implementing→testing→reviewing→complete). Skipping stages returns 422.
- [ ] R5: New `POST /api/ideas/{idea_id}/stage` endpoint allows setting an explicit stage (for corrections/admin override). Accepts `{"stage": "implementing"}`. Returns 200 on success, 422 on invalid stage value.
- [ ] R6: Auto-advance logic: when a pipeline task of type `spec` completes for an idea, advance from `none` to `specced`; when `impl` completes, advance to `implementing`→`testing`; when `test` completes, advance to `testing`→`reviewing`; when `review` completes, advance to `reviewing`→`complete`. Auto-advance is best-effort — if the idea is already at or past the target stage, it is a no-op.
- [ ] R7: New `GET /api/ideas/progress` endpoint returns a `ProgressDashboard` response with per-stage counts, a list of ideas per stage, and overall completion percentage.
- [ ] R8: The `IdeaWithScore` response includes the new `stage` field so existing consumers see it without extra calls.
- [ ] R9: Stage transitions update the `manifestation_status` field for backward compatibility: `specced`/`implementing` → `partial`, `complete` → `validated`. Other stages leave `manifestation_status` unchanged.

## Research Inputs

- `2026-03-06` - [Spec 053: Ideas Prioritization](specs/ideas-prioritization.md) - defines the existing idea model and portfolio API being extended
- `2026-03-06` - [Spec 126: Portfolio Governance Effectiveness](specs/portfolio-governance-effectiveness.md) - governance health metrics that will benefit from stage data for more granular throughput tracking
- `2026-03-15` - [Spec 005: Project Manager Pipeline](specs/project-manager-pipeline.md) - pipeline task types (spec, impl, test, review) that drive auto-advance

## Task Card

```yaml
goal: Add idea lifecycle stages with sequential transitions, auto-advance on task completion, and a progress dashboard endpoint.
files_allowed:
  - api/app/models/idea.py
  - api/app/routers/ideas.py
  - api/app/services/idea_service.py
  - api/tests/test_idea_lifecycle.py
done_when:
  - IdeaStage enum exists with six ordered values
  - POST /api/ideas/{idea_id}/advance transitions to next stage and returns updated idea
  - POST /api/ideas/{idea_id}/stage sets an explicit stage
  - GET /api/ideas/progress returns per-stage counts and completion percentage
  - Auto-advance function exists and is callable from task-completion hooks
  - All tests in api/tests/test_idea_lifecycle.py pass
commands:
  - cd api && python -m pytest tests/test_idea_lifecycle.py -x -v
constraints:
  - Do not modify existing endpoint response schemas (additive stage field only)
  - Do not break backward compatibility with manifestation_status consumers
  - Coherence scores remain 0.0–1.0
  - Stage ordering is immutable at the enum level
```

## API Contract

### `POST /api/ideas/{idea_id}/advance`

**Request**
- `idea_id`: string (path) — the idea to advance

**Response 200**
```json
{
  "id": "my-idea",
  "name": "My Idea",
  "stage": "specced",
  "manifestation_status": "partial",
  "...": "remaining IdeaWithScore fields"
}
```

**Response 404**
```json
{ "detail": "Idea not found" }
```

**Response 409**
```json
{ "detail": "Idea is already complete" }
```

**Response 422**
```json
{ "detail": "Cannot skip stages; current stage is 'none', next allowed is 'specced'" }
```

### `POST /api/ideas/{idea_id}/stage`

**Request**
- `idea_id`: string (path)
- Body: `{"stage": "implementing"}`

**Response 200**
```json
{
  "id": "my-idea",
  "stage": "implementing",
  "...": "remaining IdeaWithScore fields"
}
```

**Response 404**
```json
{ "detail": "Idea not found" }
```

**Response 422**
```json
{ "detail": "Invalid stage value" }
```

### `GET /api/ideas/progress`

**Request**
- No required parameters.

**Response 200**
```json
{
  "total_ideas": 10,
  "completion_pct": 0.2,
  "by_stage": {
    "none": { "count": 3, "idea_ids": ["a", "b", "c"] },
    "specced": { "count": 2, "idea_ids": ["d", "e"] },
    "implementing": { "count": 2, "idea_ids": ["f", "g"] },
    "testing": { "count": 1, "idea_ids": ["h"] },
    "reviewing": { "count": 0, "idea_ids": [] },
    "complete": { "count": 2, "idea_ids": ["i", "j"] }
  },
  "snapshot_at": "2026-03-21T12:00:00Z"
}
```

## Data Model

```yaml
IdeaStage:
  type: enum
  values: [none, specced, implementing, testing, reviewing, complete]

Idea:
  added_properties:
    stage: { type: IdeaStage, default: "none" }

IdeaUpdate:
  added_properties:
    stage: { type: IdeaStage, optional: true }

IdeaCreate:
  added_properties:
    stage: { type: IdeaStage, optional: true }

StageSetRequest:
  properties:
    stage: { type: IdeaStage, required: true }

StageBucket:
  properties:
    count: { type: int }
    idea_ids: { type: list[str] }

ProgressDashboard:
  properties:
    total_ideas: { type: int }
    completion_pct: { type: float, description: "Fraction of ideas at stage 'complete'" }
    by_stage: { type: dict[str, StageBucket] }
    snapshot_at: { type: datetime, description: "ISO 8601 UTC timestamp" }
```

## Files to Create/Modify

- `api/app/models/idea.py` — add `IdeaStage` enum, `StageSetRequest`, `StageBucket`, `ProgressDashboard` models; add `stage` field to `Idea`, `IdeaCreate`, `IdeaUpdate`
- `api/app/services/idea_service.py` — add `advance_idea_stage()`, `set_idea_stage()`, `auto_advance_for_task()`, `compute_progress_dashboard()` functions
- `api/app/routers/ideas.py` — add `POST /advance`, `POST /stage`, `GET /progress` routes
- `api/tests/test_idea_lifecycle.py` — new test file with acceptance tests

## Acceptance Tests

- `api/tests/test_idea_lifecycle.py::test_advance_none_to_specced`
- `api/tests/test_idea_lifecycle.py::test_advance_through_all_stages`
- `api/tests/test_idea_lifecycle.py::test_advance_complete_returns_409`
- `api/tests/test_idea_lifecycle.py::test_skip_stage_returns_422`
- `api/tests/test_idea_lifecycle.py::test_set_stage_explicit`
- `api/tests/test_idea_lifecycle.py::test_set_invalid_stage_returns_422`
- `api/tests/test_idea_lifecycle.py::test_auto_advance_on_spec_task`
- `api/tests/test_idea_lifecycle.py::test_auto_advance_noop_if_already_past`
- `api/tests/test_idea_lifecycle.py::test_progress_dashboard_counts`
- `api/tests/test_idea_lifecycle.py::test_progress_completion_pct`
- `api/tests/test_idea_lifecycle.py::test_stage_syncs_manifestation_status`
- `api/tests/test_idea_lifecycle.py::test_new_idea_defaults_to_none_stage`

## Concurrency Behavior

- **Read operations**: `GET /progress` is safe for concurrent access; computed from read-only scan.
- **Write operations**: `POST /advance` and `POST /stage` use last-write-wins. Two concurrent advances on the same idea may both succeed if they arrive before the first write is persisted — acceptable for MVP.
- **Recommendation**: Clients should not assume atomic read-modify-write without explicit ETag support.

## Verification

```bash
cd api && python -m pytest tests/test_idea_lifecycle.py -x -v
curl -s http://localhost:8000/api/ideas/progress | python -m json.tool
curl -s -X POST http://localhost:8000/api/ideas/my-idea/advance | python -m json.tool
```

## Out of Scope

- Stage-transition history/audit log (future spec)
- Notifications or webhooks on stage change
- UI rendering of the progress dashboard (separate cockpit spec)
- Modifying the free_energy_score or selection algorithm based on stage
- Deadline or SLA enforcement per stage

## Risks and Assumptions

- **Assumption**: The pipeline task completion hook has access to the idea ID associated with each task. If not, auto-advance (R6) will require a task→idea mapping to be added to the task model (additive change, low risk).
- **Risk**: With the current small portfolio (~8 ideas), the progress dashboard may not provide meaningful signal. Mitigation: the dashboard is still useful for seeing which stages are empty and which are bottlenecked.
- **Assumption**: Existing consumers of `manifestation_status` will not break from the additive `stage` field. The backward-compatibility sync in R9 ensures `manifestation_status` continues to reflect coarse state.
- **Risk**: Auto-advance logic could create confusing state if tasks complete out of order (e.g., test task completes before impl task). Mitigation: auto-advance is best-effort and will not regress an idea to an earlier stage.

## Known Gaps and Follow-up Tasks

- Follow-up task: `task_stage_transition_audit_log` — persist a log of stage transitions with timestamps and trigger source for debugging and governance reporting.
- Follow-up task: `task_cockpit_kanban_view` — render the progress dashboard as a Kanban board in the cockpit UI (spec 052).
- Follow-up task: `task_governance_health_stage_metrics` — update spec 126 governance health to include stage-based throughput metrics (time-in-stage, stage velocity).

## Failure/Retry Reflection

- Failure mode: Auto-advance called with an idea ID that doesn't exist in the portfolio
- Blind spot: Task-to-idea mapping may be stale or missing
- Next action: Log a warning and skip auto-advance rather than failing the task completion

- Failure mode: Race condition where two advances fire simultaneously
- Blind spot: No locking on stage transitions
- Next action: Last-write-wins is acceptable for MVP; add optimistic locking if stage conflicts become a real issue

## Decision Gates

- If task→idea mapping does not exist in the current task model, the auto-advance integration (R6) requires a schema addition that should be approved before implementation.
