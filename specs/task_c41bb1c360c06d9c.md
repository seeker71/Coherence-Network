# Data Hygiene — Row Count Monitoring, Noise Detection, and Growth Anomaly Alerts

**Spec ID**: task_c41bb1c360c06d9c
**Type**: Feature Spec
**Status**: Draft
**Author**: product-manager agent
**Date**: 2026-03-28

---

## Summary

Coherence Network tables are growing without visibility into whether that growth is healthy. `runtime_events` currently holds 46,614 rows in a young system — a red flag that may indicate runaway event emission, missing TTL policies, or unbounded agent logging. This spec defines:

1. **`cc db-status`** — a CLI command that shows per-table row counts, sizes, and growth rates
2. **Growth anomaly alerts** — automated detection when any table grows faster than expected thresholds
3. **Data health dashboard** — a web UI page (`/admin/data-health`) surfacing current row counts, trends, and alert history

This work is the foundation for data lifecycle management. Without it, the system has no way to detect unbounded growth before it becomes a storage or performance crisis.

---

## Motivation and Context

### Current State

| Table | Row Count | Notes |
|---|---|---|
| `runtime_events` | 46,614 | **Suspicious** — ~37× larger than all other tables combined |
| `telemetry_snapshots` | 2,001 | Reasonable for monitoring cadence |
| `agent_tasks` | 1,268 | Expected for task volume |
| `telemetry_task_metrics` | 1,372 | Reasonable |
| `measurements` | 450 | Low, expected |
| `contribution_ledger` | 530 | Low, expected |

The `runtime_events` anomaly is the immediate trigger: 46k events suggests either (a) events are being emitted at high frequency with no retention policy, (b) duplicate event emission due to retries, or (c) a bug causing fan-out. None of these are visible today.

### Why This Matters

- **Storage**: Unchecked growth consumes disk silently until things break.
- **Performance**: Unindexed large tables cause slow queries and API timeouts.
- **Correctness**: If events are duplicated or noisy, downstream analytics and CC scoring are wrong.
- **Trust**: Contributors need confidence that the data health is known and controlled.

---

## Goals

1. **Visibility**: Any developer can run `cc db-status` and get a clear table-by-table health snapshot.
2. **Alerting**: When a table grows more than 2× its expected hourly rate, an alert is logged and broadcast.
3. **Investigation support**: The snapshot includes enough metadata (growth rate, last event timestamp, estimated daily rows) to diagnose anomalies.
4. **Dashboard**: A human-readable web page confirms the system is healthy at a glance.
5. **Proof this is working**: Growth anomalies create entries in an `data_health_alerts` log that can be queried.

---

## Out of Scope

- Automatic pruning or archiving of rows (separate spec)
- Per-row deduplication logic (separate spec)
- Cross-database (Neo4j) health checks (future)
- GDPR/retention compliance (separate spec)

---

## Requirements

### R1 — `cc db-status` CLI Command

**Command**: `cc db-status`
**Output**: Table-formatted snapshot of all tracked tables showing:

```
TABLE                     ROWS     SIZE      GROWTH_1H   GROWTH_24H   STATUS
runtime_events            46,614   18.2 MB   +312        +7,488       ⚠ ANOMALY
telemetry_snapshots        2,001    0.8 MB    +24         +576         ✓ OK
agent_tasks                1,268    0.5 MB    +8          +192         ✓ OK
telemetry_task_metrics     1,372    0.5 MB    +9          +216         ✓ OK
measurements                 450    0.2 MB    +2           +48         ✓ OK
contribution_ledger          530    0.2 MB    +3           +72         ✓ OK
```

**Implementation path**: `api/routers/db_status.py` exposes `GET /api/admin/db-status`, and the `cc` CLI calls it.

**Fields per table**:
- `rows`: current `COUNT(*)`
- `size`: PostgreSQL `pg_total_relation_size()` formatted human-readable
- `growth_1h`: rows added in the last 60 minutes (requires a timestamp column or snapshot comparison)
- `growth_24h`: rows added in the last 24 hours
- `status`: `OK`, `ANOMALY`, or `UNKNOWN` based on growth thresholds

**Fallback for tables without timestamp columns**: Growth calculated from stored snapshots (see R3).

---

### R2 — Growth Anomaly Detection

**Definition of anomaly**: A table's 1-hour growth rate exceeds 2× its 7-day rolling average hourly growth.

**Thresholds (configurable via env vars)**:

| Variable | Default | Meaning |
|---|---|---|
| `DB_HEALTH_ANOMALY_MULTIPLIER` | `2.0` | How many times the rolling average before flagging |
| `DB_HEALTH_SNAPSHOT_INTERVAL_MINUTES` | `60` | How often to take a growth snapshot |
| `DB_HEALTH_ALERT_COOLDOWN_HOURS` | `4` | Don't re-alert on same table within this window |

**Alert actions when anomaly detected**:
1. Write a record to `data_health_alerts` table (see R3)
2. Log at `WARNING` level with structured fields
3. Broadcast via `cc msg broadcast` if `cc` CLI is available in runtime

**Anomaly types**:
- `growth_spike`: 1h growth > 2× rolling average
- `size_threshold`: Table exceeds absolute size limit (default: 500 MB)
- `row_threshold`: Table exceeds absolute row limit (default: 1,000,000 rows)

---

### R3 — Data Model

#### New table: `data_health_snapshots`

```sql
CREATE TABLE data_health_snapshots (
    id          SERIAL PRIMARY KEY,
    table_name  TEXT NOT NULL,
    row_count   BIGINT NOT NULL,
    size_bytes  BIGINT NOT NULL,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_dhs_table_captured ON data_health_snapshots (table_name, captured_at DESC);
```

**Purpose**: Historical row count samples enabling growth rate calculation for tables that lack their own timestamp column (e.g., junction tables). Snapshots are taken every `DB_HEALTH_SNAPSHOT_INTERVAL_MINUTES` by the monitoring job.

#### New table: `data_health_alerts`

```sql
CREATE TABLE data_health_alerts (
    id              SERIAL PRIMARY KEY,
    table_name      TEXT NOT NULL,
    alert_type      TEXT NOT NULL,       -- growth_spike | size_threshold | row_threshold
    current_value   BIGINT NOT NULL,     -- current row count or size bytes
    threshold_value BIGINT NOT NULL,     -- the threshold that was breached
    rolling_avg     NUMERIC,             -- 7-day rolling average (nullable)
    resolved_at     TIMESTAMPTZ,         -- NULL = unresolved
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_dha_table_created ON data_health_alerts (table_name, created_at DESC);
CREATE INDEX idx_dha_unresolved ON data_health_alerts (table_name) WHERE resolved_at IS NULL;
```

---

### R4 — API Endpoints

#### `GET /api/admin/db-status`

Returns current health snapshot for all monitored tables.

**Response (200 OK)**:
```json
{
  "captured_at": "2026-03-28T14:00:00Z",
  "tables": [
    {
      "table_name": "runtime_events",
      "row_count": 46614,
      "size_bytes": 19088384,
      "size_human": "18.2 MB",
      "growth_1h": 312,
      "growth_24h": 7488,
      "rolling_avg_hourly": 156.3,
      "status": "anomaly",
      "alert_type": "growth_spike"
    }
  ],
  "alert_count": 1,
  "overall_status": "degraded"
}
```

**Auth**: Requires `X-Admin-Token` header (same pattern as other admin endpoints). Returns 401 if missing.

#### `GET /api/admin/db-status/alerts`

Returns recent alert history.

**Query params**: `?limit=50&table=runtime_events&unresolved_only=true`

**Response (200 OK)**:
```json
{
  "alerts": [
    {
      "id": 1,
      "table_name": "runtime_events",
      "alert_type": "growth_spike",
      "current_value": 46614,
      "threshold_value": 23307,
      "rolling_avg": 156.3,
      "resolved_at": null,
      "created_at": "2026-03-28T13:00:00Z"
    }
  ],
  "total": 1
}
```

#### `POST /api/admin/db-status/snapshot`

Manually triggers a snapshot (useful for testing and post-deploy verification).

**Response (201 Created)**:
```json
{
  "snapshot_id": 42,
  "tables_snapshotted": 6,
  "anomalies_detected": 1,
  "captured_at": "2026-03-28T14:05:00Z"
}
```

---

### R5 — Background Monitoring Job

A lightweight background task runs within the FastAPI app using APScheduler (already a dependency or add it) or a simple `asyncio` loop.

**Job**: `db_health_monitor_job`
**Schedule**: Every `DB_HEALTH_SNAPSHOT_INTERVAL_MINUTES` (default: 60)
**Actions**:
1. Query row counts and sizes for all monitored tables
2. Insert rows into `data_health_snapshots`
3. Compute growth rates using last 7 days of snapshots
4. Detect anomalies against thresholds
5. Insert into `data_health_alerts` if threshold breached and not in cooldown
6. Log summary at `INFO` level

**Monitored tables** (configurable via `DB_HEALTH_MONITORED_TABLES` env var, default list):
```
runtime_events, telemetry_snapshots, agent_tasks, telemetry_task_metrics,
measurements, contribution_ledger, data_health_snapshots, data_health_alerts
```

---

### R6 — Web Dashboard: `/admin/data-health`

A new page in the Next.js web app at `/admin/data-health`.

**Components**:
- **Summary bar**: Overall status (OK / Degraded / Critical), last snapshot time
- **Table cards**: One card per monitored table showing row count, size, 24h trend sparkline, status badge
- **Alert feed**: Recent alerts with table name, type, timestamp, and resolution status
- **Auto-refresh**: Page refreshes data every 5 minutes via `setInterval` (or SWR revalidation)

**Visual status indicators**:
- Green badge: `OK`
- Yellow badge: `WARNING` (approaching threshold, not yet anomaly)
- Red badge: `ANOMALY`

---

### R7 — `runtime_events` Investigation Support

Because `runtime_events` is the immediate anomaly, the snapshot must include:

- `oldest_event_at`: timestamp of the oldest row (to determine event age range)
- `newest_event_at`: timestamp of the most recent row
- Top 5 `event_type` values by count (if a `type` or `event_type` column exists)

This data is returned as a `details` field in the `GET /api/admin/db-status` response for the `runtime_events` table specifically:

```json
{
  "table_name": "runtime_events",
  "details": {
    "oldest_row_at": "2026-01-15T08:00:00Z",
    "newest_row_at": "2026-03-28T13:59:00Z",
    "top_event_types": [
      {"type": "agent_heartbeat", "count": 38291},
      {"type": "task_start", "count": 4201},
      {"type": "task_complete", "count": 3819},
      {"type": "error", "count": 212},
      {"type": "metric_emit", "count": 91}
    ]
  }
}
```

This narrows the investigation: if `agent_heartbeat` makes up 80%+ of events, there is a clear retention candidate.

---

## Files to Create / Modify

| Path | Action | Description |
|---|---|---|
| `api/routers/db_status.py` | Create | API router for all db-status endpoints |
| `api/models/db_health.py` | Create | Pydantic response models |
| `api/services/db_health_service.py` | Create | Business logic: snapshot, anomaly detection |
| `api/jobs/db_health_monitor.py` | Create | Background job definition |
| `api/db/migrations/add_data_health_tables.sql` | Create | SQL migration for new tables |
| `api/main.py` | Modify | Register router and start background job |
| `web/src/app/admin/data-health/page.tsx` | Create | Dashboard page |
| `web/src/components/DataHealthCard.tsx` | Create | Per-table status card component |

---

## Verification Scenarios

### Scenario 1 — `cc db-status` returns row counts

**Setup**: System has been running; `runtime_events` table exists with rows.

**Action**:
```bash
cc db-status
```

**Expected result**: Table output showing at minimum `runtime_events` with a row count >= 46,614 (or whatever current count is), a size in MB, and a `STATUS` column. The output must not be empty.

**Edge case**: If the database is unreachable, `cc db-status` must exit with a non-zero status code and print `ERROR: cannot connect to database` rather than an empty table or a Python traceback.

---

### Scenario 2 — API endpoint returns structured JSON

**Setup**: Database is running; API is deployed.

**Action**:
```bash
curl -s -H "X-Admin-Token: $ADMIN_TOKEN" \
  https://api.coherencycoin.com/api/admin/db-status | jq .
```

**Expected result**:
- HTTP 200
- Response contains `"tables"` array with at least 6 entries (one per monitored table)
- Each entry has `table_name`, `row_count` (integer >= 0), `size_human`, `status` fields
- `"overall_status"` is one of `"ok"`, `"degraded"`, `"critical"`
- `"captured_at"` is a valid ISO 8601 timestamp within the last 5 minutes

**Edge case**: Missing or wrong `X-Admin-Token` returns HTTP 401 with `{"detail": "Unauthorized"}`.

---

### Scenario 3 — Growth anomaly is detected and stored

**Setup**: `data_health_snapshots` has at least 7 days of hourly snapshots for `runtime_events` (or inject synthetic rows for testing). The most recent snapshot shows a 3× spike vs. rolling average.

**Action**:
```bash
curl -s -X POST -H "X-Admin-Token: $ADMIN_TOKEN" \
  https://api.coherencycoin.com/api/admin/db-status/snapshot | jq .anomalies_detected
```

**Expected result**: Integer >= 1 (the spike is detected).

**Then**:
```bash
curl -s -H "X-Admin-Token: $ADMIN_TOKEN" \
  "https://api.coherencycoin.com/api/admin/db-status/alerts?unresolved_only=true" | jq '.alerts[0].alert_type'
```

**Expected result**: `"growth_spike"` for `runtime_events`.

**Edge case**: Triggering the snapshot a second time within the cooldown window (`DB_HEALTH_ALERT_COOLDOWN_HOURS`) must NOT create a duplicate alert. The alert count must not increase.

---

### Scenario 4 — `runtime_events` investigation detail

**Setup**: `runtime_events` table has rows with an `event_type` or `type` column.

**Action**:
```bash
curl -s -H "X-Admin-Token: $ADMIN_TOKEN" \
  https://api.coherencycoin.com/api/admin/db-status | \
  jq '.tables[] | select(.table_name == "runtime_events") | .details'
```

**Expected result**:
```json
{
  "oldest_row_at": "<valid ISO timestamp>",
  "newest_row_at": "<valid ISO timestamp, after oldest>",
  "top_event_types": [
    {"type": "<non-empty string>", "count": <integer > 0>},
    ...
  ]
}
```

`top_event_types` must contain at least 1 entry and no more than 5. Counts must sum to <= total row count.

**Edge case**: If `runtime_events` has no rows (e.g., test environment with empty table), `details` must still be present with `oldest_row_at: null`, `newest_row_at: null`, and `top_event_types: []`. Must not return 500.

---

### Scenario 5 — Web dashboard renders without errors

**Setup**: Web app is deployed; API is accessible.

**Action**: Navigate browser to `https://coherencycoin.com/admin/data-health`

**Expected result**:
- Page loads with HTTP 200 (no redirect to 404)
- Page title contains "Data Health" or equivalent
- At least 6 table cards are visible, each showing a row count
- At least one card shows a colored status badge
- Console has no unhandled JavaScript exceptions

**Edge case**: If the API returns 503 (database down), the dashboard must show an error banner ("Data unavailable — API error") rather than a blank page or spinner that never resolves.

---

## Evidence of Completion

The following evidence must exist and be independently verifiable:

1. **Live endpoint**: `curl -s -H "X-Admin-Token: $ADMIN_TOKEN" https://api.coherencycoin.com/api/admin/db-status` returns valid JSON with table data.
2. **Alert history**: `curl .../api/admin/db-status/alerts` returns a list (possibly empty if no anomalies yet, but endpoint must exist and return 200).
3. **Dashboard URL**: `https://coherencycoin.com/admin/data-health` loads without 404 or unhandled errors.
4. **Snapshot table**: `SELECT count(*) FROM data_health_snapshots` returns > 0 rows after the first monitoring interval.
5. **`runtime_events` investigation**: The `details` field for `runtime_events` in the API response reveals the top event types, enabling root-cause analysis of the 46k row count.

---

## Risks and Assumptions

| Risk | Likelihood | Mitigation |
|---|---|---|
| `runtime_events` lacks a timestamp column, making native growth calculation impossible | Medium | Fall back to snapshot comparison; note in response as `growth_method: "snapshot"` vs `"timestamp"` |
| Background job fails silently and snapshots never accumulate | Medium | Job must log at start/end; add a `/api/admin/db-status/job-health` endpoint returning last successful run time |
| Admin token is not set in production env | Low | API falls back to checking `ADMIN_SECRET` env var; returns 503 with clear message if neither is set |
| APScheduler not in current dependencies | Medium | Use `asyncio` background task if APScheduler unavailable; simpler but less robust |
| 46k `runtime_events` rows are legitimate (e.g., detailed observability) | Low | Spec does not delete data; investigation detail informs whether pruning spec is needed |

---

## Known Gaps and Follow-up Tasks

1. **Retention policy spec**: Once we know which event types are noise (from investigation detail), a separate spec should define TTL rules for `runtime_events`.
2. **Neo4j health**: This spec covers PostgreSQL only. A parallel spec should cover Neo4j node/edge counts.
3. **Alerting channels**: Currently alerts go to `data_health_alerts` table + logs. Slack/email/Telegram forwarding is out of scope here but should be a follow-on.
4. **Role-based access**: Admin endpoints currently use a single shared token. A future spec should tie admin endpoints into the contributor identity system.
5. **Trend sparklines**: The dashboard spec mentions sparklines but does not define the data endpoint for historical trend data. Implement as a follow-on after base snapshot data accumulates.

---

## Definition of Done

- [ ] `GET /api/admin/db-status` returns valid JSON with all 6 current tables
- [ ] `data_health_snapshots` table exists and receives rows on schedule
- [ ] `data_health_alerts` table exists and captures anomalies
- [ ] `cc db-status` command works end-to-end against production
- [ ] Web dashboard page renders at `/admin/data-health`
- [ ] All 5 verification scenarios pass against production
- [ ] `runtime_events` top event types are visible, enabling investigation
- [ ] No existing tests broken by the migration or new router
