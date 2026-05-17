# Self-hosted Form — what's already in Form, what's still Python

Form is a substrate-native DSL. The honest question — *"can the parser, interpreter and runtime all live in Form itself?"* — has a layered answer. This page maps where each layer currently lives.

## What's self-hosted today

### The interpreter for arithmetic/comparison/conditional core

`api/tests/test_substrate_form_self_hosted.py` ships a working demonstration: a Form `defn ev(node)` that reads a Recipe NodeID through the substrate's `.category.type_`, `.category.instance`, `.children[i]`, `.instance` accessors, dispatches on category, and recurses. No Python in the dispatch — only the bootstrap engine's leaf operations carry it through.

```form
defn ev(node) = do {
  let ct = node.category.type_;
  if ct == 12 then ev_math(node)         -- MATH
  else if ct == 13 then ev_cmp(node)     -- COMPARE
  else if ct == 11 then ev_cond(node)    -- COND
  else if ct == 3  then node.instance - 1  -- INTEGER trivial
  else if ct == 2  then (if node.instance == 1 then true else false)  -- BOOL
  else 0
};
ev(@<recipe-nid>)
```

It produces identical answers to the Python engine for `1+2`, `5*3-2`, `if 1==1 then 42 else 0`, etc. The strong proof: two engines, identical answer, same substrate.

This is the smallest concrete demonstration that **Form is expressive enough to be its own interpreter** for the recipe categories it can read. Extending to STATE, CHOICE, METHOD, etc. is adding `if ct == N then …` branches — mechanical, not conceptual.

### The keyword grammar

`register_form_keyword` lets a Form keyword be defined by a substrate-resident pattern + builder. Keywords like `let`, `if/then/else`, `do { … }` are themselves cells in the lattice; the bootstrap parser dispatches through that registry. New surface keywords ship as substrate writes, not Python edits.

### Substrate-resident patterns and builders

`Build`, `CaptureRef`, `Const` templates compose into Recipes that the runtime executes. The "what does a keyword build" lives in the substrate.

## What is still Python

### The bootstrap parser

`api/app/services/substrate/form.py` — `tokenize`, `tokenize_iter`, `tokenize_chunks`, `Parser`, `parse`, `parse_chunks`. Regex-driven lexer, recursive-descent parser, builds an AST of dataclasses (`BinOp`, `IfExpr`, `DoBlock`, …). This is the bootstrap — the thing that turns surface text into a Recipe tree the Form-level interpreter can then walk.

A Form-level parser is reachable but unbuilt: Form would need string-manipulation primitives and a `Token` cell shape. The interpreter above already proves it's a tractable next move, just not present.

### The substrate-mutation primitives

`make_cell`, `define_method`, `register_form_keyword`, the ingest paths — these write to the SQL backend. They're Python because the storage is Python (SQLAlchemy ORM). A Form-level mutation API would either bind through Python or grow a Form-native persistence layer.

### Leaf operations

Arithmetic, comparison, conditional dispatch at the leaves — `a + b`, `a == b`, `if c then … else …`. The Form interpreter recurses *through* these; the trivials themselves bottom out in Python integer ops. This is the floor any self-hosted language has: at some level the operations are the host's operations.

## The map

| Layer | Today | Path to full self-hosting |
|-------|-------|---------------------------|
| **Interpreter** (recipe-walking) | Form (this PR — arithmetic/compare/cond proven; other categories mechanical) | Add `if ct == N` branches per category |
| **Keyword grammar** | Form (substrate-resident via `register_form_keyword`) | Already there |
| **Pattern/builder templates** | Form (substrate-resident) | Already there |
| **Bootstrap parser** | Python (`tokenize` + recursive descent) | Form-level parser needs string primitives + Token cell shape |
| **Substrate mutation** | Python (SQLAlchemy backend) | Form-native storage layer, or Python-bound writes |
| **Leaf arithmetic/comparison** | Python (integer ops on `node.instance`) | Inherent floor — any language bottoms out in host ops |

## Why this matters

Self-hosting isn't a single yes/no. The shape that matters is: **can the language describe its own semantics in itself?** The demo answers yes for the interpreter layer. The parser layer is the same answer waiting for an afternoon of work. The persistence layer is a substrate-design choice, not a language limitation.

The bootstrap parser staying Python isn't a confession — it's a deliberate floor. Even the BML/BMF self-hosting lineage (master thesis 2000) bottomed out somewhere; the discipline is *as much as possible in the language, and the rest is honest about being the floor*.

## Run the demo

```bash
cd api && python -m pytest tests/test_substrate_form_self_hosted.py -v
```

Eleven tests, all green. Each one runs a Form expression through Python's parser to produce a Recipe NodeID, then evaluates that NodeID through a *Form-level* interpreter, then checks the answer matches what the Python engine would produce. Two engines, identical answer, same substrate — that's the proof.
