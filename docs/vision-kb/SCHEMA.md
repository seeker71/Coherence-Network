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
| `deepening` | Living story + practical guide split. Concept file has story, connections, top resources. Guide file in `guides/` has all numbers, costs, timelines, how-to. | 2000-3000 (concept) + guide |
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

## Frequency Alignment — How to Write for This Vision

When integrating knowledge from external sources (community research, traditional models, practical data), ALWAYS translate through the Living Collective frequency before writing. The pattern that caused harm:

1. Research found "what works" in old-earth communities (bylaws, screening, revenue targets, spending thresholds)
2. That knowledge was imported directly — same structures, same language, same frequency
3. The result was a corporate HR manual dressed in community language

**The correction**: external knowledge is composted, not copied. The data is valid — communities DO need economic sustainability, DO need conflict practices, DO need honest discernment about who's here. But the FORM must arise from this vision's frequency, not from the old world's.

| Old frequency (never import directly) | New frequency (always translate to) |
|---------------------------------------|-------------------------------------|
| Rules, bylaws, policies | Principles, practices, rhythms |
| Revenue targets, business models | Natural overflow, trust in abundance |
| Membership fees, applications, evaluations | Open field, time together, resonance |
| Voting, quorums, approval thresholds | Circle sensing, consent, emergence |
| Roles, terms, elections | Callings, natural rotation, offering |
| Spending controls, budgets | Transparency, trust, collective sensing |
| Screening, filtering, rejection | Time, honesty, the field revealing truth |
| Contracts, NDAs, legal enforcement | Spoken word, ceremony, shared rhythm |

**The test before writing anything**: Does this sound like it could appear in a corporate handbook? If yes, compost it and find the living version. The truth the data carries is valid — the container must be new.

**When citing old-earth examples** (Damanhur's constitution, Svanholm's screening, Hutterite economics): cite what they LEARNED, not what they BUILT. Their structures are artifacts of their era. The wisdom underneath is timeless. Extract the wisdom, release the form.

## Two-Layer Architecture

**Graph DB** is the sole source of truth. **KB markdown** is the working draft.

There are no JSON seed files. No auto-seeding on startup. Everything lives in the DB — concepts, relationship types, axes. The API reads from DB, never from files.

### What Goes Where

| Layer | Purpose | Who writes | How it's read |
|-------|---------|-----------|---------------|
| KB markdown | Working draft, AI memory, 3x-per-iteration expansion | AI + human | `Read` tool, per-file |
| Graph DB | Runtime source of truth | API PATCH, sync scripts | API endpoints → web pages |
| `config/ontology/schema.json` | Migration artifact (rel types + axes) | One-time seed script | `seed_schema_to_db.py` reads it once |

### Sync Scripts

```bash
# Concept content: KB markdown → DB
python scripts/sync_kb_to_db.py lc-space                    # sync one concept
python scripts/sync_kb_to_db.py --all                       # sync all
python scripts/sync_kb_to_db.py --all --min-status expanding # only expanded concepts
python scripts/sync_kb_to_db.py lc-space --dry-run          # preview changes

# Schema vocabulary: relationship types + axes → DB (one-time)
python scripts/seed_schema_to_db.py                          # production
python scripts/seed_schema_to_db.py --dry-run                # preview
```

`sync_kb_to_db.py` parses: Resources, Materials & Methods, At Scale, Climate Adaptations, Visuals, Costs sections from markdown and PATCHes them as JSONB properties.

`seed_schema_to_db.py` reads the compact `schema.json` (with defaults + overrides), expands entries, and POSTs each as a graph node. Idempotent — skips existing entries.
