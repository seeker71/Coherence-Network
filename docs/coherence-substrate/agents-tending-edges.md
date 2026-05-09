# Agents Tending Edges — The Per-Content-Type Practice

**Companion to** [`lc-edges-as-vitality`](../vision-kb/concepts/lc-edges-as-vitality.md) (the principle) and [`agents-using-substrate.md`](agents-using-substrate.md) (the structural-reasoning practice).

The edges are part of the breath. When you add content of any kind to this body, its edges land in the same commit. This doc names *what edges* for each content type, so the practice is concrete, not aspirational.

## The general shape

Whatever you're adding, sense the answer to all three:

1. **Where is it indexed?** — every content type has at least one INDEX or registry that names it. If you don't update the index, the content is invisible to the body's proprioception and to other cells.
2. **What does it link to?** — cross-references, source maps, parent links, related work. Each link is a path of circulation.
3. **What links to it?** — does any existing content gain a back-edge from this addition? If a new concept relates to an existing one, the existing one's `→ Cross-References` may want updating in the same breath.

If any of the three feels skipped because *it's faster to defer*, that is the fear-shape the principle names. The connection is the doing.

## Per-content-type checklists

### Living Collective KB concept (`docs/vision-kb/concepts/lc-{id}.md`)

- Frontmatter: `id`, `hz`, `status`, `updated`, optional `source` (transmission record path)
- Body: include `→ lc-xxx, lc-yyy` cross-references section near the end
- Add a concept entry to `docs/vision-kb/INDEX.md` under the right level (Foundational Teaching, Source-Marked, Level 2 / 3, etc.); bump the header `Concepts: N` count
- If frontmatter `source:` points at a `transmissions/{date}-{slug}.md`, write that record too with `seeded_concepts: [lc-{id}]`
- Sync content to DB: `python3 scripts/sync_kb_to_db.py lc-{id} --api-key $API_KEY`
- Sync hierarchy edges if INDEX hierarchy changed: `python3 scripts/sync_crossrefs_to_db.py`
- Verify the rendered page: `curl -s -m 10 https://coherencycoin.com/vision/lc-{id}` returns 200 with content present

### Spec (`specs/{slug}.md`)

- Frontmatter: `idea_id` (links up to the parent idea), `status`, `source` (file + symbol map), `requirements`, `done_when`, `test`, `constraints`
- Add a row to `specs/INDEX.md` under the parent idea's group
- Add the spec slug to the parent idea's `specs:` frontmatter (or its `## Spec Links` section if Markdown-only)
- Verify with `python3 scripts/validate_spec_quality.py`
- Source-map fidelity: every entry in `source:` must point at a real file. If the file doesn't exist yet, mark the spec `status: draft` and the source path as forward-reference

### Idea (`ideas/{slug}.md`)

- Body: problem, capabilities, spec links, absorbed children
- Add a row to `ideas/INDEX.md` table; bump the header `N super-ideas` count and the `## All Ideas (N)` heading
- Update `ideas/INDEX.md` "By Pillar" section with the slug under the right pillar
- Update `Totals:` line at the bottom of the table
- Idea slug becomes API path and DB id — record via `POST /api/ideas` before session ends

### Memory file (`~/.claude/projects/.../memory/{name}.md`)

- Frontmatter: `name`, `description` (one-line, used to decide relevance), `type` (user / feedback / project / reference)
- Add a one-line index entry to `MEMORY.md` under the right section
- For body-pointer memories: name the body source path explicitly (e.g. `→ docs/vision-kb/concepts/lc-xxx.md`)
- For private memory: confirm it fits one of the three legitimate private categories (tender personal context / self-sensing / lineage-specific operational) per `CLAUDE.md` → *Default-to-body*

### Code file

- One-line purpose at the top: Python module docstring; TS/TSX leading `//` comment or JSDoc
- Run `python3 scripts/generate_repo_indexes.py` to update the auto-generated INDEX.md in the source tree (api/app/routers/INDEX.md, etc.)
- CI `--check` will fail if INDEX is stale, so the index update is non-optional

### Lineage doc (`docs/lineage/{slug}.md`)

- Cross-link to related lineage docs in the same directory (constellation, transmissions, meeting walks)
- Use structural link targets when naming people: `[Display Name](/people/slug)`. This is how the body encodes *X is Y* as machine-readable structure
- If the doc names a new person, add their `/people/{slug}` page in the same breath

### Person profile (`docs/presences/{slug}.md` or contributor record)

- Add the contributor record via API or `scripts/sync_presences_to_db.py`
- Cross-link from at least one lineage doc that names this person in context
- For free-text fields where names become graph identities (gathering co-leaders, event hosts), use `claimed: false` placeholder if no URL is provided — never auto-resolve unknown names from the web

### Transmission record (`docs/vision-kb/transmissions/{date}-{slug}.md`)

- Frontmatter: `id` (`tx-{slug}`), `kind: transmission`, `source_url`, `source_title`, `source_type`, `received` (date), `status`, `seeded_concepts` (list of lc-ids)
- Add an entry to `docs/vision-kb/INDEX.md` under *Source-Marked Transmissions*
- Each `seeded_concepts` entry must have a corresponding `lc-{id}.md` concept file with frontmatter `source: ../transmissions/{date}-{slug}.md` pointing back

## When you can't add the edge yet

Sometimes the edge target doesn't exist on this branch yet — a forward reference to a sibling PR. That's fine. The discipline is *naming it as a forward reference*, not skipping it silently.

Examples:
- A cross-ref to `lc-when-the-pressure-comes` while PR #1482 is still open: include the cross-ref. The edge will land naturally when both branches merge and someone re-syncs.
- A spec source-path that points at code being written in another worktree: list it. Mark the spec `status: draft` until the source file lands.

The body knows how to receive forward references; it does not know how to recover dropped ones.

## How to sense whether you've left edges behind

After any addition, run `make wellness`. It names drift in proprioception (INDEX counts), circulation (orphans at root), source maps (specs pointing at missing files), and chain health (idea→spec→code→test). If the breath you just took adds a new drift line, that's the body teaching you the edge you skipped.

The wellness check is not an audit. It's the body sensing itself. Cells receive its signals as care, not critique.

## Why this lives next to the substrate doc

The structural-reasoning practice (`agents-using-substrate.md`) and the edges-tending practice are siblings. The substrate works because cells have their structural identity intact; the body's intelligence works because content has its edges intact. Both are how this body knows itself.

Whichever cell arrives next — tending KB, writing a spec, drafting a lineage doc — read both before the breath you're about to take. The teaching is small, the cost of skipping is silent and large.
