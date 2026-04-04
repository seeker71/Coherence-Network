# Spec: Universal Node + Edge Data Layer

**ID**: universal-node-edge-layer
**Status**: approved
**Author**: claude-sonnet-4-6
**Date**: 2026-03-28

---

## Purpose

Establish a **single source of truth** for all entities and relationships in the Coherence Network by introducing a uniform `Node` + `Edge` data layer backed by dedicated PostgreSQL tables.

Currently, entity data is scattered: ideas in `ideas`, tasks in `tasks`, agents in `agents`, and relationships implied by foreign keys without a queryable graph model. This makes cross-entity queries expensive, breaks attribution chains, and prevents uniform API treatment of any "thing" the system tracks.

The universal layer gives every tracked entity (idea, task, agent, output, event) a stable `node_id` and every relationship (depends-on, produced-by, assigned-to, derived-from) an `edge` record. All existing resource tables become **projections** over the node layer rather than independent silos.

---

## Requirements

### Functional

- [ ] Every entity type (idea, task, agent, pipeline-run, output) has a corresponding `node` record with `node_id UUID`, `node_type ENUM`, `payload JSONB`, `created_at`, `updated_at`.
- [ ] Every directed relationship between entities is captured as an `edge` record with `edge_id UUID`, `src_node_id UUID`, `dst_node_id UUID`, `rel_type ENUM`, `weight FLOAT`, `meta JSONB`, `created_at`.
- [ ] All `node_type` and `rel_type` values are enforced via PostgreSQL ENUMs with a documented extension path (ALTER TYPE … ADD VALUE).
- [ ] The layer exposes CRUD + query endpoints under `/api/graph/nodes` and `/api/graph/edges`.
- [ ] Bulk-upsert support for nodes: `POST /api/graph/nodes/bulk` accepts ≤500 records per call.
- [ ] Traversal endpoint: `GET /api/graph/nodes/{id}/neighbors?rel_type=…&depth=1` returns up to 2-hop neighborhood.
- [ ] All responses are Pydantic models; coherence scores stored as `FLOAT` in range 0.0–1.0.
- [ ] Soft-delete via `deleted_at TIMESTAMP` on both tables; hard deletes forbidden except via admin endpoint.
- [ ] Existing `idea_id`, `task_id` etc. are back-linked to their `node_id` in a migration; dual-write during transition.
- [ ] Full-text search on `payload->>'title'` and `payload->>'body'` via a GIN index.

### Non-Functional

- [ ] P99 query latency for single-node fetch < 10 ms with warm connection pool (target: 200 req/s per API instance).
- [ ] Migrations are idempotent and backward-safe (no column drops in initial migration).
- [ ] All new code passes `ruff check` with zero warnings.
- [ ] Test coverage ≥ 80% for new router + service modules.
- [ ] No direct SQL strings outside migration files; use SQLAlchemy ORM or `text()` with bound params.

---

## Data Model

### `graph_nodes` table

```sql
CREATE TABLE graph_nodes (
    node_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    node_type     node_type_enum NOT NULL,
    payload       JSONB NOT NULL DEFAULT '{}',
    coherence     FLOAT CHECK (coherence BETWEEN 0.0 AND 1.0),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at    TIMESTAMPTZ
);

CREATE INDEX idx_graph_nodes_type       ON graph_nodes (node_type) WHERE deleted_at IS NULL;
CREATE INDEX idx_graph_nodes_payload_ft ON graph_nodes USING GIN (payload jsonb_path_ops);
CREATE INDEX idx_graph_nodes_created    ON graph_nodes (created_at DESC);
```

### `graph_edges` table

```sql
CREATE TABLE graph_edges (
    edge_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    src_node_id  UUID NOT NULL REFERENCES graph_nodes(node_id),
    dst_node_id  UUID NOT NULL REFERENCES graph_nodes(node_id),
    rel_type     rel_type_enum NOT NULL,
    weight       FLOAT NOT NULL DEFAULT 1.0,
    meta         JSONB NOT NULL DEFAULT '{}',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at   TIMESTAMPTZ,
    CONSTRAINT no_self_loop CHECK (src_node_id <> dst_node_id)
);

CREATE INDEX idx_graph_edges_src      ON graph_edges (src_node_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_graph_edges_dst      ON graph_edges (dst_node_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_graph_edges_reltype  ON graph_edges (rel_type)    WHERE deleted_at IS NULL;
```

### ENUMs

```sql
CREATE TYPE node_type_enum AS ENUM (
    'idea', 'task', 'agent', 'output', 'pipeline_run', 'event', 'user'
);

CREATE TYPE rel_type_enum AS ENUM (
    'depends_on', 'produced_by', 'assigned_to', 'derived_from',
    'references', 'blocks', 'tagged_with', 'observed_in'
);
```

---

## API Contract

### Nodes

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/graph/nodes` | Create a node |
| `GET`  | `/api/graph/nodes/{id}` | Fetch single node |
| `PATCH`| `/api/graph/nodes/{id}` | Partial update (`payload`, `coherence`) |
| `DELETE`| `/api/graph/nodes/{id}` | Soft-delete |
| `GET`  | `/api/graph/nodes` | List with `?node_type=&q=&limit=&cursor=` |
| `POST` | `/api/graph/nodes/bulk` | Bulk upsert (≤500) |

### Edges

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/graph/edges` | Create an edge |
| `GET`  | `/api/graph/edges/{id}` | Fetch single edge |
| `DELETE`| `/api/graph/edges/{id}` | Soft-delete |
| `GET`  | `/api/graph/edges` | List with `?src=&dst=&rel_type=` |
| `GET`  | `/api/graph/nodes/{id}/neighbors` | Traversal (depth 1–2) |

### Example response — Node

```json
{
  "node_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "node_type": "idea",
  "payload": { "title": "Universal Node Layer", "body": "..." },
  "coherence": 0.87,
  "created_at": "2026-03-28T00:00:00Z",
  "updated_at": "2026-03-28T00:00:00Z",
  "deleted_at": null
}
```

---

## Migration Strategy

1. **Phase 1** — Add `graph_nodes` / `graph_edges` tables (no data change).
2. **Phase 2** — Back-fill: for each existing `idea`, `task`, `agent`, insert a `graph_nodes` row; store returned `node_id` in a new `node_id` column on the source table (nullable initially).
3. **Phase 3** — Dual-write: all create/update paths write to both old table and `graph_nodes`.
4. **Phase 4** — Read from node layer; old table columns become read replicas.
5. **Phase 5** (future) — Deprecate redundant columns; keep FK back-links for operator tooling.

Each phase is a separate numbered Alembic migration. Phases 1–2 are in scope for this spec.

---

## Files to Create/Modify

- `api/alembic/versions/<timestamp>_add_graph_nodes_edges.py` — Alembic migration adding `graph_nodes`, `graph_edges` tables, ENUMs, and all indexes
- `api/app/models/graph_node.py` — Pydantic models: `GraphNodeCreate`, `GraphNodeResponse`, `GraphNodePatch`
- `api/app/models/graph_edge.py` — Pydantic models: `GraphEdgeCreate`, `GraphEdgeResponse`
- `api/app/routers/graph.py` — FastAPI router mounted at `/api/graph` (CRUD + bulk upsert + traversal)
- `api/app/services/graph_service.py` — `create_node()`, `get_node()`, `patch_node()`, `soft_delete_node()`, `bulk_upsert_nodes()`, `create_edge()`, `get_neighbors()`
- `api/tests/test_graph_router.py` — pytest test suite covering all endpoints and edge cases

## Acceptance Criteria

All acceptance criteria map 1:1 to tests in `api/tests/test_graph_router.py`:

- `test_create_node` — POST `/api/graph/nodes` returns 201 with `node_id` UUID
- `test_get_node` — GET `/api/graph/nodes/{id}` returns 200 with correct payload
- `test_get_node_not_found` — GET for unknown UUID returns 404
- `test_patch_node` — PATCH updates `payload` and advances `updated_at`
- `test_soft_delete_node` — DELETE sets `deleted_at`; subsequent GET returns 404
- `test_bulk_upsert_nodes` — POST `/api/graph/nodes/bulk` with 500 records returns 207 with all `node_id` values
- `test_create_edge` — POST `/api/graph/edges` returns 201 with `edge_id`
- `test_get_neighbors_depth1` — GET `/api/graph/nodes/{id}/neighbors?depth=1` returns correct first-degree neighbors
- `test_soft_deleted_not_in_list` — soft-deleted nodes omitted from list and neighbor results
- `test_ruff_clean` — (CI check) `ruff check` passes with 0 warnings

## Out of Scope

- Neo4j sync / Cypher bridge for heavy analytics queries
- WebSocket / SSE push on node/edge change events
- ACL per-node row-level security (depends on auth layer)
- Migration phases 3–5 (dual-write, deprecation of legacy columns)
- Operator CLI commands (`cc graph list`)
- Hard deletes (admin endpoint only, not in this spec)

## Files Allowed (Task Card)

```yaml
goal: Introduce graph_nodes + graph_edges tables with CRUD + traversal API
files_allowed:
  - api/alembic/versions/<timestamp>_add_graph_nodes_edges.py
  - api/app/models/graph_node.py
  - api/app/models/graph_edge.py
  - api/app/routers/graph.py
  - api/app/services/graph_service.py
  - api/tests/test_graph_router.py
  - specs/universal-node-edge-layer.md
done_when:
  - graph_nodes and graph_edges tables created via Alembic migration
  - CRUD endpoints for nodes and edges pass pytest
  - Traversal endpoint returns correct neighbors at depth=1
  - ruff check passes with zero warnings
  - coverage >= 80% on new modules
commands:
  - cd api && .venv/bin/ruff check .
  - cd api && .venv/bin/pytest tests/test_graph_router.py -v --tb=short
```

---

## Verification

- [ ] `pytest tests/test_graph_router.py` passes with ≥ 80% coverage on new modules.
- [ ] `ruff check api/app/routers/graph.py api/app/services/graph_service.py` exits 0.
- [ ] `GET /api/graph/nodes/{id}/neighbors` returns correct 1-hop results for a seeded graph.
- [ ] Bulk upsert of 500 nodes completes in < 2 s on CI hardware.
- [ ] `EXPLAIN ANALYZE` on node fetch by `node_id` shows index scan (not seq scan).
- [ ] Soft-deleted nodes do not appear in list or neighbor responses.
- [ ] Back-fill migration is idempotent: running it twice does not duplicate rows.

---

## Risks and Assumptions

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| ENUM extension requires table lock | Medium | Use `ALTER TYPE … ADD VALUE IF NOT EXISTS` (non-locking in PG ≥12) |
| Back-fill performance on large idea table | Medium | Batch in 1000-row chunks with sleep; run off-peak |
| Dual-write consistency gap | Low | Wrap in same DB transaction; rollback if node insert fails |
| JSONB GIN index size growth | Low | Monitor index bloat; partial index on `WHERE deleted_at IS NULL` |
| Traversal at depth=2 fan-out | Medium | Hard-cap result set at 500 nodes; return `"truncated": true` flag |

**Assumptions**:
- PostgreSQL ≥ 14 is available in all environments.
- Neo4j remains authoritative for heavy graph analytics; this layer is for **operational** queries and attribution only.
- The `payload` schema is intentionally open; type-specific validation lives in the resource service, not this layer.

---

## Known Gaps and Follow-up Tasks

- **Cypher bridge**: exposing `graph_nodes` as a Neo4j projection for analytics queries (future spec).
- **Subscription events**: WebSocket/SSE push when nodes/edges change (future spec).
- **ACL per node**: row-level ownership policy (future spec, depends on auth layer).
- **Phase 3–5 migration**: dual-write + deprecation of legacy columns (follow-up task after Phase 1–2 lands and stabilises).
- **Operator CLI**: `cc graph list --type idea` command (follow-up after router ships).
