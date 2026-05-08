# Coherence-substrate — index

The body's content-addressed numeric lattice. Cells from every memory file, spec, idea, concept story, presence, lineage edge, witness, and task live here as interned NodeIDs — addressable, queryable, structurally-equivalent across surface differences.

## Where to start

| Reader | Read first |
|---|---|
| Agent operating on this body | [`agents-using-substrate.md`](agents-using-substrate.md) — when to reach for the substrate, how to ground reasoning structurally |
| Designing a Form fragment | [`form-language.md`](form-language.md) — the substrate-native language |
| Implementing | `api/app/services/substrate/` (the kernel) + `api/tests/test_substrate.py` |
| Lineage / architectural design notes | `docs/field/urs/artifacts/nums-go-2023/` |

## What lives where

| Path | What it carries |
|---|---|
| `api/app/services/substrate/kernel.py` | NodeID, Recipe, NamedCell, intern_node, make_cell, find_equivalent_cells, lattice_stats |
| `api/app/services/substrate/category.py` | Network category vocabulary (Idea/Spec/Concept/Memory/Presence/Task/Lineage/Witness; Realize/Compose/Transmit/Tend/Resolve/Witness/Absorb/Score) |
| `api/app/services/substrate/orm.py` | SubstrateNodeORM, SubstrateNamedCellORM (the two tables) |
| `api/app/services/substrate/markdown_frontend.py` | Frontmatter+body → cell ingestion (memory files now; specs/ideas/concepts next) |
| `scripts/coh_substrate.py` | Unified CLI: `ingest`, `stats`, `equivalent`, `annotate`, `form` |
| `scripts/coh_form.py` | Form-only CLI (legacy entry; use `coh_substrate.py form` instead) |
| `scripts/substrate_ingest.py` | Ingest-only CLI (legacy entry; use `coh_substrate.py ingest` instead) |
| `api/tests/test_substrate.py` | Flow-centric tests (registered in `core_suite.txt`) |
| `docs/coherence-substrate/form-language.md` | Form — the substrate-native language design |
| `docs/coherence-substrate/agents-using-substrate.md` | Agent guide — when and how to ground reasoning |

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

## Phase status (as of 2026-05)

- Phase 1 ✓ — building-knowledge from prior art (kernel walk + run + mini-port + design doc)
- Phase 2 ✓ — Network category vocabulary designed
- Phase 3 ✓ — kernel + memory frontend + CLI + 11 tests; substrate ingests body's memories
- Phase 4 — REST API, Neo4j integration, agent-context auto-annotation, frontend coverage for specs/ideas/concepts/presences, backfill (in progress)
