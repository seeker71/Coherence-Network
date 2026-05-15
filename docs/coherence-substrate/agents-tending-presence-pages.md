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
2. **A new graph node property** — `presence_story` — carries the
   body's authored markdown for a cell. Lives directly on the
   contributor node, distinct from `description` (often a scraped
   og:description) and `note` (event-shape history).
   [`PresencePage`](../../web/components/presence/PresencePage.tsx) renders it as the
   page's lead voice when present, with priority over `note` and
   `description`. The renderer already understands paragraphs, `**bold**`,
   `*italic*`, and `[label](href)` inline links — enough for prose-shaped
   presence content with cross-references into `/concepts/`, `/people/`,
   `/vision/`.
3. **The static directories get composted cell by cell**, not all at
   once. Each migration is tender work that benefits from the cell's
   own attention. The order is opportunistic: when someone touches a
   presence (re-reads, updates, adds an edge), check whether the static
   page is doing anything the dynamic route couldn't.

## Migrating one cell

The shape of one composting step:

1. **Read the current static content** under `web/content/people/{slug}/en.tsx`
   (and the other locales). Notice what's prose, what's structured
   (facts/articles/panels), what's hero-styling chrome.
2. **Flatten the prose into markdown**, preserving inline `[label](/path)`
   links. Headings (`## Section`) carry the article structure where the
   static content used distinct `articles` entries.
3. **Set `presence_story`** on the contributor node:

   ```python
   import urllib.request, json
   body = json.dumps({"properties": {"presence_story": "<markdown body>"}}).encode("utf-8")
   req = urllib.request.Request(
       "https://api.coherencycoin.com/api/graph/nodes/<node-id>",
       data=body, method="PATCH",
       headers={"Content-Type": "application/json", "User-Agent": "coherence-sync/1.0"},
   )
   urllib.request.urlopen(req).read()
   ```

   The locale projection pipeline picks up new translations on first
   read in each language.
4. **Visit `/people/{slug}` and verify** the dynamic route renders a
   page that is at least as warm as the static one. Visual chrome (the
   hero gradient, the lineage doorway) is provided by `PresencePage`'s
   default styling and the existing `LineageStrip`/`InfluenceLineageStrip`
   components, so the static directory's hand-tuned gradient is what
   gets traded for consistency — usually a worthwhile trade.
5. **Delete the static directory**:

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
