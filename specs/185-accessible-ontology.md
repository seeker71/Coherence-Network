# Spec 185 — Accessible Ontology: Non-Technical Contributor Extension

**Spec ID**: 185-accessible-ontology
**Idea ID**: accessible-ontology
**Task ID**: task_8865d9a8ae7ca41a
**Status**: approved
**Priority**: high
**Author**: product-manager agent
**Date**: 2026-03-28
**Category**: ux / ontology / accessibility
**Depends on**: Spec 182 (Concept Layer CRUD), Spec 169 (Fractal Node+Edge Primitives), Spec 181 (Concept Translation / Worldview Lenses)

---

## Summary

Non-technical contributors cannot currently extend the Coherence Network ontology. The graph, concept IDs, and relationship types are invisible to anyone without graph theory background. This spec closes that gap: **anyone who can describe an idea in plain language can extend the ontology**. The system handles placement, inferring where the idea fits among existing concepts or creating new conceptual space. Experts see the graph; everyone else sees gardens, cards, and conversations.

The feature is provably working when: (1) a contributor with zero graph knowledge submits a concept in prose, (2) the API places it near related concepts without human curation, and (3) a metrics endpoint shows contribution rate, placement accuracy, and relationship density growing over time.

---

## Goals

| # | Goal |
|---|------|
| G1 | A contributor submits a concept using only a name, a plain-language description, and domain tags — no graph IDs, no relationship types. |
| G2 | The system infers nearest existing concepts (by keyword and resonance similarity) and proposes candidate relationships automatically. |
| G3 | The system provides three UI modes for the same ontology data: **Graph** (force-directed, for technical contributors), **Garden** (card grid grouped by domain), **Conversation** (chat-like Q&A that explains concepts in plain language). |
| G4 | A `/api/accessible-ontology/metrics` endpoint reports contribution activity, placement quality, and relationship density — proving that the system is working and improving over time. |
| G5 | Non-technical contributions are flagged for optional expert review but are immediately visible and usable without approval. |

---

## Background and Motivation

The Coherence Network ontology currently holds 184 concepts, 46 relationship types, and 53 axes (Spec 182 baseline). These were authored by or with technical contributors. As the network grows, the ontology must grow with it — but domain experts (historians, artists, policy writers, scientists) who have never opened a graph database cannot contribute. The result is an ontology that reflects the biases of its most technical contributors.

The Living Codex origin project established that concepts like **breath**, **resonance**, **belief systems**, and **portals** are legitimate primitives — not technical constructs, but experiential ones. Those concepts were added because their originators happened to understand the system. The principle this spec encodes: **every knowledge domain deserves a native speaker at the ontology level**.

The three views (Graph, Garden, Conversation) are not cosmetic. They are epistemic access modes. A marine biologist navigating the ontology as a card garden, tagged by "marine ecology", is contributing differently — but legitimately — from an engineer viewing the same data as a directed graph. Both views must stay synchronized from a single data source.

---

## Requirements

### R1 — Plain-Language Submission

- [ ] `POST /api/accessible-ontology/concepts` accepts `{ name, description, domain_tags, submitted_by }` — no graph IDs required
- [ ] `name` max 120 chars; `description` max 2000 chars; `domain_tags` is a list of 1–10 free strings
- [ ] On success, returns HTTP 201 with the canonical concept ID, proposed relationship candidates, and nearest existing concepts (by similarity score)
- [ ] On submission, the concept is immediately visible via `GET /api/concepts` — it does not await approval
- [ ] Submitted concept gets `review_status: "pending"` by default and `review_status: "approved"` once a technical peer confirms relationships
- [ ] `description` field is **required** — empty string returns 422

### R2 — Relationship Inference

- [ ] The inference engine finds at most 5 nearest existing concepts by TF-IDF keyword overlap on `name + description + domain_tags`
- [ ] For each candidate pair, the engine assigns one of the canonical edge types: `extends`, `analogous-to`, `inspires`, `depends-on`, `parent-of`, `contradicts`
- [ ] Inferred relationships are stored with `confidence: float (0.0–1.0)` and `inferred: true` in the edge payload
- [ ] `GET /api/accessible-ontology/concepts/{id}/neighbors` returns all neighbors with confidence scores
- [ ] `PATCH /api/accessible-ontology/concepts/{id}/relationships/{edge_id}/confirm` promotes `inferred: true` → `inferred: false` and sets `review_status: "approved"` on the edge (technical peer action)
- [ ] `GET /api/accessible-ontology/concepts/{id}/neighbors?inferred_only=true` filters to only unconfirmed inferred edges

### R3 — Domain Tagging

- [ ] `GET /api/accessible-ontology/domains` returns all known domain tags with concept counts
- [ ] Domain tags are free-form strings normalized to lowercase, trimmed, and deduplicated on write
- [ ] `GET /api/accessible-ontology/concepts?domain=marine+ecology` returns all concepts tagged with that domain
- [ ] Concepts can have multiple domain tags; each tag is an independent facet
- [ ] `POST /api/accessible-ontology/concepts/{id}/tags` adds tags to an existing concept (appends, does not replace)

### R4 — Three View Modes (API Contracts)

The three views share the same data; only the API response shape differs:

| View | Endpoint | Response Shape |
|------|----------|----------------|
| Graph | `GET /api/accessible-ontology/graph` | `{ nodes: [{id, name, type}], edges: [{from, to, type, confidence}] }` — D3/vis compatible |
| Garden | `GET /api/accessible-ontology/garden` | `{ domains: [{ tag, concepts: [{id, name, description, resonance_score}] }] }` — grouped by domain |
| Conversation | `GET /api/accessible-ontology/concepts/{id}/explain` | `{ concept_id, plain_summary, analogies: [str], related_in_plain: [str], depth: "beginner"\|"expert" }` |

- [ ] `GET /api/accessible-ontology/graph` returns all approved concepts and their edges, in D3-compatible format
- [ ] `GET /api/accessible-ontology/garden` returns concepts grouped by domain tag, sorted by concept count descending
- [ ] `GET /api/accessible-ontology/concepts/{id}/explain?depth=beginner` returns a plain-language summary without jargon
- [ ] `GET /api/accessible-ontology/concepts/{id}/explain?depth=expert` returns the full graph context, axes, and relationship list
- [ ] All three view endpoints return HTTP 200 even when the ontology has zero concepts (empty but valid shapes)

### R5 — Metrics and Proof

- [ ] `GET /api/accessible-ontology/metrics` returns:
  ```json
  {
    "total_concepts": int,
    "concepts_by_domain": { "domain_tag": int },
    "inferred_edges": int,
    "confirmed_edges": int,
    "pending_review": int,
    "avg_confidence": float,
    "contribution_rate_7d": float,   // concepts submitted per day over last 7 days
    "placement_accuracy": float      // % of inferred edges confirmed without edit
  }
  ```
- [ ] `placement_accuracy` is `confirmed_edges / (confirmed_edges + rejected_edges)` — computed from the edge audit log
- [ ] `contribution_rate_7d` is recomputed at query time from `created_at` timestamps — no separate job required
- [ ] An edge rejection is recorded when a technical peer calls `DELETE /api/accessible-ontology/concepts/{id}/relationships/{edge_id}` on an inferred edge
- [ ] `GET /api/accessible-ontology/metrics/history?window=30d` returns daily snapshots for the last 30 days (one row per calendar day, zero-filled when no activity)

### R6 — Web Pages

| Path | Purpose |
|------|---------|
| `/ontology` | Garden view (default for non-technical users). Card grid grouped by domain. |
| `/ontology/graph` | Graph view (force-directed). Toggle from Garden view. |
| `/ontology/contribute` | Plain-language submission form. Name + description textarea + domain tag chips. |
| `/ontology/concepts/[id]` | Concept detail page with Explain panel, neighbor list, and review status. |

- [ ] `/ontology` renders card grid with domain filter chips
- [ ] `/ontology/contribute` form validates `description` is non-empty before submit
- [ ] Submitted concept appears on `/ontology` immediately (no page reload required after 201)
- [ ] `/ontology/graph` renders a valid React component (no SSR crash with empty data)

---

## Data Model

### New Table: `accessible_ontology_concepts`

```sql
CREATE TABLE accessible_ontology_concepts (
    id              TEXT PRIMARY KEY,          -- slugified name, e.g. "marine-photosynthesis"
    name            TEXT NOT NULL,
    description     TEXT NOT NULL,
    domain_tags     TEXT[] NOT NULL DEFAULT '{}',
    submitted_by    TEXT NOT NULL DEFAULT 'anonymous',
    review_status   TEXT NOT NULL DEFAULT 'pending',  -- 'pending' | 'approved' | 'rejected'
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ON accessible_ontology_concepts USING GIN(domain_tags);
CREATE INDEX ON accessible_ontology_concepts (review_status);
CREATE INDEX ON accessible_ontology_concepts (created_at);
```

### New Table: `accessible_ontology_edges`

```sql
CREATE TABLE accessible_ontology_edges (
    id              TEXT PRIMARY KEY,          -- uuid
    from_concept_id TEXT NOT NULL REFERENCES accessible_ontology_concepts(id),
    to_concept_id   TEXT NOT NULL REFERENCES accessible_ontology_concepts(id),
    edge_type       TEXT NOT NULL,             -- canonical edge type
    confidence      FLOAT NOT NULL DEFAULT 0.5,
    inferred        BOOLEAN NOT NULL DEFAULT TRUE,
    review_status   TEXT NOT NULL DEFAULT 'pending',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT no_self_loop CHECK (from_concept_id <> to_concept_id)
);

CREATE INDEX ON accessible_ontology_edges (from_concept_id);
CREATE INDEX ON accessible_ontology_edges (to_concept_id);
CREATE INDEX ON accessible_ontology_edges (inferred, review_status);
```

### Relationship to Existing Concepts Table

Concepts submitted via this flow are also written to the existing `concepts` table (Spec 182) with `type_id = "codex.ucore.user"`. This ensures they appear in `GET /api/concepts` and are searchable across the full ontology. The `accessible_ontology_concepts` table is the authoritative source for accessible-ontology-specific metadata (domain tags, review status, inference scores).

---

## API Summary

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/accessible-ontology/concepts` | Submit concept in plain language |
| `GET` | `/api/accessible-ontology/concepts` | List concepts (filterable by domain, review_status) |
| `GET` | `/api/accessible-ontology/concepts/{id}` | Get single concept |
| `PATCH` | `/api/accessible-ontology/concepts/{id}/tags` | Add domain tags |
| `GET` | `/api/accessible-ontology/concepts/{id}/neighbors` | Inferred + confirmed relationships |
| `PATCH` | `/api/accessible-ontology/concepts/{id}/relationships/{edge_id}/confirm` | Expert confirms inferred edge |
| `DELETE` | `/api/accessible-ontology/concepts/{id}/relationships/{edge_id}` | Expert rejects inferred edge |
| `GET` | `/api/accessible-ontology/concepts/{id}/explain` | Plain-language explanation |
| `GET` | `/api/accessible-ontology/domains` | All known domain tags with counts |
| `GET` | `/api/accessible-ontology/graph` | Graph view data (D3 compatible) |
| `GET` | `/api/accessible-ontology/garden` | Garden view data (grouped by domain) |
| `GET` | `/api/accessible-ontology/metrics` | Contribution metrics |
| `GET` | `/api/accessible-ontology/metrics/history` | Daily metrics history |

---

## Inference Algorithm (Minimum Viable)

The v1 inference algorithm is intentionally simple and runs synchronously:

1. **Tokenize** `name + " " + description + " " + " ".join(domain_tags)` → bag of normalized tokens
2. **Score each existing concept** using Jaccard similarity on token sets
3. **Select top 5** by score (minimum score 0.1 to suppress noise)
4. **Assign edge type** using a heuristic keyword map:
   - If shared token is a verb (`extends`, `inspires`, `depends`) → use that type
   - If one concept's name is a substring of another → `parent-of`
   - Otherwise → `analogous-to` (safe default)
5. **Confidence** = raw Jaccard score, clamped to `[0.1, 0.95]`

This algorithm is intentionally replaceable. A future spec can swap it for embedding-based similarity without changing any API contracts.

---

## Verification Scenarios

### Scenario 1 — Full Create-Read Cycle (non-technical submission)

**Setup:** Empty accessible ontology; at least one existing concept exists (e.g., `codex.ucore.water`).

**Action:**
```bash
API=https://api.coherencycoin.com
curl -s -X POST $API/api/accessible-ontology/concepts \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Marine Photosynthesis",
    "description": "The process by which ocean plants convert sunlight to energy, fundamental to the water cycle and life itself.",
    "domain_tags": ["marine ecology", "energy", "cycles"],
    "submitted_by": "dr-sarah-ocean"
  }'
```

**Expected:**
- HTTP 201
- Response contains `{"id": "marine-photosynthesis", "name": "Marine Photosynthesis", "review_status": "pending"}`
- Response contains `"nearest_concepts"` array with at least 1 entry
- Response contains `"proposed_relationships"` array

**Then:**
```bash
curl -s $API/api/accessible-ontology/concepts/marine-photosynthesis
# Returns 200 with concept detail

curl -s $API/api/accessible-ontology/concepts/marine-photosynthesis/neighbors
# Returns list (may be empty if no existing concepts overlap)

curl -s $API/api/concepts
# Returns list that INCLUDES "marine-photosynthesis" (synced to concepts table)
```

**Edge cases:**
- `POST` same concept again → HTTP 409 `{"detail": "Concept 'marine-photosynthesis' already exists"}`
- `GET /api/accessible-ontology/concepts/nonexistent` → HTTP 404
- `POST` with empty `description` → HTTP 422 with field error on `description`

---

### Scenario 2 — Domain Tagging and Garden View

**Setup:** At least 3 concepts exist with various domain tags: `["ecology", "physics"]`, `["ecology", "water"]`, `["philosophy"]`.

**Action:**
```bash
curl -s $API/api/accessible-ontology/garden
```

**Expected:**
- HTTP 200
- Response shape: `{"domains": [{"tag": "ecology", "concepts": [...]}, ...]}`
- Domain with most concepts appears first
- Each concept entry has `id`, `name`, `description`

**Then:**
```bash
curl -s "$API/api/accessible-ontology/concepts?domain=ecology"
# Returns only concepts tagged with "ecology"

curl -s $API/api/accessible-ontology/domains
# Returns [{"tag": "ecology", "count": 2}, {"tag": "physics", "count": 1}, ...]
```

**Edge cases:**
- `GET /api/accessible-ontology/garden` with zero concepts → HTTP 200 `{"domains": []}`
- `GET /api/accessible-ontology/concepts?domain=nonexistent-domain` → HTTP 200 `{"items": [], "total": 0}`
- `PATCH /api/accessible-ontology/concepts/{id}/tags` with duplicate tag → HTTP 200, tag appears only once in result

---

### Scenario 3 — Relationship Confirmation (Expert Peer Review)

**Setup:** Concept `marine-photosynthesis` exists with at least one inferred edge (confidence 0.5, `inferred: true`).

**Action:**
```bash
# Get the inferred edges
NEIGHBORS=$(curl -s "$API/api/accessible-ontology/concepts/marine-photosynthesis/neighbors?inferred_only=true")
EDGE_ID=$(echo $NEIGHBORS | python3 -c "import sys,json; print(json.load(sys.stdin)['edges'][0]['id'])")

# Expert confirms the edge
curl -s -X PATCH "$API/api/accessible-ontology/concepts/marine-photosynthesis/relationships/$EDGE_ID/confirm"
```

**Expected:**
- HTTP 200, response contains `{"inferred": false, "review_status": "approved"}`

**Then:**
```bash
curl -s $API/api/accessible-ontology/metrics
# "confirmed_edges" is 1 (or more), "placement_accuracy" is > 0.0
```

**Edge cases:**
- Confirm non-existent edge_id → HTTP 404
- Confirm already-confirmed edge → HTTP 200 (idempotent, not 409)
- Reject an inferred edge via `DELETE` → metrics `placement_accuracy` recalculates: rejected edge is counted in denominator

---

### Scenario 4 — Plain-Language Explain Endpoint

**Setup:** Concept `marine-photosynthesis` exists with `description` set, domain_tags `["marine ecology"]`, and at least one confirmed neighbor `codex.ucore.water`.

**Action:**
```bash
curl -s "$API/api/accessible-ontology/concepts/marine-photosynthesis/explain?depth=beginner"
```

**Expected:**
- HTTP 200
- Response contains `"plain_summary"` (non-empty string, no graph jargon)
- Response contains `"analogies"` array with at least 1 entry
- Response contains `"related_in_plain"` array listing neighbor names in plain English
- Response contains `"depth": "beginner"`

**Then:**
```bash
curl -s "$API/api/accessible-ontology/concepts/marine-photosynthesis/explain?depth=expert"
# Returns 200 with full graph context, axes list, relationship types
# "depth": "expert"
```

**Edge cases:**
- `explain` for non-existent concept → HTTP 404
- `explain` with invalid `depth` value → HTTP 422 with allowed values in error

---

### Scenario 5 — Metrics History (Proof Over Time)

**Setup:** At least 2 concepts were submitted on different calendar days (can simulate with different `created_at` values in seed data for test environment).

**Action:**
```bash
curl -s "$API/api/accessible-ontology/metrics"
curl -s "$API/api/accessible-ontology/metrics/history?window=7d"
```

**Expected for `/metrics`:**
- HTTP 200
- `total_concepts` ≥ 1
- `contribution_rate_7d` is a non-negative float
- `placement_accuracy` is between 0.0 and 1.0 inclusive
- `avg_confidence` is between 0.0 and 1.0 inclusive

**Expected for `/metrics/history?window=7d`:**
- HTTP 200
- Response contains `"days"` array with exactly 7 entries
- Each entry has `date` (ISO 8601), `concepts_added`, `edges_confirmed`, `edges_rejected`
- Days with no activity show `0` values (zero-filled, not omitted)

**Edge cases:**
- `GET /api/accessible-ontology/metrics` with zero contributions → HTTP 200 with all counts = 0, `placement_accuracy` = 1.0 (no rejections), `contribution_rate_7d` = 0.0
- `GET /api/accessible-ontology/metrics/history?window=invalid` → HTTP 422
- `GET /api/accessible-ontology/metrics/history?window=400d` → HTTP 422 (max 90 days)

---

## Implementation Files

| File | Change |
|------|--------|
| `api/app/routers/accessible_ontology.py` | Replace stub with full router (all 13 endpoints) |
| `api/app/services/accessible_ontology_service.py` | New — business logic: submission, inference, explain, metrics |
| `api/app/models/accessible_ontology.py` | New — Pydantic request/response models |
| `api/alembic/versions/XXXX_accessible_ontology.py` | New — migration for two tables |
| `web/app/ontology/page.tsx` | New — Garden view (card grid, domain filter) |
| `web/app/ontology/graph/page.tsx` | New — Graph view (force-directed, toggle) |
| `web/app/ontology/contribute/page.tsx` | New — Submission form |
| `web/app/ontology/concepts/[id]/page.tsx` | New — Concept detail with Explain panel |
| `api/tests/test_accessible_ontology.py` | New — pytest test suite |

---

## Risks and Assumptions

| # | Risk | Mitigation |
|---|------|------------|
| R1 | TF-IDF inference produces low-quality relationships for short descriptions | Require minimum 20-char description; show confidence scores to users so they know to expect imperfect suggestions |
| R2 | Non-technical contributors submit near-duplicate concepts (e.g., "ocean photosynthesis" and "marine photosynthesis") | Fuzzy duplicate detection on submission: warn (not block) if name similarity > 0.8 with existing concept |
| R3 | Graph view and Garden view get out of sync if data is cached separately | Both views read from the same tables; no separate cache layer in v1 |
| R4 | Expert review queue grows unbounded if no one reviews pending edges | Metrics endpoint exposes `pending_review` count — surfaced in admin dashboard; no SLA enforcement in v1 |
| R5 | `explain` endpoint generates jargon-filled responses for technical concepts | v1 uses description text directly; a future spec can wire a language model for reformulation |

---

## Known Gaps and Follow-up Tasks

- **FT-1**: Wire a language model (e.g., Claude haiku) to `GET /api/accessible-ontology/concepts/{id}/explain` for true plain-language generation (v1 returns the description field verbatim for `depth=beginner`).
- **FT-2**: Embedding-based similarity (sentence transformers or API embeddings) to replace TF-IDF inference for higher-quality relationship candidates.
- **FT-3**: Bulk import — allow domain experts to submit a CSV of concepts with descriptions, processed as a batch.
- **FT-4**: Resonance scoring integration — feed `accessible_ontology_concepts` into the resonance pipeline so non-technical contributions can accrue resonance scores over time.
- **FT-5**: Notifications — notify the submitter when their concept's inferred edges are confirmed or rejected by a peer.

---

## Verification

The feature is **verified and working** when all five verification scenarios above pass against the production API (`https://api.coherencycoin.com`), AND:

- `GET /api/accessible-ontology/metrics` returns `total_concepts >= 1`
- `GET /api/accessible-ontology/garden` returns at least one domain group
- `GET /api/concepts` includes at least one concept with `type_id = "codex.ucore.user"` submitted via this flow
- The web page `/ontology` renders without a runtime error
- The web page `/ontology/contribute` successfully submits a concept and shows it on `/ontology` without a page reload
