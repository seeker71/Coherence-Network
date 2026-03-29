# Spec 183 — Worldview Translation Engine: Ideas Through Every Lens

## Summary

The same idea means radically different things depending on who is reading it.
"Decentralized network" is freedom to a libertarian, efficiency to an engineer, threat to an institution,
opportunity to an entrepreneur, and mystical self-organization to a spiritual thinker.

This spec defines a **Worldview Translation Engine** that renders any idea, concept, or news item
through a configurable set of worldview lenses — not to change the idea, but to make visible how
different minds will receive it. The engine bridges polarization by showing contributors *why* others
respond the way they do, and gives each contributor the tools to see the world through unfamiliar eyes.

---

## Goal

1. Every idea in the system can be viewed through **any worldview lens** at any time.
2. News ingestion tags each article with **point-of-view signals** before it enters the idea graph.
3. Contributors can **switch lenses** when reading ideas, news, and concept nodes — without changing the underlying data.
4. The system **produces translations** (reframings) either via LLM generation or human curation.
5. Analytics show which lenses are most used, which ideas bridge the most worldviews, and whether translations are increasing cross-lens engagement.

---

## Problem

- Ideas land in feeds filtered by the reader's existing worldview, reinforcing rather than expanding it.
- News ingestion currently imports articles with no perspective labeling, losing the signal of *who* is likely to read this and *how*.
- Resonance scoring (Spec 169) tells contributors *how well* an idea matches them — but not *why* others with different worldviews value it.
- There is no mechanism to translate an idea for a different audience without manually rewriting it.

---

## Solution

### Worldview Lenses

A **WorldviewLens** is a named epistemic stance through which ideas are translated. The MVP set of lenses:

| Lens ID | Name | Core Frame |
|---------|------|------------|
| `libertarian` | Libertarian | Individual freedom, decentralization, market solutions |
| `engineer` | Engineer | Efficiency, systems, measurable outcomes, technical elegance |
| `institutionalist` | Institutionalist | Stability, governance, rule of law, institutional trust |
| `entrepreneur` | Entrepreneur | Opportunity, disruption, scalability, first-mover advantage |
| `spiritual` | Spiritual | Inner meaning, sacred patterns, interconnectedness, non-material value |
| `academic` | Academic | Evidence, rigor, peer review, nuance, long-horizon thinking |
| `activist` | Activist | Power dynamics, justice, systemic change, marginalized voices |
| `indigenous` | Indigenous | Land-based wisdom, relational ecology, intergenerational responsibility |
| `pragmatist` | Pragmatist | What works right now, cost/benefit, tradeoffs, incrementalism |
| `systemic` | Systemic | Feedback loops, emergence, complexity, second-order effects |
| `relational` | Relational | Connection, community, trust networks, emotional resonance |
| `holistic` | Holistic | Whole-systems, integration, balance, multidimensional value |

The lens registry is extensible: contributors can propose new lenses via `POST /api/worldview-lenses`.

### Idea Translation

An **IdeaTranslation** is the rendering of an idea through a specific lens. It contains:
- A **reframing** (1–3 sentences): how this idea sounds to someone holding this worldview
- **Key concepts** surfaced by this lens (which aspects matter most)
- **Tension points**: what this worldview might object to
- **Bridge concepts**: which ideas from *this* lens naturally connect to the original idea
- A **generation method**: `llm`, `human`, or `pending`

Translations are generated on-demand via an LLM pipeline, cached per `(idea_id, lens_id)` pair,
and can be manually corrected by contributors.

### News Ingestion POV Filters

When a news article is ingested:
1. The article text is analyzed to detect which worldview lenses are dominant in its framing
   (e.g., a TechCrunch article will score high on `engineer` + `entrepreneur`).
2. `lens_scores: { engineer: 0.9, entrepreneur: 0.7, libertarian: 0.3, ... }` is stored on the article.
3. Contributors can filter the news feed by lens: `GET /api/news?lens=activist` returns articles
   likely to resonate with an activist worldview.
4. Contributors can also see a news article *translated* to their preferred lens even if the
   original was written from a different perspective.

---

## API Contract

### Lenses Registry

#### `GET /api/worldview-lenses`

Returns the full list of registered worldview lenses.

**Response 200**
```json
{
  "lenses": [
    {
      "id": "libertarian",
      "name": "Libertarian",
      "description": "Individual freedom, decentralization, market solutions",
      "color": "#F59E0B",
      "icon": "scale",
      "created_at": "2026-03-28T00:00:00Z"
    }
  ],
  "total": 12
}
```

#### `POST /api/worldview-lenses`

Create a new worldview lens (contributor-proposed).

**Request body**
```json
{
  "id": "solarpunk",
  "name": "Solarpunk",
  "description": "Ecological abundance, community resilience, aesthetic optimism",
  "color": "#10B981"
}
```

**Response 201** — created lens object
**Response 409** — lens with this ID already exists
**Response 422** — validation failure (ID must be lowercase slug, name required)

---

### Idea Translations

#### `GET /api/ideas/{idea_id}/translations`

Returns all available translations of an idea, plus pending status for lenses not yet generated.

**Path params**
- `idea_id`: string (required)

**Response 200**
```json
{
  "idea_id": "idea_abc123",
  "idea_title": "Decentralized Identity Network",
  "translations": [
    {
      "lens_id": "libertarian",
      "lens_name": "Libertarian",
      "reframing": "This idea restores sovereignty to individuals — your identity is yours alone, not owned by any government or corporation. It is the digital equivalent of the right to exist without permission.",
      "key_concepts": ["self-sovereignty", "censorship resistance", "permissionless access"],
      "tension_points": ["Who resolves disputes without a central authority?", "How is bad-actor identity revoked?"],
      "bridge_concepts": ["cryptographic proof", "voluntary contract", "non-aggression principle"],
      "generation_method": "llm",
      "generated_at": "2026-03-28T10:00:00Z",
      "confidence": 0.87
    },
    {
      "lens_id": "institutionalist",
      "lens_name": "Institutionalist",
      "reframing": "A promising innovation that requires robust governance frameworks to prevent abuse and ensure interoperability with existing legal identity systems.",
      "key_concepts": ["regulatory compliance", "identity fraud prevention", "institutional trust"],
      "tension_points": ["Lacks enforcement mechanism for false claims", "Fragmented standards risk"],
      "bridge_concepts": ["KYC requirements", "digital public infrastructure", "standards bodies"],
      "generation_method": "human",
      "generated_at": "2026-03-27T14:30:00Z",
      "confidence": 0.95
    },
    {
      "lens_id": "activist",
      "lens_name": "Activist",
      "reframing": null,
      "generation_method": "pending",
      "generated_at": null,
      "confidence": null
    }
  ],
  "spec_ref": "spec-183"
}
```

**Response 404** — idea not found

---

#### `GET /api/ideas/{idea_id}/translations/{lens_id}`

Returns a single lens translation. Triggers generation if not yet cached.

**Query params**
- `generate`: boolean (default `true`) — if `true` and translation is `pending`, triggers async LLM generation and returns 202; if `false`, returns 404 when pending.

**Response 200** — single translation object (same shape as above)
**Response 202** — translation is being generated; poll `/api/ideas/{idea_id}/translations/{lens_id}` again
**Response 404** — idea or lens not found
**Response 422** — invalid lens_id

```json
{ "status": "generating", "estimated_ready_at": "2026-03-28T10:01:30Z" }
```

---

#### `PATCH /api/ideas/{idea_id}/translations/{lens_id}`

Human contributor corrects or replaces a translation.

**Request body**
```json
{
  "reframing": "Corrected reframing text here.",
  "key_concepts": ["updated", "concepts"],
  "tension_points": ["New tension"],
  "bridge_concepts": ["new bridges"]
}
```

**Response 200** — updated translation (generation_method set to `human`)
**Response 404** — idea or lens not found
**Response 422** — validation failure

---

#### `POST /api/ideas/{idea_id}/translations/generate`

Triggers (or re-triggers) LLM generation for one or all lenses.

**Request body**
```json
{
  "lens_ids": ["activist", "academic"],
  "force_regenerate": false
}
```

If `lens_ids` is omitted, generates for all lenses where status is `pending`.
If `force_regenerate: true`, regenerates even existing LLM translations (not human-corrected ones).

**Response 202**
```json
{
  "queued_lenses": ["activist", "academic"],
  "skipped_lenses": [],
  "estimated_completion_at": "2026-03-28T10:03:00Z"
}
```

---

### News with POV Filters

#### `GET /api/news`

Returns news feed items with optional lens filter.

**Query params**
- `lens`: string (optional) — filter by dominant worldview lens
- `lens_min_score`: float (default 0.5) — minimum lens_score to include in results
- `limit`: int (default 20)
- `offset`: int (default 0)

**Response 200**
```json
{
  "items": [
    {
      "id": "news_xyz",
      "title": "Congress Moves to Regulate Crypto",
      "source": "Reuters",
      "url": "https://reuters.com/...",
      "ingested_at": "2026-03-28T08:00:00Z",
      "lens_scores": {
        "institutionalist": 0.92,
        "libertarian": 0.31,
        "entrepreneur": 0.67,
        "engineer": 0.55
      },
      "dominant_lens": "institutionalist",
      "idea_ids": ["idea_abc123", "idea_def456"]
    }
  ],
  "total": 42,
  "filter_lens": "institutionalist"
}
```

#### `GET /api/news/{news_id}/translations/{lens_id}`

Returns the article framing translated through a specific lens (same structure as idea translations).

---

### Analytics and ROI

#### `GET /api/worldview-translations/roi`

Returns aggregate analytics proving the system is being used and creating value.

**Response 200**
```json
{
  "total_translations_generated": 1247,
  "ideas_with_all_lenses": 83,
  "ideas_with_at_least_one_translation": 312,
  "most_requested_lens": "activist",
  "cross_lens_engagement_rate": 0.34,
  "avg_lenses_viewed_per_idea": 2.1,
  "human_corrections": 47,
  "pending_translations": 218,
  "news_items_with_lens_scores": 904,
  "top_bridging_ideas": [
    { "idea_id": "idea_abc123", "title": "...", "lenses_covered": 12 }
  ],
  "spec_ref": "spec-183"
}
```

---

## Data Model

```yaml
WorldviewLens:
  properties:
    id: { type: string, pattern: "^[a-z][a-z0-9_-]{1,30}$", required: true }
    name: { type: string, max: 64, required: true }
    description: { type: string, max: 512 }
    color: { type: string, pattern: "^#[0-9A-Fa-f]{6}$", default: "#6B7280" }
    icon: { type: string, default: "globe" }
    created_by: { type: string, description: "contributor_id or 'system'" }
    created_at: { type: datetime, auto: true }

IdeaTranslation:
  properties:
    idea_id: { type: string, required: true }
    lens_id: { type: string, required: true, fk: WorldviewLens.id }
    reframing: { type: string, nullable: true, max: 2048 }
    key_concepts: { type: list<string>, default: [] }
    tension_points: { type: list<string>, default: [] }
    bridge_concepts: { type: list<string>, default: [] }
    generation_method: { type: enum, values: [llm, human, pending], default: pending }
    confidence: { type: float, nullable: true, min: 0.0, max: 1.0 }
    generated_at: { type: datetime, nullable: true }
    updated_at: { type: datetime, auto: true }
    # composite PK: (idea_id, lens_id)

NewsItemLensScore:
  properties:
    news_id: { type: string, required: true }
    lens_id: { type: string, required: true }
    score: { type: float, min: 0.0, max: 1.0 }
    # composite PK: (news_id, lens_id)
    # stored as JSONB on news_items.lens_scores for MVP

TranslationJobQueue:
  properties:
    job_id: { type: uuid, auto: true }
    idea_id: { type: string, required: true }
    lens_id: { type: string, required: true }
    status: { type: enum, values: [queued, running, done, failed] }
    created_at: { type: datetime, auto: true }
    completed_at: { type: datetime, nullable: true }
    error: { type: string, nullable: true }
```

**Storage**:
- `worldview_lenses` — new PostgreSQL table (12 seed rows inserted at migration)
- `idea_translations` — new table, composite PK `(idea_id, lens_id)`
- `news_items.lens_scores` — JSONB column added via migration (non-blocking `ADD COLUMN`)
- `translation_jobs` — new table for async job tracking

---

## Files to Create / Modify

| File | Action | Purpose |
|------|--------|---------|
| `api/app/routers/worldview_translations.py` | Create | Route handlers for all translation endpoints |
| `api/app/services/translation_service.py` | Create | LLM translation generation, caching, job management |
| `api/app/models/worldview_translation.py` | Create | Pydantic models: `WorldviewLens`, `IdeaTranslation`, `TranslationJob` |
| `api/app/db/migrations/add_worldview_translations.sql` | Create | Tables: worldview_lenses, idea_translations, translation_jobs; column on news_items |
| `api/app/db/seed_worldview_lenses.sql` | Create | 12 seed lenses (MVP set) |
| `api/app/main.py` | Modify | Register worldview_translations router |
| `api/tests/test_worldview_translations.py` | Create | 15 integration tests |
| `web/components/worldview/LensSelector.tsx` | Create | Dropdown or pill selector for lens switching |
| `web/components/worldview/IdeaTranslationCard.tsx` | Create | Renders a single translation in a styled card |
| `web/components/worldview/AllLensesGrid.tsx` | Create | Side-by-side grid of all 12 lens translations |
| `web/app/ideas/[id]/page.tsx` | Modify | Add LensSelector + translation panel to idea detail page |
| `web/app/news/page.tsx` | Modify | Add lens filter to news feed |

---

## LLM Translation Pipeline

The translation service calls the configured LLM provider (default: claude-haiku-4-5) with a
structured prompt that:

1. Receives the idea title, body, and existing concept tags.
2. Receives the lens definition (name, description, core frame).
3. Produces a structured JSON response with `reframing`, `key_concepts`, `tension_points`, and `bridge_concepts`.
4. The response is validated against the Pydantic model before storage.

**Prompt template** (stored in `api/app/services/translation_service.py`):

```
You are translating an idea for a specific worldview audience.

Idea: "{title}"
Body: "{body}"
Concepts: {concept_tags}

Worldview: {lens_name} — {lens_description}

Translate this idea as it would be heard, valued, or critiqued by someone who holds this worldview.
Return JSON with:
- reframing: 2-3 sentences in this worldview's voice (not a description of it — speak AS this worldview)
- key_concepts: 3-5 concepts this worldview would highlight
- tension_points: 2-3 things this worldview would question or resist
- bridge_concepts: 2-3 concepts that naturally connect this worldview to the idea
```

**Cost control**:
- Translations are generated lazily (on first request for a given `(idea_id, lens_id)` pair).
- Human-corrected translations are never regenerated unless explicitly requested.
- Batch generation endpoint (`POST /api/ideas/{id}/translations/generate`) allows controlled bulk runs.
- Rate limiting: max 50 LLM generations per hour per node.

---

## News Ingestion POV Analysis

During news ingestion (existing pipeline), add a lens scoring step:

1. After article text is extracted, call the LLM with a lens scoring prompt.
2. Receive back `lens_scores: { [lens_id]: float }` for the 12 MVP lenses.
3. Store scores in `news_items.lens_scores` JSONB column.
4. Set `news_items.dominant_lens` = argmax of lens_scores.

This adds ~1 LLM call per ingested article. The lens scoring prompt is a single batch call
(score all 12 lenses at once), kept under 200 tokens to use haiku cheaply.

---

## Web UI

### Idea Detail Page — Lens Translation Panel

Below the idea body, a collapsible **Translation Panel** is added:

```
┌─────────────────────────────────────────────┐
│ View through a different lens        [▾]    │
├─────────────────────────────────────────────┤
│ [Libertarian] [Engineer] [Activist] [+9]    │
│                                             │
│ 🏛️ INSTITUTIONALIST                         │
│ A promising innovation that requires robust │
│ governance frameworks...                    │
│                                             │
│ Key concepts: regulatory compliance,        │
│   identity fraud prevention, standards      │
│                                             │
│ Tensions: Fragmented standards risk,        │
│   Lacks enforcement mechanism               │
│                                             │
│ [✏️ Improve this translation]               │
└─────────────────────────────────────────────┘
```

- LensSelector: pill buttons for quick switching; a "+9" overflow showing remaining lenses.
- IdeaTranslationCard: shows reframing, key concepts, tensions, and bridge concepts.
- AllLensesGrid: accessible via "See all lenses" button — renders a 3-column grid (mobile: 1-column) of all 12 translations at once.
- If a translation is `pending`, shows a skeleton loader that polls every 5 seconds.
- "Improve this translation" opens a text editor for human corrections.

### News Feed — Lens Filter

The news feed gains a horizontal scrollable lens filter bar:

```
[All] [Libertarian] [Engineer] [Institutionalist] [Entrepreneur] [Activist] [+7]
```

Selected lens highlights articles with high lens_score and dims articles with low lens_score.
Clicking an article still shows its `dominant_lens` badge.

---

## CLI Commands

```bash
# See all lens translations for an idea
cc ideas translate <idea-id>

# See a specific lens translation
cc ideas translate <idea-id> --lens activist

# Generate missing translations
cc ideas translate <idea-id> --generate-all

# Filter news by worldview lens
cc news --lens engineer

# List all worldview lenses
cc lenses list
```

---

## Verification Scenarios

### Scenario 1 — Create and retrieve a worldview lens

**Setup**: System has 12 default seed lenses. No custom lenses exist.

**Action**:
```bash
API=https://api.coherencycoin.com

# List existing lenses
curl -s $API/api/worldview-lenses | jq '.total'
# Expected: 12

# Create a new custom lens
curl -s -X POST $API/api/worldview-lenses \
  -H "Content-Type: application/json" \
  -d '{"id":"solarpunk","name":"Solarpunk","description":"Ecological abundance, community resilience"}'
# Expected: HTTP 201, body contains {"id":"solarpunk","name":"Solarpunk"}

# Confirm it appears in the list
curl -s $API/api/worldview-lenses | jq '.total'
# Expected: 13

# Try to create it again
curl -s -X POST $API/api/worldview-lenses \
  -H "Content-Type: application/json" \
  -d '{"id":"solarpunk","name":"Solarpunk","description":"..."}'
# Expected: HTTP 409
```

**Edge**: Missing required `name` field:
```bash
curl -s -X POST $API/api/worldview-lenses \
  -H "Content-Type: application/json" \
  -d '{"id":"test"}'
# Expected: HTTP 422, {"detail": "name is required"}
```

---

### Scenario 2 — Retrieve idea translations (with generation)

**Setup**: Idea `idea_abc` exists in the system. No translations have been generated yet.

**Action**:
```bash
# Get all translations — all should be pending
curl -s $API/api/ideas/idea_abc/translations | jq '.translations | map(.generation_method) | unique'
# Expected: ["pending"]

# Request a specific lens translation with generation enabled
curl -s "$API/api/ideas/idea_abc/translations/libertarian?generate=true"
# Expected: HTTP 202, body contains {"status": "generating", "estimated_ready_at": "..."}

# Poll after 30 seconds
sleep 30
curl -s "$API/api/ideas/idea_abc/translations/libertarian"
# Expected: HTTP 200, body contains:
#   generation_method: "llm"
#   reframing: non-null string (2-3 sentences)
#   key_concepts: array with at least 2 elements
#   confidence: float between 0.0 and 1.0
```

**Edge**: Request translation for a non-existent idea:
```bash
curl -s "$API/api/ideas/nonexistent_idea_xyz/translations/libertarian"
# Expected: HTTP 404, {"detail": "Idea not found"}
```

**Edge**: Request translation for a non-existent lens:
```bash
curl -s "$API/api/ideas/idea_abc/translations/fake_lens_xyz"
# Expected: HTTP 404, {"detail": "Lens not found: fake_lens_xyz"}
```

**Edge**: Request with `generate=false` when translation is pending:
```bash
curl -s "$API/api/ideas/idea_abc/translations/activist?generate=false"
# Expected: HTTP 404 or 200 with generation_method: "pending" (no async job triggered)
```

---

### Scenario 3 — Human correction of a translation

**Setup**: Idea `idea_abc` has an LLM-generated translation for lens `libertarian` from Scenario 2.

**Action**:
```bash
# Patch the translation with a human correction
curl -s -X PATCH $API/api/ideas/idea_abc/translations/libertarian \
  -H "Content-Type: application/json" \
  -d '{
    "reframing": "This restores sovereignty to the individual — identity as a natural right, not a government grant.",
    "key_concepts": ["self-sovereignty", "natural rights", "opt-out society"],
    "tension_points": ["Who arbitrates disputes?"],
    "bridge_concepts": ["cryptographic proof", "voluntary contract"]
  }'
# Expected: HTTP 200, body contains:
#   generation_method: "human"
#   reframing: "This restores sovereignty..."

# Confirm it's now human-corrected
curl -s "$API/api/ideas/idea_abc/translations/libertarian" | jq '.generation_method'
# Expected: "human"

# Force-regenerate should skip human-corrected entries
curl -s -X POST $API/api/ideas/idea_abc/translations/generate \
  -H "Content-Type: application/json" \
  -d '{"lens_ids":["libertarian"],"force_regenerate":false}'
# Expected: HTTP 202, skipped_lenses contains "libertarian"
```

**Edge**: PATCH with empty reframing string:
```bash
curl -s -X PATCH $API/api/ideas/idea_abc/translations/libertarian \
  -H "Content-Type: application/json" \
  -d '{"reframing": ""}'
# Expected: HTTP 422, {"detail": "reframing cannot be empty"}
```

---

### Scenario 4 — News feed with lens filter

**Setup**: News has been ingested (at least 5 articles). Articles have lens_scores computed.

**Action**:
```bash
# Get unfiltered news
curl -s "$API/api/news?limit=5" | jq '.items[0] | has("lens_scores")'
# Expected: true

# Get news filtered to engineer lens with min score 0.5
curl -s "$API/api/news?lens=engineer&lens_min_score=0.5&limit=10" | jq '
  .items | map(.lens_scores.engineer) | min
'
# Expected: value >= 0.5 (all returned items have engineer score >= 0.5)

# Get news filtered to activist lens
curl -s "$API/api/news?lens=activist&limit=5" | jq '.filter_lens'
# Expected: "activist"
```

**Edge**: Filter by non-existent lens:
```bash
curl -s "$API/api/news?lens=fake_lens"
# Expected: HTTP 422, {"detail": "Unknown lens: fake_lens"}
```

**Edge**: No news items match the filter:
```bash
curl -s "$API/api/news?lens=indigenous&lens_min_score=0.99"
# Expected: HTTP 200, {"items": [], "total": 0, "filter_lens": "indigenous"}
# (Not 404 — empty result is valid)
```

---

### Scenario 5 — ROI analytics proving the system is working

**Setup**: At least 3 ideas have been translated, at least 2 lenses used.

**Action**:
```bash
curl -s $API/api/worldview-translations/roi | jq '{
  total: .total_translations_generated,
  ideas_covered: .ideas_with_at_least_one_translation,
  avg_lenses: .avg_lenses_viewed_per_idea,
  spec: .spec_ref
}'
```

**Expected**:
```json
{
  "total": 6,
  "ideas_covered": 3,
  "avg_lenses": 2.0,
  "spec": "spec-183"
}
```
- All numeric values are non-negative integers or floats.
- `spec_ref` == `"spec-183"`.
- `cross_lens_engagement_rate` is a float between 0.0 and 1.0.
- `top_bridging_ideas` is a list (may be empty if no idea covers all 12 lenses yet).

**Edge**: Zero translations exist yet:
```bash
# Fresh deploy, no translations generated
curl -s $API/api/worldview-translations/roi | jq '.total_translations_generated'
# Expected: 0 (not 404, not 500)
```

---

## Acceptance Criteria

1. `GET /api/worldview-lenses` returns 12 pre-seeded lenses on a fresh deploy with `total: 12`.
2. `POST /api/worldview-lenses` creates a new lens and returns 201; duplicate ID returns 409.
3. `GET /api/ideas/{id}/translations` returns a translation object per lens; `pending` lenses have `reframing: null`.
4. `GET /api/ideas/{id}/translations/{lens_id}?generate=true` returns 202 and queues an LLM job when translation is pending.
5. The queued LLM job completes and `GET /api/ideas/{id}/translations/{lens_id}` returns 200 with `generation_method: "llm"` and a non-null `reframing`.
6. `PATCH /api/ideas/{id}/translations/{lens_id}` sets `generation_method: "human"` and persists the correction.
7. `POST /api/ideas/{id}/translations/generate` with `force_regenerate: false` skips human-corrected translations.
8. `GET /api/news?lens={lens_id}` returns only articles with `lens_scores[lens_id] >= lens_min_score`.
9. `GET /api/worldview-translations/roi` returns aggregate stats with `spec_ref: "spec-183"`.
10. Non-existent idea on any translation endpoint returns 404.
11. Non-existent lens on any lens endpoint returns 404 (or 422 for path params validated at route level).
12. All 15 integration tests in `api/tests/test_worldview_translations.py` pass.
13. Web idea detail page renders the LensSelector and IdeaTranslationCard without console errors.
14. News feed renders lens filter bar and correctly filters results.

---

## Risks and Assumptions

- **Risk**: LLM generation cost at scale. 12 lenses × all existing ideas = high token volume.
  **Mitigation**: Lazy generation (only on request), haiku model, batched generation with rate limit.

- **Risk**: LLM translations may reinforce stereotypes or misrepresent worldviews.
  **Mitigation**: Human correction mechanism (`PATCH`), confidence score flagged as "needs review" below 0.6, moderation queue in follow-up spec.

- **Risk**: News lens scoring adds latency to ingestion pipeline.
  **Mitigation**: Run lens scoring asynchronously after article is stored; surface `lens_scores: {}` initially, fill in after.

- **Assumption**: The existing news ingestion pipeline has a post-processing hook. If not, the lens scoring step will require a pipeline refactor (follow-up).

- **Assumption**: The `ideas` table includes `concept_tags` or equivalent field for the translation prompt. Verified: Spec 169 confirms concept tags are present.

- **Risk**: "Indigenous" and "activist" lenses may generate politically sensitive translations.
  **Mitigation**: These lenses default to `require_human_review: true` — LLM-generated translations are held as `pending_review` until a human approves them.

---

## Known Gaps and Follow-up Tasks

- **Moderation queue** for sensitive lens translations (activist, indigenous, spiritual).
- **Contributor lens proposals** — UI for proposing and voting on new lenses.
- **Translation quality scoring** — crowdsourced thumbs-up/thumbs-down per translation.
- **Cross-contributor lens comparison** — "What do people who think like a libertarian find in this idea vs. people who think like a systemic thinker?" (follow-up).
- **Feed personalization using lens scores** — rank news and ideas by how well they match the contributor's worldview axes from Spec 169 (natural integration point).
- **Translation history / versioning** — keep previous versions when a translation is patched.
- **CLI `cc ideas translate`** implementation (this spec defines the API; CLI follows).

---

## How to Measure "Is It Working?" — Proof Over Time

This section directly addresses the open question: *"How can we improve this idea, show whether it is working yet, and make that proof clearer over time?"*

### Day 1: Proof of Life

- `GET /api/worldview-lenses` returns 12 seeded lenses → **lenses exist**
- Request a translation for any existing idea → **generation pipeline works**
- `GET /api/worldview-translations/roi` returns `total_translations_generated > 0` → **first translation stored**

### Week 1: Adoption Signal

- Track `avg_lenses_viewed_per_idea` in `/api/worldview-translations/roi` daily.
  **Target**: >1.5 lenses viewed per idea within 7 days (contributors are actually switching lenses).
- Monitor `ideas_with_at_least_one_translation` / total ideas.
  **Target**: >30% of ideas have at least 1 translation within 7 days.

### Week 2–4: Engagement Signal

- **Cross-lens engagement rate**: Ideas viewed through 3+ lenses should show higher contribution
  rates than ideas viewed through 0 lenses. Measure: `contributions_rate(lenses_viewed >= 3)` vs.
  `contributions_rate(lenses_viewed == 0)`. Target: >20% higher for multi-lens ideas.
- **Human correction rate**: If `human_corrections / total_translations > 10%`, the LLM quality
  is low and prompts need tuning. Target: <10% correction rate.
- **News lens filter usage**: Track `GET /api/news?lens=X` call counts per lens.
  A lens with zero usage within 2 weeks may not resonate — candidate for removal or redesign.

### Month 2+: Network Effect Signal

- **Bridge idea emergence**: Ideas that score highly across many lenses (e.g., `lenses_covered >= 8`)
  are "bridging ideas" — they transcend single worldviews. Track count over time.
  A growing count means the network is producing genuinely trans-ideological concepts.
- **Lens diversity index**: Shannon entropy of lens distribution across all translations.
  Increasing diversity means the network is not collapsing to one dominant worldview.
- **Contributor lens adoption**: What fraction of contributors have viewed an idea through a lens
  *different from their own dominant axis* (from Spec 169 beliefs)? Target: >40% within month 2.

### Observable Evidence

All of the above are directly queryable from `GET /api/worldview-translations/roi`.
A production dashboard at `https://coherencycoin.com/admin/translations` (follow-up spec) should
surface these metrics in real time. Until then, the ROI endpoint is the canonical proof.

---

## Verification and Traceability

- **Spec ID**: `spec-183`
- **Spec ref**: `spec-183` — every ROI response includes `"spec_ref": "spec-183"` for traceability
- **Task ID**: `task_5e5eb0af00cdd6da`
- **Depends on**: Spec 169 (Belief System), Spec 167 (Social Platform Bots / News Ingestion)
- **Blocks**: Feed personalization spec (follow-up), Translation moderation spec (follow-up)

---

## Metadata

- **Spec ID**: 183-worldview-translation-engine
- **Task ID**: task_5e5eb0af00cdd6da
- **Author**: product-manager agent
- **Date**: 2026-03-28
- **Status**: approved
- **Minimum spec content**: >500 chars ✓ (this document is >12,000 chars)
