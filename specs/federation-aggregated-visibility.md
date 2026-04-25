---
idea_id: federation-and-nodes
status: draft
source:
  - file: api/app/routers/federation.py
    symbols: [get_aggregated_node_stats, get_network_summary]
  - file: api/app/services/federation_service.py
    symbols: [get_aggregated_node_stats, get_network_summary]
  - file: api/app/models/federation.py
    symbols: [NetworkSummaryResponse, AggregatedNodeStatsResponse]
  - file: web/app/nodes/page.tsx
    symbols: [loadData, NodesPage, NetworkStatsSection]
requirements:
  - "GET /api/federation/nodes/stats returns per-provider network-wide success rates, mean duration, per-node breakdown, and alerts — already implemented; must return correct shape"
  - "GET /api/federation/network-summary returns node counts (total, online, idle), fleet success rate, active providers, and total measurements in window"
  - "web /nodes page fetches /api/federation/nodes/stats and renders a Network Measurements section below the fleet summary strip"
  - "Network Measurements section shows each provider with: network success %, mean speed, node count contributing, per-node row on expand — or a collapsed mobile card"
  - "web /nodes page fetches /api/federation/network-summary and surface node-count / fleet stats in the existing fleet summary strip"
  - "Alerts from /api/federation/nodes/stats are surfaced in the web page alongside local provider alerts"
done_when:
  - "GET /api/federation/nodes/stats?window_days=30 returns JSON with keys: nodes, providers, task_types, alerts, window_days, total_measurements"
  - "GET /api/federation/network-summary returns JSON with keys: total_nodes, online_nodes, idle_nodes, fleet_success_rate, active_providers, total_measurements, window_days"
  - "curl https://api.coherencycoin.com/api/federation/nodes/stats | jq '.providers | keys' returns a list (empty or populated)"
  - "curl https://api.coherencycoin.com/api/federation/network-summary | jq '.total_nodes' returns a number >= 0"
  - "/nodes web page renders without error when both endpoints return empty data"
  - "all existing tests pass"
test: "cd api && python -m pytest api/tests/ -q -k federation"
constraints:
  - "Do not change the existing /api/federation/nodes/stats response shape — only add the new /api/federation/network-summary endpoint"
  - "Web page must handle 404/500 from both federation endpoints gracefully (show nothing, not crash)"
  - "No new DB migrations required — build summary from existing FederationNodeRecord and NodeMeasurementSummaryRecord tables"
---

> **Parent idea**: [federation-and-nodes](../ideas/federation-and-nodes.md)
> **Source**: [`api/app/routers/federation.py`](../api/app/routers/federation.py) | [`api/app/services/federation_service.py`](../api/app/services/federation_service.py) | [`web/app/nodes/page.tsx`](../web/app/nodes/page.tsx)

# Spec: Federation Aggregated Visibility

## Summary

The federation network layer (spec `federation-network-layer`) already persists node registrations, heartbeats, and measurement summaries. The aggregation endpoint `/api/federation/nodes/stats` exists in the router but the web dashboard does not consume it. Visitors to `/nodes` see per-node streak bars and local provider health, but have no view of cross-node learning: how each provider performs across the entire fleet, which nodes contribute measurements, and what the network-wide health looks like.

This spec closes that gap. It adds one new API endpoint (`GET /api/federation/network-summary`) and wires the existing `/api/federation/nodes/stats` plus the new endpoint into the `/nodes` web page. The result: any visitor can see at a glance whether the network is healthy, which providers are performing well across nodes, and which providers need attention.

## Problem

Without this surface:
- The hub has measurement data from multiple nodes that nobody reads.
- An operator cannot tell whether a provider is struggling on one node or everywhere.
- The fleet summary strip shows "N nodes / N online" but gives no health signal about the distributed learning system.

## Requirements

### API

- **R1** — `GET /api/federation/nodes/stats` (`window_days` query param, default 30, 1–365): returns aggregated provider measurements across all registered nodes. **Already implemented** — the requirement is that the response shape matches the contract below so the web layer can depend on it.

- **R2** — `GET /api/federation/network-summary` (new endpoint): returns a compact roll-up suitable for the fleet summary strip. No query params required on initial call; optional `window_days` integer to match the stats window.

- **R3** — Both endpoints return HTTP 200 with empty collections when no nodes/measurements exist. They must not 500 on an empty database.

### Web dashboard (`/nodes`)

- **R4** — The fleet summary strip (existing 4-tile grid) incorporates data from `/api/federation/network-summary` alongside the node-list data: `total_nodes`, `online_nodes`, `fleet_success_rate`, `total_measurements`.

- **R5** — A new **Network Measurements** section appears below the fleet summary strip when `/api/federation/nodes/stats` returns at least one provider. The section shows:
  - Section header: "Network Measurements" with `window_days` and `total_measurements` as sub-label.
  - Per-provider row/card with: provider name, network-wide success rate (%), mean duration (s), node count contributing.
  - Any alerts from the `alerts` array rendered as warning banners (same style as local provider alerts).

- **R6** — On desktop (≥md), providers render in a table. On mobile, they render as stacked cards. Pattern mirrors the existing "Provider health" section.

- **R7** — When `total_measurements === 0`, the section is hidden entirely (no empty-state noise).

- **R8** — Both new fetches use `cache: "no-store"` and fail gracefully: a failed fetch returns null; the section simply does not render.

## API Contract

### `GET /api/federation/nodes/stats`

Already implemented. Response shape (confirmed from service code):

```json
{
  "nodes": {
    "<node_id>": {
      "hostname": "string",
      "os_type": "string",
      "status": "string",
      "last_seen_at": "ISO8601"
    }
  },
  "providers": {
    "<provider_name>": {
      "total_samples": 120,
      "total_successes": 108,
      "total_failures": 12,
      "success_rate": 0.9,
      "mean_duration_s": 42.3,
      "per_node": {
        "<node_id>": {
          "samples": 60,
          "successes": 55,
          "success_rate": 0.917,
          "mean_duration_s": 41.1
        }
      }
    }
  },
  "task_types": {
    "<task_type>": {
      "<provider>": { "samples": 30, "success_rate": 0.9 }
    }
  },
  "alerts": [
    {
      "provider": "string",
      "metric": "success_rate",
      "value": 0.3,
      "threshold": 0.5,
      "message": "claude success rate 30% below threshold 50%"
    }
  ],
  "window_days": 30,
  "total_measurements": 120
}
```

### `GET /api/federation/network-summary` (new)

**Response 200**
```json
{
  "total_nodes": 3,
  "online_nodes": 2,
  "idle_nodes": 1,
  "fleet_success_rate": 0.87,
  "active_providers": ["claude", "codex"],
  "total_measurements": 340,
  "window_days": 30,
  "generated_at": "2026-04-26T10:00:00Z"
}
```

`online_nodes` = nodes with `last_seen_at` within the last 5 minutes.
`idle_nodes` = registered nodes not seen in last 5 minutes but registered in last 30 days.
`fleet_success_rate` = total successes / total samples across all measurement summaries in the window; null if no data.
`active_providers` = providers with at least 1 measurement in the window.

## Data Model

No new tables. The new endpoint derives from:
- `FederationNodeRecord` — for node counts and last_seen_at.
- `NodeMeasurementSummaryRecord` — for provider stats and total_measurements.

A new `NetworkSummaryResponse` Pydantic model is needed in `api/app/models/federation.py`.

```yaml
NetworkSummaryResponse:
  total_nodes: int
  online_nodes: int
  idle_nodes: int
  fleet_success_rate: float | null
  active_providers: list[str]
  total_measurements: int
  window_days: int
  generated_at: str  # ISO8601 UTC
```

## Files

### API (create / modify)

- `api/app/models/federation.py` — add `NetworkSummaryResponse` Pydantic model
- `api/app/services/federation_service.py` — add `get_network_summary(window_days: int = 30)` function
- `api/app/routers/federation.py` — add `GET /federation/network-summary` route calling `federation_service.get_network_summary`

### Web (modify)

- `web/app/nodes/page.tsx` — update `loadData()` to also fetch `/api/federation/nodes/stats` and `/api/federation/network-summary`; add `NetworkStatsSection` inline component; render below fleet summary strip

## Verification Scenarios

### Scenario 1 — network-summary endpoint returns valid shape

```bash
curl -s https://api.coherencycoin.com/api/federation/network-summary | jq '{total_nodes, online_nodes, fleet_success_rate}'
```

Expected: `{ "total_nodes": <number>, "online_nodes": <number>, "fleet_success_rate": <number_or_null> }` — no 500, no missing keys.

### Scenario 2 — nodes/stats endpoint returns valid shape

```bash
curl -s "https://api.coherencycoin.com/api/federation/nodes/stats?window_days=30" | jq '{window_days, total_measurements, provider_count: (.providers | length)}'
```

Expected: `{ "window_days": 30, "total_measurements": <number>, "provider_count": <number> }` — providers key is an object (may be empty).

### Scenario 3 — empty database returns 200 with zero counts

```bash
# On a fresh node with no measurements pushed yet:
curl -s https://api.coherencycoin.com/api/federation/network-summary | jq '.total_measurements'
# Expected: 0
curl -s "https://api.coherencycoin.com/api/federation/nodes/stats" | jq '.total_measurements'
# Expected: 0
```

### Scenario 4 — window_days filter respected

```bash
curl -s "https://api.coherencycoin.com/api/federation/nodes/stats?window_days=1" | jq '.window_days'
# Expected: 1
curl -s "https://api.coherencycoin.com/api/federation/network-summary?window_days=7" | jq '.window_days'
# Expected: 7
```

### Scenario 5 — web page loads without error

```bash
curl -s -o /dev/null -w "%{http_code}" https://coherencycoin.com/nodes
# Expected: 200
```

If provider stats or network-summary fail, the page still returns 200 — sections simply do not render.

## Risks and Assumptions

- **Risk**: `get_aggregated_node_stats` in `federation_service.py` is marked as implemented in the router but may not be fully defined in the service (partial implementation). The impl agent must confirm the function exists and returns the documented shape; if absent, it must be written.
- **Assumption**: `NodeMeasurementSummaryRecord` exists in the DB schema (it is used by the measurement-push endpoints in the existing spec). If the table is missing on a given deployment, `get_network_summary` must catch `OperationalError` and return zeros rather than 500.
- **Risk**: The web fetch for `/api/federation/nodes/stats` may be slow on large networks (many nodes × many providers). Cache TTL is set to `no-store` to keep data fresh; if this causes page load lag, a 60-second revalidation can be introduced without changing this spec.
- **Assumption**: The `/nodes` page is server-rendered (Next.js App Router server component). No client-side state needed for these additions — server fetch + conditional render is sufficient.

## Out of Scope

- Real-time streaming / WebSocket updates of node stats
- Per-provider drill-down pages (individual provider history chart)
- Alerting / notification when a provider crosses a threshold (covered by `provider-health-alerting` spec)
- Strategy propagation visibility (covered by `federation-network-layer` spec)
- Authentication gating on the network-summary endpoint
