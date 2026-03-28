# Spec 177: Data Hygiene Monitor

## Status: Draft 2026-03-28

## Purpose

The Coherence Network database contains tables that have grown without visibility into their
growth rate, noise content, or health. `runtime_events` at 46,614 rows is suspicious for a
young system — it suggests unbounded event fanout, missing TTL, or a logging misconfiguration
that fills the table faster than any human can catch.

This spec defines:
1. A `cc db-status` command that reports per-table row counts and daily growth rates.
2. A background alerting mechanism that fires when a table grows faster than its configured
   threshold.
3. A `/api/db/health` endpoint and a dashboard panel showing data health over time.

The goal is to make data growth **visible, comparable, and actionable** so the team can
catch anomalies early instead of discovering them at 2 AM during a production incident.

---

## Background — Current Row Counts (2026-03-28)

| Table | Row Count | Notes |
|---|---|---|
| `runtime_events` | 46,614 | **Suspicious** — very high for a young system |
| `telemetry_snapshots` | 2,001 | Moderate — needs growth tracking |
| `agent_tasks` | 1,268 | Expected |
| `telemetry_task_metrics` | 1,372 | Expected |
| `measurements` | 450 | Low |
| `contribution_ledger` | 530 | Low |

`runtime_events` is the primary concern: at ~46k rows with no configured cleanup, the table
may be storing events with no deduplication, no TTL, and no circuit breaker.

---

## Requirements

### R1 — cc db-status Command Output

The `cc db-status` command (or `GET /api/db/health`) must return a structured report for
every significant table in the database showing current row counts, 24h delta, 7d delta,
and alert status. Example:

```
Table                    Rows     +1d      +7d     Alert
────────────────────────────────────────────────────────
runtime_events           46,614   +3,812   +21,200  OVER THRESHOLD
telemetry_snapshots       2,001      +82      +430
agent_tasks               1,268      +14       +90
telemetry_task_metrics    1,372      +18      +105
measurements                450       +5       +28
contribution_ledger         530       +4       +22
```

- **Rows**: current total row count.
- **+1d**: rows added in the last 24 hours (requires a `created_at` or `recorded_at` index).
- **+7d**: rows added in the last 7 days.
- **Alert**: fires if the 24h growth rate exceeds the configured threshold for that table.

When no `created_at` index exists on a table, the delta columns show `n/a` and a note
explains that growth tracking requires a timestamp column.

### R2 — Configurable Growth Thresholds

A config file `api/config/data_hygiene.json` stores per-table thresholds:

```json
{
  "thresholds": {
    "runtime_events": { "max_rows_per_day": 2000, "max_total_rows": 100000 },
    "telemetry_snapshots": { "max_rows_per_day": 500, "max_total_rows": 50000 },
    "agent_tasks": { "max_rows_per_day": 300, "max_total_rows": 20000 },
    "telemetry_task_metrics": { "max_rows_per_day": 300, "max_total_rows": 20000 },
    "measurements": { "max_rows_per_day": 200, "max_total_rows": 10000 },
    "contribution_ledger": { "max_rows_per_day": 100, "max_total_rows": 10000 }
  },
  "snapshot_interval_hours": 6,
  "retention_days": 30
}
```

- `max_rows_per_day`: alert if a table adds more rows than this in 24 hours.
- `max_total_rows`: alert if the total row count exceeds this.
- `snapshot_interval_hours`: how often the background job records a row-count snapshot.
- `retention_days`: how long to keep `db_row_count_snapshots` records.

### R3 — Row Count Snapshot Table

A new table `db_row_count_snapshots` persists historical counts so growth rates can be
computed accurately across restarts:

```sql
CREATE TABLE db_row_count_snapshots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name  TEXT NOT NULL,
    row_count   INTEGER NOT NULL,
    recorded_at TIMESTAMP NOT NULL DEFAULT (datetime("now"))
);
CREATE INDEX idx_db_row_count_snapshots_table_recorded
    ON db_row_count_snapshots (table_name, recorded_at DESC);
```

For PostgreSQL, `AUTOINCREMENT` becomes `SERIAL` or `BIGSERIAL`.

### R4 — Background Snapshot Job

A background task runs every N hours (default: 6) and:
1. Queries `SELECT COUNT(*) FROM <table>` for each monitored table.
2. Inserts a row into `db_row_count_snapshots`.
3. Compares the current count to the snapshot from 24h ago; if the delta exceeds the
   configured threshold, emits a structured WARNING log:
   `DATA_HYGIENE_ALERT table=runtime_events delta_24h=3812 threshold=2000 current=46614`
4. Purges snapshots older than `retention_days` to prevent the snapshots table from
   growing indefinitely.

The job is registered in `api/app/main.py` via FastAPI lifespan or asyncio background task.

### R5 — /api/db/health Endpoint

`GET /api/db/health` returns JSON:

```json
{
  "checked_at": "2026-03-28T07:45:00Z",
  "tables": [
    {
      "table": "runtime_events",
      "row_count": 46614,
      "delta_24h": 3812,
      "delta_7d": 21200,
      "threshold_24h": 2000,
      "status": "alert",
      "note": "Growth rate 3812/day exceeds threshold 2000/day"
    },
    {
      "table": "telemetry_snapshots",
      "row_count": 2001,
      "delta_24h": 82,
      "delta_7d": 430,
      "threshold_24h": 500,
      "status": "ok",
      "note": null
    }
  ],
  "overall_status": "alert",
  "alert_count": 1
}
```

`status` is one of: `"ok"`, `"alert"`, `"unknown"` (no historical snapshot available).

### R6 — Dashboard Panel (cc db-status CLI)

The `cc db-status` command is added to the CLI tool. It calls `GET /api/db/health` and
renders the table above in the terminal. A `--json` flag returns raw JSON.

The dashboard panel at `/status` (Next.js) shows a card per table with:
- Current row count (large number)
- 24h delta (green if under threshold, red if over)
- A sparkline of the last 7 days (optional, Phase 2)

### R7 — runtime_events Investigation

The spec explicitly requires an investigation step before implementing the alert so we
understand whether the 46k rows represent:
- (a) Correct but unbounded event logging (missing TTL)
- (b) Duplicate events from agent retry storms
- (c) Events that should have been purged by a TTL policy

The implementation MUST include a diagnostic script: `api/scripts/diagnose_runtime_events.py`

This script emits:
- Top 10 event types by count
- Top 10 source agents by count
- Row count per day for the last 14 days
- Estimated TTL recommendation based on growth rate

This runs once manually; the output informs the threshold values in `data_hygiene.json`.

---

## Files Allowed

```yaml
files_allowed:
  - api/app/routers/db_health.py
  - api/app/services/data_hygiene_service.py
  - api/app/models/db_row_count_snapshot.py
  - api/config/data_hygiene.json
  - api/scripts/diagnose_runtime_events.py
```

No changes to existing routers, models, or services outside this list.

---

## Data Model

### ORM: DbRowCountSnapshot

```python
# api/app/models/db_row_count_snapshot.py
from sqlalchemy import Column, Integer, String, DateTime
from app.services.unified_db import Base
import datetime

class DbRowCountSnapshot(Base):
    __tablename__ = "db_row_count_snapshots"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    table_name  = Column(String, nullable=False, index=True)
    row_count   = Column(Integer, nullable=False)
    recorded_at = Column(DateTime, nullable=False,
                         default=lambda: datetime.datetime.utcnow())
```

---

## API Changes

### New endpoint

`GET /api/db/health`

- No auth required (same as `/api/health`).
- Returns `200` always (alert is in the body, not the HTTP status code).
- Response is a `DbHealthResponse` Pydantic model.

### Registration in api/app/main.py

```python
from app.routers import db_health
app.include_router(db_health.router, prefix="/api")
```

---

## Service: data_hygiene_service.py

Key functions:

```python
def get_monitored_tables() -> list[str]:
    """Return table names from data_hygiene.json thresholds."""

def record_snapshot(session: Session) -> list[DbRowCountSnapshot]:
    """Query COUNT(*) for all monitored tables; persist snapshots."""

def get_current_counts(session: Session) -> dict[str, int]:
    """Return {table_name: row_count} for all monitored tables."""

def get_delta(session: Session, table_name: str, hours: int = 24) -> int | None:
    """Compute row count delta over the last N hours from snapshots.
    Returns None if insufficient snapshot history."""

def compute_health_report(session: Session) -> DbHealthReport:
    """Assemble the full health report used by /api/db/health."""

def purge_old_snapshots(session: Session, retention_days: int = 30) -> int:
    """Delete snapshots older than retention_days. Returns count deleted."""

async def run_background_snapshot_loop(interval_hours: float = 6.0) -> None:
    """Asyncio loop: record_snapshot -> check thresholds -> log alerts."""
```

---

## Verification Scenarios

### Scenario 1 — GET /api/db/health returns all monitored tables

**Setup:** API is running with a populated database (any state).

**Action:**
```bash
curl -s https://api.coherencycoin.com/api/db/health | jq ".tables[].table"
```

**Expected:** Output lists all six tables from `data_hygiene.json`:
```
"runtime_events"
"telemetry_snapshots"
"agent_tasks"
"telemetry_task_metrics"
"measurements"
"contribution_ledger"
```

**Edge:** If `data_hygiene.json` is missing, endpoint returns `503` with
`{"detail": "data hygiene config not found"}`.

---

### Scenario 2 — Alert fires for runtime_events over threshold

**Setup:** `runtime_events` has 46,614 rows. A snapshot was recorded 24h ago showing
42,800 rows. Threshold is `max_rows_per_day: 2000`.

**Action:**
```bash
curl -s https://api.coherencycoin.com/api/db/health
```

**Expected:** The `runtime_events` entry in the response shows:
```json
{
  "table": "runtime_events",
  "row_count": 46614,
  "delta_24h": 3814,
  "threshold_24h": 2000,
  "status": "alert",
  "note": "Growth rate 3814/day exceeds threshold 2000/day"
}
```
And `overall_status` is `"alert"` and `alert_count` >= 1.

**Edge:** If no snapshot exists for 24h ago, `delta_24h` is `null` and `status` is
`"unknown"` (not `"alert"` — cannot alert without baseline).

---

### Scenario 3 — cc db-status prints human-readable table

**Setup:** API is reachable. At least one snapshot has been recorded.

**Action:**
```bash
cc db-status
```

**Expected:** Terminal output shows a formatted table with all monitored tables.
Any table in alert state shows `OVER THRESHOLD` in the Alert column.
Tables with insufficient history show `n/a` for delta columns.

**Edge:** `cc db-status --json` returns raw JSON matching the `/api/db/health` schema.

---

### Scenario 4 — Snapshot is recorded and persisted

**Setup:** `db_row_count_snapshots` table exists but is empty.

**Action:**
```bash
python api/scripts/diagnose_runtime_events.py --record-snapshot
```

**Expected:** After running:
```sql
SELECT table_name, row_count FROM db_row_count_snapshots ORDER BY recorded_at DESC;
-- Returns 6 rows (one per monitored table)
```

**Edge:** Running the snapshot twice within 1 minute does not fail — both rows are
stored (snapshots are append-only timeseries, no deduplication).

---

### Scenario 5 — Old snapshots are purged

**Setup:** `db_row_count_snapshots` contains rows dated 45 days ago.

**Action:**
```python
from app.services import data_hygiene_service, unified_db
with unified_db.get_session() as s:
    n = data_hygiene_service.purge_old_snapshots(s, retention_days=30)
    print(f"Purged {n} rows")
```

**Expected:** Output is `Purged N rows` where N > 0. Subsequent query confirms no rows
with `recorded_at < now() - 30 days` remain.

**Edge:** Running purge on an empty table returns `Purged 0 rows` without error.

---

## Risks and Assumptions

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| `runtime_events` has no `created_at` column | Medium | High | Investigate schema; use snapshot deltas as fallback |
| Background job grows snapshots unboundedly | High | Medium | TTL purge runs at each snapshot cycle |
| `COUNT(*)` slow on large PostgreSQL tables | Low | Low | Use `pg_stat_user_tables.n_live_tup` in Phase 2 |
| Alert fatigue if threshold too low | Medium | Medium | Thresholds are per-table in config; tunable without code changes |
| `runtime_events` root cause unknown | High | High | `diagnose_runtime_events.py` runs first to inform thresholds |

---

## Known Gaps and Follow-up Tasks

1. **Sparkline chart** — dashboard shows only current counts; sparkline history is Phase 2.
2. **Auto-purge policy for runtime_events** — this spec diagnoses but does not clean.
   A follow-up spec should define the TTL and implement a cleanup cron.
3. **PostgreSQL fast count** — `SELECT COUNT(*)` does full table scan.
   For tables >1M rows, use `pg_stat_user_tables.n_live_tup` approximation.
4. **Alert delivery** — log-level alerts are Phase 1. Phase 2 routes alerts to Telegram/Discord.
5. **Alert deduplication** — same table firing every 6h is noisy. Phase 2 adds cooldown window.

---

## How This Proves It Is Working

The system is working when all of the following are true simultaneously:

1. `curl https://api.coherencycoin.com/api/db/health` returns HTTP 200 with JSON
   listing all monitored tables.
2. At least one table has `delta_24h` not null (proves the snapshot job ran).
3. `runtime_events` shows `status: "alert"` (confirms anomaly detected) OR
   growth has been reduced below threshold (confirms a fix was applied).
4. `cc db-status` renders a human-readable table in the terminal.
5. `diagnose_runtime_events.py` produces output explaining `runtime_events` contents
   (top event types, top agents, daily growth).

These conditions are independently verifiable by any developer with API access.

---

## Task Card

```yaml
goal: Implement row-count monitoring, growth anomaly alerts, and cc db-status dashboard
idea_id: task_17675bc995972056
spec: 177-data-hygiene-monitor.md
files_allowed:
  - api/app/routers/db_health.py
  - api/app/services/data_hygiene_service.py
  - api/app/models/db_row_count_snapshot.py
  - api/config/data_hygiene.json
  - api/scripts/diagnose_runtime_events.py
done_when:
  - GET /api/db/health returns all 6 monitored tables with row counts
  - Tables in alert state show status="alert" and a descriptive note
  - cc db-status renders a human-readable table in the terminal
  - Background snapshot job records counts every 6 hours
  - diagnose_runtime_events.py runs and explains runtime_events content
commands:
  - curl https://api.coherencycoin.com/api/db/health
  - cc db-status
  - python api/scripts/diagnose_runtime_events.py
```
