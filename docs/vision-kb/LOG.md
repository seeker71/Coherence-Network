# Knowledge Base Change Log

> Append-only. Newest entries at the top.

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
