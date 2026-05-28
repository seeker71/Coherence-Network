# 50-tree-diff — structural diff and patch as a Form recipe

## What walked

```
$ ./validate.sh form-stdlib/tree-diff.fk \
                form-samples/cross-modal/50-tree-diff/tree-diff.fk
  ✓  tree-diff.fk+tree-diff.fk → scenario-1-diff-equal: 1
                                 scenario-1-patch-eq-b: 1
                                 scenario-1-empty: 1
                                 scenario-2-diff-children: 1
                                 scenario-2-kid0-equal: 1
                                 scenario-2-kid1-replace: 1
                                 scenario-2-nonempty: 1
                                 scenario-2-patch-eq-b: 1
                                 scenario-3-diff-replace: 1
                                 scenario-3-patch-eq-b: 1
                                 10
  1 ok, 0 divergent — kernels agree on every sample.
```

Three sibling kernels (Go, Rust, TypeScript) each computed the same
diffs and the same patched reconstructions. The diff walker uses only
substrate primitives — `node_eq`, `node_category`, `node_children`,
`intern_node` — so the diff's meaning is sovereign across kernels.

## The shape

A DIFF is itself a Recipe. Three variants, each a recipe interned
under its own application category:

```
(diff-equal)                 ; trees match at this position
(diff-replace new-recipe)    ; replace whole subtree with new-recipe
(diff-children child-diffs)  ; categories match; recurse pairwise
```

Two primary operations:

```
(tree-diff a b)  → DIFF Recipe.
(tree-patch a d) → Recipe. (tree-patch a (tree-diff a b)) == b.
```

Plus the empty predicate:

```
(diff-empty? d) → 1 if d records no change anywhere, else 0.
```

The walker decides between the three diff arms in this order:

1. `node_eq a b` → `(diff-equal)`. Content-addressing makes structural
   identity a single op; same NodeID means same shape all the way down.
2. Same category AND same child arity → recurse pairwise into the
   children; wrap in `(diff-children ...)`.
3. Anything else (different category OR different arity) →
   `(diff-replace b)` carrying the whole replacement subtree.

Carrying the new subtree inside `diff-replace` is what lets `tree-patch`
reconstruct `b` from `a + diff` alone — no external corpus, no second
pass over the source.

## The three sample scenarios

1. **`scenario-1` — identical trees.** Two recipes
   `PLUS(N, N)` built from the same Blueprints. Content-addressing
   makes them the same NodeID; `tree-diff` returns `(diff-equal)`;
   `tree-patch` returns the original; `diff-empty?` is `1`.

2. **`scenario-2` — leaf substitution.** Two `PLUS`-rooted recipes
   differing in one leaf — `PLUS(N, N)` vs `PLUS(N, MINUS)`. Same
   category, same arity (2) → the walker descends. The first child is
   identical (`N == N`) → `(diff-equal)`. The second child differs
   (`N` is a different NodeID than `MINUS`-leaf) → `(diff-replace MINUS)`.
   The root diff is `(diff-children [(diff-equal), (diff-replace ...)])`.
   `tree-patch` reconstructs `PLUS(N, MINUS)` byte-for-byte — `node_eq`
   on the rebuilt recipe and the original `b` returns true because the
   substrate interns the rebuilt node to `b`'s NodeID.

3. **`scenario-3` — root category differs.** `PLUS(N, N)` vs `MINUS(N, N)`.
   `node_eq` on the categories fails immediately → no descent; the diff
   collapses to `(diff-replace MINUS(N, N))`. `tree-patch` returns the
   replacement subtree unchanged.

The verdict sums ten binary checks across the three scenarios; sibling
parity over the verdict (every kernel returns `10`) attests that all
three walk the diff and patch trees the same way.

## Why this is a recipe, not a host diff library

The DIFF is content-addressed. A diff computed in cell A (Go kernel) and
a diff computed in cell B (TypeScript kernel) intern to the same NodeID
— they ARE the same diff. The patch is canonical across kernels too;
applying the diff in any sibling kernel reconstructs the same target
Recipe with byte-identical NodeID.

This is the layer above 04-universal-diff: that sample walked two trees
and *named* their structural difference for a reader; this one
*materializes* the difference as a recipe that can cross a wire, be
re-applied, composed with another diff, or stored. The Form recipe IS
the structural-diff implementation; no diff native exists in any kernel.

A diff Recipe is also a tree, so `tree-diff` composes with itself:
`(tree-diff d1 d2)` describes how two diffs differ, which is what the
substrate needs for incremental change propagation across cells.

## Cross-refs

- [`form-stdlib/tree-diff.fk`](../../../form-stdlib/tree-diff.fk) — the canonical recipe
- [`form-stdlib/tests/tree-diff-band.fk`](../../../form-stdlib/tests/tree-diff-band.fk) — the sibling-witness band
- `04-universal-diff` — the predecessor: walking two trees and naming the delta for a reader
- `47-schema` — sibling shape-walker that validates a recipe against a schema recipe
- `17-novel-nodes` — recipes as the structural identity that crosses cells
- `33-merkle` — sibling content-addressed reconciliation primitive
