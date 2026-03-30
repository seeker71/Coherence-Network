# Idea Progress: db-error-tracking

## Current task
- Phase: impl
- Task: task_c792590c7ba89e26
- Status: COMPLETE

## Completed phases
### impl (2026-03-30)
- Expanded `_check_schema()` to validate 6 core tables: graph_nodes, graph_edges, telemetry_friction_events, audit_ledger, idea_registry_ideas, spec_registry_entries
- Added `missing_tables` (list[str]) and `db_status` ("ok"/"degraded"/"unavailable") to HealthResponse
- Health endpoint reports `status: "degraded"` when any core table is missing
- Startup DB table creation failures now logged at ERROR (was WARNING)
- Friction events recorded for: missing tables, DB connectivity failures, startup table creation failures
- `unified_db.py` engine() logs schema init failure at ERROR instead of silent pass
- Commit: e4989536

## Key decisions
- Used actual system tables (graph_nodes, graph_edges, etc.) instead of legacy tables (contributions, contributors, assets) for schema validation
- `db_status` uses 3 values: "ok" (all tables present), "degraded" (some missing), "unavailable" (all missing / unreachable)
- Friction events use `severity: "high"` for all DB failures per spec

## Blockers
- None
