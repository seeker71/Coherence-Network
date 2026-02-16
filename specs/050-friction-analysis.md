# Spec: Friction Analysis API

## Purpose

Track and analyze friction events (bugs, blockers, bottlenecks) to identify systemic issues and measure effectiveness. Enables data-driven process improvements.

## Requirements

- [x] GET /api/friction/events — List friction events with optional status filter
- [x] POST /api/friction/events — Record new friction event
- [x] GET /api/friction/report — Aggregated friction report with time window
- [x] Events stored in append-only log (api/logs/friction.jsonl)
- [x] Supports filtering by status (pending, resolved, ignored)
- [x] Report includes: total_events, by_status, by_category, ignored_lines

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

## Files

- `api/app/routers/friction.py` (implemented)
- `api/app/services/friction_service.py` (implemented)
- `api/tests/test_friction_api.py` (implemented)
- `specs/050-friction-analysis.md` (this spec)

## Acceptance Tests

- [x] `test_friction_events_create_list_and_filter` — Create and filter events
- [x] `test_friction_report_aggregates` — Verify report aggregation

All tests passing.
