---
idea_id: user-surfaces
status: done
source:
  - file: api/app/services/meta_service.py
    symbols: [MetaEndpointsResponse, MetaGraphResponse]
  - file: api/app/routers/meta.py
    symbols: [/api/meta endpoints]
  - file: api/app/models/meta.py
    symbols: [EndpointNode, ModuleNode]
done_when:
  - "`GET /api/meta/endpoints` returns HTTP 200 with `total`, `traced`, `coverage_pct`, and `endpoints` list."
  - "Each endpoint entry includes `path`, `method`, `path_hash`, `tags`, `has_trace`, and nullable `spec_id`/`idea_id`."
  - "`GET /api/meta/endpoints/{path_hash}` returns 200 for valid hash and 404 for invalid hash."
  - "`GET /api/meta/modules` returns HTTP 200 with list of module nodes including `trace_coverage_pct`."
  - "`GET /api/meta/modules/{module_name}` returns 200 for `ideas` (short name) and 404 for unknown."
  - "`GET /api/meta/coverage` returns `total_endpoints`, `traced_endpoints`, `coverage_pct`, and `untraced_paths`."
  - "All 5 verification scenarios pass in production."
  - "`coverage_pct` is consistent across `/endpoints?has_trace=false` count and `/coverage` report."
  - "No 500 errors on any meta endpoint under valid input."
  - "Meta router is registered in `main.py` with tag `meta`."
---

> **Parent idea**: [user-surfaces](../ideas/user-surfaces.md)
> **Source**: [`api/app/services/meta_service.py`](../api/app/services/meta_service.py) | [`api/app/routers/meta.py`](../api/app/routers/meta.py) | [`api/app/models/meta.py`](../api/app/models/meta.py)

# Metadata & Self-Discovery — Every Endpoint, Module, and Config is a Navigable Entity

**Spec ID**: 162-meta-self-discovery
**Task ID**: task_e9a79c46896ff3b0
**Status**: draft
**Priority**: high
**Author**: product-manager agent
**Date**: 2026-03-28

## Motivation

The system today has fragments of traceability: `@traces_to` decorators link functions to specs, spec-registry tracks specs, ideas are tracked in the portfolio. But there is no unified surface that answers: *"What does this API do, why does it exist, who wrote it, and what value does it generate?"*

The Living Codex `MetaNodeSystem` + `ServiceDiscoveryModule` pattern solves this by treating every first-class entity in the system as a node in the graph — including the system's own structure. Self-describing systems can be audited, explored, and improved without reading source code.

## Non-Goals

- Full graph traversal / Neo4j integration (Phase 2).
- Real-time usage streaming (future).
- Module-level static analysis (future).
- Authentication on meta endpoints (public read-only by design).

## API Specification

### `GET /api/meta/endpoints`

List all registered API endpoints as concept nodes.

**Query params:**
- `tag` — filter by tag (e.g. `ideas`, `health`)
- `has_trace` — `true`/`false` to filter traced/untraced
- `spec_id` — filter by spec
- `limit` — default 500, max 2000

**Response:**
```json
{
  "total": 142,
  "traced": 38,
  "coverage_pct": 26.8,
  "endpoints": [
    {
      "path": "/api/ideas",
      "method": "GET",
      "path_hash": "a1b2c3d4",
      "summary": "Browse the idea portfolio ranked by ROI",
      "tags": ["ideas"],
      "spec_id": "053",
      "idea_id": "portfolio-governance",
      "router_module": "app.routers.ideas",
      "has_trace": true
    }
  ]
}
```

### `GET /api/meta/endpoints/{path_hash}`

Return a single endpoint node by its path hash.

**Response:** Single `MetaEndpointNode` or 404.

### `GET /api/meta/modules`

List all API router modules with their trace coverage.

**Response:**
```json
{
  "total": 35,
  "modules": [
    {
      "module": "app.routers.ideas",
      "endpoint_count": 12,
      "spec_ids": ["053", "126"],
      "idea_ids": ["portfolio-governance"],
      "trace_coverage_pct": 75.0
    }
  ]
}
```

### `GET /api/meta/modules/{module_name}`

Return a single module node. `module_name` uses dot notation or the last segment (e.g., `ideas`).

**Response:** Single `MetaModuleNode` or 404.

### `GET /api/meta/coverage`

Summary of traceability coverage across the entire system.

**Response:**
```json
{
  "total_endpoints": 142,
  "traced_endpoints": 38,
  "coverage_pct": 26.8,
  "total_modules": 35,
  "modules_with_any_trace": 14,
  "untraced_paths": ["/api/audit", "/api/federation", "..."]
}
```

## CLI Commands

### `cc meta endpoints`

Lists all endpoints in table format:

```
METHOD  PATH                         SPEC     IDEA              TRACED
GET     /api/ideas                   053      portfolio-gov...  ✓
POST    /api/ideas                   053      portfolio-gov...  ✓
GET     /api/audit                   -        -                 ✗
...
Total: 142 endpoints, 38 traced (26.8%)
```

### `cc meta module <name>`

Shows a single module's endpoints and their trace status:

```
Module: app.routers.ideas
File:   api/app/routers/ideas.py
Specs:  053, 126
Ideas:  portfolio-governance

Endpoints (12):
  GET  /api/ideas                 [traced → spec:053]
  POST /api/ideas                 [traced → spec:053]
  GET  /api/ideas/{id}            [traced → spec:053]
  ...
Coverage: 75.0% (9/12 traced)
```

### Implementation

CLI commands are implemented as MCP tool handlers in `api/mcp_server.py` using the `meta_*` functions, or as dedicated CLI tool wrappers calling the API.

## Implementation Plan

### Phase 1 — API (this spec)

1. `api/app/routers/meta.py` — new router with endpoints above.
2. `api/app/services/meta_service.py` — introspection logic using `app.routes`, joined with `get_all_traces()`.
3. `api/app/models/meta.py` — Pydantic models.
4. Register `meta.router` in `main.py` under `/api` prefix with tag `meta`.

### Phase 2 — Web (follow-up spec)

5. `web/app/meta/page.tsx` — interactive system map page.
6. `web/components/meta/EndpointCard.tsx`
7. `web/components/meta/ModuleList.tsx`
8. `web/components/meta/CoverageBanner.tsx`

### Phase 3 — CLI (follow-up spec)

9. CLI `cc meta` commands via MCP or standalone handler.

## Verification Scenarios

### Scenario 1: List All Endpoints

**Setup**: API is running with at least one registered route.

**Action**:
```bash
curl -s https://api.coherencycoin.com/api/meta/endpoints | jq '{total, traced, coverage_pct}'
```

**Expected**: HTTP 200. Response contains `total > 0`, `traced >= 0`, `coverage_pct` between 0.0 and 100.0.
```json
{"total": 142, "traced": 38, "coverage_pct": 26.8}
```

**Edge case — tag filter**:
```bash
curl -s "https://api.coherencycoin.com/api/meta/endpoints?tag=ideas" | jq '.endpoints[].path'
```
Returns only paths under the `ideas` tag. No 500 errors. Unknown tag returns `{"total": 0, "traced": 0, "coverage_pct": 0.0, "endpoints": []}`.

### Scenario 3: List Modules with Coverage

**Setup**: API running with multiple routers registered.

**Action**:
```bash
curl -s https://api.coherencycoin.com/api/meta/modules | jq '{total, sample: [.modules[] | {module, endpoint_count, trace_coverage_pct}][:3]}'
```

**Expected**: HTTP 200. `total > 0`. Each module entry has `module` (string), `endpoint_count` (int ≥ 1), `trace_coverage_pct` (float 0–100).

**Edge case — module not found**:
```bash
curl -s "https://api.coherencycoin.com/api/meta/modules/nonexistent_module" -o /dev/null -w "%{http_code}"
```
Returns `404`.

### Scenario 5: Full Traceability Loop — Idea to Endpoint

**Setup**: Idea `portfolio-governance` exists. Spec `053` is in spec-registry. `GET /api/ideas` is traced via `@traces_to(spec="053", idea="portfolio-governance")`.

**Action**:
```bash
# 1. Confirm idea exists in portfolio
curl -s https://api.coherencycoin.com/api/ideas | jq '[.ideas[] | select(.id=="portfolio-governance")] | length'

# 2. Confirm spec exists in registry
curl -s https://api.coherencycoin.com/api/spec-registry/053 | jq '.id'

# 3. Confirm endpoint links back to both
curl -s "https://api.coherencycoin.com/api/meta/endpoints?tag=ideas" \
  | jq '[.endpoints[] | select(.path=="/api/ideas" and .method=="GET" and .spec_id=="053" and .idea_id=="portfolio-governance")] | length'
```

**Expected**:
1. Returns `1` or more (idea exists)
2. Returns `"053"` (spec exists)
3. Returns `1` (endpoint has correct spec + idea links — traceability loop is closed)

**Edge case — untraced endpoint has null spec/idea**:
```bash
curl -s "https://api.coherencycoin.com/api/meta/endpoints?has_trace=false" \
  | jq '[.endpoints[] | select(.spec_id != null or .idea_id != null)] | length'
```
Returns `0` — untraced endpoints must have `null` for spec_id and idea_id.

## Known Gaps and Follow-up Tasks

1. **Test registry integration** — `has_test` field requires a test-coverage registry. Spec TBD.
2. **Usage telemetry wiring** — `recent_calls` per endpoint requires API request logging. Spec TBD.
3. **Web `/meta` page** — Phase 2 follow-up spec (interactive system map).
4. **CLI `cc meta` commands** — Phase 3 follow-up spec.
5. **Neo4j graph projection** — Store `MetaEndpointNode` as graph nodes for traversal. Phase 4.
6. **Contributor attribution** — Wire endpoint authorship from git blame / contribution records. Phase 4.
7. **Periodic coverage report** — Emit coverage snapshot to `runtime_events` table nightly. Phase 3.

---

## Acceptance Criteria

- [ ] `GET /api/meta/endpoints` returns HTTP 200 with `total`, `traced`, `coverage_pct`, and `endpoints` list.
- [ ] Each endpoint entry includes `path`, `method`, `path_hash`, `tags`, `has_trace`, and nullable `spec_id`/`idea_id`.
- [ ] `GET /api/meta/endpoints/{path_hash}` returns 200 for valid hash and 404 for invalid hash.
- [ ] `GET /api/meta/modules` returns HTTP 200 with list of module nodes including `trace_coverage_pct`.
- [ ] `GET /api/meta/modules/{module_name}` returns 200 for `ideas` (short name) and 404 for unknown.
- [ ] `GET /api/meta/coverage` returns `total_endpoints`, `traced_endpoints`, `coverage_pct`, and `untraced_paths`.
- [ ] All 5 verification scenarios pass in production.
- [ ] `coverage_pct` is consistent across `/endpoints?has_trace=false` count and `/coverage` report.
- [ ] No 500 errors on any meta endpoint under valid input.
- [ ] Meta router is registered in `main.py` with tag `meta`.
