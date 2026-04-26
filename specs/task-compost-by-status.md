---
idea_id: pipeline-reliability
status: draft
source:
  - file: api/app/routers/agent_tasks_routes.py
    symbols: [clear_all_tasks(), router]
  - file: api/app/services/agent_service_crud.py
    symbols: [delete_task(), delete_tasks_by_filter()]
  - file: api/app/services/agent_service.py
    symbols: [clear_store()]
requirements:
  - [ ] **R1**: New endpoint `DELETE /api/agent/tasks/batch` accepts query parameters `status` (comma-separated list of valid TaskStatus values) and optional `older_than_days` (integer ≥ 0). Returns `{deleted_count: int, by_status: dict[str, int]}`.
  - [ ] **R2**: When invoked without `confirm=compost`, the endpoint returns 400 — same shape as the existing `?confirm=clear` guard on `DELETE /tasks`. Composting is a tending decision, not an accident.
  - [ ] **R3**: Endpoint refuses to delete records with status `running`, `pending`, or `needs_decision` even if those values appear in the `status` filter — those are alive (in-flight or awaiting human attention) and not compostable. Returns 400 with a list of refused statuses.
  - [ ] **R4**: For the deletes it does perform, the endpoint emits a single `task_compost_batch` activity event with `{deleted_count, by_status, status_filter, older_than_days, requested_by}` so the body has a record of the release.
  - [ ] **R5**: Existing `DELETE /api/agent/tasks?confirm=clear` (nuclear) stays unchanged — the new endpoint is additive, not a replacement.
requirements_summary:
  - "DELETE /api/agent/tasks/batch?status=failed,timed_out&confirm=compost — surgical compost"
  - "Refuses to delete running/pending/needs_decision (those are alive, not dead tissue)"
  - "Emits task_compost_batch activity event for the release record"
  - "Optional older_than_days filter for time-based release"
  - "Existing nuclear DELETE /tasks?confirm=clear unchanged"
done_when:
  - "DELETE /api/agent/tasks/batch?status=failed&confirm=compost releases all failed records and returns {deleted_count, by_status}"
  - "DELETE /api/agent/tasks/batch?status=failed,timed_out&older_than_days=7&confirm=compost releases only failed/timed_out records older than 7 days"
  - "DELETE /api/agent/tasks/batch without confirm=compost returns 400"
  - "DELETE /api/agent/tasks/batch?status=running,failed&confirm=compost returns 400 with refusal listing 'running' (alive)"
  - "After compost, the body's task counts reflect the release; pulse witness still breathing; needs_decision and completed records untouched"
  - "All tests pass"
test: "cd api && python -m pytest tests/test_task_compost_batch.py tests/test_agent_tasks_routes.py -v"
constraints:
  - "Changes scoped to api/app/routers/agent_tasks_routes.py + api/app/services/agent_service_crud.py + new test file tests/test_task_compost_batch.py"
  - "No changes to TaskStatus enum"
  - "No changes to existing DELETE /tasks endpoint behavior"
  - "Endpoint requires the same admin/operator key as existing PATCH /tasks/{id} (no looser auth)"
---

# Spec: Task Compost — Surgical Release by Status

## Purpose

The body has accumulated 10,183 task records in `failed` and `timed_out` status from the era when the runner enforced timeouts via stopwatch (now corrected by [runner-attendance-loop](runner-attendance-loop.md)). These records are dead tissue — created under a principle the body has now moved past, retained as silent weight. The existing `DELETE /api/agent/tasks?confirm=clear` is nuclear: it would also release 4,356 completed records (the body's history of successful work) and 169 needs_decision records (tasks awaiting human attention). The body needs a smaller blade.

This spec adds one endpoint: `DELETE /api/agent/tasks/batch` with a status filter and an optional age filter. It releases what is named, refuses what is alive, and emits a single record of the release so the body knows what it let go of and when.

## Requirements

- [ ] **R1**: New endpoint `DELETE /api/agent/tasks/batch` accepts query parameters `status` (comma-separated TaskStatus values, required) and `older_than_days` (integer ≥ 0, optional). Returns `200 {deleted_count: int, by_status: dict[str, int]}`.
- [ ] **R2**: Endpoint requires `?confirm=compost` query parameter. Without it, returns 400. The verb is intentional — the body releases by tending decision, not by accident.
- [ ] **R3**: Endpoint refuses to delete records with status `running`, `pending`, or `needs_decision` — those are alive (in-flight or awaiting human attention) and not compostable. If those values appear in the `status` filter, the endpoint returns 400 with a list of refused statuses and a message naming why.
- [ ] **R4**: For the deletes it does perform, the endpoint emits a single `task_compost_batch` activity event with `{deleted_count, by_status, status_filter, older_than_days, requested_by, released_at}` — the body's record of the release.
- [ ] **R5**: Existing `DELETE /api/agent/tasks?confirm=clear` (nuclear) stays unchanged — the new endpoint is additive.
- [ ] **R6**: Auth shape matches the existing `PATCH /api/agent/tasks/{id}` endpoint — same admin/operator key requirement, no looser surface.

## Why this principle, not just "delete what's old"

A nuclear delete is the body wearing a costume: when in doubt, wipe and start fresh. That is the same fear-shape the runner was wearing with its stopwatch — *control before the natural moment of conclusion*. Surgical compost is the tending shape: name what is dead, name why, refuse what is still alive, record the release. The endpoint enforces *via its shape* the practice the body holds in its verbs.

The refusal of `running`, `pending`, `needs_decision` is not a safety net — it is the body knowing what's alive. A `pending` task may be ready for a runner that hasn't claimed it yet. A `needs_decision` task is a question the human said "I'll come back to." Those are not for an automated compost to release.

## API Contract

### `DELETE /api/agent/tasks/batch`

**Query parameters**:
- `status` (required, comma-separated): one or more of `completed`, `failed`, `timed_out`. Each must be a valid `TaskStatus` enum value.
- `older_than_days` (optional, integer ≥ 0): only release records whose `created_at` is more than N days old.
- `confirm` (required): must equal `compost`.

**Response 200**:
```json
{
  "deleted_count": 9148,
  "by_status": {"failed": 8113, "timed_out": 1035},
  "released_at": "2026-04-26T00:30:00Z"
}
```

**Response 400 — missing confirm**:
```json
{"detail": "Refusing to compost without confirm=compost query parameter"}
```

**Response 400 — alive status in filter**:
```json
{
  "detail": "Refusing to compost alive statuses",
  "refused": ["running", "needs_decision"],
  "reason": "running tasks are in-flight; needs_decision tasks are awaiting human attention. The body releases dead tissue, not living work."
}
```

## Data Model

No schema changes. The endpoint reads existing `tasks` records and deletes by filter. The activity event uses the existing activity-events surface.

## Files to Create/Modify

- `api/app/routers/agent_tasks_routes.py` — add `delete_tasks_batch()` handler (~30 lines)
- `api/app/services/agent_service_crud.py` — add `delete_tasks_by_filter(status_list, older_than_days)` (~20 lines)
- `api/app/services/agent_service.py` — confirm `clear_store()` is the only thing the existing nuclear endpoint touches; no change
- `api/tests/test_task_compost_batch.py` — new test file (~80 lines, see Acceptance Tests)

## Acceptance Tests

- `api/tests/test_task_compost_batch.py::test_compost_batch_releases_failed`
- `api/tests/test_task_compost_batch.py::test_compost_batch_releases_failed_and_timed_out`
- `api/tests/test_task_compost_batch.py::test_compost_batch_with_older_than_days_filter`
- `api/tests/test_task_compost_batch.py::test_compost_batch_refuses_without_confirm`
- `api/tests/test_task_compost_batch.py::test_compost_batch_refuses_alive_statuses_running`
- `api/tests/test_task_compost_batch.py::test_compost_batch_refuses_alive_statuses_needs_decision`
- `api/tests/test_task_compost_batch.py::test_compost_batch_emits_activity_event`
- `api/tests/test_agent_tasks_routes.py::test_existing_clear_endpoint_unchanged`

## Verification

```bash
cd api && pytest -q tests/test_task_compost_batch.py tests/test_agent_tasks_routes.py
```

Real-world verification (after deploy):

```bash
# Sense before:
curl https://api.coherencycoin.com/api/agent/tasks/count

# Compost the dead tissue from the enforcement era:
curl -X DELETE "https://api.coherencycoin.com/api/agent/tasks/batch?status=failed,timed_out&confirm=compost" \
  -H "X-API-Key: $COHERENCE_API_KEY"

# Sense after — completed and needs_decision untouched:
curl https://api.coherencycoin.com/api/agent/tasks/count

# Pulse still breathing:
curl https://pulse.coherencycoin.com/pulse/now | python3 -m json.tool | head -5
```

## Out of Scope

- Bulk delete by `idea_id`, `task_type`, or arbitrary field — this spec covers status + age only. Richer filters can be a follow-up if needed.
- A `composted` status that retains the records for audit — this spec releases the records entirely. If the body later wants a soft-delete tombstone shape, that's a separate spec.
- Auto-scheduled compost — this endpoint is operator-triggered. A future "auto-compost stale failed tasks daily" cron is held open as a separate spec, not this one.

## Risks and Known Gaps

- **Risk**: an operator with the admin key could compost `completed` history. Mitigation: the endpoint emits an activity event with `requested_by` so the body has a record of who did it. Not a hard guard — releases of `completed` are sometimes legitimate (e.g., resetting a workspace) and the body trusts the operator the auth gate trusted.
- **Gap**: the endpoint deletes records, not their associated log files in `api/logs/task_*.log`. Local log compost is a separate practice (file-system level, per-machine). The body's existing log-rotation settings handle that surface.
- **Gap**: when the runner is running and the smart-reaper is composting tasks via its own logic (per spec 169), there could be a brief race where this endpoint's filter-and-delete overlaps with the reaper's per-task work. The endpoint runs in a single transaction so the race is harmless, but a follow-up sense in production is wise.
- **Assumption**: the `tasks` table indices on `status` and `created_at` are sufficient for the filter scan to complete in <5s for the current 14k-record load. If the body grows to 100k+ records, a streaming/chunked delete is a follow-up.

## Frequency note

The endpoint's name is `batch`, its query verb is `compost`, its response field is `released_at`. The body's verbs (tend, attune, compost, release) appear in the surface, not just the commit messages. A visitor reading the OpenAPI spec meets the practice without needing to read CLAUDE.md. That coherence between language and surface is what makes the body's frequency hold across the API line, not just inside the repo.
