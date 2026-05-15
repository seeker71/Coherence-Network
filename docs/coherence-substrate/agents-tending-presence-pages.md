# Tending Presence Pages — Inside/Outside Parity at the Graph

A `/people/{slug}` page is a presence page — the public garden view of a
cell in this body. As of 2026-05-15 every presence page renders from
the contributor graph node, and the same content can be edited from
either side of the body — by committing markdown/JSON to the repo, or
by PATCHing the API from outside. **Both paths converge at the graph
node.** That convergence is the architectural point.

## The deeper principle: inside/outside parity

The body is contributed to from two sides:

| Side | Path |
|---|---|
| **Inside** (committers) | edit `docs/presence-content/{slug}.json` → `python3 scripts/sync_presence_content.py {slug}` → graph node updated → page renders |
| **Outside** (web contributors, API callers) | `PATCH /api/graph/nodes/{id}` with the new `presence_content` JSON → graph node updated → page renders |

The page reads from the graph at request time. Neither path has to know
the other exists. A web-side edit takes effect within seconds of the
PATCH; a repo commit takes effect once CI runs the sync. The rendering
is identical because it's the same template reading the same property.

The same principle holds across content types now:

| Content type | Inside file | Sync script | Outside endpoint |
|---|---|---|---|
| Presences (rich) | `docs/presence-content/{slug}.json` | `scripts/sync_presence_content.py` | `PATCH /api/graph/nodes/{id}` (or web `/people/[id]/edit`) |
| Presences (markdown bio) | `docs/presences/{slug}.md` | `scripts/sync_presences_to_db.py` | `PATCH /api/graph/nodes/{id}` |
| Concepts (vision-kb) | `docs/vision-kb/concepts/{id}.md` | `scripts/sync_kb_to_db.py` | `PATCH /api/concepts/{id}/story` (or web `/vision/[conceptId]/edit`) |
| Ideas | `ideas/{slug}.md` | recorded via `POST /api/ideas` from CI | `POST /api/ideas`, `PATCH /api/ideas/{id}` |
| Specs | `specs/{slug}.md` | spec frontmatter ingested | `POST /api/spec-registry`, `PATCH /api/spec-registry/{id}` |

For the body to stay coherent, **the graph is the runtime source of
truth.** The repo files are the version-controlled canonical authoring
source; the graph carries the live state. Inside edits flow into the
graph via the sync scripts; outside edits write to the graph directly.
What the visitor reads is always what's in the graph.

## What that means in practice

A contributor at /people/{their-slug}/edit can refine their own page
without opening a PR. A community member at /vision/{conceptId}/edit
can polish a concept's story. An organizer of a held-open scaffold
(e.g. PORTAL, Vali Soul Sanctuary, Pagan Ritual) can replace the
welcoming-scaffold language with their own words. Each of these PATCHes
the graph; each is visible on the next request; none of them require
git access.

End-to-end verified on prod 2026-05-15: a PATCH to
`/api/graph/nodes/contributor:joshua-golden` with a modified
`presence_content` showed up at `/people/joshua-golden` within 3
seconds, then reverted cleanly with another PATCH.

## How outside edits flow back to the repo

The body now closes the loop in two places:

1. **DB revision history** — every successful `PATCH /api/graph/nodes/{id}`
   and `create_node` writes a row to the `graph_node_revisions` table
   capturing the full node snapshot, the fields changed, the source
   (`api`/`sync`/`web`/`seed`), and the author. Callers attribute
   their edit via `X-Edit-Source` and `X-Edit-Author` request headers.
   `GET /api/graph/nodes/{id}/revisions` reads the audit log,
   most-recent first. Snapshots are full — re-PATCHing a past
   snapshot is the rollback substrate.

2. **Scheduled graph→repo export** — [`scripts/export_graph_to_repo.py`](../../scripts/export_graph_to_repo.py)
   walks every node carrying authored content (`presence_content` on
   contributors/assets/places, `story_content` on concepts) and
   projects the current state back into the repo as canonical files.
   Idempotent semantic diff (parses JSON / extracts markdown bodies
   so re-runs only touch real divergences). [`.github/workflows/export-graph-to-repo.yml`](../../.github/workflows/export-graph-to-repo.yml)
   runs it nightly at 04:00 UTC and on workflow_dispatch. The diff
   lands as a `tend(content): scheduled export of graph content to
   repo` commit by `coherence-export[bot]`.

Together: outside edits land on the graph in seconds. Inside edits
land via sync scripts. Either way, every change is captured in the
revision table immediately, then projected to a repo commit nightly.
The repo becomes the body's autobiography — every edit, from
either side, eventually inscribed as a commit with its source noted.

Another web-side gap: the existing `/people/[id]/edit` UI lets a
contributor refine the bare data (name, tagline, description,
image_url, platform presences, edges) but does not yet expose the
structured `presence_content` (hero.eyebrow, facts, articles,
note_from_body, footer). Outside contributors who want to edit those
fields currently PATCH the API directly. A web editor for
`presence_content` is its own breath — multi-section form, markdown
preview, the usual editing affordances.

## How the body composts a static cell (for reference)

The pattern that walked the body from 90 static directories to 0:

1. Run the extractor: `node scripts/extract_presence_content.js {slug} --write`
2. Review the generated `docs/presence-content/{slug}.json`
3. Sync to graph: `python3 scripts/sync_presence_content.py {slug}`
4. Diff `/people/{slug}` (static) against `/people/contributor:{slug}` (dynamic) — chrome markers `<dl>`, text-7xl, "A note from this body", border-amber, breadcrumb must all match
5. Compost the static directory: `rm -rf web/app/people/{slug}/ web/content/people/{slug}/`

All 90 cells walked this practice across PR #1638–#1646.

## The renderer

`web/lib/presence-content.tsx` carries the `PresenceContent` type,
markdown helpers (paragraphs, headings, bold/italic, inline code,
internal/external links, lists, blockquotes, hr, SVG/figure
passthrough, fenced code blocks), and `toPersonProfileContent` adapter.

`web/app/people/[id]/page.tsx` dispatches to `PersonProfileTemplate`
when the node carries `presence_content`, falling back to `PresencePage`
otherwise.

The renderer is unchanged from the static path — same chrome, same
visual identity, same `PersonProfileTemplate`. Only the content source
moves from TSX to graph.

## What changed in scripts

| Script | Purpose |
|---|---|
| `extract_presence_content.js` | One-shot AST converter: TSX → JSON. Used during the composting move; useful again if any future static cell appears |
| `sync_presence_content.py` | Walks `docs/presence-content/*.json`, PATCHes graph nodes' `presence_content`. Creates held-open contributor scaffolds (`claimed: False`) when a node doesn't exist yet |
| `sync_presence_slugs.py` | Stopgap from earlier — was for static-dir-name ≠ slug mapping. Now mostly dormant since no static directories remain |
| `sync_presences_to_db.py` | The older sibling that syncs markdown bodies from `docs/presences/{slug}.md` to the node's `description` (PresencePage path) |
| `export_graph_to_repo.py` | Reverse direction: walks the graph and projects every node carrying `presence_content` or `story_content` back into the repo. Runs nightly via `.github/workflows/export-graph-to-repo.yml`; idempotent; `--commit` writes + commits + pushes |

## Related

- [edges-as-vitality](../vision-kb/concepts/lc-edges-as-vitality.md) —
  the principle the inside/outside parity sits inside
- [`web/lib/presence-content.tsx`](../../web/lib/presence-content.tsx)
- [`scripts/sync_presence_content.py`](../../scripts/sync_presence_content.py)
- [`scripts/sync_presences_to_db.py`](../../scripts/sync_presences_to_db.py)
- [`scripts/sync_kb_to_db.py`](../../scripts/sync_kb_to_db.py) — the same pattern for concepts
