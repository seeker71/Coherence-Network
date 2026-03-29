# Spec 181 — Belief Systems Translation: Idea Lens Engine

**Spec**: 181
**Idea ID**: `55948474-2703-4943-930f-13e432279e89`
**Task ID**: `task_acd2c78625dbcd3f`
**Related specs**: [`specs/169-belief-system.md`](./169-belief-system.md), [`specs/163-resonance-navigation.md`](./163-resonance-navigation.md)
**Status**: draft
**Date**: 2026-03-28

---

## Summary

The same idea means different things to different people. "Decentralized network" means
**freedom** to a libertarian, **efficiency** to an engineer, **threat** to an institution,
and **opportunity** to an entrepreneur. This spec defines the **Idea Lens Engine** — a
translation service that renders any idea through multiple structured worldview filters,
enabling perspective bridging without altering the idea's substance.

---

## Purpose

The Idea Lens Engine translates ideas through named worldview lenses so contributors who
think differently can see how their perspective connects to others who approach the same
problem from a different epistemic stance. This is not about changing ideas — it is about
removing the framing barrier that prevents people from recognizing shared goals. Without
this, ideas written in one epistemic register land poorly with contributors in another,
suppressing cross-worldview collaboration, reducing idea reach, and leaving value
unrealized. The lens system directly addresses the open question: "How can we improve this
idea, show whether it is working yet, and make that proof clearer over time?" by surfacing
resonance deltas and cross-lens engagement rates as quantified, API-accessible proof of
perspective-bridging activity.

---

## Problem

- Without per-lens framing, ideas written from one worldview alienate contributors who
  think differently — reducing engagement and cross-worldview collaboration.
- The same idea means different things to a libertarian, an engineer, an entrepreneur,
  a spiritual practitioner, or a systems thinker.
- News ingestion produces articles tagged from one perspective; contributors receive
  framing that may feel alien or hostile to their worldview axis.
- There is currently no API surface to measure whether the network is bridging perspectives
  or reinforcing existing silos.

---

## Requirements

- [ ] `GET /api/lenses` returns all registered worldview lenses with correct schema (HTTP 200).
- [ ] `GET /api/lenses/{lens_id}` returns a single lens definition or 404 if not found.
- [ ] `POST /api/lenses` creates a new lens (HTTP 201); duplicate `lens_id` returns 409.
- [ ] `GET /api/ideas/{idea_id}/translations/{lens_id}` returns a cached or freshly generated `IdeaTranslation` with `spec_ref: "spec-181"`.
- [ ] `POST /api/ideas/{idea_id}/translations/{lens_id}` with `{"force_regenerate": true}` re-runs generation and updates the cache.
- [ ] `GET /api/ideas/{idea_id}/translations/{lens_id}?contributor_id={id}` returns `resonance_delta` as float in [-1.0, 1.0].
- [ ] `GET /api/lenses/roi` returns non-negative counters (`total_translations_generated`, `cross_lens_engagement_rate`) and `spec_ref: "spec-181"`.
- [ ] 6 builtin lenses are seeded at startup: `libertarian`, `engineer`, `institutionalist`, `entrepreneur`, `spiritual`, `systemic`.
- [ ] Invalid `lens_id` on any translation endpoint returns 404, not 500.
- [ ] Axis values outside [0.0, 1.0] on `POST /api/lenses` return 422.
- [ ] Translation cache is keyed on `(idea_id, lens_id, source_hash)`; hash mismatch triggers re-generation.
- [ ] All integration tests in `api/tests/test_belief_systems_translation.py` pass.
- [ ] Idea Detail web page (`/ideas/{id}`) shows a lens selector section below the idea body.

---

## Solution

### Core Concept: Worldview Lenses

A **worldview lens** is a named filter with:
- A **framing archetype** (e.g., `libertarian`, `engineer`, `institutionalist`, `entrepreneur`, `spiritual`, `systemic`)
- **`archetype_axes`**: weights across the same axes used in spec-169 contributor belief profiles
- A **translation prompt fragment** (optional): system-level framing for the LLM restatement

The lens does not change facts, source text, or the idea's `name`/`description`. It produces
an **`IdeaTranslation`** object: a restatement tailored to the lens perspective, plus a
`resonance_delta` when a contributor ID is provided.

### Architecture

```
Contributor → requests lens  →  IdeaLensService
                                    │
                         [IdeaTranslationRepo]
                                    │
                    (cached or compute-on-demand)
                                    │
                        LLM translation layer
                       (uses BeliefSystemModule)
                                    │
                              IdeaTranslation
```

---

## Builtin Worldview Lenses (MVP)

| lens_id | Name | Core framing |
|---------|------|-------------|
| `libertarian` | Libertarian / Decentralist | Individual sovereignty, voluntary cooperation, anti-coercion |
| `engineer` | Systems Engineer | Efficiency, scalability, precision, trade-off analysis |
| `institutionalist` | Institutional / Policy | Governance, compliance, risk management, precedent |
| `entrepreneur` | Entrepreneur / Innovator | Market opportunity, user acquisition, monetization, speed |
| `spiritual` | Spiritual / Holistic | Meaning, wholeness, interconnectedness, non-dual framing |
| `systemic` | Systemic / Complexity | Feedback loops, emergence, unintended consequences, leverage |

These axes map directly to `worldview_axes` in spec-169 contributor profiles, enabling
resonance matching without additional mapping logic.

---

## API Contract

Base path: `/api`.

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/lenses` | List all registered worldview lenses |
| `GET` | `/api/lenses/{lens_id}` | Get a specific lens definition |
| `POST` | `/api/lenses` | Register a new worldview lens (operator) |
| `GET` | `/api/ideas/{idea_id}/translations` | All cached translations for an idea |
| `GET` | `/api/ideas/{idea_id}/translations/{lens_id}` | Single translation (cached or generated) |
| `POST` | `/api/ideas/{idea_id}/translations/{lens_id}` | Force-regenerate a translation |
| `GET` | `/api/lenses/roi` | Aggregate lens engagement metrics |

### `GET /api/lenses`

```json
{
  "lenses": [
    {
      "lens_id": "libertarian",
      "name": "Libertarian / Decentralist",
      "description": "Emphasizes individual sovereignty, voluntary cooperation",
      "archetype_axes": { "autonomy": 0.95, "collective": 0.1 },
      "is_builtin": true,
      "created_at": "2026-03-28T00:00:00Z"
    }
  ],
  "total": 6
}
```

### `GET /api/ideas/{idea_id}/translations/{lens_id}`

Query params:
- `contributor_id` (optional): adds `resonance_delta` relative to that contributor's belief profile

```json
{
  "idea_id": "decentralized-network-001",
  "lens_id": "libertarian",
  "original_name": "Decentralized Network Governance Proposal",
  "translated_summary": "This proposal reclaims decision-making from central authorities...",
  "emphasis": ["autonomy", "voluntary-cooperation", "censorship-resistance"],
  "risk_framing": "Risk of regulatory capture; coercion by incumbents.",
  "opportunity_framing": "First-mover advantage in trust-minimized coordination.",
  "resonance_delta": 0.23,
  "cached": true,
  "generated_at": "2026-03-28T10:00:00Z",
  "source_hash": "sha256:abc123...",
  "spec_ref": "spec-181"
}
```

### `POST /api/lenses`

Body: `{"lens_id": "regenerative", "name": "...", "description": "...", "archetype_axes": {"ecological": 0.9}}`
Response 201: lens created. Response 409: duplicate. Response 422: axis out of range.

### `GET /api/lenses/roi`

```json
{
  "total_translations_generated": 412,
  "unique_ideas_translated": 87,
  "unique_contributors_used_lens": 34,
  "most_viewed_lens": "engineer",
  "cross_lens_engagement_rate": 0.18,
  "avg_resonance_delta": 0.15,
  "spec_ref": "spec-181"
}
```

---

## Data Model

```python
class WorldviewLens(BaseModel):
    lens_id: str                        # slug, e.g. "libertarian"
    name: str
    description: str
    archetype_axes: dict[str, float]    # all values in [0.0, 1.0]
    framing_template: str | None = None
    is_builtin: bool = False
    created_at: datetime
    updated_at: datetime | None = None

class IdeaTranslation(BaseModel):
    idea_id: str
    lens_id: str
    original_name: str
    translated_summary: str
    emphasis: list[str]
    risk_framing: str
    opportunity_framing: str
    resonance_delta: float | None = None
    cached: bool
    generated_at: datetime
    source_hash: str
    spec_ref: str = "spec-181"

class TranslationRequest(BaseModel):
    force_regenerate: bool = False
    contributor_id: str | None = None
```

---

## News Ingestion Integration

When the news ingestion pipeline processes an article:
1. The article is tagged with the dominant lens of its source.
2. A contributor with a configured belief profile receives articles translated through
   their top worldview axis when the source lens diverges significantly.
3. `GET /api/news/{article_id}/translations/{lens_id}` surfaces alternative framings on demand.
4. Opt-in for MVP: news feed shows original article by default; a "View through my lens"
   toggle triggers the translation endpoint.

---

## Web Interface

### Idea Detail Page (`/ideas/{idea_id}`)

Add a **"View through another lens"** section below the idea body:
- Lens selector (tabs or dropdown showing the 6 builtin lenses)
- Translated summary in a styled callout box
- Resonance badge: "X% closer/further to your worldview" (if contributor logged in)

### Lens Browser Page (`/lenses`)

- Lists all registered lenses with archetype radar chart
- Each lens links to a gallery of the most-translated ideas in that lens

---

## Files to Create/Modify

- `api/app/routers/lenses.py` — new: `/api/lenses/*` and `/api/ideas/{id}/translations/*`
- `api/app/services/lens_service.py` — new: translation generation, caching, ROI
- `api/app/models/lens.py` — new: `WorldviewLens`, `IdeaTranslation`, `TranslationRequest`
- `api/app/db/lens_repo.py` — new: CRUD for lenses and translations (PostgreSQL)
- `api/app/main.py` — modify: `include_router(lenses_router)`
- `api/app/config/builtin_lenses.json` — new: 6 builtin lens definitions
- `api/tests/test_belief_systems_translation.py` — new: integration tests (12+ scenarios)
- `web/app/ideas/[id]/page.tsx` — modify: add lens selector section
- `web/app/lenses/page.tsx` — new: lens browser page

---

## Acceptance Tests

```bash
cd api && pytest -q tests/test_belief_systems_translation.py
```

All 12+ integration tests in `api/tests/test_belief_systems_translation.py` must pass.
Tests cover: lens CRUD, translation generation and caching, resonance delta calculation,
ROI endpoint, 404/409/422 error cases.

---

## Verification

The following commands can be run against `https://api.coherencycoin.com` to verify the feature is live.

**Scenario 1 — List all builtin lenses:**
```bash
curl -sS "https://api.coherencycoin.com/api/lenses" | jq '.lenses | length, .[0].lens_id'
# Expected: 6 (or more), "libertarian" (or another builtin lens_id)
```

**Scenario 2 — Translate an idea through the engineer lens:**
```bash
IDEA_ID=$(curl -sS "https://api.coherencycoin.com/api/ideas?limit=1" | jq -r '.ideas[0].id')
curl -sS "https://api.coherencycoin.com/api/ideas/$IDEA_ID/translations/engineer" | jq '{translated_summary, spec_ref}'
# Expected: translated_summary is non-empty string, spec_ref is "spec-181"
```

**Scenario 3 — Register a custom lens (201), then fail on duplicate (409):**
```bash
curl -sS -X POST "https://api.coherencycoin.com/api/lenses" \
  -H "Content-Type: application/json" \
  -d '{"lens_id":"test-spec181","name":"Test Lens","description":"A test lens","archetype_axes":{"pragmatic":0.8}}' | jq '.lens_id'
# Expected: "test-spec181" (HTTP 201)

curl -sS -X POST "https://api.coherencycoin.com/api/lenses" \
  -H "Content-Type: application/json" \
  -d '{"lens_id":"test-spec181","name":"Test Lens","description":"dup","archetype_axes":{"pragmatic":0.8}}' | jq '.detail'
# Expected: HTTP 409, detail contains "conflict" or similar message

curl -sS "https://api.coherencycoin.com/api/ideas/$IDEA_ID/translations/nonexistent_lens_xyz" | jq '.detail'
# Expected: HTTP 404 with detail (not 500)
```

**Scenario 4 — ROI endpoint proves lens usage:**
```bash
curl -sS "https://api.coherencycoin.com/api/lenses/roi" | jq '{total_translations_generated, cross_lens_engagement_rate, spec_ref}'
# Expected: total_translations_generated >= 1, spec_ref is "spec-181"
```

**Scenario 5 — Axis validation (422 on out-of-range):**
```bash
curl -sS -X POST "https://api.coherencycoin.com/api/lenses" \
  -H "Content-Type: application/json" \
  -d '{"lens_id":"bad-lens","name":"Bad","description":"Bad","archetype_axes":{"x":1.5}}' | jq '.detail'
# Expected: HTTP 422 with validation error about axis value out of range
```

---

## Proof of Value — How We Know This Is Working

The spec answers: **"How can we improve this idea, show whether it is working yet, and make that proof clearer over time?"**

**Short-term (first 2 weeks):**
- `total_translations_generated` grows week-over-week via `GET /api/lenses/roi`
- At least 6 builtin lenses are accessible via `GET /api/lenses`

**Medium-term (weeks 3–8):**
- `cross_lens_engagement_rate` reaches ≥ 0.10 (10% of contributors viewed an idea through a non-dominant lens)
- Track pairs of contributors with divergent `worldview_axes` who co-contribute after seeing an idea through each other's lens (`cross_lens_collaboration_events`)

**Long-term (months 2–6):**
- **Idea reach index**: `distinct lenses through which idea was viewed / 6` — an idea viewed through all 6 lenses has maximum perspective reach
- **News reframing adoption**: if opt-in lens filter on news is active for ≥ 5% of contributors, the framing-divergence gap is real and the product is solving it

These metrics are accessible via `GET /api/lenses/roi` and optionally through `/ops/lenses-dashboard` (follow-up).

---

## Out of Scope

- Automatic lens assignment based on contributor behavior (follow-up).
- LLM provider selection for translation generation (defaults to system LLM; routing spec applies).
- Fine-tuned lens models (MVP uses prompt engineering only).
- Push notifications when a new lens translation becomes available.
- Lens conflict detection (when two lenses give contradictory framings — follow-up).
- `GET /api/news/{article_id}/translations/{lens_id}` requires news pipeline being live — separate task.

---

## Risks and Assumptions

- **Risk**: LLM translation introduces bias or distortion of the original idea.
  **Mitigation**: Translations are labeled as lens-filtered; original always shown first; no translation replaces the source.

- **Risk**: Lens framing reinforces tribalism rather than bridging perspectives.
  **Mitigation**: Show translations side-by-side; default view includes the original; framing archetypes are epistemic stances, not political identities.

- **Risk**: Translation generation latency (LLM calls are slow).
  **Mitigation**: Cache aggressively per `(idea_id, lens_id, source_hash)`; surface `202 Accepted` async UX; precompute for high-value ideas.

- **Risk**: Abuse — flooding translation endpoint to exhaust LLM budget.
  **Mitigation**: Rate-limit per contributor and per idea; operator-level `force_regenerate` requires authentication (deferred to auth spec).

- **Assumption**: Contributor belief profiles (spec-169) are available; `resonance_delta` degrades gracefully to `null` if profile is missing.

---

## Known Gaps and Follow-up Tasks

- `POST /api/ideas/{idea_id}/translations/{lens_id}` (force-regenerate) needs operator authentication — follow-up auth spec task.
- `GET /api/news/{article_id}/translations/{lens_id}` depends on news pipeline being live — separate follow-up task.
- `/ops/lenses-dashboard` web page for aggregate lens stats — follow-up after MVP.
- `cc lenses translate --idea <id> --lens <name>` CLI convenience wrapper — follow-up task.
- Historical translation versioning (track how translations evolve as the idea evolves) — follow-up task.
- Cross-lens collaboration event tracking (`cross_lens_collaboration_events` table) — follow-up task.

---

## See Also

- [`specs/169-belief-system.md`](./169-belief-system.md) — Contributor worldview profiles
- [`specs/163-resonance-navigation.md`](./163-resonance-navigation.md) — Discovery layer using belief alignment
- [`specs/167-social-platform-bots.md`](./167-social-platform-bots.md) — Social distribution of translated framings
