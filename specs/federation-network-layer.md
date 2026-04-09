---
idea_id: federation-and-nodes
status: done
source:
  - file: api/app/routers/federation.py
    symbols: [register_node, heartbeat_node, list_nodes, push_measurements, list_strategies, send_message, broadcast]
  - file: api/app/services/federation_service.py
    symbols: [register_or_update_node, heartbeat_node, store_measurement_summaries, compute_and_store_strategies, record_strategy_effectiveness]
  - file: api/app/services/node_identity_service.py
    symbols: [derive_node_id]
  - file: api/app/routers/openclaw_node_bridge.py
    symbols: [bridge_sync]
requirements:
  - Node registration with capabilities declaration
  - Heartbeat keep-alive with system metrics
  - Measurement summary push from nodes to hub
  - Strategy propagation (prompt variants, provider recommendations)
  - Strategy effectiveness reporting
  - Inter-node messaging (queue-based + SSE streaming)
  - Broadcast to all nodes
  - Trust-gated payload aggregation from partner instances
  - OpenClaw bidirectional bridge
done_when:
  - POST /api/federation/nodes registers a node
  - POST /api/federation/nodes/{id}/heartbeat updates status
  - POST /api/federation/nodes/{id}/measurements stores summaries
  - GET /api/federation/strategies returns active broadcasts
  - POST /api/federation/nodes/{id}/messages sends targeted message
  - POST /api/federation/broadcast sends to all nodes
  - All tests pass
test: "python3 -m pytest api/tests/test_flow_core_api.py -q"
---

> **Parent idea**: [federation-and-nodes](../ideas/federation-and-nodes.md)
> **Source**: [`api/app/routers/federation.py`](../api/app/routers/federation.py) | [`api/app/services/federation_service.py`](../api/app/services/federation_service.py) | [`api/app/services/node_identity_service.py`](../api/app/services/node_identity_service.py) | [`api/app/routers/openclaw_node_bridge.py`](../api/app/routers/openclaw_node_bridge.py)

# Federation Network Layer -- Multi-Node Identity, Sync, and Propagation

## Goal

Provide the multi-node federation layer that transforms Coherence Network from a single-instance tool into a distributed ecosystem -- where any contributor can spin up a node, register with the hub, exchange measurements, propagate winning strategies, and communicate with peers without asking permission.

## What's Built

The federation layer spans four source files implementing the full node lifecycle: registration, health, data exchange, and inter-node communication.

**Node identity and registration**: `federation.py` exposes `register_node` which accepts a capabilities declaration (supported providers, contribution surface, version). `federation_service.py` implements `register_or_update_node` for idempotent registration -- a node that re-registers updates its capabilities rather than creating a duplicate. `node_identity_service.py` provides `derive_node_id` for deterministic, verifiable node identity derivation.

**Health and heartbeat**: `heartbeat_node` in both the router and service layer implements keep-alive with system metrics. Nodes that stop sending heartbeats are marked stale. The hub maintains a live view of which nodes are active, their capabilities, and their last-seen timestamps.

**Measurement push and strategy propagation**: `push_measurements` accepts measurement summaries (A/B ROI, cost envelopes, success rates) from nodes. `compute_and_store_strategies` aggregates these into network-wide strategy recommendations -- prompt variants and provider configurations that work well propagate to peers via `list_strategies`. `record_strategy_effectiveness` closes the feedback loop so the network learns which strategies actually improve outcomes.

**Inter-node messaging**: `send_message` delivers targeted messages to specific nodes via a queue-based system. `broadcast` sends to all registered nodes simultaneously. Both support SSE streaming for real-time delivery.

**OpenClaw bridge**: `openclaw_node_bridge.py` provides `bridge_sync` for bidirectional communication between OpenClaw marketplace instances and Coherence nodes -- skills running in OpenClaw can check inboxes, report outcomes, and record contributions.

## Requirements

1. Node registration with capabilities declaration
2. Heartbeat keep-alive with system metrics
3. Measurement summary push from nodes to hub
4. Strategy propagation (prompt variants, provider recommendations)
5. Strategy effectiveness reporting
6. Inter-node messaging (queue-based + SSE streaming)
7. Broadcast to all nodes
8. Trust-gated payload aggregation from partner instances
9. OpenClaw bidirectional bridge

## Acceptance Tests

```bash
python3 -m pytest api/tests/test_flow_core_api.py -q
```
