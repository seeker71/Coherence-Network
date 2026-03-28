# Spec: Data hygiene — DB row counts, growth, and health dashboard

## Purpose

Operational tables (`runtime_events`, automation telemetry, `agent_tasks`, etc.) can accumulate noise or leak retention bugs. This feature exposes **per-table row counts**, **growth rate between samples**, **anomaly alerts**, and a **web dashboard** plus **`cc db-status`** so operators can prove whether data volume is healthy and whether monitoring is active over time.

## Requirements

- [ ] Expose current row counts for the canonical high-volume tables used in production monitoring.
- [ ] Persist periodic samples so **growth rate** (rows per hour and percent change vs previous sample) is computable.
- [ ] Emit **alerts** when growth exceeds configurable thresholds (percentage and absolute delta), with stronger sensitivity for `runtime_events`.
- [ ] Provide **`cc db-status`** CLI output aligned with the API payload.
- [ ] Provide a **web dashboard** at `/data-health` that renders the same JSON for humans.

## Research Inputs (Required)

- `2024-06-01` - [PostgreSQL COUNT(*) performance notes](https://www.postgresql.org/docs/current/sql-select.html) — full table counts are acceptable for small/medium ops tables; documented as operational cost.
- `2026-03-28` - Internal task `task_0a82df4ffbb461f9` — baseline row counts and motivation (runtime_events volume suspicious for a young system).

## Task Card

```yaml
goal: Ship DB row-count monitoring with growth, alerts, CLI, and dashboard.
files_allowed:
  - specs/data-hygiene-db-monitoring.md
  - api/app/services/data_hygiene_service.py
  - api/app/routers/data_hygiene.py
  - api/app/services/unified_models.py
  - api/app/main.py
  - api/tests/test_data_hygiene.py
  - cli/bin/cc.mjs
  - cli/lib/commands/db_status.mjs
  - web/app/data-health/page.tsx
done_when:
  - GET /api/data-hygiene/status returns tables, counts, growth, alerts
  - cc db-status prints the same summary (or JSON with --json)
  - pytest api/tests/test_data_hygiene.py passes
commands:
  - cd api && .venv/bin/pytest -v tests/test_data_hygiene.py
  - curl -s "$API/api/data-hygiene/status?record=false"
constraints:
  - Do not modify unrelated tests; fix implementation if tests fail.
```

## API Contract

### `GET /api/data-hygiene/status`

**Query**

- `record` (bool, default `false`): when `true`, insert a new sample row per monitored table after computing counts (enables growth on next request).

**Response 200**

```json
{
  "captured_at": "2026-03-28T12:00:00+00:00",
  "tables": [
    {
      "key": "runtime_events",
      "sql_table": "runtime_events",
      "row_count": 46614,
      "previous_count": 45000,
      "previous_captured_at": "2026-03-27T12:00:00+00:00",
      "delta_rows": 1614,
      "hours_since_previous": 24.0,
      "growth_rows_per_hour": 67.25,
      "growth_pct_vs_previous": 3.59
    }
  ],
  "alerts": [
    {
      "severity": "warning",
      "table_key": "runtime_events",
      "message": "runtime_events grew 25.0% since last sample (+5000 rows).",
      "delta_rows": 5000,
      "growth_pct_vs_previous": 25.0
    }
  ],
  "meta": {
    "sample_history_rows": 120,
    "insufficient_history": false,
    "health": "degraded"
  }
}
```

`meta.health` is `ok` | `degraded` | `critical` from worst alert severity present.

### `GET /api/data-hygiene/alerts`

Returns `{ "alerts": [...], "captured_at": "..." }` — same alert list as status (no table listing).

## Data Model

```yaml
DataHygieneSampleRecord:
  table_name: string (physical SQL table name)
  row_count: int
  captured_at: datetime (UTC)
```

Samples are append-only; growth compares the latest two samples per table.

## Files to Create/Modify

- `specs/data-hygiene-db-monitoring.md` — this spec
- `api/app/services/data_hygiene_service.py` — ORM model, counts, samples, alerts
- `api/app/routers/data_hygiene.py` — HTTP routes
- `api/app/services/unified_models.py` — import model for metadata registration
- `api/app/main.py` — register router
- `api/tests/test_data_hygiene.py` — service + API tests
- `cli/lib/commands/db_status.mjs` — CLI
- `cli/bin/cc.mjs` — `db-status` command
- `web/app/data-health/page.tsx` — dashboard

## Monitored tables (logical keys)

| key | SQL table |
|-----|-----------|
| runtime_events | runtime_events |
| telemetry_snapshots | telemetry_automation_usage_snapshots |
| agent_tasks | agent_tasks |
| telemetry_task_metrics | telemetry_task_metrics |
| measurements | node_measurement_summaries |
| contribution_ledger | contribution_ledger |

## Acceptance Tests

- `api/tests/test_data_hygiene.py::test_row_counts_returned`
- `api/tests/test_data_hygiene.py::test_growth_computed_after_two_samples`
- `api/tests/test_data_hygiene.py::test_alerts_on_fast_growth`

## Verification Scenarios

### Scenario 1 — Status returns counts (no history)

- **Setup:** API running with empty `data_hygiene_samples` (or fresh SQLite test DB).
- **Action:** `curl -sS "$API/api/data-hygiene/status?record=false"`
- **Expected:** HTTP 200, JSON has `tables` array with six entries, each `row_count` is a non-negative integer, `previous_count` is null or omitted, `alerts` is empty or informational only, `meta.insufficient_history` is true when no prior sample exists.
- **Edge:** Invalid query `record=maybe` treated as false (or 422 for strict validation — document actual behavior).

### Scenario 2 — Growth rate after two samples

- **Setup:** `curl -sS "$API/api/data-hygiene/status?record=true"` twice with at least 1 second between calls (or test inserts two samples via service).
- **Action:** `curl -sS "$API/api/data-hygiene/status?record=false"`
- **Expected:** For tables with stable or known data, `previous_count` matches first sample, `delta_rows` = second minus first, `growth_rows_per_hour` is numeric (not NaN).
- **Edge:** Single sample only — no false critical alerts solely from missing history.

### Scenario 3 — CLI mirrors API

- **Setup:** `API_URL` or hub URL points at running API.
- **Action:** `cc db-status` then `cc db-status --json`
- **Expected:** Human table lists the same logical keys and row counts as `/api/data-hygiene/status`; JSON mode prints parseable JSON including `tables` length 6.
- **Edge:** API unreachable — CLI exits non-zero or prints error (not a stack trace).

### Scenario 4 — Dashboard loads

- **Setup:** Web dev or production with API rewrite configured.
- **Action:** Open `/data-health` in browser (or `curl -sI` for 200 on page).
- **Expected:** Page shows heading "Data health", fetches `/api/data-hygiene/status`, displays row counts and highlights when `alerts` non-empty.
- **Edge:** API error — page shows error string, not blank white screen.

### Scenario 5 — Alert on synthetic spike (pytest)

- **Setup:** Test DB with two samples for `runtime_events` where second is +50% rows vs first above min delta.
- **Action:** Call `evaluate_alerts` or GET status in test.
- **Expected:** At least one alert with `severity` warning or higher including `runtime_events` in message/table_key.
- **Edge:** Zero rows table — no division-by-zero in growth_pct.

## Evidence this idea is working (independent verification)

- **Live API:** `GET https://api.coherencycoin.com/api/data-hygiene/status` returns non-empty `tables` and `captured_at` on a deployed build that includes this spec.
- **Web:** `https://coherencycoin.com/data-health` renders the dashboard (200).
- **Proof over time:** After enabling `record=true` on a schedule (external cron) or manual samples, `growth_rows_per_hour` and `previous_captured_at` populate — stored samples in `data_hygiene_samples` prove the feature is not a one-shot count.

## Verification

- Manual: scenarios above on staging/production after deploy.
- Automated: `pytest api/tests/test_data_hygiene.py`.

## Risks and Assumptions

- **Risk:** `COUNT(*)` on very large tables can be slow; mitigated by scope (ops tables only) and not recording on every request by default.
- **Assumption:** All monitored tables exist in unified DB schema; if a table is missing in a dev copy, count returns 0 and optional skip flag in meta.

## Known Gaps and Follow-up Tasks

- Scheduled sampling via worker/cron (not in this spec — caller passes `record=true`).
- Push alerts to Telegram/friction — future spec if product wants automated paging.
