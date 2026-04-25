---
idea_id: knowledge-and-resonance
status: draft
source:
  - file: api/app/models/phase.py
    symbols: [PhaseState, BreathCyclePhase, EntityPhaseResponse, PhaseTransitionRequest, BreathCycleResponse, PhaseTransitionEvent]
  - file: api/app/services/phase_service.py
    symbols: [get_entity_phase, set_entity_phase, get_breath_cycle, record_breath_transition, list_phase_history]
  - file: api/app/routers/phase.py
    symbols: [get_phase, patch_phase, get_breath_cycle_handler]
  - file: api/app/main.py
    symbols: [include_router]
  - file: api/alembic/versions/add_phase_state_to_entities.py
    symbols: [upgrade, downgrade]
  - file: web/components/PhaseIndicator.tsx
    symbols: [PhaseIndicator]
  - file: web/components/BreathCycleViz.tsx
    symbols: [BreathCycleViz]
  - file: web/app/ideas/[id]/page.tsx
    symbols: [IdeaDetailPage]
  - file: web/components/IdeaCard.tsx
    symbols: [IdeaCard]
requirements:
  - "PhaseState enum: ice | water | gas — stored per entity (ideas + concepts)"
  - "BreathCyclePhase enum: inhale | hold | exhale | rest — current breath step"
  - "GET /api/entities/{entity_type}/{id}/phase returns {phase, breath_cycle_phase, transitioned_at, transitioned_by}"
  - "PATCH /api/entities/{entity_type}/{id}/phase accepts {phase, breath_cycle_phase, reason} — records transition event"
  - "GET /api/entities/{entity_type}/{id}/breath-cycle returns last 10 transition events with timestamps and actors"
  - "entity_type path param accepts: idea | concept"
  - "Phase indicator on every IdeaCard: snowflake icon for ice, wave for water, cloud for gas"
  - "BreathCycleViz on idea detail page: circular 4-segment ring showing inhale/hold/exhale/rest with current step highlighted"
  - "CLI: coh phase <entity-type> <entity-id> — shows current phase and breath step"
  - "CLI: coh phase set <entity-type> <entity-id> <phase> --breath <breath-phase> --reason <text>"
  - "Replaces binary validated/not-validated; existing ideas with stage=validated default to water"
done_when:
  - "GET /api/entities/idea/{id}/phase returns {phase, breath_cycle_phase, transitioned_at} with 200"
  - "PATCH /api/entities/idea/{id}/phase with {phase: gas} persists and returns updated state"
  - "GET /api/entities/idea/{id}/breath-cycle returns ordered list of transition events"
  - "IdeaCard in web renders PhaseIndicator icon matching the entity phase"
  - "Idea detail page renders BreathCycleViz with current breath_cycle_phase highlighted"
  - "coh phase idea <id> prints phase and breath step"
  - "All api/tests/test_breath_cycle_phases.py tests pass"
test: "cd api && python -m pytest tests/test_breath_cycle_phases.py -q"
constraints:
  - "entity_type is an enum — only idea and concept are valid in v1; 400 for unknown types"
  - "Phase transitions are append-only events — never mutate history"
  - "Default phase for all existing entities is water; default breath_cycle_phase is rest"
  - "No auth required for GET; PATCH requires valid API key"
  - "phase_state column added via Alembic migration; handles both SQLite (dev) and PostgreSQL (prod)"
---

# Spec: Breath Cycle Phases — Organic Lifecycle for Every Entity

## Purpose

Every idea and concept in the Coherence Network exists somewhere on a lifecycle arc. The current binary `validated / not-validated` flag collapses a rich spectrum into a switch. This spec adds three phase states — **Ice** (crystallized, stable, archival), **Water** (active, flowing, mutable), **Gas** (speculative, experimental, volatile) — and four breath cycle steps — **Inhale** (gathering), **Hold** (integrating), **Exhale** (releasing), **Rest** (observing) — to every entity. Phase indicators appear on every card and a breath cycle visualization on idea detail pages. The CLI gains `coh phase` commands. This is the system that shows whether something is alive, resting, or composting.

## Requirements

- [ ] **R1**: Add `phase_state` (default `water`) and `breath_cycle_phase` (default `rest`) columns to the `ideas` and `concepts` tables via Alembic migration. Migration must handle both SQLite (dev/test) and PostgreSQL (prod) — use `op.add_column` with `server_default`.

- [ ] **R2**: Create `api/app/models/phase.py` with:
  - `PhaseState(str, Enum)`: `ice`, `water`, `gas`
  - `BreathCyclePhase(str, Enum)`: `inhale`, `hold`, `exhale`, `rest`
  - `EntityPhaseResponse(BaseModel)`: `entity_type`, `entity_id`, `phase`, `breath_cycle_phase`, `transitioned_at`, `transitioned_by` (optional)
  - `PhaseTransitionRequest(BaseModel)`: `phase` (optional), `breath_cycle_phase` (optional), `reason` (optional)
  - `PhaseTransitionEvent(BaseModel)`: `id`, `entity_type`, `entity_id`, `from_phase`, `to_phase`, `from_breath`, `to_breath`, `reason`, `transitioned_at`, `transitioned_by`
  - `BreathCycleResponse(BaseModel)`: `entity_type`, `entity_id`, `current_phase`, `current_breath`, `history: list[PhaseTransitionEvent]`

- [ ] **R3**: Create `api/app/services/phase_service.py` with:
  - `get_entity_phase(entity_type, entity_id, db) → EntityPhaseResponse` — reads from DB
  - `set_entity_phase(entity_type, entity_id, request, db, actor) → EntityPhaseResponse` — writes new phase/breath, appends transition event
  - `get_breath_cycle(entity_type, entity_id, db) → BreathCycleResponse` — returns current state + last 10 events
  - `list_phase_history(entity_type, entity_id, db, limit=10) → list[PhaseTransitionEvent]`
  - Transition events stored in a `phase_transition_events` table (id, entity_type, entity_id, from_phase, to_phase, from_breath, to_breath, reason, transitioned_at, transitioned_by)

- [ ] **R4**: Create `api/app/routers/phase.py` with:
  - `GET /api/entities/{entity_type}/{id}/phase` → `EntityPhaseResponse`
  - `PATCH /api/entities/{entity_type}/{id}/phase` → `EntityPhaseResponse` (requires API key)
  - `GET /api/entities/{entity_type}/{id}/breath-cycle` → `BreathCycleResponse`

- [ ] **R5**: Register the phase router in `api/app/main.py` — `app.include_router(phase_router, prefix="/api")`.

- [ ] **R6**: Create `web/components/PhaseIndicator.tsx` — a small icon component that renders:
  - `❄` (snowflake SVG) for `ice`
  - `〜` (wave SVG) for `water`
  - `☁` (cloud SVG) for `gas`
  - Accepts `phase: "ice" | "water" | "gas"` and optional `size` prop.

- [ ] **R7**: Update `web/components/IdeaCard.tsx` to render `<PhaseIndicator phase={idea.phase} />` in the card header alongside the existing stage badge.

- [ ] **R8**: Create `web/components/BreathCycleViz.tsx` — a circular 4-segment ring visualization (SVG or CSS) with segments: Inhale / Hold / Exhale / Rest. The current `breath_cycle_phase` segment is highlighted; the rest are dimmed. Accepts `breathPhase: "inhale" | "hold" | "exhale" | "rest"` and `phase: PhaseState` props (the ring color reflects the entity phase).

- [ ] **R9**: Add `<BreathCycleViz>` to `web/app/ideas/[id]/page.tsx` — fetches from `/api/entities/idea/{id}/breath-cycle` and renders the visualization below the idea title.

- [ ] **R10**: Add CLI commands to the `coh` CLI (MCP tool `coherence_phase_get` / `coherence_phase_set` or equivalent):
  - `coh phase <entity-type> <entity-id>` — prints: `phase: water | breath: rest | since: 2026-04-25T10:00:00Z`
  - `coh phase set <entity-type> <entity-id> <phase> [--breath <step>] [--reason <text>]`

- [ ] **R11**: Write `api/tests/test_breath_cycle_phases.py` covering:
  - GET phase returns defaults for new entity
  - PATCH phase persists transition and returns updated state
  - GET breath-cycle returns ordered history list
  - Invalid entity_type returns 400
  - Unknown entity_id returns 404

- [ ] **R12**: Backfill migration: existing ideas with `stage = validated` default to `phase = water, breath_cycle_phase = rest`. All others also default to `water / rest`.

## Research Inputs

- `2026-04-25` - Living Codex BreathModule + PhaseModule — source ontology for the three phase states and four breath cycle steps
- `2026-04-25` - `ideas/knowledge-and-resonance.md` — parent idea defines Ice/Water/Gas and the breath lifecycle as a key capability

## API Contract

### `GET /api/entities/{entity_type}/{id}/phase`

Path params: `entity_type` in `[idea, concept]`, `id` = entity slug or UUID.

**Response 200**
```json
{
  "entity_type": "idea",
  "entity_id": "agent-pipeline",
  "phase": "water",
  "breath_cycle_phase": "exhale",
  "transitioned_at": "2026-04-25T10:00:00Z",
  "transitioned_by": null
}
```

**Response 400** — unknown entity_type
```json
{"detail": "Unknown entity_type 'task'. Valid types: idea, concept"}
```

**Response 404** — entity not found
```json
{"detail": "idea 'unknown-slug' not found"}
```

---

### `PATCH /api/entities/{entity_type}/{id}/phase`

Requires `X-API-Key` header.

**Request body**
```json
{
  "phase": "ice",
  "breath_cycle_phase": "rest",
  "reason": "Concept fully crystallized after validation sprint"
}
```

`phase` and `breath_cycle_phase` are both optional — omit either to keep current value.

**Response 200**
```json
{
  "entity_type": "idea",
  "entity_id": "agent-pipeline",
  "phase": "ice",
  "breath_cycle_phase": "rest",
  "transitioned_at": "2026-04-25T11:00:00Z",
  "transitioned_by": "dev-key"
}
```

---

### `GET /api/entities/{entity_type}/{id}/breath-cycle`

**Response 200**
```json
{
  "entity_type": "idea",
  "entity_id": "agent-pipeline",
  "current_phase": "ice",
  "current_breath": "rest",
  "history": [
    {
      "id": "evt_001",
      "entity_type": "idea",
      "entity_id": "agent-pipeline",
      "from_phase": "water",
      "to_phase": "ice",
      "from_breath": "exhale",
      "to_breath": "rest",
      "reason": "Concept fully crystallized",
      "transitioned_at": "2026-04-25T11:00:00Z",
      "transitioned_by": "dev-key"
    }
  ]
}
```

## Data Model

```yaml
# New columns on ideas table
ideas:
  phase_state: VARCHAR(10) DEFAULT 'water'  # ice | water | gas
  breath_cycle_phase: VARCHAR(10) DEFAULT 'rest'  # inhale | hold | exhale | rest

# New columns on concepts table (same fields)
concepts:
  phase_state: VARCHAR(10) DEFAULT 'water'
  breath_cycle_phase: VARCHAR(10) DEFAULT 'rest'

# New table
phase_transition_events:
  id: VARCHAR(36) PRIMARY KEY  # uuid4
  entity_type: VARCHAR(20) NOT NULL  # idea | concept
  entity_id: VARCHAR(255) NOT NULL
  from_phase: VARCHAR(10)  # null for initial seed
  to_phase: VARCHAR(10) NOT NULL
  from_breath: VARCHAR(10)
  to_breath: VARCHAR(10) NOT NULL
  reason: TEXT
  transitioned_at: TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  transitioned_by: VARCHAR(255)  # api key actor or null
```

## Files

### New files to create:
- `api/app/models/phase.py` — Pydantic models: `PhaseState`, `BreathCyclePhase`, `EntityPhaseResponse`, `PhaseTransitionRequest`, `PhaseTransitionEvent`, `BreathCycleResponse`
- `api/app/services/phase_service.py` — service: `get_entity_phase`, `set_entity_phase`, `get_breath_cycle`, `list_phase_history`
- `api/app/routers/phase.py` — route handlers for GET/PATCH phase and GET breath-cycle
- `api/alembic/versions/add_phase_state_to_entities.py` — migration adding columns + `phase_transition_events` table
- `api/tests/test_breath_cycle_phases.py` — flow tests (GET defaults, PATCH persists, history ordered, 400/404 cases)
- `web/components/PhaseIndicator.tsx` — icon component (snowflake / wave / cloud)
- `web/components/BreathCycleViz.tsx` — 4-segment circular SVG ring with current breath highlighted

### Existing files to modify:
- `api/app/main.py` — register `phase_router` under `/api` prefix
- `web/components/IdeaCard.tsx` — add `<PhaseIndicator phase={idea.phase_state} />` in card header
- `web/app/ideas/[id]/page.tsx` — fetch breath-cycle endpoint and render `<BreathCycleViz>`

## Verification Scenarios

### Scenario 1 — GET phase returns water/rest defaults
```bash
# Seed a known idea, then read its phase
curl -s https://api.coherencycoin.com/api/entities/idea/agent-pipeline/phase | \
  python3 -c "import sys,json; d=json.load(sys.stdin); assert d['phase']=='water', d; assert d['breath_cycle_phase']=='rest', d; print('PASS: defaults correct')"
```
Expected output: `PASS: defaults correct`

### Scenario 2 — PATCH transitions phase and returns new state
```bash
curl -s -X PATCH https://api.coherencycoin.com/api/entities/idea/agent-pipeline/phase \
  -H "X-API-Key: dev-key" \
  -H "Content-Type: application/json" \
  -d '{"phase":"ice","breath_cycle_phase":"rest","reason":"Spec complete"}' | \
  python3 -c "import sys,json; d=json.load(sys.stdin); assert d['phase']=='ice', d; print('PASS: phase is now ice')"
```
Expected output: `PASS: phase is now ice`

### Scenario 3 — GET breath-cycle returns transition history
```bash
curl -s https://api.coherencycoin.com/api/entities/idea/agent-pipeline/breath-cycle | \
  python3 -c "import sys,json; d=json.load(sys.stdin); assert len(d['history'])>=1, d; assert d['history'][0]['to_phase']=='ice', d; print('PASS: history has transition event')"
```
Expected output: `PASS: history has transition event`

### Scenario 4 — Invalid entity_type returns 400
```bash
curl -s https://api.coherencycoin.com/api/entities/task/some-task/phase | \
  python3 -c "import sys,json; d=json.load(sys.stdin); assert 'Unknown entity_type' in d['detail'], d; print('PASS: 400 for invalid type')"
```
Expected output: `PASS: 400 for invalid type`

### Scenario 5 — CLI shows phase and breath step
```bash
coh phase idea agent-pipeline
# Expected output contains:
# phase: ice
# breath: rest
```

### Scenario 6 — How do we know it's working?

The system is working when:
1. Every new idea created via `POST /api/ideas` has `phase_state = water` and `breath_cycle_phase = rest` visible in `GET /api/entities/idea/{id}/phase`.
2. The `phase_transition_events` table grows — each PATCH appends a row, never mutates prior rows.
3. The web renders a phase icon on every IdeaCard — verify by inspecting the `/ideas` page and confirming each card shows exactly one of ❄/〜/☁.
4. The BreathCycleViz on the idea detail page highlights the correct segment — verify by transitioning an idea to `inhale` and refreshing the page.
5. Over time: the distribution of `phase_state` across ideas provides a live health signal — a healthy portfolio shows a mix of `water` (active work) and `ice` (crystallized delivery), with `gas` only for genuinely exploratory items. A portfolio of all `water` with no `ice` means nothing is completing; all `ice` means nothing new is being attempted.

Proof dashboard query:
```bash
curl -s https://api.coherencycoin.com/api/entities/idea/phase-distribution
# Should return: {"ice": N, "water": M, "gas": K, "total": N+M+K}
```
This endpoint makes the lifecycle health observable at a glance.

## Out of Scope

- Phase transitions for specs, tasks, or contributions (v1 scope: ideas + concepts only)
- Automated phase transitions based on pipeline events or coherence scores (future: phase auto-advance spec)
- Phase-based access control (ice entities remain readable and patchable)
- Notifications on phase transitions
- Webhook events on phase change
- The `/api/entities/idea/phase-distribution` aggregate endpoint (listed in Scenario 6 as a future proof endpoint — not required for this spec to be done)

## Risks and Assumptions

- **Migration safety**: The `phase_state` and `breath_cycle_phase` columns use `server_default` so existing rows are backfilled on first read. The migration must handle both SQLite (TEXT column) and PostgreSQL (VARCHAR). Validate with `scripts/agent_status.py --diff` before shipping.
- **IdeaCard shape**: Assumes `IdeaCard` receives an idea object with a `phase_state` field. If the ideas API response does not yet include `phase_state`, the ideas router `GET /api/ideas` must also be updated to include it — check the `IdeaWithScore` model in `api/app/models/idea.py`.
- **Concept table**: Assumes `concepts` table exists with a string `id` column. Verify via `api/app/services/concept_service.py` before writing migration.
- **Append-only events**: `phase_transition_events` is designed for auditability. If volume grows large, an index on `(entity_type, entity_id, transitioned_at)` should be added in the migration.
