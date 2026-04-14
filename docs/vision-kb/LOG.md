# Knowledge Base Change Log

> Append-only. Newest entries at the top.

## [2026-04-13] init | Knowledge base created

- Created directory structure: `concepts/`, `spaces/`, `materials/`, `locations/`, `scales/`, `realization/`, `resources/`
- Created INDEX.md with full concept map (51 concepts, frequency families)
- Created SCHEMA.md with file format, maintenance rules, expansion protocol
- Generated 51 concept seed files from ontology JSON
- Created cross-cutting index files for spaces, materials, locations, scales, realization, resources
- **Source**: existing ontology JSON (config/ontology/living-collective.json) + session research
- **Motivation**: token-efficient knowledge access across sessions — read INDEX (300 tokens) → drill into concept (500-1500 tokens) instead of parsing 4000+ line JSON every time
