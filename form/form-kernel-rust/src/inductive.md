# INDUCTIVE — algebraic datatypes on the Rust kernel

Rust leg of the cross-kernel INDUCTIVE quartet. Mirrors TS (#21) and
Python (#33); coordinates with Go (sibling agent). Builds on the same
content-addressed substrate the Rust kernel already has — `make_inductive`
returns the same NodeID for structurally identical inductive definitions,
which is what makes cross-kernel content-addressing fall out for free.

## Cross-kernel contract

| Concept       | Rust constant            | Slot |
| ------------- | ------------------------ | ---- |
| INDUCTIVE     | `RBASIC_INDUCTIVE`       | 71   |
| CONSTRUCTOR   | `RBASIC_CONSTRUCTOR`     | 72   |
| CHOICE_MATCH  | `RBASIC_CHOICE_MATCH`    | 35   |
| ctor-tag triv | `TRIV_CONSTRUCTOR_TAG`   | 15   |

Built-in inductives installed by `install_builtin_inductives`:

| Inductive   | Constructors                 |
| ----------- | ---------------------------- |
| `Nat`       | `zero`, `succ Nat`           |
| `Bool`      | `false`, `true`              |
| `Option[T]` | `none`, `some T`             |
| `Result[T,E]` | `ok T`, `err E`            |
| `List[T]`   | `nil`, `cons T (List T)`     |

## Recipe shapes

```
INDUCTIVE[
  type-name     : Triv.STRING        ; "Nat", "List", ...
  type-params   : RB_LIST            ; parametric types (T, E, ...)
  ctor0..ctorN  : RBASIC_CONSTRUCTOR ; constructors as type definitions
]

CONSTRUCTOR[                          ; type definition (inside an inductive)
  inductive-ref : NodeID             ; self-name trivial during definition
  ctor-name     : Triv.STRING
  ctor-index    : Triv.INT
  arg-type0..N  : NodeID             ; type-recipes (self-ref allowed)
]

CONSTRUCTOR[                          ; value application (in code)
  inductive-ref : NodeID             ; the inductive's NodeID (resolved)
  ctor-name     : Triv.STRING
  ctor-index    : Triv.INT
  arg-recipe0..N: NodeID             ; value-recipes
]

CHOICE_MATCH[
  scrutinee     : NodeID             ; value-recipe that walks to a ctor
  arm0-name     : Triv.STRING
  arm0-body     : NodeID
  arm1-name     : Triv.STRING
  arm1-body     : NodeID
  ...
]
```

## Surface

`make_inductive(k, name, params, ctors)` interns the INDUCTIVE recipe and
returns its NodeID. `make_constructor(k, inductive, ctor_name, args)`
applies a constructor to value-recipe args, producing a value-recipe.
`walk_constructor(k, node)` materializes a CONSTRUCTOR value-recipe into a
`CtorValue { inductive, ctor_name, ctor_index, args }`. `make_choice` /
`walk_choice` build and walk pattern-match recipes; `match_value` is the
Rust-side imperative entry point — handler closures keyed by ctor name,
panicking on non-totality.

`is_total(k, inductive, &arm_names)` answers the totality question
without requiring a walk; the CHOICE walker reuses it on every match.

## Convenience builders

`nat_zero`, `nat_succ`, `nat_of(k, inds, n)` build Nat values from a Rust
integer. `list_nil`, `list_cons` build List values. `nat_to_int`,
`list_length` decode walked ctor values back to Rust primitives.

## Composition with QUOTIENT

Z := (Nat × Nat) / equiv lands when this module sits next to the Rust
QUOTIENT port (#35). The substrate cells compose:

1. `make_inductive` defines `Nat`.
2. A pair carrier (another inductive or RB_LIST) holds (a, b).
3. `make_quotient_recipe` wraps the pair carrier with
   `equiv_integer_from_nat_pair`.

Two raw representatives of the same integer canonicalize to the same
NodeID through QUOTIENT's `intern_quotient_value`. The Python test
(`api/tests/test_inductive.py::test_z_quotient_of_nat_pairs`) exercises
this end-to-end; the Rust composition test is gated until both arms
land on the same branch.

## Cross-kernel test contract

`cargo test --release` is the Rust leg of the INDUCTIVE conformance
quartet. The 12 unit tests in `inductive.rs` mirror the TS
`inductive.test.ts` shape one-for-one:

- Cross-kernel slot agreement (71/72/35/15)
- Nat round-trip 0..5
- List length
- Option match-covers
- Option match-missing-arm panics
- CHOICE recipe totality-check rejects missing arm
- CHOICE recipe total match returns arm body
- Custom Color inductive with NodeID-equality across structurally-identical
  definitions
- Constructor-index lookup
- Built-in inductives have expected ctor lists
- `install_builtin_inductives` is idempotent
- CtorValue carries inductive ref + index

## What's deferred

- **Dependent inductives** where constructor arg types depend on values —
  parametric/dependent-types work (task #22).
- **Higher inductive types** (constructors for equality paths) — open
  question; additive slot space (`73`+) leaves room.
- **GADTs** — deferred; the current encoding doesn't express per-ctor
  refinement of return types.
- **Coinductive types** — separate corecursive arm; deferred.
- **Form-runtime walker integration** — these arms run through the Rust
  test surface today; full dispatch from `walk()` in `main.rs` is the
  next breath (mirrors TS's pending dispatch).
