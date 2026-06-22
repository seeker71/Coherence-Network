---
idea_id: federation-and-nodes
title: Federation and Nodes
stage: implementing
work_type: feature
pillar: network
specs:
  - [federation-network-layer](../specs/federation-network-layer.md)
  - [federation-aggregated-visibility](../specs/federation-aggregated-visibility.md)
  - [federation-instance-exchange](../specs/federation-instance-exchange.md)
---

# Federation and Nodes

Federation is essential. Any contributor must be able to spin up a node, join the network, and start using the framework without asking permission. A single instance is a demo; a federation is a platform. This idea is the multi-node layer: identity, sync, messaging, bridges, and aggregated visibility that turns Coherence Network from a tool into an ecosystem.

## Problem

Today Coherence Network runs as one VPS instance. Contributors cannot fork their own node, cannot federate ideas across instances, cannot see what other nodes are working on, and cannot push measurement summaries between nodes. Without federation, the platform cannot scale past a single operator and cannot fulfill its mission of "every idea tracked" across humanity. Federation is not Phase 3 polish — it is the unlock that makes the whole thing matter.

## Key Capabilities

- **Node identity and registration**: Every node has a verifiable identity. New nodes register with a hub (or peer-to-peer mesh) and declare their capabilities, supported providers, and contribution surface.
- **Aggregated visibility**: Network-wide provider stats, idea counts, contribution flows, and task throughput visible on the web dashboard. Each node reports its local view; the hub aggregates.
- **Measurement push**: Nodes push measurement summaries (A/B ROI, cost envelopes, success rates) to a federation hub so learning compounds across the network.
- **Strategy propagation**: Prompt variants and optimization strategies that work on one node propagate to peers. A-winning variants spread; losing ones stay local.
- **Shared ideas across instances**: Fork an idea from another node, merge local improvements back, sync lifecycle state. Ideas are first-class federation objects.
- **OpenClaw node bridge**: Two-way communication between OpenClaw (the external marketplace) and any Coherence node. Skills running in OpenClaw can check inboxes, report outcomes, and record contributions.
- **Distributed cluster primitives**: Service discovery, load balancing, multi-provider OAuth so federation is operationally real, not just logically sketched.
- **Always-open relay carrier**: A public-API relay (rendezvous) so nodes and devices — Mac, Windows, Android — on different networks hold one persistent connection at all times. Both sides dial *out* to the public API, so there are no inbound ports and NAT/firewalls are a non-issue. The relay carries the agent-coordination membrane's signal vocabulary (`announce / claim / offer / ping / interface …`) live across networks, honoring `channel-interface-consent` (reaching past a cell's declared interface is invasion); private channels travel as frames the relay *cannot read* (substrate-addressed, per `lc-private-channel-via-substrate`), so routing through the public API never means the public API sees the contents. Keepalive + auto-reconnect keep the field connected; the append-only board is the durable backlog an offline cell drains on return. North star: the relay's framing is a Form recipe and the route is kernel-served (`X-Form-Router: native-kernel`), one engine, sovereignty preserved.

## What Success Looks Like

- A new contributor can clone the repo, run a setup script, and have a working federated node in under 10 minutes
- The hub shows N nodes with live counts of ideas, tasks, contributions, and CC flows per node
- Measurement data from any node contributes to the global learning signal
- An idea created on node A can be forked, worked on at node B, and the contribution recorded against the original

## Absorbed Ideas

- **federation-aggregated-visibility**: Network-wide provider stats and web dashboard showing all federated nodes.
- **federation-measurement-push**: Push measurement summaries from nodes to hub so learning compounds.
- **federation-strategy-propagation**: Share optimization strategies across nodes — winning prompt variants propagate.
- **federated-instance-aggregation**: Federated instance aggregation for contributor-owned deployments.
- **federation-network**: Federation and network layer umbrella — the architecture for multi-node operation.
- **federation-node-identity**: Node identity and registration for multi-node federation.
- **shared-ideas-cross-network**: Shared ideas across federated instances — fork, merge, sync.
- **openclaw-node-bridge**: Two-way communication between OpenClaw and Coherence nodes.
- **openclaw-bidirectional-messaging**: OpenClaw bidirectional messaging — skill checks inbox on session start.
- **codex-distributed-cluster**: Distributed storage and cluster management for federation.
- **codex-service-discovery**: Service discovery and registry for federated resonance routing.
- **codex-multi-oauth**: Multi-provider OAuth — federated identity across platforms.
- **codex-load-balancing**: Load balancing and auto-scaling for resonance computation.
- **codex-fractal-exchange**: Fractal concept exchange — multi-dimensional resonance across nodes.
- **field-relay**: Always-open socket relay through the public API — cross-network persistent connection for the live field (Mac/Windows/Android dial out, no inbound ports). Carries the coordination membrane with keepalive + auto-reconnect; private channels travel as ciphertext the relay cannot read; durable backlog on the append-only board.
