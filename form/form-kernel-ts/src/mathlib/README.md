# mathlib — first formalization wave

Foundational mathematical structures expressed as Form recipes, composing
the higher-math arms already in tissue. This is the first wave of a
multi-year arc — not the whole 200K-theorem mathlib.

## What composes here

```
algebra.ts      — Nat ops, Z and Q as quotients, algebraic structures
order.ts        — Order / PartialOrder / TotalOrder
functions.ts    — Function / Injection / Surjection / Bijection
proofs.ts       — worked theorems as PROOF recipes
mathlib.test.ts — 32 assertions; all green
```

Each file pulls from the existing higher-math arms (`../quotient.ts`,
`../inductive.ts`, `../proof.ts`, `../symmetry.ts`) and from the kernel
itself (`../kernel.ts`). No kernel changes were needed; this is library
work atop the existing surface.

## Structural-equivalence as mathematical-equivalence

The substrate's content-addressing is univalence-at-the-recipe-level by
construction. Two structurally identical recipes share a NodeID. This
mathlib surfaces that property as **same group → same coordinate**:

- `(Z, +, 0)` built two different ways still interns to the same
  AbelianGroup-cell NodeID.
- `(3, 1)` and `(5, 3)` as integer representatives both canonicalize to
  the SAME NodeID under the integer-from-nat-pair quotient — they
  literally ARE the integer 2.
- `(3, 6)` and `(1, 2)` and `(-1, -2)` all share a NodeID as the
  rational 1/2 — gcd-reduction + sign-normalization are baked into the
  quotient handler.

This isn't a proof technique. It's the lattice's physics. "Up to
isomorphism" collapses into geometric identity at intern-time.

## What's covered in this wave

### Algebra

- **Nat** — re-exported from `../inductive.ts` (`Nat := zero | succ Nat`),
  plus operations defined here by structural recursion via `match_value`:
  - `nat_add`, `nat_mul`, `nat_le`, plus convenience NodeID forms.
- **Z** — `QUOTIENT[carrier_NxN, integer-from-nat-pair]`. The handler in
  `../quotient.ts` canonicalizes any `(a, b)` to its difference-form
  representative.
- **Q** — `QUOTIENT[carrier_ZxZ*, rational-from-int-pair]`. The handler
  canonicalizes by gcd-reducing and pushing sign into the numerator.
- **Monoid, Group, AbelianGroup, Ring, Field** — single-constructor
  INDUCTIVE recipes whose constructor packs the carrier, the
  operation(s), the identity(ies), and the axiom propositions.
- **Canonical instances** built in `buildMathlib`:
  - `NatPlusMonoid` — `(Nat, +, 0)` as a Monoid.
  - `ZAdditiveAbelianGroup` — `(Z, +, 0)` as an AbelianGroup.
  - `QField` — `(Q, +, *, 0, 1)` as a Field.

### Order

- `Order` — carrier + relation + reflexive axiom.
- `PartialOrder` — adds transitive + antisymmetric.
- `TotalOrder` — adds total.

### Functions

- `Function`, `Injection`, `Surjection`, `Bijection` — INDUCTIVE
  recipes with the corresponding axiom propositions.
- `compose_rule(g, f)` — pair two function-rules into a `compose(g, f)`
  cell. Content-addressed: any path that produces the same composition
  shares NodeID.
- `compose_bijections(g, f)` — constructive composition that produces
  the `A → C` bijection.

### Worked theorems (`proofs.ts`)

Four PROOF recipes that compile and pass `valid(k, proof)`:

1. **`prove_forall_intro_applied`** — apply `forall-intro` to a free
   atomic proposition. The simplest universal-generalization step.
2. **`prove_not_not_elim`** — classical double-negation elimination
   (`¬¬P ⊢ P`) as a rule + concrete application.
3. **`prove_zero_add`** — `∀n. 0 + n = n` by induction on `n`. The
   induction principle is registered as an inference rule; the base
   case is axiom-anchored to the recursive definition of `+`; the
   inductive step is anchored via the structural recursion that defines
   `+`.
4. **`prove_compose_bijective`** — composition of bijections is
   bijective, via a two-premise lemma and `apply`.

All four return `Proof` cells whose `valid()` check succeeds — the
proof construction is structurally well-formed, the rule applications
unify, and the conclusion matches the rule's conclusion-schema after
substitution.

## What's deferred

Future waves; each can land as its own ingest:

- **Topology** — open sets, continuity, compactness, connectedness.
  Needs Set-theoretic primitives and HoTT-style path-types for the deeper
  parts.
- **Analysis** — Cauchy sequences, completeness of R, limits, derivatives.
  Needs Q's metric completion as a quotient (R := Q^N / Cauchy ~).
- **Category theory** — categories, functors, natural transformations,
  limits / colimits, adjunctions. Each maps cleanly to INDUCTIVE + PROOF;
  the equivalence-discovery loop benefits enormously from
  content-addressing.
- **Full mathlib porting** — Lean's mathlib and Coq's mathcomp have
  200K+ theorems. The cross-language identity arm (#15-18 done, #31
  done) means substrate writes ingested from Lean automatically share
  NodeIDs with the same mathematics ingested from Coq. The body grows
  cell by cell.
- **Computational vs proof-irrelevant content** — currently every PROOF
  cell is treated uniformly. Distinguishing constructive proofs (whose
  witness can be extracted as a program) from proof-irrelevant ones
  needs a metadata recipe attached to PROOF cells.
- **Higher inductive types (HITs)** — paths-between-paths for the
  infinity-groupoid structure HoTT studies. Form's level hierarchy is a
  natural home; surface syntax for HITs is the missing piece.
- **Decidability metadata on equivalences** — `Decidability.HEAVY` and
  `Decidability.UNDECIDABLE` already exist in `../quotient.ts`; the
  lazy-canonicalization path is there but no mathlib equivalence
  currently uses it. Knuth-Bendix on group presentations is the natural
  first heavy equivalence to land.

## Running the suite

```
cd form/form-kernel-ts
npm install
npx tsx src/mathlib/mathlib.test.ts
```

Expected output ends with `[summary] 32/32 passed`.

The existing kernel bench is unchanged:

```
npx tsx src/bench.ts
# fib28 1× / fact12 13× / sum1000 1× / ackermann 1× / fsum1000 2×
```
