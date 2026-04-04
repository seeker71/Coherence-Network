---
idea_id: data-infrastructure
title: Data Infrastructure
stage: implementing
work_type: feature
specs:
  - 018-coherence-algorithm-spec
  - 054-postgresql-migration
  - 118-unified-sqlite-store
  - 166-universal-node-edge-layer
  - 050-canonical-route-registry-and-runtime-mapping
  - 107-runtime-telemetry-db-precedence
  - 130-api-request-logging-middleware
  - 051-release-gates
---

# Data Infrastructure

The storage, graph, and telemetry foundations everything runs on.

## What It Does

- Coherence algorithm: formal spec for 0.0–1.0 scoring
- PostgreSQL migration for production persistence
- Unified SQLite store replacing 4 DBs and 5 JSON stores
- Universal node + edge layer: single graph source of truth
- Canonical route registry mapping API endpoints to idea IDs
- Runtime telemetry routed to DB; request logging middleware
- Release gates: automated deployment readiness checks

## API

- `GET /api/health` — system health
- `GET /api/nodes` — graph nodes
- `GET /api/edges` — graph edges
- `GET /api/release-gates` — deployment readiness

## Why It Matters

Everything runs on this. Unreliable data → unreliable everything.
