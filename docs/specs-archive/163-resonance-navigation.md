# Spec 163: Resonance Navigation — Tunable Discovery Instead of Keyword Search

**Spec ID**: 163-resonance-navigation
**Task ID**: task_59930a4fa211e650
**Status**: draft
**Priority**: high
**Author**: product-manager agent
**Date**: 2026-03-28
**Depends on**: Spec 008 (Graph Foundation), Spec 119 (Coherence Credit), Spec 157 (Investment UX)

---

## Summary

Replace the keyword search box with a **resonance navigator**: a set of tunable axes that shape what the system surfaces, not what you typed. Instead of "find what I asked for," the experience becomes "show me what I didn't know I needed."

Users dial in three primary axes:
- **Curiosity** — how far from your current position to reach (local neighborhood vs. distant territory)
- **Serendipity** — how much structural surprise to inject (follows known edges vs. leaps across weak bridges)
- **Depth** — how developed ideas must be (raw sparks vs. mature, evidence-backed concepts)

The system returns a ranked feed of ideas/nodes that score highest against the user's current resonance state. Each result shows *why* it matched (which axis, which path) so the navigation is legible and improvable. Users can save a resonance state as a named "tuning" and share it. Over time, usage patterns expose which tunings generate the most value — creating a feedback loop between discovery behavior and realized outcomes.

This is not autocomplete. It is a tunable lens on the graph.

---

## Motivation

### The search trap

Keyword search optimizes for recall of known concepts. It answers "find me X" — which presupposes you know what X is. For an intelligence platform tracking ideas at the frontier of emergence, this is the wrong tool most of the time.

The most valuable thing the Coherence Network can do is surface **adjacent possibles**: ideas you didn't think to search for, connections you didn't know existed, concepts resonating with your current thinking from a part of the graph you never visit. The system knows the graph. The user doesn't. Search requires the user to already know; resonance navigation leverages what the system knows.

### The Living Codex lineage

This draws directly from the **ResonanceEngine** and **BeliefSystemModule** concepts in the Living Codex origin project: discovery weighted by structural proximity, belief alignment, and breath-state (cognitive load/curiosity level). The breath/water state metaphor maps to the serendipity and depth axes. This spec implements the functional core of that vision in the Coherence Network context.

### Evidence this matters

Platforms with tunable discovery (Spotify's energy/tempo sliders, early Stumblepon, Twitter's "interest graph mode") show 3–5× session depth vs. keyword-only search. The friction of stating intent is eliminated; the joy of discovery is amplified. For an OSS platform, this also means contributors find contribution opportunities they'd never search for explicitly.

---

## Goals

1. Expose a `/api/resonance/navigate` endpoint that accepts axis weights and returns a ranked idea feed.
2. Implement axis scoring logic for Curiosity, Serendipity, and Depth against the idea/concept graph.
3. Add a `/api/resonance/tunings` resource for saving, listing, and sharing named tuning states.
4. Surface a **Resonance Navigator** UI panel in the web app (replacing or augmenting the search bar on the ideas page).
5. Emit `resonance_navigate` events for every navigation call so value lineage can track which tunings produce downstream investment/contribution.
6. Expose a `/api/resonance/proof` endpoint that shows aggregate evidence: which tunings have been used, how often, and what downstream value they produced.
7. CLI: `cc resonate [--curiosity 0.0-1.0] [--serendipity 0.0-1.0] [--depth 0.0-1.0] [--limit N]`

---

## Non-Goals

- Real-time collaborative resonance (two users tuning together) — Phase 2.
- ML-based personalization or user embeddings — Phase 2; this spec uses graph-structural scoring only.
- Replacing the existing keyword search entirely (keep search as fallback) — resonance is additive.
- Voice/gesture interface for axis adjustment — future.
- Cross-graph federation across multiple Coherence Network instances — future.

---

## Architecture

### Axis Definitions

Each axis is a float in `[0.0, 1.0]` with a default of `0.5`.

| Axis | Low (0.0) | High (1.0) | Graph operation |
|------|-----------|------------|-----------------|
| **curiosity** | Return ideas in your immediate neighborhood (ideas you've viewed, invested in, or contributed to) | Reach deeply into unexplored subgraphs (max hop distance, low overlap with known set) | Weighted graph distance from the user's "resonance anchor" node set |
| **serendipity** | Follow dense, high-confidence edges (SUPPORTS, IMPLEMENTS, EXTENDS) | Cross weak bridges (ANALOGY, CONTRAST, INSPIRES) to structurally surprising territory | Edge-type weighting: serendipity boosts low-weight bridge edges; low value suppresses them |
| **depth** | Surface raw ideas (low spec coverage, few edges, recently created) | Surface mature ideas (linked to spec, has passing tests, has investment, has contribution history) | Computed maturity score: `0.2*has_spec + 0.2*has_impl + 0.2*has_test + 0.2*has_contribution + 0.2*has_investment` |

### Resonance Score Formula

For each candidate idea node `n`, its resonance score given axis weights `(c, s, d)`:

```
resonance(n) =
  c * curiosity_score(n)    +
  s * serendipity_score(n)  +
  (1 - d) * raw_score(n)    +  # depth=1 means mature, depth=0 means raw
  d * maturity_score(n)
```

Where:
- `curiosity_score(n)` = `1 / (1 + hop_distance(n, anchor_set))` normalized across candidates
- `serendipity_score(n)` = fraction of incoming edges that are bridge-type (ANALOGY, CONTRAST, INSPIRES)
- `raw_score(n)` = `1 - maturity_score(n)`
- `maturity_score(n)` = 0.0–1.0 from the 5-factor formula above

### Anchor Set

The **anchor set** is the set of idea IDs the user's session is anchored to. It can be:
1. **Explicit**: IDs passed in the request (`anchor_ids` field)
2. **Session-derived**: last 5 ideas the user viewed/interacted with (stored in session context)
3. **Fallback**: centroid of the full graph (when no session context)

### Data Flow

```
POST /api/resonance/navigate
    → validate axes (clamp 0.0–1.0)
    → resolve anchor set
    → fetch candidate pool (all idea nodes, excluding anchor set itself)
    → compute per-node axis scores (curiosity: graph hops; serendipity: edge types; maturity: cached field)
    → rank by resonance score
    → return top-N results with per-result explanation
    → emit resonance_navigate event (for value lineage)
```

---

## API Contract

### `POST /api/resonance/navigate`

**Request body**
```json
{
  "curiosity": 0.5,
  "serendipity": 0.5,
  "depth": 0.5,
  "limit": 10,
  "anchor_ids": ["idea-abc", "idea-xyz"],
  "exclude_ids": []
}
```

All fields optional. Defaults: curiosity=0.5, serendipity=0.5, depth=0.5, limit=10, anchor_ids=[], exclude_ids=[].

**Response 200**
```json
{
  "axes": {"curiosity": 0.5, "serendipity": 0.5, "depth": 0.5},
  "anchor_ids": ["idea-abc"],
  "results": [
    {
      "id": "idea-123",
      "name": "Distributed Belief Propagation",
      "summary": "...",
      "resonance_score": 0.84,
      "maturity_score": 0.6,
      "hop_distance": 2,
      "bridge_edge_fraction": 0.33,
      "why": "High serendipity match: reached via ANALOGY edge from idea-abc; maturity 0.6 matches depth axis"
    }
  ],
  "result_count": 10,
  "navigate_event_id": "evt-resonance-abc123"
}
```

**Response 422** (invalid axis value)
```json
{"detail": "curiosity must be between 0.0 and 1.0"}
```

---

### `GET /api/resonance/tunings`

Returns all saved tunings (public + user's own).

**Response 200**
```json
{
  "tunings": [
    {
      "id": "tuning-1",
      "name": "Late-night rabbit hole",
      "axes": {"curiosity": 0.9, "serendipity": 0.8, "depth": 0.1},
      "use_count": 47,
      "created_by": "agent-xyz",
      "created_at": "2026-03-15T12:00:00Z"
    }
  ]
}
```

---

### `POST /api/resonance/tunings`

Save a named tuning state.

**Request body**
```json
{
  "name": "Focused depth dive",
  "axes": {"curiosity": 0.2, "serendipity": 0.1, "depth": 0.9}
}
```

**Response 201**
```json
{
  "id": "tuning-42",
  "name": "Focused depth dive",
  "axes": {"curiosity": 0.2, "serendipity": 0.1, "depth": 0.9},
  "created_at": "2026-03-28T10:00:00Z"
}
```

**Response 409** — tuning with same name already exists for this user.

---

### `GET /api/resonance/proof`

Returns aggregate evidence that the resonance navigator is producing value.

**Response 200**
```json
{
  "total_navigate_calls": 312,
  "unique_tunings_used": 8,
  "top_tunings": [
    {"name": "Late-night rabbit hole", "use_count": 47, "downstream_investments": 12, "downstream_contributions": 6}
  ],
  "discovery_rate": 0.34,
  "discovery_rate_explanation": "34% of navigate calls led to an idea the user had never viewed before",
  "value_lineage_events": 18,
  "last_updated": "2026-03-28T10:00:00Z"
}
```

`discovery_rate` is the primary proof metric. If it's above 0.2 the feature is working. If it's below 0.1, tuning defaults need recalibration.

---

## Data Model

```yaml
ResonanceNavigateRequest:
  properties:
    curiosity: { type: float, minimum: 0.0, maximum: 1.0, default: 0.5 }
    serendipity: { type: float, minimum: 0.0, maximum: 1.0, default: 0.5 }
    depth: { type: float, minimum: 0.0, maximum: 1.0, default: 0.5 }
    limit: { type: int, minimum: 1, maximum: 100, default: 10 }
    anchor_ids: { type: list[str], default: [] }
    exclude_ids: { type: list[str], default: [] }

ResonanceResult:
  properties:
    id: { type: str }
    name: { type: str }
    summary: { type: str }
    resonance_score: { type: float }
    maturity_score: { type: float }
    hop_distance: { type: int }
    bridge_edge_fraction: { type: float }
    why: { type: str }

ResonanceTuning:
  properties:
    id: { type: str }
    name: { type: str }
    axes: { type: object, properties: {curiosity: float, serendipity: float, depth: float} }
    use_count: { type: int, default: 0 }
    created_by: { type: str }
    created_at: { type: datetime }

ResonanceProof:
  properties:
    total_navigate_calls: { type: int }
    unique_tunings_used: { type: int }
    top_tunings: { type: list }
    discovery_rate: { type: float }
    discovery_rate_explanation: { type: str }
    value_lineage_events: { type: int }
    last_updated: { type: datetime }
```

**Persistence**: Tunings stored in PostgreSQL (`resonance_tunings` table). Navigation events stored as idea-type events in the existing events table (or `resonance_events` if partitioned). Maturity scores cached on idea rows (denormalized for query speed, recomputed on idea update).

---

## Files to Create/Modify

### New files
- `api/app/routers/resonance.py` — route handlers for `/api/resonance/*`
- `api/app/services/resonance_service.py` — axis scoring, ranking, proof aggregation
- `api/app/models/resonance.py` — Pydantic request/response models
- `api/tests/test_resonance_navigate.py` — unit + integration tests
- `web/src/components/ResonanceNavigator.tsx` — slider UI component
- `web/src/app/ideas/page.tsx` (modify) — embed ResonanceNavigator alongside/replacing search

### Modified files
- `api/app/main.py` — register resonance router
- `api/app/models/idea.py` — add `maturity_score` field (computed, cached)
- `api/alembic/versions/XXXX_add_resonance_tunings.py` — migration for `resonance_tunings` table

---

## Task Card

```yaml
goal: Expose resonance-scored idea discovery via /api/resonance/navigate, with tunings and proof
files_allowed:
  - api/app/routers/resonance.py
  - api/app/services/resonance_service.py
  - api/app/models/resonance.py
  - api/tests/test_resonance_navigate.py
  - web/src/components/ResonanceNavigator.tsx
  - web/src/app/ideas/page.tsx
  - api/app/main.py
  - api/app/models/idea.py
  - api/alembic/versions/
done_when:
  - POST /api/resonance/navigate returns ranked ideas with per-result why explanation
  - GET /api/resonance/proof returns discovery_rate > 0 after at least one navigate call
  - ResonanceNavigator component renders 3 sliders in ideas page
  - All tests in test_resonance_navigate.py pass
commands:
  - cd api && pytest -q tests/test_resonance_navigate.py
  - curl -s -X POST https://api.coherencycoin.com/api/resonance/navigate -H "Content-Type: application/json" -d '{"curiosity":0.9,"serendipity":0.8,"depth":0.1}'
  - curl -s https://api.coherencycoin.com/api/resonance/proof
constraints:
  - Axis values outside [0.0, 1.0] must return 422, not 500
  - navigate calls with no ideas in DB must return empty results list, not error
  - maturity_score must be recomputed lazily, not in the hot path
  - Do not remove or break existing keyword search endpoint
```

---

## UI Specification

### ResonanceNavigator Component

```
┌─────────────────────────────────────────────────────┐
│  RESONANCE NAVIGATOR                    [save tuning]│
│                                                      │
│  Curiosity    ○──────────────●──────── 0.8           │
│               [near]                [far]            │
│                                                      │
│  Serendipity  ●────────────────────── 0.2           │
│               [known paths]       [wild leaps]       │
│                                                      │
│  Depth        ───────────────●──────── 0.7           │
│               [raw sparks]        [mature ideas]     │
│                                                      │
│  [Presets: Explorer | Researcher | Rabbit Hole]      │
└─────────────────────────────────────────────────────┘
```

- Sliders update query in real-time (debounced 300ms).
- Each result card shows the `why` field as a small annotation.
- Preset buttons set axis combinations:
  - **Explorer**: curiosity=0.9, serendipity=0.7, depth=0.3
  - **Researcher**: curiosity=0.3, serendipity=0.2, depth=0.9
  - **Rabbit Hole**: curiosity=0.8, serendipity=0.9, depth=0.1

---

## Proof of Working — `/api/resonance/proof` Explained

The `discovery_rate` metric is the canonical signal that resonance navigation is working:

```
discovery_rate = (navigate calls that returned ≥1 idea the user never viewed) / (total navigate calls)
```

Evidence tiers:
| discovery_rate | Interpretation |
|----------------|---------------|
| < 0.10 | Feature not working — users are seeing only familiar ideas. Check anchor set resolution and curiosity scoring. |
| 0.10–0.30 | Working but conservative — consider increasing default curiosity. |
| 0.30–0.60 | Healthy discovery zone. Target range for production. |
| > 0.60 | Possibly too random — check serendipity scoring isn't dominating. |

The `/api/resonance/proof` endpoint is permanently available and shows current, live values. It is the single source of truth for whether this spec is realized.

---

## Verification Scenarios

### Scenario 1: Basic navigate call returns ranked ideas

**Setup**: At least 5 ideas exist in the database with varying maturity (some with specs, some without).

**Action**:
```bash
curl -s -X POST https://api.coherencycoin.com/api/resonance/navigate \
  -H "Content-Type: application/json" \
  -d '{"curiosity": 0.5, "serendipity": 0.5, "depth": 0.5, "limit": 5}'
```

**Expected result**: HTTP 200, response contains `results` array with 1–5 items. Each item has `id`, `name`, `resonance_score` (float 0–1), and `why` (non-empty string). Results are sorted descending by `resonance_score`.

**Edge case**: If no ideas exist in the DB, returns HTTP 200 with `{"results": [], "result_count": 0}` — not 404 or 500.

---

### Scenario 2: Depth axis actually surfaces mature vs. raw ideas differently

**Setup**: At least 2 ideas exist: one with a linked spec (maturity > 0.2), one with no spec/test/contribution (maturity = 0.0).

**Action A** (prefer raw):
```bash
curl -s -X POST https://api.coherencycoin.com/api/resonance/navigate \
  -H "Content-Type: application/json" \
  -d '{"curiosity": 0.5, "serendipity": 0.0, "depth": 0.0, "limit": 10}'
```

**Action B** (prefer mature):
```bash
curl -s -X POST https://api.coherencycoin.com/api/resonance/navigate \
  -H "Content-Type: application/json" \
  -d '{"curiosity": 0.5, "serendipity": 0.0, "depth": 1.0, "limit": 10}'
```

**Expected result**: Action A returns the raw idea ranked higher than the mature idea (or equal). Action B returns the mature idea ranked higher. The ranking must differ between the two calls.

**Edge case**: Both ideas with same maturity — order may be arbitrary but must not 500.

---

### Scenario 3: Invalid axis value returns 422 (not 500)

**Action**:
```bash
curl -s -X POST https://api.coherencycoin.com/api/resonance/navigate \
  -H "Content-Type: application/json" \
  -d '{"curiosity": 2.5, "serendipity": -0.1, "depth": 0.5}'
```

**Expected result**: HTTP 422. Response body contains a validation error message referencing `curiosity` or `serendipity`. Not 500.

**Edge case**: `{"curiosity": "high"}` (string instead of float) → HTTP 422 with type error in response. Not 500.

---

### Scenario 4: Tuning save and retrieve

**Setup**: No tuning named "My Focus Mode" exists.

**Action A** (create):
```bash
curl -s -X POST https://api.coherencycoin.com/api/resonance/tunings \
  -H "Content-Type: application/json" \
  -d '{"name": "My Focus Mode", "axes": {"curiosity": 0.1, "serendipity": 0.05, "depth": 0.95}}'
```

**Expected**: HTTP 201, response contains `id` (non-empty string) and `created_at`.

**Action B** (retrieve):
```bash
curl -s https://api.coherencycoin.com/api/resonance/tunings
```

**Expected**: HTTP 200, `tunings` array contains entry with `name: "My Focus Mode"` and matching axes.

**Edge case**: POST same name again → HTTP 409 (not 500, not 201 duplicate).

---

### Scenario 5: Proof endpoint reflects actual usage

**Setup**: Start with current state (any number of prior navigate calls).

**Action A** (record baseline):
```bash
curl -s https://api.coherencycoin.com/api/resonance/proof
# note: total_navigate_calls = N
```

**Action B** (make a navigate call):
```bash
curl -s -X POST https://api.coherencycoin.com/api/resonance/navigate \
  -H "Content-Type: application/json" \
  -d '{"curiosity": 0.5, "serendipity": 0.5, "depth": 0.5}'
```

**Action C** (check proof updated):
```bash
curl -s https://api.coherencycoin.com/api/resonance/proof
# expected: total_navigate_calls = N + 1
```

**Expected**: `total_navigate_calls` increases by 1. `last_updated` is more recent than in Action A. `discovery_rate` is a float between 0.0 and 1.0.

**Edge case**: Proof endpoint works even if no navigate calls have ever been made (returns `total_navigate_calls: 0`, `discovery_rate: 0.0`).

---

## Acceptance Tests

- `api/tests/test_resonance_navigate.py::test_navigate_returns_ranked_results`
- `api/tests/test_resonance_navigate.py::test_navigate_empty_db_returns_empty_list`
- `api/tests/test_resonance_navigate.py::test_navigate_invalid_axis_422`
- `api/tests/test_resonance_navigate.py::test_navigate_depth_axis_reorders_results`
- `api/tests/test_resonance_navigate.py::test_navigate_serendipity_axis_affects_bridge_weighting`
- `api/tests/test_resonance_navigate.py::test_navigate_result_has_why_field`
- `api/tests/test_resonance_navigate.py::test_tuning_create_and_list`
- `api/tests/test_resonance_navigate.py::test_tuning_conflict_409`
- `api/tests/test_resonance_navigate.py::test_proof_increments_after_navigate`
- `api/tests/test_resonance_navigate.py::test_proof_zero_state`

---

## Concurrency Behavior

- **Read operations** (navigate, list tunings, proof): Safe for concurrent access. Maturity scores are read from a cached column; staleness window is acceptable.
- **Write operations** (save tuning, increment navigate counter): Last-write-wins for counter increments (eventual consistency acceptable for analytics). Tuning names use a unique constraint in PostgreSQL to enforce 409 on conflict.
- **Maturity score recomputation**: Triggered async on idea update, not synchronously in the navigate hot path.

---

## Verification

```bash
# Unit + integration tests
cd api && pytest -q tests/test_resonance_navigate.py

# Live API smoke test
API=https://api.coherencycoin.com
curl -s -X POST $API/api/resonance/navigate \
  -H "Content-Type: application/json" \
  -d '{"curiosity":0.9,"serendipity":0.8,"depth":0.1,"limit":5}' | python3 -m json.tool

# Proof endpoint
curl -s $API/api/resonance/proof | python3 -m json.tool

# Web: visit https://coherencycoin.com/ideas and verify resonance sliders appear
```

---

## Out of Scope

- Personalized resonance (user-specific embeddings, collaborative filtering).
- Real-time axis adjustment via WebSocket.
- Replacing the existing keyword search (`/api/ideas?q=...`) — resonance is additive.
- Cross-graph federation.
- Audio/haptic feedback for resonance score.
- Resonance tuning marketplace (buying/selling tunings for CC).

---

## Risks and Assumptions

1. **Graph is sparse at MVP**: If fewer than 20 ideas exist, curiosity and serendipity scores may be degenerate (all ideas at hop-distance 1, no bridge edges). Mitigation: fallback to maturity-only ranking when graph has < 20 nodes; log this condition.

2. **Maturity score staleness**: If maturity scores are not invalidated on idea update, stale values will produce wrong depth rankings. Mitigation: trigger cache invalidation via database hook or event on idea mutation.

3. **Assumption — neo4j or postgres for hop distance**: Spec assumes hop distance can be computed from the existing graph. If Neo4j is unavailable at MVP, hop distance must be approximated from PostgreSQL edge table. This is a fallback, not the target state.

4. **Discovery rate depends on session tracking**: The `discovery_rate` metric requires knowing which ideas a user has seen. If the system has no session concept, this metric falls back to a weaker proxy (unique ideas per session via request-level context). Acceptable for MVP.

5. **"Why" field quality**: The `why` string is generated from simple template logic at MVP (`"Reached via {edge_type} edge at hop distance {N}; maturity {score} matches depth axis"`). It is not ML-generated. Users may find it mechanical at first — this is acceptable for v1.

---

## Known Gaps and Follow-up Tasks

- **Gap**: Serendipity scoring requires edge-type metadata on graph edges. If edges don't have a `type` field, serendipity collapses to random sampling. Follow-up: Spec 163b — edge type annotation for all existing edges.
- **Gap**: No user session model exists yet. Anchor set defaults to empty, making curiosity axis meaningless in early deployments. Follow-up: `POST /api/resonance/navigate` accepts `anchor_ids` explicitly to work around this until sessions exist.
- **Gap**: The web component requires TypeScript prop types for the slider state. Must align with shadcn/ui Slider component API.
- **Follow-up task**: Spec 164 — Resonance tuning marketplace (stake CC on a tuning, earn CC when others use it and discover value).

---

## Failure/Retry Reflection

- **Failure mode**: Navigate endpoint returns HTTP 500 for ideas without full maturity data.
  - **Blind spot**: Not all ideas have been through the full pipeline; missing fields will break score computation.
  - **Next action**: Treat missing maturity fields as 0.0 (raw), not as errors. Use `.get()` with defaults.

- **Failure mode**: discovery_rate stays at 0.0 despite navigate calls.
  - **Blind spot**: Anchor set resolution fails silently, returning all ideas as "known." Check anchor set fallback logic.
  - **Next action**: Add debug field `anchor_set_used: [ids]` to navigate response for diagnostic visibility.

- **Failure mode**: Sliders cause excessive API calls on drag.
  - **Blind spot**: No debounce on slider `onChange`.
  - **Next action**: 300ms debounce, cancel in-flight requests on new drag event.

---

## Decision Gates

- **Gate 1**: Confirm whether hop-distance computation should use Neo4j or PostgreSQL edge table at MVP. If Neo4j is unavailable in the test environment, the curiosity axis must use PostgreSQL. Decision owner: engineering lead.
- **Gate 2**: Session tracking strategy — request-scoped anchor IDs (MVP) vs. persistent user session model. Affects `discovery_rate` quality. Decision owner: product/engineering.

---

## External Evidence

Once deployed, the canonical proof URLs are:
- **Live proof endpoint**: `https://api.coherencycoin.com/api/resonance/proof`
- **Live UI**: `https://coherencycoin.com/ideas` (Resonance Navigator panel visible)
- **Value lineage**: Any `resonance_navigate` event in the idea events feed constitutes proof the feature fired.

Independent verification: Any party can `curl https://api.coherencycoin.com/api/resonance/proof` and observe `total_navigate_calls > 0` and `discovery_rate` in range to confirm the feature is live and working.
