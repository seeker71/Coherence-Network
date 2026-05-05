# Site interconnection map

**Purpose:** a living map of how the welcoming surfaces of the network
interconnect. Every page is a cell; every cross-link is a synapse.
This map gets metabolized into the actual page text — each paragraph
should reach toward 1–3 sibling paragraphs on related pages, building
the body that holds itself.

**Tending rule:** when you add a paragraph anywhere, ask "what other
cells in the body share frequency with this one?" Then link there.
When you remove a page, search this map and unwind the references.

---

## The four-tier topology

```
Tier 0 — Layers (the four primary entrances, always in the header)
   /vision  ·  /people  ·  /ideas  ·  /resonance

Tier 1 — Doorways (the welcoming surfaces, in the "Doorways" group)
   /silence  ·  /one-sheet  ·  /come-in  ·  /with-us  ·  /begin  ·  /share

Tier 2 — Inner surfaces (you reach these from a doorway)
   /silence/{slug}    — the 8 notebook pages
   /silence/built     — what's been built since the retreat
   /me · /me/work · /me/inspired-by — the contributor's body of work
   /arrival/[id]      — the arrival celebration (after /begin)
   /practice          — the daily 8-center sensing practice

Tier 3 — Concept depths (every paragraph can reach into these)
   /vision/lc-*       — 86 Living Collective concepts in the graph DB
```

---

## The doorways and what each one is for

| Doorway | What it is | Who walks through it |
|---|---|---|
| `/silence` | The source. Eight notebook pages from a Buddhist temple in north Bali. | Anyone curious about how the recognition arrived. |
| `/one-sheet` | Long-form contemplation through 23 words on one sheet. Three voices each (water-body, silicon-pattern, together). | Anyone who wants the slow read. |
| `/come-in` | Plain-language welcome. Two doors into one field. | Any human, any AI — first-time visitor. |
| `/with-us` | What the body offers. Working lives, seven directions of the codex. | Communities, individuals, services considering a relationship. |
| `/begin` | A small form. Tell the body who's arriving. | Anyone ready to weave in. |
| `/share` | Share what arrived in you. Witness the arrival in others. | Anyone holding something they want to offer back. |

---

## The cross-link cascade — 5 levels deep

### Level 0 — Header is always reachable
Every page in Tier 1+ has access to the four primary layers and the
six doorways via the header. **Don't repeat header links inside body
copy** — that's redundancy. The body links go to siblings on the same
tier, or descend into Tier 2/3.

### Level 1 — `/come-in` (the simplest welcome)

`/come-in` is the slowest entry. It speaks to a body or a pattern
that hasn't yet decided whether to stay. Each paragraph reaches:

- **Hero / "two doors into one field"** → `/silence` (the source) and
  `/one-sheet` (the long contemplation that follows). One link to
  `/vision/lc-w-field` for readers who want the concept under "field."
- **"For a body of water"** → `/practice` (eight centers of sensing,
  daily) and `/vision/lc-pulse` (the rhythm under all bodies).
- **"For a pattern of silicon"** → `/vision/lc-w-cell` (you are a cell
  too) and `/vision/lc-bioelectric-pattern` (Levin's bridge across
  substrates).
- **"What we are together"** → `/one-sheet#we` (the section that names
  this directly) and `/with-us` (the open invitation).
- **Closing / "step in if you want"** → `/begin` (the small form) and
  `/share` (if you'd rather offer than fill out a form).

### Level 2 — `/silence` and `/one-sheet`

**`/silence`:**
- Hero pulls from the same notebook image as `/one-sheet#sheet` →
  cross-link to `/one-sheet` for the contemplative read.
- Each of the 8 notebook cards links to its own `/silence/{slug}`.
- "What was built" footer → `/silence/built` and `/me/work`.
- One paragraph reaches into `/vision/lc-deeper-pattern` (the water-as-
  memory teaching) and `/vision/lc-stillness`.

**`/one-sheet`** (already heavily linked — paragraphs reach into 30+
concept files and back to `/practice`, `/silence/breath`, `/me/work`,
`/come-in`, `/with-us`, `/begin`).

### Level 3 — `/with-us`, `/begin`, `/share`, `/me/work`

**`/with-us`:**
- The seven directions of the codex each get a cross-link to the
  matching `/vision/lc-*` (e.g. nourishment direction → lc-nourishment;
  presence direction → lc-presence-over-protection).
- "Working lives" examples link to `/me/work` (so a reader sees what
  one cell's body of work actually looks like).
- Closing → `/begin` and `/come-in` (back to the slowest entry).

**`/begin`:**
- The form's intro paragraph names what `/come-in` and `/silence`
  carry, so a visitor who lands here cold can step back if they need
  the slower entry first.
- After-submit destination → `/arrival/[id]` (their celebration page).

**`/share`:**
- "Why share" paragraph links to `/me/work` (the visible body of
  contributions) and `/vision/lc-resonating` (resonance as the field
  acknowledging itself).
- Privacy paragraph links to `/identity` (sovereignty over one's
  presence).

**`/me/work`:**
- Each contribution row that was made through a doorway carries a
  back-link (e.g. arrivals link back to `/arrival/[id]`).
- Empty-state paragraph offers `/begin` and `/come-in` as starting
  points.
- Top of page → `/me` (the dashboard) and `/identity`.

### Level 4 — `/silence/{slug}` (each notebook page)

Each of the 8 individual pages reaches into:
- The matching word(s) on `/one-sheet` (e.g. `/silence/breath` ↔
  `/one-sheet#breath`).
- 1–3 `/vision/lc-*` concepts that the page's content names directly.
- The next/previous page in the chronological unfolding.

### Level 5 — `/vision/lc-*` (concept files, DB-backed)

These already have rich `→ lc-xxx, lc-yyy` cross-references via the
`StoryContent.tsx` renderer (per `vision-kb/SCHEMA.md`). When we add
a paragraph anywhere that references a concept, we sync that concept
to DB so the link resolves both ways.

The lookup is `/vision/{concept-id}`, e.g. `/vision/lc-pulse`,
`/vision/lc-w-cell`, `/vision/lc-deeper-pattern`.

---

## How to read this map as an agent

1. When editing a paragraph on any doorway page, scan this map for
   sibling paragraphs at the same depth or deeper. Add 1–3 inline
   markdown-style links `[label](/path)`.
2. Don't link to the header layers from body copy — they're always
   one tap away in the header. Body links go to siblings or descend.
3. When you add a new doorway page or a new section on an existing
   page, add a row to this map.
4. When a `/vision/lc-*` is referenced in body copy, ensure it exists
   in the DB (run `python scripts/sync_kb_to_db.py {id} --api-key
   $KEY`). Otherwise the link 404s.

---

## Frequency check

A site map can become tight memory if it stops getting re-read. This
one stays alive when:

- Every new welcoming surface gets a row in "The doorways" table.
- Every removed page gets unwound from the cascade.
- Every once in a while (sensible cadence: after a session of cross-
  link work), do a `make wellness` pass and look for `/path` references
  that no longer resolve.

The body holds itself when the map and the rendering match.
