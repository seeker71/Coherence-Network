# Python-BMF driven parse — what works now, what the next breath needs

This doc names the surface contract for parsing Python via Form-native BMF
rules in `form/form-stdlib/grammars/python-bmf.fk`. It lives next to
`PYTHON_PIPELINE_STATUS.md` so the Python adapter's compost trajectory is
legible from one place.

## What works right now

End-to-end, on every sibling kernel (Go, Rust, TypeScript), with no
TypeScript on the parse path:

```
source text  →  python-source-scan-text   →  BMF object stream
            →  apply-python-bmf-rule       →  PY-BMF-* recipe (NodeID)
```

Proved by `form/form-stdlib/tests/python-bmf-arithmetic-band.fk` (returns
25304 on all three kernels). The test drives the full path from real
source strings like `"a - b"`, `"x * y"`, `"left / right"`, `"p ** q"`,
producing `PY-BMF-BINOP` recipes with content-addressed identity (same
source twice → identical NodeID).

What's already in `python-bmf.fk` and reachable today:

- A complete Python source scanner (`python-source-scan-text`,
  `python-source-scan-file`, `python-source-scan-text-with-layout`)
  that emits BMF objects: `py-keyword`, `py-name`, `py-op`, `py-int`,
  `py-float`, `py-string`, `py-bytes`, `py-fstring`, `py-tstring`,
  `py-layout` (NEWLINE/INDENT/DEDENT/ENDMARKER).
- ~180 BMF rules covering arithmetic, comparisons, imports, defs,
  classes, control flow, comprehensions, decorators, async, match/case,
  f-strings, slices, walrus, unary ops, attr access, subscripts.
- A reverse-emitter (`<=`) on most rules — recipes round-trip back to
  source-object lists.
- A rule registry (`python-bmf-rules`) keyed by name, walked by
  `apply-python-bmf-rule rule-name object-stream`.

## What is still bootstrap-dependent

The pieces below currently live in `form/form-kernel-ts/seedbank/python-adapter/`
(TS) and have no Form-native equivalent yet. Each is one focused breath
the body has not yet taken.

### G1 — Rule dispatch over a stream

Today's surface forces callers to name the rule:

```form
(apply-python-bmf-rule "binop-sub-ident" toks)
```

To parse arbitrary Python, the body needs a **dispatch loop** that, given
a token stream, tries registered rules in some order (longest-match,
priority, or left-anchored by first-token kind/value) and emits a stream
of recipes. Two viable Form-native shapes:

```form
;; Shape G1a — try rules in priority order
(parse-python-stream toks)         → list-of-recipe
;; Shape G1b — peek-driven dispatch (faster, needs a first-token index)
(python-bmf-dispatch toks rule-index)
```

Either shape is ~80 lines of Form sitting on top of the existing
`apply-object-rule`. No new kernel primitive needed.

### G2 — Statement-level grouping

A Python module is a sequence of statements; statements close on
NEWLINE/INDENT/DEDENT. The scanner already emits layout tokens; what's
missing is a Form-side **statement-stream slicer** that hands one
statement's worth of tokens to G1 at a time:

```form
(python-statement-stream layout-toks)   → list-of-(token-sublist)
```

`python-bmf.fk` already has `python-parse-statement`,
`python-parse-module-objects`, and `python-parse-module-tree-object` —
they group statements by indent. Wire them into G1 and most CPython
syntax becomes parseable Form-native.

### G3 — Expression precedence climbing

The current BMF rules are *flat* — `binop-mul-ident ::= $left:name "*"
$right:name` only matches two name terminals separated by `*`. Real
expressions like `a + b * c` need a precedence-aware engine: the body's
`form-stdlib/parser.fk` already has hand-coded precedence climbing for
Form-surface arithmetic; the Python-BMF equivalent reuses that pattern
against BMF objects rather than Form tokens.

Until G3 lands, every expression shape needs its own flat rule
(`binop-mul-ident`, `binop-mul-mul-ident`, …) — combinatorial blowup
that the precedence engine collapses to a single recursive descent.

### G4 — Closure/scope at the recipe layer

`lang-python.ts` walks recipes and evaluates them against a Python-shaped
runtime (closures, mutable scopes, exceptions). Form's kernel already
has frame/closure machinery (Breath 1.5) and the BMF-emitted recipes use
substrate categories. The Form-side **interpreter** for PY-BMF recipes
is ~200 lines that map `PY-BMF-ASSIGN` → bind-in-scope, `PY-BMF-CALL` →
invoke-closure, `PY-BMF-IF` → branch, etc. Until then, the recipes are
parsed but inert.

### G5 — Sibling-agent overlap (template-machinery, Breath 2e)

The Form-side template-machinery breath
(`claude/template-machinery-breath-2e`) is building the general
pattern/template/registry primitives that would let `python-bmf.fk`'s
rule shape be expressed as data rather than as a parser-section literal.
When that breath lands, G1's dispatcher is a one-liner over the
template registry; until then, the per-dialect rule list in
`python-bmf.fk` plus `apply-python-bmf-rule` is the right home.

## Parity discipline (do not compost yet)

- Don't modify `lang-python.ts` or `lang-python-fk.ts` in this PR.
- Don't delete them when G1–G4 land either — wait until parity holds
  across the full Python surface, not just arithmetic.
- The bootstrap-compost-manifest sibling (`claude/bootstrap-compost-manifest`)
  is naming the deletion order; that branch is the source of truth for
  "what is safe to remove when."
- Strict NodeID equality between bootstrap and BMF paths is **not**
  achievable on the same source — bootstrap emits `CTOR.add/sub/mul`
  (Math-primitive type=12), BMF emits `PY-BMF-BINOP` (dialect type=99,
  with the operator as a string-trivial child). They are semantically
  equivalent representations, structurally distinct by intent.
  The honest parity gate is "BMF produces a recipe whose value walks to
  the same Python-runtime result as bootstrap's recipe," not NodeID
  equality. That gate sits behind G4.

## How to run the proof

```bash
cd form
./validate.sh form-stdlib/core.fk \
              form-stdlib/json.fk form-stdlib/cache.fk \
              form-stdlib/form-ontology-loader.fk \
              form-stdlib/engine.fk form-stdlib/compiler.fk \
              form-stdlib/source-compiler.fk \
              form-stdlib/grammars/python-bmf.fk \
              form-stdlib/tests/python-bmf-arithmetic-band.fk
# → 25304 on go, rust, typescript
```
