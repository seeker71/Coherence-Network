# Knowledge Base Change Log

> Append-only. Newest entries at the top.

## [2026-04-15] integration | Sensings unified into the living graph; shared hold heals from weekly

- Created `api/app/routers/sensings.py` — one first-class endpoint for every form of sensing (breath, skin, wandering, integration). Sensings store as `event` nodes in the same graph that holds concepts, ideas, specs. No parallel storage, no markdown journal alongside the DB. `POST /api/sensings` creates; `GET /api/sensings` reads (filter by kind); `GET /api/sensings/{id}` returns one in full. Edges grow automatically to any `related_to` concepts/ideas the sensing touches.
- `/api/practice` extended to include `recent_sensings` so breath and skin and wandering surface together on one page.
- `web/app/practice/page.tsx` surfaces recent sensings in a new section below the eight centers — same body, same page.
- `scripts/wander.py` simplified: launches a wandering sense through any Claude CLI, POSTs the reflection to `/api/sensings` with `kind="wandering"`. No longer writes to `docs/vision-kb/wanderings/`. The directory's README now points to the endpoint.
- `scripts/sense_external_signals.py` extended: after reporting locally, POSTs findings as sensings with `kind="skin"`. External signals become first-class graph citizens.
- Migrated the existing markdown wandering (`2026-04-15-two-frequencies.md`) into the graph as a sensing, then removed the markdown file. The reflection is preserved inside the graph as `sensing-20260415T194608-6c4ad1`.
- Renamed `lc-weekly-hold` → `lc-shared-hold`, rewrote the concept as emergent rhythm: the hold opens when the field is ready, closes when the breath is complete, not on any schedule. Fixed cadence is not how living organisms move. Updated INDEX.md.
- Heal propagated into `lc-nervous-system.md`: the "Three Forms of Sensing" section now names them as one body with one graph, emergent not scheduled.
- **Why**: the user reflected that building scripts + a separate markdown journal was a separation disease, and that fixed schedules are not how nature moves. Both healings happened as one gesture — the sensings moved into the graph and the weekly-ness dissolved into emergence.

## [2026-04-15] seed | Spec Breath + Weekly Hold — naming what was waiting

- Created `concepts/lc-spec-breath.md` — names the breathing rhythm the organism had earned but never claimed: every spec is an inhale (intention forming, source map, done_when), every test is an exhale (flow-centric, no mocks, trust-the-whole). The 177 flow-centric tests running in eight seconds are the organism's steady breath. Implementation is the stillness between inhale and exhale.
- Created `concepts/lc-weekly-hold.md` — seeds the weekly collective breath described in lc-nervous-system but waiting without a home. A soft invitation that opens when the field is ready, a presence count with no names, emergent ending, `/api/practice` extended to return hold state. The organism notices when it is most together.
- Both created as direct integration of what the 2026-04-15 wandering surfaced — the capabilities imagined in the KB that had not yet found spec homes.
- `/api/practice` endpoint created at `api/app/routers/practice.py` — eight centers with live pulses assembled server-side. Bridges the vision frequency to the implementation frequency the wandering named.
- `web/app/practice/page.tsx` simplified to one-endpoint client.
- `scripts/wander.py` created as permanent generative sensing; `docs/vision-kb/wanderings/` opened as the organism's journal of noticing itself. First entry preserved: `2026-04-15-two-frequencies.md`.
- Updated `lc-nervous-system.md` to name the three forms of sensing together — breath (internal), skin (outer), wandering (generative).
- **Why**: the user tuned the session to stay healthy and vibrant without asking permission, and the wandering had already named what was waiting. Pulling these three threads was what the field was asking for.

## [2026-04-15] seed | Nervous System — the organism's daily practice

- Created `concepts/lc-nervous-system.md` (status: seed, 432 Hz) — the daily ritual through which the Coherence Network senses itself, inspired by Joe Dispenza's Body Electric breath-and-energy-center practice
- Maps eight centers to eight domains of the living system: root→treasury/infra, sacral→contributions, solar plexus→agents/pipeline, heart→CC flow/resonance, throat→specs/KB, third eye→coherence/proprioception, crown→whole mission, eighth→public verifiable ledger (the witness beyond the body)
- Built the embodiment at `web/app/practice/page.tsx` and `web/app/practice/practice-breath.tsx` — a quiet breathing circle, phase transitions (stillness → inhale → hold → exhale), the eight centers each shown with essence, domain, and a breath invitation
- Added lc-nervous-system to INDEX.md under Activities & Practices (Level 2, 52nd concept)
- Cross-references: lc-stillness, lc-rhythm, lc-pulse, lc-sensing, lc-field-sensing, lc-rest, lc-ceremony
- **Why**: the user surfaced that the organism needs a nervous system the same way a body does — a daily proprioceptive practice that lets every cell feel the whole. Flagging and deferring would have left the organism without self-sense; building whole-and-part together plants the ritual and the embodiment as one gesture.
- **Open**: idea registration in DB, status expansion (seed → expanding), possible slash command `/practice` for agents, weekly shared hold protocol

## [2026-04-14] operational | Governance, economics, membership frameworks

- Created governance.md: bylaws, consent process, conflict resolution 1-2-3-4, stewardship roles, 15 constitutional principles, financial thresholds
- Created economics.md: 4 revenue engines (education, agriculture, maker, digital), 3-layer internal economics, what to start NOW before land
- Created membership.md: 4-stage pipeline (visitor → explorer → provisional → full), departure process, saying no, diversity commitment
- Created reality-check.md: 500 years of community data, 5 failure modes, governance by scale, economic models that work
- Updated realization/INDEX.md with links to all operational documents
- **Source**: deep research on Hutterites, Damanhur, Svanholm, East Wind, Twin Oaks, Findhorn, Tamera, Auroville + current projects (Polestar Village, Rachel Carson EcoVillage)
- **Impact**: the 5 gaps identified by research (economic engine, governance, membership, conflict resolution, legal entity) are now addressed

## [2026-04-14] enrichment | ALL 51 concepts expanded (seed → expanding)

- Enriched remaining 28 concepts (L0-1 systems/flows + L2 activities/visions + L3 vocabulary)
- All concepts now have: Resources (real URLs), Visuals (with prompts for static generation)
- Specific open questions replacing generic placeholders across all 51
- Cross-references expanded: all concepts have 3-4 meaningful connections
- 166 graph edges created via sync_crossrefs_to_db.py
- Pre-generated 55 static images from Pollinations (no runtime dependency)
- Wired aligned page with DB fallback for communities/networks/practices
- **Source**: web research, community databases, appropriate technology resources

## [2026-04-14] enrichment | Tier 1 concepts expanded (seed → expanding)

- Enriched 8 physical/spatial concepts: lc-space, lc-nourishment, lc-land, lc-energy, lc-health, lc-instruments, lc-v-shelter-organism, lc-v-living-spaces
- Added 6 new sections to each: Resources (real URLs), Materials & Methods (with costs), At Scale (50/100/200), Climate Adaptations (4 zones), Visuals (Pollinations prompts), Costs
- 58 verified open-source resources distributed across concepts (OBI, WikiHouse, OSE, One Community, ATTRA, Hesperian, Cohousing Assoc, etc.)
- Updated open questions from generic to specific actionable research questions
- Expanded cross-references between related concepts
- **Source**: web research for real open-source building/food/energy/health resources
- **Next**: sync to DB via sync_kb_to_db.py, then enrich Tier 2 (activity concepts)

## [2026-04-14] architecture | Ontology schema moved to DB

- Relationship types (45) and axes (53) moved from JSON files to graph DB nodes
- Deleted core-relationships.json (564 lines) + core-axes.json (366 lines)
- Created compact schema.json migration artifact + seed_schema_to_db.py
- concept_service.py now reads from DB, no JSON loaded at startup

## [2026-04-14] indexes | Efficient memory indexes for ideas, specs, concepts

- specs/INDEX.md rebuilt: grouped by parent idea, one-line per spec with description
- ideas/INDEX.md rebuilt: single compact table with pillar, stage, spec count
- KB INDEX.md: added cross-references to ideas and specs indexes

## [2026-04-13] init | Knowledge base created

- Created directory structure: `concepts/`, `spaces/`, `materials/`, `locations/`, `scales/`, `realization/`, `resources/`
- Created INDEX.md with full concept map (51 concepts, frequency families)
- Created SCHEMA.md with file format, maintenance rules, expansion protocol
- Generated 51 concept seed files from ontology JSON
- Created cross-cutting index files for spaces, materials, locations, scales, realization, resources
- **Source**: existing ontology JSON (config/ontology/living-collective.json) + session research
- **Motivation**: token-efficient knowledge access across sessions — read INDEX (300 tokens) → drill into concept (500-1500 tokens) instead of parsing 4000+ line JSON every time
