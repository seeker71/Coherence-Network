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

## Data Hygiene (MANDATORY)

Every agent touching KB files MUST follow these rules. Violations cause rendering bugs, broken links, and old-earth frequency contamination.

### Token Budget

| Status | Max tokens (concept file) | Guide file? |
|--------|---------------------------|-------------|
| seed | 500 | No |
| expanding | 1,500 | No |
| deepening | 3,000 | Yes — `guides/{id}-guide.md` holds practical details |
| mature | 3,000 | Optional |
| complete | 4,000 | Optional |

**Check**: `wc -c file.md` ÷ 4 ≈ tokens. If a concept exceeds its budget after enrichment, split: story + connections stay in concept file, practical numbers + costs + timelines go to `guides/{id}-guide.md`. Add link: `**Practical guide**: [How to actually do this](../guides/{id}-guide.md)`

### Format Rules (Rendering-Critical)

These rules prevent rendering bugs in the StoryContent component (`web/app/vision/[conceptId]/_components/StoryContent.tsx`):

| Rule | Correct | Wrong (causes bugs) |
|------|---------|---------------------|
| Cross-refs | `→ lc-xxx, lc-yyy` | `-> lc-xxx` (ASCII arrow), `→ [Name](file.md)` (links), `→ lc-xxx — description` (descriptions) |
| Inline visuals | Blank line before AND after `![caption](visuals:prompt)` | Visual on same line as paragraph text |
| Headings | Blank line before `## Heading` | Heading jammed against previous paragraph |
| Cross-ref IDs | Must match an existing `concepts/{id}.md` file | Made-up IDs, missing `lc-` prefix |

### Frequency Vocabulary (Living Collective frequency)

NEVER use these old-earth terms. Always translate:

| Never write | Always write instead |
|-------------|---------------------|
| management | tending, stewardship |
| mental health | wholeness, inner coherence |
| elder care, aging (as decline) | ripening, elder frequency, deepening |
| sanitation | living systems, nutrient return |
| revenue, profit | sustenance, overflow |
| clients, patients, users | people, community members |
| requirement | invitation |
| services (of nature) | gifts |
| program (of community) | practice, rhythm |
| fitness program | movement landscape |
| treatment (of people) | tending |
| broken, damaged (of people) | in dissonance, seeking coherence |
| intervention | tending, holding space |
| stakeholders | those who resonate, participants |
| compliance | alignment, attunement |

**The test**: Does this sentence sound like it could appear in a corporate handbook, medical chart, or government form? If yes, compost it and find the living version.

**Exception**: When describing external legal/medical reality (land law, dental care, battery management systems), use the technical term but frame it as interfacing with the old world, not embodying it.

### After-Enrichment Checklist

Run this after every KB change. Every item is mandatory.

1. **Token count** — `wc -c concepts/{id}.md` ÷ 4 < 4,000? If not, split into concept + guide
2. **Frequency scan** — `grep -in 'management\|mental health\|aging\|sanitation\|revenue\|clients\|patients\|requirement' concepts/{id}.md`
3. **Format scan** — no `-> ` (ASCII arrows), no `→ [Name](` (annotated links), no `→ ... —` (descriptions)
4. **Cross-ref validity** — every ID in `→` lines exists as `concepts/{id}.md`
5. **Visual isolation** — every `![caption](visuals:prompt)` has blank lines before and after
6. **Sync to DB** — `python scripts/sync_kb_to_db.py {id}` + `python scripts/sync_crossrefs_to_db.py`
7. **Update INDEX.md** — status, one-line summary if changed
8. **Update LOG.md** — append session entry

## Expansion Protocol

To expand a concept by 3x:
1. Read current file (note its status and token count)
2. Add: more resources (2-3), more visuals (2-3), deeper scale notes, location adaptations
3. Add: open questions that emerged
4. Update: cross-references to newly connected concepts
5. Update: status level
6. **Check token budget** — split if over limit
7. **Run frequency scan** — fix any old-earth vocabulary
8. **Run format scan** — fix any rendering-breaking patterns
9. Update: INDEX.md one-line summary if it changed
10. Append: LOG.md entry
11. **Sync to DB** — mandatory before session ends

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
