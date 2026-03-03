# Spec: Pipeline-Status Returns 200 in Empty State

## Purpose

Ensure `GET /api/agent/pipeline-status` returns HTTP 200 when there is no running task (empty state), so scripts, monitors, and smoke tests can rely on the endpoint without false failures. This is the minimal “no work in progress” case that must succeed.

## Requirements

- [ ] **Empty state:** `GET /api/agent/pipeline-status` returns 200 when there is no running task (no tasks at all, or only pending/completed/failed). Response body must include the full contract: `running`, `pending`, `recent_completed`, `attention`, and `running_by_phase` (per specs 002, 027, 032).
- [ ] **Running empty:** In that case `running` is an empty list and `running_by_phase` has empty (or zero) values for each phase.

## API Contract (if applicable)

### `GET /api/agent/pipeline-status`

**Request** — None (GET, no required query or body).

**Response 200 (empty state)** — When no task is running:

- Status code: 200.
- Body must include: `running`, `pending`, `recent_completed`, `attention`, `running_by_phase`.
- `running`: array (empty when no running task).
- `attention`: object with `stuck`, `repeated_failures`, `low_success_rate`, `flags` (see spec 032).
- `running_by_phase`: object with keys `spec`, `impl`, `test`, `review` (see spec 002).

No 4xx/5xx due to “no tasks” or “no running task”; empty state is a valid outcome.

## Data Model (if applicable)

No new data model. Reuses existing task store and pipeline-status response shape (specs 002, 027, 032).

## Files to Create/Modify

- `api/tests/test_agent.py` — Add or designate an acceptance test: pipeline-status returns 200 when no running task (empty state); assert status 200 and presence of required top-level keys and that `running` is a list (empty in this scenario).

## Acceptance Tests

- In `api/tests/test_agent.py`: A test that, with no tasks created (or with only pending/completed tasks, none running), calls `GET /api/agent/pipeline-status` and asserts:
  - `response.status_code == 200`
  - Response JSON contains `running`, `pending`, `recent_completed`, `attention`, `running_by_phase`
  - `running` is a list (empty in empty state)
  - `attention` contains `stuck`, `repeated_failures`, `low_success_rate`, `flags`

Existing tests (e.g. `test_pipeline_status_returns_200`, `test_pipeline_status_attention_stuck_false_when_no_pending`) may already cover this when the store is empty; this spec makes the empty-state 200 contract explicit and ensures a dedicated or clearly named test exists for it.

## Out of Scope

- Changing the pipeline-status response shape or router implementation (only test addition or clarification).
- Other endpoints or attention heuristic logic (covered by specs 002, 032).

## Decision Gates (if any)

None.

## See also

- [002 Agent Orchestration API](002-agent-orchestration-api.md) — pipeline-status contract.
- [027 Fully Automated Pipeline](027-fully-automated-pipeline.md) — pipeline-status and attention.
- [032 Attention Heuristics Pipeline Status](032-attention-heuristics-pipeline-status.md) — attention object.
- [006 Overnight Backlog](006-overnight-backlog.md) — item 19: “Add test: pipeline-status returns 200 when no running task (empty state)”.
