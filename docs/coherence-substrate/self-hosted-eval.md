# Self-hosted Form — what's already in Form, what's still bridge/bootstrap

Form is a substrate-native DSL. The honest question — *"can the parser, interpreter and runtime all live in Form itself?"* — has a layered answer. This page maps where each layer currently lives.

## What's self-hosted today

### The interpreter for arithmetic/comparison/logic/conditional core

The engine source lives in [`docs/coherence-substrate/form-engine.form`](form-engine.form) between `# >>> BEGIN engine` / `# >>> END engine` markers. `api/tests/test_substrate_form_self_hosted.py` loads it from disk and runs it — the substrate holds its own interpreter as an on-disk artifact, not as a Python string. Drift is fenced three ways:

1. **Flat NodeID-literal dispatch.** Each arm is `@1.2.12.1 => ...` (Level=BASIC, RBasic.MATH, RMath.PLUS) rather than a magic int. Walking a recipe whose category moved silently produces the wrong answer; the parity tests catch it.
2. **Drift sentinel.** `test_form_engine_literals_match_python_enums` parses every `@l.t.i` literal in the engine block and asserts each one points at a known `(RBasic.<verb>, instance)` pair. Rename `RBasic.MATH` or add an unknown literal — the test fails immediately.
3. **Property-based parity.** Random arithmetic / comparison / conditional expressions get evaluated by both engines and asserted equal (40 + 20 per run, fixed seed).

```form
defn ev(n) = match n.category {
  @1.2.12.1 => ev(n.children[0]) + ev(n.children[1]),     # MATH.PLUS
  @1.2.12.2 => ev(n.children[0]) - ev(n.children[1]),     # MATH.MINUS
  @1.2.13.5 => ev(n.children[0]) > ev(n.children[1]),     # COMPARE.GREATER
  @1.2.14.1 => ev(n.children[0]) && ev(n.children[1]),    # LOGIC.AND
  @1.2.11.2 => if ev(n.children[0]) then ev(n.children[1]) else ev(n.children[2]),
  ...
  _ => n.value   # substrate's own trivial decoder (NULL / BOOL / INTEGER / STRING)
}
```

The `_` arm reads through `.value` — the substrate's single source of truth for
trivial-leaf encoding. Form and the current bridge runtime read the same decoder;
a change to integer encoding moves both engines at once. Composites have no
atomic value, so `.value` on a composite raises — the engine refuses to silently
fake an answer for an unknown verb.

It produces identical answers to the bootstrap engine across MATH (×5), COMPARE
(×6), LOGIC (×3), COND (×2), and trivial INTEGER / BOOL / STRING decode. Two
engines, identical answer, same substrate.

Extending to STATE, CHOICE, METHOD, etc. is adding one arm here and one expected literal to `_EXPECTED_LITERALS` — mechanical, not conceptual.

### The keyword grammar

`register_form_keyword` lets a Form keyword be defined by a substrate-resident pattern + builder. Keywords like `let`, `if/then/else`, `do { … }` are themselves cells in the lattice; the bootstrap parser dispatches through that registry. New surface keywords ship as substrate writes, not Python edits.

### Substrate-resident patterns and builders

`Build`, `CaptureRef`, `Const` templates compose into Recipes that the runtime executes. The "what does a keyword build" lives in the substrate.

## What is still bridge/bootstrap

### The bootstrap parser

`api/app/services/substrate/form.py` — `tokenize`, `tokenize_iter`,
`tokenize_chunks`, `Parser`, `parse`, `parse_chunks`. Regex-driven lexer,
recursive-descent parser, builds an AST of dataclasses (`BinOp`, `IfExpr`,
`DoBlock`, …). This is the bootstrap bridge — the thing that turns surface text
into a Recipe tree the Form-level interpreter can then walk.

A Form-level parser is reachable but unbuilt: Form would need string-manipulation primitives and a `Token` cell shape. The interpreter above already proves it's a tractable next move, just not present.

### The substrate-mutation primitives

`make_cell`, `define_method`, `register_form_keyword`, the ingest paths — these
currently write through the compatibility service's SQLAlchemy carrier. That is
bridge tissue, not the ownership model. Form-native persistence already exists
for `.fkb` cell round-trips; the remaining work is the DB-backed storage port and
mutation API as Form-visible cells.

### Leaf operations

Arithmetic, comparison, conditional dispatch at the leaves — `a + b`, `a == b`,
`if c then … else …`. The Form interpreter recurses *through* these; the
trivials themselves bottom out in host primitives. In the bridge engine that host
is Python; in sibling kernels it is Go/Rust/TypeScript. This is the floor any
self-hosted language has: at some level the operations are the carrier's
operations.

## The map

| Layer | Today | Path to full self-hosting |
|-------|-------|---------------------------|
| **Interpreter** (recipe-walking) | Form (on-disk `form-engine.form`; MATH / COMPARE / LOGIC / COND / trivial decode proven; drift-sentinel keeps literals in sync) | Add one match arm per new category, one entry in `_EXPECTED_LITERALS` |
| **Keyword grammar** | Form (substrate-resident via `register_form_keyword`) | Already there |
| **Pattern/builder templates** | Form (substrate-resident) | Already there |
| **Bootstrap parser** | Compatibility bridge (`tokenize` + recursive descent) | Form-level parser needs string primitives + Token cell shape |
| **Substrate mutation** | Compatibility service carrier (SQLAlchemy) | Form-native DB storage port and mutation cells |
| **Leaf arithmetic/comparison** | Host primitives (`node.instance`) | Inherent floor — each sibling kernel bottoms out in its carrier ops |

## Why this matters

Self-hosting isn't a single yes/no. The shape that matters is: **can the language describe its own semantics in itself?** The demo answers yes for the interpreter layer. The parser layer is the same answer waiting for an afternoon of work. The persistence layer is a substrate-design choice, not a language limitation.

The remaining bridge parser is not the destination — it is a named floor. Even
the BML/BMF self-hosting lineage (master thesis 2000) bottomed out somewhere;
the discipline is *as much as possible in the language, and the rest is honest
about being the floor*.

## Run the demo

```bash
cd api && python -m pytest tests/test_substrate_form_self_hosted.py -v
```

Twenty tests, all green: smoke tests per dispatch arm, a drift sentinel that
asserts every NodeID literal in `form-engine.form` matches the bootstrap enum,
and property-based parity that runs random expressions through both engines. Two
engines, identical answer, same substrate — that's the proof, and it's now
armored against silent rename drift.
