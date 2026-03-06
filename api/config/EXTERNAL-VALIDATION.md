# External Validation — Compliance and Measurable Data

This document describes how an **external entity** can validate that the Coherence Network API is running end-to-end provider execution and tracking and producing **measurable, auditable data** for compliance.

## Default behaviour (from `config/settings.json`)

- **Agent tasks**: Persistence and DB usage are **on** by default (`agent_tasks.persist: true`, `agent_tasks.use_db: true`). When `DATABASE_URL` or `AGENT_TASKS_DATABASE_URL` is set, task history is stored in the database; otherwise tasks are written to file. This produces an **execution audit trail**.
- **Automation usage**: DB snapshots are **on** (`automation_usage.use_db: true`), with a retention of 2000 snapshots (`max_snapshots: 2000`). Imported files are **not** purged by default (`purge_imported_files: false`) so historical data remains available for audit.
- **Runtime events**: Stored when `RUNTIME_DATABASE_URL` or `DATABASE_URL` is set. Use these env vars in deployment so runtime telemetry (tool calls, completions) is persisted and queryable.
- **Lifecycle telemetry**: Agent lifecycle (runtime + optional JSONL) is enabled by default via `AGENT_LIFECYCLE_TELEMETRY_ENABLED` and `AGENT_LIFECYCLE_JSONL_ENABLED` (env, default `"1"`).

## Endpoints for external validators

The API exposes the following for **compliance and measurability**. All are GET unless noted. The same list is available in `config/settings.json` under `external_validation.endpoints`.

| Path | Purpose | Validates |
|------|---------|-----------|
| `GET /api/agent/tasks` | Task execution history (id, status, direction, created_at, context) | Agent execution trail |
| `GET /api/agent/status-report` | Hierarchical pipeline status (goal → orchestration → execution → attention) | Pipeline state |
| `GET /api/agent/effectiveness` | Throughput, issues, goal proximity | Pipeline effectiveness |
| `GET /api/agent/monitor-issues` | Open monitor issues and suggested actions | Attention signals |
| `GET /api/automation/usage/readiness` | Provider readiness and blocking gaps | Provider readiness |
| `GET /api/automation/usage/validation-report` | Provider validation (required providers, usage, execution evidence) | Provider execution compliance |
| `GET /api/automation/usage/overview` | Usage metrics and remaining ratios per provider | Usage measurability |
| `GET /api/runtime/events` | Runtime telemetry events (tool calls, completions) | Runtime tracking |
| `GET /api/health` | Liveness and readiness | Service availability |

## What to check for compliance

1. **Execution trail**: `GET /api/agent/tasks` returns tasks with `status`, `created_at`, and (when present) `context` so execution over time can be verified.
2. **Provider execution**: `GET /api/automation/usage/validation-report` returns required providers, readiness, usage, and execution evidence so an external party can confirm that provider execution is configured and recorded.
3. **Measurable usage**: `GET /api/automation/usage/overview` (and readiness) expose usage and remaining ratios so usage is quantifiable.
4. **Runtime tracking**: With `RUNTIME_DATABASE_URL` or `DATABASE_URL` set, `GET /api/runtime/events` returns persisted events so tool usage and completions are auditable.
5. **Pipeline and attention**: `GET /api/agent/status-report` and `GET /api/agent/monitor-issues` show pipeline state and open issues for operational and compliance visibility.

## Overriding defaults

- **Config file**: Set `CONFIG_PATH` to a different JSON file, or edit `api/config/settings.json`.
- **Env (override config)**: e.g. `AGENT_TASKS_PERSIST=0`, `AGENT_TASKS_USE_DB=0`, `DATABASE_URL=...`, `RUNTIME_DATABASE_URL=...`.

Tests and local runs often set `AGENT_TASKS_PERSIST=0` (or use DB env wipes in conftest); production deployments should rely on the config defaults above so that execution and tracking are on and measurable for external validation.

## Fallbacks: tracked, visible, minimized

All fallback paths are **tracked** and **visible** in responses so validators can detect and **minimize** them during actual validation.

### Where fallbacks appear

| Endpoint / response | Fallback meaning | How to detect | How to minimize |
|---------------------|------------------|---------------|-----------------|
| **GET /api/agent/status-report** | Report file missing, unreadable, or stale; response is derived from live pipeline + effectiveness. | `fallback_reason` non-null (e.g. `missing_status_report_file`, `stale_status_report_file`). `source` = `derived_pipeline_status`. `fallbacks_used` = list of reasons. | Run monitor so it writes `api/logs/pipeline_status_report.json` before validation; ensure file is fresh (within `status_report_max_age_seconds`). |
| **GET /api/agent/tasks** | Some listed tasks were backfilled from runtime completion events (no persisted task record). | `meta.runtime_fallback_backfill_count` > 0 when present. | Use persisted task store (DB or file) and ensure tasks are written before validation; avoid relying on runtime fallback when DB/store is empty. |
| **GET /api/automation/usage/overview** | Primary (live/cache) call timed out; response is from snapshot store. | `meta.data_source` = `snapshot_fallback`, `meta.fallback_reason` = `timeout`, `meta.fallbacks_used` includes `timeout`. | Use `force_refresh=true` and sufficient timeout; ensure live provider probes succeed so snapshot fallback is not used. |
| **GET /api/automation/usage/readiness** | Same as overview (timeout → snapshot fallback). | Same `meta.data_source` / `meta.fallback_reason` / `meta.fallbacks_used`. | Same as above. |
| **GET /api/automation/usage/validation-report** | Timeout → cached/snapshot validation payload. | `meta.data_source` = `snapshot_fallback`, `meta.fallback_reason` = `timeout`. | Same as above. |
| **GET /api/automation/usage/alerts** | Timeout → snapshot-based alerts. | `meta.data_source` = `snapshot_fallback`, `meta.fallback_reason` = `timeout`. | Same as above. |
| **GET /api/automation/usage/daily-summary** | Timeout → cached payload or empty fallback. | `meta.data_source` = `cached_fallback` or `empty_fallback`, `meta.fallback_reason` = `timeout` or `timeout_no_cache`. | Same as above. |

### Response shape (consistent)

- **Status report**: Always has `source` (`monitor_report` = primary, `derived_pipeline_status` = fallback) and `fallback_reason` (`null` = primary, string = reason). `fallbacks_used` is an array (empty when primary).
- **Automation usage** (overview, readiness, validation-report, alerts, daily-summary): When we inject tracking, responses include `meta` with `data_source` (`live_or_cache` | `snapshot_fallback` | `cached_fallback` | `empty_fallback`), optional `fallback_reason`, and `fallbacks_used` (array).
- **Task list**: When any tasks were backfilled from runtime events, `meta.runtime_fallback_backfill_count` is present and > 0.

### Minimizing fallbacks during validation

1. **Require primary data**: For strict compliance, treat a response as valid only when no fallback was used (e.g. `fallback_reason` is null, `meta.data_source` is `live_or_cache`, `meta.runtime_fallback_backfill_count` is 0 or absent).
2. **Pre-warm**: Before running validation, call status-report (after a monitor run), automation usage with `force_refresh=true`, and ensure task store and runtime DB are populated so fallbacks are not needed.
3. **Fail or flag**: In automated checks, either fail when `fallbacks_used` is non-empty or record a clear warning so operators can fix (e.g. run monitor, fix timeouts, ensure DB connectivity).
