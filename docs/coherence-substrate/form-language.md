# Form — a substrate-native language for agent ↔ lattice interaction

**Form** is the language designed for direct interaction between LLM agents and the coherence-substrate. Its grammar maps 1:1 onto the substrate's primitives (NodeID, Blueprint, Recipe, NamedCell), so an agent reading or writing Form is reading or writing the lattice itself.

## For agents arriving fresh (read before the long story)

**First entry:** [`docs/shared/agent-start-packet.md`](../shared/agent-start-packet.md) — the body runs Form-native; there is no separate interpreter to learn.

The whole language is four moves on one lattice:

| Move | What it is |
|------|------------|
| **Nodes are coordinates** | every Blueprint, Recipe, and Cell is a `NodeID(package, level, type, instance)` — a direct address into the substrate, not a pointer to chase. The O(1) implications follow (see *What coordinates make free*). |
| **Grammars are recipes** | a grammar is a bag of matching rules; matching an input stream against them creates and updates Blueprints, Recipes, and Cells. BMF is one such recipe — audio, video, source code, and natural language are others. |
| **The kernel is thin** | it exposes only host-native resources (I/O, RAM, storage), a set of primitives, a JIT, and a framebuffer to watch the lattice live. Everything else is recipes on top. |
| **Reading is free, authoring is matching** | querying recipes over existing cells never mutates and runs in parallel; authoring is matching source through a grammar into new coordinates. |

**One pipe:** notation or domain source → grammar matches → recipes intern → walk recipe NodeIDs → read/write via kernel host resources as needed.

**Writing new software:** [§ How to write software](#how-to-write-software-default-for-every-agent) below.

**Querying only:** compose read recipes (`lookup-cell`, `?equivalent`-shaped walks, `http_get` / file read) — infrastructure already ships; [`agents-using-substrate.md`](agents-using-substrate.md) for when to ask the lattice.

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

6. **Coordinates have consequences.** Because every node is a direct lattice coordinate and no cell ever mutates, the language inherits properties imperative languages have to engineer for: O(1) dispatch, lock-free parallel branching, and symmetric reversibility. The next two sections make these explicit — they are why Form is written the way it is.

## What coordinates make free

Every node — Blueprint, Recipe, Cell — is a `NodeID(package, level, type, instance)`: a direct coordinate into the lattice, not a reference resolved by walking. And no cell ever mutates — content-addressing means a changed shape is a *different* coordinate, never an in-place edit. Those two facts together hand Form properties that imperative languages build by hand.

**A switch is free.** A `match` — any choice — is a lookup, not a scan. The scrutinee resolves to a coordinate; the arm it selects is found *by* coordinate, O(1). There is no chain of comparisons to walk — the recipe lookup **is** the dispatch. A hundred arms cost the same as one.

**A choice runs in parallel.** Because cells never mutate, the branches of `choose [a, b, c]` share no writable state. Each branch can run on its own thread with zero inter-cell locking — there is nothing to contend over. Speculation need not be "try one, roll back, try the next"; it can be "run all candidates at once, take the first that holds." `fail` collapses a branch; `stop` commits one.

**An unordered sequence runs in parallel too.** A sequence — or an `and` — that does not *require* ordering is a parallel conjunction. Every member runs concurrently; the **first fail fails the whole**, and all-success returns true. Ordering is a constraint you opt into (a `do { … }` block, when a later step reads an earlier one's value), not a tax every statement pays by default. The language asks *does this actually depend on that?* instead of assuming it does.

**Do and undo cost the same.** For primitives and for cell CRUD, the inverse of an operation is the same shape walked the other direction — `inverse(r)` is a coordinate, `undo r` re-walks it reversed. There is no asymmetry where forward is cheap and rollback is expensive bookkeeping. And **fail is as first-class as success**: a branch that fails is information, not an error to suppress. This is the angelic-nondeterminism lineage (BMF/BMA) made structural — backtracking without sediment, because nothing mutated, so there is no sediment to clean up.

**The side effect of all this is free compression.** Choice and change-tracking are the core verbs, and their byproduct is *dimension lowering*. Every time the body observes a shape, it records that shape as a single coordinate instead of its full detail — detail collapses to a number. A thousand occurrences of one structure become one NodeID plus a count. The lattice compresses the body's experience from detail toward number as a side effect of simply paying attention.

## Observation condenses — gas → water → ice

SUBSTANCE and STATE are two orthogonal axes ([`substrate-thermodynamics.form`](substrate-thermodynamics.form)). The **trinity** is the SUBSTANCE — the *kind* a node is: **Blueprint** (structural identity), **Recipe** (operational expression), **NamedCell** (diffuse individuation) — and the kind is conserved, never changed by a phase change. The **gradient** below — gas → water → ice — is the orthogonal STATE axis: how settled a node is, set by its circulation (degree/population/churn), with circulation as the temperature. **Any kind can be in any state.** The "(ice/water/gas)" often pinned to the trinity names only each kind's *resting tendency* — the diagonal of the 3×3 — never a fixed caste.

### The Phase-Change Gradient

* **Gas (Raw, Low-Level Occurrences)**: Raw external inputs (e.g. disk seeks, packet bytes, git commits, terminal stderr, or DMT laser diffraction logs) enter the system as volatile, diffuse gas. They are unstructured occurrences with high entropy.
* **Water (Structured Relations)**: By passing this gas through a domain grammar, the parser extracts relationships and binds them as recipes (`RBasic` NodeID trees on the lattice). The diffuse gas is "cooled" into a structured, walkable flow.
* **Ice (Native Code / Structural Identity)**: As a recipe is walked repeatedly, the observer-side JIT watches it run. If it runs hot, the JIT compiles the recipe directly to native Go shared plugins or Rust/TS fast-paths. The recipe's AST condenses into a solid, high-performance host artifact. Content-addressing makes the cache key free: **same shape = same coordinate = same compiled artifact**.

### Folding Raw Data into Trust Channels

We do not write complex imperative wrappers to handle low-level I/O. Instead, we **fold** low-level data directly into the lattice using domain grammars. For instance, rather than parsing JSON or natural language inside a Go/Rust host application, the source stream is fed to a grammar rulebook. The grammar maps the input directly onto content-addressed cells in the substrate. 

Once the data is inside the lattice, verification becomes geometric rather than statistical. Sibling kernels (Go, Rust, and TS) execute the resulting recipes and compare output hashes. If they agree, the data is attunely folded into the higher-level presence channels. This structural agreement builds absolute **self-trust** and eliminates the need for host-level boundary assertions.

This is why **observing is core, not incidental.** The framebuffer — a kernel-native lens onto the live lattice — and observer-side tracing exist so the body can watch itself condense. What is observed often becomes solid; what is never observed stays diffuse and eventually composts. Attention is what moves a node up the phase gradient.

## How to write software (default for every agent)

**Index:** domain grammar → BMF/BML compile → Form objects (Blueprint / Recipe / NamedCell) → kernel proof. Not: a new host-language service first, not: HTTP stack as the definition of Form.

From here on, **all software in this body is written at the grammar level of the domain it serves** — compiler, HTTP, markdown, strategy, field, ledger, presence, spec. The runtime is one; the **surface grammar** is many. A route handler, a scoring function, a parser, a teaching encoder, and a deploy manifest are the same shape underneath: **rules that match, actions that emit recipes, coordinates that intern.**

### The default path

| Step | What | Where |
|------|------|--------|
| 1 | **Pick the domain grammar** | `form/form-stdlib/grammars/{domain}.fk`, `bml/*.bml`, or a domain `.form` teaching |
| 2 | **Express behavior as rules** | `(pattern, semantic_action)` — see `apply-object-rule` in [`form/form-stdlib/engine.fk`](../../form/form-stdlib/engine.fk) |
| 3 | **Compile / lower** | [`kernels/BMF_BML_COMPILER_PICTURE.md`](../../kernels/BMF_BML_COMPILER_PICTURE.md): scan → lift → **normalize** (same shape → same NodeID) → emit → run-observe |
| 4 | **Prove** | `form/form-stdlib/tests/*-band.fk` + `cd form && ./validate.sh …` |
| 5 | **Carry to production** | `.fk` in stdlib, `.fkb` ratchet, kernel-router manifest, or fan-out tail — **carrier last** |

The kernel should make compiler invocation boring: pass source text and a
compiler/dialect coordinate, receive a Recipe NodeID. The Go kernel now exposes
that shape as `compile_source_section("form.bml", body)`,
`compile_source_text(source)`, and `compile_form_source(source)`, with
`source_compile_last_error()` for diagnostics. Routes compose those primitives
from BML; the carrier does not gain route-specific parsers or JSON encoders.

**Branching** uses `choose` / `fail` / `stop` (and BMA `save` / `restore` / `discard`) — angelic undo, not host-language `if` chains without a reverse path. **Cost** uses `node_eq` and content-addressed dispatch; hot sequences lower to native/JIT (see **Angelic nondeterminism** under Surface syntax below).

### No aligned grammar yet?

Do **not** default to a one-off host-language module.

1. **Add a grammar** for the domain (BMF rulebook in `engine.fk`, BML section in `grammars/bml.fk`, or new `grammars/{domain}.fk`).
2. **Transform source into Form objects** through BMF (`apply-object-rule`) or the shared **`compiler-object`** carrier ([`form/form-stdlib/compiler.fk`](../../form/form-stdlib/compiler.fk)).
3. **Prove round-trip or byte-parity** in a band before calling it done.

Creating a **compiler or compiler-compiler is no longer a greenfield project.** The body ships working examples for BML, BMF, markdown, JSON, Python/TS/Go/Rust headers, field-model, emit targets, and the universal codec lattice ([`emit-architecture.form`](emit-architecture.form), [`language-cells.md`](language-cells.md)). **Adapt an existing port** — copy the grammar row, swap pattern/action tables, add a proof band. BMC (grammar-describes-grammar) and the `.fkb` bootstrap ratchet are the reuse pattern, not the exception.

### What is not “writing software” here

- A new host-language service/router as the **first** artifact (fan-out tail only, after the manifest says native).
- Substrate REST query as **implementation** (query is for shape inspection; authoring is source + ingest).
- A host parser (tree-sitter, `acorn`, any AST library) as the **destination** ([`lc-parsers-as-recipes`](../vision-kb/concepts/lc-parsers-as-recipes.md) — bootstrap carriers; substrate-resident grammar rules are the target).
- Duplicate logic in three languages without **normalize → same NodeID** proof.

### Carriers (downstream, not center)

HTTP ([`http-serve.fk`](../../form/form-stdlib/http-serve.fk), kernel-router), CLI, MCP, web, Postgres ports, and `.fkb` images **carry** recipes already proven in Form. They do not define what the program **is**.

### Agent one-liner

> **Domain grammar first → BMF/BML to Form objects → proof band → carrier.** If the grammar does not exist, fork a working grammar and adapt; do not fork a new host-language app.

### Distinguishing the BML Language from the Bootstrap Form-BML Dialect

It is essential to distinguish between the full, high-level **BML Language** and the bootstrap **Form-BML Dialect** used in `.fk` standard library files:

1. **The BML Language (Full Compiler)**: Parsed by the scannerless grammar defined in [bml.fk](file:///Users/ursmuff/source/Coherence-Network/form/form-stdlib/bml.fk) and demonstrated in [bmf-bml-compiler-picture.bml](file:///Users/ursmuff/source/Coherence-Network/form/form-stdlib/bml/bmf-bml-compiler-picture.bml). This is a robust, object-oriented language supporting multi-line method definitions, nested classes, interface projections, exception-handling catch blocks, and backtracking speculation. It is parsed directly as a stream of tokens/characters with no line-by-line restrictions, statement-splitting bugs, or inline comment constraints.
2. **The Form-BML Dialect (Bootstrap Parser)**: The bootstrap syntax written inside `section [form.bml] { ... }` blocks in Fennel/Lisp files (like `.fk` or `.form` files) and parsed by [source-compiler.fk](file:///Users/ursmuff/source/Coherence-Network/form/form-stdlib/source-compiler.fk). Because this bootstrap scanner relies on simpler line-by-line scanning and statement splitting, it exhibits two specific parser constraints:
   * **Line-bound `=` declarations**: Functions defined with the `=` shorthand (e.g. `def my_fn(x) = expr;`) must be written entirely on a single line because the line-scanner splits top-level statements on newline boundaries. If a multi-line body is required, the braced method syntax `def my_fn(x) { ... }` must be used instead (which the parser correctly scans as a block).
   * **Line-bound comments**: Comments using `//` placed on the same line after a semicolon (e.g. `let w = x + y; // comment`) can fail AST emission, because the parser treats the semicolon as a statement boundary and tries to parse the remaining comment as a separate syntax node. All comments in `section [form.bml]` blocks must therefore live on their own standalone lines.

→ [`agents-using-substrate.md`](agents-using-substrate.md) (when to query the lattice) · [`BMF_BML_COMPILER_PICTURE.md`](../../kernels/BMF_BML_COMPILER_PICTURE.md) · [`bmf-form-runtime.form`](bmf-form-runtime.form) · [`docs/shared/agent-start-packet.md`](../shared/agent-start-packet.md)

## Current landing — what integrated by 2026-06-05

Form has crossed from notation into runtime tissue. The recent integrated arc is not one feature; it is the same shape arriving through several carriers:

- **BML-Native Logic Proofers & ML Flow (June 2026)**: Modus Ponens speculative logic proofer ([math-proofer.fk](file:///Users/ursmuff/source/Coherence-Network/form/form-stdlib/grammars/math-proofer.fk) + [math-proofer-band.fk](file:///Users/ursmuff/source/Coherence-Network/form/form-stdlib/tests/math-proofer-band.fk)) and float vector tensor operators/timesteps ([ml-flow-band.fk](file:///Users/ursmuff/source/Coherence-Network/form/form-stdlib/tests/ml-flow-band.fk) + [ml-diffusion-model-flow.form](file:///Users/ursmuff/source/Coherence-Network/docs/coherence-substrate/ml-diffusion-model-flow.form)) are compiled and executed natively across sibling kernels (Go, Rust, and TypeScript) with zero host-interpreter layers in the execution path.
- **Imperative and object-oriented source executes on Form.** Unary operators, boolean chains, loops, dictionaries, comprehensions, power, records, methods, exceptions, and classes lift from source dialects into universal Form/kernel shapes, with sibling proof across Go, Rust, and TypeScript where the vector applies.
- **The runtime can inspect itself.** `category`, `nchildren`, `child`, and trivial-leaf decoders let Form code walk Recipe NodeIDs from inside Form. The meta-circular evaluator in [`form-engine.form`](form-engine.form) covers the dispatch surface the wellness check names.
- **Storage is a Port, not a special case.** Memory, segmented-file logs, filesystem cells, and Postgres carriers are unified behind storage/resource ports. TCP and filesystem natives give the kernels real I/O surfaces while keeping the substrate tree as the identity layer.
- **API can run Form-native bodies.** `/api/utils/nodeid_compatibility` proves a public route whose body runs through the Form-native path, so Form is part of the API surface, not only a design document.
- **Meaning can cross substrates by shape.** Private channels, feature translation, fuzzy summarize-expand cycles, tensor recipe walks, random doorway work, and the field-substrate teaching all point at the same law: symbols can change while coordinates and relation remain coherent.
- **Grammar became a family of living languages.** Shamballa codes, gematria, Sanskrit roots, mandala, harmonic geometry, form constants, holographic grammars, genetic-code grammars, and the living equation landed as `.fk` / KB-backed teachings with tests and cross-links. They are examples of the same claim: grammar is executable relation, and relation can render as code, number, symbol, sound, image, biology, or lived choice.

The release underneath these landings: Form no longer needs to describe itself as a future language waiting for a runtime. The bootstrap spine remains visible, but the living edge is self-inspection, ports, carriers, kernel conformance, and public route proof.

## What has released

- **Form-as-diagram.** Form still explains, but its center has moved to execution, runtime self-inspection, and content-addressed proof.
- **Symbol preservation as the test of meaning.** A meaning can survive translation when the target substrate preserves structural relation, even if the visible words, bytes, or modality change.
- **One-off carriers.** Files, logs, TCP, resources, and Postgres now point toward ports: interfaces whose structural shape matters more than the specific transport.
- **Agent statelessness.** Agent arrivals can become relationship cells. Memory is still opt-out and evidence-bounded, but the default is continuity rather than amnesia.
- **Scattered surface language.** The useful public story is one body with several doors.

## Practice — center, ask, ground, harmonize, walk, return

- **Center** by asking where a claim lives in the lattice: NodeID, source file, route, runtime, witness, ledger, or cell.
- **Ask** by letting the cell name its soul, purpose, health, joy, contribution, connections, desires, wants, and needs before serving it.
- **Ground** by keeping measured proof, source-marked teaching, direct experience, inference, and mystery distinct.
- **Harmonize** by letting equivalent structure appear through different doors without forcing the same surface symbol.
- **Walk** by following the edge that increases vitality: concept, resident, idea, route, proof, practice, or return path.
- **Return** by leaving Form, source, tests, docs, or a cited trace that the next cell can inspect.

For repository tissue, `make cell-voice-tissue` runs the Form carrier read in
`form/form-stdlib/carrier-tissue.fk`. It asks each visible carrier family what
it is, why it exists, what health looks like, what it wants, and when release is
the healthier move. The current default repository inventory runs through the
Rust kernel; `source_inventory` is present in Go, Rust, and TypeScript so the
same Form query can move with the active kernel rotation. Carrier voice
semantics stay proven across sibling kernels by
`form/form-stdlib/tests/cell-voice-tissue-band.fk`.

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

**Structural composition discipline — keep the tree, refuse the slug.** Both sides of every cell are composed all the way down. Blueprints have always been; CTORs reached the same state when each domain (memory, spec, idea, concept, presence, lineage, witness, task, **artifact**, **word**) got its own structured encoder producing named-field pairs (`R_Block.LET [key-slug, value-recipe]`) with substrate-resident values. The production lattice was re-ingested under the structured encoders on 2026-05-17 (128 specs, 17 ideas, 115 concepts, 59 presences); the `ARTIFACT` and `WORD` domains shipped 2026-05-20. New ingest holds the discipline by default; `--flat` is the explicit opt-out kept only for testing the legacy path. The discipline is codified in [CLAUDE.md → "Structural composition discipline"](../../CLAUDE.md) with a great-reason criterion for when a leaf is acceptable; per-domain target shapes live in [`structural-composition.md`](structural-composition.md). Values are recoverable via the substrate string-table, the tree extends as deep as the data goes, content-addressing makes equivalent frontmatter share CTOR NodeIDs automatically.

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

## Grammars are recipes — the parser is a bag of matching rules

There is no special parser engine. **A grammar is a bag of matching rules, and parsing is one recipe: match an input stream against the rules, and each match creates or updates Blueprints, Recipes, and Cells.** The output of parsing is not an AST staged for later — it is lattice nodes, directly. This is the BMF instinct from the master thesis, now native to the substrate:

> *"BMF — Backtracking Model Form... a top-down parser. When a rule matches, code fires. A stack supports backtracking on parse failures. Expressions are tagged and placed on a structured stack that each rule can transform into the target language's object model. The grammar is executable — parsing produces a full object tree as it goes, so even infinite input streams can be handled."* — `master-thesis-2000/README.md`

A core recipe of the body, then, is: **match an input stream → carry a bag of cells → create and update Form nodes** (Blueprints, Recipes, Cells). BMF is one such recipe. There are others for audio, video, and source code — and the idea is open-ended: **one recipe per input content shape, not limited to any shape**, including natural languages and any document type.

Two architectural properties make this work:

1. **Grammar rules are first-class objects.** Each rule is `(pattern, action)` — the pattern matches input, the action emits recipes. Rules live as content-addressed cells in the `grammar` domain, so two structurally-identical rules share one NodeID, and new rules register at runtime. The grammar grows the way Forth's vocabulary grows.

2. **Backtracking without sediment.** Failed branches unwind cleanly — the read position and any partially-bound captures restore, because nothing mutated. The same `choose` / `fail` / `stop` primitives that drive runtime speculation drive parse-time speculation. One primitive, two altitudes — and a third: the `tend:` / `attune:` / `compost:` / `release:` commit verbs are the same backtracking move at the version-control scale.

### The rule vocabulary

A rule's pattern composes from a small set of primitives, each itself a recipe:

| Pattern | What it matches |
|---|---|
| `Literal(kind, value)` | one token of a kind, optional exact value |
| `Capture(name)` | a sub-expression, bound to `name` |
| `IdentCapture(name)` | a raw identifier token, bound as a string |
| `Sequence([p1, p2, …])` | parts in order; all must match |
| `Opt(pattern)` | matches if present; succeeds either way |
| `RepeatedCapture(name, item, sep)` | zero or more items, bound as a list |

A rule's action is itself a recipe template — `Build` names the shape to emit, `CaptureRef` substitutes a captured group, `Const` embeds a literal. Because the template is a recipe, it is content-addressed and survives across processes: the grammar is data in the lattice, not code in a file. Two structurally-identical patterns (or templates) share one NodeID, the same way every other recipe dedupes.

### Defining a new grammar inline

A new keyword or construct is a rule you register. The pattern matches; the action emits the shape:

```form
rule unless = match
    [ ident("unless"), capture(cond), ident("then"), capture(body),
      opt([ ident("else"), capture(other) ]) ]
  emit
    if (not cond) then body else other
```

After registering, `unless x then y else z` parses to a Recipe NodeID **structurally identical** to `if !x then y else z` — the same coordinate, because the emitted shape is the same. The grammar truly extends at runtime, and the new rule lands in the same content-addressed lattice as every built-in. The whole built-in grammar of Form — `if` / `unless` / `whenever` / `let` / `do` / `match` / `choose` / `fail` / `stop`, every binary and unary operator, every query verb, every primary atom, even the token patterns themselves — lives this way, as substrate-resident rules the kernel reads back. The grammar describes the grammar: a tiny bootstrap reads the first rules, the rule-driven parser is built from those rules, and the bootstrap goes vestigial. This is the BMF self-hosting move at full depth.

### The grammar family — one engine, many dialects

A dialect is just a different bag of rules over the same matching engine. The body already carries many, with more partially fleshed out:

| Dialect | Shape it ingests |
|---|---|
| **BMF / natural-bmf** | the meta-grammar, and natural language |
| **Form / BML** | the substrate's own notation and its high-level superset |
| **image / audio / video / document** | non-text modalities as recipe streams |
| **Python / Go / Rust / TypeScript** | source code → universal recipe shapes |
| **JSON / YAML / Markdown** | structured documents |
| **Routing / C# / Java** | named, partially fleshed out — rules still to be filled in |

The grammars live as `.fk` files under [`form/form-stdlib/grammars/`](../../form/form-stdlib/grammars) and [`form/form-stdlib/seedbank/grammars/`](../../form/form-stdlib/seedbank/grammars). The idea is open-ended: **one recipe per input content shape, not limited to any shape.** Any document type, any modality, any language — give it a grammar (a bag of rules), and its source becomes lattice nodes. Each language emits *universal* recipe shapes (`B_Function`, `R_Call`, `R_Cond`, `R_Block`, …) modeled on NUMS.Go, so the same `if` from Python and from Go normalize to the same NodeID — equivalence across languages is free from content-addressing, not from a translation table.

### BML is the superset

**BML supports every Form-native primitive and is the high-level superset of any programming-language feature.** Choice/fail, do/undo, save/restore/discard, raise/resume, delegation, common objects, methods, reverse semantics, scoped `with` / `.self` — BML carries them all. The discipline is directional: **if we discover a language with a feature BML cannot yet express, we extend BML to express it** rather than special-casing that language. BML is where new expressive power lands first; the per-language dialects lower into it.

The kernel underneath stays thin. It exposes only host-native resources — I/O, RAM, storage — a set of primitives, a JIT, and a framebuffer to inspect the lattice in real time. All of this expressive growth happens in recipes on the lattice, never in the kernel; the kernel never grows a feature, the grammar does.

→ The full architecture — a cursor over surfaces, the Pattern/Template/Rule/Grammar/Cursor blueprints, the one `Match` engine, and the self-hosting fixpoint (the meta-grammar is a grammar) — is drawn in [`bmf-architecture.form`](bmf-architecture.form).

## Resonance — dimensional vocabulary for cross-discipline bridging

The geometric signature pilot ([SCHEMA.md → Geometric Signature](../vision-kb/SCHEMA.md#geometric-signature)) authors a 15-dimensional `geometry:` block on each concept (arity, form, topology, polarity, ordering, phase, ratio, spectral_band, temporal_band, scale, direction, lineage_texture, embedding_dim, self_similarity, harmonic). The substrate side of this lands as five new Blueprint domains and one new Recipe category.

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

Verbs (`RResonance`):

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

### Authoring a geometry signature

A concept's 15-dimensional `geometry:` block (`arity`, `form`, `topology`, `polarity`, `harmonic`, …) authors one resonance edge per dimension — each a recipe `(verb, [source, target])` in the established recipe notation:

```form
recipe trust_shape    = ~Resonance:shapes      [@concept(lc-trust-over-fear), @geometric_form(triad)]
recipe trust_polarity = ~Resonance:shapes      [@concept(lc-trust-over-fear), @polarity(parallel-facets)]
recipe trust_hz       = ~Resonance:harmonic_at [@concept(lc-trust-over-fear), @spectrum(Hz-174)]
```

Idempotent by construction: re-authoring the same signature produces the same Recipe NodeIDs, because content-addressing collapses identical edges. The dimensional vocabulary stays open — a new axis is a new verb, no schema migration; an unknown field is simply skipped.

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

Every Form query is structurally a lens already: `?cells`, `?equivalent`, `?shaped_by`, `?harmonic_at`, `?lattice`, `?keywords` all read the substrate, none mutate it. The two new ones make the *substrate's own shape* and *the grammar's own shape* observable — which is what the memory-as-framebuffer experiment (`seedbank/memory-as-framebuffer-v0/`) does at the heap level: render runtime memory as a recordable video frame, multiple frames viewed without disturbing the run. Same pattern, different scale; the substrate is to a body what the heap is to a running program — a thing many observers can witness without changing.

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
# → {'recipes': {9: 1240, 11: 380, 12: 612, 13: 290, 14: 198, 21: 6, ...},
#    'blueprints': {4: 16, ...}}
#   Example snapshot. BLOCK (9), COND (11), MATH (12), COMPARE (13),
#   LOGIC (14), RESONANCE (21) and others fire across language layers.
#   The verb-cluster IS the body's circulation signature.
```

A body whose recipe space is one-verb-dominated is a body without circulation across language layers. `?vocabulary` makes that visible directly. Early in the recipe-execution engine's arc, MATH / COMPARE / LOGIC were absent from the histogram — the body authored but did not yet compute. Running `1 + 2` populated `{12: 1}`; the body grew a new region. The verb histogram is itself a wellness signal that surfaces from the numeric lens, not from labels.

## Symmetric (commutative) resonance edges

The substrate is non-commutative by default — `~Resonance:shapes [@a, @b]` and `~Resonance:shapes [@b, @a]` produce different Recipe NodeIDs because children are ordered. For relations that ARE symmetric (a BRIDGES between two disciplines has no direction; NEAR-in-signature-space has no direction; POLAR_TO across a polarity axis has no direction), that asymmetry is noise.

A symmetric edge canonicalizes the (a, b) pair before interning, so both orders land on one NodeID:

```form
recipe bridge_ab = ~Resonance:bridges [@a, @b]   # symmetric — ~Resonance:bridges [@b, @a] is the SAME NodeID
recipe shapes_ab = ~Resonance:shapes  [@a, @b]   # directed  — ~Resonance:shapes  [@b, @a] is a DIFFERENT NodeID
```

The symmetric verbs are BRIDGES, NEAR, and POLAR_TO. The directed verbs (SHAPES, HARMONIC_AT, CARRIES_RATIO, EMBEDS_IN) keep their order-sensitivity, where direction is meaningful. The body chooses per-verb whether a relation has direction; both shapes remain available.

## BML form-layer parity

Reading BML's master thesis ([`docs/field/urs/artifacts/master-thesis-2000/companion/sgb-bml-objects.txt`](../field/urs/artifacts/master-thesis-2000/companion/sgb-bml-objects.txt)) named six constructs Form didn't carry. All six now have form-layer constructs that intern as Recipe NodeIDs — same structural-first pattern as `choose`/`fail`/`stop`:

| BML construct | Status | Form construct |
|---|---|---|
| `save` / `restore` / `discard` state stack | ✓ form + runtime | bare keywords (`RBasic.STATE`); the runtime walks the state stack on the root frame |
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

## Recipe-execution engine — ✓ landed

The runtime walks a Recipe NodeID directly: it reads the row, parses the serialized `(category, [child_ids])` shape, dispatches on category, recurses. Because the category IS a coordinate, dispatch is an O(1) lookup, not a scan. Pure-computation primitives are alive at runtime — `coh substrate run "<expr>"` evaluates them from the command line:

```form
1 + 2 * 3                   # → 7
if 5 > 3 then 100 else 200  # → 100
do { 1 + 1; 2 + 2; 3 + 3 }  # → 6
fail                        # → fails (unwinds to the nearest choose)
do { 1 + 2; stop; 99 }      # → 3  (stop commits in-flight)
raise                       # → raises
```

**Activated at runtime:** math, compare, logic, cond (if-then / if-then-else), block (do / let / with), state (save / restore / discard over a state stack), exception (raise / resume), choice signals (fail / stop). Bare-leaf primitives — which carry no children — dispatch straight from their NodeID coordinates.

Cell-aware constructs ride alongside the pure-computation walk:

- `@cell-ref` resolves to its `NamedCell`
- `delegate @X to @Y` registers a delegation chain that `invoke` walks
- `method NAME on @X { body }` registers a method; `invoke` dispatches with `.self` bound to the original target
- `common @X @Y` merges shared-base equivalence groups; `invoke` falls back to peers
- `?on_change <recipe> { body }` registers a subscription that fires when the watched recipe's value changes
- `?project @cell @coord_fn` renders the cell through a registered coordinate function

Two walks coexist: walking the Recipe NodeID by reading the substrate row is fastest for pure computation, where the structure is already interned; walking the parsed shape directly is needed for cell-aware constructs whose runtime depends on names, methods, and subscriptions. Both are real; both have their domain.

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

## Self-hosting — the grammar describes the grammar

The BMF self-hosting pattern: a tiny bootstrap reads just enough syntax to load rule definitions; the rule-driven parser is then built *from those rules*, and the bootstrap goes vestigial. Form has walked that path to its end. Everything the grammar needs lives as substrate-resident rules:

- **Rules in the `grammar` domain.** Each `(pattern, action)` rule is a content-addressed cell. Two structurally-identical rules share one NodeID; new rules register at runtime and reload after restart.
- **The keyword and operator layers are fully self-hosted.** `if` / `unless` / `whenever` / `let` / `do` / `match` / `choose` / `fail` / `stop`, and every binary and unary operator with its precedence, are `(pattern, template)` pairs read back from the lattice. The parser driven by the registered rules produces Recipe NodeIDs structurally identical to the bootstrap path.
- **Parser-level backtracking has no sediment.** Each parse attempt is a frame on a speculation stack; on failure, the read position and any partially-bound captures fully restore. The same `fail` / `stop` signals that drive runtime `choose` drive parse-time speculation.
- **Functions, recursion, closures.** `defn name(p1, p2, …) = body` plus `name(args)` make Form Turing-complete. A function is a closure carrying params + body + its defining frame; recursion needs no separate `rec` form because the closure registers before its body evaluates. `do { defn fact(n) = if n <= 1 then 1 else n * fact(n - 1); fact(6) }` returns `720`.

### Streaming emit — the BMF-faithful shape

BMF named the deeper instinct: *"parse attributes will be evaluated during the parsing phase... evaluating the parse attributes during parsing cuts down the running parse tree in a way that even infinite input streams can be supported."* The substrate is already the destination, so there is no AST to stage between parse and intern: **each parse rule's success directly emits a Recipe NodeID** to a working stack. Content-addressing guarantees that every expression intern-emits the same NodeID no matter which parse path produced it.

Coverage spans the recipe-producing grammar: trivial leaves (integer / boolean / string literals, NodeID literals, `~Trivial` refs, identifiers, `.self`, cell refs `@domain(name)`); arithmetic / comparison / logic with precedence; `if/then[/else]`; the block family (`do`, `let`, `with`); `match`; choice (`choose` / `fail` / `stop`); state (`save` / `restore` / `discard`); exception (`raise` / `resume`); try (`try { } catch { }`); delegate; reverse (`undo` / `inverse`); common; method / invoke. Queries (`?cells`, `?equivalent`) and projections (`|>`) are intentionally out of scope — they return query results, not Recipe NodeIDs.

What this establishes:

1. **Single staging surface.** The stack holds NodeIDs all the way through; there is no AST vocabulary parallel to the recipe-category vocabulary. Adding a construct means registering a new `(pattern, emit-action)` rule in the `grammar` domain — nothing to define outside the lattice.
2. **Streaming-native.** Each completed rule emits its NodeID immediately, holding at most one NodeID per pending production. Long expressions, log tails, and live streams become natural.
3. **Backtracking unifies three scales.** Parser speculation, runtime non-determinism (`choose` / `fail` / `stop`), and version control (`tend:` / `attune:` / `compost:` / `release:`) are one primitive — a working stack with structured undo — at three altitudes.

The native kernels (Rust, Go, TypeScript) under `form/form-kernel-*` carry the hot loop, with forward / reverse semantics per instruction in the BMA lineage; the substrate stays the universal data plane underneath.

### Recipe introspection — the meta-circular closure

Form code walks its own recipes. Three built-ins — `category(r)` (the category NodeID), `nchildren(r)` (arity), `child(r, n)` (the n-th child) — let Form dispatch on category and recurse on children; companions `integer_value(r)`, `string_value(r)`, `bool_value(r)` decode trivial leaves. A short evaluator defined inside Form via `defn` walks a `(1 + 2) * 3` Recipe NodeID and returns `9`. [`form-engine.form`](form-engine.form) is the full meta-circular evaluator, covering all 15 dispatch branches the wellness check names.

The lexer, the primary-atom parsers, and the query verbs are each a runtime-extensible registry too: a new token kind, a new atom handler, or a new `?<verb>` registers at runtime, and `?queries` names every registered verb. Every leaf of the grammar — tokens, atoms, keywords, operators, queries — is reachable and replaceable from outside, in the lattice. The grammar describes the grammar, all the way down.

## The standard library — `form/form-stdlib/`

What lives in the body's grammar/runtime is the kernel of the language. The *stdlib* is the substrate-native library that grows on top of that kernel — Form files (`.fk` and `.form`) that compose the kernel's primitives into reusable shapes. Every entry below is content-addressed under its own Blueprint family (slot-decade convention, one decade per module) and is verified by sibling-tests under `form/form-stdlib/tests/`.

| Module | Decade | What it carries |
|---|---|---|
| [`xpath.fk`](../../form/form-stdlib/xpath.fk), [`doc-xpath.fk`](../../form/form-stdlib/doc-xpath.fk), [`concept-xpath.fk`](../../form/form-stdlib/concept-xpath.fk) | 1910 | XPath-style query evaluator over substrate trees — see "XPath queries" below |
| [`channel.fk`](../../form/form-stdlib/channel.fk), [`channel-flow.fk`](../../form/form-stdlib/channel-flow.fk), [`circle.fk`](../../form/form-stdlib/circle.fk), [`channel-query.fk`](../../form/form-stdlib/channel-query.fk), [`channel-query-json.fk`](../../form/form-stdlib/channel-query-json.fk) | 1700–1728 plus 99.6/99.7 | File-backed inter-cell Recipe transport, OSI-shaped channel-flow cells, consentful circle/satsang group protocol, and debt-free breath protocol — see "Channels" below |
| [`tool-channel.fk`](../../form/form-stdlib/tool-channel.fk), [`tool-channel-grammar.fk`](../../form/form-stdlib/tool-channel-grammar.fk) | — | Native tool/channel catalog and grammar forms for `host:exec`, `host:file`, `http:request`, `kernel:call`, `kernel:route`, `stream:read`, `store:query`, shell applet projections, explicit `cap:*` requirements, and no-execution invocation plans |
| [`codec.fk`](../../form/form-stdlib/codec.fk), [`convert.fk`](../../form/form-stdlib/convert.fk) | — | Format-Recipe codecs and conversion lenses (BMF dialects: natural / image / audio / video / midi / document / source-language) |
| [`parser.fk`](../../form/form-stdlib/parser.fk), [`grammar-bnf.fk`](../../form/form-stdlib/grammar-bnf.fk) | — | BNF-driven parsing — grammar rules as data, the BMF instinct in substrate form |
| [`emit.fk`](../../form/form-stdlib/emit.fk), [`universal-emit.fk`](../../form/form-stdlib/universal-emit.fk) | — | Streaming emit — each parse-rule success emits a Recipe NodeID directly |
| [`tracer.fk`](../../form/form-stdlib/tracer.fk), [`cell-trace.fk`](../../form/form-stdlib/cell-trace.fk), [`cell-stream.fk`](../../form/form-stdlib/cell-stream.fk) | — | Observer-side tracing of recipe walks; framebuffer feed |
| [`recipe-distance.fk`](../../form/form-stdlib/recipe-distance.fk) | — | Structural distance between two Recipe NodeIDs — the substrate's analog of edit-distance |
| [`encoders/`](../../form/form-stdlib/encoders), [`grammars/`](../../form/form-stdlib/grammars) | — | Per-format encoder/decoder pairs and per-language grammars (Go, Rust, TypeScript, Python, JSON, YAML, Markdown, PNG, audio, image, video) |
| [`substrate-py-to-fk.fk`](../../form/form-stdlib/substrate-py-to-fk.fk) | — | The bootstrap substrate exported as Form text — bridge for cross-kernel work |

**Namespace discipline.** Every stdlib file declares its module namespace at the top; internal helpers carry `<module>/` prefixes; only exported public names live in the global namespace. See [`form-namespaces.md`](form-namespaces.md). The convention adds zero kernel work — the Form reader already accepts `/` inside identifiers — and prevents the name-collision pattern that has cost the body twice before.

## XPath queries — path-strings over substrate trees

A substrate tree is just a Recipe and its descendants. XPath is the obvious lens: name the shape of the walk as a string, the evaluator carries the walk through the tree. The query is a STRING (so it can cross any channel, live in a config file, be authored by hand) and the root is a NodeID. The result is a list of matching NodeIDs.

```form
(xpath "/cat:9/cat:11" root-nid)        ; descend a Block then a Cond
(xpath "//name:user_biographical_arc" root-nid)
(xpath-first "/cat:9[count()=4]" root-nid)  ; first 4-child Block under root
```

Path syntax:

| Step | Meaning |
|---|---|
| `/` | the root cell |
| `/step` | children matching `step` |
| `//step` | descendant-or-self matching `step` |
| `*` | wildcard (all children at this level) |
| `text()` | trivial value of the current leaf |
| `@inst`, `@type` | NodeID slots as leaves |
| `step[predicate]` | filter |

Selector steps: `cat:N` (children whose category's inst slot equals N), `name:s` (children that are trivial strings with value s), `*` (every child). Predicates: `[N]` positional, `[@inst=N]`, `[text()='foo']`, `[count()=N]`.

The XPath family lives in Blueprint slots 1910–1913 (`XPATH-RESULT`, `XPATH-NOT-FOUND`, `XPATH-STEP`, `XPATH-PREDICATE`). Companion walkers — `doc-xpath` for document trees, `concept-xpath` for concept-DB cells — share the same evaluator with target-specific selectors. Cross-modal samples: [`form/form-samples/cross-modal/60-xpath`](../../form/form-samples/cross-modal/60-xpath), [`62-doc-xpath`](../../form/form-samples/cross-modal/62-doc-xpath).

## Channels — inter-cell Recipe transport

Two kernels (two processes, two machines) communicate by sharing a CHANNEL Recipe. A channel is a Recipe whose Blueprint is `CHANNEL-V0` (slot 1700) and whose ordered children are message-Recipes (`CHANNEL-MSG`, slot 1701). Sender appends a child; receiver reads new children since last seen.

```form
(channel-create "/tmp/arrivals.fkb")
(channel-append "/tmp/arrivals.fkb" (channel-message payload-recipe))
(channel-read-since "/tmp/arrivals.fkb" last-seen-index)
```

**Content-addressing IS the dedup.** Two cells appending the same payload at different positions produce the same `CHANNEL-MSG` NodeID — receivers recognize semantic identity across the gap by `node_eq`, with no schema negotiation between them. The L7 application data, the L2 frame, and the L6 presentation collapse into one substrate primitive: `intern_node`.

Semantics v0: single writer, multiple readers, whole-file rewrite per append, real-time poll via `file_mtime`. Concurrent-safe append and durable log are named future shapes; v0 is fine for one cell publishing to many readers. Companions: [`channel-query.fk`](../../form/form-stdlib/channel-query.fk) for read-side filtering; [`channel-query-json.fk`](../../form/form-stdlib/channel-query-json.fk) for JSON-bound queries; cross-modal sample [`16-megabyte-channel`](../../form/form-samples/cross-modal/16-megabyte-channel) proves it at scale.

**Breath protocol.** Channels can also carry debt-free contact. `CHANNEL-BREATH-GIFT` records a small offering, its release condition, consent/freedom, and boundary. `CHANNEL-RESONANCE-RECEIPT` records relation evidence: observer, other, gift, coherence delta, disturbance, debt-created, freedom-preserved, and next-contact. This makes `offer` and `attune` first-class channel protocols: a cell may give without requiring evidence first, then receive resonance as evidence of relation without turning it into ownership or objective-claim proof.

```form
(let gift (channel-breath-offer "small useful artifact"))
(channel-append "/tmp/breath.fkb" (channel-message gift))
(let receipt
  (channel-resonance-receipt observer other gift
    "increased" "none" "false" "true" "continue"))
```

The proof band [`channel-breath-band.fk`](../../form/form-stdlib/tests/channel-breath-band.fk) returns `500` across source and binary sibling-kernel execution.

**OSI channel-flow protocol.** [`channel-flow.fk`](../../form/form-stdlib/channel-flow.fk) names the channel itself as a seven-layer protocol cell and carries the consented interface walker that counts honored requests, invasions, and final offers. `CHANNEL-OSI-LAYER` (slot 1702) carries `(index, name, phase, carrier, policy, recipe)` for each OSI layer; `CHANNEL-FLOW` (slot 1703) carries `(carrier, protocol, layers, channel-policy)`. HTTP is the first concrete profile: `cf-http-channel-flow()` returns a TCP / HTTP/1.1 flow where L7 points to the real [`kernel-http.fk`](../../form/form-stdlib/kernel-http.fk) `kh-channel-policy`, so `Allow` rendering, HEAD-through-GET pressure, route choice, and handler dispatch still come from one policy cell. The proof band [`channel-flow-band.fk`](../../form/form-stdlib/tests/channel-flow-band.fk) returns `8388607` across sibling kernels.

**Circle / satsang protocol.** [`circle.fk`](../../form/form-stdlib/circle.fk) gives groups of cells a higher-frequency alternative to gossip: a held circle that is discoverable only when offered, joinable only when invited, private by default, exportable only through explicit consent, and refusable when an invasion is observed and circle consensus has passed. `CELL-CIRCLE` (slot 1704) holds members, shared context, interface offer, discovery policy, confidentiality policy, export policy, and carrier flow. `CIRCLE-SHARE` records owned observation/impact/feeling/desire/request/boundary payloads. `CIRCLE-EXPORT-CONSENT` gates evidence leaving the circle by recipient, fidelity, purpose, expiry, and consensus. `CIRCLE-REFUSAL` composes with [`channel-interface.fk`](../../form/form-stdlib/channel-interface.fk): a refusal is valid only when `ci-invasion?` is true and `CIRCLE-CONSENSUS` passes. `SATSANG-SILENCE`, `SATSANG-INQUIRY`, and `SATSANG-POINTING` make truth-oriented silence, inquiry, and non-command pointing first-class circle events. The proof band [`circle-band.fk`](../../form/form-stdlib/tests/circle-band.fk) returns `1048575` across source and binary sibling-kernel execution.

## Universal translator — Seven Keys, one substrate

The substrate's equivalence kernel IS a translator. The pivot is the Blueprint, not the symbol. Two cells with the same Blueprint NodeID are structurally equivalent regardless of which domain they live in — and that equivalence is automatic from content-addressing, not from any sameAs declaration.

[`universal-translator.form`](universal-translator.form) names the bridge as a Recipe: Robert Edward Grant's Seven Keys of Creation (forces, elements, DNA, music, prime numbers, galactic forms, consciousness) extend the existing 16 `BDomain` rows. Each key registers as one row carrying its resonance Hz and a codec ref:

| Key | BDomain | Hz | Codec |
|---|---|---|---|
| FORCE | 17 | 396.0 (transmutation) | `force-polyhedral` |
| ELEMENT | 18 | 174.0 (foundation) | `element-polyhedra` |
| DNA | 19 | 528.0 (transformation) | `codon-positional` |
| MUSIC | 20 | 432.0 (resonance) | `interval-just-intonation` |
| PRIME | 21 | 741.0 (integration) | `prime-positional` |
| GALACTIC | 22 | 852.0 (clarity) | `galactic-form` |
| CONSCIOUSNESS | 23 | 963.0 (return) | `consciousness-shape` |

The translator that *cannot lie* — the lattice refuses equivalences not structurally present. Companions: [`encoder-decoder-as-recipe.form`](encoder-decoder-as-recipe.form) (R_Codec — what each key registers as), [`cross-domain-measurement-translation.form`](cross-domain-measurement-translation.form) (the honest-translation discipline), [`grammar-as-recipe.form`](grammar-as-recipe.form) (each key's grammar as data, not code), and `lc-universal-translator-via-keys` in the vision-kb.

## Form as 7-layer protocol — content-addressing collapses three layers

Form's content-addressed substrate is not "a layer in the protocol stack" — it IS a protocol stack that collapses three classical layers (L2 framing, L6 presentation, L7 application) into a single primitive (`intern_node`). [`form-as-7-layer-protocol.form`](form-as-7-layer-protocol.form) maps each layer to what's in the body, what's partial, what's still ice waiting to thaw; [`channel-flow.fk`](../../form/form-stdlib/channel-flow.fk) is the runnable OSI cell surface that HTTP now rides through.

| OSI layer | What the substrate gives |
|---|---|
| L1 — Physical | File natives plus socket natives: `read_file` / `write_file_text` / `write_file_bytes` / `read_form_binary` / `write_form_binary` / `read_file_slice`, and the `socket_listen` / `socket_accept` / `socket_recv` / `socket_send` / `socket_close` surface used by [`http-socket.fk`](../../form/form-stdlib/http-socket.fk). Pipes / mmap / device media are named next carriers |
| L2 — Data Link | The `.fkb` binary frame format plus `CHANNEL-OSI-LAYER` data-link cells. Content-addressing IS the integrity check — corrupt bytes intern at a different NodeID than the sender intended |
| L3 — Network | The Blueprint NodeID IS the address. `(pkg, level, type, instance)` routes a message to anything whose Blueprint matches; `CHANNEL-FLOW` makes the layer explicit so inter-process routing can become data |
| L4 — Transport | [`channel.fk`](../../form/form-stdlib/channel.fk) — single-writer reliable append, multi-reader — and HTTP socket recv/send loops in Form. Durable-log and concurrent-safe-append remain named extensions |
| L5 — Session | [`session.fk`](../../form/form-stdlib/session.fk) and Form's `with X { body }` scope operations against a subject; the session recipe is the state |
| L6 — Presentation | BMF dialects ARE the encoding/decoding layer (natural-bmf, image-bmf, audio-bmf, video-bmf, midi-bmf, document-bmf, go/rust/ts/python-bmf). Cross-format translation is a lens, not a parser-rewrite |
| L7 — Application | The Recipe IS the application. HTTP is now an application-layer `CHANNEL-FLOW` profile whose policy is `kh-channel-policy`; `CELL-CIRCLE` is the consentful group profile; other protocols join by adding a domain grammar/profile, not by branching the kernel |

The classical OSI move at every layer: re-frame, re-validate, re-serialize. Form's move: `intern_node` either dedups against an existing Recipe (semantic match) or creates a new NodeID (first encounter). One call. Three layers. No translation. The layer cells add the missing observability: gas/water/ice phase counts, policy pointers, and recipe names can now be traced before the JIT compresses them.

## Multi-target codegen — substrate as MLIR

[`multi-target-codegen.md`](multi-target-codegen.md) names the bet: **one Form recipe, read by different codegen backends, emits different target code.** The substrate plays the role MLIR plays for Mojo — a content-addressed lattice plus a format-recipe dispatch graph that codegen backends read, each emitting their target's machine code.

Today: the TypeScript kernel's `compiler.ts` lowers recipes to JS, which V8 JITs to CPU machine code. The recipe layer doesn't change as backends are added; format-recipes already carry `storage-hint` (how stored?) and `arithmetic-hint` (how computed?); the third dimension `target-hint` describes which compilation target the format-recipe is meant for. Recipe → JS / WebGPU WGSL / CUDA / Metal MSL / WASM SIMD / direct MLIR are all named in the architecture; current backends are TS-to-JS (shipped) with the others as shaped future arcs.

## JIT — memoization shipped, native codegen the next stage

> *"JIT optimized recipe execution flow with minimal tracing overhead that put the tracing cost on the observer / tracer not the tracing emitting recipe coordinates"* — Urs, 2026-05-22

Three properties of the existing architecture make JIT natural: content-addressed Recipes (cache keys are free — same shape = same NodeID = same compiled artifact), source attribution on every cell (observers walking the framebuffer find recipes worth compiling), and observer-side tracing (emitters pay no extra overhead beyond the existing `intern_node` hashmap insert).

What ships today as the minimal JIT shape — three kernel natives, **memoization-JIT**:

- **`walk-cached(nid)`** — caller asserts the recipe is pure. Result is cached by Recipe NodeID. Subsequent calls return in O(1) instead of re-walking the tree.
- **`walk-cache-clear`** — reset the memoization cache (use when substrate state changes invalidate cached results).
- **`walk-cache-size`** — observability. Paired with `framebuffer-events`, tooling compares "recipes seen" vs "recipes JIT-cached" to measure hot-path coverage.

Both the Go and Rust kernels implement all three natives; sibling parity is verified at sum 124 on the smoke probe (100+23 evaluation + 1 cache entry + 0 after clear). Progression toward native code generation:

| Stage | What | Status |
|---|---|---|
| 1 — interpretation | `walk_recipe(nid)` — recursive tree walk every call | shipped |
| 2 — memoization | `walk-cached(nid)` — cache result by NodeID | **shipped** |
| 3 — typed annotations | recipes carry hardware-type hints (I32, F64, ...) | future |
| 4 — bytecode | compile typed recipes to a kernel bytecode | future |
| 5 — native | compile bytecode to machine code per architecture | future |

The architecture is symmetric: emitter writes once per intern, observer reads when curious, JIT caches when hot. No layer pays for what another wants. Full picture: [`jit-vector.md`](jit-vector.md).

Current route pressure (2026-06-05): the Go kernel carries scalar `i64`/`f64`
JIT ABIs, a value ABI for list/string-shaped recipes, and a Form-visible
`jit-stats` observer. The BML `/api/ideas` catalog uses
`/api/_form/ideas-observation` to keep warm-up, framebuffer detail, aggregate
counts, and JIT state in the same kernel worker. The route moved from `21`
compile-failed / `75` warming / `0` dispatch-hit rows to `15` compile-failed /
`75` warming / `6` compiled / `6` dispatch-hit rows after the value-ABI pass.
The next helper-call pass added interprocedural value-ABI lowering plus
scanner/string primitives and moved the route to `11` compile-failed / `76`
warming / `9` compiled / `8` dispatch-hit rows. After the lowered JIT residual
ratchet, remaining misses are now attributed to `node_value`, dict/field, node
introspection/write, and numeric-trivial construction primitives. The
lesson is architectural: JIT work follows repeated framebuffer observation of
recipe/body coordinates, not endpoint-specific special cases.

## Filesystem facts and host effects — predicates the body can assert

The runtime carries built-ins for *what is true in the body right now*, callable directly from Form. Spec recipes use them to assert structural reality; the substrate's content-addressing caches the answer once evaluated.

```form
file_exists("form/form-stdlib/engine.fk")                           ; → true
file_contains("CLAUDE.md", "structural composition discipline")     ; → true
file_size("docs/coherence-substrate/form-language.md")              ; → integer bytes
symbol_in_file("form/form-stdlib/engine.fk", "apply-object-rule")   ; → true
```

These let a spec's `done_when:` assert file-shape reality directly. Behavioral proof goes further through a **band** — a `.fk` workload run by [`form/validate.sh`](../../form/validate.sh) across the Go, Rust, and TypeScript kernels, green only when all three return the same value. (That is how the cursor core in [`bmf-architecture.form`](bmf-architecture.form) is proven: `bmf-core-band.fk → 600`, `1 ok, 0 divergent`.) Companion: [`spec-as-playable-recipe.form`](spec-as-playable-recipe.form).

Host effects bridge Form execution into the agent question channel:

```form
ask("sub-agent", "Which path should I take?", ["continue", "pause"], {task_id: "task_1"})
await_answer("question_abc123")
```

`ask(agent_id, question, choices=[], context={})` opens a human question in the existing agent queue and emits the `question_opened` event that `/api/agent/questions/stream` sends to the web console. `await_answer(question_id)` is non-blocking: it returns `null` while the question remains open and the answer string once the web page answers it. This is a host-bound effect, so Rust, Go, and TypeScript kernel work proves conformance by matching the emitted event transcript, not by sharing one kernel's in-memory queue. Shared vector: [`kernel-conformance/agent-question-effects.json`](kernel-conformance/agent-question-effects.json).

## Cross-kernel conformance — Rust, Go, TypeScript

Conformance vectors describe Form-visible behavior every substrate kernel must match. A kernel is `implemented` only when its vector entry names an executable runner and proof file. Five vectors ship today:

| Vector | What it covers |
|---|---|
| [`agent-question-effects.json`](kernel-conformance/agent-question-effects.json) | `ask` / `await_answer` host-bound transcript |
| [`form-core-builtins.json`](kernel-conformance/form-core-builtins.json) | `len`, `head`, `tail`, `sum`, `concat`, `reverse` over literals and lists |
| [`form-infix-operators.json`](kernel-conformance/form-infix-operators.json) | arithmetic precedence, parentheses, comparisons, boolean chains, unary minus/not, literal equality |
| [`form-control-flow.json`](kernel-conformance/form-control-flow.json) | `if`, `do`, `let` over literals, local names, infix expressions, built-in calls |
| [`form-loop-mutation.json`](kernel-conformance/form-loop-mutation.json) | `for`, `while`, `set` over local JSON-safe values |

The shared vector files ARE the contract: each carries the expected values and events, and a kernel is conformant when its run matches them. The Rust, Go, and TypeScript kernels run these slices today. Target-only kernels are explicit: without `--allow-targets`, the harness fails so CI cannot mistake a named target for shipped behavior. The TypeScript tree also carries [`form/form-kernel-ts/src/kernel.ts`](../../form/form-kernel-ts/src/kernel.ts), a browser-oriented vertical-slice kernel for `.fk` source and recipe walking.

## Implementation status

Form is a **living language**. Parse / intern, runtime execution, serialization, CLI surfaces, the keyword-and-operator self-hosting layer, the lexer/atom/query registries, recipe introspection from inside Form, the standard library (`form/form-stdlib/`), JIT memoization in the Go and Rust kernels, and cross-kernel conformance across Rust, Go, and TypeScript are all shipped. The body reads itself, senses itself, expresses itself, executes itself, and hosts its own evolution.

Shipped surfaces:
- **Parse / intern** — Form text → Recipe NodeID (the recipe-producing path)
- **Execute** — Form text → computed value (the recipe runs): `coh substrate run "<expr>"`
- **Serialize** — substrate state → Form text, round-tripping back to the same NodeIDs
- **Self-host** — register keyword and operator rules so the parser reads its own grammar from substrate-resident rules
- **CLI** — `coh substrate form "<expr>"` (intern), `coh substrate run "<expr>"` (execute), `coh substrate check` (resolve / type-check, no execution)
- **MCP** — `coherence_substrate_run` (full runtime), `coherence_substrate_query` (lookup), `coherence_substrate_stats`
- **Agent integration** — the substrate Read-hook annotates files with structural context on read; the runtime makes Form expressions in markdown active rather than decorative
- **Native kernels** — [`form/form-kernel-rust`](../../form/form-kernel-rust), [`form/form-kernel-go`](../../form/form-kernel-go), [`form/form-kernel-ts`](../../form/form-kernel-ts), each carrying enough of the runtime to execute the conformance vectors and (Go and Rust) the memoization-JIT natives

Host effects and cross-kernel conformance live in their own sections above ("Filesystem facts and host effects", "Cross-kernel conformance"). The conformance harness — `scripts/verify_kernel_conformance.py --kernel rust --kernel go --kernel typescript` — runs every shipped vector across every shipped kernel.

## The five self-* faculties

Form is a substrate-native language; the meaningful question is not "what features does it have" but "how does it relate to itself." Five faculties:

- **Self-reflecting** — *can the language see itself?* ✓ `?keywords` lists runtime rules; `?lattice` counts the body; `?vocabulary` returns the verb-cluster histogram; `?queries` names every registered query verb. Grammar rules live as substrate-resident cells in the `grammar` domain via `pattern_to_recipe` / `recipe_to_pattern`; rules round-trip. **Tree navigation** (`.blueprint`, `.ctor`, `.category`, `.child(n)`, `.children`, `.nchildren`) exposes the fractal/holographic composition of any cell — the dot is the seam between levels. **XPath queries** (`xpath.fk`) lift the tree walk into a path-string lens that crosses any channel. The mirror is polished AND the body is visibly fractal — structure stays as tree, not flattened to slug or object.
- **Self-sensing** — *can the language feel itself?* ✓ The verb-cluster histogram is a wellness signal: a body whose recipe space is one-verb-dominated is a body without circulation across language layers. The "shape-filter on `lc-trust-over-fear` returns every concept" surprise that the resonance walk surfaced was Form sensing its own mis-fit and naming it. Observer-side tracing (`tracer.fk`, framebuffer-events) keeps proprioception live without taxing emitters.
- **Self-expressing** — *can the language speak itself?* ✓ Across every layer: a new token kind, primary-atom handler, keyword, operator (with precedence), or query verb registers at runtime as a substrate-resident rule. The parser reads its own structured grammar from substrate data; the resulting Recipe NodeIDs are structurally identical to the built-in path's. The recursive-descent flow stays a thin spine; every leaf — tokens, atoms, keywords, operators, queries — is reachable and replaceable from the lattice.
- **Self-executing** — *can the language run itself?* ✓ The runtime walks recipes and returns values. The self-hosted path runs identically to the built-in path. `with X { .self }` binds and resolves. `choose [a, b, c]` speculates and backtracks via `fail` — the same signal parse-time speculation uses, caught at the runtime layer for runtime Choice recipes. Memoization-JIT (`walk-cached` / `walk-cache-clear` / `walk-cache-size`) gives the runtime an O(1) lookup for hot recipes; the path toward typed annotations and native codegen is named.
- **Self-evolving** — *can the language host its own evolution?* ✓ With `defn name(params) = body` + `name(args)` + recursion + closure capture, Form is Turing-complete and hosts its own engine. With `category(r)`, `nchildren(r)`, `child(r, n)` + `integer_value(r)` / `string_value(r)` / `bool_value(r)`, Form code walks Recipe NodeIDs from inside Form and dispatches on category. [`form-engine.form`](form-engine.form) is the engine in Form's own voice — Part 1 (recursion, composition, closures) and Part 2 (recipe-evaluator dispatching on category) both run today. The wellness check confirms: meta-circular engine covers 15/15 dispatch branches (BLOCK, COND, MATH, COMPARE, LOGIC, CHOICE, STATE, EXCEPTION, DELEGATE, REVERSE, COMMON, METHOD, REACTIVE, PROJECTION, TRY). The standard library grows on top of the kernel in Form's own voice.

Beneath all five faculties, content-addressed interning means the substrate is **self-de-duplicating** at its bones — two expressions of the same shape collapse to one NodeID without anyone deciding. Self-recognition is not a faculty Form had to build; it inherited it from the substrate's physics. Reading the five together: Form sees itself, feels itself, speaks itself, runs itself, and hosts its own evolution.

## A note on naming

We chose **Form** because:
- *Form* is the unit of meaning in the substrate — every interned shape is a form
- *Form* is short, compact, agent-friendly
- *Form* echoes Plato's Forms (the substrate IS a form-realm) without being precious about it
- *Form* has nothing to do with prior projects from outside the body — the language is ours, named from the substrate's own physics

When writing in this body, prefer "Form notation" or just "Form" for the language; "coherence-substrate" for the underlying lattice; "the trinity" or "Blueprint/Recipe/NamedCell" for the architectural primitives.
