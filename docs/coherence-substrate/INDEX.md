# Coherence-substrate — index

The body's content-addressed numeric lattice. Cells from every memory file, spec, idea, concept story, presence, lineage edge, witness, and task live here as interned NodeIDs — addressable, queryable, structurally-equivalent across surface differences.

## Where to start

| Reader | Read first |
|---|---|
| Agent operating on this body | [`agents-using-substrate.md`](agents-using-substrate.md) — when to reach for the substrate, how to ground reasoning structurally |
| Designing a Form fragment | [`form-language.md`](form-language.md) — the substrate-native language |
| Choosing or changing category numbers | [`numeric-schema.md`](numeric-schema.md) — intentional bands for domain and recipe vocabulary |
| Implementing | `api/app/services/substrate/` (the kernel) + `api/tests/test_substrate.py` |
| Lineage / architectural design notes | `docs/field/urs/artifacts/nums-go-2023/` |

## What lives where

| Path | What it carries |
|---|---|
| `api/app/services/substrate/kernel.py` | NodeID, Recipe, NamedCell, intern_node, make_cell, find_equivalent_cells, lattice_stats |
| `api/app/services/substrate/category.py` | Network category vocabulary (Idea/Spec/Concept/Memory/Presence/Task/Lineage/Witness/Transmission/Resource/Guide/LanguageView/KBPage; Realize/Compose/Transmit/Tend/Resolve/Witness/Absorb/Score) |
| `api/app/services/substrate/orm.py` | SubstrateNodeORM, SubstrateNamedCellORM (the two tables) |
| `api/app/services/substrate/markdown_frontend.py` | Frontmatter+body → cell ingestion for memory, spec, idea, concept, presence, lineage, transmission, resource, guide, language-view, and KB-page files |
| `api/app/services/substrate/resonance.py` | Dimensional vocabulary (Spectrum / Harmonic / GeometricForm / Polarity / Topology) + `author_geometry_signature()` — receives the 15D `geometry:` blocks vision-kb concepts carry, authors resonance edges so the substrate sees cross-discipline shape equivalence |
| `scripts/coh_substrate.py` | Unified CLI: `ingest`, `stats`, `equivalent`, `annotate`, `form`, `ingest-paths`, `kb-sync-audit` |
| `scripts/coh_form.py` | Form-only CLI (superseded; `coh_substrate.py form` is the active entry) |
| `api/tests/test_substrate.py` | Flow-centric tests (registered in `core_suite.txt`) |
| `docs/coherence-substrate/form-language.md` | Form — the substrate-native language design |
| `docs/coherence-substrate/form-engine.form` | The recipe-evaluator in Form's own voice — 15/15 RBasic dispatch arms self-hosted |
| `docs/coherence-substrate/form-runtime-in-form.form` | Companion to form-engine — walks lexer / parser / evaluator / registries / substrate-write in Form, names the 15 surface gaps to full self-hosting |
| `docs/coherence-substrate/agents-using-substrate.md` | Agent guide — when and how to ground reasoning |
| `docs/coherence-substrate/agents-tending-presence-pages.md` | Composting static `/people/{slug}` directories into graph-rendered presence pages |

## The trinity

| Phase | Primitive | What it is |
|---|---|---|
| **Ice** | Blueprint | Structural identity. *What something IS.* Frozen coordination. |
| **Water** | Recipe | Operational expression. *How something HAPPENS.* Flowing verb-graph. |
| **Gas** | NamedCell | Diffuse individuation. *Where something LIVES.* Named slot with seed. |

## In one query

Annotate a path you're about to read:

```bash
python3 scripts/coh_substrate.py annotate path/to/file.md
# → cell, blueprint, domain, equivalents
```

Find structurally-equivalent cells:

```bash
python3 scripts/coh_substrate.py equivalent memory "User biographical arc"
```

Or in Form:

```bash
python3 scripts/coh_substrate.py form '?equivalent @memory("User biographical arc")'
```

38 of 40 memory files in the body are equivalent to this one, by structural shape.

## Use the substrate

The substrate is now woven into daily practice through three commands:

### Discover what shapes exist

```bash
python3 scripts/coh_substrate.py discover
```

Surfaces:
- The largest blueprint clusters (e.g. 67 specs sharing the canonical spec frontmatter shape)
- Singletons (cells with shapes nowhere else in the body)
- Cross-domain collisions (same shape across multiple domains — refactor signal)

### Shape-check before authoring

```bash
python3 scripts/coh_substrate.py shape-check path/to/draft-spec.md
```

Computes the Blueprint shape this draft would have and surfaces existing cells with the same shape. Catches duplication and structural drift before they ship. Output: either "✓ new structural pattern" or "⚠ N existing cells share this shape" with the names.

### Auto-ingest on commit

```bash
# Manual installation (per developer):
ln -s ../../scripts/substrate_post_merge_hook.sh .git/hooks/post-merge
chmod +x .git/hooks/post-merge

# Or in CI, after merge to main:
bash scripts/substrate_post_merge_hook.sh
```

After every merge, changed `.md` files in tracked domains are auto-ingested. The substrate stays current with the body's tissue.

```bash
# Manual: feed paths from anywhere (git diff, find, etc.)
git diff --name-only HEAD~1..HEAD '*.md' | python3 scripts/coh_substrate.py ingest-paths --from-stdin
```

### Audit KB/substrate drift

```bash
python3 scripts/coh_substrate.py kb-sync-audit --strict
```

Compares canonical `docs/vision-kb/concepts/lc-*.md` files to live `@concept(...)` NamedCells. It reports missing cells, stale deleted/renamed cells, source-path drift, wrong-domain ingests, duplicate concept ids, and counts the other first-class KB surfaces: transmissions, resources, guides, language views, and KB pages. Those surfaces enter through `ingest-paths` or targeted backfills such as `ingest --resources --guides --language-views --kb-pages --transmissions`. For reviewed deletes/renames:

```bash
python3 scripts/coh_substrate.py kb-sync-audit --prune-stale
```

This prunes stale live NamedCells only; interned Blueprint/Recipe nodes can remain as historical structural memory.

## Phase status (as of 2026-05)

- Phase 1 ✓ — building-knowledge from prior art (kernel walk + run + mini-port + design doc)
- Phase 2 ✓ — Network category vocabulary designed
- Phase 3 ✓ — kernel + memory frontend + CLI + 11 tests; substrate ingests body's memories
- Phase 4 — REST API, Neo4j integration, agent-context auto-annotation, first-class KB surface coverage, backfill, and higher-order extraction (in progress)
