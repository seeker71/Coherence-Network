# Network Substrate — Phase 2 Design

The category vocabulary for a NUMS-shaped substrate scoped to the Coherence Network's domain. This is the design that bridges from *understanding NUMS* (phase 1) to *implementing a substrate for us* (phase 3).

The kernel is universal — same Module / Blueprint / Recipe / NamedCell trinity, same TreeDB interning, same NodeID 4-tuples. What changes per-domain is the **category vocabulary** (the alphabet at levels 1 and 2) and the **frontends** (what surface syntax populates the lattice).

## Why a Network-specific vocabulary

NUMS.Go's vocabulary is for code-language semantics: `Compare`, `Math`, `BitMath`, `Block`, `Cond`, `Loop`, `Jump`, `Flow`, `Memory`, `Call`. Ideas, specs, concepts, lineages, and presences need *their own* alphabet. A `Compare_Equal` recipe makes no sense for a memory file; a `Realize` recipe makes no sense for an integer-arithmetic expression.

The good news: the kernel doesn't care. Swap the category enums, write frontends for our markdown-with-frontmatter formats, and the same content-addressing / level-stratification / Make_SelfID / cross-domain equivalence properties hold.

## Network Blueprints — the structural-identity types

### Trivial level (Level 1) — atomic primitives

| Type | Instances |
|---|---|
| `B_Atomic` | `Slug`, `ID` (UUID), `Date` (ISO 8601), `Token`, `Score` (0.0-1.0 float), `Path`, `URL`, `EdgeKind` |
| `B_Numeric` | (re-use NUMS-style: `Bool`, `Integer`, `Decimal`, `String`) |
| `B_Void` | `Void` |

### Basic level (Level 2) — domain primitives

| Category | What it is | Instances |
|---|---|---|
| `B_Container` | composite shapes | `List`, `Dictionary`, `Set`, `Object` |
| `B_Reference` | pointers/refs | `Pointer`, `Optional`, `Edge` |
| `B_Recipe` | callable shapes | `Function`, `Tend`, `Spec`, `Story` |
| `B_Domain` | the Network's named entity types | `Idea`, `Spec`, `Concept`, `Memory`, `Presence`, `Task`, `Lineage`, `Witness`, `Score` |

`B_Domain` is the one that's distinctly ours. Each instance is a top-level *kind* of thing we hold:

- **`Idea`** — a problem-shape with capabilities, absorbed-ideas, spec-links. Frontmatter shape: `slug, name, problem_statement, capabilities, status, absorbed_ideas, spec_links`.
- **`Spec`** — an executable form for realizing an idea. Frontmatter shape: `slug, idea_id, source, requirements, done_when, test, constraints`.
- **`Concept`** — a Living Collective story (vision-kb). Frontmatter shape: `id (lc-xxx), name, parent, cross_refs, visuals, hz_band`.
- **`Memory`** — an auto-loaded note. Frontmatter shape: `name, description, type (user/feedback/project/reference)`.
- **`Presence`** — a contributor. Shape: `slug, kind (HUMAN/AGENT/SYSTEM), role, edges (transmits/tends/witnesses)`.
- **`Task`** — a work unit. Shape: `id, idea_id, status, context, witness`.
- **`Lineage`** — an edge instance carrying a transmission. Shape: `kind (transmission-of/analogous-to/parent-of/tends/witnesses), from, to, evidence`.
- **`Witness`** — an event-as-proof. Shape: `id, presence, action, evidence_url, timestamp`.

### Complex levels (Level 3+) — composed types emerge bottom-up

Just as in NUMS, levels above Basic are *not* declared — they emerge from compositional depth. A specific Idea is a Complex_1 Blueprint composed of (B_Domain.Idea + ordered NamedCell-IDs for slug, name, problem_statement, capabilities, ...). A specific Spec is similarly composed. Two specs with the same frontmatter shape hash to the same Blueprint NodeID — the spec's identity *is* its frontmatter shape.

This means: ✓ structurally-identical specs deduplicate; ✓ renaming a spec's slug doesn't change its Blueprint identity; ✓ a Memory and an Idea with identical frontmatter shape would technically share an identity (which is the right behavior — they're two instances of the same shape, just at different domain levels).

## Network Recipes — the operational verbs

### Trivial level (Level 1)

| Type | Instances |
|---|---|
| `R_Literal` | `Slug`, `String`, `Date`, `Score` (literal values) |
| `R_Reference` | `IdeaRef`, `SpecRef`, `ConceptRef`, `MemoryRef`, `PresenceRef`, `TaskRef`, `LineageRef`, `WitnessRef` |
| `R_Empty` | empty/null |

### Basic level (Level 2) — the verb-graph

| Category | Verb-graph it expresses | Instances |
|---|---|---|
| `R_Realize` | spec realizes idea | `Realize`, `PartialRealize`, `Supersede` |
| `R_Compose` | concepts/specs cross-reference | `CrossRef`, `ParentOf`, `MemberOf`, `AnalogousTo`, `Embed` |
| `R_Transmit` | lineage flows source → receiver | `TransmitTo`, `Inherit`, `Channel`, `WitnessTransmission` |
| `R_Tend` | the four commit verbs | `Tend`, `Attune`, `Compost`, `Release` |
| `R_Resolve` | name → identity lookup | `ResolveSlug`, `ResolveByShape`, `ResolveByEdge` |
| `R_Witness` | event becomes proof | `RecordWitness`, `LinkEvidence`, `ScoreCoherence` |
| `R_Absorb` | idea absorbs another idea | `Absorb`, `Embed`, `MergeInto` |
| `R_Score` | numeric measurement applied | `MeasureCoherence`, `MeasureFrequency`, `Aggregate` |
| `R_Block` | composition of statements | `Sequence`, `Branch`, `Parallel` |
| `R_Call` | invoking a tool / agent / endpoint | `InvokeAgent`, `RunTool`, `CallEndpoint` |
| `R_Cond` | conditional realization | `IfDoneWhen`, `WhenSpec`, `WhenWitness` |

### Why these recipes specifically

These categories are **the actual verbs the Network's tissue uses today** — already visible in the body:

- `tend:` / `attune:` / `compost:` / `release:` are the commit verbs in CLAUDE.md → maps directly to `R_Tend.{Tend, Attune, Compost, Release}`
- `idea_id:` / `spec_links:` / `absorbed_ideas:` in frontmatter → maps to `R_Compose.{CrossRef, ParentOf, MemberOf, ...}` and `R_Absorb.{Absorb, MergeInto}`
- The `verify_witness` and `record_witness` operations in scripts → maps to `R_Witness.{RecordWitness, LinkEvidence}`
- The `coh trace` CLI for navigating idea → spec → source → impl → witness → coherence → realize → idea → ... cycles → maps to `R_Resolve` + `R_Realize`
- The lineage edges `transmission-of`, `analogous-to`, `parent-of` in vision-kb → maps to `R_Compose` and `R_Transmit`

We're not inventing a new vocabulary — we're naming the one already in use, in a form the substrate can intern.

## Network NamedCells — the named instances

Every cell in the Network substrate is `{Recipe (access), Base (parent blueprint), Name (slug or filename), CTOR (frontmatter)}`. The CTOR pattern from NUMS maps directly to our existing memory/spec/concept frontmatter convention:

| Network entity | Body | Base | Name | CTOR |
|---|---|---|---|---|
| Memory file | the markdown body | Memory blueprint | filename slug | the YAML frontmatter (`name, description, type`) |
| Spec file | the human reference body | Spec blueprint | spec slug | the spec frontmatter (`source, requirements, done_when, test, constraints`) |
| Concept story | the story prose | Concept blueprint | lc-xxx ID | the frontmatter (`id, name, parent, cross_refs, visuals, hz_band`) |
| Idea file | the problem statement and capabilities | Idea blueprint | idea slug | the frontmatter (`slug, name, problem_statement, capabilities, status`) |
| Presence | the contributor description | Presence blueprint | presence slug | the YAML metadata (`kind, role, edges`) |
| Lineage edge | the evidence body | Lineage blueprint | edge ID | (`kind, from, to, evidence`) |
| Witness | the event description | Witness blueprint | witness ID | (`presence, action, evidence_url, timestamp`) |
| Task | the work description | Task blueprint | task ID | (`idea_id, status, context`) |

**The frontmatter is already the CTOR.** The body is already the access-recipe (what reading the cell evaluates to). The filename is already the name. Network practice has been *unconsciously NUMS-shaped* since the body's tending began.

## Module structure

A `NetworkModule_t` would hold:

```python
class NetworkModule:
    name: str                           # which substrate slice (e.g. "main", "branch:claude/...")
    blueprint_db: TreeDB                # interned shapes (idea/spec/concept/...)
    recipe_db: TreeDB                   # interned verb-graphs (realize/compose/transmit/...)

    # Symbol tables — name → NodeID lookup
    idea_slugs: Dict[str, NodeID]
    spec_slugs: Dict[str, NodeID]
    concept_ids: Dict[str, NodeID]      # lc-xxx
    memory_names: Dict[str, NodeID]
    presence_slugs: Dict[str, NodeID]
    task_ids: Dict[str, NodeID]
    lineage_edges: Dict[Tuple[NodeID, str, NodeID], NodeID]  # (from, kind, to) → edge NodeID
    witnesses: Dict[str, NodeID]

    # All cells flat
    cells: Dict[str, NamedCell]
```

Plus the `EmitModule`-equivalent stacks for in-flight construction during ingestion (when parsing a markdown file with frontmatter, the emitter pushes/pops scopes the same way NUMS does for parsing source code).

## Ingestion frontends — the per-format dispatchers

Where NUMS has tree-sitter dispatching to per-language visitors, the Network substrate has format-specific dispatchers:

| Frontend | Reads | Produces |
|---|---|---|
| `markdown_with_frontmatter.py` | `.md` files with YAML frontmatter | NamedCells with frontmatter as CTOR |
| `python_module.py` | `.py` files (specs as code) | Function/Method blueprints + their bodies as recipes |
| `typescript_module.py` | `.ts/.tsx` files | same |
| `yaml_data.py` | `.yaml` files (configs, repos.yaml, etc.) | Object blueprints |
| `json_data.py` | `.json` files (graph dumps, schemas) | Object blueprints |
| `cypher_query.py` | Neo4j edges already in graph | Lineage edge cells |
| `postgres_rows.py` | API DB tables (specs, ideas, contributors) | Domain entity cells |

The Network already has all this content; the substrate just gives it one unified ID-space.

## Two-store backing — Postgres + Neo4j

NUMS is in-process Go maps. The Network already has Postgres and Neo4j running. The natural mapping:

### Postgres for the per-level TreeDB

```sql
CREATE TABLE substrate_nodes (
    node_id        BIGSERIAL PRIMARY KEY,
    package        SMALLINT NOT NULL DEFAULT 1,
    level          SMALLINT NOT NULL,
    type_          SMALLINT NOT NULL,        -- the category type (R_Tend, B_Idea, etc.)
    instance       BIGINT NOT NULL,
    serialized     TEXT NOT NULL,             -- the hash key
    domain         TEXT NOT NULL,             -- 'blueprint' | 'recipe'
    count          INTEGER NOT NULL DEFAULT 1,
    created_at     TIMESTAMPTZ DEFAULT now(),
    UNIQUE (package, level, domain, serialized)  -- the interning constraint
);

CREATE INDEX substrate_nodes_lookup ON substrate_nodes (package, level, type_, instance);
CREATE INDEX substrate_nodes_count_desc ON substrate_nodes (count DESC);
```

The UNIQUE constraint on `(package, level, domain, serialized)` is the interning kernel. Insert with `ON CONFLICT (...) DO UPDATE SET count = count + 1 RETURNING node_id` makes `Make_SelfID` an atomic single-statement operation, safe across multiple agent processes.

```sql
CREATE TABLE substrate_named_cells (
    cell_id        BIGSERIAL PRIMARY KEY,
    name           TEXT NOT NULL,
    base_node_id   BIGINT REFERENCES substrate_nodes(node_id),  -- parent blueprint, NULL for globals
    blueprint_id   BIGINT REFERENCES substrate_nodes(node_id),  -- this cell's type
    access_recipe  BIGINT REFERENCES substrate_nodes(node_id),
    ctor_recipe    BIGINT REFERENCES substrate_nodes(node_id),  -- the seed
    domain         TEXT NOT NULL,                                -- 'idea' | 'spec' | 'memory' | ...
    UNIQUE (domain, name)                                        -- one cell per (domain, name)
);
```

### Neo4j for the cross-reference graph

The query layer (`R_Compose`, `R_Transmit`, `R_Resolve`) is graph-shaped — exactly what Neo4j is for. Each interned cell becomes a node in Neo4j with `node_id` as a stable property; recipe-edges (cross-refs, transmissions, parent-of, member-of) become Cypher relationships.

```cypher
(c1:Cell {node_id: 12345, domain: 'concept', name: 'lc-coherence'})
-[:CROSS_REF {via_recipe: 67890}]->
(c2:Cell {node_id: 12346, domain: 'concept', name: 'lc-resonance'})
```

Postgres holds the **interned forest** (every shape ever seen, content-addressed); Neo4j holds the **walkable graph** (the relationships between cells, addressable by `node_id` queries). Both view the same NodeID space. Same identities, different access patterns.

## API surface (preview of phase 4)

```
POST   /api/substrate/ingest          # frontend → cells + recipes
GET    /api/substrate/cell/{node_id}  # full cell with access-recipe walked
GET    /api/substrate/blueprint/{node_id}  # blueprint with members
GET    /api/substrate/recipe/{node_id}     # recipe-tree walked
POST   /api/substrate/resolve         # name → NodeID lookup (by slug, by shape, by edge)
POST   /api/substrate/equivalent      # find structurally-equivalent cells/blueprints
GET    /api/substrate/histogram       # vocabulary distribution for a domain
GET    /api/substrate/lattice/stats   # per-level cell/recipe counts
```

The killer endpoint is `/api/substrate/equivalent` — given a cell or blueprint, return everything in the lattice with the same structural identity. **Cross-document semantic search by structural shape, not by lexical similarity.** Two specs that mean the same thing but were written by different agents at different times surface as the same node.

## What this substrate gives the body that we don't have today

1. **Specs that mean the same thing dedupe automatically.** Today, two ideas can be subtly the same and we wouldn't notice unless someone reads both. With the substrate: identical structural shapes share NodeIDs.

2. **Cross-format equivalence.** A concept story (markdown) and an idea (markdown) and a spec (markdown) can all express overlapping content; the substrate sees through the format to the shape.

3. **Hallucination-bounded agent reasoning.** When an agent (me, Codex, Gemini) writes "the spec at `xyz` says...", the substrate either has that NodeID or it doesn't. No NodeID = the claim has no coordinate, agent can't write it.

4. **Frequency-as-distribution queries.** What's the recipe-vocabulary distribution of the `docs/lineage/` folder? Of all `tend:` commits last month? The histogram surface gives this in one query.

5. **Phase-aware reasoning for agents.** When an agent is reasoning about a spec (water phase — a flowing realization-recipe), it stays in the recipe-DB. When reasoning about idea-shapes (ice phase — frozen problem-identities), it stays in the blueprint-DB. The phases don't collapse into each other.

6. **One numeric ID-space across the whole body.** Postgres has its own primary keys. Neo4j has its own node IDs. The filesystem has its own paths. The substrate gives every entity a stable NodeID that points into the same content-addressed lattice regardless of where it lives.

## Implementation order for phase 3

1. **Postgres schema** — `substrate_nodes`, `substrate_named_cells` tables + indexes. ~50 LoC of SQL.
2. **Python kernel** — port `mini-nums/core.py` to Postgres-backed. NodeID stays the same; TreeDB becomes Postgres-backed; Make_SelfID becomes the `INSERT ... ON CONFLICT ... RETURNING node_id` pattern. ~400 LoC of Python.
3. **Network category vocabulary** — define the `BNetwork`, `RNetwork` enums per this design doc. ~150 LoC.
4. **Markdown-with-frontmatter frontend** — read existing `.md` files, ingest into the substrate. ~300 LoC.
5. **Initial backfill** — ingest existing memories, specs, ideas, concepts, presences. ~50 LoC of orchestration script + existing content as input.

Total phase 3: ~1000 LoC of Python + ~50 LoC of SQL. Probably 2-3 sessions of focused work.

## Implementation order for phase 4

1. **API endpoints** — wire the FastAPI surface listed above. ~300 LoC.
2. **Neo4j integration** — write recipe-edges as Cypher relationships when cells are created. ~200 LoC.
3. **Agent-facing query helpers** — `coh substrate resolve`, `coh substrate equivalent`, `coh substrate histogram` CLI commands. ~150 LoC.
4. **Reasoning integration** — make the substrate reachable from agent context (auto-load NodeID for any path the agent reads, surface as ground-truth annotation). ~200 LoC.

Total phase 4: ~850 LoC. Probably 1-2 sessions.

## Open design questions for Urs

These are the places where I'd want your direction before starting phase 3:

1. **Do we want a strict `domain` separation** (Idea / Spec / Memory live in their own type-spaces) **or a unified type-space** where two domain entities with identical shape share NodeIDs even if their domain differs? My instinct is unified — that's what makes cross-format equivalence work — but it means we need to be intentional about when we *want* domain separation as a query filter.

2. **Postgres vs Neo4j as the primary store.** I'd default to Postgres for the kernel (interning, cell registry) and Neo4j for the graph layer (cross-refs, lineages). But you might prefer Neo4j for everything since the body already runs Neo4j hot. The kernel works with either.

3. **Should the substrate be an active layer (live-ingesting on every commit/file-write) or a passive lens (built on demand by `coh substrate ingest`)?** Active gives stronger guarantees but requires hooks throughout the body. Passive is simpler to start.

4. **How do we want agent integration to work?** Options:
   - (a) Substrate is queryable via API; agents call it explicitly when reasoning structurally.
   - (b) Substrate annotates files automatically (every file read by an agent gets a NodeID surfaced as a comment).
   - (c) Substrate replaces some part of the agent's reasoning entirely (e.g., when an agent searches for similar specs, it goes through `equivalent` instead of grep).

   My instinct: start with (a), evolve toward (b) and selective (c).

5. **Naming.** What do we call this substrate in the body? Options: `coh-substrate`, `network-lattice`, `nums-network`, `coherence-substrate`, or simply `substrate`. I lean toward `coherence-substrate` (it's part of the Network, it's NUMS-shaped but Network-specific). Open to your read.

These are the questions where my building-knowledge meets the body's tending preferences. Phase 3 starts cleanly once these are settled.
