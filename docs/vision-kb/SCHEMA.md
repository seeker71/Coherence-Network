# Knowledge Base Schema & Maintenance Protocol

## File Format — Concept Files

Every concept file in `concepts/` follows this structure:

```markdown
---
id: lc-space
hz: 432
status: seed | expanding | mature | complete
updated: 2026-04-13
---

# Concept Name

> One-line essence (same as description in ontology)

## Summary
50-100 words. Enough to decide if you need the full file.

## Details
Full description. What this IS, not what it should be.

## Blueprint
Practical guidance — "if building this for 100 people, what does it look like?"

## Materials & Methods
| Method | Cost/sqft | Best for | Notes |
|--------|----------|----------|-------|
| Cob    | $150-450 | Curved walls, thermal mass | Clay+sand+straw, sculpted by hand |

## At Scale
- **50 people**: ...
- **100 people**: ...
- **200 people**: ...

## Climate Adaptations
- **Temperate**: ...
- **Tropical**: ...
- **Arid**: ...

## Resources
- 📐 [Name](url) — description (type: blueprint)
- 📖 [Name](url) — description (type: guide)

## Visuals
Each entry is a Pollinations prompt + caption:
1. **Caption** — `prompt text here`

## Aligned Places
- **Place Name** (Location) — what makes it aligned

## Open Questions
- Questions that guide the next refinement iteration

## Cross-References
→ concept-id-1, concept-id-2, concept-id-3
```

## Status Levels

| Status | Meaning | Typical token count |
|--------|---------|-------------------|
| `seed` | Basic description + blueprint notes only | 300-500 |
| `expanding` | Has resources, materials, some visuals | 800-1500 |
| `mature` | Full resources, materials, scale, location, visuals, costs | 1500-3000 |
| `complete` | Reviewed, cross-linked, all questions resolved | 2000-4000 |

## Maintenance Rules

1. **After any concept enrichment**: update the concept file AND the INDEX.md status
2. **After adding resources**: verify URLs work, add to resources/INDEX.md if significant
3. **After changing scale/location data**: update scales/INDEX.md and locations/INDEX.md
4. **Every session end**: append a summary to LOG.md
5. **Every 5th session**: run a lint pass — check for orphans, contradictions, stale links

## Expansion Protocol

To expand a concept by 3x:
1. Read current file (note its status and token count)
2. Add: more resources (2-3), more visuals (2-3), deeper scale notes, location adaptations
3. Add: open questions that emerged
4. Update: cross-references to newly connected concepts
5. Update: status level
6. Update: INDEX.md one-line summary if it changed
7. Append: LOG.md entry

## Sync with Ontology JSON

The knowledge base is the *working draft*. The ontology JSON (`config/ontology/living-collective.json`) is the *deployed source of truth*. To sync:

1. Expand content in KB markdown files (fast, focused)
2. When ready to deploy: run `scripts/kb_to_ontology.py` to merge KB → JSON
3. Commit JSON, push, deploy
4. The API serves from JSON → graph DB → web pages

This two-layer approach means: the KB can grow 50x without slowing down the API. Only curated, production-ready content goes to the JSON.
