# Spec: Concept Layer — CRUD for 184 Universal Concepts with Typed Relationships

**Spec ID**: 182-concept-layer-crud
**Status**: Active
**Author**: product-manager agent
**Date**: 2026-03-28
**Priority**: High
**Idea Source**: Living Codex ontology port (184 concepts, 46 relationship types, 53 axes)

---

## Summary

Port the Living Codex ontology into Coherence Network as a **first-class resource**. The ontology
defines 184 universal concepts (e.g., `trust`, `resonance`, `coherence`, `breath`, `water`,
`identity`), 46 typed relationship edges between concepts, and 53 measurement axes.

Once loaded, **every idea, spec, task, and news item can be tagged with one or more concepts**.
Concepts become navigable: click any concept to see which ideas, news items, and contributors
relate to it — creating a semantic map of Coherence Network activity rooted in universal meaning.

### What Done Looks Like

- `concepts` table in PostgreSQL with 184 seeded rows from `config/ontology/core-concepts.json`.
- `concept_edges` table seeded from `config/ontology/core-relationships.json`.
- `concept_axes` table with 53 axes from `config/ontology/core-axes.json`.
- `idea_concepts` join table linking ideas to concepts.
- Full REST API: `POST/GET/PATCH/DELETE /api/concepts`, `GET /api/concepts/{id}/edges`,
  `GET /api/concepts/search?q=`.
- Web page at `/concepts` with card grid; click-through to `/concepts/{id}` showing edges +
  related ideas.
- CLI commands: `cc concepts`, `cc concept <id>`, `cc concept link <from> <rel> <to>`.
- MCP tools: `coherence_list_concepts`, `coherence_get_concept`, `coherence_link_concepts`.
- Seed runs via Alembic data migration; idempotent on re-run.

### Why This Matters

Without semantic concept tagging, ideas are text blobs — unsortable by meaning, unconnected to
prior art across the Living Codex. Concepts turn the pipeline into a knowledge graph: "all ideas
related to `trust`" becomes a query, not a manual search.

The Living Codex origin project carries deep ontology work. Porting it prevents duplication and
links Coherence Network to its intellectual foundation.

---

## Problem Statement

Current state:

- Ideas, specs, and tasks are stored with free-text tags and titles. No semantic vocabulary.
- The Living Codex project has 184 carefully curated universal concepts with typed relationships
  but this ontology lives in another codebase and is not queryable from Coherence Network.
- Contributors cannot navigate "what ideas relate to resonance?" across the system.
- There is no MCP surface for concept discovery by AI agents.

Desired state:

- Concepts are a first-class API resource with CRUD, search, and relationship traversal.
- Every idea can be tagged with one or more concepts.
- The web UI offers a concept card grid + drill-down per concept.
- CLI and MCP surfaces support agent-driven concept linking.
- The ontology seeds on first deploy; custom concepts can be added by operators.

---

## Requirements

### R1 — Database Schema

**`concepts` table**:

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | `VARCHAR(128)` | PK (slug, e.g. `trust`, `resonance`) |
| `name` | `VARCHAR(256)` | NOT NULL |
| `description` | `TEXT` | nullable |
| `category` | `VARCHAR(64)` | nullable (e.g. `social`, `physical`, `metaphysical`) |
| `source` | `VARCHAR(64)` | default `living-codex`; `custom` for operator-created |
| `axis_ids` | `TEXT[]` | array of axis slugs referencing `concept_axes.id` |
| `metadata` | `JSONB` | default `{}` |
| `created_at` | `TIMESTAMPTZ` | NOT NULL DEFAULT NOW() |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL DEFAULT NOW() |

**`concept_edges` table** (typed relationships between concepts):

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | `UUID` | PK, generated |
| `from_concept_id` | `VARCHAR(128)` | FK to `concepts.id` ON DELETE CASCADE |
| `to_concept_id` | `VARCHAR(128)` | FK to `concepts.id` ON DELETE CASCADE |
| `relationship_type` | `VARCHAR(64)` | NOT NULL (e.g. `requires`, `amplifies`, `opposes`) |
| `weight` | `FLOAT` | default 1.0 |
| `metadata` | `JSONB` | default `{}` |
| `created_at` | `TIMESTAMPTZ` | NOT NULL DEFAULT NOW() |

Unique constraint: `(from_concept_id, to_concept_id, relationship_type)` — no duplicate edges of same type.

**`concept_axes` table** (measurement/navigation axes):

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | `VARCHAR(128)` | PK (slug) |
| `name` | `VARCHAR(256)` | NOT NULL |
| `description` | `TEXT` | nullable |
| `polarity_low` | `VARCHAR(128)` | label for low end (e.g. `chaos`) |
| `polarity_high` | `VARCHAR(128)` | label for high end (e.g. `order`) |
| `created_at` | `TIMESTAMPTZ` | NOT NULL DEFAULT NOW() |

**`idea_concepts` join table** (ideas tagged with concepts):

| Column | Type | Constraints |
|--------|------|-------------|
| `idea_id` | `VARCHAR(128)` | FK to `ideas.id` ON DELETE CASCADE |
| `concept_id` | `VARCHAR(128)` | FK to `concepts.id` ON DELETE CASCADE |
| `tagged_at` | `TIMESTAMPTZ` | NOT NULL DEFAULT NOW() |
| `tagged_by` | `VARCHAR(128)` | nullable (agent/user who tagged) |

PK: `(idea_id, concept_id)` — idempotent tagging.

### R2 — Seed Data (Ontology Config Files)

Three JSON config files committed to the repo, seeded via Alembic data migration.

**`config/ontology/core-concepts.json`** — array of 184 objects:

```json
[
  {
    "id": "trust",
    "name": "Trust",
    "description": "The foundation of cooperative relationships and shared vulnerability.",
    "category": "social",
    "axis_ids": ["certainty-uncertainty", "open-closed"]
  },
  {
    "id": "resonance",
    "name": "Resonance",
    "description": "The harmonic alignment between entities, systems, or ideas.",
    "category": "energetic",
    "axis_ids": ["resonance-dissonance"]
  }
]
```

**`config/ontology/core-relationships.json`** — array of edge definitions:

```json
[
  { "from": "trust", "to": "resonance", "type": "amplifies", "weight": 0.8 },
  { "from": "coherence", "to": "resonance", "type": "requires", "weight": 1.0 },
  { "from": "resonance", "to": "coherence", "type": "generates", "weight": 0.7 }
]
```

**`config/ontology/core-axes.json`** — array of 53 axis objects:

```json
[
  {
    "id": "certainty-uncertainty",
    "name": "Certainty-Uncertainty",
    "description": "Spectrum from complete uncertainty to absolute certainty.",
    "polarity_low": "uncertainty",
    "polarity_high": "certainty"
  },
  {
    "id": "resonance-dissonance",
    "name": "Resonance-Dissonance",
    "description": "Spectrum from harmonic alignment to conflicting dissonance.",
    "polarity_low": "dissonance",
    "polarity_high": "resonance"
  }
]
```

Seed migration uses `INSERT ... ON CONFLICT DO NOTHING` — fully idempotent.

### R3 — API Endpoints

All endpoints under `/api/concepts`. Pydantic response models required for all.

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `GET` | `/api/concepts` | List all concepts (paginated, 50/page default) | None |
| `GET` | `/api/concepts/{id}` | Get single concept by slug ID with edges | None |
| `POST` | `/api/concepts` | Create a new custom concept | API key |
| `PATCH` | `/api/concepts/{id}` | Update a concept (description, metadata) | API key |
| `DELETE` | `/api/concepts/{id}` | Delete a concept (custom only; 403 for seeded) | API key |
| `GET` | `/api/concepts/{id}/edges` | Get all typed edges for this concept (in + out) | None |
| `POST` | `/api/concepts/{id}/edges` | Create a typed edge from this concept to another | API key |
| `DELETE` | `/api/concepts/{id}/edges/{edge_id}` | Delete an edge | API key |
| `GET` | `/api/concepts/search` | Full-text search on name + description (`?q=`) | None |
| `GET` | `/api/concepts/{id}/ideas` | List ideas tagged with this concept | None |
| `POST` | `/api/ideas/{id}/concepts` | Tag an idea with a concept | API key |
| `DELETE` | `/api/ideas/{id}/concepts/{concept_id}` | Remove concept tag from idea | API key |
| `GET` | `/api/concepts/axes` | List all 53 axes | None |

**Query params for `GET /api/concepts`**:

- `?category=social` — filter by category
- `?axis=certainty-uncertainty` — filter by axis
- `?q=trust` — inline text search
- `?page=1&per_page=50`
- `?source=living-codex` or `?source=custom`

**Pydantic response models** (`api/app/models/concepts.py`):

```python
class ConceptOut(BaseModel):
    id: str
    name: str
    description: Optional[str]
    category: Optional[str]
    source: str
    axis_ids: list[str]
    metadata: dict
    created_at: datetime
    updated_at: datetime

class ConceptEdgeOut(BaseModel):
    id: str
    from_concept_id: str
    to_concept_id: str
    relationship_type: str
    weight: float
    metadata: dict
    created_at: datetime

class ConceptAxisOut(BaseModel):
    id: str
    name: str
    description: Optional[str]
    polarity_low: Optional[str]
    polarity_high: Optional[str]

class ConceptWithEdgesOut(ConceptOut):
    outgoing_edges: list[ConceptEdgeOut]
    incoming_edges: list[ConceptEdgeOut]
    idea_count: int

class ConceptListOut(BaseModel):
    concepts: list[ConceptOut]
    total: int
    page: int
    per_page: int
```

**Error responses**:

- `404` concept not found: `{"detail": "Concept not found: {id}"}`
- `409` duplicate concept: `{"detail": "Concept already exists: {id}"}`
- `403` delete seeded: `{"detail": "Cannot delete seeded concept: {id}. source must be custom."}`
- `422` validation errors (Pydantic auto-handles)

### R4 — Web Pages

**`/concepts` page** (`web/app/concepts/page.tsx`):

- Card grid layout (3 columns desktop, 2 tablet, 1 mobile) via shadcn/ui `Card`.
- Each card: concept name, category badge, description (truncated 2 lines), edge count badge.
- Filter sidebar: by category, by axis.
- Search bar at top (calls `/api/concepts/search?q=`).
- Pagination (50/page default).

**`/concepts/[id]` page** (`web/app/concepts/[id]/page.tsx`):

- Concept name + description header.
- Axes badges.
- Two panels: **Outgoing edges** and **Incoming edges** (relationship type label + target chip).
- **Related Ideas** section: `IdeaCard` list for ideas tagged with this concept.
- **Copy concept ID** button for CLI/MCP usage.

### R5 — CLI Commands

```
cc concepts                         List all concepts (table: ID, Name, Category, Edges)
cc concept <id>                     Show full detail for a concept
cc concept link <from> <rel> <to>   Create typed edge: cc concept link trust amplifies resonance
cc concept tag <idea_id> <concept>  Tag an idea with a concept
cc concept search <query>           Search concepts by name/description
```

Options: `--json` returns raw JSON; default is rich table output.

### R6 — MCP Tools

Registered in `mcp-server/server.json`:

| Tool name | Description |
|-----------|-------------|
| `coherence_list_concepts` | Paginated concept list; params: `category`, `axis`, `q`, `page` |
| `coherence_get_concept` | Full concept detail + edges; param: `id` |
| `coherence_link_concepts` | Create typed edge; params: `from_id`, `to_id`, `relationship_type`, `weight` |
| `coherence_tag_idea` | Tag idea with concept; params: `idea_id`, `concept_id` |
| `coherence_search_concepts` | Text search; param: `q` |

### R7 — Concept Tagging on Existing Resources

- `GET /api/ideas/{id}` response includes `concepts: list[ConceptOut]` field (backward-compatible).
- `POST /api/ideas` and `PATCH /api/ideas/{id}` optionally accept `concept_ids: list[str]`
  to auto-tag on create/update.

### R8 — Seed Script and Startup

- Alembic schema migration creates all four tables.
- Separate Alembic data migration reads JSON files and seeds with `ON CONFLICT DO NOTHING`.
- Both run via `alembic upgrade head` — no manual seed command needed.
- JSON files committed at `config/ontology/core-concepts.json`,
  `config/ontology/core-relationships.json`, `config/ontology/core-axes.json`.

---

## Files to Create or Modify

| File | Action | Description |
|------|--------|-------------|
| `config/ontology/core-concepts.json` | Create | 184 concept definitions from Living Codex |
| `config/ontology/core-relationships.json` | Create | 46 relationship edge definitions |
| `config/ontology/core-axes.json` | Create | 53 axis definitions |
| `api/alembic/versions/xxxx_add_concept_layer.py` | Create | Schema migration (4 tables) |
| `api/alembic/versions/xxxx_seed_concept_ontology.py` | Create | Data migration (seed from JSON) |
| `api/app/models/concepts.py` | Create | Pydantic models + SQLAlchemy ORM models |
| `api/app/services/concept_service.py` | Create | Business logic: CRUD, search, tagging |
| `api/app/routers/concepts.py` | Create | FastAPI router for all concept endpoints |
| `api/app/main.py` | Modify | Register concepts router |
| `api/tests/test_concept_layer.py` | Create | Pytest tests (>=20 test cases) |
| `web/app/concepts/page.tsx` | Create | Concept card grid page |
| `web/app/concepts/[id]/page.tsx` | Create | Concept detail + edges page |
| `mcp-server/server.json` | Modify | Add 5 concept MCP tools |
| `cli/commands/concept.py` (or equivalent) | Create | CLI commands for concepts |

---

## Data Model — Relationship Types (Living Codex, 46 total — sample)

| Type | Meaning |
|------|---------|
| `requires` | A cannot exist without B |
| `amplifies` | A strengthens B |
| `opposes` | A and B are in tension |
| `generates` | A produces B over time |
| `contains` | A is a superset of B |
| `is_a` | A is a subtype of B |
| `enables` | A makes B possible |
| `constrains` | A limits B |
| `measures` | A quantifies B |
| `resonates_with` | A and B vibrate in harmony |
| `disrupts` | A breaks B pattern |
| `precedes` | A comes before B in sequence |
| `embodies` | A is an instance of B |
| `transforms_into` | A transitions to B |

---

## Axes — Sample (53 total)

| ID | Name | Low | High |
|----|------|-----|------|
| `certainty-uncertainty` | Certainty-Uncertainty | uncertainty | certainty |
| `open-closed` | Open-Closed | closed | open |
| `inner-outer` | Inner-Outer | inner | outer |
| `form-formless` | Form-Formless | formless | form |
| `fast-slow` | Fast-Slow | slow | fast |
| `trust-fear` | Trust-Fear | fear | trust |
| `order-chaos` | Order-Chaos | chaos | order |
| `resonance-dissonance` | Resonance-Dissonance | dissonance | resonance |

---

## Verification Scenarios

### Scenario 1 — Seed Load and List (full create-read cycle)

**Setup**: Fresh database. Run `alembic upgrade head`.

**Action**:

```bash
curl -s https://api.coherencycoin.com/api/concepts \
  | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['total'] == 184, f'Expected 184, got {d[\"total\"]}'
assert len(d['concepts']) == 50
print('OK - total:', d['total'])
"
```

**Expected output**: `OK - total: 184`

**Edge case (duplicate seed)**: Run `alembic upgrade head` again — migration is idempotent.

```bash
curl -s https://api.coherencycoin.com/api/concepts \
  | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['total'] == 184
print('Idempotent: OK')
"
```

Expected: `Idempotent: OK` — no duplicate rows inserted.

**Edge case (missing concept)**:

```bash
curl -s -o /dev/null -w "%{http_code}" https://api.coherencycoin.com/api/concepts/notaconcept
```

Expected: `404` (not 500).

---

### Scenario 2 — Get Single Concept With Edges

**Setup**: Concepts seeded. `trust` has outgoing `amplifies` edge to `resonance`.

**Action**:

```bash
curl -s https://api.coherencycoin.com/api/concepts/trust \
  | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['id'] == 'trust'
assert d['name'] == 'Trust'
assert isinstance(d['outgoing_edges'], list)
matches = [e for e in d['outgoing_edges']
           if e['to_concept_id'] == 'resonance' and e['relationship_type'] == 'amplifies']
assert len(matches) == 1, 'trust->resonance amplifies edge missing'
print('OK - outgoing edges:', len(d['outgoing_edges']))
"
```

**Expected output**: `OK - outgoing edges: 3` (exact count depends on seeded data).

**Edge case (nonexistent concept)**:

```bash
curl -s -o /dev/null -w "%{http_code}" https://api.coherencycoin.com/api/concepts/notaconcept
```

Expected: `404`

---

### Scenario 3 — Create Custom Concept, Update, Delete

**Setup**: `my-org-concept` does not exist.

**Create**:

```bash
curl -s -X POST https://api.coherencycoin.com/api/concepts \
  -H "Content-Type: application/json" -H "X-API-Key: $API_KEY" \
  -d '{"id":"my-org-concept","name":"My Org Concept","description":"Test","category":"custom"}' \
  | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['id'] == 'my-org-concept'
assert d['source'] == 'custom'
print('Created OK')
"
```

**Update**:

```bash
curl -s -X PATCH https://api.coherencycoin.com/api/concepts/my-org-concept \
  -H "Content-Type: application/json" -H "X-API-Key: $API_KEY" \
  -d '{"description":"Updated description"}' \
  | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert 'Updated' in d['description']
print('Updated OK')
"
```

**Delete**:

```bash
curl -s -X DELETE https://api.coherencycoin.com/api/concepts/my-org-concept \
  -H "X-API-Key: $API_KEY" \
  | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d.get('deleted') == True
print('Deleted OK')
"
```

**Verify gone**:

```bash
curl -s -o /dev/null -w "%{http_code}" https://api.coherencycoin.com/api/concepts/my-org-concept
```

Expected: `404`

**Edge case — Duplicate create returns 409**:

```bash
# POST same id twice: second call returns 409
curl -s -o /dev/null -w "%{http_code}" \
  -X POST https://api.coherencycoin.com/api/concepts \
  -H "Content-Type: application/json" -H "X-API-Key: $API_KEY" \
  -d '{"id":"my-org-concept","name":"My Org Concept"}'
# 201 on first call, 409 on second
```

**Edge case — Delete seeded concept returns 403**:

```bash
curl -s -o /dev/null -w "%{http_code}" \
  -X DELETE https://api.coherencycoin.com/api/concepts/trust \
  -H "X-API-Key: $API_KEY"
```

Expected: `403` — seeded concepts (source=`living-codex`) are protected from deletion.

---

### Scenario 4 — Search Concepts

**Setup**: 184 concepts seeded.

**Action**:

```bash
curl -s "https://api.coherencycoin.com/api/concepts/search?q=trust" \
  | python3 -c "
import json, sys
d = json.load(sys.stdin)
ids = [c['id'] for c in d['concepts']]
assert 'trust' in ids, f'trust not in results: {ids}'
assert d['total'] >= 1
print('Search OK - results:', d['total'])
"
```

Expected: `Search OK - results: 3` (at minimum 1).

**Edge case — No results**:

```bash
curl -s "https://api.coherencycoin.com/api/concepts/search?q=xyznonexistent999" \
  | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['total'] == 0
assert d['concepts'] == []
print('Empty search OK')
"
```

Expected: `200` with `{"total": 0, "concepts": []}` — not 404.

---

### Scenario 5 — Tag Idea with Concept, Navigate Back

**Setup**: Idea `abc123` exists. Concept `trust` seeded.

**Tag idea**:

```bash
curl -s -X POST https://api.coherencycoin.com/api/ideas/abc123/concepts \
  -H "Content-Type: application/json" -H "X-API-Key: $API_KEY" \
  -d '{"concept_id": "trust"}' \
  | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['concept_id'] == 'trust'
print('Tagged OK')
"
```

**Navigate from concept to tagged ideas**:

```bash
curl -s https://api.coherencycoin.com/api/concepts/trust/ideas \
  | python3 -c "
import json, sys
d = json.load(sys.stdin)
idea_ids = [i['id'] for i in d['ideas']]
assert 'abc123' in idea_ids, f'abc123 not in concept ideas: {idea_ids}'
print('Navigate OK - ideas:', len(d['ideas']))
"
```

**Idea response includes tagged concept**:

```bash
curl -s https://api.coherencycoin.com/api/ideas/abc123 \
  | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert 'concepts' in d, 'concepts field missing from idea response'
concept_ids = [c['id'] for c in d['concepts']]
assert 'trust' in concept_ids, f'trust not in idea concepts: {concept_ids}'
print('Idea->concept OK')
"
```

**Edge case — Duplicate tag is idempotent (200, not 409)**:

```bash
curl -s -o /dev/null -w "%{http_code}" \
  -X POST https://api.coherencycoin.com/api/ideas/abc123/concepts \
  -H "Content-Type: application/json" -H "X-API-Key: $API_KEY" \
  -d '{"concept_id": "trust"}'
```

Expected: `200` — tagging twice is OK, uses `ON CONFLICT DO NOTHING`.

---

## CLI Verification

```bash
# List all 184 concepts
cc concepts
# Expected: Rich table — ID | Name | Category | Edge Count (184 rows)

# Get single concept
cc concept trust
# Expected: Formatted card — Trust, description, axes, outgoing/incoming edges

# Create a typed edge
cc concept link coherence requires resonance
# Expected: "Edge created: coherence --[requires]--> resonance"

# Search
cc concept search breath
# Expected: Table showing concepts matching "breath"

# Tag an idea
cc concept tag abc123 trust
# Expected: "Tagged idea abc123 with concept trust"
```

---

## Risks and Assumptions

| Risk | Likelihood | Mitigation |
|------|-----------|-----------|
| Living Codex JSON files not yet ported | High | Files created as part of this implementation |
| Slug IDs collide with existing resources | Low | Concepts use `/api/concepts/` namespace |
| 184 rows degrades search performance | Low | Full-text index on name+description; trivial size |
| `idea_concepts` FK fails if `ideas.id` type differs | Medium | Verify `ideas.id` column type before migration |
| MCP registration breaks existing tools | Low | Additive changes to `server.json` only |
| Operator deletes seeded concept | Certain | Return 403 with clear message |

**Assumption**: Concept IDs are stable slugs (not UUIDs). The Living Codex uses semantic names
(`trust`, `resonance`), making CLI/MCP usage human-readable and memorable.

**Assumption**: Living Codex JSON files will be authored as part of this implementation work,
porting 184 concepts, 46 relationships, and 53 axes into the three config JSON files.

---

## Known Gaps and Follow-up Tasks

- **Gap**: News item concept tagging not scoped here. Follow-up: `news_concepts` join table,
  `GET /api/news/{id}/concepts`, `POST /api/concepts/{id}/news`.
- **Gap**: Contributor concept affinity (which concepts a contributor most frequently tags) is
  a future signal for resonance scoring.
- **Gap**: Concept similarity via embeddings (clustering 184 concepts by semantic proximity) is
  out of scope. A future resonance spec may add this.
- **Gap**: Visual concept graph (force-directed D3.js) is out of scope. `/concepts/{id}` shows
  edge lists; a follow-up visual spec can build on this data foundation.
- **Gap**: Concept versioning (audit trail of description/edge changes) not addressed.
- **Gap**: Deeper axis navigation (view all concepts on `trust-fear` axis sorted by affinity)
  is a follow-up feature beyond the filter dropdown.

---

## Implementation Order

1. Author `config/ontology/core-concepts.json` (184 entries), `core-relationships.json` (46 edges),
   `core-axes.json` (53 axes).
2. Write Alembic schema migration for all four tables.
3. Write Alembic data migration: reads JSON files, seeds with `ON CONFLICT DO NOTHING`.
4. Write Pydantic models + SQLAlchemy ORM in `api/app/models/concepts.py`.
5. Write service layer `api/app/services/concept_service.py`.
6. Write FastAPI router `api/app/routers/concepts.py` and register in `main.py`.
7. Write tests `api/tests/test_concept_layer.py` (>=20 test cases).
8. Write web pages (`/concepts`, `/concepts/[id]`).
9. Add CLI commands.
10. Register MCP tools in `mcp-server/server.json`.

---

## Verification

Run from API root:

```bash
cd api && .venv/bin/pytest tests/test_concept_layer.py -v --tb=short
```

Expected: All tests pass, zero failures.

API smoke test:

```bash
curl -s https://api.coherencycoin.com/api/concepts \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print('Total:', d['total'])"
```

Expected: `Total: 184`
