# Spec: Sprint 1 — Graph Foundation

## Purpose

Per docs/PLAN.md Sprint 1: 5K+ npm packages; API returns real data; search works.
This spec defines the foundational graph schema, indexer, and API to serve project data.

**Implementation path:** Use [019-graph-store-abstraction.md](019-graph-store-abstraction.md) — GraphStore abstraction with in-memory backend. Neo4j adapter can be added later when scale justifies it.

## Requirements

- [x] GraphStore: `Project` nodes with `name`, `ecosystem`, `version`; dependency edges (spec 019)
- [x] Indexer service: fetches npm package metadata from deps.dev; writes to GraphStore (spec 019)
- [x] Index ≥ 5,000 npm packages (`index_npm.py --target 5000`)
- [x] `GET /api/projects/{ecosystem}/{name}` returns project data from graph
- [x] `GET /api/search?q={query}` returns matching projects (name/description search)
- [x] API uses GraphStore (in-memory for MVP); no mocks

## API Contract

### `GET /api/projects/{ecosystem}/{name}`

**Response 200**
```json
{
  "name": "react",
  "ecosystem": "npm",
  "version": "18.2.0",
  "description": "React is a JavaScript library...",
  "dependency_count": 7
}
```

**Response 404** — Project not found

### `GET /api/search?q={query}`

**Response 200**
```json
{
  "results": [
    { "name": "react", "ecosystem": "npm", "description": "..." }
  ],
  "total": 42
}
```

## Data Model

```yaml
Project (GraphStore node):
  name: string
  ecosystem: string (npm, pypi, ...)
  version: string
  description: string
DEPENDS_ON (edge): Project -> Project
```

## Files to Create/Modify

- `api/app/adapters/graph_store.py` — GraphStore interface + in-memory impl (spec 019)
- `api/app/routers/projects.py` — project and search routes
- `api/app/services/indexer_service.py` — fetch and index logic
- `api/scripts/index_npm.py` — CLI to run indexer for npm
- `api/app/models/project.py` — Pydantic models

## Acceptance Tests

- Indexer runs without error; GraphStore contains ≥ 5K Project nodes (or 100+ for test fixture)
- GET /api/projects/npm/react returns 200 with valid data
- GET /api/search?q=react returns non-empty results
- All tests use in-memory GraphStore (no external DB)

## Out of Scope

- PyPI indexing (Sprint 2+)
- Coherence scores (Sprint 2)
- Web UI (Sprint 2+)

## See also

- [019-graph-store-abstraction.md](019-graph-store-abstraction.md) — GraphStore abstraction, in-memory backend

## Decision Gates

- deps.dev API: no key for basic usage; rate limits apply
- Neo4j adapter: future; add when scale or traversal needs justify it
