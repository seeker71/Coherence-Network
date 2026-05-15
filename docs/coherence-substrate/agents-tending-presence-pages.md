# Tending Presence Pages — From Static Files To Living Graph

A `/people/{slug}` page is a presence page — the public garden view of a
cell in this body. As of 2026-05-15 there are two parallel rendering
paths for those URLs that have been quietly coexisting. This doc names
the move from one to the other and the practice of composting the
old shape.

## The two paths

### Static (the inherited shape)

Ninety hand-authored directories under `web/app/people/{slug}/` each
shaped like:

```
web/app/people/portal/page.tsx          # thin route file
web/content/people/portal/en.tsx        # rich JSX content
web/content/people/portal/de.tsx        # same content in German
web/content/people/portal/es.tsx        # ... Spanish
web/content/people/portal/id.tsx        # ... Indonesian
web/content/people/portal/index.ts
```

Each `{locale}.tsx` exports a `PersonProfileContent` object with
embedded `<Link>` JSX, gradients, multi-section articles, panel
variants, footers, facts. Beautiful tissue, and inert: a new
contributor cannot get a presence page without someone hand-authoring
TSX files in four locales.

### Dynamic (the scalable shape)

`web/app/people/[id]/page.tsx` already renders any contributor whose
graph node exists. It fetches the node, its creations, its inspired-by
edges, and hands the lot to `PresencePage` (a templated renderer that
reads from node properties). Locales come from the node's projection
pipeline (`translation_cache_service`), not from per-locale TSX files.

Every contributor reaches a working presence page through this route
on day one. **No route file needs to exist for them.**

## Where the body is moving

The dynamic path is the truer baseline; the static directories are
debt to compost. Specifically:

1. **The /me hub tile** ([`web/components/MePage.tsx`](../../web/components/MePage.tsx)) links to `/people/{slug}` for every
   contributor with a `slug` field — not only those with a static
   directory. Implemented 2026-05-15.
2. **The graph node's `description` field** carries the body's authored
   markdown for the cell. The existing
   [`docs/presences/{slug}.md`](../presences/) → `sync_presences_to_db.py`
   → PATCH pipeline already writes here, so authoring presence content
   uses the same pattern as the rest of the body's markdown-as-truth
   tissue. [`PresencePage`](../../web/components/presence/PresencePage.tsx)
   renders `description` through `DescriptionBlock` — paragraphs,
   `**bold**`, `*italic*`, `[label](href)` inline links, `## Heading`
   and `### Subheading`, and `---` horizontal rules. (A separate
   `presence_story` property exists as a future field for when the
   body's authored voice needs to live alongside a still-useful scraped
   `description`; today it's dormant — composting writes to
   `description` directly.)
3. **The static directories get composted cell by cell**, not all at
   once. Each migration is tender work that benefits from the cell's
   own attention. The order is opportunistic: when someone touches a
   presence (re-reads, updates, adds an edge), check whether the static
   page is doing anything the dynamic route couldn't.

## Migrating one cell

The body's existing presence-as-markdown pattern is the path. Files at
[`docs/presences/{slug}.md`](../presences/) hold YAML frontmatter + a
markdown body; [`scripts/sync_presences_to_db.py`](../../scripts/sync_presences_to_db.py)
walks each file and PATCHes the node's `description`. The dynamic
`[id]` route reads `description` and renders it through
[`DescriptionBlock`](../../web/components/presence/PresencePage.tsx) —
paragraphs, `**bold**`, `*italic*`, `[label](href)` inline links,
`## Heading` and `### Subheading`, and `---` horizontal rules.

The shape of one composting step:

1. **Read the current static content** under `web/content/people/{slug}/en.tsx`
   (and the other locales). Notice what's prose, what's structured
   (facts/articles/panels), what's hero-styling chrome.
2. **Author `docs/presences/{slug}.md`** with frontmatter
   (`name`, `canonical_url`, `type`, `contributor_type`) and a rich
   markdown body. Facts flatten to `**Label** — value` lines; the
   `noteFromBody` and each article become `## Section` blocks; the
   footer becomes the closing paragraph after a `---` divider. Inline
   JSX `<Link>` becomes `[label](/path)`.
3. **Sync to the graph**:

   ```bash
   python3 scripts/sync_presences_to_db.py {slug}
   ```

   The PATCH endpoint auto-re-attunes resonance edges when description
   changes, so concept links stay aligned.
4. **Set `image_url`** if the static page used a hero image:

   ```bash
   python3 -c "import urllib.request, json; \
     body = json.dumps({'properties': {'image_url': '/people/{slug}/hero.jpg'}}).encode(); \
     req = urllib.request.Request( \
       'https://api.coherencycoin.com/api/graph/nodes/contributor:{node-id}', \
       data=body, method='PATCH', \
       headers={'Content-Type': 'application/json', 'User-Agent': 'coherence-sync/1.0'}); \
     print(urllib.request.urlopen(req).status)"
   ```

5. **Visit `/people/{node-id-suffix}` and verify** the dynamic route
   renders the rich content before deleting anything. Use the node-id
   form (e.g. `/people/portal-3980e2c1a203`) to bypass the still-present
   static route at `/people/{slug}`.
6. **Delete the static directory**:

   ```
   web/app/people/{slug}/page.tsx
   web/content/people/{slug}/
   ```

   Composting also means removing the `graphSlug=` reference in the
   route file (the only consumer was the static page itself).
6. **Re-run `python3 scripts/sync_presence_slugs.py`** so the
   `presence_slug` field on the contributor node either updates or
   composts away (when the static directory is gone, the override is
   no longer needed; the contributor's own `slug` carries the tile).

## When NOT to migrate

Some static directories carry visual chrome the dynamic route doesn't
yet honor — custom hero gradients, multi-image composites, specific
panel layouts the prose body alone can't reproduce. Those cells stay
on the static path until either:

- The body has accepted the trade (consistency > custom chrome), or
- `PresencePage` learns the missing visual primitive

Composting is care, not efficiency. The hardest tissue to release is
the lovingly-curated kind.

## What's already true

- The `[id]` dynamic route works today: try `/people/{any-slug}` for a
  contributor whose body has a graph node. PresencePage renders.
- The `presence_story` field is read on every render — no migration
  flag, no feature gate. Set it on a contributor, the page picks it
  up on next request.
- The /me tile links every contributor to their slug-based URL, so a
  brand new contributor sees their own presence page from day one
  without any authoring step.

## Related

- [edges-as-vitality](../vision-kb/concepts/lc-edges-as-vitality.md) —
  why the link from /me to /people belongs in the same breath as the
  content, not the next one.
- [`scripts/sync_presence_slugs.py`](../../scripts/sync_presence_slugs.py) —
  the stopgap that maps static-dir-name → contributor node while the
  static directories still exist.
