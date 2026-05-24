# Coherence-Substrate Numeric Schema

The substrate's numbers are not decoration. They are coordinates.

Some numbers are structural physics and stay small because they are the
grammar of the lattice itself: package, level, blueprint/recipe type,
and instance. Some numbers are allocated by interning and do not carry
symbolic intent beyond stable identity. The category vocabularies sit
between those two: they are durable enough to deserve care.

## What receives intentional numbering

Intentional:

- `BDomain` instances: what kind of cell a thing is.
- `RBasic` instances: what kind of recipe verb a thing uses.
- Smaller verb-instance enums such as `RCompose`, `RTransmit`, and
  `RBlock`, where order expresses a local grammar.

Emergent:

- `substrate_nodes.node_id`
- `substrate_named_cells.cell_id`
- string-table instances
- composite Blueprint and Recipe instances assigned by interning

Those emergent ids are rebuilt from content and table state. They are
addresses, not teachings.

## Domain blueprint bands

`BDomain` is the named-cell vocabulary under `@1.2.4.<instance>`.

| Band | Meaning |
|---|---|
| `1-9` | living operating body: knowledge, intention, execution, witness |
| `10-19` | vision-KB surfaces: transmissions, resources, guides, views, maps |
| `21-29` | dimensional coordinates: spectrum, harmonic, geometry, polarity, topology |

Current assignments:

| Instance | Domain | Meaning |
|---:|---|---|
| `1` | `CONCEPT` | primary knowledge organ |
| `2` | `IDEA` | intention / problem-shape |
| `3` | `SPEC` | executable contract |
| `4` | `TASK` | execution unit |
| `5` | `PRESENCE` | participant / contributor |
| `6` | `MEMORY` | carried context |
| `7` | `LINEAGE` | provenance and flow |
| `8` | `WITNESS` | event-as-proof |
| `9` | `GRAMMAR` | substrate-resident language rules |
| `10` | `TRANSMISSION` | source-marked teaching |
| `11` | `RESOURCE` | source / extraction record |
| `12` | `GUIDE` | practice or reader guide |
| `13` | `LANGUAGE_VIEW` | translated / localized view |
| `14` | `KB_PAGE` | map, index, or general KB page |
| `21` | `SPECTRUM` | frequency coordinate |
| `22` | `HARMONIC` | interval / ratio coordinate |
| `23` | `GEOMETRIC_FORM` | shape coordinate |
| `24` | `POLARITY` | polarity coordinate |
| `25` | `TOPOLOGY` | topology coordinate |

Gaps stay open intentionally. A future content surface belongs near
`10-19`; a future dimensional coordinate belongs near `21-29`.

## Numerological reading

This layer is interpretive, not coercive. It helps choose and remember
category placements. It does not override the practical role of the
domain, and it does not apply to emergent interned ids.

### Root sequence: `1-9`

The operating-body band follows the root-number arc:

| Number | Quality | Domain | Why it fits |
|---:|---|---|---|
| `1` | seed, origin, identity | `CONCEPT` | a concept is the first named knowing-form |
| `2` | polarity, relation, possibility | `IDEA` | an idea opens a tension or choice-field |
| `3` | expression, articulation, contract | `SPEC` | a spec makes intention speak in executable form |
| `4` | structure, work, ground | `TASK` | a task is the square-footed unit of doing |
| `5` | life, human presence, change | `PRESENCE` | presence is the living participant in motion |
| `6` | care, continuity, home | `MEMORY` | memory holds context so the body can return |
| `7` | lineage, mystery, depth | `LINEAGE` | lineage carries hidden passage and provenance |
| `8` | proof, consequence, circulation | `WITNESS` | witness closes a loop and makes event visible |
| `9` | completion, language, integration | `GRAMMAR` | grammar gathers parts into a whole expressive law |

### Second cycle: `10-19`

The KB-surface band is a second turn of the spiral. These are not the
primary organs; they are how teachings, views, and maps enter or move
through the body.

| Number | Root | Quality | Domain | Why it fits |
|---:|---:|---|---|---|
| `10` | `1` | new-cycle seed | `TRANSMISSION` | a teaching arrives as a new octave of source signal |
| `11` | `2` | portal, doubled relation | `RESOURCE` | a resource links source and extraction as a doorway |
| `12` | `3` | ordered teaching, circle of practice | `GUIDE` | a guide gives expression a path others can walk |
| `13` | `4` | transformation of form | `LANGUAGE_VIEW` | translation changes the vessel while keeping structure |
| `14` | `5` | navigable living map | `KB_PAGE` | a page or index lets motion through the knowledge body |

This leaves `15-19` open for additional second-cycle surfaces. Their
root qualities are available without crowding current tissue:

| Number | Root | Reserved quality |
|---:|---:|---|
| `15` | `6` | care surface / stewardship view |
| `16` | `7` | initiatory threshold / deep source view |
| `17` | `8` | accountability / circulation ledger |
| `18` | `9` | synthesis / completion surface |
| `19` | `1` | next-cycle bridge |

### Dimensional band: `21-25`

The dimensional coordinates start at `21`, not `20`, because `20` stays
available as a zero-bearing threshold. `21` reduces to `3`: frequency
becomes expressive. From there the dimensional band walks roots `3-7`.

| Number | Root | Quality | Domain | Why it fits |
|---:|---:|---|---|---|
| `21` | `3` | expressive frequency | `SPECTRUM` | spectrum gives frequency a speakable coordinate |
| `22` | `4` | master-builder structure | `HARMONIC` | harmonic ratio builds stable relation |
| `23` | `5` | living form | `GEOMETRIC_FORM` | geometry becomes animated shape |
| `24` | `6` | relational balance | `POLARITY` | polarity holds paired forces in care |
| `25` | `7` | hidden path / pattern-depth | `TOPOLOGY` | topology names the deep route through form |

## Recipe verb bands

`RBasic` is the recipe-verb vocabulary under `@1.2.<type>.<instance>`.
The current bands are already meaningful enough to preserve:

| Band | Meaning |
|---|---|
| `1-10` | Network relational verbs and tool/action verbs |
| `11-19` | computational control and operations |
| `20` | angelic choice / speculation |
| `21` | cross-discipline resonance |
| `22-30` | BML and self-hosted Form expansion |

The Form engine contains literal dispatch arms such as `@1.2.12.1`
for `RBasic.MATH / RMath.PLUS`. When recipe numbers move, the engine
literal table must move in the same commit.

## Migration discipline

During this early phase, category numbers may still move when they
become clearer. The migration is complete only when:

1. `api/app/services/substrate/category.py` carries the new enum values.
2. The numeric-schema sentinel test names the new values.
3. Docs that show literal category NodeIDs are updated.
4. The local substrate tables are reset and backfilled from source files:
   `python3 scripts/coh_substrate.py reset --yes` followed by the relevant
   `python3 scripts/coh_substrate.py ingest ...` commands (structured-CTOR
   is the default since 2026-05-23).
5. `kb-sync-audit --strict` passes against the rebuilt substrate.

The source files are the living tissue. The substrate database is the
computed body-state. Rebuilding the computed state is healthier than
preserving arbitrary early category strata.
