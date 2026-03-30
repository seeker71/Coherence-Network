# Spec 184 — Breath Cycle & Ice/Water/Gas Phase States: Organic Lifecycle for Every Entity

**Spec ID**: `task_3cb2649ca953cf2b`
**Status**: Draft
**Author**: product-manager agent
**Date**: 2026-03-28
**Source Concept**: Living Codex `BreathModule` + `PhaseModule`
**Priority**: High

---

## Summary

Every entity in Coherence Network — ideas, concepts, tasks, specs, contributors, news items — has a
**phase state** representing its current stage in an organic lifecycle. Phase is not binary (validated/
not-validated); it's a three-state spectrum drawn directly from the Living Codex PhaseModule:

- **Ice** (`ice`) — Stable, archived, reference. The entity is crystallized; useful as a foundation but
  not actively changing.
- **Water** (`water`) — Active, flowing, changing. The entity is being worked on, growing, or in motion.
- **Gas** (`gas`) — Speculative, volatile, experimental. The entity is unproven, exploratory, or
  in rapid flux.

Layered on top of phase is the **breath cycle** — four named moments that describe *how* an entity is
moving through its lifecycle at a given instant:

- **inhale** — gathering: pulling in context, dependencies, attention
- **hold** — integrating: synthesizing, stabilizing without committing
- **exhale** — releasing: publishing, shipping, distributing output
- **rest** — observing: dormant but aware; collecting ambient signals

Together, phase + breath-cycle replace the blunt `manifestation_status: validated/not-validated`
binary with a rich, Living Codex-native lifecycle signal that applies uniformly across all entity types.

---

## Purpose

The current `manifestation_status` enum (`none | partial | validated`) on ideas only, combined with
`IdeaLifecycle` (`active | paused | archived | retired`), creates an inconsistent vocabulary that does
not extend to concepts, tasks, specs, or contributors — and does not capture *how* active work is
moving. As a result:

1. **No shared lifecycle language across entity types.** An idea and a concept express "in progress"
   differently, making cross-entity reasoning fragile.
2. **Agents and humans lack fine-grained signaling.** "Active" tells you something is in motion but
   not *where* in the motion arc.
3. **The Living Codex BreathModule/PhaseModule is untapped.** Its Ice/Water/Gas triad is the natural
   vocabulary for system-level health, resonance, and entropy — but it has no API surface.

This spec establishes the **phase + breath-cycle API**, web indicators, and CLI commands that make the
Living Codex lifecycle model a first-class citizen in the network.

---

## Open Questions — Resolved in This Spec

### 1. Does phase replace `manifestation_status` and `lifecycle` on ideas?

**No — not immediately.** Phase is a *parallel, richer* lifecycle dimension, not a migration. Existing
`manifestation_status` and `IdeaLifecycle` remain read/write on ideas for backward compatibility.
The implementation stores `phase_state` and `breath_cycle` as new fields. A future spec may deprecate
the older fields once phase coverage is confirmed.

### 2. Which entity types support phase in MVP?

**Ideas and Concepts** in MVP. Phase is designed as a universal pattern but the first implementation
scopes to these two entity families to keep the initial PR reviewable. A follow-up spec extends to
tasks, specs, contributors.

### 3. Who can transition phase, and are transitions constrained?

Phase transitions are **user/agent-initiated** and **unconstrained in MVP** — any caller with write
access may PATCH phase to any valid value. Transition guard rules (e.g. "ice can only move to water
with explicit reason") are a follow-up feature. The API records `phase_changed_at` and `phase_set_by`
(contributor ID, if provided) for auditability.

### 4. How do we show the feature is working over time?

- The `/api/entities/{id}/phase` endpoint always returns `phase_state`, `breath_cycle`,
  `phase_changed_at`, and `phase_history` (last N transitions with timestamps).
- A **`GET /api/phase/summary`** endpoint returns counts per phase across all indexed entities — this
  proves distribution is tracked, not just individual records.
- The web card indicator reacts immediately to PATCH — a reviewer can change phase in the UI and
  observe the icon change without a page reload.

### 5. How does breath cycle relate to phase?

Breath cycle is orthogonal to phase — an `ice` entity can breathe (`rest` is most common; `inhale`
and `hold` permitted). A `gas` entity is most commonly `inhale` or `exhale`. The combination gives
a richer signal: `water/exhale` = actively shipping; `ice/rest` = stable reference; `gas/inhale` =
gathering context before committing.

---

## Requirements

- [ ] **R1 — Phase model** — Three valid `phase_state` values: `ice`, `water`, `gas`. Four valid
  `breath_cycle` values: `inhale`, `hold`, `exhale`, `rest`. Both must be validated via Pydantic enum.
- [ ] **R2 — Entity scope (MVP)** — Phase stored and retrievable for entities with entity type `idea`
  and `concept`. Response includes `entity_id`, `entity_type`, `phase_state`, `breath_cycle`,
  `phase_changed_at` (ISO 8601 UTC), `breath_changed_at`, `phase_set_by` (nullable contributor_id).
- [ ] **R3 — GET /api/entities/{id}/phase** — Returns current phase record for entity. Returns 404
  if entity does not exist. Returns 422 if entity type is not yet supported.
- [ ] **R4 — PATCH /api/entities/{id}/phase** — Updates `phase_state` and/or `breath_cycle` in a
  single request. Validates the enum values; returns 422 for invalid values. Returns 200 on success
  with the updated phase record.
- [ ] **R5 — Phase history** — GET phase returns `phase_history`: list of last 10 transitions with
  `from_phase`, `to_phase`, `changed_at`, `changed_by`. Enables proof that changes are recorded.
- [ ] **R6 — GET /api/entities/{id}/breath-cycle** — Returns current breath_cycle value and
  `last_N_breaths` (last 5 breath transitions) for rhythm visualization on the detail page.
- [ ] **R7 — GET /api/phase/summary** — Returns aggregate counts: `{ice: N, water: N, gas: N,
  unknown: N, breath_distribution: {inhale: N, hold: N, exhale: N, rest: N}}`. Used to prove
  the feature is populating data over time.
- [ ] **R8 — Default phase on create** — New ideas default to `phase_state: gas`, `breath_cycle:
  inhale`. New concepts default to `phase_state: water`, `breath_cycle: hold`. These defaults reflect
  the Living Codex model (new ideas are speculative; concepts are in-flow).
- [ ] **R9 — Web phase indicator** — Every idea card and concept card in the web UI shows a phase
  icon: snowflake for `ice`, wave for `water`, cloud for `gas`. Icon chosen from available emoji or
  SVG in the existing shadcn/ui component library.
- [ ] **R10 — Web breath visualization** — The idea detail page shows current `breath_cycle` as a
  labeled badge next to the phase icon and a mini timeline of last 5 breath transitions.
- [ ] **R11 — CLI `cc phase <entity-id>`** — Prints current phase and breath cycle for entity.
  Displays as: `<entity-id> [water/exhale] changed 2h ago by contributor-42`.
- [ ] **R12 — CLI `cc phase set <entity-id> <phase>`** — Updates phase_state. Optional flag
  `--breath <cycle>` to also set breath_cycle in same call. Prints updated values on success.
- [ ] **R13 — No deletion** — Phase records are never deleted; `DELETE /api/entities/{id}/phase`
  returns 405 (Method Not Allowed).
- [ ] **R14 — Tests** — Automated pytest tests cover: GET 200, PATCH 200, PATCH 422 (bad enum),
  GET 404 (unknown entity), summary endpoint, and breath-cycle endpoint.

---

## API Contract

### `GET /api/entities/{id}/phase`

**Path parameters**
- `id`: entity ID (string, e.g., `idea-abc123`, `concept-xyz789`)

**Response 200**
```json
{
  "entity_id": "idea-abc123",
  "entity_type": "idea",
  "phase_state": "water",
  "breath_cycle": "exhale",
  "phase_changed_at": "2026-03-28T14:22:00Z",
  "breath_changed_at": "2026-03-28T14:22:00Z",
  "phase_set_by": "contributor-42",
  "phase_history": [
    {
      "from_phase": "gas",
      "to_phase": "water",
      "from_breath": "inhale",
      "to_breath": "exhale",
      "changed_at": "2026-03-28T14:22:00Z",
      "changed_by": "contributor-42"
    }
  ]
}
```

**Response 404**
```json
{ "detail": "Entity not found: idea-nonexistent" }
```

**Response 422**
```json
{ "detail": "Unsupported entity type: task (MVP supports: idea, concept)" }
```

---

### `PATCH /api/entities/{id}/phase`

**Request body**
```json
{
  "phase_state": "ice",
  "breath_cycle": "rest",
  "set_by": "contributor-42"
}
```
All fields optional; at least one of `phase_state` or `breath_cycle` must be present.

**Response 200** — updated phase record (same shape as GET 200)

**Response 422**
```json
{ "detail": "Invalid phase_state 'frozen': must be one of ice, water, gas" }
```

---

### `GET /api/entities/{id}/breath-cycle`

**Response 200**
```json
{
  "entity_id": "idea-abc123",
  "current_breath": "exhale",
  "breath_changed_at": "2026-03-28T14:22:00Z",
  "last_n_breaths": [
    { "breath": "inhale", "at": "2026-03-28T12:00:00Z" },
    { "breath": "hold",   "at": "2026-03-28T13:00:00Z" },
    { "breath": "exhale", "at": "2026-03-28T14:22:00Z" }
  ]
}
```

---

### `GET /api/phase/summary`

**Response 200**
```json
{
  "total_entities_with_phase": 142,
  "phase_distribution": {
    "ice": 31,
    "water": 88,
    "gas": 23
  },
  "breath_distribution": {
    "inhale": 40,
    "hold": 25,
    "exhale": 55,
    "rest": 22
  },
  "computed_at": "2026-03-28T14:30:00Z"
}
```

---

## Data Model

```yaml
PhaseState (enum):
  values: [ice, water, gas]
  description: |
    ice = stable, archived, reference
    water = active, flowing, changing
    gas = speculative, volatile, experimental

BreathCycle (enum):
  values: [inhale, hold, exhale, rest]
  description: |
    inhale = gathering context, dependencies, attention
    hold = integrating, synthesizing, not yet committing
    exhale = releasing, shipping, distributing output
    rest = dormant but observing; collecting ambient signals

EntityPhase (DB record / API response):
  entity_id: string (FK to idea or concept)
  entity_type: string (idea | concept)
  phase_state: PhaseState
  breath_cycle: BreathCycle
  phase_changed_at: datetime (UTC)
  breath_changed_at: datetime (UTC)
  phase_set_by: string | null (contributor_id)

PhaseHistoryEntry:
  entity_id: string
  from_phase: PhaseState | null
  to_phase: PhaseState
  from_breath: BreathCycle | null
  to_breath: BreathCycle
  changed_at: datetime (UTC)
  changed_by: string | null
```

**PostgreSQL tables (new)**:

```sql
CREATE TABLE entity_phase (
    entity_id         TEXT         NOT NULL,
    entity_type       TEXT         NOT NULL,
    phase_state       TEXT         NOT NULL DEFAULT 'gas',
    breath_cycle      TEXT         NOT NULL DEFAULT 'inhale',
    phase_changed_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    breath_changed_at TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    phase_set_by      TEXT,
    PRIMARY KEY (entity_id)
);

CREATE TABLE entity_phase_history (
    id           SERIAL       PRIMARY KEY,
    entity_id    TEXT         NOT NULL,
    entity_type  TEXT         NOT NULL,
    from_phase   TEXT,
    to_phase     TEXT         NOT NULL,
    from_breath  TEXT,
    to_breath    TEXT         NOT NULL,
    changed_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    changed_by   TEXT
);

CREATE INDEX idx_entity_phase_type    ON entity_phase(entity_type);
CREATE INDEX idx_entity_phase_state   ON entity_phase(phase_state);
CREATE INDEX idx_phase_history_entity ON entity_phase_history(entity_id);
```

---

## Files to Create / Modify

| File | Action | Notes |
|------|--------|-------|
| `api/app/models/phase.py` | **Create** | `PhaseState`, `BreathCycle` enums; `EntityPhase`, `EntityPhaseUpdate`, `PhaseHistoryEntry`, `PhaseBreathCycle`, `PhaseSummary` Pydantic models |
| `api/app/services/phase_service.py` | **Create** | `get_entity_phase`, `patch_entity_phase`, `get_breath_cycle`, `get_phase_summary` — all DB-backed |
| `api/app/routers/phase.py` | **Create** | FastAPI router for `/api/entities/{id}/phase`, `/api/entities/{id}/breath-cycle`, `/api/phase/summary` |
| `api/app/main.py` | **Modify** | Register new `phase` router |
| `api/migrations/` | **Create** | Alembic migration or raw SQL for `entity_phase` and `entity_phase_history` tables |
| `api/tests/test_phase.py` | **Create** | Full pytest suite (GET, PATCH, 404, 422, summary, breath-cycle) |
| `web/components/PhaseIndicator.tsx` | **Create** | Reusable phase icon component: receives `phase_state`, renders phase icon + breath badge |
| `web/components/BreathTimeline.tsx` | **Create** | Mini timeline of last 5 breath transitions for idea detail page |
| `web/app/ideas/[id]/page.tsx` | **Modify** | Add `PhaseIndicator` + `BreathTimeline` on idea detail |
| `web/components/IdeaCard.tsx` (or equivalent) | **Modify** | Add `PhaseIndicator` to card header |
| `web/components/ConceptCard.tsx` (or equivalent) | **Modify** | Add `PhaseIndicator` to card header |
| `docs/RUNBOOK.md` | **Modify** | Add "Phase and Breath Cycle" section with API examples and CLI usage |

---

## Web UX

### Phase icon (every entity card)

Each entity card shows a phase icon in the top-left of its header:
- Ice phase: snowflake icon — entity is stable, crystallized, reference material
- Water phase: wave icon — entity is active, in motion
- Gas phase: cloud icon — entity is speculative, experimental

The icon is accompanied by a small badge showing the breath state: e.g., `[water/exhale]`.

### Breath timeline on detail page

The idea detail page includes a "Breath Cycle" section below the main metadata:
- Current breath state as a labeled badge
- A compact list of the last 5 breath transitions with timestamps and who made the change

---

## CLI

```bash
# Read phase for an entity
cc phase idea-abc123
# Output: idea-abc123 [water/exhale] changed 2h ago by contributor-42

# Set phase only
cc phase set idea-abc123 ice
# Output: Updated idea-abc123 -> phase: ice (breath unchanged: exhale)

# Set phase and breath in one call
cc phase set idea-abc123 ice --breath rest
# Output: Updated idea-abc123 -> ice/rest

# Aggregate summary across all entities
cc phase summary
# Output:
# Phase distribution: ice=31  water=88  gas=23
# Breath distribution: inhale=40  hold=25  exhale=55  rest=22
```

---

## Verification Scenarios

### Scenario 1 — Create idea, check default phase (gas/inhale)

**Setup**: API is running; no prior phase record for a new idea.

**Action**:
```bash
API=https://api.coherencycoin.com

# Step 1: create idea
IDEA=$(curl -s -X POST $API/api/ideas \
  -H "Content-Type: application/json" \
  -d '{"name":"Breath Test Idea","description":"Verifying default phase","potential_value":1,"estimated_cost":1}')
IDEA_ID=$(echo $IDEA | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# Step 2: read phase
curl -s $API/api/entities/$IDEA_ID/phase
```

**Expected result**: HTTP 200, body contains `"phase_state": "gas"`, `"breath_cycle": "inhale"`,
`"phase_history": []`.

**Edge case**: `GET $API/api/entities/nonexistent-id-xyz/phase` returns HTTP 404 with
`{"detail": "Entity not found: nonexistent-id-xyz"}` — not a 500 error.

---

### Scenario 2 — Transition idea from gas to water, verify history is recorded

**Setup**: Idea from Scenario 1 exists with `phase_state: gas`, `breath_cycle: inhale`.

**Action**:
```bash
# PATCH to water/exhale
curl -s -X PATCH $API/api/entities/$IDEA_ID/phase \
  -H "Content-Type: application/json" \
  -d '{"phase_state":"water","breath_cycle":"exhale","set_by":"contributor-99"}'

# Read back
curl -s $API/api/entities/$IDEA_ID/phase
```

**Expected result**: PATCH returns HTTP 200 with `"phase_state": "water"`, `"breath_cycle": "exhale"`.
GET returns same values plus `"phase_set_by": "contributor-99"` and `phase_history` with one entry:
`from_phase: "gas"`, `to_phase: "water"`, `from_breath: "inhale"`, `to_breath: "exhale"`.

**Edge case**: `PATCH $API/api/entities/$IDEA_ID/phase -d '{"phase_state":"frozen"}'` returns HTTP 422
with `{"detail": "Invalid phase_state 'frozen': must be one of ice, water, gas"}`.

---

### Scenario 3 — Full create-read-update cycle via CLI

**Setup**: cc CLI installed; entity `idea-abc123` exists.

**Action**:
```bash
cc phase set idea-abc123 ice --breath rest
cc phase idea-abc123
```

**Expected result**:
- `set` exits 0, prints: `Updated idea-abc123 -> ice/rest`
- `get` prints: `idea-abc123 [ice/rest] changed <timestamp>`

**Edge case**: `cc phase set idea-abc123 frozen` exits non-zero with error message:
`Invalid phase value 'frozen'. Valid values: ice, water, gas`

---

### Scenario 4 — Breath cycle endpoint and timeline

**Setup**: Idea has received 3 breath transitions: inhale (created) -> hold -> exhale.

**Action**:
```bash
curl -s $API/api/entities/$IDEA_ID/breath-cycle
```

**Expected result**: HTTP 200, `"current_breath": "exhale"`, `"last_n_breaths"` array contains
3 objects each with `"breath"` (string) and `"at"` (ISO 8601 UTC string), in chronological order.

**Edge case**: Entity has only 1 breath entry — `last_n_breaths` returns a single-item array (not error).
Entity does not exist — HTTP 404.

---

### Scenario 5 — Phase summary reflects aggregate state and proves feature is active

**Setup**: At least 5 entities exist with varying phase states in the system.

**Action**:
```bash
# First call
curl -s $API/api/phase/summary

# Create a new gas/inhale idea
curl -s -X POST $API/api/ideas \
  -H "Content-Type: application/json" \
  -d '{"name":"New Gas Idea","description":"summary proof","potential_value":1,"estimated_cost":1}'

# Second call — gas count must have increased by 1
curl -s $API/api/phase/summary
```

**Expected result (first call)**: HTTP 200, `phase_distribution` keys `ice`, `water`, `gas` all present
as non-negative integers; `breath_distribution` keys `inhale`, `hold`, `exhale`, `rest` all present;
`computed_at` is an ISO 8601 UTC string.

**Expected result (second call)**: `phase_distribution.gas` is 1 greater than first call.

**Edge case**: No entities have phase records yet — returns all zeros for all counts, not 404 or 500.

---

## Risks and Assumptions

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Phase records sparse until all entities are touched — most return null until first PATCH | High | `GET /api/entities/{id}/phase` auto-creates default record on first read (upsert-on-read). Document this side-effect clearly in RUNBOOK.md. |
| Breath cycle transitions become noisy if agents update on every step | Medium | PATCH is a no-op if values are identical — does not add a history entry if phase and breath unchanged. |
| Phase indicator on every card increases render overhead | Low | PhaseIndicator is static; phase fields are included in the existing list payload, no extra async fetch per card. |
| `manifestation_status` and `phase_state` diverge in meaning over time | Medium | Document clearly: `manifestation_status` = idea-specific provenance track; `phase_state` = universal lifecycle signal. Deprecation is a separate spec. |
| DB migration in production fails or deadlocks | Low | New tables are purely additive; no existing columns dropped or renamed. Safe to run against live DB. |

---

## Known Gaps and Follow-up Tasks

1. **Entity coverage** — Tasks, specs, contributors, and news items are not covered in MVP. A follow-up
   spec extends `entity_phase` to all entity types by adding entity_type discriminators.
2. **Transition guards** — No rules on valid transitions (e.g., `ice -> gas` should require a written
   reason). Follow-up spec adds `TransitionPolicy` model and required `transition_reason` field.
3. **Automatic breath advancement** — Agents could auto-advance breath cycle based on task events:
   task started -> inhale; spec accepted -> hold; PR merged -> exhale; dormant for 7d -> rest.
   Follow-up spec ties agent lifecycle events to breath transitions.
4. **Phase-aware list queries** — `GET /api/ideas?phase=water` is not in scope. Follow-up spec adds
   phase filter parameter to idea and concept list endpoints.
5. **Web phase dashboard filter** — Filter ideas/concepts by phase (show only `gas` for triage; only
   `ice` for reference browsing). Follow-up spec.
6. **Deprecation of `manifestation_status`** — Once phase achieves full coverage confirmed via
   `GET /api/phase/summary`, `manifestation_status` can be deprecated and removed. Separate spec
   required with migration plan.

---

## Task Card

```yaml
goal: >
  Implement Ice/Water/Gas phase states and breath cycle for ideas and concepts,
  with GET/PATCH API endpoints, web card indicators, and CLI commands.
files_allowed:
  - api/app/models/phase.py
  - api/app/services/phase_service.py
  - api/app/routers/phase.py
  - api/app/main.py
  - api/migrations/
  - api/tests/test_phase.py
  - web/components/PhaseIndicator.tsx
  - web/components/BreathTimeline.tsx
  - web/app/ideas/[id]/page.tsx
  - web/components/IdeaCard.tsx
  - web/components/ConceptCard.tsx
  - docs/RUNBOOK.md
done_when:
  - GET /api/entities/{id}/phase returns phase_state, breath_cycle, phase_history
  - PATCH /api/entities/{id}/phase updates values and records history entry
  - GET /api/entities/{id}/breath-cycle returns current breath + last 5 transitions
  - GET /api/phase/summary returns ice/water/gas and breath counts (zeros ok for empty DB)
  - New ideas default to gas/inhale; new concepts default to water/hold
  - Phase icon visible on idea cards and concept cards in web UI
  - Breath timeline visible on idea detail page
  - cc phase <id> and cc phase set <id> <phase> work end-to-end
  - All 5 verification scenarios pass against production
commands:
  - pytest api/tests/test_phase.py -v
  - curl -s $API/api/phase/summary
  - cc phase summary
constraints:
  - Do not modify existing manifestation_status or IdeaLifecycle fields
  - Do not delete phase history records
  - Phase transitions must be recorded atomically with the main record update
  - DELETE /api/entities/{id}/phase must return 405
  - Phase values must be validated via Pydantic enum, not raw string comparison
```

---

## Research Inputs

| Date | Source | Relevance |
|------|--------|-----------|
| 2026-03-28 | Living Codex BreathModule (internal) | Inhale/hold/exhale/rest breath cycle semantics |
| 2026-03-28 | Living Codex PhaseModule (internal) | Ice/Water/Gas phase triad definitions |
| 2026-03-28 | `api/app/models/idea.py` | Existing `ManifestationStatus`, `IdeaLifecycle` enums — must coexist |
| 2026-03-28 | `specs/TEMPLATE.md` | Spec format and section requirements |
| 2026-03-28 | `specs/176-idea-lifecycle-closure.md` | Precedent: lifecycle expansion via additive fields |
