---
idea_id: data-infrastructure
title: Data Infrastructure
stage: implementing
work_type: feature
pillar: foundation
specs:
  - [018-coherence-algorithm-spec](../specs/018-coherence-algorithm-spec.md)
  - [054-postgresql-migration](../specs/054-postgresql-migration.md)
  - [118-unified-sqlite-store](../specs/118-unified-sqlite-store.md)
  - [166-universal-node-edge-layer](../specs/166-universal-node-edge-layer.md)
  - [050-canonical-route-registry-and-runtime-mapping](../specs/050-canonical-route-registry-and-runtime-mapping.md)
  - [107-runtime-telemetry-db-precedence](../specs/107-runtime-telemetry-db-precedence.md)
  - [130-api-request-logging-middleware](../specs/130-api-request-logging-middleware.md)
  - [051-release-gates](../specs/051-release-gates.md)
---

# Data Infrastructure

The storage and query foundation everything else runs on. Every entity in Coherence Network -- ideas, specs, contributors, tasks, concepts -- is a node. Every relationship between them is an edge. Two tables (nodes + edges) replace 10+ separate tables, and every query is a graph traversal. PostgreSQL with JSONB provides the production backend; SQLite provides local development parity.

## Problem

The original schema had 10+ separate tables (ideas, specs, tasks, contributors, assets, contributions, etc.) with ad hoc foreign keys and no unified query model. Adding a new entity type required a new table, new migration, new API endpoints. Telemetry was scattered across JSON files and environment variables with no single source of truth. Local development used a different storage model than production, causing bugs that only appeared after deploy.

## Key Capabilities

- **Universal node+edge layer**: 2 tables replace 10+. `nodes` table: `id`, `type`, `name`, `properties` (JSONB). `edges` table: `from_id`, `to_id`, `type`, `strength`. Every entity is a node (idea, spec, contributor, task, concept). Every relationship is an edge (idea->spec, contributor->task, concept->idea). PostgreSQL JSONB chosen over Neo4j for operational simplicity.
- **Coherence algorithm**: Formal specification for computing 0.0-1.0 coherence scores. The algorithm considers alignment (does the contribution match the idea's goals?), completeness (how much of the idea is realized?), and quality (does it pass validation?). Scores are deterministic and reproducible.
- **PostgreSQL migration**: Production persistence with proper connection pooling, migrations, and backup. Replaces the mix of SQLite files and JSON stores that served during early development.
- **Unified SQLite store**: Single `.db` file for local development. Same schema as PostgreSQL, same queries, same behavior. Developers can run the full platform locally without Docker or PostgreSQL.
- **Canonical route registry**: Machine-readable API surface map that links every endpoint to its implementing idea and spec. Used for self-discovery, documentation generation, and route validation.
- **Runtime telemetry**: DB-first precedence for all metrics. Telemetry is written to the database, not log files. Request logging middleware captures every API call with timing, status, and caller identity.
- **Release gates**: Automated quality checks before deploy. Tests pass, migrations applied, no schema drift, health endpoint responds. Gates are checked automatically and block deploy if any fail.

## What Success Looks Like

- Adding a new entity type requires zero schema migrations -- just a new node type string
- Local development and production use identical query paths with zero behavioral differences
- Every API endpoint is traceable to an idea and spec via the route registry
- Release gates catch 100% of schema drift and migration issues before they reach production

## Absorbed Ideas

- **universal-node-edge-layer**: Replace 10+ tables with `nodes` (`id`, `type`, `name`, `properties` JSONB) + `edges` (`from_id`, `to_id`, `type`, `strength`). PostgreSQL JSONB chosen over Neo4j for operational simplicity -- one database to manage, not two. Graph queries use recursive CTEs instead of a separate graph database.
- **concept-layer-foundation**: 184 universal concepts, 46 relationship types, 53 axes from the Living Codex ontology. Concepts are nodes; relationships are edges. The concept layer provides the vocabulary for coherence scoring -- how well does an idea align with the platform's conceptual framework?
- **service-contract-registry**: `ServiceSpec`, `ServiceRef`, `IService` protocol with dependency validation and health reporting. Every service declares what it needs and what it provides. The registry validates that all dependencies are satisfied before startup.

## Open Questions

- How to migrate 200+ ideas from the old schema without downtime? Dual-write during migration period, then cut over?
- What indexes are needed on the edges table for fast traversal? `(from_id, type)` and `(to_id, type)` are obvious, but what about `(type, strength)` for coherence queries?
- At what scale does the recursive CTE approach for graph traversal become a bottleneck vs a dedicated graph DB?
