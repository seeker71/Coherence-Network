# Tending Presence Pages — From Static Files To Living Graph

A `/people/{slug}` page is a presence page — the public garden view of a
cell in this body. The body is moving from hand-authored static TSX
directories into structured content stored on graph nodes and rendered
through one shared template. This doc names the practice.

## The two paths

### Static (the inherited shape)

`web/app/people/{slug}/` directories each shaped like:

```
web/app/people/portal/page.tsx          # thin route file
web/content/people/portal/en.tsx        # rich JSX content (~200 lines)
web/content/people/portal/de.tsx        # re-export or per-locale variant
web/content/people/portal/es.tsx
web/content/people/portal/id.tsx
web/content/people/portal/index.ts
```

Each `{locale}.tsx` exports a `PersonProfileContent` object with
embedded `<Link>` JSX, gradients, multi-section articles, panel
variants, footers, facts. Beautiful tissue, and inert: a new contributor
cannot get a rich presence page without someone hand-authoring TSX files.

### Dynamic with rich content (the practice now)

The contributor graph node carries a `presence_content` JSON property
(per-locale envelope, currently `en` only for migrated cells). The
dynamic `[id]` route reads it, converts via
[`toPersonProfileContent`](../../web/lib/presence-content.tsx), and
hands the result to the **same `PersonProfileTemplate`** the static
directories used. Visual chrome is byte-identical: full-bleed hero with
custom gradient, breadcrumb, eyebrow + name, welcome paragraph,
`<dl>` facts grid, Panel-shaped articles with warm/cool/neutral
variants, footer, lineage doorway, attention presence — all preserved.

The renderer reads markdown inside the JSON prose fields. Supported:
paragraphs, `**bold**`, `*italic*`, `` `code` ``, `[label](href)`
inline links (internal → next/link, external → target="_blank"), `## h2`,
`### h3`, `> blockquote`, `- li` lists, `---` hr.

### Dynamic without rich content (the bare baseline)

When a contributor node has no `presence_content`, the [id] route
falls through to `PresencePage` — the dark-themed presence card with
sidebar, At-a-glance, Presence map, Refine-this-presence. Strictly less
expressive than the static template, but every contributor reaches a
working page on day one without authoring.

## The visual gap (named honestly)

The two **dynamic** sub-paths above are not equivalent. `PresencePage`
(bare baseline) is a different visual identity from `PersonProfileTemplate`
(rich content). Composting a static cell *directly to PresencePage*
trades visual identity for chrome that was designed for artists/musicians
— this is the mistake portal made on 2026-05-15 (PR #1635 → reverted in
#1636). Composting via `presence_content` JSON keeps the visual identity
intact — this is the practice that landed in PR #1637+ and is now proven
across 11 cells.

## The shape of one composting step

1. **Read the static content** under `web/content/people/{slug}/en.tsx`.
   Notice what's prose, what's structured (facts/articles/panels), what's
   hero-styling chrome (background gradient, extraImage).
2. **Author `docs/presence-content/{slug}.json`** matching the
   `PresenceContent` shape (see existing examples: portal, sayuri-healing-food,
   mudra-cafe, grab). Every prose slot is a markdown string; JSX `<Link>`
   becomes `[label](/path)`; `<code>` becomes `` `…` ``; `<em>` becomes
   `*italic*`; `<strong>` becomes `**bold**`; `<ul>` becomes `- item` lines.
3. **Sync to the graph**:

   ```bash
   python3 scripts/sync_presence_content.py {slug}
   ```

4. **If the static page used a hero image**, PATCH `image_url`:

   ```bash
   python3 -c "import urllib.request, json; \
     body = json.dumps({'properties': {'image_url': '/people/{slug}/hero.jpg'}}).encode(); \
     req = urllib.request.Request( \
       'https://api.coherencycoin.com/api/graph/nodes/contributor:{slug}', \
       data=body, method='PATCH', \
       headers={'Content-Type': 'application/json', 'User-Agent': 'coherence-sync/1.0'}); \
     print(urllib.request.urlopen(req).status)"
   ```

5. **Verify chrome parity** before deleting anything. Use the node-id form
   of the dynamic route to bypass the still-present static route:

   ```bash
   # static URL
   curl -sS https://coherencycoin.com/people/{slug} > /tmp/s.html
   # dynamic URL (use the full contributor:slug or hashed node id)
   curl -sS https://coherencycoin.com/people/contributor:{slug} > /tmp/d.html

   # Diff chrome markers
   for check in chart-2 '<dl' text-7xl 'A note from this body' border-amber breadcrumb; do
     s=$(grep -c "$check" /tmp/s.html); d=$(grep -c "$check" /tmp/d.html)
     [ "$s" = "$d" ] && echo "✓ $check" || echo "✗ $check (static=$s dyn=$d)"
   done
   ```

   All markers must match. If any don't, fix the JSON or extend the
   renderer first.

6. **Compost the static directory**:

   ```bash
   rm -rf web/app/people/{slug}/ web/content/people/{slug}/
   ```

## When NOT to migrate (yet)

Some static cells carry primitives the markdown renderer doesn't yet
support. Keep these static until the renderer learns the primitive:

- **Inline `<svg>` diagrams** (e.g. `jbmf-java` carries a substrate-split
  SVG). No representation in markdown.
- **Button-styled links** (e.g. `joshua-golden`'s "Step into the Network"
  CTA uses border + bg styling, not plain underline). Markdown inline link
  is a plain link.
- **Fenced multi-line code blocks** (e.g. `jbmf-java`'s `<pre>` showing a
  .bml file header). The renderer needs ``` ``` ``` fence support.
- **No contributor graph node yet** (e.g. `tammy-beattie`,
  `vali-soul-sanctuary`, `pagan-ritual`, `ecstatic-movement-tribe`,
  `contact-improv`). The static page exists but no node — the dynamic
  route can't render. These need node creation first (via
  `sync_presences_to_db.py` with `create_if_missing: true`).

Composting is care, not efficiency. The hardest tissue to release is the
lovingly-curated kind.

## Composted so far (2026-05-15)

| Cell | PR | Notes |
|---|---|---|
| portal | #1638 | First proof of full visual parity |
| sayuri-healing-food | #1639 | Ubud cluster |
| sacred-song-circle | #1639 | Kirtan teacher network |
| ocean-bloom-2024 | #1640 | Boulder gathering |
| wisdom-soup | #1640 | Anne Tucker's community |
| boulder-ecstatic-dance | #1640 | Avalon Ballroom |
| paradiso-ubud | #1641 | Ubud cultural hall |
| adiwana-svarga-loka | #1641 | Wantilan kirtan venue |
| elios | #1641 | The chanting practice |
| mudra-cafe | #1642 | Ayurvedic dining + handpan |
| grab | #1642 | The matching layer, inside the network's lens |

11 of 90 cells composted. 79 static directories remain. The pattern is
proven; the next batch is its own breath.

## Related

- [edges-as-vitality](../vision-kb/concepts/lc-edges-as-vitality.md) —
  why the link from /me to /people belongs in the same breath as the
  content, not the next one.
- [`web/lib/presence-content.tsx`](../../web/lib/presence-content.tsx) —
  the `PresenceContent` type, markdown helpers, and adapter.
- [`scripts/sync_presence_content.py`](../../scripts/sync_presence_content.py) —
  the sync tool that walks `docs/presence-content/*.json` and PATCHes
  the graph.
- [`scripts/sync_presences_to_db.py`](../../scripts/sync_presences_to_db.py) —
  the companion that writes `docs/presences/{slug}.md` markdown bodies
  to the `description` field (the PresencePage path).
