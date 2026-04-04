---
idea_id: data-infrastructure
status: done
source:
  - file: api/app/services/graph_service.py
    symbols: [create_node(), get_node(), create_edge(), get_edges()]
  - file: api/app/models/graph.py
    symbols: [Node, Edge]
  - file: api/app/routers/graph.py
    symbols: [graph CRUD endpoints]
---

# Spec: Universal Node + Edge Data Layer

## Purpose

Coherence Network currently stores entity relationships across heterogeneous tables (ideas, tasks, nodes, edges) with no uniform contract — causing 3130 failed-task events and 447,958 wasted minutes from broken contracts at seams between pipeline stages. This spec introduces a **Universal Node + Edge data layer**: a single source of truth for all graph entities and their relationships, with a uniform `payload` column and stable `node_id` / `edge_id` keys. Every pipeline stage reads and writes through this layer, eliminating ad-hoc JSON blobs and enabling consistent graph traversal, attribution, and value lineage.

**Who benefits**: API operators, pipeline agents, and downstream analytics consumers — anyone who queries or traverses the graph and expects predictable schemas and indexable relationships.

## Requirements

- [ ] `graph_nodes` table: `id UUID PK`, `node_type VARCHAR(64) NOT NULL`, `external_id VARCHAR(256)`, `payload JSONB NOT NULL DEFAULT '{}'`, `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`, `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- [ ] `graph_edges` table: `id UUID PK`, `edge_type VARCHAR(64) NOT NULL`, `from_node_id UUID NOT NULL REFERENCES graph_nodes(id) ON DELETE CASCADE`, `to_node_id UUID NOT NULL REFERENCES graph_nodes(id) ON DELETE CASCADE`, `weight FLOAT NOT NULL DEFAULT 1.0`, `payload JSONB NOT NULL DEFAULT '{}'`, `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- [ ] Unique index on `(node_type, external_id)` in `graph_nodes` to allow idempotent upserts
- [ ] Index on `(edge_type, from_node_id)` and `(edge_type, to_node_id)` in `graph_edges` for traversal queries
- [ ] FastAPI router `GET /api/graph/nodes/{node_id}` returns node + outgoing edges
- [ ] FastAPI router `POST /api/graph/nodes` upserts a node; `POST /api/graph/edges` upserts an edge
- [ ] FastAPI router `GET /api/graph/nodes/{node_id}/neighbors` returns first-degree neighbors with edge metadata
- [ ] All routers return Pydantic models with stable field names (no dynamic key leakage)
- [ ] Alembic migration for both tables and all indexes
- [ ] 90%+ test coverage on the new router and service layer

## Research Inputs (Required)

- `2024-06-01` - [Coherence Network friction events log](../data/) - 3130 failed-task events attributed to missing/broken payload contracts at pipeline seams
- `2024-06-01` - [FastAPI Pydantic docs](https://fastapi.tiangolo.com/tutorial/response-model/) - response_model enforcement ensures stable field contract
- `2024-06-01` - [PostgreSQL JSONB indexing](https://www.postgresql.org/docs/current/datatype-json.html) - JSONB + GIN index for arbitrary payload queries without schema churn

## Task Card (Required)

```yaml
goal: Create graph_nodes and graph_edges tables + CRUD API router with Pydantic contracts
files_allowed:
  - api/alembic/versions/xxxx_add_graph_node_edge_tables.py
  - api/app/models/graph.py
  - api/app/services/graph_service.py
  - api/app/routers/graph.py
  - api/tests/test_graph_layer.py
done_when:
  - alembic upgrade head applies cleanly (no errors)
  - pytest api/tests/test_graph_layer.py passes with N passed, 0 failed
  - ruff check api/app/routers/graph.py api/app/services/graph_service.py exits 0
  - GET /api/graph/nodes/{id} returns 200 with node + edges JSON
  - POST /api/graph/nodes with duplicate (node_type, external_id) returns 200 (upsert, not 409)
commands:
  - cd api && alembic upgrade head
  - cd api && .venv/bin/pytest api/tests/test_graph_layer.py -v --tb=short
  - cd api && .venv/bin/ruff check app/models/graph.py app/services/graph_service.py app/routers/graph.py
constraints:
  - Do NOT modify existing idea/task/node tables — additive only
  - Do NOT bypass Pydantic response models with raw dict returns
  - All foreign keys must use ON DELETE CASCADE to prevent orphan edges
  - Migration must be reversible (downgrade removes tables and indexes)
```

## API Contract

### `POST /api/graph/nodes`

**Request**
```json
{
  "node_type": "idea",
  "external_id": "idea-abc123",
  "payload": { "title": "Universal Node Layer", "score": 0.87 }
}
```

**Response 200**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "node_type": "idea",
  "external_id": "idea-abc123",
  "payload": { "title": "Universal Node Layer", "score": 0.87 },
  "created_at": "2026-03-28T00:00:00Z",
  "updated_at": "2026-03-28T00:00:00Z"
}
```

### `GET /api/graph/nodes/{node_id}`

**Response 200**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "node_type": "idea",
  "external_id": "idea-abc123",
  "payload": {},
  "created_at": "2026-03-28T00:00:00Z",
  "updated_at": "2026-03-28T00:00:00Z",
  "outgoing_edges": [
    {
      "id": "660e8400-...",
      "edge_type": "generates",
      "to_node_id": "770e8400-...",
      "weight": 1.0,
      "payload": {}
    }
  ]
}
```

**Response 404**
```json
{ "detail": "Node not found" }
```

### `POST /api/graph/edges`

**Request**
```json
{
  "edge_type": "generates",
  "from_node_id": "550e8400-e29b-41d4-a716-446655440000",
  "to_node_id": "660e8400-e29b-41d4-a716-446655440001",
  "weight": 1.0,
  "payload": {}
}
```

**Response 200**
```json
{
  "id": "770e8400-...",
  "edge_type": "generates",
  "from_node_id": "550e8400-...",
  "to_node_id": "660e8400-...",
  "weight": 1.0,
  "payload": {},
  "created_at": "2026-03-28T00:00:00Z"
}
```

### `GET /api/graph/nodes/{node_id}/neighbors`

**Response 200**
```json
{
  "node_id": "550e8400-...",
  "neighbors": [
    {
      "node": { "id": "660e8400-...", "node_type": "task", "external_id": "task-xyz" },
      "edge": { "edge_type": "generates", "weight": 1.0, "direction": "outgoing" }
    }
  ]
}
```

## Data Model

```yaml
graph_nodes:
  id: UUID PRIMARY KEY DEFAULT gen_random_uuid()
  node_type: VARCHAR(64) NOT NULL                          # "idea", "task", "agent", "artifact"
  external_id: VARCHAR(256)                                # FK to domain table, nullable for pure graph nodes
  payload: JSONB NOT NULL DEFAULT '{}'
  created_at: TIMESTAMPTZ NOT NULL DEFAULT NOW()
  updated_at: TIMESTAMPTZ NOT NULL DEFAULT NOW()
  indexes:
    - UNIQUE (node_type, external_id) WHERE external_id IS NOT NULL
    - GIN (payload)  # optional, add when payload queries are common

graph_edges:
  id: UUID PRIMARY KEY DEFAULT gen_random_uuid()
  edge_type: VARCHAR(64) NOT NULL                          # "generates", "depends_on", "authored_by", "resonates_with"
  from_node_id: UUID NOT NULL REFERENCES graph_nodes(id) ON DELETE CASCADE
  to_node_id: UUID NOT NULL REFERENCES graph_nodes(id) ON DELETE CASCADE
  weight: FLOAT NOT NULL DEFAULT 1.0
  payload: JSONB NOT NULL DEFAULT '{}'
  created_at: TIMESTAMPTZ NOT NULL DEFAULT NOW()
  indexes:
    - (edge_type, from_node_id)
    - (edge_type, to_node_id)
```

## Files to Create/Modify

- `api/alembic/versions/xxxx_add_graph_node_edge_tables.py` — new Alembic migration adding `graph_nodes` and `graph_edges` tables with indexes
- `api/app/models/graph.py` — Pydantic request/response models: `GraphNodeCreate`, `GraphNodeResponse`, `GraphEdgeCreate`, `GraphEdgeResponse`, `GraphNeighborsResponse`
- `api/app/services/graph_service.py` — `upsert_node()`, `upsert_edge()`, `get_node_with_edges()`, `get_neighbors()` against PostgreSQL
- `api/app/routers/graph.py` — FastAPI router mounted at `/api/graph`
- `api/tests/test_graph_layer.py` — pytest tests covering upsert, cascade delete, neighbor traversal, 404 handling

## Acceptance Criteria

All acceptance criteria map 1:1 to tests in `api/tests/test_graph_layer.py`:

- `test_upsert_node_creates_new` — POST with new `(node_type, external_id)` returns 200 with a UUID `id`
- `test_upsert_node_idempotent` — second POST with same `(node_type, external_id)` returns same `id`
- `test_get_node_not_found` — GET for unknown UUID returns 404
- `test_get_node_with_edges` — GET for known node returns `outgoing_edges` list
- `test_upsert_edge` — POST `/api/graph/edges` returns 200 with UUID `id`
- `test_cascade_delete` — DELETE node removes dependent edges
- `test_get_neighbors` — GET `/api/graph/nodes/{id}/neighbors` returns correct neighbor + edge metadata

## Verification

1. **Migration round-trip**: `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head` all exit 0 with empty database.
2. **Upsert idempotency**: Two `POST /api/graph/nodes` calls with identical `(node_type, external_id)` return same `id` and `updated_at` advances.
3. **Cascade delete**: Delete a node → all edges referencing it (from or to) are gone.
4. **Neighbor query**: Insert node A → node B → edge A→B; `GET /api/graph/nodes/A/neighbors` returns B with `direction: outgoing`.
5. **Lint clean**: `ruff check api/app/routers/graph.py api/app/services/graph_service.py` exits 0.
6. **Coverage**: `pytest --cov=api/app/routers/graph --cov=api/app/services/graph_service --cov-report=term` shows ≥90%.

## Risks and Assumptions

| Risk | Likelihood | Mitigation |
|------|------------|-----------|
| Implementers bypass the layer and add ad-hoc SQL | Medium | CI `rg` check for direct `INSERT INTO ideas` / `INSERT INTO tasks` without going through `graph_service` |
| `payload` JSONB becomes a dumping ground with no schema discipline | High | Require `node_type`-specific Pydantic validators in `graph_service.upsert_node()` |
| Circular edges cause infinite traversal loops | Low | `GET /neighbors` is depth-1 only; recursive traversal requires explicit `depth` param with max=5 |
| UUID FK performance at scale | Low | Indexes on `(edge_type, from_node_id/to_node_id)` cover traversal; monitor with `EXPLAIN ANALYZE` |
| Alembic env not configured for test DB | Medium | `api/.env.example` must include `TEST_DATABASE_URL`; CI must export it |

**Assumptions**:
- PostgreSQL 14+ (gen_random_uuid() available without pgcrypto)
- Existing tables (`ideas`, `tasks`, `nodes`) are NOT migrated into `graph_nodes` in this spec — migration is additive only
- `external_id` semantics: domain-table primary key as string, e.g. `str(idea.id)` for idea nodes

## Out of Scope

- Backfilling existing `ideas` / `tasks` rows into `graph_nodes` — additive migration only
- Neo4j sync — PostgreSQL-only in this spec
- Per-route JWT authentication — Traefik handles prod auth; app-level auth is a follow-up
- Soft delete (`deleted_at`) — not added to initial tables
- Change-data-capture / CDC hooks (Debezium, pg_notify) — separate spec
- Recursive graph traversal beyond depth-1 neighbors

## Known Gaps and Follow-up Tasks

- **Backfill**: Existing ideas/tasks are not yet represented as `graph_nodes`. A follow-up backfill migration should map them, but this is out of scope here to avoid breaking the running pipeline.
- **Neo4j sync**: The long-term vision syncs `graph_nodes/edges` to Neo4j for traversal queries. This spec is PostgreSQL-only; Neo4j sync is a separate spec.
- **Auth**: No authentication on graph endpoints in this spec. Production gate is Traefik middleware — add per-route JWT checks in follow-up.
- **Soft delete**: No `deleted_at` column. If needed, add in follow-up rather than complicating initial migration.
- **Event sourcing**: No change-data-capture (CDC) on these tables yet. Future spec should add Debezium or pg_notify hooks for real-time pipeline fanout.
