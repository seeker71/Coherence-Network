# Spec 169: Belief System — Per-Contributor Worldview, Interests, and Concept Preferences

**Spec ID**: 169-belief-system
**Task ID**: task_1a8dc28c427da8d8
**Status**: draft
**Priority**: high
**Author**: product-manager agent
**Date**: 2026-03-28
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

### The proof problem

The key open question: *How can we show that belief profiles are actually working?* The answer must be measurable. We define working as: contributors with complete belief profiles receive idea recommendations with higher engagement rates (click, contribute, comment, credit) than contributors without. The spec includes explicit ROI tracking hooks from day one so that proof accumulates automatically over time.

---

## Goals

1. Store a **BeliefProfile** per contributor: worldview axes, concept resonances, tag affinities.
2. Expose `GET /api/contributors/{id}/beliefs` and `PATCH /api/contributors/{id}/beliefs` for profile read/update.
3. Expose `GET /api/contributors/{id}/beliefs/resonance?idea_id={id}` to score alignment between a contributor's beliefs and a specific idea.
4. Expose `GET /api/contributors/{id}/beliefs/roi` to show proof-of-working: engagement lift attributable to belief-driven recommendations.
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

### ResonanceResult

Returned by the resonance match endpoint.

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

Returns the contributor's current belief profile.

**Response 200**:
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

**Response 404**: contributor not found
**Response 404**: belief profile not yet initialized (returns empty profile with defaults)

---

### PATCH /api/contributors/{id}/beliefs

Partial update of the belief profile. Any field omitted is left unchanged. Axes are merged (not replaced), so you can update a single axis without sending all seven.

**Request body**:
```json
{
  "worldview_axes": {"scientific": 0.9},
  "tag_affinities": {"quantum-computing": 0.8},
  "primary_worldview": "scientific"
}
```

**Response 200**: updated BeliefProfile
**Response 422**: axis value out of range [0.0, 1.0]
**Response 422**: unknown BeliefAxis key
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

**Response 200**: ResonanceResult
**Response 404**: contributor or idea not found
**Response 200 with score=0.0**: valid response when no overlap exists (not an error)

---

### GET /api/contributors/{id}/beliefs/roi?days=30

Returns engagement lift attributable to belief-driven recommendations over the last N days.

**Response 200**: BeliefROI
**Response 404**: contributor not found
**Response 200 with null lift**: valid when baseline data is insufficient (< 10 recommendations shown)

---

## Files to Create or Modify

### New files

| Path | Purpose |
|------|---------|
| `api/app/routers/beliefs.py` | FastAPI router with all 4 belief endpoints |
| `api/app/services/beliefs_service.py` | Business logic: resonance algorithm, ROI calculation, CRUD |
| `api/app/models/belief_profile.py` | Pydantic models: BeliefProfile, BeliefAxis, ConceptResonance, ResonanceResult, BeliefROI |
| `api/alembic/versions/xxxx_add_belief_profiles.py` | DB migration: belief_profiles + belief_recommendation_events tables |
| `api/tests/test_beliefs.py` | Pytest tests covering all endpoints and edge cases |
| `web/src/components/beliefs/BeliefRadarChart.tsx` | Radar chart visualizing worldview_axes (Recharts/Chart.js) |
| `web/src/components/beliefs/ConceptTagCloud.tsx` | Tag cloud of concept resonances, sized by score |
| `web/src/components/beliefs/WorldviewSelector.tsx` | Swipeable card selector for the 7 worldview axes |
| `web/src/components/beliefs/BeliefROICard.tsx` | Card showing engagement lift proof-of-working metrics |
| `web/src/app/contributors/[id]/beliefs/page.tsx` | Next.js page at `/contributors/{id}/beliefs` |

### Modified files

| Path | Change |
|------|--------|
| `api/app/main.py` | Register `beliefs` router |
| `api/app/routers/__init__.py` | Export beliefs router |
| `web/src/app/contributors/[id]/page.tsx` | Add link/tab to beliefs sub-page |

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
- Spider/radar chart with 7 axes (one per BeliefAxis).
- Each axis extends 0.0 → 1.0 from center.
- Rendered with Recharts `RadarChart` or equivalent.
- Mobile: full-width, touch-friendly hover tooltips.

**WorldviewSelector**
- 7 swipeable cards, one per axis.
- Each card: axis name, description (one sentence), current value as a large number + progress bar.
- User can tap +/- buttons or drag slider to set value.
- Saves via PATCH on blur/swipe-away (debounced 500ms).
- No long form — each card is a single focused choice.

**ConceptTagCloud**
- Tags sized by resonance score (0.5→1.0 maps to font-size 12px→24px).
- Click a tag to see concept details or navigate to concept page.
- Add/remove concepts via an autocomplete input below the cloud.

**BeliefROICard**
- Shows: recommendations shown, engaged, engagement rate, baseline, lift.
- Color-coded: green lift (>0), gray (insufficient data), red (-lift).
- "How this works" info icon with explanation: "Ideas matched to your beliefs. Higher engagement means your beliefs are well-tuned."
- Updates daily (or on page load with cache).

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
        overall_score=round(overall, 3),
        concept_overlap=round(concept_overlap, 3),
        worldview_alignment=round(worldview_alignment, 3),
        tag_match=round(tag_match, 3),
        explanation=explanation,
        recommended_action=action,
    )
```

The `infer_idea_worldview` function maps idea tags/categories to belief axes via a lightweight keyword mapping (e.g., `["empirical", "data", "experiment"]` → `scientific`, `["systems", "network", "emergence"]` → `holistic`). This mapping lives in a config file and can be extended without code changes.

---

## Proof of Working

The belief system is only working if it demonstrably improves engagement. The proof mechanism:

1. **On recommendation shown**: insert a `belief_recommendation_events` row with `resonance_score` and `shown_at`.
2. **On engagement**: update the row with `engaged_at` and `engagement_type`.
3. **ROI endpoint**: queries these rows to compute `engagement_rate = engaged / shown`.
4. **Baseline**: compute the network-wide average engagement rate for ideas shown without belief scoring.
5. **Lift**: `engagement_rate - baseline_engagement_rate`.
6. **Thresholds**:
   - `lift >= 0.05` → system is working (5 percentage point improvement).
   - `lift < 0` → belief profiles are miscalibrated; surface warning in BeliefROICard.

### Additional proof signals

- Contributors with `belief_completeness >= 0.7` should show higher lift than those with `< 0.3`.
- After a contributor updates a belief axis, track whether their subsequent recommendations improve (before/after comparison).
- Monthly system-level report: `GET /api/system/beliefs/effectiveness` (admin only) — cohort analysis of completeness vs. engagement.

---

## Verification Scenarios

### Scenario 1: Full CRUD cycle for a belief profile

**Setup**: Contributor `alice` exists in the database. No belief profile exists yet.

**Action**:
```bash
# GET should return empty/default profile
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
# Expected: HTTP 200, worldview_axes contains scientific=0.8, holistic=0.6
```

**Edge**: PATCH with unknown axis `"unknown_axis": 0.5` returns HTTP 422 with message `"'unknown_axis' is not a valid BeliefAxis"`.

---

### Scenario 2: Resonance match between contributor and idea

**Setup**: Contributor `alice` has `worldview_axes: {scientific: 0.8, holistic: 0.6}`, `tag_affinities: {ai: 0.9, "graph-theory": 0.7}`, `concept_resonances: [{concept_id: "c-emergence", score: 0.9}]`. Idea `idea-xyz` exists with `tags: ["ai", "graph-theory"]`, `concept_ids: ["c-emergence", "c-complexity"]`.

**Action**:
```bash
curl -s "$API/api/contributors/alice/beliefs/resonance?idea_id=idea-xyz"
```

**Expected**: HTTP 200, `overall_score > 0.5`, `concept_overlap > 0` (shares `c-emergence`), `tag_match > 0` (shares `ai`, `graph-theory`), `explanation` is a non-empty list of strings, `recommended_action` is `"Contribute"` or `"Follow"`.

**Edge**: `?idea_id=nonexistent-idea` returns HTTP 404 with `{"detail": "Idea 'nonexistent-idea' not found"}`.

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
# Expected: HTTP 422, error mentions value must be 0.0–1.0

# Invalid axis name
curl -s -X PATCH $API/api/contributors/bob/beliefs \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $BOB_KEY" \
  -d '{"worldview_axes": {"astrology": 0.5}}'
# Expected: HTTP 422, error mentions 'astrology' is not a valid BeliefAxis

# Another contributor trying to update alice's profile
curl -s -X PATCH $API/api/contributors/alice/beliefs \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $BOB_KEY" \
  -d '{"worldview_axes": {"scientific": 0.1}}'
# Expected: HTTP 403 Forbidden
```

---

### Scenario 4: ROI endpoint returns correct proof-of-working data

**Setup**: At least 10 `belief_recommendation_events` rows exist for contributor `alice` within the last 30 days. 4 out of 10 have `engaged_at` set. Network baseline is 0.2 (20% engagement rate).

**Action**:
```bash
curl -s "$API/api/contributors/alice/beliefs/roi?days=30"
```

**Expected**: HTTP 200, `recommendations_shown=10`, `recommendations_engaged=4`, `engagement_rate=0.4`, `baseline_engagement_rate=0.2`, `lift=0.2` (positive lift).

**Edge**: If fewer than 10 recommendation events exist, response still returns HTTP 200 but `lift=null` and `baseline_engagement_rate=null` with a note: `"Insufficient data — need at least 10 recommendations to compute lift"`.

---

### Scenario 5: CLI commands work end-to-end

**Setup**: User is authenticated via `cc setup`. Contributor profile exists with some axes set.

**Actions**:
```bash
# List current profile
cc beliefs
# Expected: table output showing 7 axes with bar chart indicators and scores

# Update a single axis
cc beliefs set holistic 0.8
# Expected: "✓ Updated: holistic → 0.8"

# Verify update persisted
cc beliefs
# Expected: holistic shows 0.8 in the table

# Match against an idea
cc beliefs match <valid-idea-id>
# Expected: resonance score printed with breakdown (concept_overlap, worldview_alignment, tag_match)

# Error: invalid axis
cc beliefs set nonexistent 0.5
# Expected: error message listing valid axes, non-zero exit code
```

---

## Risks and Assumptions

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Contributors don't fill in belief profiles | High | Onboarding prompt in Spec 162; show ROI card as motivation; seed with defaults from topics they've interacted with |
| Worldview inferences from idea tags are inaccurate | Medium | Start with explicit keyword mapping config; make it editable; track low-confidence inferences |
| Resonance scores feel arbitrary / unmotivated | Medium | Always show explanation list; make algorithm transparent; link to ROI card to show it working |
| PATCH race conditions if two clients update simultaneously | Low | Use `updated_at` optimistic locking; last-write-wins for MVP, add ETag header in follow-up |
| Privacy: contributors may not want their worldview exposed | Medium | GET /beliefs is private (requires auth or admin); only contributor and admins can view |
| Tag mapping doesn't scale as idea tags grow | Medium | Move to embedding-based alignment in follow-up; keyword map is the MVP |

---

## Known Gaps and Follow-up Tasks

1. **Implicit belief updates**: Track interaction events (idea clicked, task contributed to) to auto-update belief scores. Requires event streaming pipeline. Out of scope for this spec.
2. **Graph DB integration**: Persist belief profile as a contributor node property in Neo4j for graph-native queries (e.g., "find contributors who resonate with this cluster"). Follow-up spec.
3. **Belief-driven recommendation pipeline**: Spec 163 (Resonance Navigation) is the consumer of belief data. This spec is the producer. Integration spec needed.
4. **Embedding-based worldview alignment**: Replace keyword mapping with sentence embeddings for idea-to-axis alignment. Requires embedding pipeline. Follow-up.
5. **Social sharing of belief profiles**: Allow contributors to share their belief radar publicly. Privacy controls needed first.
6. **Belief history**: Track how belief axes change over time (a time-series view). Useful for observing growth/evolution.

---

## Decision Gates

- `needs-decision` if any belief axis value is used to gate access to content (curation vs. access control are different concerns — access control requires separate review).
- `needs-decision` if belief profiles are used for matching contributors to paid tasks (commercial implications for fairness/bias review).

---

## Acceptance Criteria

- [ ] `GET /api/contributors/{id}/beliefs` returns a BeliefProfile (200) or empty defaults (200) or 404 if contributor not found.
- [ ] `PATCH /api/contributors/{id}/beliefs` updates axis values, validates range [0.0, 1.0], rejects unknown axes (422), enforces ownership (403).
- [ ] `GET /api/contributors/{id}/beliefs/resonance?idea_id={id}` returns ResonanceResult with correct formula breakdown.
- [ ] `GET /api/contributors/{id}/beliefs/roi?days=30` returns BeliefROI with lift (or null if insufficient data).
- [ ] All 4 endpoints are registered in `main.py` and return correct Pydantic-validated responses.
- [ ] Database migration creates `belief_profiles` and `belief_recommendation_events` tables.
- [ ] `cc beliefs` shows formatted table of current contributor's axes.
- [ ] `cc beliefs set <axis> <value>` updates a single axis with validation.
- [ ] `cc beliefs match <idea-id>` shows resonance breakdown.
- [ ] Web page `/contributors/{id}/beliefs` renders BeliefRadarChart, ConceptTagCloud, WorldviewSelector, BeliefROICard.
- [ ] WorldviewSelector uses swipeable cards on mobile, not a long form.
- [ ] ROI card shows engagement lift with green/red/gray color coding.
- [ ] All Verification Scenarios pass against production.
- [ ] Belief profile data is never exposed cross-contributor without authentication.
