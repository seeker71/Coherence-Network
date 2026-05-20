# QUOTIENT — canonicalization under equivalence (Python kernel)

> *Substrate content-addressing IS univalence at the recipe level. QUOTIENT
> makes that property reach into the value layer: two values equivalent
> under a relation receive the same NodeID.*

QUOTIENT is the foundation arm of Form's higher-mathematics surface
(PROOF, INDUCTIVE, symmetry-aware canonicalization all build on it). It
generalizes the canonicalization the numeric-format library already
performs (NaN → quiet, ±0 → +0): instead of hard-coded float rules, the
equivalence relation is a **substrate cell** the interner reads at
canonicalization time.

This document is the Python-kernel companion to
[`experiments/form-kernel-ts/src/quotient.md`](../../../../experiments/form-kernel-ts/src/quotient.md).
The architectural shape, handler-name vocabulary, and decidability
policy are shared across kernels — the same equivalence-recipe lands at
structurally-matching NodeIDs in TS and Python by construction.

## The shape

```form
QUOTIENT[carrier-recipe, equivalence-recipe]
```

- **Carrier** — the underlying recipe whose values get quotiented (e.g.
  a pair-recipe for `(N × N)` representing integers as differences of
  naturals).
- **Equivalence** — a substrate cell carrying
  `(name, decidability, strategy, handler_name)`. Two values are
  equivalent iff their canonical forms (computed by the handler) share
  children.

Interning a value through `intern_quotient_value(session, Q, raw_children)`:

1. Resolve the equivalence cell from the QUOTIENT recipe's second child.
2. Run the equivalence's `canonicalize_fn` on `raw_children`, producing
   `canonical_children`.
3. Intern a recipe whose category is QUOTIENT (instance=2 for canonical
   values, =3 for lazy/raw) and whose children are
   `[quotient_recipe, *canonical_children]`.

Same canonical children always intern to the same NodeID. That is the
quotient.

## Registering equivalence relations as substrate cells

Equivalences are substrate writes — the kernel stays small. Each arrives
as two halves:

```python
from app.services.substrate.quotient import (
    Decidability, make_equivalence, register_handler,
    make_quotient_recipe, intern_quotient_value, quotient_equal,
)

# 1. Register the runtime handler under a stable name.
#    Same name across Python / TS / Go / Rust kernels yields cross-kernel
#    NodeID agreement for the same equivalence relation.
def my_canonicalize(session, raw):
    # raw: Sequence[NodeID] — the carrier-shape children of the value
    # returns: Sequence[NodeID] — the canonical-children-tuple
    ...

register_handler("my-equivalence", my_canonicalize)

# 2. Write the equivalence-recipe as a substrate cell.
my_eq = make_equivalence(
    session,
    equivalence_name="my-equivalence",
    decidability=Decidability.DECIDABLE_CHEAP,
    handler_name="my-equivalence",
)

# 3. Build a quotient recipe over a carrier.
Q = make_quotient_recipe(session, carrier, my_eq.node_id)

# 4. Intern values — equivalent representatives receive the same NodeID.
v1 = intern_quotient_value(session, Q, [a, b])
v2 = intern_quotient_value(session, Q, [c, d])
quotient_equal(session, v1, v2)   # True iff (a, b) ~ (c, d)
```

## Built-in library

`build_quotient_library(session)` returns the bootstrap set:

| Name | Quotient | Canonical form |
|---|---|---|
| `EQUIV_INTEGER_FROM_NAT_PAIR` | `(N × N) / ~` with `(a, b) ~ (c, d) iff a + d = b + c` | `(a - b, 0)` |
| `EQUIV_RATIONAL_FROM_INT_PAIR` | `(Z × Z*) / ~` with `(p, q) ~ (r, s) iff p*s = q*r` | `(p/gcd, q/gcd)`, sign in numerator |
| `EQUIV_COMMUTATIVE_PAIR` | `(a, b) ~ (b, a)` | sorted by `(package, level, type_, instance)` |
| `EQUIV_ASSOCIATIVE_LEFT_FOLD` | flat children passthrough (full left-fold canonicalization lives at the symmetry-aware arm) | unchanged |

## Decidability + canonicalization strategy

Each equivalence carries one of three decidability codes:

| Code | Meaning | Strategy |
|---|---|---|
| `DECIDABLE_CHEAP` | Effective algorithm, cheap to run | **EAGER** — canonicalize at intern, fast equality |
| `DECIDABLE_HEAVY` | Effective algorithm, expensive (Knuth-Bendix, full rewriting) | **LAZY** — intern raw, canonicalize on equality query |
| `UNDECIDABLE` | No effective algorithm (group iso in general, function equality) | **LAZY** + (future) requires explicit proof recipe to merge NodeIDs |

Honest default: EAGER unless the equivalence declares heavy or
undecidable. Open architectural questions (axiomatic equivalences
requiring a proof recipe; the full "lazy + axiom" flow) live in
[`docs/coherence-substrate/higher-math-surface.md`](../../../../docs/coherence-substrate/higher-math-surface.md)
— they are follow-ups, not this breath.

## Building new quotient types

### Free monoid mod relations

A free monoid over alphabet `A` is `A* / =`. To add a rewriting system
(e.g. `aa = e` makes `Z/2Z`), register a handler that reduces the word
to normal form via your rewrite system. Cheap rewrite systems
(length-reducing, confluent) declare `DECIDABLE_CHEAP`; Knuth-Bendix
completions that may not terminate declare `DECIDABLE_HEAVY`.

### Polynomial ring mod ideal

`k[x_1, ..., x_n] / I` for an ideal `I` given by a Gröbner basis. The
handler reduces a polynomial to its remainder modulo the Gröbner basis.
This is `DECIDABLE_HEAVY` (Gröbner basis computation is expensive but
finite for sufficiently nice ideals).

### T-dual string-theory backgrounds

A background recipe interned under the T-duality QUOTIENT collapses
both `R`-radius and `α'/R`-radius forms to one NodeID. The handler
computes a canonical radius (e.g. the smaller of the two, or always
the geometric one when both are present).

### Mirror-symmetric Calabi-Yau pairs

Same shape as T-duality but the canonical form is a chosen
representative in each Hodge-diamond pair.

## Cross-kernel agreement

The promise: a substrate cell ingested via a Form program lands at the
same NodeID across all kernels (TS, Go, Rust, Python). For QUOTIENT
this requires the handler-name vocabulary to be shared — the names
`integer-from-nat-pair`, `rational-from-int-pair`, `commutative-pair`,
and `associative-left-fold` resolve to the same canonicalization in
every kernel. Adding a new built-in equivalence is a cross-kernel
coordination breath; adding a Form-program-local equivalence
(handler-as-Form-recipe) is a substrate write only and needs no
cross-kernel coordination.

The Python kernel's `intern_node` auto-allocates resulting NodeID
instance numbers (whereas the TS kernel preserves caller-supplied
inst). The category-instance value still flows through `serialize_tree`
into the row's serialized field, so two values with different
category-instances always land at different rows — content-addressing
holds, and canon-vs-lazy distinction is read off the serialized prefix
via `_row_category_instance` rather than the resulting NodeID's inst.

## Forward-compat: Form-recipe handlers

Today a handler is a registered Python function — registration happens
imperatively in Python (or in TS / Go / Rust on the cognate side). The
next step is **handlers-as-Form-recipes**: the canonicalize_fn itself
expressed as a Form recipe stored in the substrate. The kernel then
reads the handler-recipe and walks it at canonicalization time, with
no per-language registration. This unlocks pure-substrate equivalence
authoring — new mathematics arrives as substrate writes only, no
kernel patch in any language. It is task follow-up; the structural
hooks (handler-name → cell-NodeID resolution) are already in place.

## What is deferred

- Symmetry-aware canonicalization at the MATH/LOGIC arm level —
  applying QUOTIENT to specific RBasic arms so e.g. `(+ 1 2)` and
  `(+ 2 1)` intern to the same NodeID under commutative
  canonicalization registered on `RBasic.MATH` / `RMath.PLUS`.
- PROOF + INFERENCE arms that depend on QUOTIENT for definitional
  equality.
- HoTT-style higher equality (paths, paths-between-paths) — open
  architectural question; the Level hierarchy gives a natural home but
  the surface needs design.
- Full mathlib bootstrap — multi-year arc.
