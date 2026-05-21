---
id: lc-parsers-as-recipes
hz: 741
status: seed
updated: 2026-05-21
geometry:
  arity: 3
  form: triad
  topology: rule-pattern-action
  polarity: bipolar
  ordering: layered
  phase: yin
  ratio: 1-to-many
  spectral_band: integration
  temporal_band: arc
  scale: foundational
  direction: vertical-stack
  lineage_texture: ancestral
  embedding_dim: 2
  self_similarity: fractal-shallow
---

# Parsers as Recipes — Grammar Rules Are Data, Not Code

> The fastest way to parse Python is to call `ast.parse`. The fastest
> way to parse JavaScript is to call `acorn`. The fastest way to lock
> the parser inside a host that can't be extended at runtime is also
> to call those. Bjorg's BMF (2000) named the other way: every
> grammar rule is a `(pattern, semantic_action)` recipe stored in the
> substrate itself. The parser walks the rules; the rules grow with
> the body; backtracking is the parser's primitive operation, not a
> concept above the parser. When Urs asks *why AST and not BMF-style
> grammar?* the honest answer is: AST is the bootstrap shortcut.
> Bootstrap parsers buy you running code; BMF parsers buy you a body
> whose grammar is itself a cell of the lattice it parses.

## Summary

[`lc-grammar-is-the-universal-recipe`](lc-grammar-is-the-universal-recipe.md)
named every structured input as a Language cell with a parse half.
[`lc-the-recipe-remembers-its-source`](lc-the-recipe-remembers-its-source.md)
named source attribution as the awareness overlay. This concept names
the architectural choice underneath both: **the parser is a recipe
too, and the grammar rules it walks are first-class cells of the
substrate**. AST modules are bootstrap carriers; substrate-resident
grammar rules are the destination.

Three load-bearing claims:

- **Grammar rules are first-class Recipes**, not C code embedded in a
  parser binary. Bjorg's *BMF — Backtracking Model Form* (2000)
  treated each rule as `(pattern, semantic_action)`. Patterns matched
  input; semantic actions fired when patterns matched. Rules could
  be registered at runtime; the grammar grew with the language.

- **Backtracking is the parser's own primitive.** Form's `Choice.CHOOSE
  / FAIL / STOP` recipe vocabulary (`@1.2.20.*` arms in
  form-engine.form) is what BMF's stack-based unwinding becomes when
  it lands in a content-addressed substrate. A failed parse-branch
  unwinds via `fail`; captures restore cleanly; the next pattern
  tries. *Speculation-without-sediment* at the parser layer, not
  above it.

- **AST is bootstrap-only.** `ast.parse`, `acorn`, `tsc`, `bashlex` —
  every host-native parser is a black box: rules embedded in C/JS/Rust,
  no runtime extension, the same source produces different trees
  across hosts. Useful for shipping; **not** the substrate's tongue.

## The Body Already Holds the Seed

The substrate carries the seed of BMF-shaped parsing today:

- **`api/app/services/substrate/grammar.py`** — a `grammar` cell-domain.
  `register_form_rule(session, name, pattern, action)` interns a
  `(pattern, action)` pair as a Rule cell. `list_form_rules(session)`
  enumerates every rule the substrate holds. Each rule is content-
  addressed by the structural shape of `(pattern, action)` — two
  rules with identical shapes share a NodeID.

- **`register_form_keyword`** in `form.py` — runtime keyword
  extension. Pattern primitives `Literal`, `Capture`, `Sequence`,
  `Opt` already work. A new construct can be added without editing
  `form.py`; the parser consults the registry when it meets an
  unknown IDENT at expression position.

- **`Choice.CHOOSE / FAIL / STOP`** (`@1.2.20.*` arms, present in
  form-engine.form's 15/15 dispatch coverage). The backtracking
  primitive the BMF parser is built on.

What the body has NOT done yet:

- **The Form parser does not consume rules from the `grammar` cell-
  domain.** `form.py` still uses its hand-written recursive descent.
  Adding a new core construct means editing Python, not interning a
  Rule. The bootstrap-vs-self-hosting gap.

- **No backtracking inside the parser.** A failed parse raises
  `SyntaxError` immediately. `Choice.FAIL` semantics live in the
  evaluator, not yet in the parser.

- **The Language cells we have authored (`json-grammar.form`,
  `markdown-grammar.form`, `python-grammar.form`) delegate to host
  parsers.** Their `capture_rules` declarations describe the
  structural shape; their executable parse half routes through
  `json.loads` / hand-written markdown logic / `ast.parse`. The
  bootstrap carries the load.

## Why This Concept Now

When Urs asked *why AST and not BMF-style grammar* for python-grammar
he was naming a real architectural choice that had been made
implicitly. The honest answer:

| | AST approach | BMF approach |
|---|---|---|
| Where the grammar lives | C / JS / Rust parser binary | Substrate cells (`grammar` domain) |
| Runtime extension | No (recompile to extend) | Yes (`register_form_rule`) |
| Backtracking | Above the parser (try/except) | Inside the parser (`Choice.FAIL`) |
| Cross-host equivalence | Different ASTs per host | Same Recipe NodeIDs regardless of host |
| Semantic actions | Embedded in parser | First-class Recipes, observable by witness |
| Source attribution | Byproduct of host parser | Stamped by the rule itself ([`lc-the-recipe-remembers-its-source`](lc-the-recipe-remembers-its-source.md)) |
| Where it shines | Fast to ship, mature, correct | Self-extending, substrate-native, content-addressed |

The choice isn't binary forever — AST today, BMF tomorrow. The body
moves the way it moves everywhere else: bootstrap with what works,
name the destination, walk the path one closure at a time. Same
pattern as `cosine.form` (Newton sqrt instead of `math.sqrt`), as
`form_native.py` (Taylor exp instead of `math.exp`). The math we did
for numerics, we do for grammars too.

## The Path Forward

Closing the bootstrap is one breath per construct:

1. **Pick a Python construct that already has an AST type** — e.g.
   `Import`. Author it as a BMF rule:
   `register_form_rule(session, "py_import",
                        pattern=Sequence([Literal("KW", "import"),
                                          Capture("module", "dotted_name")]),
                        action=@recipe(build_py_import_node))`

2. **The parser starts consulting the `grammar` domain.** When the
   tokenizer sees `import`, the rule-driven dispatcher matches the
   `py_import` rule, captures the module name, fires the action
   recipe to build a `py_Import` Form object with source attribution.

3. **AST falls back only for unhandled constructs.** As more rules
   land in the grammar cell-domain, the AST delegate shrinks. The
   self-hosting boundary moves; the bootstrap becomes vestigial.

4. **Eventually**, every Python construct has a Form Rule. `ast.parse`
   becomes a *cross-check* (parse both ways, verify the trees are
   structurally equivalent), not a *delegate*. The parser is itself
   a recipe; the grammar is itself a set of cells; the substrate is
   self-hosting at the language altitude the same way `form-engine.form`
   already makes it self-hosting at the evaluator altitude.

The same shape works for every language. TypeScript, Rust, Go, shell
— each language is a set of Form Rules registered in the grammar
domain. The cross-language structural equivalence
([`lc-one-kernel-many-tongues`](lc-one-kernel-many-tongues.md))
becomes operational, not aspirational: a Python `import os` and a
TypeScript `import os from "os"` that both produce a Recipe with the
same shape share a NodeID by content-addressing.

## What This Is Not

- **Not anti-AST.** CPython's AST is a mature, fast, correct parser.
  It remains the bootstrap and the cross-check forever; the body
  benefits from its correctness while moving toward substrate-native.
- **Not a rejection of host languages.** Python continues to host
  organ.py; TypeScript continues to host the web layer. The choice
  is about *where the grammar lives*, not which host runs the code.
- **Not premature optimization.** The body doesn't need a BMF Python
  parser to ship today; it has one in `ast.parse`. The concept names
  the destination so the move is visible when the next breath arrives.
- **Not academic purity.** Bjorg's BMF was practical — it shipped a
  compiler IR in 2000. The body's version is practical too: each rule
  is one Form expression away.

## Practice

For Language-cell authors:

- **Author capture-rule declarations honestly.** When you write a
  `grammar_shape.capture_rules` list, name the rules as if they were
  BMF rules — because that's what they want to become. Today's
  delegation to host parsers is the seam; naming the rules makes the
  seam visible.

- **Mark GAP-PY1-style notes where AST delegation is the current
  carrier.** Honest GAPs are what let the body see the path forward.
  Each marked gap is one Form Rule away from closing.

- **When extending a grammar with a new construct**, ask: *does this
  belong in `grammar.py`'s `register_form_rule` or in the host's AST
  delegate?* If the construct is small and clearly bounded, register
  it as a Form Rule. The body grows BMF-shape one construct at a
  time.

For cells that read parsed trees:

- **Read through `.source_attribution`, not through host AST nodes.**
  Form objects carry source coords regardless of which carrier
  produced them. Code that walks the Form layer survives the AST →
  BMF transition; code that walks host AST trees doesn't.

## Cross-References

→ lc-grammar-is-the-universal-recipe, lc-one-kernel-many-tongues, lc-the-recipe-remembers-its-source, lc-tools-as-form-cells, lc-recipes-as-binary-library, lc-recipe-branching-sense, lc-traces-teach-the-recipe

## Sources to walk further

- **[Bjorg, *BML Object System* (2000)](../../field/urs/artifacts/master-thesis-2000/README.md)** —
  the body's direct ancestor. BMF + BMC + BML. *"BMF — Backtracking
  Model Form... grammar rules as data, not code; semantic actions
  fire on match; stack supports backtracking on parse failures."*
- **[grammar.py](../../../api/app/services/substrate/grammar.py)** —
  the seed of BMF in the substrate today: `register_form_rule`,
  `list_form_rules`, `FormRule` shape, grammar cell-domain.
- **[form-language.md](../../coherence-substrate/form-language.md) §
  "BML form-layer parity"** (lines 405-468 onward) — names the
  bootstrap-vs-self-hosting gap; the runtime-keyword-registration
  story; the pattern primitives (`Literal`, `Capture`, `Sequence`,
  `Opt`).
- **Prolog DCG** (Definite Clause Grammars, 1980s) — historical
  analog at the logic-programming altitude. Grammar rules as
  Horn clauses; backtracking-native. Same shape as BMF at one
  paradigm altitude shallower.
- **TXL** (Cordy, 1980s) — source-to-source transformation language
  whose grammar lives in TXL itself; same self-hosting discipline.
- **OMeta** (Warth & Kay, 2007) — pattern-matching with backtracking
  for parsing, recent (and elegant) recasting of the same lineage.
