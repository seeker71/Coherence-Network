# Spec 182 — Worldview Translation: Ideas Through Every Lens

**Spec ID**: 182-worldview-translation
**Task ID**: task_3a5c59a84394e17a
**Status**: approved
**Priority**: high
**Author**: product-manager agent
**Date**: 2026-03-28
**Depends on**: Spec 169 (Belief System), Spec 163 (Resonance Navigation), Spec 008 (Graph Foundation)
**Blocks**: personalized news feed with POV filter (follow-up)

---

## Summary

The same idea means different things to different people. A decentralized network means
**freedom** to a libertarian, **efficiency** to an engineer, **threat** to an institution,
**opportunity** to an entrepreneur. The system already translates ideas through five
epistemological lenses (scientific, economic, spiritual, artistic, philosophical). This spec
extends translation to cover **social, political, and role-based worldviews** — the kinds
of perspectives that shape how real people interpret real news and real proposals.

The goal is not to change ideas or to argue which worldview is correct. It is to make
visible how the same kernel of truth refracts through different belief systems, so contributors
can see their own perspective alongside others — and find the connections between them.

---

## Problem

1. **Five lenses are not enough.** The existing `TranslateLens` enum covers abstract
   epistemological categories. It cannot represent how a politician, a parent, an engineer,
   or a farmer actually reads an idea. Real discourse happens across social and role-based
   axes, not just philosophical ones.

2. **No side-by-side view.** There is no endpoint that returns all worldview framings of
   an idea at once. Seeing one lens at a time hides the connections between perspectives.

3. **News lacks POV filters.** News ingestion currently produces generic summaries. There
   is no mechanism to reframe a news article through a contributor's stated worldview before
   surfacing it, reducing relevance and engagement.

4. **Bridges are invisible.** Even when two people disagree on an idea, they may agree on
   underlying values surfaced through different worldviews. The system cannot currently show
   these connection points — the "common ground map."

5. **Proof of value is unmeasured.** There is no endpoint or metric showing whether
   worldview translation actually helps contributors understand each other better or engage
   more deeply with ideas outside their primary worldview.

---

## Solution

### 1. Extended Worldview Registry

Add a `WorldviewLens` enum extending `TranslateLens` with social/role/political perspectives.
The union of both is called the **full worldview registry**.

New lenses to add:

| Lens | Description |
|------|-------------|
| `libertarian` | Values individual freedom, voluntary exchange, minimal coercion; sees ideas through the lens of who controls what and whether force is involved. |
| `institutionalist` | Values stable rules, established procedures, and collective continuity; sees ideas through risk to existing structures and legitimacy. |
| `entrepreneurial` | Values opportunity, disruption, speed-to-market, and asymmetric upside; sees ideas through "what market does this create?" |
| `engineer` | Values correctness, composability, measurability, and implementation feasibility; sees ideas through "can this be built and verified?" |
| `communitarian` | Values shared identity, mutual obligation, and community flourishing; sees ideas through impact on relationships and belonging. |
| `ecological` | Values long-cycle sustainability, interdependence, and systemic health; sees ideas through whether they regenerate or deplete. |
| `pragmatist` | Values what works in practice over elegant theory; sees ideas through "has this been tried, and did it succeed?" |

These are additive — the existing 5 lenses remain unchanged and fully supported.

### 2. `/api/worldviews` — Registry Endpoint

```
GET /api/worldviews
```
Returns the full list of available lenses with metadata: id, name, description, category
(`epistemological` | `social` | `political` | `role`), and example framing prompt.

### 3. `/api/ideas/{id}/worldviews` — All-Lenses Translation

```
GET /api/ideas/{id}/worldviews
GET /api/ideas/{id}/worldviews?lenses=libertarian,engineer,spiritual
```
Returns translations through all worldview lenses (or a filtered subset) in a single
response. Each entry is a `WorldviewTranslation` object matching the existing
`translate_idea()` response shape. This enables the side-by-side view.

Response shape:
```json
{
  "idea_id": "abc123",
  "idea_name": "Decentralized identity protocol",
  "translations": [
    {
      "lens": "libertarian",
      "lens_category": "political",
      "summary": "...",
      "bridging_concepts": [...],
      "common_ground": ["freedom", "autonomy"]
    }
  ],
  "common_ground_map": {
    "libertarian<>engineer": ["autonomy", "composability"],
    "communitarian<>ecological": ["interdependence", "belonging"]
  },
  "spec_ref": "spec-182"
}
```

### 4. Common-Ground Map

When `/worldviews` returns multiple lenses, compute a `common_ground_map` — pairwise
bridging concepts shared between lens framings. This makes visible where worldviews
overlap even when their surface language differs. Algorithm: intersect bridging_concept
token sets across lens pairs; emit concept names that appear in both.

### 5. News POV Filter

Extend the news ingestion pipeline to accept a `pov_lens` parameter. When set, the
ingested article's summary is reframed through the specified lens before storage.

```
POST /api/news/ingest  { ..., "pov_lens": "entrepreneurial" }
GET /api/news?pov=ecological&limit=20
```

The `GET /api/news` feed accepts a `pov` query parameter. If the requesting contributor
has a belief profile (Spec 169), the default `pov` is derived from their primary worldview
axis. Contributors without a profile receive the default (no POV filter).

### 6. Proof Endpoint

```
GET /api/worldviews/proof
```
Returns aggregate evidence that worldview translation is working:
- `total_translations`: count of all `/translate` and `/worldviews` calls
- `lens_distribution`: how often each lens has been requested
- `avg_bridging_concepts`: mean number of bridging concepts returned per translation
- `cross_lens_engagement`: for ideas where a contributor requested >1 lens, what % also
  contributed or staked after viewing the alternate lens (measures "bridging effect")
- `common_ground_rate`: % of multi-lens requests that found at least 1 shared bridging concept

---

## Data Model

### New: `worldview_translations` table (PostgreSQL)

```sql
CREATE TABLE IF NOT EXISTS worldview_translations (
    id           SERIAL PRIMARY KEY,
    idea_id      TEXT NOT NULL,
    lens         TEXT NOT NULL,
    summary      TEXT NOT NULL,
    bridging_ids TEXT[] DEFAULT '{}',
    common_ground TEXT[] DEFAULT '{}',
    created_at   TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_worldview_translations_idea ON worldview_translations(idea_id);
CREATE INDEX idx_worldview_translations_lens ON worldview_translations(lens);
```

Translations are **cached on first compute** and reused until the idea's description or
tags change. Cache invalidation: when `idea_service.update_idea()` is called, delete rows
for that `idea_id`.

### Lens metadata additions to `translate_service.py`

Extend `_LENS_META` dict and `TranslateLens` enum with the 7 new social/role lenses.
Each entry follows the existing pattern: `description`, `keywords`, `axes`.

### News model extension

Add `pov_lens: Optional[str]` to `NewsItem` model. Nullable; `null` = no POV filter applied.
Add `pov_summary: Optional[str]` — the lens-reframed summary alongside the original.

---

## API Changes

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/worldviews` | List all lenses with metadata |
| `GET` | `/api/ideas/{id}/worldviews` | All-lenses translation with common-ground map |
| `GET` | `/api/ideas/{id}/worldviews?lenses=a,b,c` | Filtered multi-lens translation |
| `GET` | `/api/worldviews/proof` | Aggregate evidence metrics |
| `GET` | `/api/news?pov=<lens>` | News feed filtered/reframed by worldview lens |

Existing endpoint `GET /api/ideas/{id}/translate?view=<lens>` is **unchanged** — backward
compatible. New endpoints are additive.

---

## Acceptance Criteria

1. `GET /api/worldviews` returns at least 12 lenses (5 existing + 7 new), each with `id`, `name`,
   `description`, `category`, and `example`.
2. `GET /api/ideas/{id}/worldviews` returns a translation for **every** registered lens by
   default; `?lenses=a,b` returns only the requested subset.
3. Each translation entry contains `lens`, `summary` (non-empty string), `bridging_concepts`
   (list, may be empty if ontology has no matches), and `common_ground` (list).
4. `common_ground_map` in the multi-lens response contains pairwise keys for every pair
   of requested lenses; values are lists of shared concept name strings.
5. `GET /api/worldviews/proof` returns all 5 metrics defined above with correct field names
   and `spec_ref: "spec-182"`.
6. `GET /api/news?pov=entrepreneurial` returns news items whose `pov_summary` is reframed
   through the entrepreneurial lens if `pov_lens` was set on ingest.
7. Requesting an unknown lens (e.g., `?lenses=marxist`) returns 422 with a message listing
   valid lenses.
8. Requesting `/api/ideas/{id}/worldviews` for a non-existent idea returns 404.
9. All 12 tests in `api/tests/test_worldview_translation.py` pass.
10. `GET /api/worldviews/proof` returns `total_translations > 0` after any translation call.

---

## Verification Scenarios

The reviewer will run these scenarios against production at `https://api.coherencycoin.com`.

### Scenario 1 — Registry lists all lenses including new social ones

**Setup**: No special setup required.

**Action**:
```bash
curl -s https://api.coherencycoin.com/api/worldviews | python3 -c "
import json, sys
d = json.load(sys.stdin)
lenses = [l['id'] for l in d['lenses']]
print('count:', len(lenses))
print('has libertarian:', 'libertarian' in lenses)
print('has engineer:', 'engineer' in lenses)
print('has scientific:', 'scientific' in lenses)
"
```

**Expected**: `count: 12` (or more), `has libertarian: True`, `has engineer: True`,
`has scientific: True`.

**Edge**: `GET /api/worldviews?category=political` returns only political category lenses.
Unknown category returns empty list, not 422.

---

### Scenario 2 — All-lenses endpoint returns side-by-side translations with common ground

**Setup**: Create an idea about decentralized identity.
```bash
curl -s -X POST https://api.coherencycoin.com/api/ideas \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-key" \
  -d '{"id":"test-decentralized-id","name":"Decentralized identity protocol",
       "description":"A protocol where individuals control their own identity without central authority. Uses cryptographic keys and distributed ledgers. Enables freedom and autonomy.",
       "tags":["identity","decentralization","cryptography","freedom","autonomy"]}'
```

**Action**:
```bash
curl -s "https://api.coherencycoin.com/api/ideas/test-decentralized-id/worldviews?lenses=libertarian,engineer,institutionalist" \
  | python3 -c "
import json, sys
d = json.load(sys.stdin)
translations = {t['lens']: t for t in d['translations']}
print('lenses returned:', sorted(translations.keys()))
print('libertarian summary non-empty:', len(translations.get('libertarian',{}).get('summary','')) > 0)
print('engineer summary non-empty:', len(translations.get('engineer',{}).get('summary','')) > 0)
print('common_ground_map keys:', list(d.get('common_ground_map',{}).keys()))
"
```

**Expected**:
- `lenses returned: ['engineer', 'institutionalist', 'libertarian']`
- Both summaries non-empty
- `common_ground_map` contains key `libertarian<>engineer` (or equivalent pair notation)

**Edge**: `?lenses=libertarian,not-a-lens` returns 422 with message listing valid lens names.

---

### Scenario 3 — Proof endpoint shows real usage after translation calls

**Setup**: Run Scenario 2 first (at least one translation call made).

**Action**:
```bash
curl -s https://api.coherencycoin.com/api/worldviews/proof | python3 -c "
import json, sys
d = json.load(sys.stdin)
print('spec_ref:', d.get('spec_ref'))
print('total_translations:', d.get('total_translations'))
print('has lens_distribution:', isinstance(d.get('lens_distribution'), dict))
print('avg_bridging_concepts:', d.get('avg_bridging_concepts'))
"
```

**Expected**:
- `spec_ref: spec-182`
- `total_translations > 0`
- `has lens_distribution: True`
- `avg_bridging_concepts` is a float >= 0.0

**Edge**: Called before any translation call returns `total_translations: 0` with HTTP 200.

---

### Scenario 4 — Backward compatibility: single-lens endpoint unchanged

**Action**:
```bash
for lens in scientific economic spiritual artistic philosophical; do
  status=$(curl -s -o /dev/null -w "%{http_code}" \
    "https://api.coherencycoin.com/api/ideas/test-decentralized-id/translate?view=$lens")
  echo "$lens: $status"
done
```

**Expected**: All 5 return `200`.

**Also**: `?view=libertarian` on the old single-lens endpoint also returns 200 — new lenses
are valid in the existing endpoint.

**Edge**: `?view=not-a-real-worldview` on existing single-lens endpoint returns 422.

---

### Scenario 5 — Error handling: non-existent idea and invalid lens

**Action A** — Non-existent idea:
```bash
curl -s -o /dev/null -w "%{http_code}" \
  "https://api.coherencycoin.com/api/ideas/does-not-exist-xyz/worldviews"
```
**Expected**: `404`

**Action B** — Invalid lens on multi-lens endpoint:
```bash
curl -s -o /dev/null -w "%{http_code}" \
  "https://api.coherencycoin.com/api/ideas/test-decentralized-id/worldviews?lenses=not-a-real-worldview"
```
**Expected**: `422`

**Action C** — Invalid lens on existing single-lens endpoint:
```bash
curl -s -o /dev/null -w "%{http_code}" \
  "https://api.coherencycoin.com/api/ideas/test-decentralized-id/translate?view=not-a-real-worldview"
```
**Expected**: `422`

---

## Files to Create or Modify

| File | Action | Notes |
|------|--------|-------|
| `api/app/services/translate_service.py` | **Modify** | Add 7 new lenses to `_LENS_META` and `TranslateLens` enum |
| `api/app/routers/worldviews.py` | **Create** | New router: `/api/worldviews`, `/api/worldviews/proof` |
| `api/app/routers/ideas.py` | **Modify** | Add `GET /api/ideas/{id}/worldviews` endpoint |
| `api/app/models/worldview.py` | **Create** | Pydantic models: `WorldviewLensInfo`, `WorldviewTranslation`, `AllWorldviewsResponse`, `WorldviewProofResponse` |
| `api/app/main.py` | **Modify** | Register `worldviews` router |
| `api/tests/test_worldview_translation.py` | **Create** | 12 integration tests |
| `api/alembic/versions/` | **Create** | Migration adding `worldview_translations` table |

---

## Implementation Notes

### Lens metadata for new worldviews

```python
"libertarian": {
    "description": "Values individual freedom, voluntary exchange, and minimal coercion. Asks: who controls what, and is force involved?",
    "keywords": ["freedom", "autonomy", "voluntary", "coercion", "individual", "rights", "liberty",
                 "decentralize", "self-sovereign", "privacy", "consent", "choice", "market"],
    "axes": ["autonomy", "voluntary", "anti-coercive", "self-sovereign"],
    "category": "political",
},
"institutionalist": {
    "description": "Values stable rules, established procedures, and collective continuity. Asks: what risk does this pose to existing legitimate structures?",
    "keywords": ["stability", "institution", "procedure", "legitimacy", "continuity", "governance",
                 "rule", "trust", "accountability", "oversight", "compliance", "structure"],
    "axes": ["stability", "procedural", "accountable", "collective"],
    "category": "political",
},
"entrepreneurial": {
    "description": "Values opportunity, disruption, speed, and asymmetric upside. Asks: what market does this create and who captures it first?",
    "keywords": ["opportunity", "market", "disruption", "growth", "scale", "product", "user",
                 "revenue", "startup", "mvp", "iterate", "capture", "platform", "network"],
    "axes": ["opportunistic", "disruptive", "growth", "market-driven"],
    "category": "role",
},
"engineer": {
    "description": "Values correctness, composability, measurability, and implementation feasibility. Asks: can this be built, verified, and maintained?",
    "keywords": ["build", "system", "interface", "api", "test", "verify", "measure", "composable",
                 "modular", "debug", "reliability", "performance", "deploy", "spec", "correct"],
    "axes": ["systematic", "verifiable", "composable", "pragmatic"],
    "category": "role",
},
"communitarian": {
    "description": "Values shared identity, mutual obligation, and community flourishing. Asks: how does this affect belonging and social bonds?",
    "keywords": ["community", "belonging", "shared", "mutual", "obligation", "identity", "culture",
                 "solidarity", "trust", "neighbor", "commons", "welfare", "inclusion", "care"],
    "axes": ["relational", "collective", "inclusive", "caring"],
    "category": "social",
},
"ecological": {
    "description": "Values long-cycle sustainability, interdependence, and systemic health. Asks: does this regenerate or deplete the systems it depends on?",
    "keywords": ["sustain", "ecology", "cycle", "regenerate", "deplete", "habitat", "climate",
                 "biodiversity", "system", "interdependence", "resource", "longterm", "health"],
    "axes": ["sustainable", "systemic", "long-cycle", "regenerative"],
    "category": "ecological",
},
"pragmatist": {
    "description": "Values what works in practice over elegant theory. Asks: has this been tried, and did it succeed under real conditions?",
    "keywords": ["works", "proven", "practical", "evidence", "result", "outcome", "trial", "test",
                 "implement", "real", "condition", "iterate", "feedback", "learn", "adapt"],
    "axes": ["evidence-based", "iterative", "results-oriented", "adaptive"],
    "category": "social",
},
```

### Common-ground map algorithm

```python
def _build_common_ground_map(translations: list[dict]) -> dict[str, list[str]]:
    cg = {}
    for i, a in enumerate(translations):
        for b in translations[i+1:]:
            key = f"{a['lens']}<>{b['lens']}"
            a_names = {c["name"] for c in a.get("bridging_concepts", [])}
            b_names = {c["name"] for c in b.get("bridging_concepts", [])}
            cg[key] = sorted(a_names & b_names)
    return cg
```

### Caching strategy

For MVP: translations are **computed in-memory on each request** (no DB write). The
`worldview_translations` table is defined in the migration for future caching but not
required for the first shipped version. DB caching is a follow-up.

---

## How to Measure "Is It Working?" — Proof Over Time

This spec explicitly addresses: *"How can we improve this idea, show whether it is working
yet, and make that proof clearer over time?"*

### Immediate proof (deploy day)

- `GET /api/worldviews` returns at least 12 lenses.
- `GET /api/ideas/{any-id}/worldviews` returns translations for all lenses without 500.
- `GET /api/worldviews/proof` returns `spec_ref: "spec-182"`.

### Short-term proof (1-2 weeks)

- **Multi-lens engagement rate**: Track how often contributors request more than 1 lens for
  the same idea. Rising rate = the side-by-side view is useful.
- **Common-ground discovery**: Monitor `common_ground_rate` in `/api/worldviews/proof`.
  If contributors find common ground, they should show higher follow-up engagement on those
  ideas (measurable via contribution/stake events on the same idea_id).

### Medium-term proof (1 month)

- **Cross-worldview contribution**: Do contributors who view an idea through a lens that
  differs from their primary worldview contribute more than those who view only their
  primary lens? If so, translation is building bridges.
- **News POV engagement**: POV-reframed news items should show >= 10% higher engagement
  for contributors whose belief profile matches the POV lens.

### Observable proof in existing endpoints

| Endpoint | Signal | Healthy threshold |
|----------|--------|-------------------|
| `GET /api/worldviews/proof` | `total_translations > 0` | Day 1 |
| `GET /api/worldviews/proof` | `lens_distribution` has >= 3 distinct lenses used | Week 1 |
| `GET /api/worldviews/proof` | `cross_lens_engagement > 0` | Week 2 |
| `GET /api/worldviews/proof` | `avg_bridging_concepts >= 2.0` | Week 1 |

---

## Risks and Assumptions

- **Risk**: Worldview labels carry political connotations. **Mitigation**: Lenses are tools
  for idea exploration, not contributor labels. The UI copy must make this clear: "View this
  idea through the libertarian lens" does not mean "You are a libertarian."

- **Risk**: Keyword-based bridging produces low-quality translations for lenses with sparse
  ontology coverage (especially communitarian, ecological). **Mitigation**: Ship with a
  "low-coverage" badge when `bridging_concepts` is empty; treat it as a signal to enrich
  the ontology.

- **Risk**: The `common_ground_map` may be trivially empty for distant worldview pairs.
  **Mitigation**: Empty common ground is information. The UI shows "no shared concepts found"
  as a meaningful state.

- **Risk**: News POV reframing may distort politically charged articles. **Mitigation**:
  `pov_summary` is additive alongside `summary`, never replacing the original.

- **Assumption**: `translate_service.py` is the canonical service (used by the `ideas.py`
  router). The 7 new lenses are added there. Consolidation of the two translation service
  files is a follow-up.

---

## Known Gaps and Follow-up Tasks

- Ontology enrichment for social/role lenses (communitarian, ecological).
- DB caching of translations (`worldview_translations` table) after perf profiling.
- LLM-enhanced translation summaries (currently keyword-only).
- Cross-contributor "who sees this like me?" feature based on shared lens engagement.
- News ingestion POV filter UI.
- Worldview analytics dashboard card showing lens usage heatmap.
- CLI: `cc worldviews <idea-id>` showing all translations in terminal.

---

## Decision Gates

- **D1**: Should the 7 new lenses extend `TranslateLens` or be a separate enum?
  Decision: **extend `TranslateLens`** — single enum, simpler validation, backward compatible.
- **D2**: Should common-ground be computed on all pairs or only adjacent pairs?
  Decision: **all pairs** — O(n^2) is fine for <= 12 lenses; maximum bridge visibility.
- **D3**: Should POV news filter replace or supplement the original summary?
  Decision: **supplement only** — `pov_summary` is additive; `summary` is never modified.
- **D4**: Should `/api/worldviews` require authentication?
  Decision: **public read** — lens metadata is not sensitive.

---

## External Evidence

The feature is realized when all of the following are independently verifiable:

1. `curl https://api.coherencycoin.com/api/worldviews` returns HTTP 200 with >= 12 lens
   objects including `libertarian` and `engineer`.
2. `curl "https://api.coherencycoin.com/api/ideas/{any-valid-id}/worldviews"` returns HTTP 200
   with a `translations` array containing entries for all registered lenses.
3. `curl https://api.coherencycoin.com/api/worldviews/proof` returns HTTP 200 with
   `spec_ref: "spec-182"` and measurable usage metrics.
4. Web UI displays a "View through worldview" selector on the idea detail page (screenshot
   attestation from a contributor).

---

## Metadata

- **Spec ID**: 182-worldview-translation
- **Task ID**: task_3a5c59a84394e17a
- **Author**: product-manager agent
- **Date**: 2026-03-28
- **Status**: approved
- **Depends on**: Spec 169 (Belief System), Spec 163 (Resonance Navigation)
- **Blocks**: news POV filter UI (follow-up), worldview analytics dashboard (follow-up)
