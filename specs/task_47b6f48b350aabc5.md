# Spec: Belief System — Per-Contributor Worldview, Interests, and Concept Preferences

**Spec ID**: task_47b6f48b350aabc5
**Parent Spec**: 169-belief-system (approved)
**Task ID**: task_47b6f48b350aabc5
**Status**: approved
**Priority**: high
**Author**: product-manager agent
**Date**: 2026-03-28
**Depends on**: Spec 169 (Belief System), Spec 008 (Graph Foundation), Spec 163 (Resonance Navigation)
**Consolidates**: task_9460b68fbf0e81f5 (prior attempt), 169-belief-system

---

## Summary

Every contributor operates from a personal worldview — a set of values, interests, and concept affinities that shape how they engage with ideas. The Belief System makes this worldview explicit, structured, and actionable within Coherence Network.

A **BeliefProfile** stores which concepts a contributor resonates with, which epistemic axes they value (scientific rigor, spiritual intuition, pragmatic utility, holistic thinking, synthetic integration, critical analysis, imaginative exploration), and which worldview framing they apply to new ideas. These preferences drive personalized news matching, idea recommendations, and contribution suggestions.

Adapted from the `UserConceptModule` and `BeliefSystemModule` in the Living Codex origin project. This spec covers the full implementation contract: data model, API, web UI, CLI, proof-of-working metrics, and mobile UX.

---

## Goal

Build a belief profile system that:

1. Stores per-contributor worldview preferences across 7 canonical axes
2. Allows contributors to explicitly set and update beliefs via API, web, and CLI
3. Computes resonance scores between a contributor's beliefs and specific ideas
4. Tracks engagement lift from belief-driven recommendations to prove the system works
5. Displays proof-of-working metrics inline — contributors see their own lift trend, not just admins

---

## Open Question Resolution: How Do We Prove It Is Working?

**Question**: How can we improve this idea, show whether it is working yet, and make that proof clearer over time?

**Answer**: The proof is measurable, compounding, and visible to the contributor — not just admins.

### Definition of "Working"

- Contributors with complete belief profiles (`belief_completeness >= 0.7`) receive idea recommendations with measurably higher engagement rates than contributors without profiles (`belief_completeness < 0.3`).
- The gap between these cohorts grows over time as profiles are refined through use.
- Individual contributors can see their own lift trend via a sparkline chart — not just a static snapshot.

### Proof Mechanism 1: `belief_recommendation_events` Table

Every recommendation shown to a contributor records:
- `contributor_id`, `idea_id`, `resonance_score`, `recommended_at`
- Populated at recommendation time — cannot be gamed retroactively

Every engagement (click, contribute, credit, comment) records:
- `engaged_at`, `engagement_type`

The `GET /api/contributors/{id}/beliefs/roi` endpoint queries this table to return:
- `engagement_lift_pct`: % improvement in engagement rate for belief-matched vs. unmatched recommendations
- `engagement_lift_trend`: 7-day sparkline of daily lift values
- `belief_completeness`: % of 7 axes set to non-zero

### Proof Mechanism 2: Network-Wide `GET /api/beliefs/roi`

Returns aggregate stats:
- `profile_adoption_rate`: fraction of contributors with ≥1 axis set
- `avg_resonance_match_rate`: mean resonance score for engaged ideas vs. all shown
- `top_worldview_axes`: most common axes across all profiles

### Proof Mechanism 3: `BeliefROICard` Web Component

Visible on the contributor's belief profile page:
- Status badge: `needs_data` (< 3 recommendations) → `improving` (lift > 0%) → `working` (lift > 15%) → `strong` (lift > 30%)
- Sparkline chart of weekly lift trend
- "Your recommendations are X% more relevant since you set your beliefs"

### Proof Mechanism 4: CLI Feedback

`cc beliefs` output includes:
- `Engagement lift: +22% (last 14 days)` when data is available
- `No data yet — make some recommendations to see lift` when too few events

---

## Acceptance Criteria

1. `GET /api/contributors/{id}/beliefs` returns full belief profile with `worldview_axes`, `concept_resonances`, `interest_tags`, `belief_completeness`, and `updated_at`.
2. `PATCH /api/contributors/{id}/beliefs` accepts partial updates; additive by default; `replace: true` replaces lists. Unknown fields return 422.
3. `GET /api/contributors/{id}/beliefs/resonance?idea_id={idea_id}` returns `resonance_score` (0.0–1.0) with breakdown showing `concept_overlap`, `worldview_alignment`, `tag_match`.
4. `GET /api/contributors/{id}/beliefs/roi` returns `engagement_lift_pct`, `engagement_lift_trend` (7 values), `belief_completeness`, and `status` badge (`needs_data` | `improving` | `working` | `strong`).
5. `GET /api/beliefs/roi` (network-wide) returns aggregate stats with `spec_ref: "spec-169"`.
6. Non-existent contributor returns 404 on all belief endpoints.
7. Invalid worldview axis name returns 422. Weight outside [0.0, 1.0] returns 422.
8. Web page `/contributors/{id}/beliefs` renders `BeliefRadarChart`, `WorldviewSelector` (swipeable on mobile), `ConceptTagCloud`, and `BeliefROICard` without console errors.
9. `BeliefRadarChart` renders with default zero-values when no axes are set (no empty-data crash).
10. `WorldviewSelector` renders as swipeable cards on mobile (< 640px wide) and as a compact grid on desktop.
11. `cc beliefs` CLI command prints formatted profile with engagement lift when available.
12. `cc beliefs set <axis> <value>` updates a single axis via PATCH.
13. `cc beliefs match <idea-id>` prints resonance score and breakdown.
14. All 14 integration tests in `api/tests/test_belief_system.py` pass.

---

## Data Model

```yaml
BeliefAxis:
  enum:
    - scientific      # values empiricism, evidence, reproducibility
    - spiritual       # values transcendence, meaning, inner experience
    - pragmatic       # values utility, outcomes, what works
    - holistic        # values whole-system thinking, interconnection
    - synthetic       # values integration of multiple frameworks
    - critical        # values questioning, deconstruction, rigor
    - imaginative     # values creativity, novel framings, possibility

ConceptResonance:
  properties:
    concept_id: { type: string, description: "concept node ID (free-form string in MVP)" }
    weight: { type: float, min: 0.0, max: 1.0 }

BeliefProfile:
  properties:
    contributor_id: { type: string, required: true }
    worldview_axes: { type: map<BeliefAxis, float[0,1]>, default: {} }
    concept_resonances: { type: list<ConceptResonance>, default: [] }
    interest_tags: { type: list<string>, default: [] }
    belief_completeness: { type: float, computed: true, description: "fraction of 7 axes with non-zero value" }
    updated_at: { type: datetime, auto: true }

BeliefPatch:
  properties:
    worldview_axes: { type: map<BeliefAxis, float[0,1]>, optional: true }
    concept_resonances: { type: list<ConceptResonance>, optional: true }
    interest_tags: { type: list<string>, optional: true }
    replace: { type: bool, default: false, description: "replaces lists instead of appending" }

ResonanceResult:
  properties:
    contributor_id: { type: string }
    idea_id: { type: string }
    resonance_score: { type: float, min: 0.0, max: 1.0 }
    breakdown:
      concept_overlap: { type: float }
      worldview_alignment: { type: float }
      tag_match: { type: float }
    matched_concepts: { type: list<string> }
    matched_axes: { type: list<string> }

BeliefROIResult:
  properties:
    contributor_id: { type: string }
    belief_completeness: { type: float }
    engagement_lift_pct: { type: float, description: "% lift vs baseline; null if < 3 events" }
    engagement_lift_trend: { type: list<float>, description: "7 daily values, oldest first" }
    status: { type: enum[needs_data, improving, working, strong] }
    recommendations_shown: { type: int }
    recommendations_engaged: { type: int }

NetworkBeliefROI:
  properties:
    contributors_with_profiles: { type: int }
    contributors_total: { type: int }
    profile_adoption_rate: { type: float }
    top_worldview_axes: { type: list<{axis: string, avg_weight: float}> }
    avg_resonance_match_rate: { type: float }
    concept_resonances_total: { type: int }
    spec_ref: { type: string, const: "spec-169" }

belief_recommendation_events:
  columns:
    id: { type: uuid, pk: true }
    contributor_id: { type: string, fk: contributors.id }
    idea_id: { type: string }
    resonance_score: { type: float }
    recommended_at: { type: datetime }
    engaged_at: { type: datetime, nullable: true }
    engagement_type: { type: string, nullable: true, enum: [click, contribute, credit, comment] }
```

**Storage**: Belief profiles stored in PostgreSQL on the `contributors` table as JSONB columns (`worldview_axes`, `concept_resonances`, `interest_tags`). The `belief_recommendation_events` table is a separate append-only table.

---

## API Contract

### `GET /api/contributors/{id}/beliefs`

Returns the full belief profile. All axes default to 0.0 in the response even if not stored (so the radar chart always has data).

**Response 200**
```json
{
  "contributor_id": "abc123",
  "worldview_axes": {
    "scientific": 0.8,
    "spiritual": 0.3,
    "pragmatic": 0.7,
    "holistic": 0.5,
    "synthetic": 0.6,
    "critical": 0.7,
    "imaginative": 0.4
  },
  "concept_resonances": [
    { "concept_id": "entropy", "weight": 0.95 },
    { "concept_id": "emergence", "weight": 0.82 }
  ],
  "interest_tags": ["entropy", "consciousness", "emergence"],
  "belief_completeness": 0.71,
  "updated_at": "2026-03-28T11:00:00Z"
}
```

**Response 404**: `{ "detail": "Contributor not found" }`

---

### `PATCH /api/contributors/{id}/beliefs`

Partial update. Additive by default (lists are appended, not replaced). `replace: true` replaces lists.

**Request body** (all fields optional)
```json
{
  "worldview_axes": { "scientific": 0.9 },
  "concept_resonances": [{ "concept_id": "entropy", "weight": 0.95 }],
  "interest_tags": ["entropy"],
  "replace": false
}
```

**Response 200**: updated belief profile (same shape as GET)

**Response 422** — validation failure:
```json
{ "detail": "worldview axis 'astral' is not a valid BeliefAxis" }
```

**Response 404**: `{ "detail": "Contributor not found" }`

---

### `GET /api/contributors/{id}/beliefs/resonance?idea_id={idea_id}`

Compute resonance score between contributor's beliefs and a specific idea.

**Response 200**
```json
{
  "contributor_id": "abc123",
  "idea_id": "idea_xyz",
  "resonance_score": 0.74,
  "breakdown": {
    "concept_overlap": 0.65,
    "worldview_alignment": 0.83,
    "tag_match": 0.70
  },
  "matched_concepts": ["entropy", "emergence"],
  "matched_axes": ["systemic", "scientific"]
}
```

**Response 422**: `{ "detail": "idea_id is required" }` — when `idea_id` param is missing

**Response 404**: `{ "detail": "Idea not found" }` or `{ "detail": "Contributor not found" }`

---

### `GET /api/contributors/{id}/beliefs/roi`

Per-contributor proof-of-working metrics.

**Response 200**
```json
{
  "contributor_id": "abc123",
  "belief_completeness": 0.71,
  "engagement_lift_pct": 22.4,
  "engagement_lift_trend": [0.0, 5.2, 8.1, 12.3, 15.0, 19.4, 22.4],
  "status": "working",
  "recommendations_shown": 147,
  "recommendations_engaged": 61
}
```

When insufficient data (< 3 recommendation events):
```json
{
  "contributor_id": "abc123",
  "belief_completeness": 0.14,
  "engagement_lift_pct": null,
  "engagement_lift_trend": [],
  "status": "needs_data",
  "recommendations_shown": 1,
  "recommendations_engaged": 0
}
```

---

### `GET /api/beliefs/roi`

Network-wide aggregate stats.

**Response 200**
```json
{
  "contributors_with_profiles": 42,
  "contributors_total": 100,
  "profile_adoption_rate": 0.42,
  "top_worldview_axes": [
    { "axis": "pragmatic", "avg_weight": 0.71 },
    { "axis": "scientific", "avg_weight": 0.68 }
  ],
  "avg_resonance_match_rate": 0.63,
  "concept_resonances_total": 312,
  "spec_ref": "spec-169"
}
```

---

## Resonance Scoring Algorithm

```
resonance_score = 0.4 * concept_overlap + 0.4 * worldview_alignment + 0.2 * tag_match
```

Where:
- **concept_overlap**: Jaccard-weighted similarity between contributor's `concept_resonances` and the idea's concept tags. Defaults to 0.5 (neutral) when either side has no concept data.
- **worldview_alignment**: Cosine-like dot product between contributor's 7-axis worldview vector and the idea's inferred axis weights (derived from its concepts and text). Normalized to [0, 1]. Defaults to 0.5 when idea has no axis data.
- **tag_match**: Fraction of contributor's `interest_tags` present in the idea's tags. Defaults to 0.5 when either side has no tags.

**Score interpretation**:
- < 0.3: low resonance (grey badge in UI)
- 0.3–0.7: moderate resonance (default styling)
- > 0.7: high resonance (highlighted, surfaced first)

**Constraint**: Algorithm weights must sum to 1.0. Current: 0.4 + 0.4 + 0.2 = 1.0 ✓

---

## Files to Create / Modify

```
api/
  app/
    routers/beliefs.py                      # CREATE — route handlers for all belief endpoints
    services/belief_service.py              # CREATE — resonance scoring, PATCH merge, ROI calc
    models/belief.py                        # CREATE — Pydantic models: BeliefProfile, BeliefPatch, etc.
  db/
    migrations/add_belief_columns.sql       # CREATE — JSONB columns + belief_recommendation_events table
  main.py                                   # MODIFY — register beliefs router
  tests/
    test_belief_system.py                   # CREATE — 14 integration tests

web/
  src/
    app/
      contributors/[id]/beliefs/page.tsx    # CREATE — belief profile page
    components/
      beliefs/
        BeliefRadarChart.tsx                # CREATE — hexagonal radar chart (Recharts)
        ConceptTagCloud.tsx                 # CREATE — tag cloud sized by weight
        WorldviewSelector.tsx               # CREATE — axis sliders / swipeable cards (mobile)
        BeliefROICard.tsx                   # CREATE — status badge + sparkline chart
```

---

## CLI Commands

```bash
# Show my belief profile
cc beliefs

# Set a worldview axis value
cc beliefs set scientific 0.9
cc beliefs set holistic 0.4

# Add concept resonance
cc beliefs add-concept entropy 0.95

# See how well my beliefs match an idea
cc beliefs match <idea-id>

# See resonance breakdown
cc beliefs match <idea-id> --verbose
```

Expected output of `cc beliefs`:
```
Belief Profile — @handle
────────────────────────────────────────────────
Worldview Axes:
  scientific   ████████░░  0.80
  pragmatic    ███████░░░  0.70
  critical     ███████░░░  0.70
  holistic     █████░░░░░  0.50
  synthetic    ██████░░░░  0.60
  imaginative  ████░░░░░░  0.40
  spiritual    ███░░░░░░░  0.30

Concept Resonances (top 5):
  entropy (0.95), emergence (0.82), coherence (0.78)

Interest Tags: #entropy #consciousness #emergence

Engagement lift: +22% (last 14 days)
Profile completeness: 71%
```

---

## Web UI

**Route**: `/contributors/{id}/beliefs`

### BeliefRadarChart

- Hexagonal radar chart of the 7 worldview axes using Recharts `RadarChart`
- Mobile-responsive, min height 280px
- When all axes are 0.0, renders a small "set your beliefs to see your chart" placeholder inside the chart area — does NOT crash or show empty SVG
- Axes labelled with short descriptions on hover/tap

### ConceptTagCloud

- Word cloud of `interest_tags` and top `concept_resonances`, sized by weight
- Clickable tags navigate to `/concepts/{id}`
- Renders empty state ("add concept interests to see your cloud") when no data

### WorldviewSelector

- Six/seven axis sliders (0–100 range, step 1)
- **Desktop** (≥ 640px): compact 2-column grid layout
- **Mobile** (< 640px): swipeable cards — one axis per card, horizontal swipe to navigate, vertical swipe to adjust value
- Save button sends PATCH request; optimistic update with rollback on 4xx/5xx
- Debounce: 500ms on slider change before sending PATCH

### BeliefROICard

- Status badge: `needs_data` (grey) → `improving` (yellow) → `working` (green) → `strong` (blue)
- Sparkline: 7-day engagement lift trend line
- Text: "Your recommendations are {lift}% more relevant since you set your beliefs"
- Empty state: "Keep using the network to see your engagement lift data"

---

## Migration SQL

```sql
-- Add JSONB columns to contributors table
ALTER TABLE contributors
  ADD COLUMN IF NOT EXISTS worldview_axes JSONB NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS concept_resonances JSONB NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS interest_tags JSONB NOT NULL DEFAULT '[]'::jsonb;

-- Append-only events table for ROI tracking
CREATE TABLE IF NOT EXISTS belief_recommendation_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  contributor_id TEXT NOT NULL REFERENCES contributors(id) ON DELETE CASCADE,
  idea_id TEXT NOT NULL,
  resonance_score FLOAT NOT NULL CHECK (resonance_score >= 0.0 AND resonance_score <= 1.0),
  recommended_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  engaged_at TIMESTAMPTZ,
  engagement_type TEXT CHECK (engagement_type IN ('click', 'contribute', 'credit', 'comment'))
);

CREATE INDEX IF NOT EXISTS idx_belief_events_contributor
  ON belief_recommendation_events (contributor_id, recommended_at DESC);
```

---

## Verification Scenarios

### Scenario 1 — Full CRUD cycle (create, read, update, verify additive)

**Setup**: Contributor `abc123` exists. Beliefs are initially empty.

**Actions**:
```bash
API=https://api.coherencycoin.com

# 1. Read initial empty profile
curl -s $API/api/contributors/abc123/beliefs
# Expected: HTTP 200, worldview_axes={}, concept_resonances=[], interest_tags=[], belief_completeness=0.0

# 2. Set worldview axes + interest tags
curl -s -X PATCH $API/api/contributors/abc123/beliefs \
  -H "Content-Type: application/json" \
  -d '{"worldview_axes":{"scientific":0.9,"pragmatic":0.7},"interest_tags":["entropy"]}'
# Expected: HTTP 200, worldview_axes.scientific=0.9, interest_tags=["entropy"]

# 3. Additive PATCH — append tag only
curl -s -X PATCH $API/api/contributors/abc123/beliefs \
  -H "Content-Type: application/json" \
  -d '{"interest_tags":["emergence"]}'
# Expected: HTTP 200, interest_tags=["entropy","emergence"] (both present)

# 4. Replace PATCH — replace tags entirely
curl -s -X PATCH $API/api/contributors/abc123/beliefs \
  -H "Content-Type: application/json" \
  -d '{"interest_tags":["coherence"],"replace":true}'
# Expected: HTTP 200, interest_tags=["coherence"] (previous tags gone)

# 5. Verify final state
curl -s $API/api/contributors/abc123/beliefs | jq '{axes: .worldview_axes, tags: .interest_tags}'
# Expected: {axes: {scientific: 0.9, pragmatic: 0.7}, tags: ["coherence"]}
```

**Edge**: `PATCH` with `replace: true` on `worldview_axes` replaces all axes (not merge).

---

### Scenario 2 — Resonance match against an idea

**Setup**: Contributor `abc123` has `worldview_axes: {scientific: 0.9, pragmatic: 0.7}` and `interest_tags: ["entropy","emergence"]`. Idea `idea_xyz` exists with tags `["entropy","complexity"]`.

**Actions**:
```bash
# 1. Resonance match
curl -s "$API/api/contributors/abc123/beliefs/resonance?idea_id=idea_xyz"
# Expected: HTTP 200, resonance_score between 0.0-1.0, breakdown object present,
#           matched_concepts contains "entropy" (or is empty if idea has no concept nodes)

# 2. Missing idea_id param
curl -s "$API/api/contributors/abc123/beliefs/resonance"
# Expected: HTTP 422, {"detail": "idea_id is required"}

# 3. Non-existent idea
curl -s "$API/api/contributors/abc123/beliefs/resonance?idea_id=nonexistent_zzz999"
# Expected: HTTP 404, {"detail": "Idea not found"}
```

**Constraint**: `resonance_score` must be in [0.0, 1.0]. `breakdown` values must each be in [0.0, 1.0].

---

### Scenario 3 — Validation errors

**Setup**: Contributor `abc123` exists.

**Actions**:
```bash
# Invalid axis name
curl -s -X PATCH $API/api/contributors/abc123/beliefs \
  -H "Content-Type: application/json" \
  -d '{"worldview_axes":{"astral":0.5}}'
# Expected: HTTP 422, detail mentions "astral" is not a valid BeliefAxis

# Weight out of range (> 1.0)
curl -s -X PATCH $API/api/contributors/abc123/beliefs \
  -H "Content-Type: application/json" \
  -d '{"worldview_axes":{"scientific":1.5}}'
# Expected: HTTP 422, detail mentions weight out of range

# Negative weight
curl -s -X PATCH $API/api/contributors/abc123/beliefs \
  -H "Content-Type: application/json" \
  -d '{"worldview_axes":{"scientific":-0.1}}'
# Expected: HTTP 422

# Unknown top-level field
curl -s -X PATCH $API/api/contributors/abc123/beliefs \
  -H "Content-Type: application/json" \
  -d '{"unknown_field":"value"}'
# Expected: HTTP 422
```

---

### Scenario 4 — Non-existent contributor (404 on all endpoints)

**Setup**: No contributor with ID `ghost999`.

**Actions**:
```bash
curl -s $API/api/contributors/ghost999/beliefs
# Expected: HTTP 404, {"detail": "Contributor not found"}

curl -s -X PATCH $API/api/contributors/ghost999/beliefs \
  -H "Content-Type: application/json" \
  -d '{"interest_tags":["entropy"]}'
# Expected: HTTP 404, {"detail": "Contributor not found"}

curl -s "$API/api/contributors/ghost999/beliefs/resonance?idea_id=idea_xyz"
# Expected: HTTP 404, {"detail": "Contributor not found"}

curl -s "$API/api/contributors/ghost999/beliefs/roi"
# Expected: HTTP 404, {"detail": "Contributor not found"}
```

---

### Scenario 5 — Network ROI endpoint and zero-data edge cases

**Setup**: At least 2 contributors exist; one has axes set (abc123), one does not.

**Actions**:
```bash
# Network-wide ROI
curl -s $API/api/beliefs/roi
# Expected: HTTP 200
#   contributors_with_profiles >= 1
#   contributors_total >= 2
#   profile_adoption_rate between 0.0-1.0
#   top_worldview_axes: list with >= 1 entry
#   spec_ref == "spec-169"

# Per-contributor ROI (abc123 — newly set, insufficient events)
curl -s $API/api/contributors/abc123/beliefs/roi
# Expected: HTTP 200
#   status == "needs_data"
#   engagement_lift_pct == null
#   engagement_lift_trend == []
#   belief_completeness > 0.0 (axes were set in scenario 1)
```

**Edge**: Zero contributors — `GET /api/beliefs/roi` returns HTTP 200 with
`contributors_with_profiles=0, contributors_total=0, profile_adoption_rate=0.0, top_worldview_axes=[]`.

---

## Risks and Assumptions

- **Assumption**: Contributor IDs from TOFU onboarding spec (168) are used as `{id}` in belief endpoints. If handles differ from internal IDs, the router must support both (handle lookup + UUID fallback).
- **Risk**: Resonance scoring is heuristic. Low-quality idea concept tags produce meaningless scores. Mitigation: surface a "low data" badge when idea has fewer than 2 concept tags; default component scores to 0.5 (neutral) when data is absent.
- **Risk**: JSONB column migration on a live `contributors` table. Mitigation: `ADD COLUMN ... DEFAULT '{}'::jsonb` is non-blocking on PostgreSQL 11+.
- **Risk**: Recharts `RadarChart` errors on empty data arrays. Mitigation: API always returns all 7 axes defaulting to 0.0; never return null or missing axes.
- **Risk**: Mobile swipeable cards add complexity. Mitigation: MVP ships with sliders on all devices; swipeable cards are a progressive enhancement using CSS `scroll-snap-type` (no external library).
- **Assumption**: `belief_recommendation_events` table is populated by the recommendation engine (separate spec). The ROI endpoint must gracefully handle zero rows (return `status: "needs_data"`, not 500).

---

## Known Gaps and Follow-up Tasks

- CLI implementation: `cc beliefs`, `cc beliefs set`, `cc beliefs match` (follow-up task).
- Belief-driven feed ranking integration (follow-up spec: "personalized idea feed").
- Cross-contributor similarity search ("who thinks like me") — follow-up spec.
- Concept ID validation against the concept graph (currently free-form strings in MVP).
- Belief profile history / audit log (follow-up).
- `GET /api/beliefs/analytics` dashboard endpoint (follow-up spec).
- Push notifications for high-resonance new ideas (follow-up spec).

---

## Implementation Guard-Rails (Common Mistakes to Avoid)

1. **Do not** return `null` for any axis in the `worldview_axes` map — always return 0.0 as the default. Recharts will error on null radar data.
2. **Do not** add new columns to `contributors` without a corresponding migration file. The test conftest.py must apply the migration before tests run.
3. **Do not** error with 500 when an idea has no concept tags — return neutral score 0.5 for that component.
4. **Do not** make PATCH replace-by-default — replace only when `replace: true` is explicitly sent. This is a safety rail to prevent accidental data loss.
5. **Do not** compute `belief_completeness` in the client — compute it server-side as `len([v for v in axes.values() if v > 0]) / 7`.
6. **Do not** hardcode 6 axes — the system uses 7 axes: `scientific, spiritual, pragmatic, holistic, synthetic, critical, imaginative`.
7. **Always** validate that resonance algorithm weights sum to 1.0 in a unit test.

---

## Task Card

```yaml
goal: implement per-contributor belief profiles with resonance scoring and ROI proof
files_allowed:
  - api/app/routers/beliefs.py
  - api/app/services/belief_service.py
  - api/app/models/belief.py
  - api/app/db/migrations/add_belief_columns.sql
  - api/main.py
  - api/tests/test_belief_system.py
  - web/src/app/contributors/[id]/beliefs/page.tsx
  - web/src/components/beliefs/BeliefRadarChart.tsx
  - web/src/components/beliefs/ConceptTagCloud.tsx
  - web/src/components/beliefs/WorldviewSelector.tsx
  - web/src/components/beliefs/BeliefROICard.tsx
done_when:
  - GET /api/contributors/{id}/beliefs returns 200 with 7-axis profile, defaults to 0.0
  - PATCH /api/contributors/{id}/beliefs returns 200, additive by default
  - GET /api/contributors/{id}/beliefs/resonance?idea_id=X returns resonance_score 0.0-1.0
  - GET /api/contributors/{id}/beliefs/roi returns status badge + trend data
  - GET /api/beliefs/roi returns network stats with spec_ref="spec-169"
  - pytest api/tests/test_belief_system.py — 14/14 pass
  - web page /contributors/{id}/beliefs renders all 4 components without console errors
commands:
  - pytest api/tests/test_belief_system.py -v
  - cd web && npm run build
constraints:
  - Do not modify existing contributor auth/session logic
  - Belief PATCH is additive by default (replace: false)
  - Resonance algorithm weights must sum to 1.0
  - No new external dependencies beyond recharts (already in web)
  - 7 axes only: scientific, spiritual, pragmatic, holistic, synthetic, critical, imaginative
  - ROI endpoint must not 500 when belief_recommendation_events is empty
```

---

## Metadata

- **Spec ID**: task_47b6f48b350aabc5
- **Task ID**: task_47b6f48b350aabc5
- **Author**: product-manager agent
- **Date**: 2026-03-28
- **Status**: approved
- **Consolidates**: 169-belief-system, task_9460b68fbf0e81f5
- **Depends on**: Spec 169 (Belief System base), Spec 168 (TOFU Onboarding), Spec 163 (Resonance Navigation), Spec 048 (Contributions API)
- **Blocks**: personalized idea feed spec (follow-up), belief-driven contribution suggestions (follow-up), belief analytics dashboard (follow-up)
