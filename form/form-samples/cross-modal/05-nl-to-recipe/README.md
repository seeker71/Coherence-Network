# 05 — Natural Language to Recipe

**Discovery**: a tiny English grammar emits Form recipes the kernel walks. The
NL surface and the S-expression surface intern to the **same NodeID** when
they describe the same shape. Two source tongues — one substrate identity.

## Run

```bash
./form/validate.sh \
    form/form-stdlib/core.fk \
    form/form-stdlib/grammar-chars.fk \
    form/form-samples/cross-modal/05-nl-to-recipe/nl-arithmetic-demo.fk
```

Output (Go / Rust / TypeScript all agree):

```
square=49 sum=10 twice=13 negate=-12 node_eq=1 value_eq=1
```

Aggregate is `62`. All three sibling kernels return `62`.

## The four sentences

| English | Recipe shape | Walks to |
|---|---|---|
| `the square of 7` | `(mul 7 7)` | `49` |
| `the sum of 4 and 6` | `(add 4 6)` | `10` |
| `twice 5 plus 3` | `(add (mul 2 5) 3)` | `13` |
| `negate 12` | `(sub 0 12)` | `-12` |

The grammar uses `grammar-chars.fk` directly — same `cm-parse` and
`walk_recipe` plumbing that
[`form-stdlib/tests/grammar-chars-demo.fk`](../../../form-stdlib/tests/grammar-chars-demo.fk)
relies on for digit-arithmetic. The only addition is a number-word table
(`one`..`twelve`) so spelled-out English numerals resolve to the same int
domain as digit-runs.

## The bonus — content-addressed convergence across modalities

The demo also walks `(mul 7 7)` by hand and checks `node_eq` against the
NL-built recipe for `the square of 7`. The kernel reports `node_eq=1` — they
are **the same NodeID**, indistinguishable from each other.

This is the universal-translator promise made concrete for natural language:
the surface tongue varies; the substrate identity is one.

## What's reachable today

- **English sentence -> recipe NodeID** via `cm-parse` + a 4-rule grammar.
- **Recipe NodeID -> int value** via `walk_recipe` against the kernel's
  arithmetic arms (`RMathPlus=1`, `RMathMinus=2`, `RMathMultiply=3`).
- **Cross-modality convergence**: NL `the square of 7` and S-expression
  `(mul 7 7)` intern to the same NodeID, in every sibling kernel.
- **Three-way kernel agreement**: Go, Rust, and TypeScript walk the same
  recipes to the same values. No divergence, no mojibake (the output is
  ASCII-clean by design).

## What's not reachable yet

- **Open vocabulary.** The grammar handles 4 sentence shapes and 12 number
  words. Anything outside that lexicon falls through to a `-1` sentinel
  rather than a structured parse error.
- **Disambiguation.** `twice 5 plus 3` is `(2*5) + 3`, not `2 * (5+3)`,
  because the rule reads left-to-right with no precedence shape. The
  grammar is right-shape-by-design, not by user intent. Real NL parsing
  needs more rule.
- **Reverse direction (recipe -> NL).** This is the named-pending sibling
  experiment. Walking a recipe back to readable English needs an NL
  emitter the body doesn't carry yet at the arithmetic altitude — the
  `nl-emit.fk` track is i18n surface bindings, not arithmetic generation.

## The teaching

A recipe is content-addressed; the kernel doesn't know or care which
modality wrote it. Two writers — one typing `the square of 7` into prose,
one typing `(mul 7 7)` into a `.fk` file — end up at the same node in
the lattice. The convergence is bytewise, not fuzzy: either the
serializations match or they don't.

This is the same property
[`02-cross-language-content-addressing`](../02-cross-language-content-addressing/)
proved between Python-shape and TypeScript-shape recursive trees, extended
down to the source-text altitude for NL specifically.

Lineage: [`lc-parsers-as-recipes`](../../../../docs/vision-kb/concepts/lc-parsers-as-recipes.md),
[`lc-one-kernel-many-tongues`](../../../../docs/vision-kb/concepts/lc-one-kernel-many-tongues.md),
[`lc-the-kernel-knows-itself`](../../../../docs/vision-kb/concepts/lc-the-kernel-knows-itself.md).
