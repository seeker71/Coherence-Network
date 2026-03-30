# Spec: Friction Analysis API

## Purpose

Track and analyze friction events (bugs, blockers, bottlenecks) to identify systemic issues and measure effectiveness. Enables data-driven process improvements.

## Requirements

- [x] GET /api/friction/events — List friction events with optional status filter
- [x] POST /api/friction/events — Record new friction event
- [x] GET /api/friction/report — Aggregated friction report with time window
- [x] GET /api/friction/entry-points — Unified friction entry points from monitor issues, failed-task cost, and CI failure waste
- [x] Events stored in append-only log (api/logs/friction.jsonl)
- [x] Supports filtering by status (pending, resolved, ignored)
- [x] Report includes: total_events, by_status, by_category, ignored_lines


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: 115

## Task Card

```yaml
goal: Track and analyze friction events (bugs, blockers, bottlenecks) to identify systemic issues and measure effectiveness.
files_allowed:
  - api/app/routers/friction.py
  - api/app/services/friction_service.py
  - api/tests/test_friction_api.py
  - specs/050-friction-analysis.md
done_when:
  - GET /api/friction/events — List friction events with optional status filter
  - POST /api/friction/events — Record new friction event
  - GET /api/friction/report — Aggregated friction report with time window
  - GET /api/friction/entry-points — Unified friction entry points from monitor issues, failed-task cost, and CI failure ...
  - Events stored in append-only log (api/logs/friction.jsonl)
commands:
  - cd api && /Users/ursmuff/source/Coherence-Network/api/.venv/bin/pytest -q tests/test_friction_api.py
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

## API Contract

### `GET /api/friction/events`

**Request**:
- `limit`: Integer (query, 1-1000, default: 100)
- `status`: String (query, optional) — Filter by status

**Response 200**:
```json
[
  {
    "timestamp": "2026-02-15T10:00:00Z",
    "category": "bug",
    "description": "API timeout on /distributions",
    "status": "pending",
    "metadata": {}
  }
]
```

### `POST /api/friction/events`

**Request**:
```json
{
  "timestamp": "2026-02-15T10:00:00Z",
  "category": "blocker",
  "description": "Database migration failed",
  "status": "pending",
  "metadata": {"severity": "high"}
}
```

**Response 201**: Returns created event

### `GET /api/friction/report`

**Request**:
- `window_days`: Integer (query, 1-365, default: 7)

**Response 200**:
```json
{
  "total_events": 42,
  "by_status": {"pending": 10, "resolved": 30, "ignored": 2},
  "by_category": {"bug": 20, "blocker": 12, "bottleneck": 10},
  "source_file": "api/logs/friction.jsonl",
  "ignored_lines": 0
}
```


### Input Validation

- All string fields: min_length=1, max_length=1000
- Numeric fields: appropriate min/max bounds
- Required fields validated; missing returns 422
- Unknown fields rejected (Pydantic extra="forbid" where applicable)

## Files to Create/Modify

- `api/app/routers/friction.py` (implemented)
- `api/app/services/friction_service.py` (implemented)
- `api/tests/test_friction_api.py` (implemented)
- `specs/050-friction-analysis.md` (this spec)

## Acceptance Tests

- [x] `api/tests/test_friction_api.py::test_friction_events_create_list_and_filter` — Create and filter events
- [x] `api/tests/test_friction_api.py::test_friction_report_aggregates` — Verify report aggregation
- [x] `api/tests/test_friction_api.py::test_friction_entry_points_merges_sources` — Verify unified entry-point aggregation

All tests passing.

## Concurrency Behavior

- **Read operations**: Safe for concurrent access; no locking required.
- **Write operations**: Last-write-wins semantics; no optimistic locking for MVP.
- **Recommendation**: Clients should not assume atomic read-modify-write without explicit ETag support.

## Failure and Retry Behavior

- **Gate failure**: CI gate blocks merge; author must fix and re-push.
- **Flaky test**: Re-run up to 2 times before marking as genuine failure.
- **Rollback behavior**: Failed deployments automatically roll back to last known-good state.
- **Infrastructure failure**: CI runner unavailable triggers alert; jobs re-queue on recovery.
- **Timeout**: CI jobs exceeding 15 minutes are killed and marked failed; safe to re-trigger.


## Verification

```bash
cd api && /Users/ursmuff/source/Coherence-Network/api/.venv/bin/pytest -q tests/test_friction_api.py
cd api && /Users/ursmuff/source/Coherence-Network/api/.venv/bin/pytest -q tests/test_automation_usage_api.py
cd api && /Users/ursmuff/source/Coherence-Network/api/.venv/bin/pytest -q tests/test_monitor_pipeline_github_actions.py
```

## Out of Scope

- UI redesign for friction analytics beyond entry-point visibility pages.
- Provider-specific failure remediation workflows.

## Risks and Assumptions

- Risk: event-source files or DB snapshots can be unavailable; mitigation is tolerant parsing with explicit ignored/error counters.
- Assumption: monitor issue and metrics schemas remain backward compatible for friction aggregation.

## Downstream Consumers

- **Spec 115** ([115-grounded-cost-value-measurement.md](115-grounded-cost-value-measurement.md)) — Reads `telemetry_persistence_service.list_friction_events()` filtered by idea_id and extracts `cost_of_delay` as a friction cost avoidance signal. This is normalized on a log scale ($1 = 0.2, $10 = 0.5, $100+ = 0.9) and feeds into the grounded value formula as an economic signal for task-level ROI.

## Known Gaps and Follow-up Tasks

- Follow-up task: `friction-metric-cost-normalization` to calibrate cost-of-delay models against measured provider billing data.
