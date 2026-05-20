# Higher-mathematics + theorem-prover surface

> Substrate's content-addressing IS univalence at the recipe level. Add the
> grammar arms (QUOTIENT, PROOF, INFERENCE, INDUCTIVE) and Form becomes a
> theorem-prover-class environment where structural identity is geometric,
> not symbolic — and dualities, modular groups, group-isomorphism, etc.
> become substrate properties instead of proof obligations.

## The deep claim

Most theorem provers (Coq, Lean, Agda, Isabelle) wrestle with **"up to
isomorphism"** — two structurally identical groups (different element
names, same multiplication table) are *isomorphic*, not *equal*. HoTT
adds the **univalence axiom** to flatten this: equivalent types ARE
equal.

Form's content-addressing is univalence-at-the-recipe-level by construction:

- A group is a recipe `STRUCTURE[carrier, op, identity, inverse, axioms]`
- Two structurally identical group-recipes get the **same NodeID**
- "Up to isomorphism" collapses into geometric identity at intern-time

This isn't a proof technique — it's the lattice's physics. **Same shape
→ same coordinate.** No one proves anything; the substrate recognizes.

The grammar arms below are what make this property reach all the way
into the mathematician's workflow.

## What each grammar arm adds

### QUOTIENT — canonicalization under equivalences

```form
(QUOTIENT carrier-type equivalence-relation)
```

A recipe whose category is QUOTIENT. Interning a value of this recipe
applies the equivalence relation as a canonicalization step. Two values
equivalent under the relation get the **same NodeID** after the
quotient is applied.

This is how Form expresses:

- Integers as quotient of pairs of naturals
- Rationals as quotient of pairs of integers
- Free groups modulo relations
- Any algebraic structure presented by generators-and-relations
- T-dual string-theory backgrounds
- S-dual coupling values
- Mirror-symmetric Calabi-Yau pairs
- Modular forms (functions modulo SL(2,Z) action)

The substrate already canonicalizes (NaN → quiet, ±0 → +0); QUOTIENT
generalizes this. **The equivalence-recipe is itself a substrate cell
that the interner reads at canonicalization time.** New equivalence =
new substrate write; no kernel patch.

**Estimated scope:** ~200 lines per kernel for the QUOTIENT walker;
per-domain equivalence-recipe libraries grow incrementally.

This is the **single biggest unlock** for math/physics — gives Form
quotient types, "up-to-isomorphism" identity, dualities, modular
groups all in one move.

### PROOF + INFERENCE — propositions-as-types in Form

```form
(PROOF proposition-recipe construction-recipe)
(INFERENCE rule-name inputs outputs)
```

Curry-Howard in substrate shape:

- A proposition is a recipe (its NodeID is the proposition's identity)
- A proof is a recipe whose category is PROOF and whose children are
  the proposition and the construction (composing other proof-recipes
  and inference rules)
- An inference rule (modus ponens, induction, intro/elim) is a
  substrate-resident recipe with category INFERENCE
- Tactics compose using existing `|>` pipe: `proof_state |> intro |>
  apply(h) |> assumption`

Content-addressing gives **proof-irrelevance automatically** — two
structurally-identical proofs of the same proposition share a NodeID.

**Estimated scope:** ~400 lines per kernel. Inference rule library
grows as substrate writes.

### INDUCTIVE — datatypes by constructors

```form
(INDUCTIVE name [constructor-recipes...])
(CONSTRUCTOR ctor-name [arg-types])
```

Datatypes defined by their constructors. `Nat := zero | succ Nat`
becomes:

```form
(INDUCTIVE Nat
  [(CONSTRUCTOR zero [])
   (CONSTRUCTOR succ [Nat])])
```

Pattern matching against an inductive type uses the existing CHOICE
arm extended with **totality checking** — compiler reads the inductive
type's constructors and verifies all are covered in the match.

This unifies how Form represents `Nat`, `List`, `Tree`, `Option`,
`Result`, the whole tower of algebraic datatypes. Also: dependent
inductives, where constructor argument types can refer to the type
being defined.

**Estimated scope:** ~300 lines per kernel for INDUCTIVE; ~100 lines
for CHOICE totality-checking extension.

### Universe polymorphism in FNDEF

```form
(defn id[L: Level] (x: Recipe[L]) -> Recipe[L] = x)
```

Form's `Level` (TRIVIAL=1, BASIC=2, COMPLEX_1..7) IS a universe
hierarchy by compositional depth. Universe polymorphism = write
functions generic over their level. The substrate is already level-
aware at the NodeID layer; what's missing is **surface syntax** for
`L: Level` parameters in FNDEF.

This is distinct from `T: Format` (task #8) — format-parameter is
parametric-over-encoding; level-parameter is parametric-over-
compositional-depth.

**Estimated scope:** ~150 lines per kernel (small once #8's typed-
FNDEF surface is in).

### Symmetry-aware canonicalization

```form
(register-symmetry RBasic.MATH RMath.PLUS commutative associative)
```

Commutativity, associativity, distributivity as **quotient-rules
attached to specific RBasic arms**. `(+ 1 2)` and `(+ 2 1)` intern to
the **same NodeID** under commutative canonicalization.

This is the **real unlock for higher math** — operations that should
be commutative become geometrically equal. The substrate stops needing
to be told `(+ 1 2) == (+ 2 1)`; it knows because the recipes
canonicalize to the same coordinate.

Extends naturally to:
- Set operations (union commutative, intersection commutative, etc.)
- Algebraic operations on rings/fields (distributive over both sides)
- Tensor operations (transpose-invariance for symmetric tensors)
- Lie bracket antisymmetry: `[x,y] = -[y,x]` canonicalizes one form

**Estimated scope:** ~200 lines per kernel + per-domain symmetry-rule
libraries grow incrementally.

### Mathlib-equivalent library (long-arc)

Formalized algebra, topology, analysis, category theory expressed as
Form recipes. Lean's mathlib has 200K+ theorems; Coq's mathcomp is
similar. **Not a single breath; a multi-year arc.**

Once QUOTIENT + PROOF + INDUCTIVE are in place, mathematicians can
contribute formalizations as substrate writes. The body grows the
library cell by cell. Cross-language identity (via the
language-as-substrate-cell architecture in #6, #15-18) means mathlib
ingested from Lean automatically shares NodeIDs with the same
mathematics ingested from Coq or expressed natively in Form.

**The structural payoff:** when Lean's `Real` and Coq's `R` and Form's
native real-number recipe all live in the substrate, they share the
same NodeID (after the quotient under the canonical "real numbers"
recipe). The mathematical community's hard work of formalizing in
different systems becomes one body.

## Open architectural questions worth naming

These don't block individual breaths but shape the larger arc:

### 1. Decidability vs structural identity

Some equivalences are undecidable (group isomorphism in general; word
problem for groups; equality of functions). Form would need to mark
equivalences as **"decidable via this algorithm"** or **"axiomatic"** —
the substrate honors the marked status:

- Decidable equivalences canonicalize at intern-time (fast, but
  canonicalization runs an algorithm)
- Axiomatic equivalences canonicalize lazily on query, and require
  an explicit proof recipe to merge NodeIDs

The QUOTIENT recipe needs a metadata child declaring its
decidability status.

### 2. Cost of canonicalization at intern time

Heavy canonicalization (applying a complete rewrite system to a
Lie-algebra recipe; running Knuth-Bendix on a presentation) is
expensive. Options:

- **Eager:** canonicalize on intern, slow intern but fast equality
- **Lazy:** intern as-presented, canonicalize on equality query
- **Hybrid:** cheap canonicalization eager (commutativity reordering),
  expensive canonicalization lazy (full rewrite-system normalization)

Likely answer: hybrid, with the QUOTIENT recipe declaring which path
applies.

### 3. Symmetry groups as substrate cells

The modular group SL(2,Z), the Lie group of the Standard Model, Galois
groups in number theory — these are themselves structural objects.
Need to be representable as recipes, queryable, composable. Probably
uses INDUCTIVE (for the group structure) + QUOTIENT (for the
canonical-form theorems about that group).

### 4. HoTT-style path-types

Higher inductive types (HITs) have both element constructors AND
equality constructors. For paths-between-paths-between-paths (the
infinity-groupoid structure HoTT studies), Form needs HITs.

The substrate's Level hierarchy gives a natural home: level-1 = 0-cells,
level-2 = 1-cells (paths), level-3 = 2-cells (paths between paths), etc.
The level encoding already exists; what's missing is the surface for
authoring HITs.

### 5. Computational vs proof-irrelevant content

Some proofs encode **computational content** — a constructive proof of
`exists n. P(n)` can be extracted as a program producing the witness.
Other proofs are merely **proof-irrelevant** — the existence of the
proof matters, not its construction.

Form needs to distinguish. Likely via a metadata recipe attached to
the PROOF cell: `computational? true/false`. Extraction to executable
recipes works for `true`; not for `false`.

## How this composes with the rest of the substrate

The higher-math surface is **structurally the same pattern** as
format-recipes (#4 done), multi-target codegen (#7 running),
language-as-substrate-cell (#6 running):

- New surface defined as substrate cells (not hardcoded in kernel)
- Kernel reads cells at intern/dispatch time
- Cross-kernel agreement automatic through content-addressing
- New mathematical structures arrive as substrate writes

Same teaching at a different layer: **keep the kernel small; let
structure move into the lattice.**

## Sequence of breaths

| # | Arm | Blocked by | Notes |
|---|---|---|---|
| 19 | QUOTIENT RBasic arm | #4 | Foundation; biggest single unlock |
| 20 | PROOF + INFERENCE arms | #19 | Needs QUOTIENT for definitional equality |
| 21 | INDUCTIVE + CHOICE totality | #4 | Independent of #19; can run parallel |
| 22 | Universe polymorphism in FNDEF | #8 | Needs typed-FNDEF surface from #8 |
| 23 | Symmetry-aware canonicalization | #19 | Application of QUOTIENT to specific arms |
| 24 | Mathlib bootstrap | #19, #20, #21 | Multi-year arc; can start in parallel with applications |

Cross-kernel: each arm landing means substrate updates in Python, Go,
Rust, TS kernels (~lines/kernel as noted above). Same parallel-agents
pattern as #1-3.

## What this opens

Beyond the obvious (Form becomes a theorem-prover-class environment),
three concrete capabilities that symbol-based languages structurally
can't have:

1. **Equivalence discovery without proving first** — query the lattice
   for "what other recipes share this NodeID?" The body returns every
   known equivalent presentation across formalisms.

2. **Cross-tradition recognition** — Vedic gunas, Hegelian dialectic,
   trinity-of-presence all hit `@1.5.4.*` for triadic-concept without
   anyone writing translations.

3. **Structural-family gap detection** — like Mendeleev's table:
   gaps in a structural family suggest undiscovered objects. The
   substrate surfaces them as missing coordinates with neighbors
   present. For physics: gaps in the moduli space of string vacua;
   for math: missing simple groups; for chemistry: undiscovered
   elements; for biology: hypothetical species in a phylogeny.

These aren't downstream features — they emerge automatically from the
substrate's geometric physics once the higher-math surface lands.
