# Spec 181 — Concept Translation: Idea Lens Views Across Worldviews

## Summary

Every idea carries a different meaning depending on who is reading it. "Decentralized
network" means freedom to a libertarian, efficiency to an engineer, a competitive threat to
an institution, and an untapped market to an entrepreneur. This spec defines a **translation
layer** that renders any idea through multiple named worldview lenses — not to change the
idea but to reveal how different epistemic standpoints interpret the same concept.

The output is an `IdeaTranslation` object per lens: a one-paragraph reframing, a resonance
score (how much the lens cares about this idea), and a list of key concepts surfaced by that
lens. News ingestion gains custom point-of-view filters so incoming articles are tagged with
the lens(es) most relevant to them. Every idea becomes navigable through any worldview from
both the API and the web.

---

## Goal

Make the epistemic diversity of the network visible and navigable. A contributor should be
able to look at any idea and instantly see how a scientist, a spiritual practitioner, a
systems thinker, or a pragmatic builder would read it — and understand where those readings
converge or diverge.

---

## Problem

- Ideas are published as neutral blobs; their meaning is implicitly assumed rather than
  made explicit from multiple perspectives.
- Contributors with different worldviews cannot see which ideas already align with their
  epistemic stance, causing low resonance and shallow engagement.
- News ingestion (spec-154+) produces articles tagged only by topic, not by which worldview
  community each article serves — limiting targeted discovery.
- Without translation scaffolding, bridging across belief systems requires manual effort
  (writing multiple summaries per idea), which is not scalable.

---

## Solution

### Core concepts

A **Lens** is a named worldview filter. Each lens has:
- A name (e.g., `libertarian`, `engineer`, `scientist`, `spiritual`, `entrepreneur`,
  `institutionalist`, `systemic`, `pragmatic`, `holistic`, `relational`)
- A short description of its epistemic stance
- A prompt template used to generate translations
- A set of keywords / concept tags that weight its relevance

A **Translation** is the application of a lens to an idea:
- `lens`: the lens that produced this translation
- `translation_text`: 1–3 sentence reframing of the idea from that lens's perspective
- `resonance_score`: how strongly the lens cares about this idea (0.0–1.0)
- `highlighted_concepts`: list of concept IDs this lens surfaces from the idea
- `divergence_note`: optional short sentence where this lens *conflicts* with the idea as
  stated (e.g., "a libertarian lens resists the implicit centralization in step 3")
- `generated_at`: ISO 8601 UTC timestamp

A **Lens View** on an idea is the collection of all translations available for that idea.

### Architecture

1. **Translation service** (`api/app/services/translation_service.py`) — generates
   translations for a given (idea, lens) pair. Uses an LLM (via existing
   `api/app/services/llm_service.py`) with a per-lens prompt template. Caches results
   in PostgreSQL to avoid recomputation.

2. **Lens registry** (`api/app/config/lenses.json`) — static JSON defining the built-in
   lenses (name, description, stance, keywords). New lenses can be added without code
   changes.

3. **Translation router** (`api/app/routers/translations.py`) — REST endpoints to fetch,
   generate, and list translations.

4. **News POV filter** — extends news ingestion to tag each article with the top-2 lenses
   most relevant to it, based on keyword/concept overlap. Stored in the `news_items` table.

5. **Web lens selector** — a horizontal chip-bar on the idea detail page allowing users
   to switch the "current lens" and see the idea reframed in real time.

---

## Lens Registry (built-in lenses)

```json
[
  {
    "id": "libertarian",
    "name": "Libertarian",
    "stance": "Maximizes individual freedom; distrusts centralized control; values voluntary exchange",
    "keywords": ["freedom", "decentralized", "autonomy", "voluntary", "consent", "property"],
    "prompt_template": "Reframe the following idea from a libertarian perspective that values individual freedom, voluntary cooperation, and skepticism of institutional power. In 2-3 sentences: {idea_text}"
  },
  {
    "id": "engineer",
    "name": "Engineer",
    "stance": "Prioritizes efficiency, reliability, scalability, and measurable outcomes",
    "keywords": ["efficiency", "scalability", "reliability", "system", "performance", "architecture"],
    "prompt_template": "Reframe the following idea from an engineering perspective focused on technical feasibility, system design, and measurable performance. In 2-3 sentences: {idea_text}"
  },
  {
    "id": "scientist",
    "name": "Scientist",
    "stance": "Evidence-based reasoning; falsifiability; peer review; models over intuition",
    "keywords": ["evidence", "hypothesis", "experiment", "data", "falsifiable", "peer-review"],
    "prompt_template": "Reframe the following idea from a scientific perspective emphasizing evidence, testability, and empirical verification. In 2-3 sentences: {idea_text}"
  },
  {
    "id": "entrepreneur",
    "name": "Entrepreneur",
    "stance": "Sees opportunity, market fit, and path to value creation in every idea",
    "keywords": ["market", "opportunity", "revenue", "adoption", "growth", "traction"],
    "prompt_template": "Reframe the following idea from an entrepreneurial perspective focused on market opportunity, adoption paths, and value creation. In 2-3 sentences: {idea_text}"
  },
  {
    "id": "institutionalist",
    "name": "Institutionalist",
    "stance": "Values stability, governance, accountability, and incremental reform",
    "keywords": ["governance", "regulation", "accountability", "compliance", "policy", "stability"],
    "prompt_template": "Reframe the following idea from an institutionalist perspective that values governance, accountability, and stable systemic change. In 2-3 sentences: {idea_text}"
  },
  {
    "id": "spiritual",
    "name": "Spiritual",
    "stance": "Seeks meaning, purpose, connection, and alignment with larger cosmic or moral order",
    "keywords": ["meaning", "purpose", "consciousness", "interconnection", "wisdom", "sacred"],
    "prompt_template": "Reframe the following idea from a spiritual perspective that emphasizes meaning, purpose, and the deeper significance of human connection. In 2-3 sentences: {idea_text}"
  },
  {
    "id": "systemic",
    "name": "Systemic",
    "stance": "Focuses on feedback loops, emergent behavior, and second-order effects",
    "keywords": ["emergence", "feedback", "complexity", "leverage", "interdependence", "nonlinear"],
    "prompt_template": "Reframe the following idea through a systems-thinking lens that highlights feedback loops, emergent properties, and second-order effects. In 2-3 sentences: {idea_text}"
  },
  {
    "id": "pragmatic",
    "name": "Pragmatic",
    "stance": "What works matters more than what's theoretically correct; focus on implementation",
    "keywords": ["practical", "actionable", "implementation", "tradeoff", "realistic", "deliverable"],
    "prompt_template": "Reframe the following idea from a pragmatic perspective focused on what is actionable, realistic, and likely to produce results given current constraints. In 2-3 sentences: {idea_text}"
  }
]
```

---

## Requirements

- [ ] `GET /api/ideas/{id}/translations` returns all cached translations for an idea
- [ ] `GET /api/ideas/{id}/translations/{lens_id}` returns a single lens translation,
      generating it on-demand if not cached
- [ ] `POST /api/ideas/{id}/translations/generate` triggers async generation of translations
      for all lenses (or a subset via `lenses` param)
- [ ] `GET /api/lenses` returns the full lens registry (id, name, stance, keywords)
- [ ] `GET /api/ideas/{id}/translations/compare?lens_a={a}&lens_b={b}` returns both
      translations plus a `divergence_summary` computed from their highlighted concepts
- [ ] News items gain a `top_lenses` array (up to 2 lens IDs) computed at ingest time
- [ ] `GET /api/news?lens={lens_id}` filters news items to those tagged with that lens
- [ ] Translations are cached; a second request for the same (idea, lens) pair returns the
      cached result without re-running the LLM (unless `?force_regenerate=true`)
- [ ] A non-existent idea returns 404 on all translation endpoints
- [ ] An unknown lens_id returns 404 with `detail: "Lens not found"`
- [ ] `resonance_score` is always a float in [0.0, 1.0]
- [ ] All translations include `generated_at` (ISO 8601 UTC)

---

## API Contract

### `GET /api/lenses`

**Response 200**
```json
{
  "lenses": [
    {
      "id": "libertarian",
      "name": "Libertarian",
      "stance": "Maximizes individual freedom; distrusts centralized control",
      "keywords": ["freedom", "decentralized", "autonomy"]
    }
  ],
  "total": 8
}
```

---

### `GET /api/ideas/{id}/translations`

**Path params**
- `id`: idea ID (string)

**Response 200**
```json
{
  "idea_id": "decentralized-network",
  "translations": [
    {
      "lens_id": "libertarian",
      "lens_name": "Libertarian",
      "translation_text": "A decentralized network removes the chokepoint of institutional gatekeepers, allowing individuals to transact and communicate freely without requiring permission.",
      "resonance_score": 0.91,
      "highlighted_concepts": ["autonomy", "voluntary-exchange", "decentralization"],
      "divergence_note": null,
      "generated_at": "2026-03-28T12:00:00Z"
    },
    {
      "lens_id": "engineer",
      "lens_name": "Engineer",
      "translation_text": "A decentralized network eliminates single points of failure and distributes load, improving fault tolerance at the cost of coordination overhead.",
      "resonance_score": 0.78,
      "highlighted_concepts": ["fault-tolerance", "scalability", "latency"],
      "divergence_note": "Byzantine fault tolerance adds significant protocol complexity.",
      "generated_at": "2026-03-28T12:00:00Z"
    }
  ],
  "lenses_missing": ["spiritual", "systemic"],
  "spec_ref": "spec-181"
}
```

**Response 404** — idea not found
```json
{ "detail": "Idea not found" }
```

---

### `GET /api/ideas/{id}/translations/{lens_id}`

**Query params**
- `force_regenerate`: boolean (default false) — bypass cache and regenerate

**Response 200**
```json
{
  "idea_id": "decentralized-network",
  "lens_id": "libertarian",
  "lens_name": "Libertarian",
  "translation_text": "A decentralized network removes the chokepoint of institutional gatekeepers...",
  "resonance_score": 0.91,
  "highlighted_concepts": ["autonomy", "voluntary-exchange"],
  "divergence_note": null,
  "generated_at": "2026-03-28T12:00:00Z",
  "from_cache": true
}
```

**Response 404** — idea not found OR lens not found
```json
{ "detail": "Lens not found" }
```

---

### `POST /api/ideas/{id}/translations/generate`

**Request body** (all optional)
```json
{
  "lenses": ["libertarian", "engineer"],
  "force_regenerate": false
}
```

If `lenses` is omitted, all lenses are generated.

**Response 202** — accepted (async)
```json
{
  "idea_id": "decentralized-network",
  "queued_lenses": ["libertarian", "engineer"],
  "already_cached": ["scientist"],
  "estimated_seconds": 12
}
```

**Response 404** — idea not found
```json
{ "detail": "Idea not found" }
```

---

### `GET /api/ideas/{id}/translations/compare?lens_a={a}&lens_b={b}`

**Response 200**
```json
{
  "idea_id": "decentralized-network",
  "lens_a": { "lens_id": "libertarian", "translation_text": "...", "resonance_score": 0.91 },
  "lens_b": { "lens_id": "institutionalist", "translation_text": "...", "resonance_score": 0.45 },
  "shared_concepts": ["governance", "network"],
  "divergence_concepts": ["autonomy", "regulation"],
  "divergence_summary": "Libertarian lens highlights individual freedom while institutionalist lens focuses on accountability mechanisms — they share concern for network governance but diverge on who holds authority.",
  "convergence_score": 0.31
}
```

**Response 422** — missing lens_a or lens_b

---

### `GET /api/news?lens={lens_id}`

Extends the existing news endpoint with a `lens` filter.

**Response 200** — same structure as current news endpoint; items filtered to those with
`top_lenses` array containing `{lens_id}`.

---

## Data Model

```yaml
Lens:
  properties:
    id: { type: string, unique: true }
    name: { type: string }
    stance: { type: string }
    keywords: { type: list<string> }
    prompt_template: { type: string }

IdeaTranslation:
  table: idea_translations
  properties:
    id: { type: uuid, auto: true }
    idea_id: { type: string, fk: ideas.id }
    lens_id: { type: string }
    translation_text: { type: text }
    resonance_score: { type: float, min: 0.0, max: 1.0 }
    highlighted_concepts: { type: list<string>, stored: jsonb }
    divergence_note: { type: text, nullable: true }
    generated_at: { type: datetime, auto: true }
    model_used: { type: string, nullable: true }
  unique_constraint: [idea_id, lens_id]

# Extends news_items table:
NewsItem.top_lenses: { type: list<string>, stored: jsonb, default: [] }
```

**Storage**: `idea_translations` table in PostgreSQL. Lens registry stored as a static JSON
file (not in DB) to allow fast iteration without migrations.

---

## Files to Create/Modify

- `api/app/routers/translations.py` — route handlers for all translation endpoints
- `api/app/services/translation_service.py` — core translation logic: lens lookup, LLM
  call, cache check/write, resonance scoring, divergence computation
- `api/app/models/translation.py` — Pydantic models: `LensModel`, `IdeaTranslation`,
  `TranslationResponse`, `CompareResponse`, `GenerateRequest`
- `api/app/config/lenses.json` — lens registry (8 built-in lenses)
- `api/app/db/migrations/add_idea_translations_table.sql` — new table + news_items column
- `api/main.py` — register translations router
- `api/tests/test_concept_translation.py` — 14 integration tests
- `web/src/app/ideas/[id]/page.tsx` — add lens selector chip-bar and translation panel
- `web/src/components/translations/LensSelector.tsx` — horizontal scrollable chip row
- `web/src/components/translations/TranslationPanel.tsx` — renders single lens view

---

## Resonance Scoring Algorithm

The `resonance_score` for a (lens, idea) pair is computed as:

```
resonance_score = 0.5 * keyword_overlap + 0.3 * llm_confidence + 0.2 * concept_match
```

Where:
- **keyword_overlap**: Jaccard similarity between lens keywords and idea tags/concept_ids.
  If the idea has no tags, defaults to 0.4 (weak signal).
- **llm_confidence**: Parsed from LLM response metadata (logprob-derived confidence or
  explicit 0–10 rating in structured prompt). Normalized to [0, 1]. If unavailable, 0.5.
- **concept_match**: Fraction of `highlighted_concepts` that exist in the idea's concept
  graph neighbors. Requires concept graph integration; defaults to 0.5 if unavailable.

This scoring is deterministic given the same input and cached with the translation.

---

## News POV Filter

At ingest time (`api/app/services/news_ingest_service.py`), each incoming article is
scored against all 8 lenses via keyword overlap (no LLM call — fast path). The top 2 lens
IDs by score are stored in `news_items.top_lenses`. This enables:

- `GET /api/news?lens=libertarian` — articles flagged as libertarian-relevant
- Contributor home feed filtered by their belief profile's top lens axis (spec-169 extension)

Threshold: only lenses with keyword overlap > 0.15 are included in `top_lenses`. If none
exceed threshold, `top_lenses` is empty.

---

## CLI Commands

```bash
# Translate an idea through all lenses
cc translate <idea-id>

# Translate through a specific lens
cc translate <idea-id> --lens libertarian

# Compare two lenses on an idea
cc translate <idea-id> --compare libertarian institutionalist

# Show available lenses
cc lenses

# Filter news by lens
cc news --lens engineer
```

CLI output for `cc translate <idea-id> --lens libertarian`:
```
Translation — Libertarian lens
Idea: decentralized-network

"A decentralized network removes the chokepoint of institutional gatekeepers,
allowing individuals to transact and communicate freely without permission."

Resonance: ████████████░░  0.91
Highlighted: #autonomy #voluntary-exchange #decentralization
Divergence: none
Generated: 2026-03-28T12:00:00Z (cached)
```

---

## Web UI

**Route**: `/ideas/[id]` (extends existing detail page)

**New components**:
- **LensSelector**: horizontal scrollable chip-bar showing 8 built-in lens names. Active
  chip is highlighted. Clicking a chip switches the visible translation. On mobile: single
  row with horizontal scroll and momentum.
- **TranslationPanel**: card below the idea body showing the active lens's translation_text,
  resonance_score (progress bar), highlighted_concepts (clickable tags), and divergence_note
  (if present). "Compare with another lens" link opens a split-panel view.

**State**: client-side SWR fetch to `/api/ideas/{id}/translations/{lens_id}` on chip
selection. Skeletons shown while loading. "Generate all lenses" button triggers POST
`/api/ideas/{id}/translations/generate` with a loading spinner.

---

## Proof of Working: How to Know It Works Over Time

This section directly addresses the open question: *"How can we improve this idea, show
whether it is working yet, and make that proof clearer over time?"*

### Immediate proof (deploy day)

- `GET /api/lenses` returns 8 lenses with non-empty stances and keywords.
- `GET /api/ideas/{any-idea-id}/translations/{lens_id}` returns a non-empty `translation_text`
  and a `resonance_score` in [0.0, 1.0].
- `GET /api/news?lens=engineer` returns a non-empty list (if news items exist).

### Short-term proof (1 week post-deploy)

- **Translation coverage metric**: track `lenses_missing` count in
  `GET /api/ideas/{id}/translations`. An idea with 0 lenses missing has full coverage.
  Target: >80% of top-50 ideas have full 8-lens coverage within 1 week.
- **Lens popularity**: log which lens chips are clicked most on the web. Top lens reveals
  dominant worldview of active contributors — alignment with contributor belief profiles
  from spec-169 is expected.

### Medium-term proof (1 month)

- **Resonance correlation**: contributors with `worldview_axes.libertarian > 0.7` (spec-169)
  should be more likely to engage with ideas where the libertarian lens has `resonance_score
  > 0.7`. A correlation coefficient > 0.4 shows the translation layer is connecting
  contributor profiles to relevant ideas.
- **Bridge discovery**: track pairs of contributors with divergent lens preferences who
  both engage with the same idea. More bridge engagements = more cross-worldview dialogue.
  Visible in `GET /api/beliefs/roi` (extended) as `cross_lens_engagements`.
- **News lens filter usage**: `GET /api/news?lens=` request count per lens. Growing
  usage means contributors find the filter useful.

### Long-term observability

- A dedicated `GET /api/translations/stats` endpoint (added in this spec) returns:
  - Total translations generated
  - Coverage by idea (% of ideas with ≥1 lens)
  - Top lens by resonance score across all ideas
  - Average resonance score per lens (higher = more ideas align with that lens)
  - Cross-lens divergence distribution (measures worldview spread in the corpus)
- Dashboard card on `/admin/stats` showing these metrics.

---

## Verification Scenarios

### Scenario 1 — Lens registry is navigable

**Setup**: API is running. Lens config file `api/app/config/lenses.json` contains 8 built-in lenses.

**Action**:
```bash
curl -s $API/api/lenses
```

**Expected**: HTTP 200, response contains `{"lenses": [...], "total": 8}`. Each lens has:
`id`, `name`, `stance`, `keywords` (non-empty list). Lenses include `libertarian`,
`engineer`, `scientist`, `entrepreneur`, `institutionalist`, `spiritual`, `systemic`,
`pragmatic`.

**Edge**: request with unknown lens_id in downstream endpoints:
```bash
curl -s $API/api/ideas/some-idea/translations/nonexistent_lens
# Expected: HTTP 404, {"detail": "Lens not found"}
```

---

### Scenario 2 — Single lens translation generated and cached

**Setup**: Idea `decentralized-finance` exists in the database. No translation for it yet.

**Action**:
```bash
# First request — generates translation (LLM call)
curl -s "$API/api/ideas/decentralized-finance/translations/libertarian"
# Second request — returns from cache
curl -s "$API/api/ideas/decentralized-finance/translations/libertarian"
```

**Expected**:
- First response: HTTP 200, `translation_text` is a non-empty string (≥20 chars),
  `resonance_score` in [0.0, 1.0], `from_cache: false`, `generated_at` is an ISO 8601
  timestamp.
- Second response: HTTP 200, same `translation_text` as first, `from_cache: true`.

**Edge** (force regenerate):
```bash
curl -s "$API/api/ideas/decentralized-finance/translations/libertarian?force_regenerate=true"
# Expected: HTTP 200, from_cache: false, new generated_at timestamp
```

---

### Scenario 3 — Full lens coverage via batch generate

**Setup**: Idea `open-source-software` exists. No translations cached.

**Action**:
```bash
# Trigger full generation
curl -s -X POST "$API/api/ideas/open-source-software/translations/generate" \
  -H "Content-Type: application/json" \
  -d '{}'

# Wait ~15 seconds, then check coverage
sleep 15
curl -s "$API/api/ideas/open-source-software/translations"
```

**Expected**:
- POST: HTTP 202, `queued_lenses` contains all 8 lens IDs.
- GET after wait: HTTP 200, `translations` array contains entries for all 8 lenses,
  `lenses_missing` is an empty list `[]`.
- Each translation has `resonance_score` in [0.0, 1.0] and non-empty `translation_text`.

**Edge**: POST to non-existent idea:
```bash
curl -s -X POST "$API/api/ideas/nonexistent-idea/translations/generate" \
  -H "Content-Type: application/json" -d '{}'
# Expected: HTTP 404, {"detail": "Idea not found"}
```

---

### Scenario 4 — Lens comparison reveals divergence

**Setup**: Idea `universal-basic-income` exists with translations for both `libertarian`
and `institutionalist` lenses.

**Action**:
```bash
curl -s "$API/api/ideas/universal-basic-income/translations/compare?lens_a=libertarian&lens_b=institutionalist"
```

**Expected**: HTTP 200, response contains:
- `lens_a.lens_id == "libertarian"`, non-empty `translation_text`
- `lens_b.lens_id == "institutionalist"`, non-empty `translation_text`
- `divergence_summary`: non-empty string (≥20 chars) explaining the tension
- `convergence_score`: float in [0.0, 1.0] (expected to be < 0.5 for these two lenses on UBI)
- `divergence_concepts`: non-empty list of string concept IDs

**Edge**: missing `lens_b` param:
```bash
curl -s "$API/api/ideas/universal-basic-income/translations/compare?lens_a=libertarian"
# Expected: HTTP 422, {"detail": "lens_b is required"}
```

---

### Scenario 5 — News filtered by lens

**Setup**: At least 3 news items exist. News items tagged at ingest time with `top_lenses`.
At least one item has `top_lenses` containing `"engineer"`.

**Action**:
```bash
# All news
curl -s "$API/api/news" | jq '.total'
# Engineer-filtered news
curl -s "$API/api/news?lens=engineer" | jq '.items | length'
# Verify every returned item has engineer in top_lenses
curl -s "$API/api/news?lens=engineer" | jq '.items[].top_lenses | contains(["engineer"])'
```

**Expected**:
- Total ≥ 3.
- Engineer-filtered count ≤ total.
- Every `jq` check returns `true` (no item lacks the `engineer` lens tag).

**Edge**: unknown lens in news filter:
```bash
curl -s "$API/api/news?lens=unknown_lens"
# Expected: HTTP 422, {"detail": "lens 'unknown_lens' is not a valid lens ID"}
```

---

## Task Card

```yaml
goal: Translate any idea through named worldview lenses; news filtered by POV
files_allowed:
  - api/app/routers/translations.py
  - api/app/services/translation_service.py
  - api/app/models/translation.py
  - api/app/config/lenses.json
  - api/app/db/migrations/add_idea_translations_table.sql
  - api/main.py
  - api/tests/test_concept_translation.py
  - web/src/app/ideas/[id]/page.tsx
  - web/src/components/translations/LensSelector.tsx
  - web/src/components/translations/TranslationPanel.tsx
done_when:
  - GET /api/lenses returns 8 lenses
  - GET /api/ideas/{id}/translations/{lens_id} returns translation_text and resonance_score
  - Second call to same endpoint returns from_cache=true
  - POST /api/ideas/{id}/translations/generate returns 202
  - GET /api/ideas/{id}/translations/compare returns divergence_summary
  - GET /api/news?lens=engineer returns only items with engineer in top_lenses
  - GET /api/translations/stats returns coverage and resonance metrics
  - pytest api/tests/test_concept_translation.py — 14/14 pass
  - web page /ideas/{id} shows LensSelector chip-bar without console errors
commands:
  - pytest api/tests/test_concept_translation.py -v
  - cd web && npm run build
constraints:
  - Do not modify existing idea storage logic
  - Lens registry is static JSON — no migration needed for new lenses
  - Translations are always generated by the LLM — never hand-authored
  - resonance_score weights must sum to 1.0
  - Cache invalidation only via force_regenerate=true — never automatic expiry
  - No new external dependencies beyond existing llm_service
```

---

## Risks and Assumptions

- **Assumption**: `api/app/services/llm_service.py` exists and exposes a callable interface
  for text generation. If it does not, the translation service must use the model routing
  layer directly (`api/config/model_routing.json`).
- **Risk**: LLM translation quality is variable. Low-quality translations degrade trust.
  Mitigation: surface `model_used` in response; allow admin regeneration with better model.
- **Risk**: LLM cost per translation. 8 lenses × N ideas = N×8 LLM calls. Mitigation:
  caching is mandatory; generation is lazy (on-demand per lens) not eager (all-at-once).
- **Risk**: Bias in lens templates. Prompt templates are deliberately written from the
  lens's perspective — they will produce biased output by design. This is the feature, not
  a bug. Users must be informed that translations are interpretive, not authoritative.
- **Assumption**: The `news_items` table exists and news ingestion runs via a service layer
  that can be extended with lens scoring.
- **Risk**: News lens scoring (keyword-only, no LLM) may be low quality. Mitigation:
  keyword list per lens is curated; a follow-up spec can upgrade to LLM scoring for top
  news items.

---

## Known Gaps and Follow-up Tasks

- Contributor-personalized lens ordering based on belief profile (spec-169 integration)
- Custom user-defined lenses (allow contributors to add their own lens templates)
- Lens heat map on the ideas list page (which lenses are most active across all ideas)
- Crowd-sourced translation corrections (flag a translation as inaccurate)
- `GET /api/contributors/{id}/translations` — all translations generated by a contributor's
  most resonant lenses
- Translation quality scoring (crowd upvotes/downvotes on specific translations)
- Multi-language support (translate ideas into human languages too — separate spec)

---

## Verification

### What evidence proves this is realized

1. **API**: `curl https://api.coherencycoin.com/api/lenses` returns 8 lenses.
2. **Translation**: `curl https://api.coherencycoin.com/api/ideas/{id}/translations/libertarian`
   returns a non-empty `translation_text` for any valid idea ID.
3. **Compare**: `curl https://api.coherencycoin.com/api/ideas/{id}/translations/compare?lens_a=libertarian&lens_b=engineer`
   returns non-empty `divergence_summary`.
4. **News filter**: `curl https://api.coherencycoin.com/api/news?lens=engineer` returns
   fewer items than the unfiltered endpoint with every item containing `"engineer"` in
   `top_lenses`.
5. **Stats**: `curl https://api.coherencycoin.com/api/translations/stats` returns non-zero
   `total_translations` and `coverage_pct`.
6. **Web**: Navigate to `https://coherencycoin.com/ideas/{any-id}` — a horizontal lens
   chip-bar is visible and clicking "Engineer" changes the translation panel content.

All six can be independently verified by any party with network access to the production API.

---

## Research Inputs

- `2026-03-28` — Spec 169 (Belief System) — defines `BeliefAxis` enum and per-contributor
  worldview profiles; this spec extends that model to ideas
- `2026-03-28` — Coherence Network task brief (this document) — provides the concept
  translation framing and open questions
- `2025-01-01` — [Framing Effect (Wikipedia)](https://en.wikipedia.org/wiki/Framing_effect_(psychology)) —
  same information has different effects depending on presentation frame
- `2024-09-01` — Living Codex `UserConceptModule` — internal origin pattern for
  per-user concept resonance and belief stances

---

## Metadata

- **Spec ID**: 181-concept-translation-worldview-lenses
- **Task ID**: task_da25944846b7bb45
- **Author**: product-manager agent
- **Date**: 2026-03-28
- **Status**: draft
- **Depends on**: Spec 169 (Belief System), news ingestion pipeline
- **Blocks**: personalized idea feed (follow-up), cross-lens bridge discovery (follow-up)
