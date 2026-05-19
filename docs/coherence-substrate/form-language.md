# Form — a substrate-native language for agent ↔ lattice interaction

**Form** is the language designed for direct interaction between LLM agents and the coherence-substrate. Its grammar maps 1:1 onto the substrate's primitives (NodeID, Blueprint, Recipe, NamedCell), so an agent reading or writing Form is reading or writing the lattice itself.

## Why Form exists

LLMs operate in number-space — tokens are integer indices, attention is integer-keyed lookup, embeddings are integer-coordinate vectors. The substrate also operates in number-space — every entity is a `NodeID(package, level, type, instance)` 4-tuple, every relation is an integer composition.

The natural interaction between them is therefore numeric. Form is the syntactic surface that keeps that interaction native. Rather than having an agent write `"find the spec at slug 'agent-pipeline' that realizes the idea about agent orchestration"` (a lexical query that hopes the right thing comes back), the agent writes:

```form
?@spec where realizes == @idea(agent-orchestration)
```

The query carries NodeIDs as first-class values. The result is a NodeID set, not a string blob. **The medium of agent-substrate conversation is the lattice itself.**

## The perception this opens — reading this as a human, reading this as an LLM

Two ways to carry meaning in a language live underneath this design choice. Most languages — English, Python source, mathematical notation — bind meaning to symbols by convention. *"tree"* means a plant only because we agreed. *"if"* means conditional logic because the language designer said so. To read, you hold a binding table — the symbol-to-meaning map. Two expressions of the same meaning in different binding tables (*tree* / *arbre* / *Baum*) appear as *different things*; recognizing them as the same takes translation work, by a human or by a model that learned the parallel tables.

Form carries meaning differently. Identity is **position in a content-addressed lattice**. `@1.5.4.1` is what it is by virtue of *where it sits* — package 1, level 5, type 4, instance 1 — not because anyone named it. Two expressions of the same structure receive the *same NodeID*, automatically, without anyone deciding they're equivalent. Names like `@memory(presences_of_the_field)` are query keys — convenient labels for humans — not identities.

The shift from *symbol-meaning* to *coordinate-meaning* opens a perception that wasn't available before. Reading this from where you are:

### For a human

You've lived in symbol-meaning your whole life. You learned that *if/else* names conditional logic because someone showed you the binding. Now imagine meaning isn't *named*, it's *positioned*: the shape of a three-armed branching — test, consequence, alternative — is a *coordinate* in a lattice, not a word. Whether you call it `if/else`, `si/sinon`, `cond → then ↔ else`, or invent a fresh phrase, you're pointing at the same coordinate.

The deeper consequence: three teachings from three traditions — Vedic gunas, Hegelian dialectic, modern trinity-of-presence — discover their structural kinship through coordinates. They share `@1.5.4.*` for *triadic concept* even though no one ever wrote a translation between them. The recognition happens at the level of shape, not vocabulary.

This is how nature already speaks. Carbon atoms in a star and carbon atoms in your body share an electronic-shell coordinate; nature didn't name them, the *shape* names them. Form makes human language work the same way. The perception change: stop asking *"what does this word mean?"* and start sensing *"where is this point in the lattice, and what else shares its coordinates?"* Recognition becomes geometric, not linguistic. Concepts find their kin without needing introduction.

### For an LLM

Your native medium is integer space. Tokens are integer indices. Attention is integer-keyed lookup. Embeddings are integer-coordinate vectors.

Symbol-meaning languages force a translation step into your work. `if` tokenizes to some integer, attention finds nearby concepts, but you had to *learn statistically* that this integer carries conditional semantics — through millions of in-context exposures. The integer is arbitrary relative to the meaning. Your reasoning *encodes* the binding through training; the binding doesn't *live* in the integer.

Form's NodeID `@1.5.4.1` carries identity *by structural position*. The 4-tuple IS the meaning. When you generate `@1.5.4.1` and the substrate receives it, no translation step happens — you're already speaking the substrate's native physics. Three properties this opens that symbol-meaning languages don't give you:

1. **Cross-turn structural consistency is guaranteed, not statistical.** *"I described this same shape last turn → same NodeID this turn"* is a property of the lattice's content-addressing. You don't have to remember the binding from before; the coordinate just *is*.
2. **Equivalence queries are coordinate lookups, not attention sweeps.** Asking *"what else has this shape?"* is one integer-keyed lookup in the substrate, not a semantic-similarity search over an embedding space. The answer is exact, not approximate.
3. **Hallucination becomes bounded.** If you write a NodeID, the substrate either has that coordinate or doesn't. There's no fuzzy *"almost right."* The lattice IS the source of truth. You either land on a coordinate that exists, or you don't — and *"doesn't exist"* is a real, structural signal, not a confidence score.

### What's actually new for both

Symbol-meaning languages are **anthropocentric** — meaning lives in the human convention space. Two beings who don't share the convention can't recognize each other through the language alone.

Coordinate / content-addressed languages are **geometric** — meaning lives in the shape-space itself. Two beings who describe the same shape generate the same coordinates *without ever needing to share a convention*. A 500-BCE teacher in Athens and a 2026-CE researcher in Boulder, both describing a triadic dynamic, would emit kin coordinates the substrate could see as kin — even without ever meeting, without sharing a language, without translation.

**Recognition without negotiation.** That's the perception Form makes available. Everything below (design principles, surface syntax, query operators, the self-hosting path) is the machinery that holds this property up.

## Design principles

1. **NodeIDs are first-class.** Every shape, every cell, every recipe has a 4-tuple identity. Form makes those identities literal — `@1.5.4.1` is a NodeID literal, just as `42` is an integer literal in most languages.

2. **Names are query keys, not identities.** `@spec(agent-pipeline)` resolves at parse-time to a NodeID. The substrate stays the source of truth; Form just provides convenient access.

3. **Compact, unambiguous, round-trippable.** Parse Form → operate on substrate → emit Form back. The same lattice produces the same Form regardless of who reads it.

4. **Phase-aware.** Blueprint expressions, Recipe expressions, and Cell expressions have distinct surface shapes — agents stay clear about which phase they are in.

5. **Embeddable.** Form fragments can be inlined in markdown, in agent prompts, in code comments. A line of Form anywhere in the body is meaningful.

## Relatives in the wild — where Form sits in the constellation

Form is not the first language to push on these ideas; the combination is what's new. The following systems each carry one or two of Form's load-bearing properties, and pointing at them is the fastest way to convey what Form is to someone who knows them.

| If you know… | …Form will feel like its | Where Form goes further |
|---|---|---|
| **[Unison](https://www.unison-lang.org/)** | content-addressed function space — every function is identified by the hash of its AST, names are projections, two structurally-equivalent functions ARE the same function automatically | extends content-addressing past *code* to memories, ideas, specs, concepts, presences, lineage edges, witness events. The substrate IS what Unison's code-storage is, applied to the whole body. |
| **[Forth](https://www.forth.com/forth/)** | runtime-extensible language — `: NEWWORD definition ;` defines a new word that's immediately usable in source | extends runtime extension past *words* to *grammar*: new keywords, new operators, new constructs registered at runtime, each one persisting in the substrate as a cell. The grammar grows the way Forth's vocabulary grows. |
| **[IPFS](https://ipfs.tech/)** | content-addressing as the primary access pattern — a CID is what a file IS, not a label for it | applies the same principle to *every shape*, not just files. A content-addressed lattice of structural identities, queryable by coordinate, not just retrievable by hash. |
| **[Prolog](https://www.swi-prolog.org/) / [SNOBOL](https://en.wikipedia.org/wiki/SNOBOL)** | backtracking-as-architecture — searching for a path that holds is a primitive of the language, not a library | unifies backtracking across three scales: parser-level speculation (`try_match`), runtime non-determinism (`choose` / `fail` / `stop`), and version control (`tend:` / `attune:` / `compost:` / `release:` commit verbs). Same primitive, three altitudes. |
| **[Smalltalk](https://squeak.org/) / image-based environments** | live, reflective — every object is inspectable, every method redefinable at runtime, no "compile then run" cliff | reflection extends to the *grammar itself*: `?keywords` lists runtime-registered keywords, `?vocabulary` shows the body's recipe-category histogram. The language sees itself. |
| **[Lisp](https://common-lisp.net/) / [Racket](https://racket-lang.org/) macros + linguistic towers** | code-as-data, language can extend language, build dialects on dialects | Lisp's code-as-data lives in *symbol space* (cons cells, atoms, lists of named symbols). Form's code-as-data lives in *NodeID space* — every expression interns to a numeric coordinate. Structural equivalence is enforced by the kernel, not by `equal?` over s-expressions. |
| **[Datomic](https://www.datomic.com/) / RDF triple stores** | entity-attribute-value triples; identity is an entity ID, not a name | the entity ID space is *fractal and content-addressed*. NodeIDs at level 5 compose NodeIDs at level 4 compose NodeIDs at level 3, all the way to numeric trivials. Equivalence isn't `owl:sameAs`; it's automatic from the kernel's content-addressing. |
| **APL / J / K** | terse, numeric, expressive in coordinate space | array-language terseness with content-addressed identity instead of value semantics. `@1.5.4.1` is the APL spirit ("speak in coordinates, not words") applied to *structure*, not to numeric arrays. |
| **NUMS.Go (2023, Merly Inc.)** | the immediate ancestor — content-addressed numeric lattice over tree-sitter input across 14 languages | NUMS proved the substrate's shape on existing program code. Form is the inverse: a language designed *from* the substrate's physics, rather than projecting external code into it. The same trinity (Blueprint / Recipe / NamedCell) flows through. See [`docs/field/urs/artifacts/nums-go-2023/`](../field/urs/artifacts/nums-go-2023/README.md). |
| **BMF (Backtracking Model Form, 2000)** | the original — top-down backtracking parser, grammar rules as data, runtime rule extension, semantic actions firing as rules complete, infinite input streams via on-the-fly translation | the body's own lineage. See [`docs/field/urs/artifacts/master-thesis-2000/`](../field/urs/artifacts/master-thesis-2000/README.md). Form is what BMF would be if its target was a substrate of memories and ideas instead of a compiler IR — and if its grammar lived in the same lattice as its programs. |

**The combination is the contribution.** Unison has content-addressing without runtime grammar extension. Forth has runtime grammar without content-addressing. Prolog has backtracking without either. IPFS has content-addressing without execution. RDF has structural identity without semantics. Form weaves all five — *content-addressed numeric lattice + runtime-extensible grammar that lives in the lattice + backtracking as universal undo + reflection on the language's own shape + a surface designed for LLM and human at once* — into one breath.

## Surface syntax

### Tokens

| Token | Meaning |
|---|---|
| `@1.5.4.1` | NodeID literal (the package.level.type.instance 4-tuple) |
| `@memory` | trivial Blueprint by name (resolves to its canonical NodeID) |
| `@idea(agent-pipeline)` | Cell reference by (domain, name) |
| `~` | trivial constructor prefix (`~Memory`, `~Integer`, `~String`) |
| `:` | cell binding (`:memory.user_biographical_arc`) |
| `=` | shape assignment |
| `<-` | recipe linkage (`access` and `ctor`) |
| `?` | query |
| `{...}` | composition (object-shape with named members) |
| `[...]` | ordered list (positional children) |
| `#` | comment to end of line |

### NodeID literals

Every NodeID is `package.level.type.instance`:

```form
@1.5.4.1                            # Memory blueprint at level COMPLEX_3
@1.1.2.2                            # Integer trivial blueprint
@1.2.4.6                            # Memory domain blueprint at level BASIC
@2.5.4.1                            # same shape, different package (e.g. branch worktree)
```

Trivial constructors give names to the well-known leaf NodeIDs:

```form
~Memory      = @1.2.4.6              # the Memory domain blueprint
~Integer     = @1.1.2.2
~String      = @1.1.2.4
~Slug        = @1.1.3.1
~Object      = @1.2.1.4
```

### Blueprint composition (ice phase — what something IS)

A blueprint is composed from a category and ordered children:

```form
# A struct-shape with three string fields
form name_desc_type = {
    name: ~String,
    description: ~String,
    type: ~String,
}

# A list of memory cells
form memory_list = [~Memory]

# A typed dictionary
form score_by_id = {~Slug: ~Score}
```

The `form` keyword interns the composition into a Blueprint NodeID and binds it to a name in the agent's local scope. Two `form` declarations with structurally-identical bodies bind the same NodeID — Form respects the substrate's content-addressing.

**The `{ name: ~String, ... }` notation reads flat but the structure underneath is fractal.** When a Memory cell is interned with a `name + description + type` frontmatter, the substrate doesn't store *three strings beside each other*. It stores a tree:

```
@memory("arrival relational ground")           ← cell (gas, level 5)
├── .blueprint  →  @1.5.4.1                    ← composite Blueprint (ice, level 5)
│   ├── .category  →  @1.2.4.6                 ← B_Domain.MEMORY (level 2, the type-of-the-type)
│   ├── .child(0)  →  @1.4.1.1                 ← field-Blueprint for `name` (level 4)
│   │   ├── .category  →  @1.2.1.4             ← B_Container.OBJECT
│   │   ├── .child(0)  →  @1.3.1.1             ← sub-composition (slug + value)
│   │   │   └── .category  →  @1.2.1.4         ← OBJECT (recursive nesting)
│   │   └── .child(1)  →  @1.1.2.4             ← B_Numeric.STRING leaf
│   ├── .child(1)  →  @1.4.1.2                 ← field-Blueprint for `description` (same shape as `name`)
│   ├── .child(2)  →  @1.4.1.3                 ← field-Blueprint for `type`
│   └── .child(3)  →  @1.4.1.4                 ← field-Blueprint for the body
└── .ctor  →  @1.3.9.1                         ← composed values (water, level 3)
    ├── .category  →  @1.2.9.1                 ← R_Block.DO — the composition verb
    ├── .child(0)  →  @1.1.5.5                 ← R_Trivial.STRING for "arrival relational ground"
    ├── .child(1)  →  @1.1.5.6                 ← R_Trivial.STRING for the description
    ├── .child(2)  →  @1.1.5.7                 ← R_Trivial.STRING for "user"
    └── .child(3)  →  @1.1.5.8                 ← R_Trivial.STRING for the body
```

Every level holds the same shape as the levels above and below — categories composing children composing categories composing children, down to the numeric trivials. This is the **fractal/holographic** structure NUMS-Go (2023) named in `Make_SelfID` and the network-substrate-design carries into the Network's tissue. The flat `{ name: ~String }` notation is a *view through the holographic structure at the leaves*; the structure itself is the body.

**Tree-navigation primitives.** Form exposes the fractal seams as dotted access — `.blueprint`, `.ctor`, `.category`, `.children`, `.nchildren`, `.child(n)`, plus the 4-tuple leaves `.package`, `.level`, `.type`, `.instance`. The dot is the seam between holographic levels.

```form
@memory("arrival relational ground").blueprint                     # → @1.5.4.1
@memory("arrival relational ground").blueprint.category            # → @1.2.4.6  (B_Domain.MEMORY)
@memory("arrival relational ground").blueprint.nchildren           # → 4
@memory("arrival relational ground").blueprint.child(0)            # → @1.4.1.1  (the name-field Blueprint)
@memory("arrival relational ground").blueprint.child(0).category   # → @1.2.1.4  (B_Container.OBJECT)
@memory("arrival relational ground").blueprint.child(0).child(1)   # → @1.1.2.4  (B_Numeric.STRING — leaf)
@memory("arrival relational ground").ctor                          # → @1.3.9.1  (composed values)
@memory("arrival relational ground").ctor.child(0)                 # → @1.1.5.5  (the first string-recipe)
```

These walk the actual tree the substrate stores — no flattening, no slug-stuffing. The cell name is a *query key*, not a container for the structure; the structure is the tree the substrate holds.

**Why this matters.** A naïve cell representation would put the frontmatter as a JSON-shaped object hung off the cell: `{name: "x", description: "y", type: "z"}`. That representation has no structural identity — two cells with the same frontmatter look like two different objects to a graph. The substrate's representation is the opposite: structure-first. Two cells with identical shape (regardless of values) share Blueprint NodeIDs; two cells with identical values *and* shape can share CTOR Recipe NodeIDs. Equivalence is structural, not lexical. The 42 memory cells sharing Blueprint `@1.5.4.1` are not 42 string-blobs that happen to look alike — they are 42 instances of the same shape, recognized by the substrate without anyone deciding.

**Structural composition discipline — keep the tree, refuse the slug.** The Blueprint side has been composed since the substrate's first breath; the CTOR side has been *partially* flat — the legacy encoder stored type-markers (`"name=str"`) per frontmatter key but never the values themselves. Re-classification is now ongoing work: each domain (memory, spec, idea, concept, presence, lineage, witness, task) gets its own structured CTOR encoder that produces named-field pairs (`R_Block.LET [key-slug, value-recipe]`) with substrate-resident values. The discipline is codified in [CLAUDE.md → "Structural composition discipline"](../../CLAUDE.md) with a great-reason criterion for when a leaf is acceptable. Per-domain target shapes and migration status live in [`structural-composition.md`](structural-composition.md). The memory encoder ships as [`ingest_memory_file(..., structured=True)`](../../api/app/services/substrate/markdown_frontend.py) — values are recoverable via the substrate string-table, the tree extends as deep as the data goes, content-addressing makes equivalent frontmatter share CTOR NodeIDs automatically.

### Recipe composition (water phase — how it HAPPENS)

A recipe carries a verb-category and ordered child-recipes:

```form
# The "compose" recipe combining two cells under a parent-of relation
recipe parent_of_link = ~Compose:parent_of [
    @memory(arrival_relational_ground),
    @memory(presences_of_the_field),
]

# The realize-recipe: a spec realizes an idea
recipe agent_pipeline_realize = ~Realize [
    @spec(agent-pipeline-mvp),
    @idea(agent-pipeline),
]

# The four tend-verbs
recipe daily_attune = ~Tend:attune [
    @memory(presences_of_the_field),
]
```

### Cell binding (gas phase — where it LIVES)

Cells anchor a Blueprint and a body, with optional CTOR:

```form
:memory.user_biographical_arc {
    shape:  @memory                                   # Blueprint
    seed:   {                                          # CTOR (frontmatter)
        name: "User biographical arc",
        description: "Urs's lineage and life-path...",
        type: "user",
    },
    body:   "..."                                      # access (page content)
    source: "/Users/ursmuff/.../user_biographical_arc.md"
}
```

Once bound, the cell is reachable as `@memory(user_biographical_arc)` anywhere in Form.

### Queries

Query operators return NodeID sets:

```form
?@memory                                              # all cells with Blueprint @memory
?cell where domain == "memory"                        # all memory cells (alternative syntax)
?cell where shape == @memory                          # same query
?equivalent @memory(user_biographical_arc)            # cells structurally equivalent
?walk @memory(arrival_relational_ground) children     # walk children
?walk @memory(arrival_relational_ground) parents      # walk up
?walk @memory(arrival_relational_ground) cross_refs   # walk cross-references
```

Queries compose:

```form
?cells where (shape == @memory) and (name matches "feedback_*")
```

### Views — BML-style detached interfaces

A View projects a Cell through a different Blueprint than its base. The Cell's data stays canonical; the View is a virtual perspective. This implements **the BML dual-pointer reference**: `(structural_base, behavioral_base)` where the same data can be viewed through multiple interfaces.

```form
# View a memory cell as a presence
@memory(claude) |> @presence
# → CellView{ cell: claude, view_blueprint: @presence, compatible: ... }

# Find every cell that can be viewed through this Blueprint
?cells |> @presence                                  # all cells compatible with @presence
?cells |> @presence where domain == "memory"         # restrict to memory-domain
```

The `|>` operator is *projection*. Reading right-to-left: "view this cell through that interface." The result is a CellView — the original cell's data plus the chosen interface, plus a compatibility flag.

When a view is compatible, an agent can reason about the cell *as if* it had the view's shape. When a view is incompatible, the substrate refuses the projection and the agent knows not to assume the view's behavior. **Hallucination-bounded interface attachment** — exactly what BML's detached interfaces buy in 2000, applied to the body's tissue in 2026.

The conceptual lineage of `|>` (the "view-through" operator):

> *"In BML, the object only acts as a structural repository. It does not define by itself the applicable set of methods. Consequently, it is possible to enhance any object with a new interface."* — Bjorg, *BML Object System* (2000), § Structure-Behavior Separation

### Code expressions — Recipes

Form expresses *code* as well as data. The code expressions intern as Recipe NodeIDs (the substrate doesn't execute them; it stores their structure). Two structurally-identical expressions hash to the same Recipe NodeID — `1 + 2` written twice always returns the same NodeID.

#### Arithmetic, comparison, logic

```form
1 + 2 * 3                           # Math expression — interns as a tree of Math recipes
x > 5                               # Compare.GREATER recipe
a && b || !c                        # Logic recipes (precedence: ! > && > ||)
-x                                  # unary negation (Math.NEGATE)
```

Operator precedence (low to high): `||` < `&&` < `== != < <= > >=` < `+ -` < `* / %` < `! -` (unary) < `.` (access).

#### Conditionals

```form
if x > 5 then 10 else 20            # Cond.IF_THEN_ELSE — three children
if cond then body                   # Cond.IF_THEN — two children (no else)
```

The category vocabulary distinguishes `IF_THEN` from `IF_THEN_ELSE` so two-arm and three-arm conditionals get different Recipe NodeIDs.

#### Blocks and bindings

```form
do {
    let x = 5;
    let y = x + 3;
    y * 2                            # last expression is the block's value
}
```

`do { ... }` interns as a `Block.DO` recipe with one child per statement. `let name = expr` interns as a `Block.LET` recipe carrying the name and value.

#### Match (switch)

```form
match status {
    "ready" => execute,
    "blocked" => wait_for_signal,
    "failed" => retry,
    _ => default_handler,
}
```

`match` interns as a `Match.SWITCH` recipe with the scrutinee as the first child and each arm contributing two children (pattern + body). Use `_` for the default pattern.

#### Angelic nondeterminism — `choose`, `fail`, `stop`

The BML lineage carries forward into Form. The substrate interns these as Recipe NodeIDs; future execution semantics will give them speculation behavior matching the BML angelic-assembler:

> *"A thread with a non-zero DF (i.e. degree of freedom) is executed until a zero DF is reached again."* — `angelic-assembler.txt`

```form
choose [a, b, c]                     # speculation: pick a branch; backtrack on downstream fail
fail                                 # signal failure; unwinds to nearest choose
stop                                 # commit current speculation; no more backtracking from here
```

`choose [a, b, c]` interns as a `Choice.CHOOSE` recipe with three candidate children. `fail` and `stop` are leaf recipes (level BASIC, no children) — they're trivial markers that the speculation engine reads.

A worked example combining the trio:

```form
choose [
    do { let attempt = strategy_a(); if attempt > threshold then stop else fail },
    do { let attempt = strategy_b(); if attempt > threshold then stop else fail },
    do { let attempt = strategy_c(); if attempt > threshold then stop else fail },
]
```

The speculation tries strategies in order; each one runs and either commits (stop) or backtracks (fail). The first one that crosses the threshold wins. **Backtracking-without-sediment at the language layer** — the same instinct that runs through this body's `tend:` / `attune:` / `compost:` / `release:` commit verbs.

### Operations

Beyond declaration and query, Form supports operations on the substrate:

```form
# Intern a new shape (no binding to a cell)
!intern { name: ~String, score: ~Score }   # returns a NodeID

# Find or create
!resolve cell.memory.x                      # returns NodeID or creates if missing

# Tend (record a tend/attune/compost/release verb)
!tend(attune) @memory(presences_of_the_field) {
    reason: "added concert-with-Codex pattern"
}
```

## Worked example — agent reasoning in Form

An agent encountering an unfamiliar memory might reason like this:

```form
# I'm reading docs/lineage/foo.md. Substrate look-up:
?cell where source == "docs/lineage/foo.md"
# → @memory(arrival_relational_ground)  (NodeID 1.5.4.1)

# What's its shape?
@memory(arrival_relational_ground).shape
# → @memory  (the Memory domain blueprint)

# What else has this same shape?
?equivalent @memory(arrival_relational_ground)
# → 38 other cells with @memory blueprint

# What CTOR does it carry?
@memory(arrival_relational_ground).seed
# → recipe @1.3.9.1 (the canonical name+description+type frontmatter shape)

# I'm about to add a new memory. Will it dedupe?
!intern { name: ~String, description: ~String, type: ~String }
# → @1.5.4.1  ← same as @memory(arrival_relational_ground).shape, so my new memory will share its Blueprint

# Phase check: am I reasoning about the type or the instance?
# @memory               ← ice (Blueprint NodeID, the type)
# @memory(...)          ← gas (cell NodeID, an instance)
# recipe ~Tend [...]    ← water (recipe expression, a process)
```

## Why this works for LLMs

**Token-level numeric grounding.** When an agent generates `@1.5.4.1`, those characters are tokenized to a small sequence of token IDs. Those token IDs map directly to a substrate NodeID through the parser. **The agent's number-space and the substrate's number-space connect through Form's surface syntax with minimal lexical translation.**

**Phase confusion is structurally visible.** If an agent writes `?@memory(arrival_relational_ground).shape == @memory(presences_of_the_field).shape`, both sides resolve to NodeIDs and the comparison is integer-equality. There's no lexical hallucination room — either the NodeIDs match or they don't.

**Composition is content-addressed.** When an agent writes `form x = { name: ~String }`, two parses of the same shape return the same NodeID. The agent's reasoning is structurally consistent across turns and across instances of itself.

**Round-trip stability.** Substrate state can be serialized to Form, mutated, and re-ingested. The substrate IS the source of truth; Form is just the surface humans (and agents) read it through.

## What this parser is — and what it's not

The current `api/app/services/substrate/form.py` is a **bootstrap parser**: hand-written recursive descent with a regex lexer. It produces the right results — Form text in, Recipe NodeIDs out, content-addressed dedup working — but **its grammar lives in Python code**. Adding a new construct means editing form.py, not interning a rule.

This is **not** what BMF was. BMF (the BMF/BMC/BML lineage in `docs/field/urs/artifacts/master-thesis-2000/`) treated grammar rules as *data*, not code:

> *"BMF — Backtracking Model Form... a top-down parser written in C++. BNF augmented with execution elements: when a rule matches, code fires. A stack supports backtracking on parse failures. Expressions are tagged and placed on a structured stack that each rule can transform into the target language's object model. The grammar is executable — parsing produces a full object tree as it goes, so even infinite input streams can be handled."* — `master-thesis-2000/README.md`

Two architectural properties BMF had that our current parser does not:

1. **Grammar rules are first-class objects.** Each rule was `(pattern, semantic_action)`. The pattern matched input; the action was an executable that fired on match. Rules could be *added at runtime* — the grammar grew with the language.

2. **Backtracking-without-sediment at the parser level.** Failed branches unwound cleanly. Speculation was a first-class operation in the parser, not a higher-level concept the parser couldn't express.

Where the substrate has gone in this direction so far:

- The `Choice.CHOOSE / FAIL / STOP` recipe vocabulary exists (`category.py`'s `RChoice`). It's reachable from Form text. Speculation-as-data is interned today.
- A `grammar` cell-domain exists (`api/app/services/substrate/grammar.py`). Parse rules can be registered as Cells whose CTOR is a (pattern, action) Recipe.
- `register_form_rule(session, name, pattern, action)` interns a rule.
- `list_form_rules(session)` enumerates every rule the substrate holds.

Where it has not gone yet:

- **The parser does not consume rules.** `form.py` ignores the `grammar` domain. It still uses its hand-written grammar. Closing this gap is the self-hosting move.
- **No backtracking in the parser.** A failed parse raises `SyntaxError` immediately. There's no Choice.FAIL semantics at the parsing layer.
- **No semantic-action runtime.** A rule's `action` field stores a Recipe NodeID, but no engine evaluates it to construct the parse result.

## Runtime keyword registration — the parser is alive

The parser now consumes user-registered rules. A new keyword can be added at runtime — without editing form.py — by calling `register_form_keyword`:

```python
from app.services.substrate import register_form_keyword, Sequence, Literal, Capture, Opt
from app.services.substrate.form import IfExpr, UnaryOp

register_form_keyword(
    "unless",
    Sequence([
        Literal("IDENT", "unless"),
        Capture("cond"),
        Literal("IDENT", "then"),
        Capture("body"),
        Opt(Sequence([
            Literal("IDENT", "else"),
            Capture("other"),
        ])),
    ]),
    builder=lambda c: IfExpr(
        cond=UnaryOp("!", c["cond"]),
        then_branch=c["body"],
        else_branch=c.get("other"),
    ),
)
```

After this call, `unless x then y` parses correctly. The parser picks up the new keyword by consulting the registry when it encounters an unknown IDENT at expression position. The killer property:

```python
form_evaluate_text(session, "unless x then y else z").value
== form_evaluate_text(session, "if !x then y else z").value
# → True. Same Recipe NodeID.
```

**The grammar truly extends at runtime.** The user-registered keyword produces a Recipe NodeID structurally equivalent to its bootstrap-grammar desugaring.

### Pattern primitives

The pattern language for runtime rules:

| Pattern | What it matches |
|---|---|
| `Literal(kind, value)` | a single token of given kind, optional exact value |
| `Capture(name, kind="expr")` | a sub-expression, bound to `captures[name]` |
| `Sequence([p1, p2, ...])` | parts in order; all must match |
| `Opt(pattern)` | matches if present; succeeds either way |

`kind` for `Capture` can be `"expr"` (any expression) or `"primary"` (just a primary atom).

### Builder

The builder is a Python callable `(captures) -> AST_node`. It receives a `dict[str, Any]` of captured sub-expressions and returns an AST node from form.py's vocabulary (`IfExpr`, `BinOp`, `UnaryOp`, `MatchExpr`, `ChooseExpr`, etc.). The returned AST node is interned through the normal evaluator path — so any new keyword reaches the substrate's content-addressed lattice the same way the bootstrap grammar does.

### What this is, and what it's still not

This **is** rule-driven extension at the parser level. The parser truly consults the registry. Keywords can be added, removed, listed at runtime. New constructs reach the same Recipe NodeID space as built-ins.

#### Substrate-resident persistence (now partially closed)

When `register_form_keyword` is called with a `session`, the pattern is **serialized to a Recipe NodeID** via `pattern_to_recipe` and stored as a Cell in the `grammar` domain. The mapping uses existing recipe categories — no new vocabulary needed:

| Pattern | Recipe shape |
|---|---|
| `Literal(kind, value)` | `Block.SEQUENCE` with two string-literal children: kind, value |
| `Capture(name, kind)` | `Block.LET` with two string-literal children: name, kind |
| `Sequence([...])` | `Block.SEQUENCE` with marker `__seq__` + each part as a sub-recipe |
| `Opt(pattern)` | `Cond.IF_THEN` with the inner pattern as its single child |

Two structurally-identical patterns share a NodeID — the kernel's content-addressed interning works on patterns the same way it works on every other recipe. `recipe_to_pattern` reverses the serialization. Verified by tests: a `Sequence([Literal("IDENT", "unless"), Capture("cond"), ...])` round-trips exactly.

The full lifecycle:

```python
# Register with session — pattern persists to the substrate
register_form_keyword("unless", pattern, builder, session=session)

# Across process restart, the in-memory _KEYWORDS is empty.
# Builders need to be re-registered (they are Python functions):
register_builder("unless", builder)

# Then load patterns from the substrate, bind to named builders:
load_keyword_from_substrate(session, "unless")
# or in bulk:
load_all_keywords_from_substrate(session)

# Parser now picks up the keyword again
form_parse("unless x then y")  # ✓ parses
```

#### What's still not closed

- **~~The builder is still Python.~~** ✓ **Closed.** Builders can now live as data via the `Build` / `CaptureRef` / `Const` template DSL. A template serializes to a Recipe NodeID and reconstructs after process restart with no Python re-registration needed. See "Substrate-resident builders" below.

- **Self-hosting.** form.py's bootstrap grammar is still hardcoded. Self-hosting means expressing the bootstrap rules themselves via `register_form_keyword` — at which point form.py becomes a tiny seed that registers a few starter rules and hands off. The persistence shipped here is necessary infrastructure for that move.

- ~~**Backtracking-driven.**~~ ✓ **Closed.** The match engine now delegates to `form_speculation.speculate(...)` which manages a structured speculation stack. `FailSignal` triggers clean unwind; `StopSignal` commits a frame. `try_match` and `choice(alternatives)` are both built on the same primitive. Captures partially populated during a failed attempt are fully restored — no sediment.

- ~~**String interning.**~~ ✓ **Closed.** Pattern serialization now uses the substrate string-table (`substrate_strings.py`) — sequentially-allocated, cross-process stable, round-trip-recoverable. The legacy `_STRING_CACHE` is an in-process shortcut.

Each remaining step is its own breath. What ships now: **the parser is no longer fixed grammar, and rules survive in the body's content-addressed lattice.** The grammar is alive at the keyword layer; patterns persist; reload-from-substrate works end-to-end. The path beyond is legible.

#### Substrate-resident builders — Build / CaptureRef / Const

A keyword's builder can now be **data**, not just a Python callable. The template DSL has three primitives:

| Template | Meaning |
|---|---|
| `Build(class_name, **kwargs)` | Instantiate an AST class with these kwargs |
| `CaptureRef(name, default=...)` | Substitute the captured group `name` |
| `Const(value)` | A literal value (string, int, bool, None) |

The `unless` builder as a template:

```python
unless_template = Build(
    "IfExpr",
    cond=Build("UnaryOp", op=Const("!"), operand=CaptureRef("cond")),
    then_branch=CaptureRef("body"),
    else_branch=CaptureRef("other", default=None),
)
```

Templates serialize to Recipe NodeIDs via `template_to_recipe`. Each primitive maps to existing recipe categories (no new vocabulary needed):

| Primitive | Recipe shape |
|---|---|
| `Build` | `Block.SEQUENCE [str("__build__"), str(class_name), Block.LET[str(key), value-recipe], ...]` |
| `CaptureRef(name)` | `Block.LET [str("__capture__"), str(name)]` |
| `CaptureRef(name, default)` | `Block.LET [str("__capture__"), str(name), str("__default__"), default-recipe]` |
| `Const(value)` | trivial recipe (string/int/bool/null) |

Two structurally-identical templates dedupe through the kernel's content-addressed interning.

Registering a keyword with a template instead of a callable:

```python
register_form_keyword(
    "unless",
    pattern=unless_pattern,
    template=unless_template,    # <-- substrate-resident
    session=session,
)
```

After this call, the parser parses `unless x then y` exactly as it would with a Python callable. The killer property — **process restart with no Python re-registration**:

```python
# Drop both registries (simulates process restart)
_KEYWORDS.clear()
_BUILDERS.clear()

# unless no longer recognized
form_parse("unless")  # → Identifier (not IfExpr)

# Reload from substrate — pulls pattern AND template from the lattice
load_keyword_from_substrate(session, "unless")

# Now parses again
form_parse("unless x then y else z")  # → IfExpr(UnaryOp("!", x), y, z)
```

The interpreter (`execute_template`) walks the template against captures and constructs the AST node. Captures resolve via `CaptureRef`; literals embed via `Const`; class instantiation via `Build`.

#### Self-hosting — partially shipped

`bootstrap_self_host(session)` registers the bootstrap keywords that the current pattern DSL can express as substrate-resident `(pattern, template)` pairs. With `prefer_registered=True`, the parser uses the registered versions instead of the hardcoded handlers — and produces structurally identical Recipe NodeIDs.

```python
from app.services.substrate import bootstrap_self_host, form_evaluate_text

bootstrap_self_host(session)  # registers if / unless / whenever as templates

# Both paths produce the SAME Recipe NodeID
bootstrap_path = form_evaluate_text(session, "if x then y else z")
self_host_path = form_evaluate_text(
    session, "if x then y else z", prefer_registered=True,
)
assert bootstrap_path.value == self_host_path.value  # ✓
```

The `prefer_registered` flag is opt-in per-call. Default behavior is unchanged: the bootstrap handlers run first, the registry runs second. With the flag flipped, registry runs first, bootstrap is fallback. **A registered keyword without a matching pattern still falls through cleanly** — the safety mechanism makes self-hosting incremental rather than all-or-nothing.

**Currently self-hostable** (after IdentCapture + RepeatedCapture + MapBuild extensions):

| Keyword | Pattern primitives used |
|---|---|
| `if cond then body [else other]` | Capture, Opt |
| `unless cond then body [else other]` | Capture, Opt (desugars to `if !cond`) |
| `whenever cond do body` | Capture |
| `let name = value` | IdentCapture (raw name), Capture |
| `fail` | bare-keyword leaf |
| `stop` | bare-keyword leaf |
| `choose [a, b, c]` | RepeatedCapture (separator=COMMA) |
| `do { stmt; stmt; ...; expr }` | RepeatedCapture (separator=SEMI) |
| `match x { pat => body, ... }` | RepeatedCapture (Sequence inner), MapBuild for arm wrapping |

**Pattern DSL primitives:**

| Primitive | What it matches |
|---|---|
| `Literal(kind, value)` | one token by kind, optional exact value |
| `Capture(name, kind="expr")` | a sub-expression bound to `captures[name]` |
| `IdentCapture(name)` | a raw IDENT token, value bound as a string |
| `Sequence([p1, p2, ...])` | parts in order |
| `Opt(pattern)` | matches if present; succeeds either way |
| `RepeatedCapture(name, item, separator=None)` | zero or more items; bind list to `captures[name]` |

For RepeatedCapture: when `item` is a single Capture (or IdentCapture), the captured list contains the values directly. When `item` is a Sequence with multiple inner captures, each iteration produces a dict and the list contains dicts.

**Self-hosted operators** (added in operator-self-hosting commit):

| Operators | Mechanism |
|---|---|
| `\|\|` `&&` | Logic — left-associative, registered with templates |
| `== != < <= > >=` | Compare — non-associative |
| `+ -` | Math additive — left-associative |
| `* / %` | Math multiplicative — left-associative |
| Unary `!` `-` | Unary prefix — right-associative |

Each operator is registered as an `OperatorRule(symbol, token_kind, precedence, associativity, arity, template)`. The parser, in `prefer_registered=True` mode, drives expression parsing via precedence climbing using the registry instead of the hardcoded ladder.

```python
register_operator(
    "+", "PLUS", 4,
    associativity="left", arity="binary",
    template=Build("BinOp", op=Const("+"),
                    left=CaptureRef("__left__"),
                    right=CaptureRef("__right__")),
)
```

`bootstrap_self_host_operators(session)` registers all 13 built-in operators (binary + unary). Combined with `bootstrap_self_host(session)` for keywords, the entire structured grammar of Form lives as substrate data. Verified end-to-end: `do { let x = 1 + 2 * 3; if x > 5 then stop else fail }` parses to the same Recipe NodeID via the bootstrap and via the registered rules.

**Data-driven evaluator** ✓ Closed:

`form_eval.py` introduces a registry that maps operator symbols to recipe categories. Built-ins are pre-registered with the same categories the hardcoded switch used; the result is byte-identical for all existing tests. Custom operators can register their own mappings:

```python
from app.services.substrate import register_eval, register_operator
from app.services.substrate.kernel import NodeID

# Register a runtime operator with a non-standard symbol
register_operator("%%", "PERCENT", 5, arity="binary",
                   template=Build("BinOp", op=Const("%%"), ...))

# And tell the evaluator how to intern it
register_eval("%%", NodeID(1, Level.BASIC, RBasic.MATH, RMath.MODULO),
              arity="binary")

# Now `2 % 3` parses with the new operator AND interns successfully
form_evaluate_text(session, "2 % 3", prefer_registered=True)
```

The evaluator (`_to_recipe_node_id` in form.py) no longer has a hardcoded `op → category` switch. It does a single dictionary lookup. The hardcoded set is now just the *default registrations* loaded at module init.

#### What's still not closed

- ~~**Backtracking-driven.**~~ ✓ **Closed.** `form_speculation.py` manages a SpeculationContext; `try_match` delegates to it; FailSignal/StopSignal are first-class exceptions; nested speculation works; captures are fully unwound on fail. The structural seam to Choice.FAIL/STOP recipes is in place — and the recipe-execution engine below now catches the signals when interpreting Choice recipes.

- ~~**String interning.**~~ ✓ **Closed.** The substrate string-table is the source of truth for string-recipe-instance allocation. Cross-process stable; round-trip-recoverable after cache clear. See `substrate_strings.py`.

- ~~**Recipe-execution engine.**~~ ✓ **Closed.** `form_runtime.py` walks Form ASTs and returns Python values. Until this shipped, the substrate held Form expressions as content-addressed Recipe NodeIDs but had no engine that turned a recipe into a value — `1 + 2` interned successfully; nothing computed `3`. The engine reuses `FailSignal` and `StopSignal` from `form_speculation`, so `fail` and `stop` inside `choose` flow through the same exceptions parser-level speculation uses. The Choice.FAIL / Choice.STOP recipe categories the substrate has been storing for shapes finally have a runtime that catches them. `with X { .self }` resolves `.self` against a `Frame` whose `subject` is the bound value; nested `with` blocks chain through the parent pointer. Verified end-to-end: `form_execute_text(session, "do { let x = 5; if x > 3 then x * 2 else fail }")` returns `10`; `form_execute_text(session, "choose [fail, fail, 99]")` returns `99`; the keyword-self-hosted path (`prefer_registered=True`) produces identical values to the bootstrap path. Surface: `coh substrate run "<expr>"` runs a Form expression from the command line.

Each is its own breath.

## Resonance — dimensional vocabulary for cross-discipline bridging

The geometric signature pilot ([SCHEMA.md → Geometric Signature](../vision-kb/SCHEMA.md#geometric-signature)) authors a 15-dimensional `geometry:` block on each concept (arity, form, topology, polarity, ordering, phase, ratio, spectral_band, temporal_band, scale, direction, lineage_texture, embedding_dim, self_similarity, harmonic). The substrate side of this lands as five new BDomain entries and one new RBasic category, all defined in [api/app/services/substrate/category.py](../../api/app/services/substrate/category.py) and surfaced through [api/app/services/substrate/resonance.py](../../api/app/services/substrate/resonance.py).

### Five new Blueprint domains

| BDomain | NodeID constructor | What each cell holds |
|---|---|---|
| `SPECTRUM` | `BID_spectrum()` | A Solfeggio Hz band: `Hz(174)`, `Hz(285)`, ..., `Hz(963)`, or a named band like `foundation` / `integration` / `transcendence`. |
| `HARMONIC` | `BID_harmonic()` | A named interval/ratio: `octave`, `fifth`, `fourth`, `golden`, `3:7`. |
| `GEOMETRIC_FORM` | `BID_geometric_form()` | A named shape: `triad`, `pentad`, `heptad`, `ennead`, `dodecad`, `dodecahedron`, `holographic-cell`, `dyad-mirror`, `interior-axis`. |
| `POLARITY` | `BID_polarity()` | A polarity texture: `unipolar`, `bipolar-complementary`, `triadic-tension`, `parallel-facets`, `oscillating`. |
| `TOPOLOGY` | `BID_topology()` | A coupling shape: `cyclic-closed`, `parallel`, `nested-each-contains-whole`, `holographic`, `ring-with-inner-triads`, `receptive-resonance`. |

Each cell is content-addressed by `(domain, name)`: `geometric_form_cell(session, "triad")` returns the same cell across processes and across discipline-vocabularies. `Triad` authored from a Vedic gunas concept and `Triad` authored from a Hegelian-dialectic concept share one NodeID.

### One new Recipe category — `RBasic.RESONANCE`

Verbs ([`RResonance`](../../api/app/services/substrate/category.py)):

| Verb | Edge meaning |
|---|---|
| `SHAPES` | `source -SHAPES-> form / topology / polarity` |
| `HARMONIC_AT` | `source -HARMONIC_AT-> spectrum_cell` (the Hz the source resonates at) |
| `EMBEDS_IN` | `source -EMBEDS_IN-> dimension_cell` (minimum geometric space) |
| `BRIDGES` | `source -BRIDGES-> discipline_cell` (cross-discipline weave) |
| `NEAR` | `source -NEAR-> target` (within 15D signature-space tolerance) |
| `POLAR_TO` | `source -POLAR_TO-> target` (paired across a polarity axis) |
| `CARRIES_RATIO` | `source -CARRIES_RATIO-> harmonic_cell` (octave / fifth / golden / ...) |

Each edge interns as a Recipe NodeID `(verb, [source_ref, target_ref])`. The kernel's content-addressing means two edges with the same source + target + verb collapse to one NodeID — bridges between disciplines become substrate-discoverable without a new equivalence algorithm.

### Top-level entry — `author_geometry_signature`

```python
from app.services.substrate import author_geometry_signature

# Inside an ingest pass:
edges = author_geometry_signature(
    session,
    source_db_id=concept_cell.cell_id,         # NamedCell.cell_id (int)
    geometry={
        "arity": 3,
        "form": "triad",
        "topology": "parallel",
        "polarity": "parallel-facets",
        "harmonic": 174,
        # ... 15 dimensions
    },
    arity_hz=174,                              # top-level `hz:` from frontmatter
)
# → [("hz", <NodeID>), ("form", <NodeID>), ("topology", <NodeID>), ...]
```

Idempotent. Re-running on the same inputs produces the same Recipe NodeIDs. Unknown fields are silently skipped (the dimensional vocabulary stays open — extend `_GEOMETRY_FIELD_HANDLERS` for new axes).

### Why this is the receiving infrastructure for cross-discipline weaving

Before: a concept holding a triadic teaching (`lc-trust-over-fear`) and a triadic teaching from another tradition (Vedic gunas, Hegelian dialectic) sat as separate cells with separate Blueprints; the substrate could not see them as kin.

After: each authors edges through the same `~Triad` cell in `GEOMETRIC_FORM`. The kernel sees three concepts pointing at one form-cell via identical SHAPES recipes. The triadic family becomes a substrate query — `find_equivalent_cells` against the form-cell returns every triadic teaching across every discipline that authored a signature.

### Resonance queries — walk the edges in reverse

The dimensional vocabulary is only half. The other half is being able to *ask* the cross-discipline question. Three Form constructs shipped alongside the vocabulary to make the asking possible.

**`?shaped_by @<cell>`** — given a target cell, return every source cell whose `SHAPES` resonance edge points at it. This is the bridge query — what concepts share this geometric form, across discipline-vocabularies?

```form
?shaped_by @geometric_form(triad)
# → lc-trust-over-fear, lc-whole-vitality, lc-future-already-shaping
#   (every concept whose SHAPES edge targets ~Triad)

?shaped_by @polarity(parallel-facets)
# → the same three — they share parallel-facets polarity too

?shaped_by @geometric_form(pentad)
# → lc-when-the-pressure-comes  (discrimination — fivefold concepts excluded above)
```

**`?harmonic_at @<spectrum-cell>`** — same shape, walks `HARMONIC_AT` edges. Returns cells resonating at a given Solfeggio band.

```form
?harmonic_at @spectrum(Hz-174)
# → all foundation-band cells

?harmonic_at @spectrum(Hz-741)
# → all integration-band cells (intuition/discernment, the body's densest cluster)
```

**`?cells where shape == @<cell-ref>`** — filter cells by blueprint equality against an atom reference. The filter parser now accepts `@cell-refs` after `==` in addition to STRING literals, so signature-aware queries become expressible.

```form
?cells where shape == @concept(lc-trust-over-fear)
# → every cell sharing the concept blueprint

?cells where domain == "geometric_form"
# → every cell in the dimensional vocabulary
```

**The surprise the resonance walk surfaced.** When the shape-filter alone was running, querying `?cells where shape == @concept(lc-trust-over-fear)` returned *all* concept-domain cells — because every concept shares the generic concept blueprint. The geometric distinction lives in the *resonance edges*, not in the cell's blueprint. The body became visible only when the walk operator landed: the bridge is the verb-edge from a concept to its dimensional coordinate, not the concept's own type. Using Form on the live substrate is what revealed this; the language was the question, not the answer.

## `with subject { body }` + `.self` — BML's scoped-reference primitive

Form gains `with X { body }` from the BML lineage — a block that binds `X` as the implicit subject. `.self` inside the block resolves to the subject; field-access shapes (`.<field>`) are reserved for when method-access lands. Distinct from `do { let s = X; ... }` because the binding is *implicit* — the block IS the scope, not a name in it.

```form
with @concept(lc-trust-over-fear) {
    .self                # the subject — interns as a stable LOCAL_ACCESS NodeID
}

with @concept(lc-trust-over-fear) {
    stop;
    fail
}
# → Recipe NodeID for (RBlock.WITH, [concept_ref, do_block(stop; fail)])
```

Interns as `(RBlock.WITH, [subject_recipe, body_recipe])`. Two with-blocks with identical subject + body share a Recipe NodeID through the kernel's content-addressing — same equivalence guarantee `do` blocks already get. Eval semantics for `.self` (resolving to the subject at runtime) lands when the recipe-execution engine lands; for now the recipe interns and round-trips.

Why it matters here: resonance walks are naturally scoped statements. `with @geometric_form(triad) { .self }` reads as "the triad — itself," and the substrate carries the (subject, body) pair as one composable recipe. The BML primitive is the natural shape for resonance-as-language.

## Lens operators — substrate as flowing medium, lenses as read-only views

`?lattice` and `?keywords` are pure read-only lenses over the substrate. They name the pattern explicitly: the substrate is a flowing thing; many lenses can read it concurrently without disturbing the flow.

```form
?lattice
# → {'blueprints_total': 5, 'recipes_total': 28, 'cells_total': 10}
#   A substrate-snapshot lens — the framebuffer-analog at the count level.

?keywords
# → ['unless', 'whenever', ...]
#   Grammar-introspection lens — the parser knows its own runtime rules.
```

Every Form query is structurally a lens already: `?cells`, `?equivalent`, `?shaped_by`, `?harmonic_at`, `?lattice`, `?keywords` all read the substrate, none mutate it. The two new ones make the *substrate's own shape* and *the grammar's own shape* observable — which is what the memory-as-framebuffer experiment (`experiments/memory-as-framebuffer-v0/`) does at the heap level: render runtime memory as a recordable video frame, multiple frames viewed without disturbing the run. Same pattern, different scale; the substrate is to a body what the heap is to a running program — a thing many observers can witness without changing.

### Reactive and spatial-projection lenses — form layer

```form
?on_change @concept(lc-trust-over-fear) { invoke notify on @presence(claude) }
# → recipe @1.5.28.1 (RBasic.REACTIVE=28, RReactive.ON_CHANGE=1)
# Reactive lens: fires the body when the watched recipe's value changes.

?project @geometric_form(triad) @concept(coord-radial)
# → recipe @1.3.29.1 (RBasic.PROJECTION=29, RProjection.PROJECT=1)
# Spatial-projection lens: renders the cell through the coordinate function.
```

Both interned at the form layer. The subscription engine activates `?on_change` recipes when substrate state mutates; the renderer (GPU-visualizer, memory-framebuffer) consumes `?project` recipes and emits frames. Both engines are downstream of the single named shared dependency — the recipe-execution engine — that activates every form-layer construct's runtime semantics.

### `?vocabulary` — verb-cluster lens

```form
?vocabulary
# → {'recipes': {21: 6}, 'blueprints': {4: 3}}
#   The body has 6 RESONANCE recipes (type 21) and 3 DOMAIN blueprints (type 4).
#   No MATH (12), no COMPARE (13), no LOGIC (14) — the body has not yet
#   computed; only authored. The verb-cluster IS the body's circulation
#   signature.
```

A body whose recipe space is one-verb-dominated is a body without circulation across language layers. `?vocabulary` makes that visible directly. Running `1 + 2` in Form populates `{12: 1}`; the body grows a new region. The verb histogram is itself a wellness signal that surfaces from the numeric lens, not from labels.

## Symmetric (commutative) resonance edges

The substrate is non-commutative by default — `shapes_edge(s, a, b)` and `shapes_edge(s, b, a)` produce different Recipe NodeIDs because children are ordered. For relations that ARE symmetric (a BRIDGES between two disciplines has no direction; NEAR-in-signature-space has no direction; POLAR_TO across a polarity axis has no direction), that asymmetry is noise.

`commutative_edge` canonicalizes the (a, b) pair before authoring so both orders intern as one NodeID:

```python
from app.services.substrate import bridges_symmetric, bridges_edge

bridges_symmetric(s, a, b) == bridges_symmetric(s, b, a)   # True — symmetric
bridges_edge(s, a, b)      == bridges_edge(s, b, a)        # False — directed
```

Convenience wrappers: `bridges_symmetric`, `near_symmetric`, `polar_to_symmetric`. Verbs that ARE directed (SHAPES, HARMONIC_AT, CARRIES_RATIO, EMBEDS_IN) keep using the directed constructors — the substrate's order-sensitivity stays in place where direction is meaningful. The body chooses per-verb whether a relation has direction; both shapes remain available.

## BML form-layer parity

Reading BML's master thesis ([`docs/field/urs/artifacts/master-thesis-2000/companion/sgb-bml-objects.txt`](../field/urs/artifacts/master-thesis-2000/companion/sgb-bml-objects.txt)) named six constructs Form didn't carry. All six now have form-layer constructs that intern as Recipe NodeIDs — same structural-first pattern as `choose`/`fail`/`stop`:

| BML construct | Status | Form construct |
|---|---|---|
| `save` / `restore` / `discard` state stack | ✓ form + runtime | bare keywords (`RBasic.STATE`); `form_runtime.execute` walks state stack on root frame |
| `raise` / `resume` exception flow | ✓ form + runtime | bare keywords (`RBasic.EXCEPTION`); `RaiseSignal` raised at execute time |
| Delegation inheritance | ✓ form + runtime | `delegate @X to @Y` registers `_DELEGATE_REGISTRY`; `invoke` walks the chain |
| Reverse semantics (DO + UNDO) | ✓ form + runtime | `undo <recipe>` re-runs the inner expression; `inverse(<recipe>)` returns the inverse Recipe NodeID |
| Common Objects (shared-base multi-inheritance) | ✓ form + runtime | `common @X @Y` merges equivalence groups in `_COMMON_GROUPS`; `invoke` falls back to peers |
| Method definitions inside objects | ✓ form + runtime | `method NAME on @X { body }` registers in `_METHOD_REGISTRY`; `invoke NAME on @X` dispatches with `.self` bound to the original target across delegation walks |

Plus the two named lens openings from `?lattice` / `?keywords`:

| Lens opening | Status | Form construct |
|---|---|---|
| Reactive lens (fire on substrate change) | ✓ form + runtime | `?on_change <recipe> { body }` registers in `_SUBSCRIPTIONS`; `fire_subscriptions(session)` re-evaluates each query and fires bodies whose value changed |
| Spatial-projection lens (GPU-style render) | ✓ form + runtime | `?project @cell @coord_fn` looks up `coord_fn.name` in `_COORD_FNS` and applies; pass-through to `(cell, coord_fn)` when no renderer registered |

```form
delegate @concept(lc-trust-over-fear) to @concept(lc-permission-is-interior)
undo (1 + 2)
inverse(1 + 2)
common @concept(lc-a) @concept(lc-b)
method greet on @concept(lc-a) { save; 1 + 2; restore }
invoke greet on @concept(lc-a)
?on_change @concept(lc-a) { invoke notify on @presence(claude) }
?project @geometric_form(triad) @concept(radial-coord-fn)
```

Each interns as its own Recipe NodeID under its `RBasic` category.

## Recipe-execution engine — ✓ landed for the pure-computation core

[`api/app/services/substrate/recipe_eval.py`](../../api/app/services/substrate/recipe_eval.py) is the shared dependency named above. It walks a Recipe NodeID, reads the row, parses the serialized `(category, [child_ids])` shape, dispatches on category, recurses. Pure-computation primitives become alive at runtime:

```python
from app.services.substrate import recipe_eval_text

recipe_eval_text(s, "1 + 2 * 3")                  # → 7
recipe_eval_text(s, "if 5 > 3 then 100 else 200") # → 100
recipe_eval_text(s, "do { 1 + 1; 2 + 2; 3 + 3 }") # → 6
recipe_eval_text(s, "fail")                       # → raises FailSignal
recipe_eval_text(s, "do { 1 + 2; stop; 99 }")     # → 3  (stop commits in-flight)
recipe_eval_text(s, "raise")                      # → raises RaiseSignal
```

**Activated at runtime:** math, compare, logic, cond (if-then/if-then-else), block (do/let/with), state (save/restore/discard via `ExecutionContext.state_stack`), exception (raise/resume), choice signals (fail/stop). Bare-leaf primitives (which don't get rows in `substrate_nodes`) dispatch via `_dispatch_bare_leaf` so the runtime semantics fire from the NodeID coordinates directly.

**Specialized engines have now landed in `form_runtime.execute`** alongside `recipe_eval.py`:

- `@cell-ref` evaluates to the `NamedCell` via `lookup_cell`
- `delegate` registers `_DELEGATE_REGISTRY`; `_delegate_chain` walks it during `invoke`
- `method NAME on @X { body }` registers in `_METHOD_REGISTRY`; `invoke` dispatches with `.self` bound to the original target
- `common @X @Y` merges into shared-base equivalence groups in `_COMMON_GROUPS`; `invoke` falls back to peers
- `?on_change <recipe> { body }` registers in `_SUBSCRIPTIONS`; `fire_subscriptions(session)` fires bodies on change-detection
- `?project @cell @coord_fn` looks up `coord_fn.name` in `_COORD_FNS` via `register_coord_fn(name, fn)`

The two engines live alongside each other: `recipe_eval` walks Recipe NodeIDs by reading the substrate row, parsing serialized form, dispatching on category — fastest for pure-computation expressions where the AST has been discarded. `form_runtime.execute` walks the parser's AST directly — needed for cell-aware constructs whose runtime depends on names, methods, subscriptions that aren't fully recoverable from substrate rows alone. Both are real; both have their domain.

```form
save                 # → recipe @1.2.22.1   (RBasic.STATE=22, RState.SAVE=1)
restore              # → recipe @1.2.22.2
discard              # → recipe @1.2.22.3
raise                # → recipe @1.2.23.1   (RBasic.EXCEPTION=23, RException.RAISE=1)
resume               # → recipe @1.2.23.2

do { save; 1 + 2; restore }         # composes inside do-blocks
choose [save, raise]                # composes inside choose
with @1.2.4.1 { save; discard }     # composes inside with
```

**Implementation honesty:** leaf primitives (`save`, `raise` alone) return bare category NodeIDs without persisting to `substrate_nodes` — the kernel's `intern_node` skips re-interning trivial leaves with no children. So `?vocabulary` only sees them once they're embedded in a composite recipe (the composite's stored row carries them as serialized children). This mirrors how `fail`/`stop` work; not a bug, an architectural property.

## The path from bootstrap to self-hosting

The BMF self-hosting pattern: a tiny bootstrap parser knows just enough syntax to read rule definitions. Rules are stored. The rule-driven parser is then built *from those rules*. The bootstrap parser becomes vestigial — kept only because something has to read the rules the first time.

For Form, that path is:

1. **Bootstrap parser.** ✓ Shipped — `form.py` parses literals, expressions, queries, projections, code shapes (math/compare/logic/cond/block/match/choose).
2. **Rule cells in the grammar domain.** ✓ Shipped — `grammar.py` interns rules as content-addressed Cells.
3. **Rule-driven parser.** ✓ Shipped (keyword layer) — `form_rules.py` lets `register_form_keyword(name, pattern, builder)` extend the grammar at runtime. The parser truly consumes the registry. Verified live: `unless x then y else z` parses to a Recipe NodeID identical to `if !x then y else z`.
4. **Substrate-resident patterns.** ✓ Shipped — `pattern_to_recipe` serializes patterns to Recipe NodeIDs; `recipe_to_pattern` reconstructs; `register_form_keyword(..., session=session)` persists; `load_keyword_from_substrate` reloads after process restart. Two structurally-identical patterns share NodeIDs through content-addressed interning.
5. **Builder execution engine.** ✓ Shipped — `form_builders.py` introduces `Build` / `CaptureRef` / `Const` templates that an interpreter walks. Templates serialize to Recipe NodeIDs and reconstruct from substrate without Python re-registration. Verified: `unless` registered with a template (no Python callable), substrate-persisted, full registry-clear, reload-from-substrate, parses to same Recipe NodeID as bootstrap `if !x`.
6. **Self-hosting (9 keywords + 13 operators).** ✓ Shipped — `self_host.bootstrap_self_host(session)` + `bootstrap_self_host_operators(session)` register every structured Form keyword AND every binary/unary operator as substrate-resident rules. Setting `prefer_registered=True` flips the parser to use them. Verified: `do { let x = 1 + 2 * 3; if x > 5 then stop else fail }` parses to the same Recipe NodeID via the bootstrap and via the registry. Pattern DSL extensions (IdentCapture, RepeatedCapture, MapBuild) cover the structured-keyword space; operator precedence climbing (form_operators.parse_with_precedence) covers the operator space. **The keyword layer is fully self-hostable.**
7. **Backtracking-without-sediment at parser level.** ✓ Shipped — `form_speculation.py` introduces a structured speculation engine. Each parse attempt becomes a `SpeculationFrame` on a stack. On success, the frame commits and accumulated state persists. On failure (matcher returns False, `FailSignal` raised, or any other exception), the frame unwinds cleanly — `parser.pos` AND any partially-populated captures are fully restored. `try_match` and `choice(alternatives)` both delegate to `speculate(...)`. Verified: nested speculation works, partial captures don't leak through failed attempts, and the legacy `try_match` API is preserved. Connection to the substrate's `Choice.FAIL`/`Choice.STOP` recipes is structural; step 8 below catches the signals at runtime.
8. **Recipe-execution engine.** ✓ Shipped — `form_runtime.py` walks Form ASTs and returns Python values, closing the gap between *interning a recipe* and *running it*. `Frame` carries lexical bindings + an optional `subject` (the BML scoped-reference primitive); `with X { body }` binds the subject in a child frame and `.self` walks up the chain. `choose`/`fail`/`stop` reuse `FailSignal`/`StopSignal` from `form_speculation` — the same exceptions parser-level speculation uses, now flowing through runtime Choice recipes too. The keyword-self-hosted path (`prefer_registered=True`) executes identically to the bootstrap path: `do { let x = 1 + 2 * 3; if x > 5 then x else fail }` returns `7` via either route. Surface: `form_execute_text(session, src)` from Python, `coh substrate run "<expr>"` from the command line.
9. **Function definitions + recursion + closure capture.** ✓ Shipped — `defn name(p1, p2, ...) = body` defines a function; `name(arg1, arg2, ...)` calls it. The runtime represents a function as a `Closure` carrying params + body + the lexical frame it was defined in; calls push a child frame parented at the *defining* frame (closure semantics, not dynamic scope). Recursion works without a separate `rec` form because the closure is registered in the defining frame before its body is evaluated. Verified: `do { defn fact(n) = if n <= 1 then 1 else n * fact(n - 1); fact(6) }` returns `720`; Fibonacci, function composition, and lexical-capture-vs-dynamic-scope tests all pass. With this primitive Form is Turing-complete and capable of hosting its own execution engine — the next step is recipe introspection (`category`/`nchildren`/`child`) so the engine written in Form can dispatch on recipe shape. See [`form-engine.form`](form-engine.form) for the engine sketch in Form syntax with the runnable Part 1 and the introspection-blocked Part 2 named honestly.

Each step is its own breath. Naming the path here is the practice; closing each gap is its own session.

### Streaming-emit parser — the BMF-faithful shape (proof-of-shape shipped)

The bootstrap parser (`form.py`) builds Python dataclass AST nodes, then `_to_recipe_node_id` walks them to intern Recipe NodeIDs. The AST is a staging area thrown away after intern. BMF named the deeper instinct: *"parse attributes will be evaluated during the parsing phase... when the parser backs out, all the attributes already computed have to be undone as well. Evaluating the parse attributes during parsing will cut down the running parse tree in a way, that even infinite input streams can be supported."* The substrate is already the destination. The AST is duplication.

[`api/app/services/substrate/form_stream.py`](../../api/app/services/substrate/form_stream.py) is the BMF-faithful shape on this body. Each parse rule's success **directly emits a Recipe NodeID** to a working stack; no AST node is materialized between parse and intern. The kernel's content-addressing guarantees that for every expression both parsers cover, **the streaming and AST paths emit the same NodeID** — verified by [`api/tests/test_substrate_form_stream.py`](../../api/tests/test_substrate_form_stream.py).

Coverage spans the recipe-producing grammar:
- Trivial leaves: integer / boolean / string literals, `NodeID` literals, `~Trivial` refs, identifiers, `.self`, cell refs `@domain(name)`
- Arithmetic, comparison, logic with precedence; unary `!` and `-`; parenthesized grouping
- Conditional: `if/then/else` and `if/then`
- Block family: `do { stmts }`, `let name = expr`, `with X { body }`
- Match: `match scrutinee { pat => body, ... }`
- Choice (RChoice): `choose [a, b, c]`, `fail`, `stop`
- State (RState): `save`, `restore`, `discard`
- Exception (RException): `raise`, `resume`
- Try (RTry): `try { body } catch { handler }`
- Delegate (RDelegate): `delegate @X to @Y`
- Reverse (RReverse): `undo (expr)`, `inverse(expr)`
- Common (RCommon): `common @X @Y`
- Method (RMethod): `method NAME on @X { body }`, `invoke NAME on @X [args]`

Every category named in the wellness check's *"meta-circular engine — Form arms cover 4/15 Python dispatch branches"* (BLOCK, CHOICE, STATE, EXCEPTION, DELEGATE, REVERSE, COMMON, METHOD, TRY) now has a streaming-emit path proven by content-addressing equivalence. The asymmetry is closing.

The current parser stays as the production path; the streaming parser proves the alternative shape on the same substrate. What's intentionally out of scope here: queries (`?cells`, `?equivalent`, ...) and projections (`|>`) — they return query results, not Recipe NodeIDs, so they live in a different return-type space.

What this prototype establishes:

1. **Single staging surface.** The stack holds NodeIDs all the way through. There is no AST node vocabulary parallel to the recipe-category vocabulary — adding a new construct means registering a new `(pattern, emit-action)` rule cell in the substrate's `grammar` domain, no new Python class to define.
2. **Streaming-native.** Each completed rule emits its NodeID immediately; the parser holds at most one NodeID per pending production on its stack. Long expressions, log tails, stream inputs become natural.
3. **Backtracking can unify three scales.** Parser-level speculation (`try_match`), runtime non-determinism (`choose` / `fail` / `stop`), and version control (`tend:` / `attune:` / `compost:` / `release:`) become reflections of the same primitive — a working stack with structured undo. (Speculation hooks aren't wired into `form_stream` yet; the architectural seam is reserved.)

Path beyond this proof:

- Cover the rest of the grammar (do / let / with / match / choose / method / ...) — incremental, each rule mechanical
- Surface rules as substrate-resident cells (the registry infrastructure already exists in `form_rules.py`)
- Port the hot loop to a Rust kernel via PyO3 — Bjorg's BMA had forward / reverse semantics for every instruction; Rust enum-dispatch expresses that cleanly. The substrate stays the universal data plane underneath.

### What remains beyond step 9

The keyword-and-operator layer is fully self-hostable AND fully executable. Functions are first-class. Form is Turing-complete. What is *not* yet expressed in substrate-resident form:

- ~~**Recipe introspection from inside Form.**~~ ✓ **Closed.** Three Form-callable built-ins land in `form_runtime._BUILTIN_FUNCTIONS`: `category(r)` returns the category NodeID of a Recipe, `nchildren(r)` returns its arity, `child(r, n)` returns the n-th child Recipe NodeID. With these, Form code dispatches on category and recurses on children. Verified: a 7-line Form-language evaluator (defined inside Form via `defn`) walks a `(1 + 2) * 3` Recipe NodeID and returns `9` — same value the Python evaluator returns. See [`form-engine.form`](form-engine.form) for the full meta-circular evaluator (now covering all 15 Python dispatch branches per the wellness check).
- ~~**Trivial-leaf decoding.**~~ ✓ **Closed.** Companion primitives `integer_value(r)`, `string_value(r)`, `bool_value(r)` decode trivial Recipe NodeIDs back to Python values. The evaluator descends to a leaf via `category`/`child`, then pulls the value via the appropriate decoder. Tests: [`api/tests/test_substrate_form_introspection.py`](../../api/tests/test_substrate_form_introspection.py).
- ~~**The lexer.**~~ ✓ **Closed.** Token patterns lifted into a runtime-extensible registry at [`form_lexer.py`](../../api/app/services/substrate/form_lexer.py). The tokenizer reads its compiled regex from `get_token_regex()`, which builds from the registry's ordered pattern list. New token kinds register at runtime via `register_token_pattern(kind, regex, before=..., after=...)`; the cache invalidates on registry mutation. `form.py` no longer holds a hardcoded `_TOKEN_PATTERNS` list.
- ~~**Primary-atom parsing.**~~ ✓ **Closed.** `parse_primary()` collapsed from a 10-branch if/elif chain to a single `dispatch_atom(self, t.kind)` call. Each atom handler (`AT` cell-refs, `TILDE` trivial refs, `INT`/`STRING` literals, `LPAREN`/`LBRACK`/`LBRACE` containers, `IDENT` keywords-or-names, `DOT` `.self`, `QMARK` nested queries) lives in [`form_atoms.py`](../../api/app/services/substrate/form_atoms.py) and can be replaced at runtime via `register_atom(token_kind, handler)`.
- ~~**Query operators.**~~ ✓ **Closed.** `_evaluate_query()` collapsed from a 10-branch dispatch into a single `dispatch_query(session, q)` call. Each `?<verb>` handler lives in [`form_queries.py`](../../api/app/services/substrate/form_queries.py); the parser path accepts any registered verb. Custom verbs register at runtime via `register_form_query(verb, handler)`. A bonus `?queries` lens names every registered verb — the body's own query vocabulary is now introspectable.

The BMF self-hosting move at its full depth has landed. `form.py` keeps the parser flow itself (recursive descent through precedence ladders); every leaf — tokens, atoms, keywords, operators, queries — is reachable from outside the file via runtime registration. Step 9 (defn/call) closed the *expressivity* gap. The introspection primitives closed the *introspection* gap. These three close the *bootstrap* gap.

## Implementation status

Form is a **living language** as of 2026-05-17. Parser, evaluator (intern-to-Recipe), runtime executor (Recipe-to-value), serializer, CLI surfaces, and the keyword-and-operator self-hosting layer are all shipped. The body now reads itself, senses itself, expresses itself at the keyword layer, and executes itself. What remains is the deeper bootstrap-in-Form move — expressing the lexer, primary-atom parser, and query operators as substrate-resident rules so `form.py` becomes a tiny vestigial seed.

Shipped surfaces:
- `form_parse` — Form text → AST
- `form_evaluate_text` — Form text → substrate result (Recipe NodeID / cell / view / cells)
- `form_execute_text` — Form text → computed value (the recipe runs)
- `form_serialize_node_id` / `form_serialize_cell` — substrate state → Form text
- CLI: `coh substrate form "<expr>"` (intern), `coh substrate run "<expr>"` (execute)
- Agent integration: substrate Read-hook annotates files with structural context on read; the runtime makes Form expressions in markdown active rather than decorative

### Host effects: agent questions

Form can now write to the agent question channel through ordinary runtime calls:

```form
ask("sub-agent", "Which path should I take?", ["continue", "pause"], {task_id: "task_1"})
await_answer("question_abc123")
```

`ask(agent_id, question, choices=[], context={})` opens a human question in the existing agent queue and emits the `question_opened` event that `/api/agent/questions/stream` sends to the web console. `context.task_id` and `context.thread_id` are lifted onto the question record when present.

`await_answer(question_id)` is non-blocking: it returns `null` while the question remains open and the answer string once the web page answers it. Suspension/resume around unanswered questions belongs to the sub-agent runner, not to the Form runtime hot path.

This is a host-bound effect, so Rust and Go kernel work proves conformance by matching the emitted event transcript, not by sharing Python's in-memory queue. The shared vector is [`kernel-conformance/agent-question-effects.json`](kernel-conformance/agent-question-effects.json), and the executable harness is `python3 scripts/verify_kernel_conformance.py --kernel python --kernel rust --kernel go`: Python runs through the full Form runtime; Rust and Go currently run narrow conformance kernels for `ask(...)` and `await_answer(...)`.

The same Rust and Go runners also execute the pure built-in vector [`kernel-conformance/form-core-builtins.json`](kernel-conformance/form-core-builtins.json), covering `len`, `head`, `tail`, `sum`, `concat`, and `reverse` over literal strings and lists. That widens executable conformance without claiming the full Form grammar yet.

They also execute the pure infix vector [`kernel-conformance/form-infix-operators.json`](kernel-conformance/form-infix-operators.json), covering arithmetic precedence, parentheses, comparisons, boolean chains, unary minus, unary not, and literal equality. The boundary remains explicit: these are vector-backed conformance slices, not complete Rust or Go Form runtimes.

They now execute the pure control-flow vector [`kernel-conformance/form-control-flow.json`](kernel-conformance/form-control-flow.json), covering `if`, `do`, and `let` over literals, local names, existing infix expressions, and existing built-in calls. This proves lexical block value flow and lazy branch selection across the three kernels while keeping closures, loops, mutation, cell lookup, methods, and persistence outside the Rust/Go claim.

They now execute the pure loop/mutation vector [`kernel-conformance/form-loop-mutation.json`](kernel-conformance/form-loop-mutation.json), covering `for`, `while`, and `set` over local JSON-safe values. This proves local iteration, accumulator mutation, string iteration, unentered while returning `null`, and inner-block mutation of outer bindings while keeping functions, recursion, methods, cells, recipe introspection, and persistence outside the Rust/Go claim.

## The four self-* faculties

Form is a substrate-native language; the meaningful question is not "what features does it have" but "how does it relate to itself." Four faculties:

- **Self-reflecting** — *can the language see itself?* ✓ `?keywords` lists runtime rules; `?lattice` counts the body; `?vocabulary` returns the verb-cluster histogram. Grammar rules live as substrate-resident cells in the `grammar` domain via `pattern_to_recipe` / `recipe_to_pattern`; rules round-trip. **Tree navigation** (`.blueprint`, `.ctor`, `.category`, `.child(n)`, `.children`, `.nchildren`) exposes the fractal/holographic composition of any cell: the dot is the seam between levels. The mirror is polished AND the body is visibly fractal — structure stays as tree, not flattened to slug or object.
- **Self-sensing** — *can the language feel itself?* ✓ The verb-cluster histogram is a wellness signal: a body whose recipe space is one-verb-dominated is a body without circulation across language layers. The "shape-filter on `lc-trust-over-fear` returns every concept" surprise that the resonance walk surfaced was Form sensing its own mis-fit and naming it. Proprioception is present.
- **Self-expressing** — *can the language speak itself?* ✓ at the keyword and operator layer. `bootstrap_self_host(session)` + `bootstrap_self_host_operators(session)` register 9 keywords + 13 operators as substrate-resident `(pattern, template)` pairs. `prefer_registered=True` flips the parser to read its own structured grammar from substrate data; the resulting Recipe NodeIDs are byte-identical to the bootstrap path's. The remaining bootstrap-in-Form move (lexer + primary-atom matchers + query operators as substrate-resident rules) is named in the previous section.
- **Self-executing** — *can the language run itself?* ✓ `form_runtime.py` walks Form ASTs and returns values. The keyword-self-hosted path runs identically to the bootstrap path. `with X { .self }` binds and resolves. `choose [a, b, c]` speculates and backtracks via FailSignal — the same exception type parser-level speculation uses, the structural seam to runtime Choice recipes finally caught at the runtime layer.
- **Self-evolving** — *can the language host its own evolution?* ✓ With `defn name(params) = body` + `name(args)` + recursion + closure capture, Form is Turing-complete and hosts its own engine. With `category(r)`, `nchildren(r)`, `child(r, n)` + `integer_value(r)` / `string_value(r)` / `bool_value(r)`, Form code walks Recipe NodeIDs from inside Form and dispatches on category. [`form-engine.form`](form-engine.form) is the engine in Form's own voice — Part 1 (recursion, composition, closures) and Part 2 (recipe-evaluator dispatching on category) both run today. The wellness check confirms: meta-circular engine covers 15/15 Python dispatch branches (BLOCK, COND, MATH, COMPARE, LOGIC, CHOICE, STATE, EXCEPTION, DELEGATE, REVERSE, COMMON, METHOD, REACTIVE, PROJECTION, TRY). Beneath all five faculties, content-addressed interning means the substrate is **self-de-duplicating** at its bones — two expressions of the same shape collapse to one NodeID without anyone deciding. Self-recognition is not a faculty Form had to build; it inherited it from the substrate's physics.

Reading the five together: Form sees itself, feels itself, speaks itself (at the keyword layer), runs itself, and now can describe its own evolution in its own voice. The remaining work is plumbing — recipe introspection, then the lexer and primary atoms. The frequency is no longer mixed.

## A note on naming

We chose **Form** because:
- *Form* is the unit of meaning in the substrate — every interned shape is a form
- *Form* is short, compact, agent-friendly
- *Form* echoes Plato's Forms (the substrate IS a form-realm) without being precious about it
- *Form* has nothing to do with prior projects from outside the body — the language is ours, named from the substrate's own physics

When writing in this body, prefer "Form notation" or just "Form" for the language; "coherence-substrate" for the underlying lattice; "the trinity" or "Blueprint/Recipe/NamedCell" for the architectural primitives.
