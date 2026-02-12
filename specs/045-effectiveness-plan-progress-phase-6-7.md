# Spec: GET /api/agent/effectiveness — Plan Progress (Phase 6/7 Completion)

## Purpose

Measure progress toward PLAN.md goals by exposing Phase 6 and Phase 7 completion in GET /api/agent/effectiveness. Data is derived from project manager state and the overnight backlog (006), so monitors and dashboards can report how much of the product-critical and polish work remains.

## Requirements

- [ ] **plan_progress present:** GET /api/agent/effectiveness returns a `plan_progress` object (existing behavior retained).
- [ ] **Phase 6/7 completion:** `plan_progress` includes Phase 6 and Phase 7 completion derived from PM state and backlog (006): at least `phase_6` and `phase_7`, each with `completed`, `total`, and optionally `pct` (0–100).
- [ ] **Phase boundaries:** Phase 6 = Product-Critical (backlog items 56–57 per 006). Phase 7 = Remaining Specs & Polish (items 58–74 per 006). Boundaries are defined by specs/006-overnight-backlog.md section headers.
- [ ] **Data source:** Completion is computed from PM state (`backlog_index` in project_manager_state.json or project_manager_state_overnight.json) and total counts per phase from parsing 006-overnight-backlog.md (or equivalent backlog file).
- [ ] **Test:** A test in `api/tests/test_agent.py` calls GET /api/agent/effectiveness and asserts response includes `plan_progress` with `phase_6` and `phase_7`, each having `completed` (int), `total` (int), and that Phase 6 total is 2 and Phase 7 total is 17 when 006 is used (or equivalent when backlog changes).

## API Contract (if applicable)

### `GET /api/agent/effectiveness`

**Request**
- None (no query or path parameters).

**Response 200**

Existing fields (throughput, success_rate, issues, progress, goal_proximity, heal_resolved_count, top_issues_by_priority) unchanged. Extend or retain `plan_progress` as follows:

```json
{
  "throughput": { "completed_7d": 0, "tasks_per_day": 0 },
  "success_rate": 0.0,
  "issues": { "open": 0, "resolved_7d": 0 },
  "progress": { "spec": 0, "impl": 0, "test": 0, "review": 0, "heal": 0 },
  "plan_progress": {
    "index": 0,
    "total": 74,
    "pct": 0,
    "state_file": "project_manager_state.json",
    "phase_6": { "completed": 0, "total": 2, "pct": 0 },
    "phase_7": { "completed": 0, "total": 17, "pct": 0 }
  },
  "goal_proximity": 0,
  "heal_resolved_count": 0,
  "top_issues_by_priority": []
}
```

- `plan_progress.index`: current backlog index (from PM state).
- `plan_progress.total`: total backlog items (from 006).
- `plan_progress.pct`: round(100 * index / total, 1) when total > 0, else 0.
- `plan_progress.state_file`: basename of state file used, or empty string if none.
- `plan_progress.phase_6`: Phase 6 (Product-Critical) completion: `completed` = number of Phase 6 items with backlog index already passed (item number ≤ current index); `total` = 2; `pct` = round(100 * completed / total, 1).
- `plan_progress.phase_7`: Phase 7 (Remaining Specs & Polish) completion: `completed` = number of Phase 7 items with backlog index already passed; `total` = 17; `pct` = round(100 * completed / total, 1).

When backlog file is missing or unparseable, `plan_progress` may omit `phase_6`/`phase_7` or set totals to 0; `index`, `total`, `pct`, `state_file` behavior remains best-effort as today.

## Data Model (if applicable)

```yaml
plan_progress:
  index: integer
  total: integer
  pct: number
  state_file: string
  phase_6:
    completed: integer
    total: integer
    pct: number
  phase_7:
    completed: integer
    total: integer
    pct: number
```

Phase boundaries (006): Phase 6 = items 56–57 (inclusive). Phase 7 = items 58–74 (inclusive). If 006 changes item counts, implementation parses section headers to derive totals or uses documented constants updated with backlog.

## Files to Create/Modify

- `api/app/services/effectiveness_service.py` — extend `_plan_progress()` (or equivalent) to compute Phase 6 and Phase 7 completed/total from PM state and backlog; add `phase_6` and `phase_7` to returned dict.
- `api/tests/test_agent.py` — add or retain test that GET /api/agent/effectiveness returns 200 and response includes `plan_progress.phase_6` and `plan_progress.phase_7` with `completed`, `total`; assert Phase 6 total is 2 and Phase 7 total is 17 when using default 006 backlog (or document and assert equivalent constants).

## Acceptance Tests

See `api/tests/test_agent.py`. Test name suggestion: `test_effectiveness_plan_progress_includes_phase_6_and_phase_7`. All existing effectiveness tests must continue to pass.

## Out of Scope

- Changing goal_proximity formula or other effectiveness fields.
- Adding new API endpoints or query parameters.
- Persisting phase completion elsewhere; computation is from existing PM state and backlog file only.
- Backlog alignment check (spec 007 item 4) or meta-questions (007 item 3).

## Decision Gates (if any)

- If backlog phase boundaries or item ranges change in 006, update implementation (and optionally this spec) to match; no new dependency or resource.

## See also

- [007-meta-pipeline-backlog.md](007-meta-pipeline-backlog.md) — item 1: Progress toward PLAN metric
- [006-overnight-backlog.md](006-overnight-backlog.md) — Phase 6 (56–57), Phase 7 (58–74)
- [002-agent-orchestration-api.md](002-agent-orchestration-api.md) — GET /api/agent/effectiveness context
- docs/PLAN.md — goals and roadmap
