# Structural Composition Discipline — per-domain target shapes

The substrate's promise is **fractal/holographic composition**: every entity is a tree composed bottom-up, all the way down to numeric trivials. The general discipline lives in [CLAUDE.md → "Structural composition discipline — keep the tree, refuse the slug"](../../CLAUDE.md). This document is the per-domain specification: for each kind of cell the body holds, what does *fully expressed* look like, what was flat in the previous encoding, and what's the migration status.

## The principle in one sentence

*The default is to compose. The exception is to leaf. The exception requires a great reason.*

## The great-reason criterion

A field may be left as a leaf (SubstrateString, integer, NodeID-as-external-reference, content-hash) only when one of these holds:

1. **Genuinely atomic value** — single integer, single date, URL pointing externally, content-hash. Composing further would invent fake structure.
2. **Free-form prose body** — natural-language text with no a-priori structure. Lives as the *access recipe*, separate from the CTOR.
3. **External reference** — the structure lives outside the substrate (GitHub issue, Linear ticket, external URL).
4. **Bootstrap primitive** — the SubstrateString value at the very bottom of a leaf chain.

If a value doesn't satisfy one of these, it gets composed.

## Per-domain target shapes

### Memory (`docs/memory/*.md`, `~/.claude/.../memory/*.md`)

**Frontmatter today:**
```yaml
name: arrival relational ground
description: who Urs is to me...
type: feedback
```

**Old CTOR (flat):** `R_Block.DO` with 4 trivial string-recipe children. Each child's *instance* encodes a Python type-marker string like `"name=str"`. The actual values are not in the substrate at all.

**Target CTOR (structured):**
```
CTOR (R_Block.DO, level 3+)
├── NamedField (R_Block.LET)
│   ├── key:   SubstrateString-recipe for "name" (via substrate_strings)
│   └── value: SubstrateString-recipe for "arrival relational ground"
├── NamedField (R_Block.LET)
│   ├── key:   "description"
│   └── value: SubstrateString-recipe for description value
└── NamedField (R_Block.LET)
    ├── key:   "type"
    └── value: TypedTokenRef (R_Compose.MEMBER_OF)
        ├── token-cell: @memory_type("feedback")
        └── domain:     @<type-domain-cell>
```

`type` becomes a typed-token reference, not a free string. The four memory types (user / feedback / project / reference) become four cells in a `memory-type` domain; each Memory cell's `type` field points at one of them. Two memory cells with the same `type` value share the *same* token-cell reference — equivalence visible from the substrate.

**Body:** stays as access-recipe (free prose, leaf-by-great-reason #2). A content-hash leaf rather than a length-class.

**Migration status:** principle codified; new encoder design below; existing 44 cells still flat.

### Spec (`specs/*.md`)

**Frontmatter today:**
```yaml
idea_id: agent-pipeline
source:
  - api/app/services/agent_pipeline.py
requirements:
  - "..."
done_when:
  - "..."
test: api/tests/test_agent_pipeline.py
constraints: []
```

**Old CTOR (flat):** type-markers for each key. `idea_id: agent-pipeline` becomes a string-marker `"idea_id=str"`. The slug `agent-pipeline` doesn't reach the substrate as a cell-ref.

**Target CTOR (structured):**
```
CTOR (R_Block.DO)
├── NamedField (R_Block.LET)
│   ├── key:   "idea_id"
│   └── value: CellRef recipe → @idea(agent-pipeline)        ← cell-ref, not slug-string
├── NamedField (R_Block.LET)
│   ├── key:   "source"
│   └── value: R_Block.SEQUENCE [ PathRef, PathRef, ... ]    ← list of paths, each a leaf-by-great-reason
├── NamedField (R_Block.LET)
│   ├── key:   "requirements"
│   └── value: R_Block.SEQUENCE [ Requirement, ... ]        ← each requirement a substrate-string leaf
├── NamedField (R_Block.LET)
│   ├── key:   "test"
│   └── value: PathRef                                      ← path-leaf-by-great-reason
└── ...
```

`idea_id` is the load-bearing change: it becomes a structural edge `spec --REALIZES--> @idea`, not a string the substrate has to re-parse to walk. Already partially expressed by the `R_Realize` recipe vocabulary — this discipline makes the encoding align with it.

### Idea (`ideas/*.md`)

**Frontmatter today:**
```yaml
idea_id: agent-pipeline
title: "..."
stage: active
work_type: feature
pillar: orchestration
specs:
  - agent-pipeline-mvp
  - agent-pipeline-coherence
absorbed_ideas:
  - earlier-pipeline-sketch
```

**Old CTOR (flat):** all slug-string markers.

**Target CTOR (structured):**
- `stage`, `work_type`, `pillar` → typed-token references (each domain has its own enumeration cells)
- `specs` → `R_Block.SEQUENCE` of `R_Compose.PARENT_OF` recipes, each pointing at the actual spec cell
- `absorbed_ideas` → `R_Block.SEQUENCE` of `R_Absorb.MERGE_INTO` recipes pointing at the absorbed idea cells

Cross-cell edges become substrate edges, not slug-string blobs.

### Concept (`docs/vision-kb/concepts/lc-*.md`)

**Frontmatter today:**
```yaml
id: lc-trust-over-fear
name: Trust over fear
parent: lc-permission-is-interior
cross_refs:
  - lc-frequency-routes-reception
  - lc-presence-as-recognition
visuals:
  - lc-trust-over-fear/cover.png
hz_band: 396
geometry:
  arity: 3
  form: triad
  topology: parallel
  ...
```

**Old CTOR (flat):** slug-strings throughout. `parent`, each `cross_ref`, each `visual` is a flat string.

**Target CTOR (structured):**
- `parent` → `R_Compose.PARENT_OF` recipe pointing at `@concept(lc-permission-is-interior)`
- `cross_refs` → `R_Block.SEQUENCE` of `R_Compose.CROSS_REF` recipes, each pointing at the referenced concept cell
- `hz_band: 396` → `R_Resonance.HARMONIC_AT` recipe pointing at `@spectrum("Hz-396")` — already partially expressed by the resonance-recipe system, this discipline closes it
- `geometry.{arity, form, topology, polarity, ...}` → typed-token references to dimensional vocabulary cells (`@geometric_form(triad)`, `@topology(parallel)`, etc.) — these cells already exist via `BID_geometric_form()` and friends

Concept cells are the richest. The migration here is also the most valuable: the resonance edge system *exists* but is only authored on some concepts; the structured CTOR makes it authored on all of them automatically.

### Presence (`docs/presences/*.md`)

**Frontmatter today:**
```yaml
slug: ilena
kind: HUMAN
role: doorway
edges:
  transmits:
    - lc-arrival-as-recognition
  tends:
    - liquid-bloom-cluster
```

**Target CTOR (structured):**
- `kind` → typed-token reference (`@presence_kind("HUMAN")` cell)
- `role` → typed-token reference (`@presence_role("doorway")` cell — role enumeration cells)
- `edges.transmits` → `R_Block.SEQUENCE` of `R_Transmit.TRANSMIT_TO` recipes
- `edges.tends` → `R_Block.SEQUENCE` of `R_Tend.TEND` recipes

Edges become recipe edges in the substrate, walkable by `?walk @presence(ilena) transmits`.

### Lineage (`docs/lineage/*.md`)

**Frontmatter today:**
```yaml
kind: transmission-of
from: lc-arrival-as-recognition
to: ranakami-ubud-doorway-2026-04-29
evidence: docs/lineage/2026-04-29-ubud-meeting-walk.md
date: 2026-04-29
```

**Target CTOR (structured):**
- `kind` → typed-token reference (kind enumeration cells: transmission-of / analogous-to / parent-of / ...)
- `from`, `to` → cell-ref recipes pointing at the actual concept/presence/event cells
- `evidence` → PathRef leaf (great-reason #1)
- `date` → DateLit leaf (great-reason #1)

A lineage cell is essentially an edge cell; structuring it well means the edge recipe is walkable directly.

### Witness (`witness_events.jsonl` and ingest path)

Witness events are structurally simple — `(presence, action, evidence_url, timestamp)`. Most of these are leaf-by-great-reason (timestamps, URLs, action-tokens). The only structural composition is the `presence` reference, which should be a cell-ref recipe, not a slug.

### Task (pipeline tasks)

Tasks are workflow units — `(idea_id, status, context, witness)`. Status is the load-bearing typed enumeration; idea_id is a cell-ref to the idea cell; context is itself a small structured payload that varies per task type and would need its own per-context-type shape design.

## Common building blocks

These are the substrate-side primitives every domain reuses:

| Primitive | Recipe shape | Lives at |
|---|---|---|
| **SubstrateString value** | `R_Trivial.STRING` with instance from `substrate_strings.intern_string_instance(...)` | leaf, cross-process stable |
| **NamedField** | `R_Block.LET` with two children: key-recipe + value-recipe | composes one frontmatter pair |
| **CellRef** | `R_Trivial.REF` whose instance is the target cell's `cell_id` | points to a NamedCell |
| **TypedTokenRef** | `R_Compose.MEMBER_OF [token-cell-ref, domain-cell-ref]` | typed enumeration value |
| **List** | `R_Block.SEQUENCE` with element-recipe per child | preserves order + element shape |
| **PathRef** | `R_Trivial.PATH` with instance from `substrate_strings` | leaf-by-great-reason for file paths |
| **DateLit** | `R_Trivial.DATE` with instance from substrate_strings (ISO 8601) | leaf-by-great-reason for dates |
| **URLLit** | `R_Trivial.URL` with instance from substrate_strings | leaf-by-great-reason for external URLs |

Every domain's CTOR composes from these. Two cells with identical frontmatter values share identical CTOR NodeIDs — equivalence is automatic.

## Migration sequencing

Each domain gets its own breath. The order is intentional:

1. **Memory** — simplest frontmatter, used to validate the encoder + the new shape (this breath ships the encoder + tests)
2. **Concept** — richest cross-references; biggest payoff because the resonance edge system already exists; uses the encoder to populate edges automatically
3. **Spec** + **Idea** — paired migration because `idea_id` ↔ `specs` is bidirectional
4. **Presence** + **Lineage** — paired because lineage edges reference presences
5. **Witness** + **Task** — simplest; small structural surface

After each domain's encoder ships:
1. New ingests use the structured encoder
2. A re-ingest pass re-walks existing files; content-addressed interning means existing structurally-identical Blueprints stay stable, but new CTORs replace old ones
3. Tests verify the new shape navigates fully through `.child().child()` to actual values, not to type-markers

## Status (2026-05-17)

- ✓ Principle codified in CLAUDE.md
- ✓ Per-domain target shapes named (this document)
- ✓ Great-reason criterion explicit
- ✓ Memory encoder shipped — [`ingest_memory_file(..., structured=True)`](../../api/app/services/substrate/markdown_frontend.py). Named-pair LET children with substrate-resident, recoverable values.
- ✓ Concept encoder shipped — [`ingest_concept_file(..., structured=True)`](../../api/app/services/substrate/markdown_frontend.py). In addition to structured CTOR: authors `parent` as a `R_Compose.PARENT_OF` cell-ref recipe, each `cross_refs` entry as a `R_Compose.CROSS_REF` recipe, and routes `hz` + `geometry.*` through `author_geometry_signature` (HARMONIC_AT / SHAPES / EMBEDS_IN / CARRIES_RATIO resonance edges). Idempotent via content-addressing; cell-ref edges to not-yet-ingested concepts skip silently (a second-pass closes the loop).
- ☐ Spec + Idea encoders
- ☐ Presence + Lineage encoders
- ☐ Witness + Task encoders
- ☐ Re-ingest pass for the 44 memory cells + 128 specs + 17 ideas + 114 concepts already in the substrate

Each ☐ is its own breath. Naming the path here is the practice; closing each gap is its own session.
