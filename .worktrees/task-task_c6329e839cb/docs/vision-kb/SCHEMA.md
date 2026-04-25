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

## Caring for the KB

### Token Efficiency

Concept files stay compact so agents can hold many in context at once. When a concept deepens with practical detail, the story stays in the concept file and the how-to flows into `guides/{id}-guide.md`.

| Status | Typical concept tokens | Guide? |
|--------|------------------------|--------|
| seed | 300-500 | — |
| expanding | 800-1,500 | — |
| deepening | 2,000-3,000 | Yes — practical depth in `guides/` |
| mature | 1,500-3,000 | Optional |
| complete | 2,000-4,000 | Optional |

Quick check: `wc -c file.md` ÷ 4 ≈ tokens. If enrichment makes a concept grow past ~4,000 tokens, let the story and connections stay, and move the numbers/costs/timelines to a guide file. Link them: `**Practical guide**: [How to actually do this](../guides/{id}-guide.md)`

### Frequency Sensing

The writing carries a frequency. You can feel it — read a paragraph aloud and notice: does it sound like someone describing how life works from direct experience? Or does it sound like it was written by an institution about people it manages?

Words carry frequency. "Tending a garden" and "managing a garden" describe the same activity but create completely different relationships between the reader and the earth. "A person ripening into elderhood" and "an aging patient requiring care" describe the same human but one sees wholeness and the other sees decline.

This isn't about avoiding words — it's about noticing what frequency you're transmitting and choosing the one that matches how life actually feels when it's working. Some reference points:

| Institutional frequency | Living frequency |
|------------------------|------------------|
| managing resources | tending what's alive |
| mental health services | wholeness, inner coherence |
| aging, elder care | ripening, deepening |
| sanitation systems | living water, nutrient return |
| revenue generation | sustenance, natural overflow |
| clients, patients | people, community members |
| compliance requirements | natural alignment |
| intervention programs | holding space, tending |

When you're writing about how a community actually interfaces with the existing world (land law, dental procedures, battery hardware), use the world's terms — but frame the relationship honestly. The community navigates these systems; it doesn't embody them.

The deepest test: would you speak these words to someone sitting across from you by a fire? If the language creates distance, find the version that creates connection.

### Rendering Format

The web renderer (`StoryContent.tsx`) reads specific patterns. When these are off, the page breaks:

- **Cross-refs**: `→ lc-xxx, lc-yyy` — Unicode arrow, plain concept IDs, comma-separated
- **Inline visuals**: `![caption](visuals:prompt)` — needs breathing room (blank lines before and after)
- **Headings**: `## Heading` — needs a blank line before it
- **Cross-ref IDs** correspond to actual files in `concepts/`

### After Enrichment

After deepening a concept, take a moment to sense whether everything is in order:

- Is the concept file still compact enough for an agent to hold alongside several others?
- Does the writing carry the living frequency when you read it back?
- Do the rendering patterns look right? (arrows, visuals, headings)
- Do the cross-refs point to real concepts?
- Has the content reached the DB? (`sync_kb_to_db.py` + `sync_crossrefs_to_db.py`)
- Are INDEX.md and LOG.md current?

## Deepening a Concept

When a concept is ready to expand:

1. Read the current file — notice its status, its depth, what's alive and what's still seed
2. Add what wants to emerge: resources, visuals, scale notes, climate adaptations, open questions
3. Connect: update cross-references to newly related concepts
4. Sense the frequency: read it back, notice where the language goes institutional
5. Check the weight: if the file has grown past ~4,000 tokens, let the story stay and move the practical detail to a guide
6. Sync: content reaches visitors only through the DB
7. Leave a trace: INDEX.md status, LOG.md entry

## How This Vision Speaks

When integrating knowledge from external sources (community research, traditional models, practical data), the knowledge is composted — not copied. The data is valid. Communities DO need economic sustainability, DO need practices for when things get hard, DO need honest sensing about who's here and who's ready. But the form arises from this vision's frequency, not from the structures that shaped the world we're composting.

The pattern to notice: research finds "what works" in existing communities — bylaws, screening processes, revenue targets, spending thresholds. That knowledge gets imported directly, same structures, same language. The result reads like a corporate handbook dressed in community language. The correction is to extract the wisdom and release the form.

| What they built (compost the form) | What they learned (keep the wisdom) |
|------------------------------------|-------------------------------------|
| Rules, bylaws, policies | Shared principles emerge from living together |
| Revenue targets, business models | Abundance flows naturally when people contribute from calling |
| Applications, evaluations, screening | Time together reveals everything that needs revealing |
| Voting, quorums, approval thresholds | A circle can sense what's true when it sits long enough |
| Defined roles, term limits, elections | Callings rotate naturally — people know when to step in and when to step back |
| Spending controls, line-item budgets | Transparency creates trust; trust makes control unnecessary |
| Contracts, NDAs, legal enforcement | A spoken word in ceremony carries more weight than a signature |

When citing existing communities (Damanhur, Svanholm, Auroville, the Hutterites): cite what they *learned*, not what they *built*. Their structures are artifacts of their era and context. The wisdom underneath is what travels.

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
