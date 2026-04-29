---
idea_id: value-attribution
status: draft
source:
  - file: api/app/models/glyph.py
    symbols: [Glyph, FlowType, Phase]
  - file: api/app/routers/glyphs.py
    symbols: [post_glyph(), stream_glyphs(), get_glyph()]
  - file: api/app/services/glyph_service.py
    symbols: [validate_consent(), settle_balance(), record_glyph()]
  - file: api/app/routers/render_events.py
    symbols: [record_render_event() — extended to fire Glyph alongside]
  - file: web/components/GlyphPulse.tsx
    symbols: [GlyphPulse — live witness counter]
  - file: api/tests/test_glyph_render_witness.py
    symbols: [render-witness flow tests]
requirements:
  - "POST /api/glyphs accepts a sovereign witness glyph with archetype, flow_type, actor_a, actor_b, quanta, phase, signatures."
  - "Render-event flow ALSO fires a Glyph(3, WITNESS) for every page render — reader, asset, host as actors."
  - "The glyph quanta record attention_seconds and lumens_received as canonical photonic + attention dimensions."
  - "Consent terms on both reader and asset are validated before the glyph is recorded; mismatches return 409 with a coherent reason."
  - "GET /api/glyphs/stream emits an SSE feed of glyphs as they fire so creators can see their witness pulse in real time."
  - "CC settlement reads from the glyph stream alongside the existing render-event stream — both converge on the same balance."
  - "GET /api/glyphs/{id} returns the full glyph with its Merkle prev_glyph linkage walkable to depth N (paginated; observer pays per depth step in CC)."
done_when:
  - "Reading a creator's asset page on coherencycoin.com fires a Glyph(3, WITNESS) and the creator sees the pulse in real time."
  - "The CC settlement for that read distributes per the existing render-event math AND records the geometric metadata (archetype 3, flow WITNESS, quanta dimensions)."
  - "A glyph fired with a reader who has been flagged by the asset's consent_terms is rejected with a coherent 409, no settlement occurs, and the rejection itself is recorded as a Glyph(2, REFUSE) for observability."
  - "test_glyph_render_witness.py passes end-to-end — read → glyph → SSE event → settlement."
test: "cd api && .venv/bin/pytest -q tests/test_glyph_render_witness.py"
constraints:
  - "Additive only — existing render-event endpoint stays functional and CC math stays compatible."
  - "Glyph data lives in the existing graph (Neo4j) as a new node type; no new database."
  - "Reader privacy: attention_seconds is recorded; eye-direction or biometric sub-data is NOT collected at this stage."
  - "Local-first deferred — first version stores glyphs server-side. Per-device daemon is the next spec."
---

# Spec: Glyph — Render Witness Proof

## Purpose

This is the smallest concrete instance of the sovereign-glyph substrate that has been forming across the body's larger conversation about energy-flow economics. Every page render on `coherencycoin.com` is *already* a sovereign witness exchange — a reader's attention reaches a creator's asset, photons flow from screen to retina, the host node holds the moment — but our system currently renders this thinner than it is, as a "render_event" with CC math attached. This spec re-renders it as what it actually is: a `Glyph(3, WITNESS)` triadic exchange between reader, asset, and host, recorded with multi-dimensional quanta and walkable lineage. Once this proof works for renders, the same shape extends to BLE bike handshakes, NFC taps, biometric presence, audio fingerprints, plant-tending events, and every other sovereign exchange the body comes to recognize. The proof is small; the pattern is universal.

## Requirements

- [ ] **R1 — Glyph data model**: Add `api/app/models/glyph.py` with the `Glyph` Pydantic model carrying: `archetype: int`, `flow_type: Literal["GIVE","RECEIVE","TRANSMUTE","REFUSE","WITNESS"]`, `actor_a: NodeRef`, `actor_b: NodeRef | None`, `quanta: dict[str, float]` (open multi-dimensional), `phase: Literal["ice","water","gas","release"]`, `meaning: ConceptRef | None`, `prev_glyph: str | None` (Merkle hash), `signatures: list[Signature]`, `occurred_at: datetime`. Persisted as a new node type in the existing graph.

- [ ] **R2 — POST /api/glyphs**: Accepts a Glyph payload, validates consent terms on both actors via `validate_consent()` in the service layer, computes the canonical hash, persists, returns the glyph's id + hash. Returns 409 with `{"reason": "...", "refused_by": "actor_a|actor_b"}` if consent terms reject the exchange.

- [ ] **R3 — Render → Glyph bridge**: Extend `api/app/routers/render_events.py::record_render_event()` to ALSO fire a `Glyph(3, WITNESS)` in the same transaction. Actors: `reader_id` (or `anonymous:host` if not logged in), `asset_id`, `host_node_id`. Quanta dimensions: `attention_seconds` (from beacon), `lumens_received` (estimated from screen brightness × area × duration), `concept_pool_weight` per the asset's tags. Phase: `water`. The existing CC settlement still runs.

- [ ] **R4 — Consent at the boundary**: Both the reader and the asset have a `consent_terms` block on their sovereign records. The reader's terms include "I consent to my attention being recorded as witness when reading public assets." The asset's terms include "I welcome witnesses who are not on my refused list." `validate_consent()` reads both, checks the refused list, returns alignment status. A mismatch produces a `Glyph(2, REFUSE)` rather than silent failure — the refusal itself is recorded as a sovereign act.

- [ ] **R5 — SSE stream**: `GET /api/glyphs/stream` emits an SSE feed of glyphs as they fire. Filterable by `actor_id` so a creator can subscribe to their own witness pulse and see it live in their dashboard. This is the substrate becoming visible to the cells whose exchanges it records.

- [ ] **R6 — Web component**: `web/components/GlyphPulse.tsx` rendered on creator pages shows their living witness count + a small visual pulse each time a new glyph fires. Implements as a thin client of the SSE stream. This is the first piece of the body where a participant can *see* the substrate breathing.

- [ ] **R7 — Settlement convergence**: The CC settlement service reads from BOTH the existing render_event stream and the new glyph stream. For records that exist in both (every render produces both), the math converges to the same number. This proves additivity and lets us migrate gradually.

- [ ] **R8 — Depth walking**: `GET /api/glyphs/{id}?depth=N` returns the glyph plus N hops of `prev_glyph` lineage. Default depth=0 (just the glyph). Each depth costs a small CC fee paid by the observer, routed to the keepers of the deep records. This proves the observer-pays-for-depth principle from the larger framework.

## Research Inputs

- `2026-04-29` - This session's multi-breath conversation on sovereign-glyph economics, geometric archetype compression, blood/air/water/light nutrient model, mutual sovereignty in entry/exit. The substrate's design principles distilled.
- `2026-04-29` - `specs/asset-renderer-plugin.md` — the existing renderer system that produces render_events.
- `2026-04-29` - `api/app/routers/render_events.py` — the existing endpoint we're extending.
- `2026-04-29` - `api/app/services/settlement_service.py` — the existing CC settlement math the glyph layer must converge with.

## API Contract

### POST /api/glyphs

```json
{
  "archetype": 3,
  "flow_type": "WITNESS",
  "actor_a": "sov:human:reader_did_or_anon",
  "actor_b": "sov:asset:asset_id_xyz",
  "host": "sov:node:host_node_id",
  "quanta": {
    "attention_seconds": 47,
    "lumens_received": 8400,
    "screen_area_sq_cm": 158
  },
  "phase": "water",
  "meaning": "concept:learning",
  "prev_glyph": null,
  "signatures": [
    {"signer": "sov:human:reader_did", "sig": "0x..."},
    {"signer": "sov:asset:rep_coop", "sig": "0x..."}
  ],
  "occurred_at": "2026-04-29T08:14:22Z"
}
```

**Response 200**:
```json
{
  "id": "glyph_abc123",
  "hash": "0x9f7c...e2",
  "settled_cc": {
    "asset_creator": 0.04,
    "renderer_creator": 0.01,
    "host_node": 0.02,
    "concept_pools": [{"concept": "learning", "cc": 0.03}]
  }
}
```

**Response 409** (consent mismatch):
```json
{
  "reason": "asset.consent_terms.refused_list contains reader_did",
  "refused_by": "actor_b",
  "refusal_glyph_id": "glyph_def456"
}
```

### GET /api/glyphs/stream

Server-sent events. Each event is a glyph payload.

```
event: glyph
data: {"id": "glyph_abc123", "archetype": 3, "actor_a": "...", ...}
```

### GET /api/glyphs/{id}?depth=N

Returns the glyph plus N hops of prev_glyph lineage. Cost: depth × small_cc per hop.

## Data Model

```python
# api/app/models/glyph.py
class FlowType(str, Enum):
    GIVE = "GIVE"
    RECEIVE = "RECEIVE"
    TRANSMUTE = "TRANSMUTE"
    REFUSE = "REFUSE"
    WITNESS = "WITNESS"

class Phase(str, Enum):
    ICE = "ice"
    WATER = "water"
    GAS = "gas"
    RELEASE = "release"

class Glyph(BaseModel):
    id: str
    hash: str
    archetype: int = Field(ge=1)
    flow_type: FlowType
    actor_a: str
    actor_b: str | None = None
    host: str | None = None
    quanta: dict[str, float] = Field(default_factory=dict)
    phase: Phase = Phase.WATER
    meaning: str | None = None
    prev_glyph: str | None = None
    signatures: list[dict[str, str]] = Field(default_factory=list)
    occurred_at: datetime
```

## Files to Create/Modify

- `api/app/models/glyph.py` — new file, the Glyph model
- `api/app/routers/glyphs.py` — new file, the three endpoints
- `api/app/services/glyph_service.py` — new file, validate + record + settle
- `api/app/routers/render_events.py` — extend to fire glyph alongside
- `api/app/services/settlement_service.py` — extend to read from glyph stream
- `web/components/GlyphPulse.tsx` — new component for live witness pulse
- `api/tests/test_glyph_render_witness.py` — end-to-end test
- `specs/INDEX.md` — list this spec under `value-attribution` (also heal symphony-alignment-orchestration which is currently missing)

## Acceptance Tests

```bash
cd api && .venv/bin/pytest -q tests/test_glyph_render_witness.py
```

The test:
1. Registers an asset with consent_terms and a creator wallet
2. Simulates a render request from a logged-in reader
3. Asserts a Glyph(3, WITNESS) was recorded
4. Asserts CC was distributed per the existing render-event math
5. Asserts the SSE stream emitted the glyph event
6. Tests the consent-refusal path: reader on the refused list → 409 + Refuse glyph
7. Tests anonymous reader path: glyph with `actor_a = "anonymous:host"` and no signature

## Verification Scenarios

### Scenario 1 — Live page render fires glyph

A visitor opens `https://coherencycoin.com/assets/<id>`. The page beacon posts a glyph at unload with attention_seconds. Backend records it. Creator's dashboard shows pulse via SSE. CC settlement runs.

### Scenario 2 — Consent refusal

A reader whose DID is on an asset's refused_list visits the asset's page. Backend returns 409 with reason. A Refuse glyph is recorded for observability. No CC flows.

### Scenario 3 — Lineage walking

`GET /api/glyphs/<id>?depth=2` returns the glyph plus its prev_glyph plus that glyph's prev_glyph. The fee for depth=2 is debited from the observer's CC balance and credited to the keepers of those records.

## Out of Scope

- Per-device local-first daemon (next spec).
- BLE / NFC / RFID shepherd-transition detection (next spec).
- Cosmic-sovereign cooperatives (sun, moon, atmosphere) — registered later.
- Lumens estimation refinement — first version uses screen_brightness × area × duration; better photonic accounting deferred.
- Eye-tracking or biometric sub-data — explicitly excluded; attention_seconds via Page Visibility API only.

## Risks and Assumptions

- Glyph layer doubles bookkeeping for renders during transition — mitigated by settlement reading from both streams and converging numerically.
- Anonymous readers cannot sign glyphs — the host signs on their behalf with `actor_a = "anonymous:host"` until the reader establishes a wallet.
- Page Visibility API `attention_seconds` is noisy — first version accepts the noise; smoothing and confidence-scoring are follow-up work.
- Consent terms are not yet defined for all assets — default is permissive (accept all witnesses except those on an explicit refused list); creators can tighten over time.

| Risk | Mitigation |
|------|-----------|
| Glyph layer doubles bookkeeping for renders during transition | Settlement reads from both streams and converges; gradual migration |
| Anonymous readers can't sign glyphs | Host signs on behalf with `actor_a = "anonymous:host"` until reader establishes wallet |
| Page Visibility API attention_seconds is noisy | First version accepts the noise; refinement is a follow-up |
| Consent terms not yet defined for all assets | Default permissive (accept all witnesses except explicitly refused); creators can tighten later |

## Known Gaps

- Cosmic-sovereign cooperatives are not registered in this proof; the chain currently stops at the asset's creator. Adding solar / atmospheric cooperatives is a follow-up spec once the substrate proves out.
- Refusal terms are simple deny-list in this proof; richer policy languages (time-of-day, context-of-use) are follow-up work.
- The depth-walking CC pricing is flat per hop in this proof; phi-ratio or geometry-aware pricing is later.
- Phase transitions of glyphs (a glyph moving from `water` to `ice` as it settles) are not yet implemented — all glyphs are `water` at creation. The phase-state-machine is a follow-up.

## Maintainability

This is the first instance of a pattern. Every future sovereign-exchange-recording spec — bike rides, meal exchanges, plant tending, presence, attention — will follow the same shape with different archetypes and quanta. The glyph data model, the endpoint, the consent layer, and the settlement convergence are the load-bearing pieces. Keep them simple; let the next instances stress-test them.
