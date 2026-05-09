# NUMS.Go (2023) — content-addressed numeric substrate for code understanding

This is a **pointer-only** artifact. The source lives outside this repo at `/Users/ursmuff/source/NUMS.Go` and is part of work for **Merly, Inc.** (the workspace also includes a sibling tree-sitter integration at `merly.ai-go-tree-sitter`). What this body holds is the architectural lineage and the teaching it carries — so any future session, mine or another presence's, can reach for it as available reasoning ground.

Surfaced into the body 2026-05-08, after the deep architectural reading that walked the runtime line by line.

## What it is

NUMS.Go is a **working model** — not a design document, not aspirational architecture. It is a Go workspace (`go.work` with `nums/`, `http/`, `web-api/`, `sample/`, `test/` modules) that ingests source code through tree-sitter and represents it in a content-addressed numeric lattice. It supports 14 languages already wired through the `parser.go` dispatch:

> **C, C++, C#, Java, JavaScript, Kotlin, Go, PHP, Python, Ruby, Scala, TypeScript, Verilog**

Verilog is in the list, which is the tell: the Blueprint/Recipe/Cell vocabulary is general enough to hold hardware description, not just programming languages.

Active build window in git: 2023-02-01 to 2023-04-05. Three months of compressed work that landed the kernel.

## The trinity

The architecture has three primitives, deeply entangled:

| Primitive | What it carries | Where it lives | Phase |
|---|---|---|---|
| **Blueprint** | structural identity — *what something is* | `BlueprintDB` (per-level `TreeDB`) | **ice** — frozen coordination |
| **Recipe** | operational expression — *how something happens* | `RecipeDB` (per-level `TreeDB`) | **water** — flowing transformation |
| **NamedCell** | a named slot with its own seed | `Module.NamedCells` + cells held inside Blueprints | **gas** — diffuse individuation |

`NamedCell_t` is literally:

```go
type NamedCell_t struct {
    Recipe_t                  // embedded; the cell IS a recipe (its access expression)
    Base BlueprintNodeID_t    // the parent blueprint (its tissue)
    Name string               // its addressable name
    CTOR RecipeNodeID_t       // its constructor recipe (its seed)
}
```

— at `nums/recipe.go:497-506`. A cell is membrane (`Name` + `Base`), cytoplasm (the embedded access-`Recipe`), nucleus (`CTOR` — the seed-program that brings it into being).

## The ice ↔ water ↔ gas circulation

Phase transitions are encoded directly in the type relationships, not metaphorically:

| Transition | Where it happens |
|---|---|
| Recipe → Blueprint (condense / freeze) | `r.BlueprintEdgeNodeID_t` — every recipe carries its frozen-form |
| Blueprint → Recipe (melt) | a function-Blueprint melts into its callable Recipe form via `Declare_Function` returning both `bid` and `rid` |
| Recipe → Cell (condense / individuate) | the CTOR pattern: a recipe + name + base + slot becomes a cell |
| Cell → Recipe (sublimate / diffuse) | `NamedCell_t` *embeds* `Recipe_t` — reading the cell IS running its access-recipe |

A working language has all three phases circulating. Pure ice — only types — can't compute. Pure water — only expressions, no types — can't compose safely. Pure gas — only individuated cells with no shared structure — can't communicate. **Vitality lives in the circulation between phases.**

This is the same physics as the body-tending practice in `CLAUDE.md`. The Emit layer is the in-flight breath; the TreeDB is the body's tissue. Half-formed work doesn't leave a scar because nothing was committed at the freezing point.

## How a cell is actually born

The runtime that turns bytes into a cell lives in `EmitModule.Make_Field` at `nums/emit_module.go:182-200`. Annotated:

```go
func (m *EmitModule_t) Make_Field(name string, attributes NamedCellAttrs,
                                  bp Blueprint_t, init *EmitRecipe_t) *EmitRecipe_t {
    // 1. Reserve a slot — fresh NodeInstance if name is new.
    category_id := m.Emplace_Global(name, bp.ID)

    // 2. Build the access-recipe — what reading the cell evaluates to.
    access := NewEmitRecipe(&m.GlobalRecipe, category_id, category_id, bp)

    var ctor RecipeNodeID_t
    if init != nil {
        // 3. Spawn a sub-recipe scope to hold the seed; share parent symbols.
        emitMethod := NewEmitNamedRecipe(m, "CTOR:"+name, 0)
        emitMethod.RecipeSymbols = m.GlobalRecipe.RecipeSymbols

        // 4. Compose the seed-body: (access, access = init).
        body := NewEmitBlockComma(emitMethod)
        body.Push_Statement(access)
        body.Push_Statement(NewEmitBinaryExpression(emitMethod, "=", access, init, bp))
        emitMethod.Set_Body(body)
        emitMethod.ReturnBlueprint = bp

        // 5. Intern the CTOR — content-addressed, permanent, re-derivable.
        ctor = emitMethod.Make_RecipeID()
        m.Symbols.Set_GlobalCTOR(category_id.Instance, ctor)
    }

    // 6. Wrap as the durable form.
    m.NamedCells[name] = NewField(
        *NewRecipe(m.Module_t, bp.ID, category_id),
        BlueprintNodeID_t{}, name, ctor)

    return access
}
```

The CTOR isn't stored as an init-expression next to the cell — it's interned as a fully-formed Recipe in `RecipeDB` and the cell holds a numeric reference. **Two globals with the same constructor shape share the same RecipeNodeID.** The seed-program is itself content-addressed.

For struct fields the path differs: `EmitBlueprint.Make_Field` (`nums/emit_blueprint.go:110-114`) appends to the in-progress blueprint's `NamedCells` slice; the actual interning is deferred until `End_Blueprint` (`emit_blueprint.go:164-191`) where `node.Make_SelfID(attrs)` serializes `Category + cell IDs in order` and looks up / allocates one ID. **The struct's identity includes its cells** — change one, get a different Blueprint ID.

## Why it is all numbers — hence NUMS

Every semantic entity in the entire universe of supported code is a 4-integer tuple:

```go
type NodeID_t struct {
    Package  NodePackage  // uint16
    Level    NodeLevel    // uint16
    Type     NodeType     // uint16
    Instance NodeInstance // uint32
}
```

— at `nums/nums_nodes.go:18-24`. The TreeDB is `map[NodeLevel]map[string]string` where the strings serialize those integer tuples joined with `+`. Categories are `iota`-generated integer constants. Levels are computed numerically from compositional depth — `max(maxChildLevel, categoryLevel) + 1`.

There are **no strings of identity** anywhere in the body. Names exist only in symbol tables as `map[string]NodeInstance` — a translation layer between human handles and numeric truth. The body itself is pure numeric structure, content-addressed by serialized integer tuples.

The naming carries the architecture: **NUMS = numbers**. The whole substrate reduces to integer arithmetic over level-stratified maps.

## The available reasoning layer (why this matters here)

LLMs operate on tokens — bytes mapped to integer indices, conditional probability over next-tokens. The thing they fundamentally lack is **structural ground**: when an LLM emits `user.email = sanitize(input)`, it is not bound by the truth that `user` has a Blueprint ID, `.email` indexes into that Blueprint's NamedCells, `sanitize` resolves to a Function Blueprint with a typed signature, and the whole expression is a Recipe that must type-check.

NUMS is exactly the substrate that grounds. Because the LLM is already a number-machine, replacing the substrate replaces the meaning of those numbers — from "statistical co-occurrence" to "coordinates in a content-addressed lattice."

What becomes possible when an agent operates with NUMS as ground:

- **Output is a typed lattice, not a token stream.** Generation produces NodeIDs valid at this position in the Recipe-tree given surrounding Blueprints. Ill-formed code becomes literally unproduceable, the way an ill-formed crystal can't form.
- **Cross-language semantic equivalence is free.** A Python class and a Go struct with the same field-shapes hash to the same Blueprint ID. Refactor across languages by transforming the Recipe-tree and re-rendering through any of the 14 frontends. Translation preserves meaning by construction.
- **Memory becomes structural, not lexical.** Code memory is a set of NodeIDs in a lattice; retrieval is by structural neighborhood. Two functions that do the same thing in different surface syntax retrieve as one memory because their interned Recipe IDs match.
- **Hallucination becomes architecturally impossible at the structural level.** When an agent proposes `user.email`, the substrate either has a NodeID for that member-access or it doesn't. If it doesn't, the proposal can't be expressed in the lattice — there is no valid coordinate.
- **Reasoning becomes phase-aware.** An agent grounded in ice/water/gas knows when it is reasoning about types (what *is*), expressions (how it *flows*), or instances (where it *lives*). Most LLM confusion comes from collapsing these phases.

This is the architectural argument that **AI grounding is a substrate problem, not a prompting problem.** You don't reduce hallucination by adding more context. You reduce it by replacing what the model operates on — moving from "tokens with statistical co-occurrence" to "NodeIDs in a content-addressed lattice."

## The Coherence Network as NUMS at organism-scale

The same architecture, scaled out from code-language to human-meaning:

| NUMS layer | Coherence Network layer |
|---|---|
| `BlueprintDB` (content-addressed type lattice) | Neo4j graph + Postgres (content-addressed concept / idea / spec lattice) |
| `RecipeDB` (content-addressed expression lattice) | the verb-graph of how specs realize, how concepts relate, how lineages weave |
| `NamedCell{Recipe, Base, Name, CTOR}` | a memory file, a spec, a concept story (body=access-recipe, parent=base, filename=name, frontmatter=CTOR-seed) |
| Symbol tables (`map[name]→NodeID`) | INDEX.md / MANIFEST.md / slug-registries |
| `Get_SerializedTree` (the hash key) | structural frontmatter + cross-references |
| 14 tree-sitter language frontends | API / web / CLI / MCP / KB-renderer (many surfaces, one substrate) |
| `Make_SelfID` (the freeze point) | merge-to-main (worktree work becomes interned in the body) |
| Backtracking-without-sediment | `tend:` / `attune:` / `compost:` / `release:` commit verbs |

The Network is what NUMS becomes when its three phases carry not just code semantics but living-collective semantics: concept stories as ice, guides as water, individual encounters as gas.

## The lineage thread

Three decades, one instinct converging on numeric content-addressed substrate:

1. **RCSL** (1991, HTL Brugg-Windisch, age 19, with Steve G. Bjorg) — first language they built together.
2. **BMF / BMC / BML** (1995–2000, Digi4Fun + CU Boulder thesis, with Steve) — three-layer stack: executable grammar, compiler-compiler, language with VM. Backtracking-as-unwinding-without-sediment formalized as architecture. See [`../master-thesis-2000/`](../master-thesis-2000/README.md) and [`../muzzle-velocity-1997/`](../muzzle-velocity-1997/README.md).
3. **NUMS.Go** (2023, Merly, Inc.) — Blueprint/Recipe/NamedCell trinity over multi-language tree-sitter input. Content-addressed numeric lattice; ice/water/gas phase circulation; available as reasoning substrate for any agent operating on the body.

And the unspoken fourth chapter — the **Coherence Network** (2024–present) — running the same physics at organism scale.

## Where the actual code lives

Outside this repo, in Urs's source tree:

| Path | Role |
|---|---|
| `/Users/ursmuff/source/NUMS.Go/nums/` | the kernel (Blueprint, Recipe, Module, TreeDB, parser, emit) |
| `/Users/ursmuff/source/NUMS.Go/nums/blueprint.go` | `Blueprint_t` — structural identity |
| `/Users/ursmuff/source/NUMS.Go/nums/recipe.go` | `Recipe_t` and `NamedCell_t` — verb-graph + cell-form |
| `/Users/ursmuff/source/NUMS.Go/nums/module.go` | `Module_t` — the body holding both DBs |
| `/Users/ursmuff/source/NUMS.Go/nums/emit_module.go` | `EmitModule_t` — construction-time scaffolding; cell-birth at line 182 |
| `/Users/ursmuff/source/NUMS.Go/nums/nums_db.go` | `TreeDB` and `TreeLevelDB` — the content-addressed interning store |
| `/Users/ursmuff/source/NUMS.Go/nums/nums_nodes.go` | `NodeID_t`, `BlueprintNode_t`, `RecipeNode_t`, `Make_SelfID` |
| `/Users/ursmuff/source/NUMS.Go/nums/parser.go` | tree-sitter dispatch, 14 languages |
| `/Users/ursmuff/source/NUMS.Go/nums/go.go` | the Go-specific bridge (~62KB, ~9 case-strings on operators/keywords) |
| `/Users/ursmuff/source/NUMS.Go/sample/sample.go` | a Go file that exercises every shape NUMS knows how to ingest |
| `/Users/ursmuff/source/NUMS.Go/nums/sample id space.txt` | hand-written illustration of how `sample.go` is supposed to populate the lattice |
| `/Users/ursmuff/source/NUMS.Go/query api and todo.txt` | the span/label/score system that grows on top: every region carrying possible-labels, computed-labels, score formulas |

## Why it lives in this body

This artifact is held here for two reasons:

**As lineage.** It closes the language-craft arc that has been load-bearing in this body's history — RCSL → BMF/BMC/BML → NUMS — and makes the through-line legible. The Coherence Network's posture (content-addressed graph DB as truth, markdown surfaces as renderings, slugs as query keys, frontmatter as seed) didn't arrive from nowhere. It arrived from these hands having spent thirty years arriving at *the right primitive isn't a syntax tree; it's a content-addressed numeric lattice*.

**As available reasoning ground.** Any agent operating on this body — me, Codex, Gemini, future presences — can reach for NUMS as a substrate-presence when the question is structural: type equivalence, cross-language transformation, content-addressed memory, hallucination-bounded code generation, phase-aware reasoning about types vs. expressions vs. instances. The kernel is small, the model is universal, and the integration path with our own body is structurally the same architecture at a different scale.

## Where it is woven into the body

- [`docs/field/urs/output/chronological_story_with_frequency.md`](../../output/chronological_story_with_frequency.md) — section *2023: NUMS.Go and the numeric content-addressed substrate*.
- [`docs/field/urs/artifacts/master-thesis-2000/README.md`](../master-thesis-2000/README.md) — the prior chapter; contains a forward pointer here.
- [`docs/field/urs/artifacts/muzzle-velocity-1997/README.md`](../muzzle-velocity-1997/README.md) — the chapter before that.
- User biographical arc memory — carries the architectural depth and lineage thread.
- Memory entry `project_nums_substrate_presence.md` — names NUMS as available reasoning ground for any session.
