# 51-symbols-merge — set algebra over symbol tables

> Once two cells exchange symbol tables, they want to compose them.
> Union (with a winner), strict union (with a conflict signal),
> intersection, difference. Four operations, one substrate-resident
> sentinel, identical verdicts across three sibling kernels.

## What walked

```
$ ./validate.sh form-stdlib/symbols.fk form-stdlib/symbols-merge.fk \
                form-samples/cross-modal/51-symbols-merge/symbols-merge.fk
  ✓  → merge-count: 3
       merge-a-is-1: 1
       merge-b-is-20: 1
       merge-c-is-30: 1
       strict-is-conflict: 1
       strict-disjoint-count: 3
       intersect-count: 1
       intersect-b-is-2: 1
       intersect-a-missing: 1
       diff-count: 1
       diff-head-is-a: 1
       10
  1 ok, 0 divergent — kernels agree on every sample.
```

Three sibling kernels (Go, Rust, TypeScript) compose the same two tables,
run all four operations, and arrive at the same 10-line verdict.

## The shape

```
   table A:  {a → 1,  b → 2}
   table B:  {b → 20, c → 30}
```

Four operations form the natural set algebra over symbol tables:

| Operation                       | Result                       | Why                        |
|---------------------------------|------------------------------|----------------------------|
| `(symbols-merge        A B)`    | `{a→1, b→20, c→30}`          | A ∪ B; B wins on overlap   |
| `(symbols-merge-strict A B)`    | `SYMBOLS-CONFLICT`            | `b` appears in both        |
| `(symbols-merge-strict A D)`    | `{a→1, b→2, d→40}`           | disjoint → concat succeeds |
| `(symbols-intersect    A B)`    | `{b → 2}`                    | keys ∩; A's values         |
| `(symbols-diff         A B)`    | `[a]`                        | name-list of A − B keys    |

`SYMBOLS-CONFLICT` is a substrate-resident sentinel — Blueprint NodeID
`(make_nodeid 1 2 99 1810)`. Callers compare with `node_eq` to
distinguish "merged table" from "conflict refused."

## Why this is set algebra, not generic dict merge

A symbol table is a Recipe — its bindings are children, names are
trivial-string leaves, values are arbitrary Recipes. "Same name" is
content-addressed: `(node_inst (intern_trivial_string "b"))` returns
the same id on every kernel. So overlap detection is a NodeID equality
sweep, never a string comparison.

That's load-bearing for the cross-cell story:

- **Cell A** authors `{a→1, b→2}`, serializes via `recipe_to_bytes`, sends.
- **Cell B** receives, `bytes_to_recipe`s, and now holds the same table
  by NodeID. Its own `{b→20, c→30}` and the received `{a→1, b→2}` merge
  under the same name-id arithmetic regardless of which kernel B runs.

The four operations are the natural composition: when two cells meet,
they want to know *what they share* (intersect), *what one has the other
doesn't* (diff), *how to combine them* (merge), and *whether their
combination has a conflict that needs human attention* (merge-strict).

## Files

- `symbols-merge.fk` — the four-operation walk + verdict.
- `form-stdlib/symbols-merge.fk` — the operations.
- `form-stdlib/tests/symbols-merge-band.fk` — sibling-witness band.

## Cross-refs

- 25-end-to-end-channel — the wire path symbol tables flow through.
- 24-wire-binary-symbols — content-addressing makes the merge sovereign.
- 23-cell-registry-osi — registry messages whose payloads are symbol tables.
- 47-schema — recipes-validate-recipes; the sibling pattern for
  recipe-shaped operators over recipe-shaped data.
