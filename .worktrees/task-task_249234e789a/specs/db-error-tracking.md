---
idea_id: developer-experience
status: draft
source:
  - file: api/app/routers/health.py
    symbols: [_check_schema(), HealthResponse, health()]
  - file: api/app/main.py
    symbols: [_ensure_db_tables(), _warm_startup_caches(), _record_startup_friction_events()]
requirements:
  - "GET /api/health returns schema_ok=false and schema_missing_tables=[...] when any core table is absent"
  - "Missing tables logged at ERROR level (not WARNING) in both _check_schema() and _ensure_db_tables()"
  - "Each missing table recorded as a high-severity friction event at startup (via _record_startup_friction_events)"
  - "HealthResponse gains schema_missing_tables: list[str] field alongside schema_ok boolean"
  - "_ensure_db_tables() exception handler escalates from WARNING to ERROR"
done_when:
  - "GET /api/health returns schema_ok=true and schema_missing_tables=[] when all tables exist"
  - "Dropping a core table causes health to return schema_ok=false with the table name in schema_missing_tables"
  - "Application log contains at least one ERROR-level entry naming the missing table"
  - "A friction event with block_type=missing_table and severity=high exists in the friction ledger after startup with a missing table"
  - "all tests pass"
test: "cd api && python -m pytest tests/test_health.py -q"
constraints:
  - "Health check must stay fast (<200ms p99); check table existence only, not column schema"
  - "Friction event recording must not raise or block the health response — wrap in try/except"
  - "Do not modify tests to force passing behavior"
  - "Backward-compatible: schema_missing_tables defaults to [] so existing consumers see no change when schema is healthy"
---

# Spec: DB Error Tracking — Schema Validation, Friction Events, Error Logging

## Purpose

Silent database failures are invisible until they cause data loss or confusing 500s in production. The health endpoint already carries a `schema_ok` boolean, but a missing table is logged only at WARNING level and never surfaces in the friction telemetry system. This spec closes all three gaps: ERROR-level logging, friction event recording, and structured table-level detail in the health response. Any operator polling `/api/health` or reading the logs will see a clear, actionable signal the moment a core table disappears.

## Requirements

- [ ] **R1 — ERROR-level logging**: `_check_schema()` in `health.py` must log at `logger.error(...)` (not `logger.warning(...)`) when any core table is missing, naming each absent table explicitly.

- [ ] **R2 — Structured health field**: `HealthResponse` gains a new field `schema_missing_tables: list[str]` (default `[]`). When `schema_ok=False`, the list contains the names of every absent table. Existing consumers see no change when the schema is healthy.

- [ ] **R3 — Health endpoint wires new field**: `health()` calls the updated `_check_schema()` which returns `(bool, list[str])` instead of `bool`, and passes the missing-tables list into `HealthResponse`.

- [ ] **R4 — Startup friction events for missing tables**: `_warm_startup_caches()` in `main.py` calls `_check_schema()` after `_ensure_db_tables()` and appends any missing table name to the existing `startup_errors` list. `_record_startup_friction_events()` already turns those entries into high-severity friction events — no change needed there.

- [ ] **R5 — _ensure_db_tables() escalates log level**: The `except` block in `_ensure_db_tables()` changes from `_startup_logger.warning(...)` to `_startup_logger.error(...)` so startup DB bootstrap failures appear at the same severity as runtime schema failures.

## Research Inputs

- `2026-04-26` — Code audit of `api/app/routers/health.py` — `_check_schema()` currently logs at WARNING; `schema_ok` boolean exists but missing-table detail is absent.
- `2026-04-26` — Code audit of `api/app/main.py` — `_record_startup_friction_events()` already handles graph-node startup errors with high-severity events; schema check is not yet wired into that path.
- `2026-04-26` — `ideas/developer-experience.md` — "Missing tables recorded as friction events with table name, expected schema, and timestamp."

## API Contract

### `GET /api/health`

**Response 200 — healthy schema**
```json
{
  "status": "ok",
  "version": "1.2.3",
  "timestamp": "2026-04-26T12:00:00Z",
  "schema_ok": true,
  "schema_missing_tables": [],
  "...": "other existing fields unchanged"
}
```

**Response 200 — degraded schema**
```json
{
  "status": "ok",
  "version": "1.2.3",
  "timestamp": "2026-04-26T12:01:00Z",
  "schema_ok": false,
  "schema_missing_tables": ["contributions"],
  "...": "other existing fields unchanged"
}
```

Note: the endpoint always returns 200. Operators distinguish healthy from degraded by inspecting `schema_ok`. A future alerting spec may change this to 207, but that is out of scope here.

## Data Model

```yaml
HealthResponse (additions only):
  schema_missing_tables: list[str]  # default []
  # schema_ok already present — no change to type
```

`_check_schema()` return type changes from `bool` to `tuple[bool, list[str]]`:

```python
# Before
def _check_schema() -> bool: ...

# After
def _check_schema() -> tuple[bool, list[str]]:
    """Returns (all_present, missing_table_names)."""
```

## Files to Create/Modify

- `api/app/routers/health.py` — update `_check_schema()` return type to `(bool, list[str])`; change `logger.warning` → `logger.error`; update `HealthResponse` with `schema_missing_tables` field; update `health()` to unpack tuple and populate new field.
- `api/app/main.py` — in `_warm_startup_caches()`, call `_check_schema()` after `_ensure_db_tables()` and append missing table names to `startup_errors`; change `_ensure_db_tables()` except-block log from WARNING to ERROR.

## Acceptance Tests

- `api/tests/test_health.py` — extend or add tests:
  - `test_health_schema_ok_true` — healthy DB returns `schema_ok=true`, `schema_missing_tables=[]`
  - `test_health_schema_ok_false_with_missing_table` — drop a table, assert `schema_ok=false` and table name in `schema_missing_tables`

## Verification Scenarios

### Scenario 1 — Healthy schema (baseline)

```bash
curl -s https://api.coherencycoin.com/api/health | jq '{schema_ok, schema_missing_tables}'
```

**Expected output:**
```json
{
  "schema_ok": true,
  "schema_missing_tables": []
}
```

### Scenario 2 — schema_missing_tables field is present in response

```bash
curl -s https://api.coherencycoin.com/api/health | jq 'has("schema_missing_tables")'
```

**Expected output:**
```
true
```

### Scenario 3 — Application log shows ERROR (not WARNING) on missing table

After startup with a missing table (simulate by pointing to an empty DB or dropping a table in dev):

```bash
grep -E "ERROR.*schema|ERROR.*missing.*table|ERROR.*contributions" api/logs/api.log | head -5
```

**Expected:** At least one line containing `ERROR` and a core table name.

### Scenario 4 — Friction events recorded for missing table at startup

```bash
curl -s https://api.coherencycoin.com/api/friction/events?stage=startup&block_type=missing_table | \
  jq '[.[] | select(.severity=="high")] | length'
```

**Expected:** Integer `>= 1` when a table was absent at last startup.

### Scenario 5 — No regression: all existing health fields still present

```bash
curl -s https://api.coherencycoin.com/api/health | jq 'keys | sort'
```

**Expected:** All previously-present keys (status, version, timestamp, started_at, uptime_seconds, uptime_human, schema_ok, smart_reap_available, recent_outcomes, integrity_compromised) plus `schema_missing_tables`.

## Out of Scope

- Column-level schema validation (checking that columns match expected types) — existence check only.
- Changing the HTTP status code of `/api/health` based on schema health.
- Auto-remediation (running migrations when tables are absent).
- Alerting or notification systems — this spec only surfaces the signal; routing it is a separate concern.

## Risks and Assumptions

- **Risk**: `_check_schema()` is called on every `/api/health` request. If the DB is slow, this adds latency. Mitigation: the check is a single `SELECT 1 FROM {table} LIMIT 1` per table with no joins — negligible overhead under normal conditions. The existing `schema_ok` check already runs this; the change only adds error-level logging and a return-value refactor.
- **Assumption**: The three core tables (`contributions`, `contributors`, `assets`) are the authoritative sentinel set for schema health. Adding more tables to this check is out of scope but is a natural follow-on.
- **Assumption**: `_record_startup_friction_events()` already handles arbitrary string labels in `startup_errors`; routing missing table names through it requires no structural change to that function.
- **Risk**: If `_check_schema()` is called at startup before the DB is up, it will fail and record spurious friction events. Mitigation: call it after `_ensure_db_tables()` completes, so the DB bootstrap has already been attempted.
