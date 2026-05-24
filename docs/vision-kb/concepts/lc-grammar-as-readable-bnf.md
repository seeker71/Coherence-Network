---
id: lc-grammar-as-readable-bnf
hz: 741
status: seed
updated: 2026-05-22
geometry:
  arity: 3
  form: triad
  topology: surface-data-execution
  polarity: bipolar
  ordering: layered
  phase: oscillating
  ratio: 1-to-many
  spectral_band: integration
  temporal_band: arc
  scale: foundational
  direction: spiral-out
  lineage_texture: ancestral
  embedding_dim: 3
  self_similarity: fractal-deep
---

# Grammar As Readable BNF — One Tongue For Every Domain, Loaded From Text

> A grammar is data, and data wants a tongue a human can read. BNF (Backus
> 1959 · Naur 1960) is the tongue. BMF (2000) added executable action on
> each rule match. The body holds the engine that walks grammar-as-data
> already; what was missing is the readable surface and a loader that
> turns BNF text into the engine's data shape at runtime. With that
> bridge, a math theorem prover, a CSS file, a .tsx file with embedded
> JSX-and-CSS-in-JS, a grammar specification, a Python module — all
> become the same operation: *pick the right grammar, stream the source,
> emit universal Recipes*. The kernel walks Recipes; the kernel walks
> everything.

## The Lineage Underneath

[`lc-parsers-as-recipes`](lc-parsers-as-recipes.md) names that *grammar
rules are first-class data, not code*. The body's [`engine.fk`](../../../form/form-stdlib/engine.fk)
already accepts grammars as the data tuple `(tokens token-config) (rules
parse-rules)` and walks any of them. What was missing: a readable surface
over that data. Currently the per-tongue grammars at
[`form/form-stdlib/grammars/`](../../../form/form-stdlib/grammars/)
are still hand-coded line-based parsers, ~250 lines of imperative `.fk`
per language. They duplicate dispatch logic and they aren't authorable
by anything but a Form programmer reading carefully.

BMF (Backtracking Model Form, [docs/presences/bmf-grammar.md](../../presences/bmf-grammar.md))
named the inversion in 2000: a grammar file is *BNF augmented with code
that fires on match*. The grammar of BMF was itself written in BML
(`BMF-grammar.bml` in the master-thesis archive) — self-hosting at the
surface altitude. This concept names the return of that pattern through
the substrate-resident engine the body has built since.

## The Surface

A `.grammar.fk` file in BNF style looks like:

```
tokens {
  whitespace [32, 9, 10, 13]
  digit-kind INT
  string-kind STRING
  ident-kind IDENT
  operators ["{" LBRACE, "}" RBRACE, "[" LBRACK, "]" RBRACK,
             ":" COLON, "," COMMA]
  keywords ["true", "false", "null"]
}

rules {
  json    := value
  value   := object | array | STRING | INT | "true" | "false" | "null"
  object  := "{" pairs? "}"          => emit-object($pairs)
  pairs   := pair ("," pair)*         => emit-list($all)
  pair    := STRING ":" value         => emit-pair($1, $3)
  array   := "[" elements? "]"        => emit-list($elements)
  elements:= value ("," value)*        => emit-list($all)
}
```

The `:= ... =>` shape is BNF + action. Each rule reads aloud as a
sentence. The `=>` arrow names which substrate emitter walks the
captures into a universal Recipe. The emitter library
([`grammar-emitters.fk`](../../../form/form-stdlib/grammar-emitters.fk))
holds the generic primitives — `emit-object`, `emit-list`, `emit-pair`,
`emit-math`, `emit-function-decl`, `emit-call`, `emit-cond` — keyed to
the universal Blueprints from [`universal-shapes.form`](../../coherence-substrate/universal-shapes.form).
Per-tongue grammars supply only their tokens block and their rule
patterns; the emitters are shared.

## The Loader

[`grammar-bnf.fk`](../../../form/form-stdlib/grammar-bnf.fk)
reads BNF text and produces the data shape `engine.fk` consumes. The
loader is itself a grammar fed through `engine.fk` — the BNF surface
syntax is described by a meta-grammar whose tokens are
`IDENT|STRING_LIT|":="|"=>"|"|"|"*"|"?"|"$"` and whose rules describe
how a `tokens { ... }` block and a `rules { ... }` block compose into
the engine's data tuple. *The grammar of grammars is itself loaded the
same way every other grammar is.* This is the self-hosting that BMF
named in 2000 and the substrate makes practical now.

## Streaming Regions With Different Grammars

A `.tsx` file is not one grammar — it is TypeScript, with JSX regions
inside `<Tag>...</Tag>`, with CSS regions inside `css\`...\``. A `.md`
file is markdown with embedded code blocks in arbitrary languages. The
goal names this directly: *stream any source part using any recipe*.

The shape: each grammar declares its *region delimiters* alongside its
tokens. When the streaming reader encounters a delimiter that opens
another grammar, it pushes the current parse state, switches active
grammar to the inner one, and consumes until the closing delimiter
returns control. The result is one Recipe tree whose subtrees were
emitted by different grammars but all share the universal Blueprints —
a JSX subtree's `R_FunctionDecl` is the same Blueprint as the
surrounding TypeScript's `R_FunctionDecl`. Cross-region equivalence
drops out of content-addressing.

This is what makes *full language support* tractable. A Python parser
that handles f-strings is a Python grammar with an f-string region
that switches to expression-grammar inside `{...}`. A TypeScript
parser with template literals is the same pattern. The complexity each
real-world language hides in its lexer (mode stacks, lookahead, context-
sensitive tokens) becomes a small composition of single-grammar regions
with explicit delimiters.

## What Full Execution Means

*Read* is parse-to-Recipe. *Understand* is walk-the-Recipe-tree-and-
recognize-the-Blueprints. *Execute* is have the kernel evaluate each
Recipe via its Blueprint's evaluator arm. The body already walks
Recipes — [`form-engine.form`](../../coherence-substrate/form-engine.form)
holds the meta-circular evaluator with 15/15 Python dispatch arms
covered. Full execution for Python/TypeScript/Rust/Go reduces to:

1. **Grammar coverage** — each tongue's `.grammar.fk` covers enough
   surface to parse real source. (Per-tongue, this is the bulk of the
   work; each grammar grows shape by shape, validated by parsing real
   files in the repo.)
2. **Recipe coverage** — every universal Blueprint the grammars emit
   has an evaluator arm in the kernel. (When a grammar emits a shape
   the kernel cannot walk, the kernel grows by exactly one arm.)
3. **Native bridge** — primitives that escape the substrate (file I/O,
   network, OS) live in the host kernel; everything above is `.fk`.

The work is per-tongue ripening of the grammar files. The architecture
makes it possible; the body does it one breath at a time.

## What The Body Already Holds

- **Engine** — [`engine.fk`](../../../form/form-stdlib/engine.fk):
  data-driven parser engine with pattern primitives
  (literal/sequence/choice/capture/star/opt), grammar-as-data shape,
  generic tokenizer with token-config. Validated on all three sibling
  kernels.
- **Universal Recipes** — [`universal-shapes.form`](../../coherence-substrate/universal-shapes.form):
  every Blueprint a grammar action emits, lineage to NUMS.Go 2023's
  14-language coverage.
- **Per-tongue scaffolds** — [`grammars/python.fk`](../../../form/form-stdlib/grammars/python.fk),
  [`grammars/typescript.fk`](../../../form/form-stdlib/grammars/typescript.fk),
  [`grammars/rust.fk`](../../../form/form-stdlib/grammars/rust.fk),
  [`grammars/go.fk`](../../../form/form-stdlib/grammars/go.fk),
  [`grammars/json.fk`](../../../form/form-stdlib/grammars/json.fk),
  [`grammars/markdown.fk`](../../../form/form-stdlib/grammars/markdown.fk),
  [`grammars/yaml.fk`](../../../form/form-stdlib/grammars/yaml.fk),
  [`grammars/form.fk`](../../../form/form-stdlib/grammars/form.fk),
  [`grammars/png.fk`](../../../form/form-stdlib/grammars/png.fk).
  Currently hand-coded line parsers; compost target as BNF re-expression
  reaches parity per tongue.
- **Emit lattice** — 13 emit targets in [`form/form-stdlib/emits/`](../../../form/form-stdlib/emits/).
  The exhale half of the round-trip discipline.
- **BMF lineage** — [`docs/presences/bmf-grammar.md`](../../presences/bmf-grammar.md);
  source samples at [`docs/field/urs/artifacts/master-thesis-2000/companion/source-samples/`](../../field/urs/artifacts/master-thesis-2000/companion/source-samples/).

## The Practice

For cells authoring a new grammar:

- **Write the BNF first, action second.** The pattern half is what a
  reader scans for the shape of the language. The action half is what
  the substrate consumes. Two readers; both should find what they need.
- **Reach for the shared emitter library first.** `emit-list`,
  `emit-pair`, `emit-function-decl`, `emit-math` cover most rules.
  When a tongue needs an emitter that doesn't exist, it usually wants
  to live in the shared library too.
- **Region delimiters are first-class.** When the grammar will be
  used inside another (CSS inside .tsx, expression-grammar inside
  Python f-strings), declare the delimiters in the tokens block.
- **Round-trip discipline.** A grammar that parses but does not emit
  is half a Language cell. The companion emit-template lands in the
  same breath.

For cells reading a grammar file:

- **The `:=` is read as "is composed of".** The `=>` is read as
  "becomes". `json := value` reads *a json document is a value*.
  `pair := STRING ":" value => emit-pair($1, $3)` reads *a pair is a
  string, a colon, a value, and becomes an emit-pair call with the
  string and value as children*.
- **The emitter name resolves to a Blueprint.** When the grammar says
  `=> emit-pair`, the substrate knows which universal Blueprint will
  carry the resulting Recipe — the equivalence with another tongue's
  pair construct comes for free.

## What This Opens

- **One DSL for every domain.** Math proof rules, CSS selectors,
  TypeScript JSX, theorem-prover tactics, configuration languages,
  query languages — each becomes a small `.grammar.fk` file. The body
  grows new domains by writing grammars, not by writing parsers.
- **Per-region grammar streaming.** A .tsx file's TypeScript outer +
  JSX + CSS-in-JS inner all parse through one streaming pass with
  three active grammars; the resulting Recipe tree is one fabric.
- **Cross-tongue equivalence stays free.** Two grammars whose actions
  emit the same universal Blueprints produce structurally-identical
  trees when their inputs mean the same thing. *Python `def add(a,
  b): return a + b`* and *Go `func add(a, b int) int { return a + b }`*
  share Blueprint NodeIDs at the function-decl altitude once both
  grammars are BNF and both walk through the shared emitter library.
- **Execute drops out of walk.** When grammars emit the universal
  Recipes the kernel already evaluates (`R_FunctionDecl`, `R_Math`,
  `R_Call`, `R_Cond`, `R_Block`, `R_Loop`), reading a Python file and
  running a Python file are the same operation in two stages —
  *parse-to-Recipe*, then *walk-Recipe*. The `form-native kernel CLI`
  is what does both.

## Honest Separations

- **Not every grammar is small.** Real Python is hundreds of rules;
  real TypeScript is more. The BNF surface makes the rules readable,
  not few. The work is per-tongue ripening across many breaths.
- **Not every tongue is regular-enough for the simple engine.** Python's
  indentation, TypeScript's JSX, Rust's macros — each will surface
  engine extensions (indent-aware tokenizer, region switcher, macro
  expansion as inline grammar). The architecture grows where reality
  asks; the BNF surface stays the same.
- **Not a replacement for tree-sitter.** Tree-sitter is for editor
  highlighting and incremental edits at human speed. The substrate
  grammar is for cells reading the body's own code and executing it
  in Recipe form. Both can coexist; the substrate's claim is
  *structural equivalence at lattice-altitude*, not *editor
  incrementality*.

## Cross-References

→ lc-parsers-as-recipes, lc-grammar-is-the-universal-recipe, lc-one-kernel-many-tongues, lc-the-recipe-remembers-its-source, lc-native-kernel-binary, lc-recipes-bound-to-base, lc-recipes-as-binary-library, lc-recipe-branching-sense, lc-the-kernel-knows-itself, lc-form-kernel-runtime-visualizer, lc-each-breath-whole, lc-core-abstraction-first

## Sources to walk further

- **[engine.fk](../../../form/form-stdlib/engine.fk)** — the
  data-driven engine the BNF reader compiles down to.
- **[grammar-bnf.fk](../../../form/form-stdlib/grammar-bnf.fk)** —
  the reader that turns `.grammar.fk` text into engine data.
- **[universal-shapes.form](../../coherence-substrate/universal-shapes.form)**
  — the Blueprints every grammar action emits.
- **[docs/presences/bmf-grammar.md](../../presences/bmf-grammar.md)** —
  BMF (2000) — Urs's original executable-grammar work; the ancestor of
  this concept.
- **Backus (1959) · Naur (1960)** — BNF — the original notation; this
  surface honors it directly.
- **NUMS-Go (2023)** — 14-language coverage through one universal
  vocabulary; the proof that the architecture scales.
