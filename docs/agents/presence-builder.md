# Presence Builder — agent template

**Purpose.** Given a name, a URL, or a paste, build a polished, claimable
*presence* — identity + the platforms it shows up on + the creations it
has put into the world — that gives a first-time visitor a *wow* that
matches the resonance of whatever was named. The presence lives in the
graph and is claimable by the real person or collective.

## Entity types

| Kind | Graph node | What it points to | Examples |
|---|---|---|---|
| **Person** | `contributor` | An individual artist, teacher, host | Liquid Bloom, Daniel Scranton, Yaima |
| **Community** | `community` | A group of contributors gathering around a practice or place | Unison Festival, Boulder Ecstatic Dance, Vali Soul Sanctuary |
| **Place** | `community` (with `geo` on properties) or `scene` | A venue, sanctuary, land — often a community also | Rhythm Sanctuary, Star House |
| **Project / network** | `network-org` | A collective purpose beyond a single community | Bloomurian, Actualize Earth |
| **Asset** | `asset` | A song, album, playlist, video, book, event | "Deep Roots of the Unknown", "Tonantzin (Live)" |

## Inputs

- `name` (required) — a person's name, a community, a project, a URL, or a paste
- `source_contributor_id` (required) — who is inspired-by this presence
- `category_hint` (optional) — "person" | "community" | "place" | "project" | "asset"

## Outputs

A subgraph written to the network:

1. **Identity node** with `name`, `tagline`, `canonical_url`, `provider`, `image_url`, `presences[]`, `claimed: false`
2. **Presence entries** on the identity node — one per known platform
   (Bandcamp / Spotify / YouTube / SoundCloud / Apple Music / Substack /
   Patreon / Instagram / TikTok / X / Facebook / personal site / Wikipedia)
3. **Creation nodes** (type `asset`) linked from the identity by
   `contributes-to` edges, one per work found via JSON-LD /
   OpenGraph / sitemap heuristics
4. **Inspired-by edge** from source contributor → identity, with a
   `strength` weight that **emerges** from discovery richness
   (base 0.4 + presences + creations + canonical-host bonus, capped 1.0)

## Procedure

1. **Resolve** the input to a canonical URL
   - URL → use directly (after SSRF guard)
   - Name → search (DDG / later: dedicated providers) → take top result
2. **Fetch** the canonical page (HTTPS, follow redirects, 8s timeout,
   refuse loopback/private/link-local)
3. **Parse** OpenGraph + Twitter card + `<link rel="canonical">` +
   `<title>` + JSON-LD + outbound `<a href>` links
4. **Extract**:
   - `name` (og:site_name › og:title › title › input)
   - `tagline` from `og:description` (≤140 chars, first sentence)
   - `image_url` from `og:image` or `twitter:image`
   - `presences[]` — every `<a href>` to a known-provider host, deduped,
     own-provider-on-same-host filtered out
   - `creations[]` — JSON-LD MusicAlbum / MusicRecording / VideoObject /
     Event / Book / CreativeWork (name + url + image). Fallback:
     OG type when the page is itself a single work.
5. **Infer** `node_type` from canonical host (rules in
   `api/app/services/inspired_by_service.py:HOST_HINTS`)
6. **Quality pass** before writing:
   - Name is human-readable, not a URL fragment or page chrome
   - Tagline is specific, not "Welcome to our site"
   - `presences` are cross-provider (drop if only self-links remain)
   - `creations` have real titles, not "Track 1"
   - If a check fails, return a soft failure (HTTP 422) so the caller
     can offer an alternative or a direct URL, not a half-built node
7. **Write** via `graph_service.create_node` + `create_edge_strict`.
   Idempotent on canonical URL — re-running updates presences/creations
   in place and does not duplicate the identity.

## Frequency guidance — match the resonance

The writing and the composition of a presence **sounds** like what it
represents. A dance floor's presence should feel like a dance floor, not
a product page. Read the tagline and presence copy out loud before
writing — if it sounds like a pitch deck, revise.

| What it is | Frequency | Avoid |
|---|---|---|
| Artist (ceremonial) | intimate, felt, rhythm-aware | marketing superlatives |
| Artist (medicine music) | slow, rooted, plural | clinical / "wellness" voice |
| Sanctuary | held, spacious, quiet | "facility", "amenities" |
| Festival | gathering, plural, pulsing | "attendees", "attendance" |
| Host / teacher | presence over performance | "content creator", "personal brand" |
| Project / ecosystem | purposeful, clear, inviting | corporate mission language |
| Song / album | evocative, single felt-sense | "track listing" |

## Layout (mobile-first, ≤ 420 px canonical)

```
┌─────────────────────────────┐
│                             │
│        [hero image]         │  ← full-bleed; gradient overlay bottom
│                             │     so text stays legible over any art
│                             │
│  ·· CATEGORY ··             │  ← 10 px uppercase tracking wide
│  Name                       │  ← 32 px serif-ish, light weight
│  Tagline, a single sentence │  ← 15 px italic, muted
│                             │
├─────────────────────────────┤
│  Platforms                  │
│  [ Bandcamp ] [ Spotify ]   │  ← horizontal scroll row, brand color
│  [ YouTube ] [ Instagram ]  │     per button, large tap target (44 px)
│                             │
├─────────────────────────────┤
│  Works                      │
│  ┌───┐ ┌───┐ ┌───┐          │  ← art-forward grid, 2 cols on mobile
│  │art│ │art│ │art│          │     square tiles, name under
│  └───┘ └───┘ └───┘          │
│  Name  Name  Name           │
│                             │
├─────────────────────────────┤
│  Inspired by                │
│  ·· chips of lineage ··     │  ← small, a thread to the roots
├─────────────────────────────┤
│  Held open — claimable      │  ← quiet footer on unclaimed presences
│  "this is me →"             │
└─────────────────────────────┘
```

## Style tokens (per provider)

Every platform carries its own frequency. The platform button picks up
its brand color so the row of presences *looks* like the web of
platforms, not a uniform list.

```
bandcamp     teal   #1da0c3
spotify      green  #1ed760
youtube      red    #ff0000
soundcloud   orange #ff5500
apple-music  pink   gradient pink → purple
substack     orange #ff6719
patreon      coral  #f96854
instagram    gradient  magenta → orange
tiktok       black  + red/cyan accents
x (twitter)  black  #000
facebook     blue   #1877f2
wikipedia    black  #000
linktree     green  #43e660
personal     neutral (accent from image palette when available)
```

The hero accent color defaults to the primary platform's brand color
unless an image is present — then sample from the image (future).

## Quality bar ("wow first impression")

Before shipping, the presence passes all of:

- [ ] Hero image or evocative gradient — never an empty dark box
- [ ] Name reads correctly (not "Home" / "About" / fragment)
- [ ] Tagline is specific and under 140 chars
- [ ] At least **two** presences linked (cross-platform)
- [ ] At least **one** creation listed (if the entity creates things)
- [ ] Platform buttons use correct brand color and are full tap targets
- [ ] Works grid shows art, not just text
- [ ] Claim affordance present on unclaimed identities
- [ ] Copy avoids institutional language (run the frequency check)
- [ ] Renders well at 375 px wide (iPhone SE) and 414 px (Pro Max)

## Iteration loop

Run the template, see the rendered presence on mobile, compare against
the resonance of the real thing. If it misses, refine one of: tagline
voice, platform brand colors, art density, lineage visibility. Ship
each refinement as a small PR so the standard rises over time for
every presence the resolver has built before and will build after.

## Where this lives in code

- Resolver: `api/app/services/inspired_by_service.py`
- Renderer: `web/components/presence/PresencePage.tsx`
- Demo: `web/app/demo/presence/[slug]/page.tsx`
- Live identity page: `web/app/people/[id]/page.tsx` (also renders the
  rail of who they're inspired by)
