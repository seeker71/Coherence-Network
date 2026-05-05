# Presence page data gaps

The `/people/[id]` presence renderer is now responsive on desktop and
mobile and surfaces every signal we have for an identity:

- hero image (when present), category, name, tagline
- platforms (every `presences[]` entry, brand-coloured chips)
- upcoming and past gatherings (every `event` node connected via
  `contributes-to`)
- creations (every `asset` node connected via `contributes-to`)
- resonance (every `resonates-with` edge to a `concept`)
- kindred (other presences sharing concepts with this one — derived
  via `/api/concepts/{id}/carried-by` and aggregated client-side)
- inspired-by lineage
- claim card

What the **renderer cannot fix** is missing source data. When a
presence's page feels empty, the gap usually lives in one of these
places:

## 1. No image_url

The graph node carries `image_url` only if the resolver found one.
Today the resolver is light: it picks up an obvious og-image when the
identity is created from a canonical URL. It does NOT:

- Walk the canonical site looking for `<meta property="og:image">`,
  `<link rel="apple-touch-icon">`, or `<img>` tags around the
  about/header
- Try the platform-native API (Spotify artist photo, Bandcamp band
  image, YouTube channel banner, Facebook page profile photo,
  Instagram profile photo) for each presence URL
- Re-resolve when a presence is added later

**Fix shape:** a `presence-resolver` worker that, for every
`identity` node missing `image_url`, fetches every URL in
`presences[]` and the `canonical_url`, parses common image meta, and
stores the best one. Re-runnable. Idempotent. Records source so we
can attribute.

## 2. No tagline

Same shape as image_url: would come from og-description /
about-text scrape. Today it must be hand-edited via the claim flow.

## 3. No `event` edges (empty Upcoming + no past events)

Events are only created when a contributor explicitly adds one via
`POST /api/presences/{id}/gatherings`. Public event listings on
Facebook events, Eventbrite, Bandsintown, Songkick — none of those
flow into the graph today.

**This is the gap that bit us on Actualize Earth.** That presence has
been the public Boulder events listing for years (FB events, IG
posts, the actualize.earth calendar). None of it is in the graph.
The page renders honestly: Actualize Earth has no events because no
one has added them. But the page reads as if Actualize Earth is
disconnected from the Boulder ecosystem — which is the opposite of
true.

**Fix shape:** a `gatherings-importer` worker. For every presence
that carries a Bandsintown / Eventbrite / Facebook URL, fetch the
upcoming + past events list, dedupe against existing event nodes by
`(name, when, where)`, create the event nodes that are missing, and
draw `contributes-to` edges from the presence to the event with
`role="primary"|"hosting"|"co-leading"` based on the source's
attribution. Re-runnable nightly.

For the actualize.earth calendar specifically, the import path is
likely an iCal feed or scraping the event grid on the page —
inspect `actualize.earth` to confirm. Both are doable.

## 4. No `creations` edges (empty Works grid)

Same pattern as events. Creations come from explicit POSTs to
`/api/presences/{id}/creations` (or whatever the analogous endpoint
is — verify in `api/app/routers/`). For artists, Spotify/Bandcamp/
YouTube/Apple Music could all auto-populate this if a worker existed.

## 5. No `resonates-with` edges (empty Resonates With + Kindred)

These are populated by `/api/presences/{id}/resonances/attune` —
which compares this presence's text (name, tagline, description) to
every concept in the Living Collective and lays edges where shared
tokens cross a threshold. **It runs once when the presence is
created or claimed**, then sits frozen unless someone re-runs it.

If this presence's resonances feel thin, the cause is usually:

- The presence has no tagline or description for the matcher to chew
  on (only a name + a URL list)
- Concepts have been added since the resonance attunement ran, so the
  presence never got compared against them

**Fix shape:** schedule the attunement on a timer (e.g. weekly), and
re-run it whenever the concept set changes by N. Cheap.

## 6. Location

There is no `location` edge model today. A presence either lives
somewhere or nowhere — but we can't say "Actualize Earth is in
Boulder" in a structured way that lets the page surface "other
Boulder presences" or "Boulder gatherings."

**Fix shape:** add a `place` node type and an `at-place` edge type.
Allow either a free-form locality string or a structured node
(City/Region) so we can surface geographic constellations on every
presence page.

## Why we're shipping the layout fix anyway

The layout change is independently useful: the page no longer wastes
992px of horizontal space on a 1440px desktop, the hero now feels
present even without a photo, and the kindred-presences sidebar
surfaces the constellation we *do* have (concept overlap) so a
visitor isn't faced with a totally lonely page.

The data-shaped gaps above are the next breath of work. None of them
should land as one-off scripts: they belong as workers that can be
re-run safely, that record provenance, and that compose with each
other (resolver before importer; importer before attunement). Spec
them properly before building.
