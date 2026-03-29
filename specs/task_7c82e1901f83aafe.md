# Spec — Concept Layer: CRUD for 184 Universal Concepts with Typed Relationships

**ID:** task_7c82e1901f83aafe
**Alias:** concept-layer-crud
**Status:** approved
**Priority:** high
**Category:** ontology / knowledge graph
**Author:** claude (product-manager)
**Created:** 2026-03-28
**Task:** task_7c82e1901f83aafe

---

## Summary

Port the Living Codex ontology (184 concepts, 46 relationship types, 53 axes) into Coherence
Network as a first-class, navigable resource. Concepts become the semantic backbone of the
platform: every idea, spec, task, and news item can be tagged with concepts, and any concept
can be explored to see what connects to it.

The feature has four surfaces:

| Surface | What it provides |
|---------|-----------------|
| **API** | REST CRUD + edge management + tagging + search |
| **Web** | `/concepts` card grid + `/concepts/{id}` detail drill-down |
| **CLI** | `cc concepts`, `cc concept <id>`, `cc concept link <from> <rel> <to>` |
| **MCP** | `coherence_list_concepts`, `coherence_get_concept`, `coherence_link_concepts` |

Ontology seed data lives in `config/ontology/` and is loaded at startup:
- `core-concepts.json` — 184 universal concepts
- `core-relationships.json` — 46 relationship types
- `core-axes.json` — 53 ontological axes

---

## Goals

| # | Goal |
|---|------|
| G1 | All 184 Living Codex concepts are accessible via API, web, and CLI without manual data entry. |
| G2 | Users can create, read, update, and delete user-defined concepts that extend the ontology. |
| G3 | Typed edges (46 relationship types) can be created between any two concepts. |
| G4 | Ideas, specs, tasks, and news can be tagged with concepts; concepts are discoverable from those items. |
| G5 | Concepts are navigable: any concept page shows related ideas, specs, edges, and contributors. |
| G6 | MCP tools expose the concept layer to AI agents so they can query and extend the ontology. |
| G7 | Proof of working: `GET /api/concepts/stats` returns `{"concepts": 184, "relationship_types": 46, "axes": 53}` in production. |

---

## Architecture Overview

```
config/ontology/
  core-concepts.json        ← 184 seed concepts (loaded at startup)
  core-relationships.json   ← 46 relationship types
  core-axes.json            ← 53 axes

api/app/services/concept_service.py    ← in-memory store + CRUD logic
api/app/routers/concepts.py            ← FastAPI routes
api/app/services/mcp_tool_registry.py  ← MCP tool handlers (concept tools to add)

web/app/concepts/page.tsx              ← card grid, stats banner
web/app/concepts/[id]/page.tsx         ← detail: edges, axes, related items

cli/lib/commands/concepts.mjs          ← cc concepts / cc concept <id>
```

---

## Data Model

### Concept

```json
{
  "id": "string (slug, unique)",
  "name": "string",
  "description": "string",
  "typeId": "string (e.g. codex.ucore.base | codex.ucore.user)",
  "level": "integer (0=Core, 1=Primary, 2=Secondary, 3=Derived)",
  "keywords": ["string"],
  "axes": ["string (axis id)"],
  "parentConcepts": ["string (concept id)"],
  "childConcepts": ["string (concept id)"],
  "userDefined": "boolean",
  "createdAt": "ISO 8601 UTC (user-defined concepts only)"
}
```

### ConceptEdge

```json
{
  "id": "string (uuid)",
  "from": "string (concept id)",
  "to": "string (concept id)",
  "type": "string (relationship type id, e.g. resonates-with)",
  "created_by": "string",
  "created_at": "ISO 8601 UTC"
}
```

### ConceptStats

```json
{
  "concepts": 184,
  "relationship_types": 46,
  "axes": 53,
  "user_edges": 0,
  "user_concepts": 0
}
```

---

## API Specification

### Core CRUD

| Method | Path | Description | Status codes |
|--------|------|-------------|-------------|
| `GET` | `/api/concepts` | List concepts (paged). Query: `limit`, `offset` | 200 |
| `POST` | `/api/concepts` | Create user-defined concept | 201, 409 (duplicate id) |
| `GET` | `/api/concepts/search` | Full-text search. Query: `q` (required), `limit` | 200 |
| `GET` | `/api/concepts/stats` | Ontology statistics | 200 |
| `GET` | `/api/concepts/{id}` | Get single concept with metadata | 200, 404 |
| `PATCH` | `/api/concepts/{id}` | Update mutable fields (name, description, keywords, axes) | 200, 404 |
| `DELETE` | `/api/concepts/{id}` | Delete user-defined concept (core concepts: 403) | 204, 403, 404 |

### Edge Management

| Method | Path | Description | Status codes |
|--------|------|-------------|-------------|
| `GET` | `/api/concepts/{id}/edges` | Get all edges for a concept (in + out) | 200, 404 |
| `POST` | `/api/concepts/{id}/edges` | Create typed edge from this concept to another | 201, 404 |

### Tagging (associating entities with concepts)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/ideas/{idea_id}/concepts` | Tag idea with concept IDs |
| `GET` | `/api/ideas/{idea_id}/concepts` | Get concepts tagged on idea |
| `POST` | `/api/specs/{spec_id}/concepts` | Tag spec with concept IDs |
| `GET` | `/api/specs/{spec_id}/concepts` | Get concepts tagged on spec |

### Discovery

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/concepts/{id}/related` | Ideas and specs tagged with this concept |

### Translation (bonus surface)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/concepts/{id}/translate` | Translate concept through a worldview lens. Query: `from_lens`, `to_lens` |

---

## Request / Response Schemas

### POST /api/concepts (body)

```json
{
  "id": "my-concept",
  "name": "My Concept",
  "description": "A user-defined extension to the ontology",
  "type_id": "codex.ucore.user",
  "level": 0,
  "keywords": ["innovation", "custom"],
  "parent_concepts": ["activity"],
  "child_concepts": [],
  "axes": ["temporal"]
}
```

### POST /api/concepts/{id}/edges (body)

```json
{
  "from_id": "consciousness",
  "to_id": "awareness",
  "relationship_type": "resonates-with",
  "created_by": "contributor-123"
}
```

---

## MCP Tools (to add to `mcp_tool_registry.py`)

### `coherence_list_concepts`

Lists concepts from the ontology, optionally filtered by search query.

**Input schema:**
```json
{
  "type": "object",
  "properties": {
    "limit": {"type": "integer", "default": 50},
    "offset": {"type": "integer", "default": 0},
    "search": {"type": "string"}
  }
}
```

**Handler:** calls `concept_service.search_concepts(query=search, limit=limit)` when search
is provided, otherwise `concept_service.list_concepts(limit=limit, offset=offset)`.

---

### `coherence_get_concept`

Retrieves a single concept by ID with full metadata, edges, and related items.

**Input schema:**
```json
{
  "type": "object",
  "properties": {
    "concept_id": {"type": "string"}
  },
  "required": ["concept_id"]
}
```

**Handler:** calls `concept_service.get_concept(concept_id)`. Returns `{"error": "..."}` if
not found.

---

### `coherence_link_concepts`

Creates a typed edge between two concepts.

**Input schema:**
```json
{
  "type": "object",
  "properties": {
    "from_id": {"type": "string"},
    "to_id": {"type": "string"},
    "relationship_type": {"type": "string"},
    "created_by": {"type": "string"}
  },
  "required": ["from_id", "to_id", "relationship_type"]
}
```

**Handler:** validates both concepts exist, calls `concept_service.create_edge(...)`.

---

## Web Pages

### `/concepts` (card grid)

- Stats banner: `{n} concepts · {r} relationship types · {a} axes`
- Card per concept: name, level badge (Core/Primary/Secondary/Derived), first 2 keywords, axis count
- Search input (client-side filter or server-side via `/api/concepts/search`)
- Click card → navigates to `/concepts/{id}`

### `/concepts/{id}` (detail page)

- Full concept metadata: name, description, typeId, level badge
- Axes chips
- Keywords list
- Parent concepts → clickable links
- Child concepts → clickable links
- Typed edges panel: outgoing and incoming edges with relationship type label
- Related ideas panel: count + list of idea IDs/names tagged with this concept
- Related specs panel: count + list of spec IDs tagged with this concept

---

## CLI Commands

### `cc concepts [--limit N] [--search <query>]`

Lists concepts from the ontology with stats footer.

```
consciousness     Core   · temporal, systemic, emergent
creativity        Primary · temporal, ucore
...
──────────────────────────────────────
184 concepts · 46 rel-types · 53 axes · 0 user-edges
```

### `cc concept <id>`

Shows full concept detail: metadata, axes, edges, related items.

```
consciousness (Core)
  The state of being aware and able to experience and feel.
  Axes: temporal, systemic, emergent, ucore
  Keywords: awareness, mind, perception, sentience
  Edges (2 outgoing):
    resonates-with → awareness
    emerges-from  → neural-activity
  Related: 3 ideas, 1 spec
```

### `cc concept link <from-id> <rel-type> <to-id>`

Creates a typed edge between two concepts.

```
cc concept link consciousness resonates-with creativity
✓ Edge created: consciousness --[resonates-with]--> creativity
```

---

## Ontology Seed Data

The three config files in `config/ontology/` are the authoritative source and are loaded
at API startup by `concept_service._load_ontology()`.

| File | Key | Count | Notes |
|------|-----|-------|-------|
| `core-concepts.json` | `concepts` | 184 | U-CORE universal concepts |
| `core-relationships.json` | `relationships` | 46 | Typed relationship definitions |
| `core-axes.json` | `axes` | 53 | Ontological dimensions |

Core ontology concepts (typeId ≠ `codex.ucore.user`) **cannot be deleted** via the API
(returns HTTP 403). They can be patched (name, description, keywords, axes).

User-defined concepts (typeId = `codex.ucore.user`) can be fully deleted.

---

## Files Changed / Created

| File | Action | Notes |
|------|--------|-------|
| `api/app/routers/concepts.py` | **exists** | Full CRUD + edges + tagging |
| `api/app/services/concept_service.py` | **exists** | In-memory store, loads from config/ontology |
| `api/app/services/mcp_tool_registry.py` | **extend** | Add 3 concept MCP tools |
| `api/app/main.py` | **verify** | concepts router must be registered |
| `web/app/concepts/page.tsx` | **exists** | Stats + card grid |
| `web/app/concepts/[id]/page.tsx` | **exists** | Detail page with edges + related |
| `cli/lib/commands/concepts.mjs` | **exists** | cc concepts + cc concept <id> + link |
| `config/ontology/core-concepts.json` | **exists** | 184 seed concepts |
| `config/ontology/core-relationships.json` | **exists** | 46 relationship types |
| `config/ontology/core-axes.json` | **exists** | 53 axes |
| `api/tests/test_concepts_crud.py` | **create/verify** | Acceptance test suite |

---

## Verification Scenarios

These scenarios are intended to be run against production (`https://api.coherencycoin.com`).
Set `API=https://api.coherencycoin.com` before running.

---

### Scenario 1 — Ontology loads correctly (seed data check)

**Setup:** Fresh API startup with `config/ontology/` files present.

**Action:**
```bash
curl -s $API/api/concepts/stats
```

**Expected result:**
```json
{"concepts": 184, "relationship_types": 46, "axes": 53, "user_edges": 0, "user_concepts": 0}
```
Exactly 184, 46, 53. Not 0. Not "null".

**Then:**
```bash
curl -s "$API/api/concepts?limit=1" | jq '.total'
```
Expected: `184`

**Edge case:**
```bash
curl -s $API/api/concepts/nonexistent-concept-xyz
```
Expected: HTTP 404 with `{"detail": "Concept 'nonexistent-concept-xyz' not found"}` — not 500.

---

### Scenario 2 — Full create-read-update-delete cycle for a user concept

**Setup:** No concept with id `test-spec-concept-2026` exists.

**Action (Create):**
```bash
curl -s -X POST $API/api/concepts \
  -H "Content-Type: application/json" \
  -d '{"id":"test-spec-concept-2026","name":"Test Spec Concept","description":"Created by spec verification","type_id":"codex.ucore.user","level":0,"keywords":["test","spec"],"axes":["temporal"]}' \
  | jq '{id,name,description}'
```
**Expected:** HTTP 201, `{"id": "test-spec-concept-2026", "name": "Test Spec Concept", "description": "Created by spec verification"}`

**Action (Read):**
```bash
curl -s $API/api/concepts/test-spec-concept-2026 | jq '.name'
```
**Expected:** `"Test Spec Concept"`

**Action (Update):**
```bash
curl -s -X PATCH $API/api/concepts/test-spec-concept-2026 \
  -H "Content-Type: application/json" \
  -d '{"description":"Updated by spec verification"}' \
  | jq '.description'
```
**Expected:** `"Updated by spec verification"`

**Action (Delete):**
```bash
curl -s -X DELETE $API/api/concepts/test-spec-concept-2026 -w "%{http_code}"
```
**Expected:** HTTP 204 (empty body)

**Then:**
```bash
curl -s $API/api/concepts/test-spec-concept-2026 -w "%{http_code}" | tail -1
```
**Expected:** `404`

**Edge case (duplicate create):**
```bash
curl -s -X POST $API/api/concepts \
  -H "Content-Type: application/json" \
  -d '{"id":"consciousness","name":"Duplicate","description":""}' \
  -w "\n%{http_code}" | tail -1
```
**Expected:** `409` (concept already exists, not 201 or 500)

---

### Scenario 3 — Typed edge creation and retrieval

**Setup:** Concepts `consciousness` and `awareness` exist (they are core ontology concepts).

**Action (Create edge):**
```bash
curl -s -X POST $API/api/concepts/consciousness/edges \
  -H "Content-Type: application/json" \
  -d '{"from_id":"consciousness","to_id":"awareness","relationship_type":"resonates-with","created_by":"spec-verifier"}' \
  | jq '{id,from,to,type}'
```
**Expected:** HTTP 201, `{"id": "<uuid>", "from": "consciousness", "to": "awareness", "type": "resonates-with"}`

**Action (Read edges):**
```bash
curl -s $API/api/concepts/consciousness/edges | jq 'map(.type)'
```
**Expected:** array containing `"resonates-with"`

**Edge case (missing target):**
```bash
curl -s -X POST $API/api/concepts/consciousness/edges \
  -H "Content-Type: application/json" \
  -d '{"from_id":"consciousness","to_id":"nonexistent-xyz","relationship_type":"resonates-with","created_by":"test"}' \
  -w "\n%{http_code}" | tail -1
```
**Expected:** `404`

---

### Scenario 4 — Full-text concept search

**Action:**
```bash
curl -s "$API/api/concepts/search?q=consciousness&limit=5" | jq '[.[].id]'
```
**Expected:** Array containing at minimum `"consciousness"`. Results ranked by relevance, not empty.

**Action (search by keyword):**
```bash
curl -s "$API/api/concepts/search?q=awareness" | jq 'length'
```
**Expected:** integer > 0 (awareness appears in keywords or descriptions of multiple concepts)

**Edge case (empty query):**
```bash
curl -s "$API/api/concepts/search?q=" -w "\n%{http_code}" | tail -1
```
**Expected:** `422` (validation error — `q` has `min_length=1`)

---

### Scenario 5 — Concept tagging (ideas ↔ concepts)

**Setup:** An idea exists with a known id (use any idea from `GET /api/ideas?limit=1`).

**Action:**
```bash
IDEA_ID=$(curl -s "$API/api/ideas?limit=1" | jq -r '.items[0].id')
curl -s -X POST $API/api/ideas/$IDEA_ID/concepts \
  -H "Content-Type: application/json" \
  -d '{"concept_ids":["consciousness","creativity"]}' \
  | jq '.tagged'
```
**Expected:** `["consciousness", "creativity"]` (or equivalent tagged list)

**Then (read back):**
```bash
curl -s $API/api/ideas/$IDEA_ID/concepts | jq '.[].id' 2>/dev/null || \
curl -s $API/api/ideas/$IDEA_ID/concepts | jq '.concept_ids'
```
**Expected:** includes `"consciousness"` and `"creativity"`

**Then (navigate from concept):**
```bash
curl -s $API/api/concepts/consciousness/related | jq '.total'
```
**Expected:** integer ≥ 1 (the tagged idea appears)

**Edge case (tag with missing concept):**
```bash
curl -s -X POST $API/api/ideas/$IDEA_ID/concepts \
  -H "Content-Type: application/json" \
  -d '{"concept_ids":["nonexistent-xyz-abc"]}' \
  -w "\n%{http_code}" | tail -1
```
**Expected:** `404` (not 201 or 500)

---

### Scenario 6 — Core concept protection (delete forbidden)

**Action:**
```bash
curl -s -X DELETE $API/api/concepts/consciousness -w "\n%{http_code}" | tail -1
```
**Expected:** `403` — core ontology concepts cannot be deleted.

---

## Proof of Working Over Time

To make it clear that the concept layer is live and healthy in production, the following
monitoring signals should be observable:

| Signal | How to check | Target value |
|--------|-------------|-------------|
| Ontology loaded | `GET /api/concepts/stats` → `concepts` field | 184 |
| No startup errors | API logs at startup | No "Failed to load" warnings |
| Search latency | `GET /api/concepts/search?q=consciousness` p99 | < 100 ms |
| User edge growth | `GET /api/concepts/stats` → `user_edges` | Increases as contributors link concepts |
| Concept page visits | Web analytics (future) | Upward trend after launch |

The `GET /api/concepts/stats` endpoint is the canonical health check for the concept layer.
It should be included in dashboards alongside `/api/health`.

---

## Risks and Assumptions

| Risk | Mitigation |
|------|-----------|
| In-memory store loses user edges on restart | Acceptable for v1; future spec to add Postgres/Neo4j persistence |
| 184 concepts loaded each request may be slow | Concepts indexed in `_concept_index` dict — O(1) lookup |
| Duplicate edges possible (no dedup) | Edges are immutable log entries; duplicates are acceptable in v1 |
| MCP tools not yet in `mcp_tool_registry.py` | Three tools must be added: `coherence_list_concepts`, `coherence_get_concept`, `coherence_link_concepts` |
| Web page uses SSR fetch — revalidate 60s | Concept adds/patches by users are eventually consistent (up to 60s delay) |
| Core concept deletion returns 403 | Intentional — core ontology must not be destroyed by user actions |

---

## Known Gaps and Follow-up Tasks

1. **MCP tools not yet implemented** — `coherence_list_concepts`, `coherence_get_concept`,
   `coherence_link_concepts` handlers and TOOLS entries are missing from
   `api/app/services/mcp_tool_registry.py`. This is the primary implementation gap.

2. **No persistence for user-defined concepts/edges** — stored in-memory; a server restart
   wipes user-created data. Future: persist to PostgreSQL (`concept_user_edges` table).

3. **News tagging not yet wired** — spec calls for news items to be taggable with concepts;
   the `/api/news/{id}/concepts` endpoints do not yet exist.

4. **Task tagging not yet wired** — tasks should also be taggable; `/api/tasks/{id}/concepts`
   endpoints not yet implemented.

5. **Concept graph visualisation** — a force-directed graph of concepts connected by edges
   would make navigation richer; deferred to a future UX spec.

6. **Axis drill-down page** — `/axes` and `/axes/{id}` pages showing which concepts belong
   to each axis are not yet implemented.

---

## Acceptance Criteria

All criteria must pass before the feature is considered complete:

- [ ] `GET /api/concepts/stats` returns `{"concepts": 184, "relationship_types": 46, "axes": 53, ...}` in production
- [ ] `GET /api/concepts/{id}` returns 200 for any core concept id and 404 for unknown ids
- [ ] `POST /api/concepts` creates a user concept and returns 201; duplicate id returns 409
- [ ] `PATCH /api/concepts/{id}` updates name/description/keywords and returns updated concept
- [ ] `DELETE /api/concepts/{id}` returns 204 for user concepts and 403 for core concepts
- [ ] `POST /api/concepts/{id}/edges` creates a typed edge and returns 201
- [ ] `GET /api/concepts/{id}/edges` returns all edges for that concept
- [ ] `GET /api/concepts/search?q=<term>` returns relevant concepts (non-empty for known terms)
- [ ] `POST /api/ideas/{id}/concepts` tags an idea; `GET /api/concepts/{id}/related` reflects the tag
- [ ] `/concepts` web page renders the card grid with stats banner
- [ ] `/concepts/{id}` web page shows full concept detail with edges and related items
- [ ] `cc concepts` CLI command lists concepts with stats footer
- [ ] `cc concept <id>` CLI command shows concept detail
- [ ] `cc concept link <from> <rel> <to>` creates an edge
- [ ] MCP tools `coherence_list_concepts`, `coherence_get_concept`, `coherence_link_concepts` are registered and callable
