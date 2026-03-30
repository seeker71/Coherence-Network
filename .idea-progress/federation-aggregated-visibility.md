# Idea Progress: federation-aggregated-visibility

## Current task
- Task ID: task_584e214d9901a8c1
- Phase: impl
- Status: COMPLETE — all code already exists on main, all 7 tests pass

## Completed phases
- **impl**: Network-wide provider stats aggregation endpoints and tests
  - GET /api/federation/nodes/stats — aggregated cross-node provider data
  - GET /api/providers/stats/network — web-compatible reshaped view
  - 7 acceptance tests covering: empty data, single node, multi-node, per-task-type, alerts, window filter, compatible shape

## Key decisions
- Aggregation reads from node_measurement_summaries (Spec 131) with configurable FEDERATION_STATS_WINDOW_DAYS (default 7)
- Deduplication: for each (node_id, decision_point, slot_id) only the most recent row is used
- Weighted average for duration calculations (weighted by sample count)
- Alert threshold: <50% network-wide success rate

## Blockers
None
