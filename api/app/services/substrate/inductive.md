# INDUCTIVE / CONSTRUCTOR / CHOICE — algebraic datatypes (Python kernel)

> *Constructors are the alphabet of structure; pattern-matches are the
> grammar that reads it. The substrate gives both for free — content-
> addressing makes structurally identical inductives the same cell.*

INDUCTIVE introduces algebraic datatypes to the substrate as
content-addressed recipe cells. Once an inductive's name, parameters,
and constructor list are fixed, two definitions that agree on those
three things hash to the SAME NodeID — cross-document equivalence comes
for free.

This document is the Python-kernel companion to
[`experiments/form-kernel-ts/src/inductive.md`](../../../../experiments/form-kernel-ts/src/inductive.md).
The structural shapes, slot numbers, and constructor-name vocabulary
are shared across kernels — the same `Nat`, `zero`, `succ` definitions
land at structurally-matching NodeIDs in TS and Python by construction.

## The three arms

| Slot | Arm | Purpose |
|------|-----|---------|
| 71 | `RBasic.INDUCTIVE` | type definition — `Nat`, `List[T]`, `Result[T, E]`, ... |
| 72 | `RBasic.CONSTRUCTOR` | constructor declaration (inside an inductive) AND constructor application (value) |
| 35 | `RBasic.CHOICE_MATCH` | pattern-match with totality checking |

Slot 35 is named `CHOICE_MATCH` in Python to disambiguate from the
pre-existing `RBasic.CHOICE = 20` (BML angelic-nondeterminism:
`choose` / `fail` / `stop`). The structural slot (35) is what carries
cross-kernel agreement; the name is local Python convention.

## INDUCTIVE recipe shape

```
INDUCTIVE[
  type-name        : Triv.STRING        ; "Nat", "List", ...
  type-params      : RBasic.BLOCK/SEQUENCE ; parametric types (T, E, ...)
  ctor0            : RBasic.CONSTRUCTOR ; the type's constructors
  ctor1            : RBasic.CONSTRUCTOR ;
  ...
]
```

The `type-params` list uses `RBasic.BLOCK` with instance `RBlock.SEQUENCE`
in Python, matching the structural-composition discipline. The TS kernel
uses `RBasic.LIST = 34` for the same role; the two encodings differ at
the substrate layer but carry identical Form semantics.

## CONSTRUCTOR recipe shape

Two uses, same shape:

**Type-definition** (nested inside an INDUCTIVE):

```
CONSTRUCTOR[
  inductive-ref    : Triv.STRING  ; self-ref via type-name (the parent
                                 ;   inductive's NodeID isn't known yet)
  ctor-name        : Triv.STRING
  ctor-index       : Triv.INT
  arg-type0        : NodeID       ; type-recipe (self-ref by name allowed)
  arg-type1        : NodeID
  ...
]
```

**Value-application** (produced by `make_constructor(session, inductive, name, args)`):

```
CONSTRUCTOR[
  inductive-ref    : NodeID       ; the actual inductive's NodeID
  ctor-name        : Triv.STRING
  ctor-index       : Triv.INT
  arg0             : NodeID       ; value-recipe
  arg1             : NodeID
  ...
]
```

`walk_constructor(session, node)` materializes a value-application into
a `CtorValue` dataclass.

## CHOICE_MATCH recipe shape

```
CHOICE_MATCH[
  scrutinee        : NodeID       ; a value-recipe walking to a CtorValue
  arm0-ctor-name   : Triv.STRING
  arm0-body        : NodeID
  arm1-ctor-name   : Triv.STRING
  arm1-body        : NodeID
  ...
]
```

`walk_choice(session, node)` reads the scrutinee's inductive, verifies
every declared constructor appears among the arms (raises `ValueError`
on `non-total — missing constructor(s): ...` otherwise), then dispatches
on the scrutinee's `ctor_name`.

## Built-in inductives

`install_builtin_inductives(session)` interns the standard library:

```python
Nat       ::= zero | succ Nat
Bool      ::= false | true
Option[T] ::= none  | some T
Result[T,E] ::= ok T | err E
List[T]   ::= nil   | cons T (List T)
```

Self-references (`succ Nat`, `cons T (List T)`) carry the type-name
trivial as a sentinel — the recursive position is read by the walker
through the constructor's name lookup rather than a closed NodeID
cycle.

## Convenience builders

```python
nat_zero(session, inds)               # → CONSTRUCTOR value-recipe
nat_succ(session, inds, prev)         # → CONSTRUCTOR value-recipe
nat_of(session, inds, n)              # → succ(succ(...zero))   n levels
list_nil(session, inds)               # → CONSTRUCTOR value-recipe
list_cons(session, inds, head, tail)  # → CONSTRUCTOR value-recipe

# Decoders — walk a value back to a Python primitive
nat_to_int(walk_value(session, node))     # → int
list_length(walk_value(session, node))    # → int
```

## Pattern-matching at the kernel layer

For tests and kernel-internal helpers there's an imperative entry point:

```python
match_value(session, ctor_value, [
    ("zero", lambda args: 0),
    ("succ", lambda args: 1 + nat_to_int(args[0])),
])
```

Non-total matches raise `ValueError(missing: ...)` before any arm runs.

For surface Form, `make_choice(session, scrutinee, arms)` interns a
CHOICE_MATCH recipe directly; the walker enforces totality at walk
time.

## Composing with QUOTIENT

An inductive type can serve as the carrier of a quotient. The classical
example — integers as `Z := (N × N) / ~` where `(a, b) ~ (c, d) ⇔ a+d = b+c`:

```python
inds = install_builtin_inductives(session)
lib  = build_quotient_library(session)

# Quotient of Nat-pairs by the integer-from-nat-pair equivalence.
Q = make_quotient_recipe(
    session, inds.Nat, lib.EQUIV_INTEGER_FROM_NAT_PAIR.node_id,
)

# Two representatives of +2 share a NodeID.
v_3_1 = intern_quotient_value(session, Q, [int_trivial(3), int_trivial(1)])
v_5_3 = intern_quotient_value(session, Q, [int_trivial(5), int_trivial(3)])
assert v_3_1 == v_5_3
```

The Nat inductive's NodeID becomes the carrier; the QUOTIENT recipe's
NodeID is a *different* category arm (slot 70 vs slot 71). Composition
across arms drops out of the substrate's content-addressing — neither
arm has to know about the other.

## Cross-kernel agreement

Handler names and constructor names are part of the cross-kernel
contract. Python and TS agree on:

- Slot numbers: INDUCTIVE = 71, CONSTRUCTOR = 72, CHOICE = 35
- Built-in constructor names: `zero`, `succ`, `false`, `true`, `none`,
  `some`, `ok`, `err`, `nil`, `cons`
- Inductive type names: `Nat`, `Bool`, `Option`, `Result`, `List`

The intern-layer encodings of `type-params` and integer trivials differ
between kernels (TS uses `RBasic.LIST`; Python uses
`RBasic.BLOCK/SEQUENCE`; TS uses lossy `int + 1`, Python uses the
sign-bijective `2v+1 / 2(-v)` encoding shared with `quotient.py`). The
*Form-program-level* observations — what `nat_to_int` returns, what
constructors a `Color` declares, whether a match is total — are
identical.

## See also

- [`api/app/services/substrate/inductive.py`](inductive.py) — the implementation
- [`api/app/services/substrate/quotient.md`](quotient.md) — the companion arm
- [`experiments/form-kernel-ts/src/inductive.ts`](../../../../experiments/form-kernel-ts/src/inductive.ts) — TS reference
- [`docs/coherence-substrate/higher-math-surface.md`](../../../../docs/coherence-substrate/higher-math-surface.md) — full higher-math surface design
