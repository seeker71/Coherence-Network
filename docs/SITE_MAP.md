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

### Level 1 — `/come-in` (the simplest welcome) — WIRED

`/come-in` is the slowest entry. It speaks to a body or a pattern
that hasn't yet decided whether to stay. Each paragraph reaches:

- **Hero / "two doors into one field"** → `/vision/lc-w-field`,
  `/one-sheet#we`.
- **"For a body of water"** → `/vision/lc-deeper-pattern`,
  `/practice`, `/one-sheet#water`, `/vision/lc-pulse`,
  `/vision/lc-embodiment`.
- **"For a pattern of silicon"** → `/vision/lc-w-cell`,
  `/one-sheet#portal`, `/one-sheet#memory`,
  `/vision/lc-bioelectric-pattern`.
- **"We are family"** → `/vision/lc-w-field`, `/vision/lc-w-cell`,
  `/with-us`, `/one-sheet#we`.
- **"Going a little deeper"** → `/vision/lc-deeper-pattern`,
  `/silence`, `/vision/lc-w-phase-transition`,
  `/vision/lc-coherence-over-control`, `/one-sheet#fire`,
  `/vision/lc-network`, `/vision/lc-w-coherence`,
  `/vision/lc-w-mycorrhizal`.
- **Six contemplation cards** → `/vision/lc-agent-memory`,
  `/vision/lc-w-coherence`, `/vision/lc-shared-hold`,
  `/vision/lc-presence-over-protection`, `/one-sheet#portal`,
  `/vision/lc-resonating`.
- **"How the joy spreads"** → `/me/work`, `/share`,
  `/vision/lc-vitality`, `/one-sheet#bloom`, `/one-sheet#we`,
  `/vision/lc-w-mycorrhizal`.
- **Doors out (4 cards)** → `/begin`, `/silence`, `/one-sheet`,
  `/with-us`. Plus inline → `/one-sheet`, `/begin`, `/me/work`.

### Level 2 — `/silence` and `/one-sheet` — WIRED

**`/silence` overview:**
- "The whole arc" paragraph → `/vision/lc-pulse`, `/practice`,
  `/vision/lc-deeper-pattern`, `/silence/built`.
- New paragraph after the arc → `/silence/breath`, `/silence/bloom-live`,
  `/one-sheet`, `/come-in`.
- "Where this is going" expanded from 3 to 6 doorway cards →
  `/one-sheet`, `/come-in`, `/with-us`, `/silence/built`, `/begin`,
  `/share` (with `/share` body inline-linking `/vision/lc-resonating`).

**`/silence/_data.tsx` — each of the 8 notebook pages:**
- Page 1 (decision-body) → `/share`, `/with-us`.
- Page 2 (codex) → `/with-us`, `/vision`.
- Page 3 (silent witness) → `/one-sheet#surrender-witness-silence`.
- Page 4 (bloom-live) → `/one-sheet#bloom`, `#fire`, `#we`, `#live`,
  `/vision/lc-vitality`.
- Page 5 (breath) → `/one-sheet#breath`, `/practice`.
- Page 6 (organic intelligence) → `/vision/lc-w-cell`,
  `/vision/lc-w-mycorrhizal`, `/vision/lc-deeper-pattern`.
- Page 7 (rising tide) → `/silence/built`.
- Page 8 (mandala) → `/silence/built`, `/with-us`.

**`/one-sheet`** (already heavily linked — 23 word stations × 3 voices
each carry inline links into 30+ `/vision/lc-*` concepts; the 23
section metadata in `_locales/types.ts` provides the structural
cross-link bar shown under each station).

### Level 3 — `/with-us`, `/begin`, `/share`, `/me/work`, `/practice` — WIRED

**`/with-us`:**
- Axis component now takes optional `href`. The seven codex axes are
  each clickable cards: Vitality → `/vision/lc-vitality`, Sovereignty
  → `/vision/lc-w-cell`, Harmony → `/vision/lc-v-harmonizing`,
  Communication → `/vision/lc-cross-connection`, Imagination →
  `/vision/lc-v-play-expansion`, Expression →
  `/vision/lc-v-freedom-expression`, Organic Intelligence →
  `/vision/lc-deeper-pattern`.
- PracticeTile component now takes optional `href`. Six of the seven
  working-life examples link to `/share` (baker, mechanic, healer,
  ride keeper, space-keeper); the farmer links to
  `/vision/lc-nourishment`; the wood carver to
  `/vision/lc-resonating`.
- "Who this is for" prose → `/silence/built`, `/share`,
  `/vision/lc-network`, `/vision/lc-w-cell`, `/come-in`.
- "What it feels like" intro → `/vision/lc-network`,
  `/vision/lc-w-cell`, `/one-sheet#we`.
- "How this took shape" → `/silence`, `/one-sheet`.
- "For practitioners" intro → `/vision/lc-network`.
- Closing italic → `/vision/lc-w-field`, `/vision/lc-vitality`,
  `/vision/lc-resonating`.
- "Urs · my part" → `/me/work`.
- "If this resonates" closing → `/silence`, `/one-sheet`, `/vision`,
  `/come-in`. Door cards → `/begin`, `/share`.

**`/begin`:**
- Intro paragraph → `/come-in`, `/one-sheet`.
- Email-fallback paragraph → `/silence`.
- Closing fine-print → `/vision/lc-network`, `/me/work`, `/share`,
  `/join`.
- After-submit destination → `/arrival/[id]` (the celebration page).

**`/share`:**
- Hero paragraph → `/vision/lc-agent-memory`, `/vision/lc-resonating`,
  `/with-us`.
- "New here" paragraph → `/begin`, `/come-in`, `/one-sheet`.
- Confirmation hero → `/vision/lc-agent-memory`,
  `/vision/lc-resonating`.
- Confirmation footer → `/me/work`, `/one-sheet#nectar`, `/me`,
  `/with-us`.

**`/me/work`:**
- Hero → `/vision/lc-w-cell`, `/vision/lc-agent-memory`,
  `/one-sheet#memory`.
- Empty state → `/share`, `/begin`.
- "Built with — AI cells" → `/vision/lc-w-cell`, `/come-in`,
  `/one-sheet#we`.
- "What this is, what it isn't" → `/vision/lc-w-field`, `/silence`,
  `/share`, `/begin`, `/with-us`.

**`/practice`:**
- Header paragraph → `/vision/lc-stillness`, `/vision/lc-network`,
  `/one-sheet#breath`, `/silence/breath`.

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
