# Spec 171 — Metadata and Self-Discovery: Every API Endpoint, Module, and Config is a Navigable Entity

**Spec ID**: task_2bfd59d1e7156ad1
**Status**: draft
**Author**: product-manager agent
**Date**: 2026-03-28
**Priority**: High

---

## Purpose

Make the Coherence Network fully self-describing: every API endpoint, code module, and configuration
entity is a navigable graph node with traced edges to the idea, spec, and contributors that created
it. This closes the traceability loop (idea → spec → code → endpoint → usage → value) and enables
agents and developers to reason about system coverage, gaps, and lineage without reading source code.

## Out of Scope

- Writing endpoint nodes to Neo4j as graph citizens (Phase 3; out of scope for initial MVP)
- Surfacing configuration files (`model_routing.json`, Docker Compose) as `MetaConfig` nodes (Phase 4)
- Retroactively adding `@traces_to` annotations to existing endpoints (follow-up annotation campaign)
- Authentication/authorisation changes for meta endpoints (read-only, public; auth is out of scope)
- Real-time push notifications when traceability score changes

---

## Summary

The Coherence Network is a graph of ideas, specs, code, contributors, and value. But the system
itself — its API endpoints, code modules, configuration — is not yet a first-class graph citizen.
There is no way for an agent, developer, or user to ask "which idea spawned this endpoint?",
"which spec governs this module?", or "who contributed to this feature?"

This spec closes the **traceability loop**: `idea → spec → code → API endpoint → usage → value`.

Every API endpoint becomes a **concept node** with edges to the spec that defined it, the idea
that inspired it, and the contributors who built it. Every code module is linked to its governing
specs and originating ideas. The system describes itself.

This is drawn from the Living Codex **MetaNodeSystem** and **ServiceDiscoveryModule** patterns:
treat infrastructure as ontology, make configuration navigable as knowledge.

---

## Background and Motivation

### The Traceability Gap

Today the Coherence Network tracks:
- Ideas (`/api/ideas`) — the origin of features
- Specs (`/api/spec-registry`) — the governing documents
- Contributions (`/api/contributions`) — the value produced

But there is **no link** between these artifacts and the live, running API surface they produced.
A developer looking at `GET /api/concepts` cannot discover that it came from idea `X`, was defined
in spec `Y`, and was implemented by contributor `Z`.

### What the MetaNodeSystem Solves

The Living Codex MetaNodeSystem principle: every entity in the system should be able to describe
itself as a graph node with typed edges. An API endpoint is not just a URL — it is a **node** with:
- `IMPLEMENTS` edge to its spec
- `SPAWNED_FROM` edge to its originating idea
- `CONTRIBUTED_BY` edge to contributors
- `MEASURED_BY` edge to value/usage metrics

When the system can describe itself, it becomes self-improving: agents can reason about what exists,
what gaps remain, and where to focus next.

### Why Now

The pipeline now has reliable spec → impl → test → review → deploy flow. The missing piece is
surfacing **why** each endpoint exists and **who** it serves. This closes the intelligence loop.

---

## Requirements

### FR-1: Endpoint Discovery API

**`GET /api/meta/endpoints`** — List all API endpoints as concept nodes.

Each endpoint node includes:
- `path` — the URL pattern (e.g., `/api/concepts`)
- `method` — HTTP method (`GET`, `POST`, etc.)
- `tag` — OpenAPI tag (e.g., `concepts`, `ideas`)
- `summary` — one-line description from OpenAPI
- `spec_ids` — list of spec IDs that define this endpoint (from `@traces_to` annotations)
- `idea_ids` — list of idea IDs linked to this endpoint (transitively via specs)
- `contributors` — contributor handles who implemented this endpoint (from git blame / contribution records)
- `call_count_30d` — usage count over last 30 days (from traceability/audit log, 0 if unknown)
- `last_called_at` — ISO 8601 timestamp of most recent call (null if never)
- `status` — `active`, `deprecated`, or `unknown`

Response shape:
```json
{
  "endpoints": [
    {
      "path": "/api/concepts",
      "method": "GET",
      "tag": "concepts",
      "summary": "List all concepts in the graph",
      "spec_ids": ["108"],
      "idea_ids": ["concept-graph-foundation"],
      "contributors": ["ursmuff"],
      "call_count_30d": 42,
      "last_called_at": "2026-03-28T04:00:00Z",
      "status": "active"
    }
  ],
  "total": 87,
  "generated_at": "2026-03-28T05:00:00Z"
}
```

Query parameters:
- `tag` — filter by OpenAPI tag
- `spec_id` — filter to endpoints defined by a specific spec
- `idea_id` — filter to endpoints linked to a specific idea
- `status` — filter by status (`active`, `deprecated`, `unknown`)
- `limit` / `offset` — pagination

**`GET /api/meta/endpoints/{path_hash}`** — Get a single endpoint node by its SHA-1 of `{method}:{path}`.

Returns the same shape as a single item in the list, plus:
- `openapi_operation` — the raw OpenAPI operation object
- `recent_callers` — last 5 caller IPs/agent IDs (anonymized)

---

### FR-2: Module Discovery API

**`GET /api/meta/modules`** — List all code modules as graph nodes.

A "module" is a Python file in `api/app/` or a web page in `web/app/`. Each module node:
- `name` — module name (e.g., `routers.concepts`, `app/page`)
- `path` — repo-relative path (e.g., `api/app/routers/concepts.py`)
- `type` — `api_router`, `service`, `model`, `adapter`, `web_page`, `web_component`
- `spec_ids` — specs that govern this module
- `idea_ids` — ideas that led to this module's creation
- `contributors` — contributors who touched this file
- `line_count` — lines of code
- `last_modified` — ISO 8601 timestamp
- `test_file` — path to primary test file (null if no test)

Response shape:
```json
{
  "modules": [
    {
      "name": "routers.concepts",
      "path": "api/app/routers/concepts.py",
      "type": "api_router",
      "spec_ids": ["108"],
      "idea_ids": ["concept-graph-foundation"],
      "contributors": ["ursmuff"],
      "line_count": 156,
      "last_modified": "2026-03-20T12:00:00Z",
      "test_file": "api/tests/test_concepts.py"
    }
  ],
  "total": 43,
  "generated_at": "2026-03-28T05:00:00Z"
}
```

Query parameters:
- `type` — filter by module type
- `spec_id` — filter to modules governed by a spec
- `idea_id` — filter to modules from an idea
- `has_tests` — `true`/`false` filter

**`GET /api/meta/modules/{module_name}`** — Get a single module node.

Returns the same shape plus:
- `exports` — list of exported function/class names
- `imports` — list of internal imports (for dependency graph)
- `git_log` — last 5 commits touching this file

---

### FR-3: System Self-Description

**`GET /api/meta/summary`** — Single-endpoint system overview.

```json
{
  "system": "Coherence Network",
  "version": "main@<git_sha>",
  "generated_at": "2026-03-28T05:00:00Z",
  "counts": {
    "endpoints": 87,
    "modules": 43,
    "specs_linked": 34,
    "specs_unlinked": 9,
    "ideas_traced": 28,
    "ideas_untraced": 156
  },
  "traceability_score": 0.39,
  "coverage": {
    "endpoints_with_spec": 34,
    "endpoints_without_spec": 53,
    "modules_with_tests": 31,
    "modules_without_tests": 12
  }
}
```

The `traceability_score` (0.0–1.0) measures `endpoints_with_spec / total_endpoints`. This is the
primary health metric for self-discovery. Target: > 0.80.

---

### FR-4: Spec-to-Endpoint Linkage

**`GET /api/meta/trace/{idea_or_spec_id}`** — Trace an idea or spec to all its produced artifacts.

```json
{
  "id": "108",
  "type": "spec",
  "title": "Concept Graph Foundation",
  "endpoints": [
    { "method": "GET", "path": "/api/concepts" },
    { "method": "POST", "path": "/api/concepts" },
    { "method": "GET", "path": "/api/concepts/{id}" }
  ],
  "modules": [
    { "name": "routers.concepts", "path": "api/app/routers/concepts.py" }
  ],
  "contributors": ["ursmuff"],
  "first_commit": "2026-01-15T09:00:00Z",
  "call_count_30d": 127
}
```

---

### FR-5: CLI Commands

**`cc meta endpoints`** — Print a table of all API endpoints with their spec and idea links.

```
$ cc meta endpoints
PATH                          METHOD  TAG          SPEC   IDEA
/api/concepts                 GET     concepts     108    concept-graph
/api/concepts/{id}            GET     concepts     108    concept-graph
/api/ideas                    GET     ideas        053    portfolio-gov
...
87 endpoints total. Traceability score: 0.39
```

**`cc meta endpoints --tag concepts`** — Filter by tag.

**`cc meta module <name>`** — Show details for a specific module.

```
$ cc meta module routers.concepts
Module: routers.concepts
Path:   api/app/routers/concepts.py
Type:   api_router
Spec:   108 (Concept Graph Foundation)
Idea:   concept-graph-foundation
Lines:  156
Tests:  api/tests/test_concepts.py ✓
Last:   2026-03-20 by ursmuff
```

**`cc meta summary`** — Print the system summary with traceability score.

```
$ cc meta summary
System:             Coherence Network (main@abc1234)
Endpoints:          87 (34 with spec, 53 without)
Modules:            43 (31 tested, 12 untested)
Traceability score: 0.39  ←  target: 0.80
```

---

### FR-6: Web Page — `/meta`

An interactive system map at `/meta` with three views:

**View 1: Endpoint Map**
- Table/grid of all API endpoints grouped by tag
- Each endpoint row shows: path, method, spec badge (linked), idea badge (linked), call count
- Click spec badge → navigates to `/specs/{id}`
- Click idea badge → navigates to `/ideas/{id}`
- Filter bar: by tag, by spec, by coverage status

**View 2: Module Graph**
- Visual graph (using existing graph UI components) showing modules as nodes
- Edges: `IMPLEMENTS` (module → spec), `SPAWNED_FROM` (module → idea)
- Node color by type (router=blue, service=green, model=gray, web=purple)
- Click node → side panel with module details and navigation links

**View 3: Traceability Score**
- Big number: current traceability score (0.0–1.0)
- Progress bar toward 0.80 target
- List of top 10 "untraced" endpoints (no spec link) — actionable gap list
- Historical chart: score over last 30 days (if data available)

---

## Data Model

### MetaEndpointNode

```python
class MetaEndpointNode(BaseModel):
    path: str
    method: str  # GET, POST, PUT, DELETE, PATCH
    path_hash: str  # SHA-1 of "{method}:{path}"
    tag: str
    summary: str
    spec_ids: list[str]
    idea_ids: list[str]
    contributors: list[str]
    call_count_30d: int
    last_called_at: datetime | None
    status: Literal["active", "deprecated", "unknown"]
```

### MetaModuleNode

```python
class MetaModuleNode(BaseModel):
    name: str
    path: str
    type: Literal["api_router", "service", "model", "adapter", "web_page", "web_component"]
    spec_ids: list[str]
    idea_ids: list[str]
    contributors: list[str]
    line_count: int
    last_modified: datetime
    test_file: str | None
```

### MetaSummary

```python
class MetaSummary(BaseModel):
    system: str
    version: str
    generated_at: datetime
    counts: dict[str, int]
    traceability_score: float  # 0.0-1.0
    coverage: dict[str, int]
```

---

## Implementation Strategy

### Phase 1 — Static Discovery (MVP)

For the MVP, endpoint and module data is **introspected at startup** from:

1. **Endpoints**: iterate `app.routes` from the FastAPI app instance; extract path, method, tag,
   summary. Spec linkage comes from `@traces_to` decorator metadata already present on route
   handlers. No database writes — purely in-memory at startup, re-read on each request or cached
   with 60s TTL.

2. **Modules**: walk `api/app/` directory at startup; extract file metadata (path, line count,
   last modified). Parse `# Implements: spec-XXX` comments in file headers to extract spec links.
   Contributor data from `git log --follow --format="%an" -- <file>` (cached).

3. **Idea linkage**: transitively from spec → idea via the existing `spec_registry` service and
   `idea_service` (specs already have `idea_id` fields).

### Phase 2 — Usage Metrics

Pull `call_count_30d` and `last_called_at` from the existing traceability/audit log (already
records requests via the `traceability` middleware). Query is a GROUP BY on `endpoint` over the
last 30 days.

### Phase 3 — Graph Integration

Write endpoint nodes to Neo4j as `MetaEndpoint` nodes with `IMPLEMENTS_SPEC` and
`SPAWNED_FROM_IDEA` edges, enabling graph traversal and the web module graph view.

---

## API Endpoint Summary

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/meta/endpoints` | List all endpoints as concept nodes |
| GET | `/api/meta/endpoints/{path_hash}` | Get single endpoint node |
| GET | `/api/meta/modules` | List all code modules as graph nodes |
| GET | `/api/meta/modules/{module_name}` | Get single module node |
| GET | `/api/meta/summary` | System self-description summary |
| GET | `/api/meta/trace/{id}` | Trace idea/spec to its artifacts |

---

## Files to Create or Modify

### New Files

- `api/app/routers/meta.py` — FastAPI router for all `/api/meta/*` routes
- `api/app/services/meta_service.py` — Business logic: endpoint introspection, module discovery,
  traceability computation
- `api/app/models/meta.py` — Pydantic models: `MetaEndpointNode`, `MetaModuleNode`,
  `MetaSummary`, `MetaTraceResult`
- `api/tests/test_meta.py` — Pytest tests for all meta endpoints
- `web/app/meta/page.tsx` — Web page at `/meta` with three views
- `web/app/meta/EndpointMap.tsx` — Endpoint table component
- `web/app/meta/ModuleGraph.tsx` — Module graph component
- `web/app/meta/TraceabilityScore.tsx` — Score display component

### Modified Files

- `api/app/main.py` — Register `meta.router` with `prefix="/api", tags=["meta"]`
- `cli/bin/cc.mjs` — Add `meta` subcommand with `endpoints`, `module <name>`, `summary` actions
- `web/app/layout.tsx` or nav component — Add `/meta` link to navigation

---

## Verification Scenarios

### Scenario 1: List endpoints returns structured data

**Setup**: Production API is running at `https://api.coherencycoin.com`

**Action**:
```bash
curl -s https://api.coherencycoin.com/api/meta/endpoints | jq '.total, .endpoints[0].path, .endpoints[0].method'
```

**Expected result**:
- HTTP 200
- `total` is an integer > 0 (e.g., `87`)
- `endpoints[0].path` is a string starting with `/api/`
- `endpoints[0].method` is one of `GET`, `POST`, `PUT`, `DELETE`, `PATCH`

**Full shape check**:
```bash
curl -s https://api.coherencycoin.com/api/meta/endpoints | jq '.endpoints[0] | keys | sort'
# Expected: ["call_count_30d","contributors","idea_ids","last_called_at","method","path","path_hash","spec_ids","status","summary","tag"]
```

**Edge case — bad tag filter returns empty, not error**:
```bash
curl -s "https://api.coherencycoin.com/api/meta/endpoints?tag=nonexistent-xyz" | jq '{total, http_status: 200}'
# Expected: {"total": 0, "http_status": 200}
```

---

### Scenario 2: Traceability score is computed and valid

**Setup**: System is running; at least one `@traces_to` annotation exists in the codebase.

**Action**:
```bash
curl -s https://api.coherencycoin.com/api/meta/summary | jq '{score: .traceability_score, endpoints: .counts.endpoints, with_spec: .coverage.endpoints_with_spec, without_spec: .coverage.endpoints_without_spec}'
```

**Expected result**:
- `traceability_score` is a float between 0.0 and 1.0
- `counts.endpoints` equals `coverage.endpoints_with_spec + coverage.endpoints_without_spec`
- `version` contains a git SHA (`main@` prefix pattern)
- `generated_at` is a valid ISO 8601 timestamp

**Edge case — score is numeric even if no annotations**:
```bash
curl -s https://api.coherencycoin.com/api/meta/summary | jq '.traceability_score | type'
# Expected: "number"  (not "null" or error)
```

---

### Scenario 3: Trace a known spec to its endpoints

**Setup**: Spec `053` exists in the spec registry and has `@traces_to(spec="053")` on at least one route handler.

**Action**:
```bash
curl -s https://api.coherencycoin.com/api/meta/trace/053 | jq '{type: .type, title: .title, endpoint_count: (.endpoints | length)}'
```

**Expected result**:
- HTTP 200
- `type` is `"spec"`
- `title` is a non-empty string
- `endpoints` array has at least one entry with `{"method": "GET", "path": "/api/ideas"}`

**Edge case — unknown ID returns 404**:
```bash
curl -o /dev/null -w "%{http_code}" -s https://api.coherencycoin.com/api/meta/trace/spec-does-not-exist-999
# Expected output: 404
```

---

### Scenario 4: Module discovery lists known API router

**Setup**: `api/app/routers/concepts.py` exists and is non-empty.

**Action**:
```bash
curl -s https://api.coherencycoin.com/api/meta/modules | jq '.modules[] | select(.name == "routers.concepts") | {path, type, line_count}'
```

**Expected result**:
- Returns exactly one object with `path` equal to `"api/app/routers/concepts.py"`
- `type` equals `"api_router"`
- `line_count` is an integer greater than 0

**Edge case — nonexistent module returns 404**:
```bash
curl -o /dev/null -w "%{http_code}" -s https://api.coherencycoin.com/api/meta/modules/nonexistent.module.xyz
# Expected output: 404
```

---

### Scenario 5: CLI `cc meta summary` prints structured output

**Setup**: `cc` CLI available and configured to point at production API.

**Action**:
```bash
cc meta summary
```

**Expected result** (stdout contains all four lines):
```
System:             Coherence Network (main@...)
Endpoints:          <N> (<M> with spec, <K> without)
Modules:            <N> (<M> tested, <K> untested)
Traceability score: <float>  ←  target: 0.80
```

The `<float>` is between 0.00 and 1.00. The counts `<N>`, `<M>`, `<K>` are non-negative integers.

**Edge case — nonexistent module lookup exits non-zero**:
```bash
cc meta module does-not-exist-xyz-module; echo "exit: $?"
# Expected: stderr contains "not found" (or similar), stdout empty, exit code is 1
```

---

## Risks and Assumptions

- **Git blame latency (Medium)**: Running `git log` on every module file at startup could be slow on large repos. Mitigation: cache results at server startup, refresh on a 5-minute TTL.
- **Incomplete `@traces_to` annotations (High)**: Most existing endpoints lack spec annotations. This is expected — the traceability_score metric is designed to surface and track this gap; links are added incrementally via the annotation campaign follow-up task.
- **Internal route pollution (Medium)**: FastAPI `app.routes` includes `/docs`, `/openapi.json`, and redirect routes. Mitigation: filter to only routes that carry at least one tag; exclude Swagger/redoc introspection routes.
- **Neo4j unavailable in dev/test (Low)**: Phase 3 graph integration requires Neo4j. Mitigation: Phase 3 is behind a feature flag; Phase 1 static discovery works with no graph DB.
- **Web graph performance with 40+ nodes (Low)**: Cap rendered nodes at 50; use existing D3/graph library already present in the web codebase.
- **Stale module data between deploys (Low)**: Module introspection is cached; files that change without a server restart will show stale data. Mitigation: 60s TTL + admin-only `POST /api/meta/refresh` to force re-scan.

---

## Known Gaps and Follow-up Tasks

- **Annotation coverage campaign (follow-up task)**: After implementation, a follow-up task should add `@traces_to` annotations to the 50+ endpoints currently lacking them, targeting traceability score ≥ 0.80.
- **Contributor attribution from git (follow-up task)**: Phase 1 uses `git log`; a more reliable approach (Phase 2+) is to cross-reference git commits with the `contributions` table using `contribution.spec_id`.
- **Configuration as nodes (follow-up task)**: Config files (`model_routing.json`, Docker Compose services) can be added as `MetaConfig` nodes in Phase 4, after the endpoint/module foundation is stable.
- **Webhook on spec merge (follow-up task)**: When a spec is merged, automatically scan for new endpoints matching the spec's routes and update `spec_ids` linkage to keep the graph current.
- **Value lineage closure (follow-up task)**: Connect `MetaEndpoint.call_count_30d` to the value lineage model (`/api/value-lineage`) so that API usage can be attributed back to the idea that spawned the endpoint, completing the full idea → value loop.

---

## Acceptance Criteria

Automated test coverage: `api/tests/test_meta.py` must pass (run with `cd api && python -m pytest tests/test_meta.py -v`).

- [ ] `GET /api/meta/endpoints` returns HTTP 200 with `endpoints` array and `total` count — covered by `tests/test_meta.py::test_list_endpoints`
- [ ] `GET /api/meta/endpoints?tag=ideas` returns only idea-tagged endpoints — covered by `tests/test_meta.py::test_list_endpoints_filter_tag`
- [ ] `GET /api/meta/endpoints/{path_hash}` returns HTTP 404 for unknown hash — covered by `tests/test_meta.py::test_get_endpoint_not_found`
- [ ] `GET /api/meta/modules` returns HTTP 200 with `modules` array — covered by `tests/test_meta.py::test_list_modules`
- [ ] `GET /api/meta/modules/{name}` returns 404 for unknown module name — covered by `tests/test_meta.py::test_get_module_not_found`
- [ ] `GET /api/meta/summary` returns `traceability_score` as float 0.0–1.0 — covered by `tests/test_meta.py::test_summary`
- [ ] `GET /api/meta/trace/{spec_id}` returns endpoints and modules linked to that spec — covered by `tests/test_meta.py::test_trace_spec`
- [ ] `GET /api/meta/trace/nonexistent` returns HTTP 404 — covered by `tests/test_meta.py::test_trace_not_found`
- [ ] `cc meta endpoints` prints endpoint table to stdout with traceability score footer
- [ ] `cc meta module routers.concepts` prints module details including spec and idea links
- [ ] `cc meta summary` prints system overview with traceability score
- [ ] `/meta` web page loads without error and shows endpoint list grouped by tag
- [ ] Traceability score equals `endpoints_with_spec / total_endpoints` — covered by `tests/test_meta.py::test_traceability_score_formula`
- [ ] All 5 Verification Scenarios pass against production
