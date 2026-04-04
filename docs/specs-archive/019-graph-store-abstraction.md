# Spec: GraphStore Abstraction + In-Memory Backend

## Purpose

Unblock Sprint 1 (spec 008) without Neo4j by introducing a GraphStore abstraction with an in-memory backend. Enables 5K+ npm packages, project API, and search. Neo4j adapter can be added later when scale or operational needs justify it.

## Requirements

- [x] `GraphStore` protocol/interface: `get_project()`, `search()`, `upsert_project()`, `add_dependency()`, `count_projects()`
- [x] In-memory implementation: dict-based projects + edges; optional JSON persistence for restart
- [x] Indexer writes to GraphStore (deps.dev + npm registry); `--target N` grows by deps; no Neo4j
- [x] `GET /api/projects/{ecosystem}/{name}` and `GET /api/search?q={query}` use GraphStore
- [x] Tests use in-memory store (no external DB)
- [ ] Future: Neo4j adapter implements same interface


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: 008, 024

## Task Card

```yaml
goal: Unblock Sprint 1 (spec 008) without Neo4j by introducing a GraphStore abstraction with an in-memory backend.
files_allowed:
  - api/app/adapters/__init__.py
  - api/app/adapters/graph_store.py
  - api/app/services/indexer_service.py
  - api/app/routers/projects.py
  - api/app/models/project.py
  - api/app/main.py
  - api/scripts/index_npm.py
  - api/tests/test_projects.py
  - specs/008-sprint-1-graph-foundation.md
done_when:
  - `GraphStore` protocol/interface: `get_project()`, `search()`, `upsert_project()`, `add_dependency()`, `count_projects()`
  - In-memory implementation: dict-based projects + edges; optional JSON persistence for restart
  - Indexer writes to GraphStore (deps.dev + npm registry); `--target N` grows by deps; no Neo4j
  - `GET /api/projects/{ecosystem}/{name}` and `GET /api/search?q={query}` use GraphStore
  - Tests use in-memory store (no external DB)
commands:
  - python3 -m pytest api/tests/test_projects.py -x -v
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

## GraphStore Interface (Python)

```python
# Protocol or ABC — minimal surface
def get_project(ecosystem: str, name: str) -> Project | None
def search(query: str, limit: int = 20) -> list[ProjectSummary]
def upsert_project(project: Project) -> None
def add_dependency(from_eco: str, from_name: str, to_eco: str, to_name: str) -> None
def count_projects() -> int
```

## Data Model (matches spec 008)

```yaml
Project:
  name: string
  ecosystem: string  # npm, pypi
  version: string
  description: string
  dependency_count: int  # derived

ProjectSummary (for search results):
  name: string
  ecosystem: string
  description: string
```

## Persistence (In-Memory Backend)

- **Runtime:** dict keyed by `(ecosystem, name)`; list of `(from_key, to_key)` edges
- **Restart:** Optional JSON file in `api/logs/graph_store.json` (or configurable path). Load on startup if present; save after index runs.
- **No new dependencies** — stdlib `json` only

## API Contract (unchanged from spec 008)

### `GET /api/projects/{ecosystem}/{name}`

**Response 200** — project from GraphStore  
**Response 404** — not found

### `GET /api/search?q={query}`

**Response 200** — `{"results": [...], "total": N}`. Search by name/description substring.


### Input Validation

- All string fields: min_length=1, max_length=1000
- Numeric fields: appropriate min/max bounds
- Required fields validated; missing returns 422
- Unknown fields rejected (Pydantic extra="forbid" where applicable)

## Files to Create/Modify

- `api/app/adapters/__init__.py`
- `api/app/adapters/graph_store.py` — Protocol + InMemoryGraphStore
- `api/app/services/indexer_service.py` — fetch from deps.dev, call GraphStore
- `api/app/routers/projects.py` — project and search routes
- `api/app/models/project.py` — Pydantic models
- `api/app/main.py` — include projects router, init GraphStore
- `api/scripts/index_npm.py` — CLI to run indexer
- `api/tests/test_projects.py` — API tests (use fresh InMemoryGraphStore per test)
- `specs/008-sprint-1-graph-foundation.md` — add "Uses GraphStore; Neo4j adapter future"

## Indexer (minimal)

- Fetch from deps.dev API + npm registry
- For each package: name, version, description, dependencies
- Call `upsert_project()`, `add_dependency()` for each
- `--target N`: grow graph by adding discovered dependencies until count ≥ N
- Target: ≥ 5,000 projects via `index_npm.py --target 5000`

## Acceptance Tests

- InMemoryGraphStore: upsert, get, search, count work correctly
- GET /api/projects/npm/react returns 200 when project exists
- GET /api/projects/npm/nonexistent returns 404
- GET /api/search?q=react returns matching results
- Indexer script runs without error; count_projects() ≥ 100 (or 5K for full run)
- No Neo4j or neo4j driver dependency

## Out of Scope

- Neo4j adapter (separate spec when needed)
- PyPI indexing — now implemented in [024-pypi-indexing.md](024-pypi-indexing.md)
- Coherence scores — implemented in spec 020
- Full 5K seed in CI (use smaller fixture for tests)

## See also

- [008-sprint-1-graph-foundation.md](008-sprint-1-graph-foundation.md) — API contract, data model
- docs/concepts/OSS-CONCEPT-MAPPING.md

## Decision Gates

- deps.dev API: no key required for basic usage (rate limits apply)
- Adding httpx: already a dependency

## Concurrency Behavior

- **Read operations**: Safe for concurrent access; no locking required.
- **Write operations**: Last-write-wins semantics; no optimistic locking for MVP.
- **Recommendation**: Clients should not assume atomic read-modify-write without explicit ETag support.

## Failure and Retry Behavior

- **Render error**: Show fallback error boundary with retry action.
- **API failure**: Display user-friendly error message; retry fetch on user action or after 5s.
- **Network offline**: Show offline indicator; queue actions for replay on reconnect.
- **Asset load failure**: Retry asset load up to 3 times; show placeholder on permanent failure.
- **Timeout**: API calls timeout after 10s; show loading skeleton until resolved or failed.

## Risks and Known Gaps

- **No auth gate**: Endpoints unprotected until C1 auth middleware applied.
- **No rate limiting**: Subject to abuse until M1 rate limiter active.
- **Single-node only**: No distributed locking; concurrent access may race.
- **Follow-up**: Add end-to-end browser tests for critical paths.


## Verification

```bash
python3 -m pytest api/tests/test_projects.py -x -v
```

## Known Gaps and Follow-up Tasks

- No known gaps at time of writing.
- Follow-up: review after initial implementation for completeness.
