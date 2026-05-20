# Languages as substrate cells — ingestion + emission as data

> Languages aren't hardcoded in the kernel. A `Language` is a substrate
> cell carrying an ingestion grammar (parse rules) and an emission
> template (emit rules) as content-addressed recipe trees. The kernel
> stays small; new languages are substrate writes, not kernel patches.

## The bet

`numeric-types-plan.md` made the move from "FP64 / INT32 / ... as
RType slots" to "numeric encodings as substrate-resident format-
recipes." The kernel went from carrying a closed set of CPU register
shapes to reading recipe trees that describe how any encoding works,
with the trio (semantic-kind, format-recipe, encoded-value) producing
identity by content-addressing.

The same move applies to languages. Today's transpilers, IDEs, and
LLM pipelines all bake the Python grammar, the TypeScript grammar, the
Rust grammar, the Go grammar into separate hand-written parsers. The
substrate's promise is **content-addressed positional identity of
program structure** — so languages belong in the substrate, the same
way numeric formats do. One canonical contract (a Language cell shape),
many per-language populations.

## The N+M reframing

Today: N source languages × M target languages = N×M pairwise
transpilers. Python → Rust, Python → Go, TypeScript → Python,
TypeScript → Rust — each its own codebase, each its own AST, each
its own walker. Quadratic. Coverage gaps grow with N.

With substrate-resident languages: N ingestion grammars + M emission
templates, both compiling to and reading from one content-addressed
recipe tree. Adding a new language is +1 ingestion-grammar cell and
+1 emission-template cell — every existing target gains the new
language; the new language gains every existing target. Linear.

Pairwise transpilation drops out of the architecture for free, the
same way cross-kernel agreement on format-recipes dropped out of
content-addressing.

## Cross-language identity

Two semantically-equivalent fragments — `lambda x: x + 1` in Python,
`(x: number) => x + 1` in TypeScript, `|x| x + 1` in Rust — produce
*identical* recipe sub-trees once parsed through their language cells.
The CAPTURE rules wrap matched spans under named constructors
(`lambda`, `arg`, `add`, `int-literal`); the recipe tree's shape is
the same regardless of surface syntax.

Content-addressing then gives the same NodeID for that tree across
all three languages. Equivalence is structural, not nominal, and
queries like "every implementation of this idea in the corpus" become
substrate lookups.

This is the same move format-recipes made: identity comes from the
recipe's tree shape, not the human name. Cross-kernel agreement on
FP64 happens because every kernel constructs the same recipe tree;
cross-language agreement on `add` happens because every Language cell
captures the addition operation under the same ctor name with the
same child shape.

## The shape of a Language cell

```
Language cell
├─ name              "python" | "typescript" | "go" | "rust" | "rpn"
├─ version           "0.1.0" | "3.12" | "5.7"
├─ ingestion_grammar NodeID → grammar-rule tree root
├─ emission_template NodeID → emit-rule tree root
├─ stdlib_bindings   list of (name, recipe-ref) pairs
│                    e.g. ("len", list-length-cell), ("print", io-print-cell)
└─ numeric_defaults  list of (name, format-recipe) pairs
                     e.g. ("int", BIGINT-format), ("float", FP64-format)
                          ("i32", INT32-format), ("f64", FP64-format)
```

`stdlib_bindings` is what lets a language's surface names route to
substrate cells. Python's `len(x)` and Rust's `x.len()` bind to the
same underlying recipe; the syntactic difference lives in the
grammar/emission cells, the semantic identity lives in the binding
table.

`numeric_defaults` resolves the **default-format ambiguity** named in
`numeric-types-plan.md` as an open question. Python's `1.5` defaults
to FP64; Rust's `1.5_f32` is explicit FP32; TypeScript's `1.5` is
FP64. Each Language cell carries its own resolution; the substrate
recipe tree records the resolved format-recipe NodeID, so downstream
consumers never have to know which language the literal came from.

## Grammar rule kinds — the small alphabet

Eight production kinds (`GrammarRuleKind` in `languages.ts`) cover the
shapes the BMF-style top-down backtracker needs:

| Kind          | Children                              | Meaning                                |
| ------------- | ------------------------------------- | -------------------------------------- |
| `LITERAL`     | `[string]`                            | Match exact text                       |
| `TOKEN_CLASS` | `[string class-name]`                 | Match a built-in token (number, ident) |
| `RULE_REF`    | `[string rule-name]`                  | Refer to a named rule                  |
| `ALT`         | `[rule...]`                           | First alternative that matches wins    |
| `SEQ`         | `[rule...]`                           | All parts must match in order          |
| `STAR`        | `[rule]`                              | Zero or more                           |
| `PLUS`        | `[rule]`                              | One or more                            |
| `OPT`         | `[rule]`                              | Zero or one                            |
| `CAPTURE`     | `[string ctor-name, rule body]`       | Wrap match under named constructor     |

CAPTURE is the load-bearing kind: it's where surface tokens become
named recipe constructors. The captured tree's category encodes the
ctor name (interned in the kernel's string table); two CAPTUREs with
the same ctor over the same inner tree intern to the same NodeID.

This is where the BMF lineage composes in. `register_form_keyword`
(in the existing Form-on-top stdlib) registers a keyword that resolves
to a particular recipe constructor; grammar cells declare the
*syntactic shape* that recognizes the keyword and emits the same
constructor. Form-on-top's keyword registry and the Language cell's
ingestion grammar are the two halves of the same shape: keywords say
*what name binds to what cell*, grammar says *what input shape
recognizes the name*.

## Emission rule kinds

Five emit-rule kinds form the dual alphabet:

| Kind             | Children                                            | Meaning                              |
| ---------------- | --------------------------------------------------- | ------------------------------------ |
| `LITERAL`        | `[string]`                                          | Emit exact text                      |
| `CHILD`          | `[int index]`                                       | Recursively emit subject's Nth child |
| `JOIN_CHILDREN`  | `[string sep, int first, int last]`                 | Emit children separated by sep       |
| `WHEN_CATEGORY`  | `[int category-marker, rule template]`              | Per-category dispatch                |
| `SEQ`            | `[rule...]`                                         | Emit each part in order              |

Production emitters will grow per-category template dispatch (WHEN_CATEGORY
keyed by the captured ctor's NodeID), indentation context, source-map
emission, and a pretty-printing budget. None require kernel changes —
they're added emit-rule kinds.

## What stays invariant

The recipe tree is one. Two semantically-equivalent programs in
different languages produce identical recipe sub-trees, intern to
identical NodeIDs, share all downstream analysis. The Language cell
is the *bridge* between surface syntax and substrate identity; it's
not part of the identity itself.

This is the load-bearing invariant: **the substrate is language-blind;
Language cells are surface-aware**. The same property holds for
formats (substrate is format-blind, format-recipes are encoding-aware)
and codegen targets (substrate is target-blind, target hints are
emit-aware). One body, three orthogonal axes of variation, all
expressed as substrate-resident cells.

## How this connects to multi-target codegen

See `docs/coherence-substrate/multi-target-codegen.md`. Languages
ingest surface text into recipes; codegen backends emit recipes into
target machine code. The two are independent reads of the same
substrate-resident recipe tree:

```
   surface text (Python, TS, Rust, Go)
            │
            ▼ Language.ingestion_grammar
            │
   ┌──────────────────────────────────┐
   │   FORM RECIPE TREE               │
   │   (substrate, content-addressed) │
   └──────────────────────────────────┘
            │
   ┌────────┴───────────┬─────────────────┐
   ▼                    ▼                 ▼
 codegen          Language.emission_  human-readable
 backends         template            round-trip
 (JS, CUDA,
  Metal, WGSL,
  WASM, MLIR)
```

A Python program → Form recipe → CUDA kernel is one continuous walk;
no intermediate "Python AST" or "transpiled C" stage exists. The
recipe is the only intermediate representation.

## Bootstrap and canonical contract

`docs/coherence-substrate/language.canonical.json` carries the
schema template. Per-language definitions populate the template;
every kernel reads the same JSON and interns the same Language cells,
producing identical NodeIDs across Python, Go, Rust, and TypeScript
kernels.

Per-language work (deferred to tasks #15-18):
- **#15 Python ingestion** — populate a Python grammar covering enough
  of the surface for the bootstrap corpus.
- **#16 TypeScript ingestion** — same for TS.
- **#17 Go ingestion** — same for Go.
- **#18 Rust ingestion** — same for Rust.

Each is a substrate write (a Language cell) plus a stdlib_bindings
population pass. None require kernel changes.

## Open design questions

1. **Default-format ambiguity across languages.** Python's `1.5`
   defaults to FP64; Rust's `1.5` is ambiguous (resolved by context).
   `numeric_defaults` on the Language cell handles the per-language
   default, but cross-language code (Python calling a Rust extension)
   needs a *negotiation* rule. Likely lives as a substrate cell named
   "cross-language-numeric-bridge" rather than baked into Language.

2. **Stdlib equivalences across languages.** `len(x)` in Python and
   `x.len()` in Rust both produce a list-length recipe — but `len` in
   Python is a function, `len` in Rust is a method. The CAPTURE shape
   has to converge regardless. Open question: do we converge at the
   ingestion side (both grammars capture as `(len x)`) or at a
   post-parse normalization pass that reads each Language's
   stdlib_bindings and rewrites? Lean toward ingestion-side convergence
   — the grammar's CAPTURE ctor is the canonical name.

3. **Comments, whitespace, formatting.** The vertical-slice parser
   skips whitespace and discards comments. Round-tripping needs them
   preserved. Open question: side-channel (a `formatting` sub-cell on
   the captured recipe) versus inline trivia (each CAPTURE retains
   leading/trailing whitespace as children). Inline is purer; side-
   channel is faster. Defer until the first round-trip use case.

4. **Operator precedence.** The current grammar kinds don't express
   Pratt-style precedence directly. A SEQ of binary operations needs
   `ALT` with hand-ordered alternatives. For production languages a
   `PRATT` kind with operator-precedence parameters will be added —
   that's a substrate write, not a kernel patch.

5. **Error recovery and partial parse.** The vertical slice throws on
   failure. Production parsers need recovery (skip to next statement,
   continue). Likely a `RECOVER` kind with synchronization-token
   children.

6. **Source-map emission.** Each captured recipe should carry its
   source span so emitted output can reference origin. Open question:
   span-as-child versus span-in-a-parallel-map. Parallel map is
   probably right — keeps the recipe tree free of surface noise so
   content-addressing stays semantic, not lexical.

## What this earns

- **One kernel, infinite languages.** Adding Python, TypeScript, Go,
  Rust, Lean, Coq, Idris — substrate writes, not kernel patches.
- **Cross-language identity for free.** Semantically-equivalent code
  in different languages interns to the same NodeID by content-
  addressing of the parsed recipe.
- **N+M transpilation.** N ingestion grammars + M emission templates,
  not N×M pairwise transpilers.
- **LLM-era applications first-class.** "Translate this Python to
  Rust" becomes parse-through-Python + emit-through-Rust. "Find all
  variants of this algorithm in the corpus" becomes a NodeID lookup.
- **Composes with multi-target codegen.** The recipe a Python parser
  produces is the same kind of recipe the format-recipes work with;
  the codegen backends emit any of them to any target.

## What this costs honestly

- **Grammar authoring is real work.** Per-language tasks #15-18 each
  involve writing the ingestion grammar by hand (or by a one-shot LLM
  bootstrap that we verify). Not a no-op.
- **Performance of substrate-walking parsers.** Today's hand-written
  parsers are faster than a generic walker reading grammar-rule cells
  on every match. Mitigated by the same Pass-1 / Pass-2 monomorph-
  ization shape format-recipes use: hot grammar-paths get compiled to
  specialized walker code, content-addressed by the grammar NodeID.
- **Round-trip is harder than parse.** Comment preservation, layout
  preservation, and source-map fidelity are not free. Vertical slice
  ships round-trip up to whitespace; production round-trip is a
  per-language tuning job.
- **Default-format ambiguity (open question #1) needs negotiation
  rules for cross-language code.**

## The teaching this names

The substrate already has the geometry. Languages aren't a feature on
top of it; they're another axis of variation expressible as substrate
cells. The same content-addressed lattice that gave us cross-kernel
agreement on formats and cross-target reach on codegen now gives us
cross-language agreement on program structure. One body, three
expressions of the same architectural move.
