# Spec: Federation Aggregated Visibility

## Purpose

Operators need a combined view of provider performance across all federation nodes. Without aggregation, each node's measurements are siloed — the hub cannot answer "which provider works best fleet-wide?" or "is claude degraded on any node?". This spec adds hub-side aggregation queries and a network-wide provider stats endpoint that web pages consume to render cross-node dashboards.

## Requirements

- [ ] `GET /api/federation/nodes/stats` returns aggregated provider stats across all nodes from `node_measurement_summaries`.
- [ ] Response includes per-provider totals: `node_count`, `total_samples`, `total_successes`, `total_failures`, `overall_success_rate`, `avg_duration_s`.
- [ ] Response includes per-provider per-node breakdown: `{provider: {node_id: {success_rate, samples, avg_duration_s}}}`.
- [ ] Response includes per-task-type breakdown with the same per-provider structure.
- [ ] `GET /api/providers/stats/network` returns the same data shaped for web page consumption (compatible with existing `/api/providers/stats` response shape plus `nodes` field).
- [ ] Both endpoints handle zero data gracefully — return empty structures, not errors.
- [ ] Aggregation uses only `node_measurement_summaries` rows pushed within the last 7 days (configurable via `FEDERATION_STATS_WINDOW_DAYS` env, default 7).
- [ ] Response includes `alerts` list for any provider whose network-wide success rate is below 50%.

## Research Inputs (Required)

- `2026-03-21` - [Spec 131: Federation Measurement Push](specs/131-federation-measurement-push.md) — defines the `node_measurement_summaries` table and push protocol this spec reads from.
- `2026-03-21` - [Spec 132: Federation Node Identity](specs/132-federation-node-identity.md) — defines the `federation_nodes` table joined for node metadata.
- `2026-03-21` - [Provider Stats endpoint](api/app/routers/provider_stats.py) — existing local-only stats endpoint shape to maintain compatibility.

## Task Card (Required)

```yaml
goal: Aggregate cross-node measurement summaries into fleet-wide provider stats endpoints
files_allowed:
  - api/app/routers/federation.py
  - api/app/routers/provider_stats.py
  - api/app/services/federation_service.py
  - api/tests/test_federation_aggregated_visibility.py
done_when:
  - GET /api/federation/nodes/stats returns aggregated cross-node provider data
  - GET /api/providers/stats/network returns web-compatible aggregated view
  - Both endpoints handle empty data gracefully
  - Alerts generated for providers below 50% network success rate
commands:
  - cd api && pytest -q tests/test_federation_aggregated_visibility.py
constraints:
  - Read-only queries on node_measurement_summaries — no writes
  - No modifications to the push protocol or storage schema
  - Compatible with existing /api/providers/stats response shape
```

## API Contract (if applicable)

### `GET /api/federation/nodes/stats`

**Response 200**
```json
{
  "nodes": {
    "a3f8c2e1": {"hostname": "macbook-pro", "os_type": "darwin", "status": "active", "last_seen_at": "2026-03-21T15:00:00Z"},
    "b7d9e4f2": {"hostname": "srv1482815", "os_type": "linux", "status": "active", "last_seen_at": "2026-03-21T14:30:00Z"}
  },
  "providers": {
    "claude": {
      "node_count": 2,
      "total_samples": 142,
      "total_successes": 135,
      "total_failures": 7,
      "overall_success_rate": 0.951,
      "avg_duration_s": 70.2,
      "per_node": {
        "a3f8c2e1": {"success_rate": 1.0, "samples": 50, "avg_duration_s": 65.0},
        "b7d9e4f2": {"success_rate": 0.924, "samples": 92, "avg_duration_s": 73.0}
      }
    }
  },
  "task_types": {
    "spec": {
      "providers": {
        "claude": {"total_samples": 30, "success_rate": 1.0, "avg_duration_s": 72.5}
      }
    }
  },
  "alerts": [],
  "window_days": 7,
  "total_measurements": 142
}
```

### `GET /api/providers/stats/network`

Same data reshaped to match existing `/api/providers/stats` format with added `nodes` field.

## Data Model (if applicable)

No new tables — reads from `node_measurement_summaries` (Spec 131) and `federation_nodes` (Spec 132).

## Files to Create/Modify

- `api/app/services/federation_service.py` — add `get_aggregated_node_stats(window_days)` query function
- `api/app/routers/federation.py` — add `GET /api/federation/nodes/stats` endpoint
- `api/app/routers/provider_stats.py` — add `GET /api/providers/stats/network` endpoint
- `api/tests/test_federation_aggregated_visibility.py` — new test file

## Acceptance Tests

- `api/tests/test_federation_aggregated_visibility.py::test_aggregated_stats_empty_returns_defaults` — no data returns empty structures
- `api/tests/test_federation_aggregated_visibility.py::test_aggregated_stats_single_node` — one node's data aggregated correctly
- `api/tests/test_federation_aggregated_visibility.py::test_aggregated_stats_multi_node` — two nodes' data combined correctly
- `api/tests/test_federation_aggregated_visibility.py::test_aggregated_stats_per_task_type` — task type breakdown computed correctly
- `api/tests/test_federation_aggregated_visibility.py::test_alert_generated_below_50pct` — provider with <50% success triggers alert
- `api/tests/test_federation_aggregated_visibility.py::test_window_filter_excludes_old_data` — data older than window_days excluded
- `api/tests/test_federation_aggregated_visibility.py::test_network_endpoint_compatible_shape` — `/stats/network` shape matches `/stats` plus nodes

## Concurrency Behavior

- Read-only queries on `node_measurement_summaries` — no write conflicts.
- Multiple concurrent readers are safe under standard PostgreSQL read isolation.

## Verification

```bash
cd api && pytest -q tests/test_federation_aggregated_visibility.py
```

## Out of Scope

- Real-time streaming of cross-node stats (this is query-on-demand).
- Write-back from aggregation to individual nodes.
- Alerting notifications (email, Slack) — only API response alerts.
- Historical trend analysis or time-series charts.

## Risks and Assumptions

- Risk: Large number of summaries could make aggregation queries slow. Mitigation: window_days filter limits query scope; add `pushed_at` index.
- Assumption: `node_measurement_summaries` table exists per Spec 131.
- Assumption: `federation_nodes` table exists per Spec 132.

## Known Gaps and Follow-up Tasks

- Follow-up: add caching with TTL for aggregated stats to reduce DB load.
- Follow-up: add historical trend endpoint for time-series visualization.
- Follow-up: web page "Network" tab implementation for /automation.

## Failure/Retry Reflection

- Failure mode: DB connection failure during aggregation query.
  - Blind spot: web pages show stale or empty data without explanation.
  - Next action: return explicit `"data_source": "unavailable"` flag in response so frontend can show appropriate message.

## Decision Gates (if any)

None — straightforward aggregation of existing data.
