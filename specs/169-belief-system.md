# Spec 169 — Belief System: Per-Contributor Worldview, Interests, and Concept Preferences

## Goal

Every contributor carries a belief profile — a structured worldview that captures which
concepts they resonate with, which axes of reasoning they value, and which epistemic stance
they approach ideas from. The belief system powers personalized news matching, idea
recommendations, and contribution suggestions, making the network feel like it *knows* each
contributor rather than presenting one-size-fits-all feeds.

## Problem

- Without contributor-specific worldviews, idea recommendations are generic and low-signal.
- The same idea means different things to a systems-thinker versus a spiritual practitioner.
- Contributors have no way to express their epistemic identity, reducing engagement and
  attribution alignment.
- The Living Codex `UserConceptModule` defines a proven pattern for this; we adapt it here.

## Solution

A **belief profile** is attached to each contributor and exposes:

1. **Concept resonances** — which concept nodes the contributor finds most meaningful (0.0–1.0 weight).
2. **Worldview axes** — epistemic stance across named axes (e.g., `scientific`, `spiritual`,
   `pragmatic`, `holistic`, `relational`, `systemic`).
3. **Interest tags** — free-form concept tags the contributor actively follows.
4. **Resonance match score** — how well a given idea aligns with the contributor's profile.

The web exposes a profile page with a radar chart, tag cloud, and worldview selector.
The CLI exposes `cc beliefs`, `cc beliefs set`, and `cc beliefs match`.

---

## Acceptance Criteria

1. `GET /api/contributors/{id}/beliefs` returns the full belief profile for a contributor,
   including `worldview_axes`, `concept_resonances`, `interest_tags`, and `updated_at`.
2. `PATCH /api/contributors/{id}/beliefs` accepts a partial update to any belief fields;
   unknown fields are rejected with 422.
3. `GET /api/contributors/{id}/beliefs/resonance?idea_id={idea_id}` returns a resonance
   score (0.0–1.0) and a breakdown showing which concepts and axes contributed.
4. A non-existent contributor returns 404 on all belief endpoints.
5. Worldview axes are validated against an enum; invalid values return 422.
6. Concept resonance weights are clamped to [0.0, 1.0]; values outside range return 422.
7. Belief updates are additive (PATCH semantics): sending `{"interest_tags": ["entropy"]}`
   appends, does not replace existing tags, unless `replace: true` is included.
8. ROI endpoint `GET /api/beliefs/roi` returns aggregate network stats: contributors with
   profiles, most common worldview axes, resonance match rate, and `spec_ref: spec-169`.
9. All 12 integration tests in `api/tests/test_belief_system.py` pass.

---

## API Contract

### `GET /api/contributors/{id}/beliefs`

**Path params**
- `id`: contributor UUID or handle (string)

**Response 200**
```json
{
  "contributor_id": "abc123",
  "worldview_axes": {
    "scientific": 0.8,
    "spiritual": 0.3,
    "pragmatic": 0.7,
    "holistic": 0.5,
    "relational": 0.6,
    "systemic": 0.9
  },
  "concept_resonances": [
    { "concept_id": "entropy", "weight": 0.95 },
    { "concept_id": "emergence", "weight": 0.82 }
  ],
  "interest_tags": ["entropy", "consciousness", "emergence"],
  "updated_at": "2026-03-28T11:00:00Z"
}
```

**Response 404**
```json
{ "detail": "Contributor not found" }
```

---

### `PATCH /api/contributors/{id}/beliefs`

**Request body** (all fields optional)
```json
{
  "worldview_axes": { "scientific": 0.9 },
  "concept_resonances": [{ "concept_id": "entropy", "weight": 0.95 }],
  "interest_tags": ["entropy"],
  "replace": false
}
```

**Response 200** — updated belief profile (same shape as GET)

**Response 422** — validation failure (bad axis name, weight out of range, unknown field)
```json
{ "detail": "worldview axis 'random_axis' is not a valid BeliefAxis" }
```

**Response 404** — contributor not found

---

### `GET /api/contributors/{id}/beliefs/resonance?idea_id={idea_id}`

**Query params**
- `idea_id`: string (required)

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

**Response 404** — contributor or idea not found
```json
{ "detail": "Idea not found" }
```

**Response 422** — missing idea_id param
```json
{ "detail": "idea_id is required" }
```

---

### `GET /api/beliefs/roi`

**Response 200**
```json
{
  "contributors_with_profiles": 42,
  "contributors_total": 100,
  "profile_adoption_rate": 0.42,
  "top_worldview_axes": [
    { "axis": "systemic", "avg_weight": 0.71 },
    { "axis": "pragmatic", "avg_weight": 0.68 }
  ],
  "avg_resonance_match_rate": 0.63,
  "concept_resonances_total": 312,
  "spec_ref": "spec-169"
}
```

---

## Data Model

```yaml
BeliefAxis:
  enum:
    - scientific
    - spiritual
    - pragmatic
    - holistic
    - relational
    - systemic

ConceptResonance:
  properties:
    concept_id: { type: string, description: "ID of an existing concept node" }
    weight: { type: float, min: 0.0, max: 1.0 }

BeliefProfile:
  properties:
    contributor_id: { type: string, required: true }
    worldview_axes: { type: map<BeliefAxis, float[0,1]>, default: {} }
    concept_resonances: { type: list<ConceptResonance>, default: [] }
    interest_tags: { type: list<string>, default: [] }
    replace: { type: bool, default: false, description: "PATCH only — replaces lists instead of appending" }
    updated_at: { type: datetime, auto: true }

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
```

**Storage**: Belief profiles stored in PostgreSQL on the `contributors` table as JSONB columns
(`worldview_axes`, `concept_resonances`, `interest_tags`). No new table needed for MVP.

---

## Files to Create/Modify

- `api/app/routers/beliefs.py` — route handlers for all belief endpoints
- `api/app/services/belief_service.py` — business logic: resonance scoring, PATCH merge
- `api/app/models/belief.py` — Pydantic models: `BeliefProfile`, `BeliefPatch`, `ResonanceResult`, `BeliefAxis` enum
- `api/app/db/migrations/add_belief_columns.sql` — JSONB columns on contributors table
- `api/main.py` — register beliefs router
- `api/tests/test_belief_system.py` — 12 integration tests
- `web/src/app/profile/[handle]/beliefs/page.tsx` — belief radar chart + tag cloud + worldview selector
- `web/src/components/beliefs/BeliefRadarChart.tsx` — radar chart component (recharts)
- `web/src/components/beliefs/ConceptTagCloud.tsx` — tag cloud component
- `web/src/components/beliefs/WorldviewSelector.tsx` — axis sliders, mobile-friendly swipeable cards

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

# Show resonance breakdown
cc beliefs match <idea-id> --verbose
```

CLI output format for `cc beliefs`:
```
Belief Profile — @handle
────────────────────────────────
Worldview Axes:
  scientific  ████████░░  0.80
  systemic    █████████░  0.90
  pragmatic   ███████░░░  0.70
  holistic    █████░░░░░  0.50
  relational  ██████░░░░  0.60
  spiritual   ███░░░░░░░  0.30

Concept Resonances (top 5):
  entropy (0.95), emergence (0.82), coherence (0.78)

Interest Tags: #entropy #consciousness #emergence
```

---

## Web UI

**Route**: `/profile/[handle]/beliefs`

**Components**:
- **BeliefRadarChart**: hexagonal radar chart of the 6 worldview axes using Recharts
  `RadarChart`. Mobile-responsive, min height 280px.
- **ConceptTagCloud**: word cloud of `interest_tags` and top `concept_resonances`, sized by
  weight. Clickable tags navigate to `/concepts/{id}`.
- **WorldviewSelector**: six axis sliders (0–100) rendered as swipeable cards on mobile,
  a compact grid on desktop. Each card shows axis name, description, and current value.
  Save button sends PATCH request; optimistic update with rollback on error.

**State**: fetched client-side via SWR from `/api/contributors/{handle}/beliefs`. Updates
via PATCH with debounce (500ms) on slider change.

---

## Resonance Scoring Algorithm

The resonance score between a contributor's belief profile and an idea is computed as:

```
resonance_score = 0.4 * concept_overlap + 0.4 * worldview_alignment + 0.2 * tag_match
```

Where:
- **concept_overlap**: Jaccard-weighted similarity between contributor's concept_resonances
  and the idea's concept tags. If the idea has no concept tags, score = 0.5 (neutral).
- **worldview_alignment**: Dot product (cosine-like) between contributor's worldview_axes
  vector and the idea's inferred axis weights (derived from its concepts and text).
  Normalized to [0, 1]. If the idea has no axis data, score = 0.5.
- **tag_match**: Fraction of contributor's interest_tags present in the idea's tags.
  If no tags on either side, score = 0.5.

Scores below 0.3 are surfaced as "low resonance" in the UI (grey); above 0.7 as "high
resonance" (highlighted). Between 0.3 and 0.7 is "moderate" (default).

---

## Task Card

```yaml
goal: implement per-contributor belief profiles with resonance scoring
files_allowed:
  - api/app/routers/beliefs.py
  - api/app/services/belief_service.py
  - api/app/models/belief.py
  - api/app/db/migrations/add_belief_columns.sql
  - api/main.py
  - api/tests/test_belief_system.py
  - web/src/app/profile/[handle]/beliefs/page.tsx
  - web/src/components/beliefs/BeliefRadarChart.tsx
  - web/src/components/beliefs/ConceptTagCloud.tsx
  - web/src/components/beliefs/WorldviewSelector.tsx
done_when:
  - GET /api/contributors/{id}/beliefs returns 200 with full profile
  - PATCH /api/contributors/{id}/beliefs returns 200 with updated profile
  - GET /api/contributors/{id}/beliefs/resonance?idea_id=X returns resonance_score 0.0–1.0
  - GET /api/beliefs/roi returns network stats with spec_ref
  - pytest api/tests/test_belief_system.py — 12/12 pass
  - web page /profile/[handle]/beliefs renders radar chart without console errors
commands:
  - pytest api/tests/test_belief_system.py -v
  - cd web && npm run build
constraints:
  - Do not modify existing contributor auth/session logic
  - Belief PATCH is additive by default (replace: false)
  - Resonance algorithm weights must sum to 1.0
  - No new external dependencies beyond recharts (already in web)
```

---

## Verification Scenarios

### Scenario 1 — Full belief profile CRUD cycle

**Setup**: Contributor `abc123` exists (created via POST /api/onboarding/register).
Beliefs are initially empty.

**Action**:
```bash
# 1. Read initial (empty) profile
curl -s $API/api/contributors/abc123/beliefs
# 2. Set worldview axes
curl -s -X PATCH $API/api/contributors/abc123/beliefs \
  -H "Content-Type: application/json" \
  -d '{"worldview_axes":{"scientific":0.9,"systemic":0.8},"interest_tags":["entropy"]}'
# 3. Read updated profile
curl -s $API/api/contributors/abc123/beliefs
# 4. PATCH again — additive
curl -s -X PATCH $API/api/contributors/abc123/beliefs \
  -H "Content-Type: application/json" \
  -d '{"interest_tags":["emergence"]}'
# 5. Confirm tags are now ["entropy","emergence"]
curl -s $API/api/contributors/abc123/beliefs | jq .interest_tags
```

**Expected**:
- Step 1: HTTP 200, `{"worldview_axes":{},"concept_resonances":[],"interest_tags":[]}`
- Step 2: HTTP 200, `worldview_axes.scientific == 0.9`, `interest_tags == ["entropy"]`
- Step 3: HTTP 200 same as step 2
- Step 5: `["entropy","emergence"]` (additive — both tags present)

**Edge**: `PATCH` with `replace: true` replaces tags. Verify:
```bash
curl -s -X PATCH $API/api/contributors/abc123/beliefs \
  -H "Content-Type: application/json" \
  -d '{"interest_tags":["coherence"],"replace":true}' | jq .interest_tags
# Expected: ["coherence"] — previous tags gone
```

---

### Scenario 2 — Resonance match against an idea

**Setup**: Contributor `abc123` has `worldview_axes.systemic = 0.9` and
`interest_tags = ["entropy","emergence"]`. Idea `idea_xyz` exists with tags `["entropy"]`.

**Action**:
```bash
curl -s "$API/api/contributors/abc123/beliefs/resonance?idea_id=idea_xyz"
```

**Expected**: HTTP 200, `resonance_score` between 0.0–1.0, `matched_concepts` includes
`"entropy"`, `breakdown` object present with `concept_overlap`, `worldview_alignment`,
`tag_match` all between 0.0–1.0.

**Edge**: missing `idea_id` param:
```bash
curl -s "$API/api/contributors/abc123/beliefs/resonance"
# Expected: HTTP 422, {"detail": "idea_id is required"}
```

**Edge**: idea does not exist:
```bash
curl -s "$API/api/contributors/abc123/beliefs/resonance?idea_id=nonexistent_idea"
# Expected: HTTP 404, {"detail": "Idea not found"}
```

---

### Scenario 3 — Validation errors

**Setup**: Any existing contributor.

**Action**:
```bash
# Invalid axis name
curl -s -X PATCH $API/api/contributors/abc123/beliefs \
  -H "Content-Type: application/json" \
  -d '{"worldview_axes":{"astral":0.5}}'
# Expected: HTTP 422

# Weight out of range
curl -s -X PATCH $API/api/contributors/abc123/beliefs \
  -H "Content-Type: application/json" \
  -d '{"worldview_axes":{"scientific":1.5}}'
# Expected: HTTP 422

# Unknown field
curl -s -X PATCH $API/api/contributors/abc123/beliefs \
  -H "Content-Type: application/json" \
  -d '{"unknown_field":"value"}'
# Expected: HTTP 422
```

**Expected**: All three return HTTP 422 with a `detail` message naming the invalid field.

---

### Scenario 4 — Non-existent contributor

**Setup**: No contributor with ID `ghost999`.

**Action**:
```bash
curl -s $API/api/contributors/ghost999/beliefs
curl -s -X PATCH $API/api/contributors/ghost999/beliefs \
  -H "Content-Type: application/json" \
  -d '{"interest_tags":["entropy"]}'
curl -s "$API/api/contributors/ghost999/beliefs/resonance?idea_id=idea_xyz"
```

**Expected**: All three return HTTP 404, `{"detail": "Contributor not found"}`.

---

### Scenario 5 — ROI and network stats

**Setup**: At least 2 contributors exist; one has a belief profile set (from scenario 1),
one does not.

**Action**:
```bash
curl -s $API/api/beliefs/roi
```

**Expected**: HTTP 200, response contains:
- `contributors_with_profiles >= 1`
- `contributors_total >= 2`
- `profile_adoption_rate` between 0.0–1.0
- `top_worldview_axes` list with at least one entry
- `spec_ref == "spec-169"`

**Edge**: zero contributors in system:
```bash
# Expected: HTTP 200, contributors_with_profiles=0, contributors_total=0, profile_adoption_rate=0.0
```

---

## Research Inputs

- `2024-09-01` — Living Codex `UserConceptModule` (internal) — source pattern for
  per-user concept resonance weights and worldview axes
- `2025-01-15` — [Recharts RadarChart docs](https://recharts.org/en-US/api/RadarChart) —
  radar chart rendering for web component
- `2025-03-01` — [FastAPI PATCH best practices](https://fastapi.tiangolo.com/tutorial/body-updates/) —
  partial update model patterns
- `2026-03-28` — Coherence Network task spec (this document) — belief system task brief

---

## Concurrency Behavior

- **Read operations**: Safe for concurrent access; no locking needed.
- **Write operations (PATCH)**: Last-write-wins for scalar fields. List fields (tags,
  resonances) use an atomic JSONB array append (PostgreSQL `||` operator) unless
  `replace: true` is specified.
- **Recommendation**: Clients should show optimistic UI and rollback on 4xx/5xx.

---

## Out of Scope

- Full graph-driven concept taxonomy validation (concept_id merely needs to be a non-empty string in MVP).
- Belief-based feed ranking algorithm changes to the main idea list (follow-up spec).
- Push notifications for high-resonance new ideas (follow-up spec).
- Cross-contributor belief similarity ("who thinks like me") feature (follow-up spec).
- CLI `cc beliefs` command implementation (CLI spec deferred; API is the authority).

---

## Risks and Assumptions

- **Assumption**: Contributor IDs from spec-168 TOFU onboarding are used as `{id}` in
  belief endpoints. If handles differ from internal IDs, the router must support both
  (handle lookup + UUID fallback).
- **Risk**: Resonance scoring is heuristic. Low-quality idea concept tags will produce
  meaningless scores. Mitigation: surface confidence indicator alongside score; show
  "low data" badge when idea has fewer than 2 concept tags.
- **Risk**: JSONB column migration on an existing `contributors` table with live traffic.
  Mitigation: use `ADD COLUMN ... DEFAULT '{}'::jsonb` (non-blocking on PostgreSQL 11+).
- **Assumption**: Recharts is already installed in the web project. If not, it must be
  added before the web component is implemented.
- **Risk**: Mobile swipeable card UX adds complexity. Mitigation: MVP ships with axis
  sliders on all devices; swipeable cards are a progressive enhancement in a follow-up.

---

## Known Gaps and Follow-up Tasks

- CLI `cc beliefs` / `cc beliefs set` / `cc beliefs match` implementation (follow-up task).
- Swipeable card UI for mobile (progressive enhancement, follow-up).
- Belief-driven feed ranking (follow-up spec: "personalized idea feed").
- Cross-contributor similarity search ("who thinks like me") — follow-up spec.
- Concept ID validation against the concept graph (currently free-form strings in MVP).
- Belief profile history / audit log (follow-up).

---

## Failure / Retry Reflection

- **Failure mode**: Resonance endpoint returns 500 if idea has no concept tags.
  **Blind spot**: Assuming all ideas have tags.
  **Next action**: Default concept_overlap to 0.5 (neutral) when idea tags are absent.

- **Failure mode**: PATCH test fails because test DB has no contributors table with JSONB cols.
  **Blind spot**: Migration not applied in test fixtures.
  **Next action**: Add `add_belief_columns.sql` to conftest.py setup.

- **Failure mode**: Radar chart renders empty on first load (contributor has no axes set).
  **Blind spot**: Recharts RadarChart errors on empty data.
  **Next action**: Default all 6 axes to 0.0 in the API response (never return null).

---

## How to Measure "Is It Working?" — Proof Over Time

This spec explicitly addresses the open question: *"How can we improve this idea, show
whether it is working yet, and make that proof clearer over time?"*

### Immediate proof (deploy day)

- `GET /api/beliefs/roi` returns `profile_adoption_rate > 0` after any contributor sets beliefs.
- Resonance endpoint returns scores for all existing contributors × ideas.

### Short-term proof (1–2 weeks)

- Track `avg_resonance_match_rate` in `/api/beliefs/roi` daily. An increasing trend means
  contributors are setting profiles that align with the ideas they engage with.
- Monitor `profile_adoption_rate` weekly. Target: >20% of contributors have ≥1 axis set
  within 2 weeks of launch.

### Medium-term proof (1 month)

- Compare idea engagement (upvotes, contributions) for ideas surfaced via resonance vs.
  not. High-resonance ideas should show higher engagement rates.
- A/B test: contributors who have belief profiles set should show higher contribution rates
  than those who don't (controllable via feature flag).

### Observable signals in existing endpoints

- `GET /api/beliefs/roi` → `avg_resonance_match_rate` (above 0.5 = beliefs are predicting
  engagement better than random).
- `GET /api/contributors/{id}/beliefs` → non-empty profiles = adoption.
- `GET /api/contributors/{id}/beliefs/resonance` → scores clustering above 0.6 for ideas
  contributors actually engage with = system is learning preferences.

### Dashboard integration

A future spec (follow-up) will add a `/beliefs/analytics` endpoint and a dashboard card
showing adoption rate, match rate trend, and top worldview axes across the network.

---

## Decision Gates

- **D1**: Should concept_resonances reference validated concept graph nodes, or allow free-form
  strings for MVP? → **Decision: free-form strings for MVP** (reduces dependency on concept graph spec).
- **D2**: Should PATCH be strictly additive (append-only) or support both modes? →
  **Decision: additive by default, `replace: true` for explicit replacement** (preserves
  safety while enabling flexibility).
- **D3**: Should the resonance algorithm be exposed/configurable? → **Decision: hardcoded
  weights (0.4/0.4/0.2) for MVP; follow-up spec for tunable resonance** (see Spec 163).
