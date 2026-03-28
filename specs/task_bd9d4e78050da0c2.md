# Spec: Accessible Ontology — Non-Technical Contributors Extend It Naturally

**ID**: task_bd9d4e78050da0c2
**Status**: approved
**Author**: claude-sonnet-4-6
**Date**: 2026-03-28

---

## Summary

Non-technical contributors should be able to extend the Coherence Network's ontology without
understanding graph theory, knowledge representation, or any technical vocabulary. A contributor
shares an idea or concept in plain language, optionally tags it with domains they already know
(science, music, ecology, finance, etc.), and the system takes care of placement: finding where it
fits in the existing graph or carving out new space for it.

Technical users continue to see the underlying graph with typed nodes, edges, and coherence
scores. Everyone else sees **gardens** (spatial domain clusters), **cards** (concept summaries),
and **conversations** (resonance threads). Both views point at the same data model — the
presentation layer adapts to the viewer, not the other way around.

A key open question is **proof of utility**: how do we show that the system is actually
helping non-technical contributors connect ideas, not just accepting text and silently ignoring it?
This spec answers that with explicit "working signals" — visible counts, resonance traces, and
periodic digest emails that surface the journey from plain-language submission to confirmed graph placement.

---

## Purpose

Ontologies grow slowly when only specialists can edit them. Most contributors to the Coherence
Network are domain practitioners (artists, scientists, educators, engineers) who have valuable
conceptual knowledge but no training in ontology engineering or graph databases. This feature
removes that barrier.

By accepting plain-language input and inferring structure, the system dramatically increases
the surface area of knowledge capture, reduces friction for new contributors, and makes the
ontology self-evidently alive rather than an expert artifact. The "gardens, cards, and
conversations" UX layer makes the ontology feel like a collaborative wiki, not a database.

---

## Requirements

### Functional

- [ ] `POST /api/ontology/concepts` — accepts `title` (string, ≤200 chars), `body`
  (plain-language description, ≤2000 chars), `domains` (array of domain slugs, 0–5),
  `contributor_id` (optional UUID). Returns a `OntologyConcept` with `id`, `status: "pending"`,
  and `inferred_relations: []`.
- [ ] `GET /api/ontology/concepts` — paginated list with filters `?domain=&status=&q=&limit=&cursor=`.
- [ ] `GET /api/ontology/concepts/{id}` — fetch single concept with current `inferred_relations`,
  `resonance_score`, and `confirmation_count`.
- [ ] `PATCH /api/ontology/concepts/{id}` — update `title`, `body`, `domains`. Status transitions:
  `pending → confirmed → deprecated`.
- [ ] `DELETE /api/ontology/concepts/{id}` — soft-delete (sets `deleted_at`).
- [ ] `POST /api/ontology/concepts/{id}/resonate` — increment resonance signal from a contributor
  (body: `{ "contributor_id": "...", "strength": 0.0–1.0 }`). Updates `resonance_score`.
- [ ] `GET /api/ontology/concepts/{id}/related` — returns inferred related concepts with
  `confidence` scores, sorted descending. Supports `?min_confidence=0.3`.
- [ ] `GET /api/ontology/garden` — returns spatial cluster data: each domain with its member
  concepts (id, title, resonance_score, status). Used by the garden view.
- [ ] `GET /api/ontology/domains` — list all known domain slugs with labels, colors, and
  concept counts.
- [ ] `GET /api/ontology/activity` — time-series of submissions, confirmations, and resonance
  events. Supports `?since=ISO8601&until=ISO8601`. Proves the feature is working over time.
- [ ] Relation inference runs asynchronously after concept creation: the system computes
  cosine similarity against existing concept bodies and records candidate relations with
  `confidence` scores in `ontology_relations`. No ML model required — TF-IDF over concept
  bodies is sufficient for MVP.
- [ ] Garden view page at `/ontology` (Next.js): renders domain clusters as interactive
  card groups. Default view for all visitors.
- [ ] Graph view page at `/ontology/graph`: renders the full technical graph (nodes + edges,
  coherence scores, relation types). Accessible via toggle from the garden view.
- [ ] Concept detail page at `/ontology/{id}`: shows card view with plain-language description,
  domain tags, related concepts, resonance score, and a "resonate" button.
- [ ] Contribution form at `/ontology/new`: single-page form — title, body textarea, domain
  multi-select (checkboxes with friendly labels). On submit, calls `POST /api/ontology/concepts`
  and redirects to `/ontology/{id}`.
- [ ] CLI command `cc ontology add "<title>" --body "<text>" --domains science,ecology` submits
  a new concept.
- [ ] CLI command `cc ontology list [--domain <slug>] [--status pending|confirmed]` lists concepts.
- [ ] CLI command `cc ontology show <id>` shows a concept with inferred relations.

### Non-Functional

- [ ] Concept creation P99 < 100 ms (synchronous write); relation inference runs in background task.
- [ ] Garden view renders ≤ 500 concepts without pagination; larger sets are clustered by domain
  first, then by resonance rank.
- [ ] All new Python code passes `ruff check` with zero warnings.
- [ ] Test coverage ≥ 75% on new router and service modules.
- [ ] Soft-deleted concepts are excluded from all list and related-concept responses.

---

## Data Model

### `ontology_concepts` table

```sql
CREATE TABLE ontology_concepts (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title            TEXT NOT NULL CHECK (char_length(title) BETWEEN 1 AND 200),
    body             TEXT NOT NULL CHECK (char_length(body) BETWEEN 1 AND 2000),
    domains          TEXT[] NOT NULL DEFAULT '{}',
    contributor_id   UUID,
    status           TEXT NOT NULL DEFAULT 'pending'
                       CHECK (status IN ('pending', 'confirmed', 'deprecated')),
    resonance_score  FLOAT NOT NULL DEFAULT 0.0
                       CHECK (resonance_score BETWEEN 0.0 AND 1.0),
    confirmation_count INTEGER NOT NULL DEFAULT 0,
    view_count       INTEGER NOT NULL DEFAULT 0,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at       TIMESTAMPTZ
);

CREATE INDEX idx_ontology_concepts_status    ON ontology_concepts (status)    WHERE deleted_at IS NULL;
CREATE INDEX idx_ontology_concepts_domains   ON ontology_concepts USING GIN (domains);
CREATE INDEX idx_ontology_concepts_created   ON ontology_concepts (created_at DESC);
CREATE INDEX idx_ontology_concepts_resonance ON ontology_concepts (resonance_score DESC);
```

### `ontology_relations` table

```sql
CREATE TABLE ontology_relations (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    src_concept_id   UUID NOT NULL REFERENCES ontology_concepts(id),
    dst_concept_id   UUID NOT NULL REFERENCES ontology_concepts(id),
    rel_type         TEXT NOT NULL DEFAULT 'related'
                       CHECK (rel_type IN ('related', 'specialises', 'generalises', 'contrasts', 'co_occurs')),
    confidence       FLOAT NOT NULL CHECK (confidence BETWEEN 0.0 AND 1.0),
    inferred_by      TEXT NOT NULL DEFAULT 'tfidf_cosine',
    confirmed        BOOLEAN NOT NULL DEFAULT FALSE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT no_self_relation CHECK (src_concept_id <> dst_concept_id),
    CONSTRAINT unique_relation_pair UNIQUE (src_concept_id, dst_concept_id, rel_type)
);

CREATE INDEX idx_ontology_relations_src  ON ontology_relations (src_concept_id);
CREATE INDEX idx_ontology_relations_dst  ON ontology_relations (dst_concept_id);
```

### `ontology_domains` table

```sql
CREATE TABLE ontology_domains (
    slug             TEXT PRIMARY KEY,
    label            TEXT NOT NULL,
    description      TEXT NOT NULL DEFAULT '',
    color            TEXT NOT NULL DEFAULT '#6B7280',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### Pydantic Models

```python
class OntologyConceptCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=1, max_length=2000)
    domains: list[str] = Field(default_factory=list, max_items=5)
    contributor_id: UUID | None = None

class OntologyConceptResponse(BaseModel):
    id: UUID
    title: str
    body: str
    domains: list[str]
    contributor_id: UUID | None
    status: str
    resonance_score: float
    confirmation_count: int
    view_count: int
    inferred_relations: list[OntologyRelationSummary]
    created_at: datetime
    updated_at: datetime

class OntologyRelationSummary(BaseModel):
    id: UUID
    related_concept_id: UUID
    related_concept_title: str
    rel_type: str
    confidence: float
    confirmed: bool

class OntologyConceptPatch(BaseModel):
    title: str | None = None
    body: str | None = None
    domains: list[str] | None = None
    status: str | None = None

class OntologyResonateRequest(BaseModel):
    contributor_id: UUID | None = None
    strength: float = Field(default=0.5, ge=0.0, le=1.0)

class OntologyGardenResponse(BaseModel):
    domains: list[OntologyGardenDomain]
    total_concepts: int
    generated_at: datetime

class OntologyGardenDomain(BaseModel):
    slug: str
    label: str
    color: str
    concepts: list[OntologyConceptCard]

class OntologyConceptCard(BaseModel):
    id: UUID
    title: str
    resonance_score: float
    status: str
    related_count: int

class OntologyActivityPoint(BaseModel):
    date: date
    submissions: int
    confirmations: int
    resonance_events: int
    new_relations: int
```

---

## API Contract

### Concepts

| Method   | Path                                    | Description                             |
|----------|-----------------------------------------|-----------------------------------------|
| `POST`   | `/api/ontology/concepts`                | Submit new concept in plain language    |
| `GET`    | `/api/ontology/concepts`                | List with `?domain=&status=&q=&cursor=` |
| `GET`    | `/api/ontology/concepts/{id}`           | Fetch concept + inferred relations      |
| `PATCH`  | `/api/ontology/concepts/{id}`           | Update title/body/domains/status        |
| `DELETE` | `/api/ontology/concepts/{id}`           | Soft-delete                             |
| `POST`   | `/api/ontology/concepts/{id}/resonate`  | Send resonance signal                   |
| `GET`    | `/api/ontology/concepts/{id}/related`   | Related concepts by inference           |

### Garden + Domains + Activity

| Method | Path                         | Description                                  |
|--------|------------------------------|----------------------------------------------|
| `GET`  | `/api/ontology/garden`       | Spatial domain cluster data                  |
| `GET`  | `/api/ontology/domains`      | All domain slugs with labels and counts      |
| `GET`  | `/api/ontology/activity`     | Time-series of ontology health metrics       |

### Example Responses

**POST /api/ontology/concepts → 201**

```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "title": "Murmuration",
  "body": "When starlings fly in coordinated flocks that change shape fluidly...",
  "domains": ["ecology", "complexity"],
  "contributor_id": null,
  "status": "pending",
  "resonance_score": 0.0,
  "confirmation_count": 0,
  "view_count": 0,
  "inferred_relations": [],
  "created_at": "2026-03-28T10:00:00Z",
  "updated_at": "2026-03-28T10:00:00Z"
}
```

**GET /api/ontology/concepts/{id}/related → 200**

```json
{
  "concept_id": "3fa85f64-...",
  "related": [
    {
      "id": "rel-uuid",
      "related_concept_id": "concept-uuid-2",
      "related_concept_title": "Emergence",
      "rel_type": "related",
      "confidence": 0.73,
      "confirmed": false
    }
  ],
  "total": 1
}
```

**GET /api/ontology/garden → 200**

```json
{
  "domains": [
    {
      "slug": "ecology",
      "label": "Ecology",
      "color": "#22C55E",
      "concepts": [
        { "id": "uuid", "title": "Murmuration", "resonance_score": 0.41, "status": "pending", "related_count": 3 }
      ]
    }
  ],
  "total_concepts": 142,
  "generated_at": "2026-03-28T10:05:00Z"
}
```

**GET /api/ontology/activity?since=2026-03-01 → 200**

```json
{
  "series": [
    { "date": "2026-03-01", "submissions": 3, "confirmations": 1, "resonance_events": 12, "new_relations": 5 },
    { "date": "2026-03-02", "submissions": 0, "confirmations": 2, "resonance_events": 4,  "new_relations": 2 }
  ],
  "totals": { "submissions": 3, "confirmations": 3, "resonance_events": 16, "new_relations": 7 }
}
```

---

## How We Know It's Working

This feature's value is invisible unless we instrument it explicitly. Three "proof signals" are
required — each surfaced in the UI and queryable via API:

### Signal 1 — Submission Velocity (Are people contributing?)
`GET /api/ontology/activity` returning `submissions > 0` each week. The garden view header
shows a live count: "142 concepts from 38 contributors." The trend is the proof — a flat line
means the UX is not landing.

### Signal 2 — Relation Confirmation Rate (Is inference useful?)
Each inferred relation has a `confirmed` boolean. Contributors can accept or reject suggestions
from the concept detail page. Target: ≥ 40% of inferred relations get confirmed within 30 days.
`GET /api/ontology/activity` includes `confirmations` in the time series. Below 20% means
inference quality is too low; above 70% means we may be over-confirming easy matches.

### Signal 3 — Resonance Spread (Are concepts finding their community?)
A concept with `resonance_score > 0.5` from multiple contributors is evidence that non-technical
people are affirming others' concepts, not just submitting their own. The garden view sorts
concepts by resonance within each domain — high-resonance concepts "float up" visually. The
`/api/ontology/activity` endpoint exposes `resonance_events` per day.

These three signals combine into a simple health indicator on the `/ontology` page:
`📡 This week: 7 new concepts, 4 confirmations, 23 resonance signals — ontology is growing.`

---

## Web Pages

| Route           | Purpose                                                      |
|-----------------|--------------------------------------------------------------|
| `/ontology`     | Garden view: domain clusters with cards, sorted by resonance |
| `/ontology/new` | Plain-language contribution form (title, body, domain tags)  |
| `/ontology/{id}`| Concept detail: card + inferred relations + resonance button |
| `/ontology/graph`| Technical graph view (nodes/edges, toggled from garden)    |

The garden view and graph view share the same data source (`GET /api/ontology/garden` +
`GET /api/ontology/concepts`). The toggle is a URL param or button that switches rendering mode
without a page reload.

---

## Files to Create/Modify

```
api/
  alembic/versions/<ts>_add_ontology_tables.py   — migration: concepts, relations, domains tables
  app/models/ontology.py                          — Pydantic models (all types listed above)
  app/routers/ontology.py                         — FastAPI router mounted at /api/ontology
  app/services/ontology_service.py               — CRUD + inference trigger logic
  app/services/ontology_inference.py             — TF-IDF cosine similarity relation inference
  tests/test_ontology_router.py                  — pytest suite (see Acceptance Criteria)

web/
  app/ontology/page.tsx                          — Garden view (domain clusters)
  app/ontology/new/page.tsx                      — Contribution form
  app/ontology/[id]/page.tsx                     — Concept detail page
  app/ontology/graph/page.tsx                    — Technical graph view

cli/ (or api/cli/ depending on project structure)
  commands/ontology.py                           — cc ontology add / list / show commands
```

---

## Task Card

```yaml
goal: Allow non-technical contributors to add plain-language concepts; system infers relations and presents garden/card/graph views.
files_allowed:
  - api/alembic/versions/*_add_ontology_tables.py
  - api/app/models/ontology.py
  - api/app/routers/ontology.py
  - api/app/services/ontology_service.py
  - api/app/services/ontology_inference.py
  - api/tests/test_ontology_router.py
  - web/app/ontology/page.tsx
  - web/app/ontology/new/page.tsx
  - web/app/ontology/[id]/page.tsx
  - web/app/ontology/graph/page.tsx
done_when:
  - POST /api/ontology/concepts creates a concept and triggers async relation inference
  - GET /api/ontology/concepts/{id}/related returns inferred relations with confidence scores
  - GET /api/ontology/garden returns domain-clustered concept data
  - GET /api/ontology/activity returns time-series activity data
  - /ontology web page renders garden view
  - /ontology/new form submits and redirects to concept detail
  - pytest tests/test_ontology_router.py passes all tests
  - ruff check passes with 0 warnings
commands:
  - cd api && .venv/bin/ruff check app/routers/ontology.py app/services/ontology_service.py
  - cd api && .venv/bin/pytest tests/test_ontology_router.py -v --tb=short
constraints:
  - Relation inference must be async (background task); concept creation must not block on it
  - TF-IDF over concept bodies is acceptable for MVP; no external ML API calls
  - All status transitions are server-enforced; clients cannot set arbitrary status values
  - Soft-delete only; no hard deletes via public API
```

---

## Acceptance Criteria

All AC map 1:1 to tests in `api/tests/test_ontology_router.py`:

| Test | Requirement Verified |
|------|----------------------|
| `test_create_concept_201` | POST returns 201 with UUID, status=pending, empty inferred_relations |
| `test_create_concept_invalid_domains_exceed_5` | POST with 6 domains returns 422 |
| `test_create_concept_empty_title` | POST with title="" returns 422 |
| `test_get_concept_200` | GET /{id} returns full response including inferred_relations |
| `test_get_concept_404` | GET /nonexistent-uuid returns 404 |
| `test_patch_concept_status` | PATCH transitions pending→confirmed; invalid status→422 |
| `test_soft_delete_concept` | DELETE sets deleted_at; subsequent GET returns 404 |
| `test_soft_deleted_excluded_from_list` | Deleted concepts not in GET /ontology/concepts |
| `test_resonate_increments_score` | POST /resonate updates resonance_score |
| `test_resonate_clamped_at_1` | Score never exceeds 1.0 after many resonance events |
| `test_related_concepts_returned` | GET /related returns list after inference runs |
| `test_related_min_confidence_filter` | ?min_confidence=0.9 excludes low-confidence relations |
| `test_garden_view` | GET /garden returns domain clusters with concepts |
| `test_domains_list` | GET /domains returns all seeded domain slugs |
| `test_activity_time_series` | GET /activity?since=X returns dated series with correct counts |
| `test_duplicate_resonate_idempotent` | Same contributor resonating twice updates score but doesn't double-count |

---

## Verification Scenarios

Each scenario is intended to be run against the deployed API at `https://api.coherencycoin.com`.

### Scenario 1 — Full Concept Lifecycle (Create → Read → Update → Delete)

**Setup**: No concept with title "Murmuration" exists.

**Action**:
```bash
# Create
curl -s -X POST https://api.coherencycoin.com/api/ontology/concepts \
  -H "Content-Type: application/json" \
  -d '{"title":"Murmuration","body":"Coordinated movement of starlings forming fluid shapes in the sky, an emergent behaviour of simple local rules.","domains":["ecology","complexity"]}'

# Capture the returned id, then:
ID=<returned-id>
curl -s https://api.coherencycoin.com/api/ontology/concepts/$ID

# Update status to confirmed
curl -s -X PATCH https://api.coherencycoin.com/api/ontology/concepts/$ID \
  -H "Content-Type: application/json" \
  -d '{"status":"confirmed"}'

# Soft-delete
curl -s -X DELETE https://api.coherencycoin.com/api/ontology/concepts/$ID

# Verify gone from list
curl -s "https://api.coherencycoin.com/api/ontology/concepts?q=Murmuration"
```

**Expected**:
- POST → HTTP 201, `status: "pending"`, `id` is a UUID, `inferred_relations: []`
- GET → HTTP 200, full concept with same title and body
- PATCH → HTTP 200, `status: "confirmed"`
- DELETE → HTTP 200 or 204
- List query → empty `items: []` (soft-deleted not shown)

**Edge cases**:
- POST with empty title → HTTP 422 with validation error
- POST with 6 domains → HTTP 422 (`domains` exceeds max 5)
- GET after DELETE → HTTP 404 (not 500)
- PATCH with `status: "active"` (invalid) → HTTP 422

---

### Scenario 2 — Relation Inference (Background Task)

**Setup**: Concept "Emergence" already exists with body mentioning "collective behaviour" and "local interactions."

**Action**:
```bash
# Submit a new concept thematically related to emergence
curl -s -X POST https://api.coherencycoin.com/api/ontology/concepts \
  -H "Content-Type: application/json" \
  -d '{"title":"Swarm Intelligence","body":"Collective problem-solving behaviour arising from many simple agents interacting locally, producing global intelligence.","domains":["complexity","ai"]}'

ID=<returned-id>

# Wait for inference to run (background task; allow 5s)
sleep 5

curl -s "https://api.coherencycoin.com/api/ontology/concepts/$ID/related?min_confidence=0.1"
```

**Expected**:
- POST → HTTP 201
- GET /related → HTTP 200, `related` array containing at least one entry referencing "Emergence" concept with `confidence > 0.1` and `rel_type: "related"`
- Each relation entry has `confirmed: false` (not yet confirmed by human)

**Edge case**:
- `?min_confidence=0.99` for a fresh concept → returns empty `related: []` (no error)
- GET /related for deleted concept → HTTP 404

---

### Scenario 3 — Resonance Signals and Score Accumulation

**Setup**: Concept "Murmuration" exists with `resonance_score: 0.0`.

**Action**:
```bash
ID=<concept-id>

# Three distinct contributors send resonance signals
for i in 1 2 3; do
  curl -s -X POST https://api.coherencycoin.com/api/ontology/concepts/$ID/resonate \
    -H "Content-Type: application/json" \
    -d "{\"contributor_id\":\"00000000-0000-0000-0000-00000000000$i\",\"strength\":0.8}"
done

curl -s https://api.coherencycoin.com/api/ontology/concepts/$ID | jq .resonance_score
```

**Expected**:
- Each POST /resonate → HTTP 200
- Final `resonance_score > 0.0` (non-zero after resonance)
- Score is `≤ 1.0` (clamped)

**Edge case**:
- Same contributor resonating twice → score is not doubled; second call is idempotent or averaged
- `strength: 1.5` → HTTP 422 (out of range 0.0–1.0)

---

### Scenario 4 — Garden View (Non-Technical UX Proof)

**Setup**: At least 5 concepts exist across 2 domains (`ecology` and `complexity`).

**Action**:
```bash
curl -s https://api.coherencycoin.com/api/ontology/garden | jq '{
  total: .total_concepts,
  domains: [.domains[] | {slug: .slug, count: (.concepts | length)}]
}'
```

**Expected**:
- HTTP 200
- `total_concepts ≥ 5`
- Two domain entries present: `ecology` and `complexity`
- Each domain entry has a non-empty `concepts` array
- Concepts sorted by `resonance_score DESC` within each domain
- Response time < 500 ms

**Edge case**:
- If zero concepts exist → returns `{ "domains": [], "total_concepts": 0, "generated_at": "..." }` (not 500)

---

### Scenario 5 — Activity Time Series (Proof the Feature is Working)

**Setup**: At least one concept has been created and resonated in the last 7 days.

**Action**:
```bash
SINCE=$(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-7d +%Y-%m-%dT%H:%M:%SZ)
curl -s "https://api.coherencycoin.com/api/ontology/activity?since=$SINCE" | jq '{
  total_submissions: .totals.submissions,
  total_resonance: .totals.resonance_events,
  days_with_activity: [.series[] | select(.submissions > 0 or .resonance_events > 0)] | length
}'
```

**Expected**:
- HTTP 200
- `total_submissions ≥ 1` (at least one concept was created this week)
- `total_resonance ≥ 1` (at least one resonance signal was sent)
- `days_with_activity ≥ 1`
- All dates in `series` are within the requested range

**Edge case**:
- `?since=2099-01-01` → HTTP 200 with empty series `[]` and all totals = 0 (not 500)
- `?since=not-a-date` → HTTP 422 with validation detail

---

## Out of Scope

- ML-based relation inference (BERT embeddings, external NLP APIs); TF-IDF is MVP
- User authentication / per-contributor permissions (depends on auth layer)
- Ontology versioning / change history (follow-up spec)
- Export to OWL/RDF/SKOS formats
- Neo4j sync of ontology_concepts/relations (follow-up; graph DB reserved for heavy analytics)
- Email digest of weekly activity (follow-up; requires email service integration)
- Moderation workflow for spam/low-quality concepts
- Mobile-optimised garden view (responsive is fine; native app out of scope)

---

## Risks and Assumptions

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| TF-IDF inference produces low-quality relations (< 20% confirm rate) | Medium | Add minimum body length validation (≥ 50 chars); review threshold at first 100 concepts |
| Background inference task blocks event loop | Low | Use FastAPI `BackgroundTasks` or offload to Celery worker; do not block request thread |
| Garden view slow with > 500 concepts | Medium | Cap garden response at top-50 by resonance per domain; add `?all=true` escape hatch |
| Domain list grows unbounded (user-invented slugs) | Medium | Validate `domains` against `ontology_domains` table; 422 on unknown slug; seed initial set of ~20 domains |
| Resonance score manipulation (one contributor inflating score) | Low | Rate-limit resonate endpoint to 1/contributor/concept/hour; idempotent by (contributor_id, concept_id) |
| `pg_trgm` or `ts_vector` needed for quality full-text search | Low | Use `ILIKE %q%` for MVP; add GIN index on text search vector in follow-up |

**Assumptions**:
- PostgreSQL ≥ 14 is available in all environments (array type, gen_random_uuid()).
- The Coherence Network already has a concept of `contributor_id` (even as anonymous UUIDs); this spec does not require a logged-in user.
- The initial domain seed set (~20 slugs) will be inserted in the migration; the domain table can grow later via admin endpoint.
- TF-IDF computation over ≤ 1000 concept bodies is fast enough to run synchronously in a background task (< 2 s).

---

## Known Gaps and Follow-up Tasks

- **Auth integration**: once user accounts exist, link `contributor_id` to user record and surface personal contribution history.
- **Inference quality tuning**: after first 100 concepts are submitted, audit confirmation rate and tune TF-IDF parameters or add synonym expansion.
- **Neo4j projection**: for large-scale traversal and community detection, project `ontology_concepts` + `ontology_relations` into Neo4j (follow-up spec).
- **Moderation**: flagging/review queue for concepts with low resonance or duplicate titles (follow-up spec).
- **Activity digest**: weekly email to contributors showing "your concept reached 5 resonance signals this week" (follow-up; requires email service).
- **Operator CLI**: `cc ontology infer` to manually trigger relation inference for a batch of concepts (useful for backfill after algorithm changes).

---

## Failure / Retry Reflection

- **Failure**: Relation inference never surfaces any related concepts.
  **Blind spot**: Concepts submitted without enough body text (< 50 chars) produce zero TF-IDF signal.
  **Next action**: Add `min_length=50` validation on `body`; add `inference_skipped_reason` field to relation response.

- **Failure**: Garden view returns 500 on first load.
  **Blind spot**: Empty `ontology_domains` table; join produces null rows.
  **Next action**: Seed `ontology_domains` in migration; add null guard in service layer.

- **Failure**: Resonance score never changes.
  **Blind spot**: Idempotency key blocks all updates after first resonate.
  **Next action**: Idempotency should be per-hour window, not lifetime; review constraint scope.

---

## Decision Gates

- **Domain seed set**: Which ~20 initial domain slugs ship with the migration? Needs input from product team before implementation. Suggested: `science, ecology, complexity, mathematics, art, music, philosophy, technology, ai, economics, education, history, literature, social-science, health, engineering, linguistics, spirituality, politics, design`.
- **Inference algorithm**: TF-IDF is specified for MVP. If a team member has a preferred alternative (BM25, simple keyword overlap) that is already available in the Python environment, they may substitute it — but must update the `inferred_by` field value and document the change in the PR.
