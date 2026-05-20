# PROOF + INFERENCE — propositions-as-types in substrate shape

> Task #20. Sister to QUOTIENT (#19) and INDUCTIVE (#21). Together these
> three RBasic arms carry the higher-math surface that mathlib bootstrap
> (#24) will stand on.

## Architecture

The Curry–Howard correspondence says **propositions are types** and
**proofs are programs of those types**. We render that directly in
substrate shape:

| Logical | Substrate |
|---------|-----------|
| Proposition | A recipe — any NodeID. Its identity *is* the claim. |
| Proof of P | A `PROOF`-category recipe with children `[proposition, construction]` where `proposition = P`. |
| Inference rule | An `INFERENCE`-category recipe with children `[name, premises-list, conclusion]`. Premises and conclusion are proposition-schemas with VAR holes. |
| Rule application | An `INFERENCE`-category recipe with children `[rule, ...premise-proofs]`. |
| Axiom / assumption | A `PROOF` cell whose `construction` is the string trivial `"axiom"`. |

Two reserved RBasic slots:

```ts
RBasic.PROOF     = 73   // shape marker for proof cells
RBasic.INFERENCE = 74   // shape marker for inference-rule cells and applications
```

The walker does **not** dispatch these — they are recipe-shape markers
consumed by helpers in `proof.ts`. The kernel's existing nine arms are
untouched.

### Why content-addressing gives proof-irrelevance for free

Two structurally identical proofs of the same proposition produce the
same `recipeKey` and therefore share one `NodeID`. We never assign
proof-identity; the substrate does. Proof-irrelevance is a property of
the storage layer, not an algorithm.

### Why inference rules live in the substrate

A rule like modus-ponens is just another cell:

```
INFERENCE category
  ├─ "modus-ponens" (string trivial)
  ├─ LIST [ ==>(?P, ?Q), ?P ]   ← premises (schemas with VAR holes)
  └─ ?Q                          ← conclusion
```

`builtinRules(k)` interns the standard set once per Kernel; subsequent
calls return the same NodeIDs. The substrate knows its own logic.

## Proof construction patterns

### Modus ponens (the canonical first proof)

```ts
const k = new Kernel();
const rules = builtinRules(k);
const P = k.internString("P");
const Q = k.internString("Q");
const PimpliesQ = Prop.implies(k, P, Q);

const proofPimpliesQ = axiom(k, PimpliesQ);
const proofP         = axiom(k, P);
const proofQ         = apply(k, rules.modusPonens, [proofPimpliesQ, proofP]);

// proofQ.proposition === Q
// valid(k, proofQ) === true
```

### Proof by constructor introduction (cross-composition with INDUCTIVE)

A proposition like `succ(zero) : Nat` is a `:`-typing claim. We give it
two rules:

- **`nat-zero-intro`** : an axiom `⊢ zero : Nat`
- **`nat-succ-intro`** : a rule `n : Nat ⊢ succ(n) : Nat` with hole `?n`

Then proving `succ(zero) : Nat` is one rule application:

```ts
const succRule = makeInferenceRule(
  k, "nat-succ-intro",
  [hasType(holeN)],          // premises
  hasType(succ(holeN)),      // conclusion
);
const zeroIsNat    = axiom(k, hasType(zero));
const succZeroIsNat = apply(k, succRule, [zeroIsNat])!;
```

When `inductive.ts` lands (#21), its `Constructor` cells become the
proposition recipes here — same shape, different author. No coupling.

### Hole-binding (first-order unification)

Holes are string trivials whose name begins with `"?"`. The leading `?`
is the only convention this module uses. Holes that recur in a single
rule must bind consistently:

```
rule: forall-intro,  premise: ?P,  conclusion: ∀x. ?P
```

When `?P` binds against `succ(n) : Nat` in the premise, the conclusion
substitutes to `∀x. succ(n) : Nat`. No higher-order goals — schema
match is structural, NodeID-pointwise.

## What `valid()` checks

`valid(k, proof)` recursively descends a proof tree, verifying at every
node:

1. The cell is a `PROOF`-category recipe with two children.
2. Either:
   - **Axiom**: construction is the string trivial `"axiom"` (or
     `"axiom:label"`), OR
   - **Inference application**: construction is an `INFERENCE`-category
     cell with `[rule, ...sub-proofs]` where:
     - The rule is a real `INFERENCE`-category cell.
     - The sub-proofs validate recursively.
     - Each sub-proof's proposition unifies against the corresponding
       rule premise (with bindings shared across all premises).
     - The substituted conclusion equals the proof's claimed
       proposition (by `nodeKey`).

`apply()` is the introduction side; `valid()` is the elimination side.
The two are not symmetric in name but symmetric in algebra:
`apply(rule, [...])` always produces a `valid` proof; `valid` accepts
any proof whose construction could have come from `apply` or `axiom`.

## Bundled inference rules

| Rule | Schema |
|------|--------|
| `modusPonens` | `P → Q, P ⊢ Q` |
| `andIntro` | `P, Q ⊢ P ∧ Q` |
| `andElim1` | `P ∧ Q ⊢ P` |
| `andElim2` | `P ∧ Q ⊢ Q` |
| `orIntro1` | `P ⊢ P ∨ Q` |
| `orIntro2` | `Q ⊢ P ∨ Q` |
| `impliesIntro` | `Q ⊢ P → Q` (assumption-discharge deferred) |
| `impliesElim` | alias of modus ponens |
| `notIntro` | `⊥ ⊢ ¬P` (assumption-discharge deferred) |
| `notElim` | `¬P, P ⊢ ⊥` |
| `forallIntro` | `P[x] ⊢ ∀x. P` |
| `forallElim` | `∀x. P ⊢ P[x]` |
| `existsIntro` | `P[x] ⊢ ∃x. P` |
| `existsElim` | `∃x. P, P ⊢ Q` (assumption-discharge deferred) |

## Cross-composition

### With INDUCTIVE (#21)

Inductive types declare constructors. Each constructor declaration
becomes an inference rule of the form:

```
C : T₁ → T₂ → ... → T          ⇒          ⊢ T₁, ..., ⊢ Tₙ  ⊢  C(t₁, ..., tₙ) : T
```

`builtinRules` produces only propositional + first-order rules. When
inductive.ts arrives, an adapter `inductiveAsRule(constructor)` will
read each declared constructor and intern the corresponding inference
rule. The PROOF cells then carry both surfaces — proof-by-induction is
just well-founded application of these rules.

### With QUOTIENT (#19)

QUOTIENT carries definitional equality at the substrate layer:
`equiv(a, b)` collapses two NodeIDs into one quotient class. For PROOF,
this means propositions that are *definitionally* equal share NodeIDs
automatically, and `valid()` accepts proofs across quotient boundaries
without any special-case logic — the unification check on `nodeKey` is
already canonical because the quotient projection happened upstream.

When equalities are themselves propositions (e.g. `x = y` as a recipe),
PROOF and QUOTIENT compose at two levels:

- *Substrate level*: quotient classes collapse NodeIDs.
- *Logical level*: equality propositions can be reasoned about
  through `forallElim`, `existsIntro`, etc.

## What's deferred

- **Assumption discharge** — implication-introduction and
  not-introduction are surfaced as single-premise rules. Full natural
  deduction requires tracking open assumptions and the rule that
  discharges them. Deferred to mathlib bootstrap (#24).
- **Full dependent-type proofs** — `Π`-types, `Σ`-types, and judgmental
  equality require a typing context that travels with each proof
  obligation. The current PROOF arm encodes simply-typed
  Curry–Howard; the dependent slice arrives with #24.
- **Higher-order unification** — the unifier is first-order. Holes
  bind to concrete sub-NodeIDs; we don't reconstruct functions from
  partial applications. Sufficient for the standard rule set and for
  inductive-type proofs; insufficient for tactic-style theorem
  proving.
- **Equality reasoning beyond `nodeKey`** — equality of propositions
  is by NodeID identity. When QUOTIENT cells declare two terms equal,
  the substrate-level quotient projection is what makes them share
  NodeIDs. Definitional-equality-as-PROOF (with reflexivity, symmetry,
  transitivity as inference rules over inductive `Eq` cells) is the
  next layer up.

## Files

- `src/kernel.ts` — adds `RBasic.PROOF = 73` and `RBasic.INFERENCE = 74`
- `src/proof.ts` — Proposition / Proof / InferenceRule, `apply`, `valid`,
  `proofOf`, `axiom`, `builtinRules`
- `src/proof.test.ts` — runnable via `npx tsx src/proof.test.ts`

## Running

```bash
cd experiments/form-kernel-ts
npm install
npx tsc --noEmit          # typecheck — existing + new
npx tsx src/proof.test.ts # 23 tests, all pass
```
