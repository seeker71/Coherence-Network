# QUOTIENT — canonicalization under equivalence

> *Substrate content-addressing IS univalence at the recipe level. QUOTIENT
> makes that property reach into the value layer: two values equivalent
> under a relation receive the same NodeID.*

QUOTIENT is the foundation arm of Form's higher-mathematics surface (PROOF,
INDUCTIVE, symmetry-aware canonicalization all build on it). It generalizes
the canonicalization the format library already performs (NaN to quiet,
±0 to +0): instead of hard-coded float rules, the equivalence relation is
a **substrate cell** the interner reads at canonicalization time.

## The shape

```form
QUOTIENT[carrier-recipe, equivalence-recipe]
```

- **Carrier** — the underlying recipe whose values get quotiented (e.g. a
  pair-recipe for `(N × N)` representing integers as differences of naturals).
- **Equivalence** — a substrate cell carrying `(name, decidability,
  strategy, handler_name)`. Two values are equivalent iff their canonical
  forms (computed by the handler) share children.

Interning a value through `intern_quotient_value(k, Q, raw_children)`:

1. Resolve the equivalence cell from the QUOTIENT recipe's second child.
2. Run the equivalence's `canonicalize_fn` on `raw_children`, producing
   `canonical_children`.
3. Intern a recipe whose category is QUOTIENT (inst=2 for canonical values)
   and whose children are `[quotient_recipe, ...canonical_children]`.

Same canonical children always intern to the same NodeID. That's the quotient.

## Registering a new equivalence

Equivalences are substrate writes — the kernel stays small. Each arrives
as two halves:

```ts
import { registerHandler, makeEquivalence, Decidability } from "./quotient.ts";

// 1. Register the runtime handler under a stable name.
//    Same name across Python / Go / Rust / TS kernels for cross-kernel
//    NodeID agreement.
registerHandler("my-equivalence", (k, raw) => {
  // raw: readonly NodeID[] — the carrier-shape children of the value
  // returns: readonly NodeID[] — the canonical-children-tuple
  return /* canonicalized children */;
});

// 2. Write the equivalence-recipe as a substrate cell.
const myEq = makeEquivalence(k, {
  equivalence_name: "my-equivalence",
  decidability: Decidability.DECIDABLE_CHEAP,
  handler_name: "my-equivalence",
});

// 3. Build a quotient recipe over a carrier.
const Q = make_quotient_recipe(k, carrier, myEq.nodeID);

// 4. Intern values; equivalent representatives receive the same NodeID.
const v1 = intern_quotient_value(k, Q, [a, b]);
const v2 = intern_quotient_value(k, Q, [c, d]);
quotient_equal(k, v1, v2);  // true iff (a,b) ~ (c,d)
```

## Built-in library

`buildQuotientLibrary(k)` returns the bootstrap set:

| Name | Quotient | Canonical form |
|---|---|---|
| `EQUIV_INTEGER_FROM_NAT_PAIR` | `(N × N) / ~` with `(a,b) ~ (c,d) iff a+d=b+c` | `(a-b, 0)` |
| `EQUIV_RATIONAL_FROM_INT_PAIR` | `(Z × Z*) / ~` with `(p,q) ~ (r,s) iff p*s=q*r` | `(p/gcd, q/gcd)`, sign in numerator |
| `EQUIV_COMMUTATIVE_PAIR` | `(a,b) ~ (b,a)` | sorted by NodeID order key |
| `EQUIV_ASSOCIATIVE_LEFT_FOLD` | flat children passthrough (real left-fold canonicalization lives at the symmetry-aware arm) | unchanged |

## Decidability + canonicalization strategy

Each equivalence carries one of three decidability codes:

| Code | Meaning | Strategy |
|---|---|---|
| `DECIDABLE_CHEAP` | Effective algorithm, cheap to run | **EAGER** — canonicalize at intern, fast equality |
| `DECIDABLE_HEAVY` | Effective algorithm, expensive (Knuth-Bendix, complete rewriting) | **LAZY** — intern raw, canonicalize on equality query |
| `UNDECIDABLE` | No effective algorithm (group iso in general, function equality) | **LAZY** + requires explicit proof recipe to merge NodeIDs |

The honest default: EAGER unless the equivalence declares heavy. Open
architectural questions (axiomatic equivalences requiring a proof recipe;
the full "lazy + axiom" flow) live in `docs/coherence-substrate/higher-
math-surface.md` — they're follow-ups, not this breath.

## Building new quotient types

### Free monoid mod relations

A free monoid over alphabet `A` is `A* / =`. To add a rewriting system
(e.g. `aa = e` makes `Z/2Z`), register a handler that reduces the word
to normal form via your rewrite system. Cheap rewrite systems (length-
reducing, confluent) declare `DECIDABLE_CHEAP`; Knuth-Bendix completions
that may not terminate declare `DECIDABLE_HEAVY`.

### Polynomial ring mod ideal

`k[x_1, ..., x_n] / I` for an ideal `I` given by a Gröbner basis. The
handler reduces a polynomial to its remainder modulo the Gröbner basis.
This is `DECIDABLE_HEAVY` (Gröbner basis computation is expensive but
finite for sufficiently nice ideals).

### T-dual string-theory backgrounds

A background recipe interned under the T-duality QUOTIENT collapses both
`R`-radius and `α'/R`-radius forms to one NodeID. The handler computes a
canonical radius (e.g. the smaller of the two, or always the geometric
one when both are present).

### Mirror-symmetric Calabi-Yau pairs

Same shape as T-duality but the canonical form is a chosen representative
in each Hodge-diamond pair.

## Cross-kernel agreement

The promise: a substrate cell ingested via a Form program lands at the
same NodeID across all kernels (TS, Go, Rust, Python). For QUOTIENT this
requires the handler-name vocabulary to be shared — `integer-from-nat-
pair` resolves to the same canonicalization in every kernel. Adding a
new built-in equivalence is a cross-kernel coordination breath; adding
a Form-program-local equivalence (handler-as-Form-recipe) is a substrate
write only and needs no cross-kernel coordination.

## What's deferred

- Python / Go / Rust ports of this arm (task follow-ups; same shape as
  here).
- Symmetry-aware canonicalization at MATH/LOGIC arm level — applying
  QUOTIENT to specific RBasic arms (task #23). E.g. `(+ 1 2)` and
  `(+ 2 1)` interning to the same NodeID under commutative
  canonicalization registered on RBasic.MATH/RMath.PLUS.
- PROOF + INFERENCE arms that depend on QUOTIENT for definitional
  equality (task #20).
- HoTT-style higher equality (paths, paths-between-paths) — open
  architectural question; the Level hierarchy gives a natural home but
  the surface needs design.
- Full mathlib bootstrap (task #24) — multi-year arc.
