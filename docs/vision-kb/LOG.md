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

## [2026-04-14] deepening | lc-health rewritten with comprehensive practical depth

- Rewrote lc-health.md from ~82 lines to ~450+ lines of deeply practical content
- Added "Community Health Model" — the five threads of daily health (movement, food, water, connection, purpose) and why community structure IS the health system
- Added "The Herbal Medicine Garden" — 20 essential medicinal plants organized by use (immune, digestive, first aid, women's health/sleep/nervous system), climate adaptations for temperate/arid/tropical, and complete apothecary how-to (tinctures, infused oils, salves, teas, fire cider) with preparation instructions
- Added "Water and Sanitation" — drinking water testing and treatment for wells/springs/rainwater, composting toilets (three designs: Clivus Multrum, twin-vault batch, bucket system with urine diversion), greywater systems (branched drain and constructed wetland with sizing calculations and costs)
- Added "Mental Health and Belonging" — co-regulation, witness, purpose, rhythm as natural mental health infrastructure. Conflict resolution via talking circle. Role of ceremony. When to seek outside help (Mental Health First Aid training, crisis protocols, maintaining practitioner relationships)
- Added "First Aid and Emergency" — WFR training ($700-1K per person), complete medical kit inventory, 6-step emergency protocol, hospital relationship building, evacuation planning
- Added "Movement and Body" — work-as-exercise design principles, community layout as fitness program, dedicated practices (yoga, tai chi, contact improv, swimming, walking, dance), spaces designed for movement
- Added "Sauna, Sweat Lodge, Cold Plunge" — complete wood-fired sauna build guide (dimensions, stove, ventilation, benches, floor, cost breakdown $2K-$4.5K), cold plunge options, peer-reviewed health benefits with citations, ritual description
- Added "What You Need From Outside" — honest accounting of what requires professional care (dental, surgery, diagnostics, chronic disease, psychiatric medication, vision/hearing), maintaining insurance and access, telehealth, local practitioner relationships, community health fund budgeting ($500-1,500/person/year)
- Added "Aging and Elder Care" — purpose shifts, multi-generational contact, movement maintenance through community design, cognitive engagement, when professional care is needed, end-of-life in community
- Added "At Scale" sections for 50/100/200 people with specific infrastructure counts and budget figures
- Added "Climate Adaptations" for temperate, arid, and tropical with zone-specific risks and adaptations
- Expanded resources from 6 to 14 entries (added Humanure Handbook, NOLS WFR, Oasis Design greywater, Mental Health First Aid, Sauna Times, Blue Zones, Wim Hof science, Rosemary Gladstar herbal guide)
- Expanded open questions from 5 to 10
- Expanded cross-references from 4 to 10 connected concepts
- Updated INDEX.md status to deepening

## [2026-04-14] deepening | lc-land rewritten with comprehensive practical depth

- Rewrote lc-land.md from ~85 lines to ~450+ lines of substantive content
- Added "How to Start" — forming core group, scouting land, detailed checklist of non-negotiables: water, soil, aspect/slope, road access, existing infrastructure, zoning, neighbors, history. Land-to-people ratios.
- Added "Custodianship Models" — CLT (detailed mechanics of 99-year ground lease, tripartite board, 300+ operating in US), housing cooperative, conservation easement (30-60% value reduction, tax benefits), sovereign land models, layered approach advice
- Added "Climate-Specific Guidance" with four zones:
  - Temperate (Europe, NE USA, NZ): food forests, cob/straw bale, seasonal rhythms, hoop houses, rocket mass heaters
  - Tropical (Costa Rica, Bali, Thailand): bamboo, syntropic agroforestry, cross-ventilation, year-round production
  - Arid (SW USA, Spain, Australia): earthships, water harvesting, desert permaculture, solar sizing
  - Mediterranean (Portugal, Greece, S France): drought-adapted systems, fire management, water retention landscapes
- Added "First Year Timeline" — month-by-month guidance: mapping/testing (M1-3), shelter/water (M4-6), earthworks/plantings (M7-9), infrastructure/rhythms (M10-12)
- Added "Technology and Infrastructure" — energy sizing for 50 people (solar 50kW array, battery 750kWh, micro-hydro, wind, biogas), water systems (catchment calculations, greywater wetlands, composting toilets, spring management), communications
- Added "Exchange and Sovereignty" — what to produce locally vs trade for, income streams (workshops $20-80K/yr, visitors $30-100K/yr, farm surplus, remote work), inter-community exchange networks
- Added "Costs and Funding" — land costs by region (8 regions with per-acre ranges), total project cost table for 50 people ($580K-$3.97M), funding models (community shares, sweat equity, grants, social enterprise, crowdfunding)
- Added "Legal Pathways" — country-specific guidance for US, Portugal, Costa Rica, UK/Ireland, NZ, SE Asia. Zoning strategies: ag zoning, PUD, conservation subdivision, incremental development, rural exemptions
- Expanded Where You Can See It with Auroville example and quantified details for Tamera and Gaviotas
- Added 4 new inline visuals (scouting group, desert community, autumn food forest, campfire planning)
- Expanded resources from 7 to 15 entries
- Added 3 new open questions, expanded cross-references
- Updated INDEX.md status from expanding to deepening

## [2026-04-14] deepening | lc-energy rewritten with comprehensive practical depth

- Rewrote lc-energy.md from ~82 lines to ~400+ lines of substantive content
- Added 9 major new sections: Energy Budget for 50 People, Solar (sizing/costs/DIY), Wind (when/sizing/Piggott designs), Biogas (digesters/output/build), Heating & Cooling (rocket mass heaters/passive solar/earth-sheltered), Water Heating (solar thermal/batch heaters/heat recovery), Sovereignty vs Exchange, First Year Energy Plan, Climate Adaptations
- Energy budget: 50-100 kWh/day for 50 people (vs 1,500 kWh/day American equivalent)
- Solar: peak sun hours to panel count to inverter to battery bank with costs ($6k-10k panels, $12k-20k inverters, $40k-60k LiFePO4)
- Wind: complementary pattern, Hugh Piggott hand-built designs ($2k-4k materials)
- Biogas: IBC tote digester ($300-600), underground for cold climates ($2k-5k), fixed-dome ($3k-8k)
- Heating: rocket mass heaters ($200-800), passive solar (R-40 walls, R-60 roof), earth-sheltered, earth tube cooling
- Water heating: evacuated tube collectors ($4k-8k for 50 people), stratified tank, drain-water heat recovery
- First Year Plan: phased 5-year timeline, $65k-150k total ($1,300-3,000/person)
- Climate adaptations: 4 zones (heating-dominated, cooling-dominated, balanced, arid)
- Scale notes: 50/100/200 people with cost ranges
- Added 6 new resources, 5 new questions, Earthaven + Findhorn examples
- Updated INDEX.md status to deepening

## [2026-04-14] deepening | lc-nourishment rewritten with full practical depth

- Rewrote lc-nourishment.md from ~80 lines to ~500+ lines with 8 new/expanded sections
- Added "How to Feed 50 People": caloric math, protein sources, acreage breakdown
- Added "The Food Forest": 7-layer design, pioneer species, year-by-year timeline (0-7), species by 4 climate zones
- Added "Kitchen & Preservation": community kitchen layout, fermentation targets, drying, canning, root cellar specs
- Added "Animals in the System": chickens (50 hens), goats (6-12 dairy), bees (3-6 hives), ethical integration, scale recommendations
- Added "Water for Growing": irrigation math, rainwater harvesting from roofs, swale construction, pond specs, drip systems
- Added "What You Can't Grow": coffee, salt, oil, grains, spices — honest gaps + exchange network strategies
- Added "First Year Food Plan": month-by-month planting/harvest/preservation calendar, quick wins vs long game timeline
- Added "Costs": detailed first-year budget ($17k-40k total, $340-795/person) broken into seeds, infrastructure, tools, animals, bridge food
- Expanded resources from 8 to 14, added fermentation, canning, market gardening, plant database references
- Updated INDEX.md status: expanding → deepening
- Cross-references expanded to include lc-v-food-practice, lc-energy, lc-circulation

## [2026-04-14] deepening | lc-space rewritten with deep practical building guidance

- Rewrote lc-space.md from ~80 lines to ~350+ lines of substantive content
- Added "What to Build First" — phased priority: temp shelters (week 1) → Hearth (month 1-3) → Clearing (month 2-4) → Sanctuary (month 3-6) → Den (month 4-12) → Nests (month 6-24)
- Added "Building Methods by Climate" — full comparison table: cob, straw bale, rammed earth, earthbag, bamboo, timber frame, CEB, earthship with cost/sqft, DIY-ability, thermal performance
- Climate guidance for cold continental, temperate maritime, arid, tropical, and mixed climates
- Added "The Hearth" — community kitchen design for 50: cooking core, prep space, long table, open wall, storage. Materials cost $8K-25K
- Added "The Clearing" — gathering space design: fire pit, bench ring, acoustic design. $500-3K, 2-5 days to build
- Added "The Nest" — private dwellings: 15-25 sqm, cluster design, shared walls, privacy gradients, rocket mass heaters. $2K-8K each
- Added "The Sanctuary" — stillness space: 45-60cm thick walls, round skylight, curved entry passage. $3K-8K, doubles as training project
- Added "Infrastructure Layout" — full site planning: water flow, sun path, wind, concentric rings (core → nesting → growing → wild edge), paths, vehicles, water, power
- Added "Costs & Timeline" — 4-phase build plan with itemized costs: $50K lean / $100K moderate / $200K comfortable for 50 people over 24 months
- Expanded "Open-Source Plans" — organized into complete village plans, method-specific guides, community design references, and living examples with 15+ resources
- Added 4 new inline visuals (construction scene, clearing gathering, nest cluster, sanctuary interior)
- Updated cross-references to include lc-energy, lc-nourishment, lc-instruments
- Updated INDEX.md status to deepening

## [2026-04-14] deepening | lc-network rewritten with practical depth

- Rewrote lc-network.md from ~120 lines to ~280 lines of substantive content
- Added 9 new sections: Why Network, What Gets Exchanged, Exchange Models That Work, Sovereignty and Interdependence, Starting a Network, Inter-Community Coordination, Technology for Connection, Digital Infrastructure (tech stack table), First Steps
- Practical exchange models: gift economy, surplus sharing pools, skill exchange, knowledge commons — with honest assessment of what does not work (barter ledgers, centralized distribution, obligatory quotas)
- Real community examples: Gaviotas (Colombia), Auroville (India), GEN, CASA, Transition Towns with specific lessons
- Technology stack: LoRa mesh ($30-50/node), OpenWrt mesh WiFi, Raspberry Pi servers, Matrix messaging, Wiki.js, Jitsi — all open-source, community-owned
- Sovereignty/interdependence framework: 80% local / 20% network, with specific lists of what falls in each category
- Six concrete first steps someone can take today
- Expanded resources from 3 to 13 entries (GEN, CASA, Meshtastic, Matrix, Wiki.js, OpenWrt, WWOOF, Practical Farmers of Iowa, etc.)
- Expanded open questions from 4 to 8
- Expanded cross-references from 3 to 7 connected concepts
- **Frequency check**: no bylaws, no voting, no applications, no corporate structures — resonance-based coordination throughout

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
