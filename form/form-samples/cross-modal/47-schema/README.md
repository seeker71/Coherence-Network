# 47-schema — recipe-shape validation as a Form recipe

## What walked

```
$ ./validate.sh form-stdlib/schema.fk form-samples/cross-modal/47-schema/schema.fk
  ✓  schema.fk+schema.fk → tuple-match: 1
                          tuple-wrong-arity: 0
                          tuple-wrong-leaf: 0
                          list-mixed: 0
  1 ok, 0 divergent — kernels agree on every sample.
```

Three sibling kernels (Go, Rust, TypeScript) each ran the same four
validations and arrived at the same verdicts. The walker uses only
substrate primitives — `node_category`, `node_eq`, `node_level`,
`node_type`, `node_value`, `node_children` — so the schema's meaning is
sovereign across kernels.

## The shape

A SCHEMA is itself a recipe. Five variants, each a recipe interned
under its own application category:

```
(schema-cat cat-nid)        ; recipe's category equals cat-nid
(schema-leaf leaf-type)     ; recipe is a TRIVIAL leaf of given type
(schema-list child-schema)  ; recipe is a LIST whose every child matches
(schema-tuple sub-schemas)  ; recipe's children match positionally + arity
(schema-any)                ; matches anything
```

`(schema-validate schema recipe)` walks both and returns `1` if the shape
matches, `0` otherwise. The four scenarios in `schema.fk`:

1. **`tuple-match: 1`** — a person recipe `("ada", 37)` against the
   schema `(tuple (leaf TRIV_STRING) (leaf TRIV_INT))`. The walker
   checks arity (2 children, 2 sub-schemas), then descends into each
   leaf check.

2. **`tuple-wrong-arity: 0`** — a recipe with three children fails the
   same schema. `schema-positional?` walks both lists in parallel; one
   draining before the other returns 0.

3. **`tuple-wrong-leaf: 0`** — a recipe where the age slot carries a
   trivial-string instead of a trivial-int. The SCHEMA-LEAF arm checks
   `(node_level recipe) == LEVEL_TRIVIAL` and then
   `(node_type recipe) == leaf-type-int`. The wrong type collapses the
   match.

4. **`list-mixed: 0`** — a list containing two ints and a string fails
   `(schema-list (schema-leaf TRIV_INT))`. The SCHEMA-LIST arm requires
   every child to match the single child-schema; the first mismatch
   short-circuits to 0.

## Why this is a recipe, not a host validator

A schema is content-addressed. The same schema constructed by `Cell A`
in Go and `Cell B` in TypeScript interns to the same NodeID because the
substrate is canonical. A schema can cross any channel (registry
message, file, socket) via `recipe_to_bytes` / `bytes_to_recipe` and
arrive intact — `node_eq` attests structural identity on both sides.

The walker is a Form recipe too. The same source in
`form-stdlib/schema.fk` runs across all three sibling kernels with
byte-identical output. Recipe-walk is the canonical execution path;
JIT-aliasing into a host validator is an opt-in bootstrap (see
16-jit-registry for the alias mechanism).

## Cross-refs

- `form-stdlib/schema.fk` — the validator + variant constructors
- `form-stdlib/tests/schema-band.fk` — the sibling-witness band
- 17-novel-nodes — recipes as the structural identity that crosses cells
- 16-jit-registry — recipes as canonical truth, natives as opt-in speed
