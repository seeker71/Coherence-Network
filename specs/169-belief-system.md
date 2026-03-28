# Spec 169: Belief System — Per-Contributor Worldview, Interests, and Concept Preferences

**Spec ID**: 169-belief-system
**Task ID**: task_0b965651310e5bd3
**Status**: approved
**Priority**: high
**Author**: product-manager agent
**Date**: 2026-03-28
**Revised**: 2026-03-28 (enhanced with implementation guard-rails, proof-over-time mechanisms)
**Depends on**: Spec 008 (Graph Foundation), Spec 119 (Coherence Credit), Spec 162 (Identity-Driven Onboarding), Spec 163 (Resonance Navigation)

---

## Summary

Every contributor operates from a personal worldview: a set of values, interests, and concept affinities that shape how they engage with ideas. The Belief System makes this worldview explicit, structured, and actionable.

A **BeliefProfile** stores which concepts a contributor resonates with, which epistemic axes they value (e.g., scientific rigor vs. spiritual intuition vs. pragmatic utility), and which worldview framing they apply to new ideas. These preferences are used to personalize news matching, idea recommendations, and contribution suggestions — surfacing content that genuinely resonates rather than flooding with noise.

Adapted directly from the `UserConceptModule` and `BeliefSystemModule` in the Living Codex origin project, this spec brings that deep architectural vision into the Coherence Network's contributor graph.

---

## Motivation

### The relevance problem

As the Coherence Network grows, contributors are exposed to increasing volumes of ideas, concepts, and tasks. Without a belief profile, the system has no basis for distinguishing what matters to *this person* from what matters in general. The result is noise — or the absence of any personalization at all.

A belief profile transforms the system from a neutral feed into a **resonant discovery engine**: one that knows whether a contributor cares more about rigorous empirical validation or emergent spiritual insight, whether they are drawn to pragmatic tooling problems or holistic systemic thinking.

### The Living Codex lineage

The Living Codex `UserConceptModule` tracked per-user concept affinity scores, updated through interaction. The `BeliefSystemModule` stored worldview axes (scientific, spiritual, pragmatic, holistic, synthetic) and used them to weight the `ResonanceEngine`'s output. This spec is the Coherence Network instantiation of that vision.

### The proof problem (open question addressed)

The key open question: *How can we show that belief profiles are actually working, and make that proof clearer over time?*

**The answer must be measurable and compounding.** We define "working" as:
- Contributors with complete belief profiles (`belief_completeness >= 0.7`) receive idea recommendations with measurably higher engagement rates than contributors without profiles (`belief_completeness < 0.3`).
- The gap between these cohorts grows over time as profiles are refined.
- Individual contributors can see their own lift trend (not just a snapshot).

Three mechanisms ensure the proof accumulates automatically:
1. **`belief_recommendation_events` table**: Every recommendation shown records its `resonance_score`. Every engagement records `engaged_at`. This is the raw data.
2. **`GET /api/contributors/{id}/beliefs/roi`**: Per-contributor lift endpoint. Shows engagement_rate vs. baseline, trend over time with `period_days` parameter.
3. **`GET /api/system/beliefs/effectiveness` (admin)**: System-wide cohort analysis showing completeness vs. engagement lift, updated daily.

The **BeliefROICard** web component displays this proof inline on the contributor's beliefs page, with a time-series sparkline showing whether lift is improving. Green = working. Red = needs recalibration. Gray = insufficient data. This is visible to the contributor, not just admins.

---

## Goals

1. Store a **BeliefProfile** per contributor: worldview axes, concept resonances, tag affinities.
2. Expose `GET /api/contributors/{id}/beliefs` and `PATCH /api/contributors/{id}/beliefs` for profile read/update.
3. Expose `GET /api/contributors/{id}/beliefs/resonance?idea_id={id}` to score alignment between a contributor's beliefs and a specific idea.
4. Expose `GET /api/contributors/{id}/beliefs/roi?days=30` to show proof-of-working: engagement lift attributable to belief-driven recommendations.
5. Add CLI commands: `cc beliefs`, `cc beliefs set <axis> <value>`, `cc beliefs match <idea-id>`.
6. Add a web profile page section: belief radar chart, concept tag cloud, worldview selector.
7. Use belief profiles as input to the personalized idea recommendation pipeline.
8. Make the UI mobile-friendly via swipeable cards, not long forms.

---

## Non-Goals

- This spec does not implement the full recommendation pipeline (that is Spec 163/170). It exposes belief data as an input.
- This spec does not implement real-time belief updates from implicit signals (click tracking, dwell time). Explicit PATCH only in this phase.
- This spec does not store beliefs in the graph DB (Neo4j). PostgreSQL is the source of truth for belief profiles; the graph layer can be added in a follow-up.

---

## Data Model

### BeliefAxis (enum)

The worldview axes a contributor can position themselves on. Each axis is a spectrum from 0.0 to 1.0.

> **IMPLEMENTATION NOTE**: These are the EXACT enum values. Do NOT use `relational`, `systemic`, or any other names. All 7 axes must be present in the enum and in the WorldviewSelector component.

```python
class BeliefAxis(str, Enum):
    scientific   = "scientific"    # empirical, evidence-driven, skeptical of unfalsifiable claims
    spiritual    = "spiritual"     # meaning-oriented, transcendent, sacred dimension of experience
    pragmatic    = "pragmatic"     # utility-first, solution-oriented, what works in practice
    holistic     = "holistic"      # systems thinking, interconnectedness, emergent properties
    synthetic    = "synthetic"     # integrative, bridge-builder, draws across worldviews
    critical     = "critical"      # power-aware, deconstructive, questions default narratives
    imaginative  = "imaginative"   # speculative, futures-oriented, comfort with uncertainty
```

### ConceptResonance

A scored affinity between a contributor and a concept node in the graph.

> **IMPLEMENTATION NOTE**: The field is named `score` (not `weight`, not `resonance`, not `affinity`). The field `concept_name` is denormalized for display.

```python
class ConceptResonance(BaseModel):
    concept_id: str          # references a concept node in the graph
    concept_name: str        # denormalized for display
    score: float             # 0.0 (no resonance) to 1.0 (full resonance)
    updated_at: datetime
```

### BeliefProfile (Pydantic / DB model)

```python
class BeliefProfile(BaseModel):
    contributor_id: str
    worldview_axes: dict[BeliefAxis, float]   # axis -> 0.0–1.0 value
    concept_resonances: list[ConceptResonance]
    tag_affinities: dict[str, float]          # tag -> 0.0–1.0 score
    primary_worldview: BeliefAxis | None      # dominant axis, derived or explicitly set
    updated_at: datetime
    created_at: datetime
```

### BeliefProfileUpdate (PATCH body)

> **IMPLEMENTATION NOTE**: This is the request body for PATCH. All fields are optional. `worldview_axes` is merged into the existing axes (not replaced entirely).

```python
class BeliefProfileUpdate(BaseModel):
    worldview_axes: dict[str, float] | None = None
    concept_resonances: list[ConceptResonance] | None = None
    tag_affinities: dict[str, float] | None = None
    primary_worldview: BeliefAxis | None = None

    @validator('worldview_axes')
    def validate_axes(cls, v):
        if v:
            for axis, value in v.items():
                if axis not in BeliefAxis.__members__:
                    raise ValueError(f"'{axis}' is not a valid BeliefAxis. Valid axes: {list(BeliefAxis.__members__)}")
                if not (0.0 <= value <= 1.0):
                    raise ValueError(f"Axis value must be between 0.0 and 1.0, got {value}")
        return v
```

### ResonanceResult

Returned by the resonance match endpoint.

> **IMPLEMENTATION NOTE**: The top-level score field is named `overall_score` (not `resonance_score`, not `score`). All sub-scores are present.

```python
class ResonanceResult(BaseModel):
    contributor_id: str
    idea_id: str
    overall_score: float          # 0.0–1.0
    concept_overlap: float        # how many of the idea's concepts match contributor beliefs
    worldview_alignment: float    # alignment between idea's worldview tags and contributor axes
    tag_match: float              # tag affinity overlap
    explanation: list[str]        # human-readable reasons e.g. "Strong alignment on 'holistic' axis"
    recommended_action: str | None  # e.g. "Contribute", "Follow", "Skip"
```

### BeliefROI

Proof-of-working metrics.

```python
class BeliefROI(BaseModel):
    contributor_id: str
    period_days: int
    recommendations_shown: int
    recommendations_engaged: int   # click, contribute, credit, comment
    engagement_rate: float         # engaged / shown
    belief_completeness: float     # 0.0–1.0, how much of the profile is filled in
    baseline_engagement_rate: float | None  # network average for comparison
    lift: float | None             # engagement_rate - baseline_engagement_rate
    lift_trend: list[float] | None # weekly lift values for sparkline (null if < 4 weeks data)
    insufficient_data_reason: str | None  # explains why lift is null
```

### PostgreSQL Migration

New table `belief_profiles`:

```sql
CREATE TABLE belief_profiles (
    contributor_id  TEXT PRIMARY KEY REFERENCES contributors(id) ON DELETE CASCADE,
    worldview_axes  JSONB NOT NULL DEFAULT '{}',
    concept_resonances JSONB NOT NULL DEFAULT '[]',
    tag_affinities  JSONB NOT NULL DEFAULT '{}',
    primary_worldview TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_belief_profiles_primary_worldview ON belief_profiles(primary_worldview);
```

New table `belief_recommendation_events` (for ROI tracking):

```sql
CREATE TABLE belief_recommendation_events (
    id              TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    contributor_id  TEXT NOT NULL REFERENCES contributors(id) ON DELETE CASCADE,
    idea_id         TEXT NOT NULL,
    resonance_score FLOAT NOT NULL,
    shown_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    engaged_at      TIMESTAMPTZ,
    engagement_type TEXT   -- 'click', 'contribute', 'credit', 'comment'
);

CREATE INDEX idx_belief_rec_events_contributor ON belief_recommendation_events(contributor_id);
CREATE INDEX idx_belief_rec_events_shown_at ON belief_recommendation_events(shown_at);
```

---

## API Contract

### GET /api/contributors/{id}/beliefs

Returns the contributor's current belief profile. If no profile exists yet, returns an empty default profile (not 404 — the contributor exists, they just haven't configured beliefs yet). Returns 404 only if the contributor does not exist.

**Response 200** (profile exists):
```json
{
  "contributor_id": "alice",
  "worldview_axes": {
    "scientific": 0.8,
    "holistic": 0.6,
    "pragmatic": 0.5,
    "spiritual": 0.2,
    "synthetic": 0.4,
    "critical": 0.3,
    "imaginative": 0.7
  },
  "concept_resonances": [
    {"concept_id": "c-emergence", "concept_name": "Emergence", "score": 0.9, "updated_at": "2026-03-28T12:00:00Z"}
  ],
  "tag_affinities": {
    "ai": 0.9,
    "graph-theory": 0.7,
    "consciousness": 0.4
  },
  "primary_worldview": "scientific",
  "updated_at": "2026-03-28T12:00:00Z",
  "created_at": "2026-03-01T00:00:00Z"
}
```

**Response 200** (no profile yet — return empty defaults, not 404):
```json
{
  "contributor_id": "alice",
  "worldview_axes": {},
  "concept_resonances": [],
  "tag_affinities": {},
  "primary_worldview": null,
  "updated_at": "...",
  "created_at": "..."
}
```

**Response 404**: contributor not found (contributor `id` does not exist)

---

### PATCH /api/contributors/{id}/beliefs

Partial update of the belief profile. Any field omitted is left unchanged. `worldview_axes` entries are merged (not replaced), so you can update a single axis without sending all seven.

**Request body**:
```json
{
  "worldview_axes": {"scientific": 0.9},
  "tag_affinities": {"quantum-computing": 0.8},
  "primary_worldview": "scientific"
}
```

**Response 200**: updated BeliefProfile
**Response 422**: axis value out of range [0.0, 1.0] — body: `{"detail": "Axis value must be between 0.0 and 1.0, got 1.5"}`
**Response 422**: unknown BeliefAxis key — body: `{"detail": "'astrology' is not a valid BeliefAxis. Valid axes: scientific, spiritual, pragmatic, holistic, synthetic, critical, imaginative"}`
**Response 404**: contributor not found
**Response 403**: authenticated contributor can only update their own profile (unless admin)

---

### GET /api/contributors/{id}/beliefs/resonance?idea_id={idea_id}

Computes how well this contributor's belief profile aligns with a specific idea.

**Algorithm**:
```
overall_score = (0.4 × concept_overlap) + (0.4 × worldview_alignment) + (0.2 × tag_match)
```

- `concept_overlap`: Jaccard similarity between the idea's concept tags and the contributor's top resonated concepts (score ≥ 0.5).
- `worldview_alignment`: cosine similarity between the idea's worldview vector (inferred from its tags and category) and the contributor's `worldview_axes` dict.
- `tag_match`: proportion of the idea's tags that appear in the contributor's `tag_affinities` with score ≥ 0.4.

**Response 200**: ResonanceResult (see above — field is `overall_score`)
**Response 404**: contributor or idea not found — `{"detail": "Contributor 'x' not found"}` or `{"detail": "Idea 'y' not found"}`
**Response 200 with all scores = 0.0**: valid response when contributor has empty belief profile or no overlap exists (not an error)

---

### GET /api/contributors/{id}/beliefs/roi?days=30

Returns engagement lift attributable to belief-driven recommendations over the last N days. Default is 30 days.

**Query params**:
- `days` (int, optional, default=30): lookback window

**Response 200**: BeliefROI
- If `recommendations_shown < 10`: `lift=null`, `baseline_engagement_rate=null`, `insufficient_data_reason="Need at least 10 recommendations to compute lift"`
- If `recommendations_shown >= 10`: `lift` is computed as `engagement_rate - baseline_engagement_rate`

**Response 404**: contributor not found

---

## Files to Create or Modify

### New files

| Path | Purpose |
|------|---------|
| `api/app/routers/beliefs.py` | FastAPI router with all 4 belief endpoints (GET, PATCH, resonance, roi) |
| `api/app/services/beliefs_service.py` | Business logic: resonance algorithm, ROI calculation, CRUD |
| `api/app/models/belief_profile.py` | Pydantic models: BeliefProfile, BeliefAxis (7 axes exactly), ConceptResonance, ResonanceResult, BeliefROI |
| `api/alembic/versions/xxxx_add_belief_profiles.py` | DB migration: belief_profiles + belief_recommendation_events tables |
| `api/tests/test_beliefs.py` | Pytest tests covering all endpoints and edge cases |
| `web/src/components/beliefs/BeliefRadarChart.tsx` | Radar chart visualizing worldview_axes (Recharts/Chart.js) |
| `web/src/components/beliefs/ConceptTagCloud.tsx` | Tag cloud of concept resonances, sized by `score` field (not `weight`) |
| `web/src/components/beliefs/WorldviewSelector.tsx` | Swipeable card selector for the 7 worldview axes (scientific, spiritual, pragmatic, holistic, synthetic, critical, imaginative) |
| `web/src/components/beliefs/BeliefROICard.tsx` | Card showing engagement lift, sparkline, and proof-of-working metrics |
| `web/src/app/contributors/[id]/beliefs/page.tsx` | Next.js page at `/contributors/{id}/beliefs` |

### Modified files

| Path | Change |
|------|--------|
| `api/app/main.py` | Register `beliefs` router under prefix `/api/contributors` |
| `api/app/routers/__init__.py` | Export beliefs router |
| `web/src/app/contributors/[id]/page.tsx` | Add link/tab to beliefs sub-page |

---

## Implementation Guard-Rails

These are common implementation errors from prior attempts. Do not repeat them.

| Mistake | Correct behavior |
|---------|-----------------|
| Using `weight` for concept affinity score | Must be `score` (field on ConceptResonance) |
| Using `resonance_score` as the top-level result field | Must be `overall_score` (field on ResonanceResult) |
| Using axes `relational` or `systemic` | Must use only the 7 canonical axes: scientific, spiritual, pragmatic, holistic, synthetic, critical, imaginative |
| Web page at `/profile/[handle]/beliefs` | Must be at `/contributors/[id]/beliefs` |
| Returning 404 when belief profile doesn't exist yet | Must return 200 with empty defaults (profile auto-created or returned as default) |
| Router stub with no endpoints | All 4 endpoints (GET, PATCH, resonance, roi) must be implemented |
| Service file missing (only .pyc cache) | Source file `beliefs_service.py` must exist with actual logic |
| Migration file missing | `xxxx_add_belief_profiles.py` must be committed with valid `upgrade()` and `downgrade()` |
| BeliefROICard missing from web page | Must be imported and rendered in `/contributors/[id]/beliefs/page.tsx` |
| CLI using `resonance_score` from API | CLI must read `overall_score` from ResonanceResult |

---

## CLI Commands

All implemented in the `cc` CLI tool. Require the contributor to be authenticated (API key set via `cc setup`).

### `cc beliefs`

Show the current contributor's belief profile in a compact table.

```
$ cc beliefs
Worldview Axes
──────────────────────────────────
scientific   ████████░░  0.8
holistic     ██████░░░░  0.6
imaginative  ███████░░░  0.7
pragmatic    █████░░░░░  0.5
synthetic    ████░░░░░░  0.4
critical     ███░░░░░░░  0.3
spiritual    ██░░░░░░░░  0.2

Top Concepts: Emergence (0.9), Graph Theory (0.7), AI (0.9)
Top Tags: ai, graph-theory, consciousness
```

### `cc beliefs set <axis> <value>`

Update a single axis value (0.0–1.0).

```
$ cc beliefs set holistic 0.8
✓ Updated: holistic → 0.8
```

Error cases:
- `cc beliefs set unknown 0.5` → `Error: 'unknown' is not a valid BeliefAxis. Valid axes: scientific, spiritual, pragmatic, holistic, synthetic, critical, imaginative`
- `cc beliefs set scientific 1.5` → `Error: value must be between 0.0 and 1.0`

### `cc beliefs match <idea-id>`

Show resonance score between the current contributor and an idea.

```
$ cc beliefs match idea-abc123
Resonance: 0.74 / 1.00 ██████████████░░░░░░

  Concept overlap:     0.80 (4/5 concepts match your profile)
  Worldview alignment: 0.70 (strong holistic + scientific fit)
  Tag match:           0.65 (ai, graph-theory matched)

  Recommended action: Contribute
  Why: Your expertise in Emergence and AI aligns strongly with this idea's core concepts.
```

---

## Web UI

### Route

`/contributors/{id}/beliefs`

### Components

**BeliefRadarChart**
- Spider/radar chart with 7 axes (one per BeliefAxis — all 7 canonical axes).
- Each axis extends 0.0 → 1.0 from center.
- Rendered with Recharts `RadarChart` or equivalent.
- Mobile: full-width, touch-friendly hover tooltips.

**WorldviewSelector**
- 7 swipeable cards, one per axis (scientific, spiritual, pragmatic, holistic, synthetic, critical, imaginative).
- Each card: axis name, description (one sentence), current value as a large number + progress bar.
- User can tap +/- buttons or drag slider to set value.
- Saves via PATCH on blur/swipe-away (debounced 500ms).
- No long form — each card is a single focused choice.

**ConceptTagCloud**
- Tags sized by resonance `score` field (0.5→1.0 maps to font-size 12px→24px).
- Click a tag to see concept details or navigate to concept page.
- Add/remove concepts via an autocomplete input below the cloud.

**BeliefROICard**
- Shows: recommendations shown, engaged, engagement rate, baseline, lift.
- Shows `lift_trend` as a sparkline (weekly lift values) — this makes proof visible over time, not just as a snapshot.
- Color-coded: green lift (>0.05), yellow (0 to 0.05), gray (insufficient data), red (<0).
- "How this works" info icon with explanation: "Ideas matched to your beliefs. Higher engagement means your beliefs are well-tuned."
- Updates on page load (stale-while-revalidate, max 1 hour cache).

### Mobile-first principles

- No long scrollable forms. Each setting is a card.
- Swipeable WorldviewSelector (horizontal swipe through axes).
- Radar chart is full-width on mobile.
- BeliefROICard is a compact 2×2 stat grid, not a table.

---

## Resonance Algorithm Detail

```python
def compute_resonance(contributor: BeliefProfile, idea: Idea) -> ResonanceResult:
    # 1. Concept overlap (Jaccard)
    contributor_concepts = {r.concept_id for r in contributor.concept_resonances if r.score >= 0.5}
    idea_concepts = set(idea.concept_ids or [])
    if contributor_concepts | idea_concepts:
        concept_overlap = len(contributor_concepts & idea_concepts) / len(contributor_concepts | idea_concepts)
    else:
        concept_overlap = 0.0

    # 2. Worldview alignment (cosine similarity)
    # Idea worldview inferred from its category and tags mapped to BeliefAxis keywords
    idea_axes = infer_idea_worldview(idea)   # returns dict[BeliefAxis, float]
    worldview_alignment = cosine_similarity(contributor.worldview_axes, idea_axes)

    # 3. Tag match
    contributor_tags = {t for t, s in contributor.tag_affinities.items() if s >= 0.4}
    idea_tags = set(idea.tags or [])
    tag_match = len(contributor_tags & idea_tags) / max(len(idea_tags), 1)

    overall = 0.4 * concept_overlap + 0.4 * worldview_alignment + 0.2 * tag_match

    explanation = build_explanation(concept_overlap, worldview_alignment, tag_match, contributor, idea)
    action = recommend_action(overall)

    return ResonanceResult(
        contributor_id=contributor.contributor_id,
        idea_id=idea.id,
        overall_score=round(overall, 3),      # NOTE: field is overall_score
        concept_overlap=round(concept_overlap, 3),
        worldview_alignment=round(worldview_alignment, 3),
        tag_match=round(tag_match, 3),
        explanation=explanation,
        recommended_action=action,
    )
```

The `infer_idea_worldview` function maps idea tags/categories to belief axes via a lightweight keyword mapping (e.g., `["empirical", "data", "experiment"]` → `scientific`, `["systems", "network", "emergence"]` → `holistic`). This mapping lives in a config file and can be extended without code changes.

---

## Proof of Working — Compounding Over Time

The belief system is only working if it demonstrably improves engagement. The proof mechanism compounds over time — it does not just show a snapshot.

### Level 1: Per-Recommendation Tracking (immediate)

1. **On recommendation shown**: insert a `belief_recommendation_events` row with `resonance_score` and `shown_at`.
2. **On engagement**: update the row with `engaged_at` and `engagement_type`.

### Level 2: Per-Contributor ROI (daily, visible to contributor)

3. **ROI endpoint**: queries `belief_recommendation_events` to compute `engagement_rate = engaged / shown`.
4. **Baseline**: compute the network-wide average engagement rate for ideas shown in the same period.
5. **Lift**: `engagement_rate - baseline_engagement_rate`.
6. **Trend**: compute `lift_trend` as a list of weekly lift values — this shows whether the contributor's profile is improving over time, not just a static score.
7. **BeliefROICard**: renders the sparkline, making the trend visible.

### Level 3: System-Level Effectiveness (admin, monthly)

8. **`GET /api/system/beliefs/effectiveness`** (admin only): cohort analysis grouping contributors by `belief_completeness` (0–0.3, 0.3–0.7, 0.7–1.0) and comparing engagement rates across cohorts.
9. **Threshold**: `lift >= 0.05` across the high-completeness cohort = system is working. `lift < 0` = beliefs are miscalibrated; alert.
10. **Before/after analysis**: when a contributor updates an axis, track whether their recommendations improve in the subsequent 7 days.

### Proof thresholds

| Signal | Working | Needs attention |
|--------|---------|----------------|
| `lift` per contributor | ≥ 0.05 (5pp) | < 0 |
| High-completeness cohort lift | ≥ 0.08 | < 0.02 |
| `belief_completeness` average across active contributors | ≥ 0.5 | < 0.2 |

---

## Verification Scenarios

### Scenario 1: Full CRUD cycle for a belief profile

**Setup**: Contributor `alice` exists in the database. No belief profile exists yet.

**Action**:
```bash
API=https://api.coherencycoin.com

# GET should return empty/default profile (200, not 404)
curl -s $API/api/contributors/alice/beliefs
# Expected: HTTP 200, worldview_axes={}, concept_resonances=[], tag_affinities={}

# PATCH to set axes
curl -s -X PATCH $API/api/contributors/alice/beliefs \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $ALICE_KEY" \
  -d '{"worldview_axes": {"scientific": 0.8, "holistic": 0.6}, "tag_affinities": {"ai": 0.9}}'
# Expected: HTTP 200, returns updated profile with scientific=0.8, holistic=0.6

# GET again to confirm persistence
curl -s $API/api/contributors/alice/beliefs
# Expected: HTTP 200, worldview_axes contains scientific=0.8, holistic=0.6, tag_affinities contains ai=0.9

# PATCH again to update a single axis (merge, not replace)
curl -s -X PATCH $API/api/contributors/alice/beliefs \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $ALICE_KEY" \
  -d '{"worldview_axes": {"holistic": 0.9}}'
# Expected: HTTP 200, scientific still=0.8, holistic now=0.9 (merge, not replace)
```

**Edge**: PATCH with unknown axis `"unknown_axis": 0.5` returns HTTP 422 with message `"'unknown_axis' is not a valid BeliefAxis"`.

**Edge**: PATCH with axis value `1.5` returns HTTP 422 with message `"Axis value must be between 0.0 and 1.0"`.

---

### Scenario 2: Resonance match between contributor and idea

**Setup**: Contributor `alice` has `worldview_axes: {scientific: 0.8, holistic: 0.6}`, `tag_affinities: {ai: 0.9, "graph-theory": 0.7}`, `concept_resonances: [{concept_id: "c-emergence", score: 0.9}]`. Idea `idea-xyz` exists with `tags: ["ai", "graph-theory"]`, `concept_ids: ["c-emergence", "c-complexity"]`.

**Action**:
```bash
curl -s "$API/api/contributors/alice/beliefs/resonance?idea_id=idea-xyz"
```

**Expected**: HTTP 200, response body matches ResonanceResult schema:
```json
{
  "contributor_id": "alice",
  "idea_id": "idea-xyz",
  "overall_score": <number between 0.0 and 1.0>,
  "concept_overlap": <number > 0>,
  "worldview_alignment": <number >= 0.0>,
  "tag_match": <number > 0>,
  "explanation": ["<non-empty string>", ...],
  "recommended_action": "Contribute"
}
```

**Note**: `overall_score > 0.5` expected given significant overlap. Field MUST be `overall_score`, not `resonance_score` or `score`.

**Edge**: `?idea_id=nonexistent-idea` returns HTTP 404 with `{"detail": "Idea 'nonexistent-idea' not found"}`.

**Edge**: Contributor with empty belief profile gets `overall_score=0.0` (not an error, HTTP 200).

---

### Scenario 3: Validation rejects invalid input

**Setup**: Contributor `bob` exists.

**Actions**:
```bash
# Out-of-range axis value
curl -s -X PATCH $API/api/contributors/bob/beliefs \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $BOB_KEY" \
  -d '{"worldview_axes": {"scientific": 1.5}}'
# Expected: HTTP 422, error body mentions "must be between 0.0 and 1.0"

# Invalid axis name
curl -s -X PATCH $API/api/contributors/bob/beliefs \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $BOB_KEY" \
  -d '{"worldview_axes": {"astrology": 0.5}}'
# Expected: HTTP 422, error body mentions "'astrology' is not a valid BeliefAxis"

# Cross-contributor unauthorized update
curl -s -X PATCH $API/api/contributors/alice/beliefs \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $BOB_KEY" \
  -d '{"worldview_axes": {"scientific": 0.1}}'
# Expected: HTTP 403 Forbidden

# GET for non-existent contributor
curl -s $API/api/contributors/nonexistent-xyz/beliefs
# Expected: HTTP 404, not HTTP 200 or 500
```

---

### Scenario 4: ROI endpoint returns proof-of-working data

**Setup**: At least 10 `belief_recommendation_events` rows exist for contributor `alice` within the last 30 days. 4 out of 10 have `engaged_at` set. Network baseline is measurable.

**Action**:
```bash
curl -s "$API/api/contributors/alice/beliefs/roi?days=30"
```

**Expected**: HTTP 200, BeliefROI:
```json
{
  "contributor_id": "alice",
  "period_days": 30,
  "recommendations_shown": 10,
  "recommendations_engaged": 4,
  "engagement_rate": 0.4,
  "belief_completeness": <0.0–1.0>,
  "baseline_engagement_rate": <number or null>,
  "lift": <number or null>,
  "lift_trend": <list or null>,
  "insufficient_data_reason": null
}
```

**Edge**: If fewer than 10 recommendation events exist, response still returns HTTP 200 but:
```json
{
  "lift": null,
  "baseline_engagement_rate": null,
  "insufficient_data_reason": "Need at least 10 recommendations to compute lift"
}
```

**Edge**: `?days=0` or `?days=-1` returns HTTP 422.

---

### Scenario 5: CLI commands work end-to-end

**Setup**: User is authenticated via `cc setup`. Contributor profile exists.

**Actions**:
```bash
# List current profile
cc beliefs
# Expected: table output showing worldview axes with bar chart indicators and scores
# Output MUST show 7 axes: scientific, spiritual, pragmatic, holistic, synthetic, critical, imaginative

# Update a single axis
cc beliefs set holistic 0.8
# Expected: "✓ Updated: holistic → 0.8"

# Verify update persisted (GET must reflect the PATCH)
cc beliefs
# Expected: holistic shows 0.8 in the table

# Match against an idea
cc beliefs match <valid-idea-id>
# Expected: shows overall_score, concept_overlap, worldview_alignment, tag_match with breakdown

# Error: invalid axis
cc beliefs set nonexistent 0.5
# Expected: error message listing valid axes, non-zero exit code

# Error: value out of range
cc beliefs set scientific 2.0
# Expected: error message about range 0.0–1.0, non-zero exit code
```

---

## Risks and Assumptions

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Contributors don't fill in belief profiles | High | Onboarding prompt in Spec 162; show ROI card as motivation; seed with defaults from topics they've interacted with |
| Worldview inferences from idea tags are inaccurate | Medium | Start with explicit keyword mapping config; make it editable; track low-confidence inferences |
| Resonance scores feel arbitrary / unmotivated | Medium | Always show explanation list; make algorithm transparent; link to ROI card to show it working |
| PATCH race conditions if two clients update simultaneously | Low | Use `updated_at` optimistic locking; last-write-wins for MVP |
| Privacy: contributors may not want their worldview exposed | Medium | GET /beliefs is private (requires auth or admin); only contributor and admins can view |
| Tag mapping doesn't scale as idea tags grow | Medium | Move to embedding-based alignment in follow-up; keyword map is the MVP |
| Implementation uses wrong field names | High (prior art) | See Implementation Guard-Rails section; spec names are canonical |

---

## Known Gaps and Follow-up Tasks

1. **Implicit belief updates**: Track interaction events (idea clicked, task contributed to) to auto-update belief scores. Requires event streaming pipeline. Out of scope for this spec.
2. **Graph DB integration**: Persist belief profile as a contributor node property in Neo4j for graph-native queries (e.g., "find contributors who resonate with this cluster"). Follow-up spec.
3. **Belief-driven recommendation pipeline**: Spec 163 (Resonance Navigation) is the consumer of belief data. This spec is the producer. Integration spec needed.
4. **Embedding-based worldview alignment**: Replace keyword mapping with sentence embeddings for idea-to-axis alignment. Requires embedding pipeline. Follow-up.
5. **Social sharing of belief profiles**: Allow contributors to share their belief radar publicly. Privacy controls needed first.
6. **Belief history**: Track how belief axes change over time (a time-series view). Useful for observing growth/evolution.
7. **`GET /api/system/beliefs/effectiveness`**: Admin cohort analysis endpoint. Defined in this spec but implemented as a follow-up.

---

## Decision Gates

- `needs-decision` if any belief axis value is used to gate access to content (curation vs. access control are different concerns — access control requires separate review).
- `needs-decision` if belief profiles are used for matching contributors to paid tasks (commercial implications for fairness/bias review).

---

## Acceptance Criteria

- [ ] `GET /api/contributors/{id}/beliefs` returns BeliefProfile (200) or empty defaults (200) when profile not yet set, or 404 if contributor does not exist.
- [ ] `PATCH /api/contributors/{id}/beliefs` updates axis values by merging (not replacing), validates range [0.0, 1.0], rejects unknown axes (422), enforces ownership (403).
- [ ] `GET /api/contributors/{id}/beliefs/resonance?idea_id={id}` returns ResonanceResult with `overall_score` field and correct formula breakdown.
- [ ] `GET /api/contributors/{id}/beliefs/roi?days=30` returns BeliefROI with `lift` (or null with `insufficient_data_reason` if < 10 events).
- [ ] All 4 endpoints registered in `main.py` and return correct Pydantic-validated responses.
- [ ] `api/app/routers/beliefs.py` contains actual endpoint implementations (not a stub).
- [ ] `api/app/services/beliefs_service.py` source file exists with resonance algorithm and ROI logic.
- [ ] `api/app/models/belief_profile.py` exists with all models including exact field names (`score`, `overall_score`, 7 exact axes).
- [ ] Database migration creates `belief_profiles` and `belief_recommendation_events` tables.
- [ ] `api/tests/test_beliefs.py` exists with tests for all endpoints and edge cases.
- [ ] `cc beliefs` shows formatted table of all 7 canonical axes.
- [ ] `cc beliefs set <axis> <value>` updates a single axis with validation.
- [ ] `cc beliefs match <idea-id>` shows resonance breakdown reading `overall_score` from API.
- [ ] Web page `/contributors/{id}/beliefs` renders BeliefRadarChart, ConceptTagCloud, WorldviewSelector, BeliefROICard.
- [ ] WorldviewSelector shows all 7 canonical axes with swipeable mobile UI.
- [ ] ConceptTagCloud uses `score` field (not `weight`).
- [ ] BeliefROICard renders `lift_trend` sparkline for proof-over-time visibility.
- [ ] All Verification Scenarios pass against production.
- [ ] Belief profile data is never exposed cross-contributor without authentication.
