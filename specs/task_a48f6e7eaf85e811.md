# Spec: Concept Layer — CRUD for 184 Universal Concepts with Typed Relationships

**Spec ID**: task_a48f6e7eaf85e811
**Status**: draft
**Author**: agent (product-manager)
**Created**: 2026-03-28
**Priority**: high

---

## Summary

Port the Living Codex U-Core ontology (184 concepts, 46 relationship types, 53 axes) into Coherence Network as a first-class navigable resource. The concept layer provides the semantic backbone of the platform: every idea, spec, task, and news item can be tagged with concepts, and concepts are browsable through a rich UI and CLI surface.

The foundational data (seeded from `config/ontology/core-concepts.json`, `core-relationships.json`, `core-axes.json`) already loads in-memory via `concept_service.py`. This spec formalises the **full CRUD surface**, the **tagging integration** with ideas/specs/news, the **web UI**, the **CLI commands**, and the **MCP tools** required to make concepts first-class.

---

## Goals

1. **Complete API surface**: POST/GET/PATCH/DELETE on concepts; POST/GET/DELETE on concept edges.
2. **Tagging integration**: ideas, specs, and news items gain a `concept_ids` field; concepts expose a reverse index of all tagged entities.
3. **Navigable web UI**: `/concepts` card grid + `/concepts/[id]` drill-down page showing edges, related ideas, news, and contributors.
4. **CLI commands**: `cc concepts`, `cc concept <id>`, `cc concept link <from> <rel> <to>`.
5. **MCP tools**: `coherence_list_concepts`, `coherence_get_concept`, `coherence_link_concepts`.
6. **Observability**: stats endpoint, search, and pagination already exist; extend with concept usage counts.

---

## Current State

The following already exists and must NOT be broken:

| Component | Status |
|-----------|--------|
| `api/app/routers/concepts.py` | GET routes only; POST edge creation |
| `api/app/services/concept_service.py` | In-memory loader from ontology JSON; search, stats |
| `config/ontology/core-concepts.json` | 184 concepts seeded |
| `config/ontology/core-relationships.json` | 46 relationship types |
| `config/ontology/core-axes.json` | 53 axes |
| `web/components/beliefs/ConceptTagCloud.tsx` | Displays concept resonances (belief page) |
| `GET /api/concepts` | Paginated concept list |
| `GET /api/concepts/search?q=` | Text search |
| `GET /api/concepts/stats` | Count stats |
| `GET /api/concepts/{id}` | Single concept fetch |
| `GET /api/concepts/{id}/edges` | Edges for a concept |
| `POST /api/concepts/{id}/edges` | Create user-defined edge |

---

## What Is Missing (Must Be Implemented)

### 1. API — Additional Endpoints

#### 1a. Custom concept creation
```
POST /api/concepts
```
Allows contributors to add new concepts beyond the seeded 184. Body:
```json
{
  "id": "string (slug, required, unique)",
  "name": "string (required)",
  "description": "string",
  "typeId": "string (default: codex.custom)",
  "level": "integer (default: 1)",
  "keywords": ["string"],
  "axes": ["string (axis IDs)"],
  "created_by": "string"
}
```
Returns 201 on success, 409 on duplicate `id`.

#### 1b. Concept update
```
PATCH /api/concepts/{concept_id}
```
Partial update of mutable fields: `name`, `description`, `keywords`, `axes`. The seeded 184 concepts from the Living Codex are considered canonical; update is allowed but a `source: "canonical"` flag is preserved. Returns 200 with updated concept, 404 if not found.

#### 1c. Concept deletion
```
DELETE /api/concepts/{concept_id}
```
Hard-deletes custom concepts (those with `source != "canonical"`). Canonical concepts return 403 ("Cannot delete canonical concept"). Returns 204 on success, 404 if not found.

#### 1d. Edge deletion
```
DELETE /api/concepts/{concept_id}/edges/{edge_id}
```
Deletes a user-created edge. Returns 204 on success, 404 if edge not found.

#### 1e. Concept tagging — tagged entities
```
GET /api/concepts/{concept_id}/tagged
```
Returns all entities tagged with this concept across all entity types (ideas, specs, news). Response:
```json
{
  "concept_id": "string",
  "tagged": {
    "ideas": [{"id": "...", "title": "...", "created_at": "..."}],
    "specs": [{"id": "...", "title": "..."}],
    "news": [{"id": "...", "headline": "..."}]
  },
  "total": 42
}
```

### 2. Idea Tagging Integration

Add `concept_ids: list[str]` to `IdeaCreate` and `IdeaUpdate` models (alongside existing `tags`). `concept_ids` are validated against the concept index at write time — unknown IDs are rejected with 422.

`GET /api/ideas/{id}` response must include `concept_ids` if any are set.

`GET /api/ideas?concept_id=resonance` filters ideas by concept tag.

### 3. Web UI

#### 3a. `/concepts` page
- Card grid of all 184+ concepts, each card showing: name, description excerpt, axis badges, edge count.
- Search bar wired to `/api/concepts/search?q=`.
- Filter by axis (dropdown).
- Cards link to `/concepts/[id]`.

#### 3b. `/concepts/[id]` drill-down page
- Header: concept name, description, `typeId`, level.
- **Edges panel**: visualises typed relationships to other concepts (from/to, relationship type).
- **Tagged entities panel**: ideas, specs, news tagged with this concept (via `GET /api/concepts/{id}/tagged`).
- **Contributors panel**: contributors whose belief profiles include this concept (from concept resonance scores).
- Breadcrumb back to `/concepts`.

### 4. CLI Commands

#### 4a. `cc concepts`
Lists all concepts with pagination. Output columns: id, name, axis count, edge count.

#### 4b. `cc concept <id>`
Fetches and pretty-prints a single concept including its edges.

#### 4c. `cc concept link <from_id> <rel_type> <to_id>`
Creates an edge between two concepts. Validates both concepts exist before posting.

Implementation file: `cli/lib/commands/concepts.mjs`

Must be registered in `cli/lib/commands/index.mjs` (or equivalent router).

### 5. MCP Tools

Register three new MCP tools in `api/app/services/mcp_tool_registry.py` and expose via `api/mcp_server.py`:

#### `coherence_list_concepts`
- **Description**: "List concepts from the Living Codex ontology"
- **Params**: `limit` (int, default 50), `offset` (int, default 0), `query` (string, optional)
- **Returns**: paginated concept list

#### `coherence_get_concept`
- **Description**: "Get a concept by ID with its edges and tagged entities"
- **Params**: `concept_id` (string, required)
- **Returns**: concept object + edges + tagged counts

#### `coherence_link_concepts`
- **Description**: "Create a typed edge between two concepts"
- **Params**: `from_id` (string), `to_id` (string), `relationship_type` (string), `created_by` (string)
- **Returns**: created edge object

---

## Data Model

### Concept (canonical / custom)

```json
{
  "id": "resonance",
  "name": "Resonance",
  "description": "Harmonic alignment between systems or entities",
  "typeId": "codex.ucore.base",
  "level": 0,
  "keywords": ["resonance", "harmony", "alignment", "frequency"],
  "parentConcepts": ["vibration"],
  "childConcepts": ["coherence", "entanglement"],
  "axes": ["energetic", "temporal"],
  "source": "canonical",
  "created_by": null,
  "created_at": "2025-09-22T00:00:00Z",
  "edge_count": 0,
  "usage_count": 0
}
```

### Edge

```json
{
  "id": "e-a1b2c3",
  "from": "resonance",
  "to": "coherence",
  "type": "resonates-with",
  "created_by": "contributor-xyz",
  "created_at": "2026-03-28T10:00:00Z"
}
```

### Relationship type

```json
{
  "id": "resonates-with",
  "name": "Resonates With",
  "description": "Harmonic resonance relationship indicating vibrational alignment",
  "bidirectional": true,
  "symmetric": true,
  "weight": 0.9
}
```

### Axis

```json
{
  "id": "water_states",
  "name": "12 States of Water",
  "description": "The twelve fundamental states of water representing different phases of matter and consciousness",
  "dimensions": ["ice", "liquid", "vapor", ...],
  "epistemicLabel": "physics"
}
```

---

## Files Affected

| File | Change |
|------|--------|
| `api/app/routers/concepts.py` | Add POST /concepts, PATCH /concepts/{id}, DELETE /concepts/{id}, DELETE /concepts/{id}/edges/{edge_id}, GET /concepts/{id}/tagged |
| `api/app/services/concept_service.py` | Add create_concept, update_concept, delete_concept, delete_edge, get_tagged_entities, get_concept_usage |
| `api/app/models/idea.py` | Add `concept_ids: list[str]` to IdeaCreate, IdeaUpdate, IdeaResponse |
| `api/app/routers/ideas.py` | Filter by concept_id query param; validate concept_ids at write |
| `api/app/services/mcp_tool_registry.py` | Register 3 MCP concept tools |
| `api/mcp_server.py` | Expose MCP concept tools |
| `web/app/concepts/page.tsx` | New page: concept card grid |
| `web/app/concepts/[id]/page.tsx` | New page: concept drill-down |
| `cli/lib/commands/concepts.mjs` | New CLI command module |
| `cli/lib/commands/` (router) | Register concepts command |
| `api/tests/test_concepts.py` | Unit + integration tests |

---

## API Contract

### Endpoints — full list

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/api/concepts` | List all concepts (paginated) | none |
| POST | `/api/concepts` | Create custom concept | API key |
| GET | `/api/concepts/search?q=` | Search concepts by name/desc | none |
| GET | `/api/concepts/stats` | Ontology statistics | none |
| GET | `/api/concepts/relationships` | List 46 relationship types | none |
| GET | `/api/concepts/axes` | List 53 axes | none |
| GET | `/api/concepts/{id}` | Get single concept | none |
| PATCH | `/api/concepts/{id}` | Update concept fields | API key |
| DELETE | `/api/concepts/{id}` | Delete custom concept | API key |
| GET | `/api/concepts/{id}/edges` | Get edges for concept | none |
| POST | `/api/concepts/{id}/edges` | Create typed edge | none |
| DELETE | `/api/concepts/{id}/edges/{edge_id}` | Delete edge | API key |
| GET | `/api/concepts/{id}/tagged` | Entities tagged with concept | none |

---

## Observability / Proof It's Working

The spec must leave a visible trace that proves functionality:

1. **Stats endpoint**: `GET /api/concepts/stats` must return `{"concepts": 184, "relationship_types": 46, "axes": 53, ...}`.
2. **Usage count**: ideas tagged with a concept increment `usage_count` on the concept object.
3. **Search response time**: `GET /api/concepts/search?q=resonance` must respond in < 200ms (in-memory).
4. **Web page**: `/concepts` renders all 184 cards with axis badges visible.
5. **MCP audit**: Every MCP call logged in audit ledger with tool name and concept_id.

---

## Verification Scenarios

The reviewer will run each of these scenarios against the live API at `https://api.coherencycoin.com`.

---

### Scenario 1: Full CRUD lifecycle for a custom concept

**Setup**: No concept with id `test-synthesis-001` exists.

**Action**:
```bash
API=https://api.coherencycoin.com

# Create
curl -s -X POST $API/api/concepts \
  -H "Content-Type: application/json" \
  -d '{"id":"test-synthesis-001","name":"Test Synthesis","description":"A temporary test concept","created_by":"spec-reviewer"}' | jq .

# Read
curl -s $API/api/concepts/test-synthesis-001 | jq .id,.name

# Update
curl -s -X PATCH $API/api/concepts/test-synthesis-001 \
  -H "Content-Type: application/json" \
  -d '{"description":"Updated description for test"}' | jq .description

# Delete
curl -s -X DELETE $API/api/concepts/test-synthesis-001 -o /dev/null -w "%{http_code}"
# Expect: 204
curl -s $API/api/concepts/test-synthesis-001 -o /dev/null -w "%{http_code}"
# Expect: 404
```

**Expected results**:
- POST returns HTTP 201, body contains `{"id":"test-synthesis-001","name":"Test Synthesis",...}`
- GET returns same concept with `source: "custom"`
- PATCH returns 200 with `"description": "Updated description for test"`
- DELETE returns 204
- Second GET returns 404

**Edge cases**:
- POST same id again returns 409 (not 500, not 201)
- GET `/api/concepts/does-not-exist-xyz` returns 404
- PATCH `/api/concepts/does-not-exist-xyz` returns 404

---

### Scenario 2: Canonical concept protection

**Setup**: Concept `resonance` is a canonical seeded concept.

**Action**:
```bash
API=https://api.coherencycoin.com

# Attempt to delete canonical
curl -s -X DELETE $API/api/concepts/resonance -o /dev/null -w "%{http_code}"
# Expect: 403

# Verify still exists
curl -s $API/api/concepts/resonance | jq .name,.source
# Expect: "Resonance", "canonical"

# Update is allowed on canonical (but source stays canonical)
curl -s -X PATCH $API/api/concepts/resonance \
  -H "Content-Type: application/json" \
  -d '{"keywords":["resonance","harmony","frequency","alignment","updated"]}' \
  | jq .source
# Expect: "canonical" (preserved)
```

**Expected results**:
- DELETE canonical returns 403
- Concept remains intact
- PATCH is allowed; `source` field remains `"canonical"`

---

### Scenario 3: Stats endpoint proves ontology is seeded

**Setup**: Fresh API start after standard deployment.

**Action**:
```bash
curl -s https://api.coherencycoin.com/api/concepts/stats | jq .
```

**Expected result**:
```json
{
  "concepts": 184,
  "relationship_types": 46,
  "axes": 53,
  "user_edges": 0
}
```
(user_edges may be > 0 if prior tests ran; concepts/relationship_types/axes must equal exactly 184/46/53)

**Edge case**: If ontology files are missing, the endpoint returns `{"concepts": 0, "relationship_types": 0, "axes": 0}` rather than a 500.

---

### Scenario 4: Edge creation and retrieval

**Setup**: Concepts `coherence` and `resonance` both exist (canonical).

**Action**:
```bash
API=https://api.coherencycoin.com

# Create edge
EDGE=$(curl -s -X POST $API/api/concepts/coherence/edges \
  -H "Content-Type: application/json" \
  -d '{"from_id":"coherence","to_id":"resonance","relationship_type":"resonates-with","created_by":"spec-reviewer"}')
echo $EDGE | jq .id,.type

EDGE_ID=$(echo $EDGE | jq -r .id)

# Retrieve edges
curl -s $API/api/concepts/coherence/edges | jq 'length'
# Expect: >= 1

# Delete edge
curl -s -X DELETE $API/api/concepts/coherence/edges/$EDGE_ID -o /dev/null -w "%{http_code}"
# Expect: 204

# Verify gone
curl -s $API/api/concepts/coherence/edges | jq "[.[] | select(.id == \"$EDGE_ID\")] | length"
# Expect: 0
```

**Edge cases**:
- POST edge with nonexistent `to_id` returns 404
- POST edge with invalid `relationship_type` returns 422 if type validation is enforced (or 201 if permissive — spec author prefers validation)
- DELETE nonexistent edge returns 404

---

### Scenario 5: Search and filtering

**Setup**: Ontology seeded with 184 concepts.

**Action**:
```bash
API=https://api.coherencycoin.com

# Search by keyword
curl -s "$API/api/concepts/search?q=resonance" | jq 'length'
# Expect: >= 1 (at least concept named "Resonance")

curl -s "$API/api/concepts/search?q=resonance" | jq '.[0].name'
# Expect contains "Resonance"

# Search with no match
curl -s "$API/api/concepts/search?q=xyzzy_does_not_exist_8472" | jq 'length'
# Expect: 0 (not 404, not error)

# Pagination
curl -s "$API/api/concepts?limit=10&offset=0" | jq '.total,.items | length'
# Expect: total=184 (or more if custom added), items length=10

curl -s "$API/api/concepts?limit=10&offset=180" | jq '.items | length'
# Expect: 4 (184 - 180)
```

**Edge cases**:
- `GET /api/concepts?limit=0` returns 422 (limit must be >= 1)
- `GET /api/concepts?limit=501` returns 422 (limit max 500)
- `GET /api/concepts/search` without `q` returns 422

---

## Risks and Assumptions

| Risk | Mitigation |
|------|------------|
| In-memory store lost on restart | Acceptable for user-created edges in v1; v2 will persist to PostgreSQL |
| Canonical concept IDs collide with user-created IDs | POST /concepts validates against full concept index; returns 409 on collision |
| Tagging ideas with nonexistent concept_ids | concept_ids validated at write time; 422 returned for unknown IDs |
| MCP tool surface increases attack surface | MCP calls logged in audit ledger; read tools are unauthenticated, write tools require creator attribution |
| Web UI concept count grows beyond 184 | Card grid is paginated/searchable; no unbounded render |
| Concept deletion breaks idea tags | Soft-delete or rejection: v1 rejects deletion of concepts with usage_count > 0 unless `force=true` |

---

## Known Gaps and Follow-up Tasks

1. **Persistence**: User-created concepts and edges are in-memory only. A follow-up spec should add PostgreSQL persistence for concepts and edges tables.
2. **Concept graph visualisation**: The `/concepts/[id]` page could render a D3 force graph of connected concepts — deferred to a dedicated viz spec.
3. **Bulk tagging**: Batch endpoint `POST /api/concepts/{id}/tag-entities` to tag multiple ideas/specs at once — deferred.
4. **Concept merge**: Two concepts pointing to the same real-world notion should be mergeable — complex operation, deferred.
5. **Contributor concept attribution**: Track which contributor proposed/created each concept — needs contributor auth integration.
6. **CLI autocomplete**: `cc concept link` should autocomplete concept IDs from the local cache — deferred to CLI enhancement spec.

---

## Implementation Order

1. **API**: `concept_service.py` — add create/update/delete/tagged methods
2. **API**: `concepts.py` router — add missing endpoints
3. **Models**: `idea.py` — add `concept_ids` field; wire into `ideas.py` router
4. **MCP**: register 3 tools
5. **CLI**: `concepts.mjs` + router registration
6. **Web**: `/concepts` page + `/concepts/[id]` page
7. **Tests**: `api/tests/test_concepts.py`

---

## Acceptance Criteria

- [ ] `GET /api/concepts/stats` returns `{"concepts": 184, "relationship_types": 46, "axes": 53, ...}`
- [ ] `POST /api/concepts` creates a custom concept and returns 201
- [ ] `POST /api/concepts` with duplicate id returns 409
- [ ] `PATCH /api/concepts/{id}` updates mutable fields, returns 200
- [ ] `DELETE /api/concepts/{custom_id}` returns 204
- [ ] `DELETE /api/concepts/{canonical_id}` returns 403
- [ ] `GET /api/concepts/{nonexistent}` returns 404
- [ ] `POST /api/concepts/{id}/edges` creates a typed edge, returns 201
- [ ] `DELETE /api/concepts/{id}/edges/{edge_id}` returns 204
- [ ] `GET /api/concepts/{id}/tagged` returns structured tagged-entity list
- [ ] `IdeaCreate.concept_ids` field exists; unknown IDs return 422
- [ ] `GET /api/ideas?concept_id=resonance` filters ideas by concept tag
- [ ] MCP tools `coherence_list_concepts`, `coherence_get_concept`, `coherence_link_concepts` are registered
- [ ] `cc concepts` CLI command lists concepts
- [ ] `cc concept <id>` CLI command displays a single concept
- [ ] `cc concept link <from> <rel> <to>` creates an edge
- [ ] `/concepts` web page renders concept card grid
- [ ] `/concepts/[id]` web page renders concept details, edges, and tagged entities
- [ ] All 5 Verification Scenarios above pass against production
