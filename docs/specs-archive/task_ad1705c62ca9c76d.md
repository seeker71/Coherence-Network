# Spec: Data Hygiene — Row Count Monitoring, Noise Detection, and Growth Anomaly Alerts

**Spec / idea ID:** `task_ad1705c62ca9c76d`  
**Related draft:** An earlier draft exists at `specs/task_a58cac25401b5d34.md` with overlapping scope; **this file** is the contract for task `task_ad1705c62ca9c76d`. Implementation should reference **this** path in commits and evidence.

## Summary

Operational visibility into relational storage is insufficient today: high-volume tables (especially `runtime_events` at ~46k rows in a young deployment) can hide runaway logging, duplicate ingestion, or retention gaps. This spec defines **data hygiene** capabilities: **(1)** a `cc db-status` command that prints per-table row counts and **growth rate** versus a stored baseline, **(2)** **alerts** when any monitored table grows faster than configured expectations, and **(3)** a **data health** surface (API + optional web dashboard) that makes anomalies and remediation hints visible to operators and reviewers.

**Baseline snapshot (reference, 2026-03-28):** `runtime_events` 46,614; `telemetry_snapshots` 2,001; `agent_tasks` 1,268; `telemetry_task_metrics` 1,372; `measurements` 450; `contribution_ledger` 530. These numbers are **not** acceptance targets; they anchor investigation (why `runtime_events` is large relative to system age) and calibration of growth thresholds.

## Purpose

Unbounded append-only telemetry can silently exhaust disk, skew dashboards, and mask real incidents. Operators need the same discipline applied to **data** as to **provider health**: measurable baselines, growth signals, and evidence that mitigation (retention, sampling, deduplication) is working. This spec prevents silent database bloat and makes “is the feature working?” answerable with **independently verifiable** metrics and API output.

## Requirements

- [ ] **R1 — Inventory** — Enumerate all application tables in the configured primary SQL store (SQLite dev / PostgreSQL prod as applicable) and report **exact row count** per table (excluding `sqlite_sequence` and other internal SQLite artifacts if present).
- [ ] **R2 — Growth rate** — Persist a **timestamped snapshot** of row counts (at least daily; configurable) and compute **absolute delta** and **percent change** per table per interval. Expose the last **N** snapshots for trend display.
- [ ] **R3 — CLI `cc db-status`** — Add `cc db-status` (alias acceptable if documented) that prints human-readable table rows, **prior snapshot count**, **delta**, **% growth**, and **age of snapshot**. Support `--json` for automation.
- [ ] **R4 — Anomaly thresholds** — Per-table **soft** and **hard** growth rules (e.g., max rows, max % growth per 24h, max absolute delta per 24h). Defaults must be conservative enough to flag `runtime_events` spikes without false alarming on tiny tables.
- [ ] **R5 — Alerts** — When a hard threshold is breached, create a **friction event** (or reuse existing monitoring/alert pipeline) with `block_type` = `data_growth_anomaly` (or agreed name), table name, counts, delta, and recommended checks (retention, duplicate tool calls, worker loop).
- [ ] **R6 — Dashboard / API** — Expose `GET /api/data-health` (or equivalent) returning JSON: tables, counts, last snapshot time, growth metrics, alert status, and **health score** (0.0–1.0) derived from whether any table is in hard breach.
- [ ] **R7 — Noise / duplication signals** — Document **investigation** steps for `runtime_events` (e.g., event type distribution, rate per hour, source); MVP may be **read-only** SQL or API facet counts, not full ML—must be **actionable** in the Verification Scenarios below.
- [ ] **R8 — Evidence over time** — Store historical snapshots so reviewers can prove “growth slowed after retention change” without SSH access (see § Improving the idea and proof).

## Improving the idea, proving it works, and clearer proof over time

| Mechanism | What it proves |
|-----------|----------------|
| **Snapshot ledger** | Immutable history of row counts; any party can compare two dates. |
| **Health score + breach reasons** | Single number to gate deploys; reasons list explains *why* score dropped. |
| **Before/after attribution** | Link friction events to remediation tasks (task IDs or commit SHAs in notes). |
| **Public API** | `curl`/`cc` verification without database credentials. |
| **Optional export** | Periodic JSON export to `docs/system_audit/` or artifact bucket (follow existing evidence patterns). |

**Definition of “working”:** (a) no table in **hard** breach for 7 consecutive days after baseline calibration, or (b) breaches are **opened** and **resolved** with documented cause (retention tuned, bug fixed), visible in friction/event history.

## Research Inputs (Required)

- `2026-03-28` — [Spec 107: Runtime Telemetry DB Precedence](specs/107-runtime-telemetry-db-precedence.md) — explains persistence paths for runtime telemetry and why `runtime_events` volume matters.
- `2026-03-28` — [Spec 135: Provider Health Alerting](specs/135-provider-health-alerting.md) — pattern for threshold-based friction events and deduplication.
- `2026-03-28` — [runtime_event_store.py](api/app/services/runtime_event_store.py) — `runtime_events` table definition and schema ensure path.
- `2026-03-28` — [friction_service.py](api/app/services/friction_service.py) — existing friction event types for alert integration.
- `2026-03-28` — [Spec 148: Coherence CLI](specs/148-coherence-cli-comprehensive.md) — where `cc` subcommands live (`cli/bin/cc.mjs`, `cli/lib/commands/`).

## Task Card (Required)

```yaml
goal: Ship data hygiene observability — db-status CLI, growth snapshots, anomaly alerts, and data-health API/dashboard contract.
files_allowed:
  - specs/task_ad1705c62ca9c76d.md
  - api/app/routers/data_health.py
  - api/app/services/data_hygiene_service.py
  - api/app/models/data_health.py
  - api/app/main.py
  - api/app/services/friction_service.py
  - cli/bin/cc.mjs
  - cli/lib/commands/db-status.mjs
  - web/app/data-health/page.tsx
  - web/components/data-health/*.tsx
  - api/tests/test_data_health_api.py
done_when:
  - GET /api/data-health returns JSON with per-table counts, growth, and health score.
  - cc db-status matches API counts for the same environment (within same request window).
  - Growth anomaly creates friction event with block_type data_growth_anomaly when threshold exceeded (test with injected counts or fixture).
  - pytest -q api/tests/test_data_health_api.py passes.
commands:
  - python3 scripts/validate_spec_quality.py --file specs/task_ad1705c62ca9c76d.md
  - cd api && pytest -q tests/test_data_health_api.py
  - node cli/bin/cc.mjs db-status --json
  - curl -sS "$API_URL/api/data-health" | jq .
constraints:
  - Do not weaken retention or delete production data without explicit operator approval; tests use fixtures.
  - No new notification providers; reuse friction/Telegram flags per spec 135 patterns.
  - Schema changes require explicit migration review if not SQLite-only additive.
```

## API Contract

### `GET /api/data-health`

**Query:** optional `?format=json` (default JSON).

**Response 200**

```json
{
  "generated_at": "2026-03-28T12:00:00Z",
  "database_kind": "sqlite|postgresql",
  "health_score": 0.95,
  "tables": [
    {
      "name": "runtime_events",
      "row_count": 46614,
      "previous_snapshot_at": "2026-03-27T12:00:00Z",
      "previous_row_count": 45000,
      "delta_24h": 1614,
      "pct_change_24h": 3.59,
      "status": "ok|warn|breach"
    }
  ],
  "open_friction_ids": [],
  "investigation_hints": [
    "Check runtime_events by event_type for duplicate tool calls"
  ]
}
```

**Response 503** — Database unreachable: `{"detail": "data_health_unavailable", "reason": "..."}`

### `GET /api/data-health/snapshots`

**Response 200** — List last N stored snapshots (metadata + per-table counts) for auditing.

## Data Model (if applicable)

```yaml
DataHygieneSnapshot:
  properties:
    id: { type: string, format: uuid }
    captured_at: { type: string, format: date-time }
    table_counts: { type: object, additionalProperties: { type: integer, minimum: 0 } }
    source: { type: string, enum: [scheduled, manual, api] }

DataHygieneConfig:
  properties:
    tables_monitored:
      type: array
      items: { type: string }
    max_pct_growth_24h_per_table:
      type: object
      additionalProperties: { type: number }
    max_absolute_delta_24h:
      type: object
      additionalProperties: { type: integer }
```

Persistence: prefer a **dedicated table** `data_hygiene_snapshots` in the primary app DB, or a JSON artifact under `data/` with documented rotation—implementation choice must be **listed in files** section at implementation time.

## Files to Create/Modify (implementation)

- `specs/task_ad1705c62ca9c76d.md` — this spec.
- `api/app/services/data_hygiene_service.py` — snapshot capture, growth math, threshold evaluation.
- `api/app/models/data_health.py` — Pydantic response models.
- `api/app/routers/data_health.py` — FastAPI routes.
- `api/app/main.py` — include router.
- `api/app/services/friction_service.py` — register `data_growth_anomaly` handling if needed.
- `cli/lib/commands/db-status.mjs` + `cli/bin/cc.mjs` — wire subcommand.
- `web/app/data-health/page.tsx` — optional dashboard (MVP can be API-only with follow-up).
- `api/tests/test_data_health_api.py` — contract tests.

## Acceptance Tests

- `api/tests/test_data_health_api.py::test_data_health_returns_table_counts`
- `api/tests/test_data_health_api.py::test_data_health_growth_computed_from_snapshots`
- `api/tests/test_data_health_api.py::test_data_growth_breach_creates_friction_event`
- `api/tests/test_data_health_api.py::test_data_health_503_when_db_unconfigured`

## Verification Scenarios

These scenarios are **contracts** for production and staging review. A reviewer must be able to execute them without ambiguity.

### Scenario 1 — API returns row counts and health score

- **Setup:** API running against a database that has at least `runtime_events` and `agent_tasks` tables with known seed or production counts.
- **Action:** `curl -sS "$API_URL/api/data-health" -H "Accept: application/json"`
- **Expected:** HTTP 200; JSON includes `health_score` between 0.0 and 1.0; `tables` array has entries for `runtime_events` and `agent_tasks` with `row_count` matching `SELECT COUNT(*)` for those tables (same transaction window).
- **Edge:** If `DATABASE_URL` is unset and no SQLite file exists, **Expected:** HTTP 503 with `detail` containing `data_health_unavailable` (not HTTP 500 stack trace).

### Scenario 2 — `cc db-status` matches API

- **Setup:** `COHERENCE_API_URL` points to the same environment as Scenario 1; CLI installed from repo `cli/`.
- **Action:** `node cli/bin/cc.mjs db-status --json`
- **Expected:** Exit code 0; JSON or structured output lists `runtime_events` with same `row_count` as `/api/data-health` when run within 60 seconds of each other.
- **Edge:** Invalid API URL (`COHERENCE_API_URL=http://127.0.0.1:9`) **Expected:** non-zero exit and stderr or JSON `error` field explaining connection failure (not silent empty).

### Scenario 3 — Growth rate reflects snapshot delta

- **Setup:** Two snapshots exist for the same table with `previous_row_count` = 1000 and current count = 1100; or test fixtures inject this.
- **Action:** `curl -sS "$API_URL/api/data-health"` and inspect `delta_24h` / `pct_change_24h` for that table.
- **Expected:** `delta_24h` = 100; `pct_change_24h` ≈ 10.0 (within floating tolerance).
- **Edge:** If no prior snapshot exists, **Expected:** `previous_row_count` null or 0 and growth fields documented as `null` or `0` with `status` = `ok` (no false breach).

### Scenario 4 — Hard breach raises friction

- **Setup:** Configure threshold so `runtime_events` row growth of +5000 in 24h breaches; inject snapshot or simulate count increase in test.
- **Action:** Trigger evaluation (scheduled job or `POST /api/data-health/snapshot` if exposed for admin).
- **Expected:** New friction event with `block_type` = `data_growth_anomaly` (or agreed constant) and `status` = `open`; `GET /api/data-health` lists `open_friction_ids` non-empty or `health_score` drops below 1.0 with reason.
- **Edge:** Duplicate evaluation in the same breach window **Expected:** deduplicated friction (no duplicate events per spec 135 pattern), or idempotent notes update.

### Scenario 5 — Snapshots history for audit

- **Setup:** At least three daily snapshots stored.
- **Action:** `curl -sS "$API_URL/api/data-health/snapshots?limit=5"`
- **Expected:** HTTP 200; array length ≥ 3; each entry has `captured_at` ISO8601 UTC and `table_counts` object.
- **Edge:** `limit=9999` **Expected:** capped to server max (e.g., 100) with `X-Total-Count` or `detail` explaining cap (not OOM).

## Concurrency Behavior

- **Read operations:** Snapshot reads are safe; counts use `COUNT(*)` or approximate where documented.
- **Write operations:** Snapshot writes must be serialized per environment to avoid duplicate “same second” snapshots from cron overlap.
- **Recommendation:** Use a single advisory lock or `INSERT ... ON CONFLICT` for snapshot idempotency.

## Verification (CI / local)

```bash
python3 scripts/validate_spec_quality.py --file specs/task_ad1705c62ca9c76d.md
cd api && pytest -q tests/test_data_health_api.py
node cli/bin/cc.mjs db-status --json
```

## Out of Scope

- Automatic deletion of rows (retention enforcement) — separate spec; this spec only **observes** and **alerts**.
- Full ML-based anomaly detection; first version is **rule-based** thresholds.
- Neo4j graph size monitoring (relational store only unless explicitly extended).

## Risks and Assumptions

- **Risk:** `COUNT(*)` on huge tables is slow; **mitigation:** optional approximate counts for PostgreSQL (`reltuples`) behind flag, or off-peak scheduling.
- **Risk:** False positives on small tables; **mitigation:** minimum row floor before % thresholds apply.
- **Assumption:** Primary operational DB is reachable from API and CLI uses the same API truth source (not direct DB from CLI in cloud without tunnel).

## Known Gaps and Follow-up Tasks

- Follow-up: **Retention policy spec** for `runtime_events` tied to `runtime_events` cardinality investigation.
- Follow-up: **Web dashboard** polish if MVP ships API-only.
- Follow-up: **Export** of weekly snapshot to `docs/system_audit/` for offline audit.

## Evidence That This Idea Is Realized

Independently verifiable evidence (any party):

1. **Public API:** `GET https://api.coherencycoin.com/api/data-health` returns 200 with schema above after deploy.
2. **CLI:** `npm i -g coherence-cli` (or repo `node cli/bin/cc.mjs`) and `cc db-status --json` succeed against production URL.
3. **Attestation:** Contributor record via `POST /api/contributions` or `cc contribute` referencing spec ID `task_ad1705c62ca9c76d` and deployment SHA.
4. **Optional:** Screenshot of `/data-health` page when web scope is delivered.

## Failure/Retry Reflection

- **Failure mode:** Snapshot job fails silently — **blind spot:** no baseline for growth. **Next action:** health endpoint returns `last_snapshot_at` stale warning when older than 48h.
- **Failure mode:** `runtime_events` grows due to bug — **next action:** Scenario 4 friction + investigation_hints point to `event_type` breakdown endpoint.

## Decision Gates

- Production **hard** thresholds require operator sign-off after 7 days of baseline data.
- Schema migration (if any) must pass existing DB migration review.

## See also

- [Spec 107: Runtime Telemetry DB Precedence](specs/107-runtime-telemetry-db-precedence.md)
- [Spec 135: Provider Health Alerting](specs/135-provider-health-alerting.md)
- [Spec 136: Data-Driven Timeout Dashboard](specs/136-data-driven-timeout-dashboard.md)
