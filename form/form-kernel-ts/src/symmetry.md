# Symmetry-aware canonicalization — structural surprise reduction at the algebra level

## The teaching

A content-addressed substrate gives you one form of equality for free: **same shape ⇒ same NodeID**. Two recipes built with identical category and identical children intern to the same identity, no matter who built them or when.

Algebra extends "same shape" with a second layer: **same shape under symmetry ⇒ same NodeID**. `(+ 1 2)` and `(+ 2 1)` are not the same shape — the children are ordered — but every algebraist knows they denote the same value. The teaching of `symmetry.ts` is that this knowledge can live IN the substrate, not OUTSIDE in a proof obligation:

- Declare that `MATH.PLUS` is commutative. Now `(+ 1 2)` and `(+ 2 1)` intern to the same NodeID.
- Declare that `LOGIC.AND` is idempotent. Now `(and p p)` and `p` are the same NodeID.
- Declare that `0` is the right-identity of `MATH.PLUS`. Now `(+ x 0)` IS `x`.

The walker never sees the redundant form. The conformance kernels (Go, Rust, TypeScript) all agree the two expressions are one entity. No tactic, no rewrite step, no normal-form lemma — the algebra is in the intern table.

This is the **REAL unlock for higher math**. Building a mathlib on top of this substrate means that "equal up to ring-axiom" isn't a theorem about your representation; it IS your representation. Future work (group actions, Lie algebra commutators, tensor index conventions) attaches to the same hook.

## Pattern: declaring a symmetry rule as a substrate write

A `SymmetryRule` is a plain record:

```ts
interface SymmetryRule {
  arm: number;       // RBasic.MATH / RBasic.LOGIC / RBasic.COMPARE
  op_inst: number;   // RMath.PLUS / RLogic.AND / RCmp.EQ
  kind: SymmetryKindT;
  op_inner_arm?: number;
  op_inner_inst?: number;
  identity?: NodeID;
}
```

It is the same shape regardless of which algebraic law it expresses. Commutativity for `MATH.PLUS` and commutativity for `LOGIC.AND` are not two different records — they are two instances of the same record. Cross-domain equivalence falls out: any sibling kernel that ingests the same `SymmetryRule` recipe canonicalizes the same way. The rule itself is substrate-resident in the sense that matters — it is a flat, content-addressable data structure that any process can read and apply.

(A future move stores rules as cells under an existing RBasic arm — e.g., a dedicated INDUCTIVE-typed value inside `RBasic.LIST` — so that the rule itself has a NodeID. That orthogonal step lets one kernel declare a symmetry and another kernel discover it via content-addressing. The current implementation keeps rules in a sidecar `WeakMap<Kernel, SymmetryRegistry>` because the substrate-write surface for non-trivial rule recipes is still in flux. The shape is ready; the persistence is deferred.)

## How the canonicalization composes

Inside `canonicalizeUnderSymmetries(k, arm, op_inst, children)`:

1. **Associative flatten** — `(+ (+ 1 2) 3)` becomes `(+ 1 2 3)`. Nesting of the same op disappears. Recursive at construction time, so deep nests collapse in one pass.
2. **Distributive expansion** — eager. `(* a (+ b c))` becomes `(+ (* a b) (* a c))`. Replaces the outer node entirely. The result is re-canonicalized, so distribution composes with commutativity and associativity of the inner op for free.
3. **Identity elimination** — `(+ x 0)` drops the `0` child; `(* x 1)` drops the `1`. After dropping, a single-child n-ary op collapses to that child. An empty op collapses to the identity itself.
4. **Commutative sort** — children sorted by canonical NodeID key. This is the cheapest pass and the highest-leverage one: it covers `(+ 1 2) ≡ (+ 2 1)` and every permutation of an n-ary `(+ a b c d e)`.
5. **Idempotent dedupe** — after sorting, adjacent identical children collapse. `(and p p p q)` becomes `(and p q)`.

The order matters. Associative before commutative because flattening changes children. Identity before commutative because identity-drop changes children. Idempotent dedupe after sorting because dedupe assumes order.

## Eager vs lazy — what this implementation chose

- **Eager**: commute, associate, identity-elim, idempotent-dedupe. All cheap (O(n log n) for sort, O(n) for the rest). Applied at intern time. The redundant form simply never enters the table.
- **Eager**: distributive expansion. Strictly speaking this *enlarges* the term, so "eager" is a stronger choice than associative. The justification is that the canonical form for ring expressions is sum-of-products (fully expanded) — that's what mathematicians write when they want canonical equality. The cost is bounded by the actual subterm sharing of the inner sums; the substrate's content-addressing means each `(* a b)` is interned once regardless of how many distribution sites produced it.
- **Lazy / not registered**: OR-over-AND distribution. The dual of AND-over-OR. Registering both creates a canonicalization loop (sum-of-products vs product-of-sums). We register AND-over-OR (DNF) by default and treat the dual as a query-time option, not an intern-time rule. The teaching is that any commutative semiring has two canonical forms and the implementation must pick one.
- **Lazy / informational**: `ANTISYMMETRIC` for COMPARE.LT/GT and LE/GE. `(< a b)` ≡ `(> b a)` would require flipping both children AND op_inst, which is a structural transform we don't apply at intern time (it would couple two op-instances during canonicalization, making the registry order-sensitive). Recorded so query-time tools can reason about it.

## Cost model

- One sort per intern call on an op with `COMMUTATIVE`. Sort key is the precomputed `nodeKey` string.
- Associative flatten is one pass over the children list. Worst case O(n) per construction; sharing kicks in via the intern table.
- Identity-elim is one pass.
- Distributive can blow up term size — but content-addressing means each unique subterm is stored once. The blowup is in the recipe-tree structure, not in the byte cost.
- `recanonicalize(node)` walks an existing tree bottom-up and re-emits each composite under the registry. Useful when rules are installed after a tree was built (rare; the test exercises this path).

## What's deferred

- **Substrate-resident rule cells.** Rules are currently a sidecar JS object. Persisting each rule as a NodeID lets one kernel publish a symmetry and another discover it by content-addressing alone. Requires a small extension to the RBasic vocabulary — likely a SYMMETRY recipe under `RBasic.LIST` or a new `RBasic.INDUCTIVE` slot — coordinated across the Go/Rust kernels.
- **Knuth-Bendix completion.** When the user registers an arbitrary equational theory (not just the built-in algebraic laws), we should compute a confluent term-rewriting system from the axioms so that ANY two equal terms canonicalize to the same NodeID. Out of scope for this slice; the built-in library is the curated subset that works without completion.
- **Group / Lie-algebra symmetry rules.** The natural next step. A group action declares `(g · x) ≡ x` for `g` in the stabilizer. A Lie commutator declares `[x, y] ≡ -[y, x]` (antisymmetric in the Lie sense). The current `SymmetryKind` enum covers the abelian-monoid case; extending it to encode group-element-parameterized rules and antisymmetry-with-sign is the move that unlocks tensor algebra.
- **Constant folding.** `(+ 1 2)` could collapse to `3` at intern time. We deliberately don't do this — the substrate represents structure; the walker represents evaluation. Folding belongs in a separate `evaluate(node)` pass, not in canonicalization. (Otherwise `(+ x 1 2)` and `(+ x 3)` would have to agree, which requires partial evaluation of the symbolic part.)

## Test coverage

`symmetry.test.ts` exercises:

- Commutativity (`+ 1 2 ≡ + 2 1`).
- Associativity (`(+ (+ 1 2) 3) ≡ (+ 1 (+ 2 3))`).
- Distributivity (`(* 2 (+ 1 3)) ≡ (+ (* 2 1) (* 2 3))`).
- Identity elimination (`(+ x 0) ≡ x`, `(+ 0 x) ≡ x`, `(* 1 x) ≡ x`).
- AND commutativity + idempotency (`(and p q) ≡ (and q p)`, `(and p p) ≡ p`, `(and p true) ≡ p`).
- The regular `intern` path is untouched (no symmetry collapse).
- `recanonicalize` re-emits a previously-interned tree under newly-installed rules.
- Per-kernel registry stability.

## The relationship to QUOTIENT and PROOF

A symmetry rule is one half of a QUOTIENT: it says "these two structural representations name the same equivalence class." The PROOF surface (#20) is the other half: it lets a kernel verify that a claimed equivalence holds for an arbitrary pair, not just an axiom. Symmetry rules are the axioms; PROOF discharges the theorems. Together, they are what makes a content-addressed substrate viable as the storage layer for higher math.

Generative composition (#26) consumes the symmetry layer as a pre-condition: when a generator emits `(* a (+ b c))`, the symmetry-aware intern collapses it to its canonical sum-of-products form, so downstream consumers see exactly one shape per equivalence class.
