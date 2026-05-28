# 60-xpath — XPath-style queries over substrate trees

> Substrate trees are just Recipes whose children are Recipes whose
> children are leaves. Once that shape is given, the obvious lens is
> XPath: a string names the walk, the evaluator carries it. Three
> sibling kernels parse the same path string, walk the same tree, and
> return the same five attestations.

## What walked

```
$ ./validate.sh form-stdlib/symbols.fk form-stdlib/xpath.fk \
                form-samples/cross-modal/60-xpath/xpath.fk
  ✓  → all-bindings-count: 3
       first-binding-name-matches: 1
       at-inst-match-count: 1
       first-hit-found: 1
       first-miss-found: 0
       5
  1 ok, 0 divergent — kernels agree on every sample.
```

## The shape

```
   root
     └─ SYMBOL-TABLE (cat-inst 1731)
          ├─ SYMBOL-BIND (cat-inst 1730)
          │    ├─ "first-name"
          │    └─ 100
          ├─ SYMBOL-BIND
          │    ├─ "second-name"
          │    └─ 200
          └─ SYMBOL-BIND
               ├─ "third-name"
               └─ 300
```

Four queries exercise the path syntax against this tree:

| Query                                          | Result            | Notes                              |
|------------------------------------------------|-------------------|------------------------------------|
| `/cat:1731/*`                                  | 3 NodeIDs         | wildcard over table's children     |
| `/cat:1731/cat:1730[0]/*[0]/text()`            | "first-name"      | positional + leaf-text             |
| `/cat:1731/cat:1730[@inst=N]`                  | 1 NodeID          | inst-equality predicate            |
| `/cat:9999` via `xpath-first`                  | XPATH-NOT-FOUND   | sentinel on miss                   |

## Path syntax

```
/                          root (the passed-in cell)
/step                      children of current matching step
/step/step                 nested descent
//step                     descendant-or-self
*                          wildcard (all children)
text()                     trivial value of the current leaf
@inst                      access the inst slot
@type                      access the type slot
[N]                        positional predicate (0-based)
[@inst=N]                  inst-equality predicate
[text()='foo']             trivial-text predicate
[count()=N]                arity predicate
```

Selectors:
- `cat:N` — children whose category's inst slot equals N.
- `name:s` — children that are trivial strings with value s.
- `*` — every child at this level.

## API

```
(xpath path-string root-nid)       → list of matching NodeIDs
(xpath-first path-string root-nid) → first match, or XPATH-NOT-FOUND
(xpath-found? result)              → 1 / 0 (pairs with xpath-first)
```

## Why this is sovereign

The path string carries the same meaning into any sibling kernel.
The evaluator composes only kernel primitives — `node_category`,
`node_children`, `node_inst`, `node_value`, `intern_node`,
`intern_trivial_*`, plus the canonical string natives (`str_eq`,
`substring`, `str_find`, `str_to_int`). No host XPath library, no
external dependency; the recipe MEANS XPath.

Content-addressing makes the queries work cross-cell: a cell that
authors `/cat:1731/*` and a cell that runs it against bytes received
over a channel address the same Blueprint inst-slots, because both
sides interned the same SYMBOL-TABLE Blueprint at NodeID
`(make_nodeid 1 2 99 1731)`.

## Files

- `xpath.fk` — the four-query sample + 5-line verdict.
- `form-stdlib/xpath.fk` — the parser + evaluator + Blueprints
  (1910..1913).
- `form-stdlib/tests/xpath-band.fk` — sibling-witness band covering
  every step kind and every predicate.

## Cross-refs

- 21-cell-query-protocol — questions cells ask each other; xpath is
  the natural query shape over the receiver's substrate.
- 47-schema — recipes-validate-recipes; sibling pattern for
  recipe-shaped operators over recipe-shaped data.
- 50-tree-diff — structural diff over the same kind of tree.
- 51-symbols-merge — set algebra over symbol tables; xpath is the
  read-side cousin of those write-side operations.
