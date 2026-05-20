# INDUCTIVE — algebraic datatypes as substrate cells (Go port)

INDUCTIVE is an additive RBasic arm (type code `71`). It lets the substrate
hold algebraic datatypes — `Nat`, `List[T]`, `Option[T]`, `Result[T, E]`, and
arbitrary user-defined ADTs — as content-addressed recipes. The companion
arm `CONSTRUCTOR` (`72`) carries both constructor *type definitions* (inside
an INDUCTIVE) and constructor *value applications* (the runtime ctor values
walked by `WalkConstructor`).

The CHOICE_MATCH arm (`35`) carries pattern-match arms with totality
checking: when a match scrutinee is a constructor of a known INDUCTIVE
type, the walker verifies every constructor of that type is covered by a
match arm, and panics with the missing names if not.

This Go port mirrors:
- `experiments/form-kernel-ts/src/inductive.ts` (TS reference)
- `api/app/services/substrate/inductive.py` (Python port)

## Recipe shapes

```
INDUCTIVE
  children:
    type-name        : Triv.STRING        ; "Nat", "List", ...
    type-params      : RBasicList         ; parametric types (T, E, ...)
    ctor0..ctorN     : RBasicConstructor  ; constructors as type definitions

CONSTRUCTOR  (type definition, inside an INDUCTIVE)
  children:
    inductive-ref    : NodeID  ; self-name trivial during definition
    ctor-name        : Triv.STRING
    ctor-index       : Triv.INT
    arg-type0..N     : NodeID  ; type-recipes (self-ref allowed)

CONSTRUCTOR  (value application, in code)
  children:
    inductive-ref    : NodeID  ; the inductive's NodeID (resolved)
    ctor-name        : Triv.STRING
    ctor-index       : Triv.INT
    arg-recipe0..N   : NodeID  ; value-recipes

CHOICE_MATCH  (pattern match)
  children:
    scrutinee        : NodeID  ; value-recipe that walks to a ctor Value
    arm0-name        : Triv.STRING
    arm0-body        : NodeID
    arm1-name        : Triv.STRING
    arm1-body        : NodeID
    ...
```

## Runtime representation

The Go port uses its own `IndValue` interface for runtime values rather
than extending `main.go`'s `Value` enum:

- `*CtorValue` — constructor application result. Carries `Inductive`,
  `CtorName`, `CtorIndex`, and `Args []IndValue`.
- `NodeValue` — wraps a raw `NodeID` (trivial literal or other recipe).

This keeps the inductive arm purely additive — `main.go` is unmodified.
Convert with `AsCtor(v) (*CtorValue, bool)`, `AsNode(v) (NodeID, bool)`,
or `AsInt(v) (int64, bool)` for the common int trivial.

## Quick usage

```go
import (
    // package main; the kernel is a single Go package
)

k := NewKernel()
inds := InstallBuiltinInductivesTyped(k)

// Build succ(succ(zero)) — Nat = 2
two := NatOf(k, inds, 2)
v := WalkValue(k, two)
n := NatToInt(v)                        // 2

// Pattern match on Option
someFive := MakeConstructor(k, inds.Option, "some",
    []NodeID{k.internTrivialInt(5)})
v = WalkValue(k, someFive)
result := MatchValue(k, v, map[string]ArmHandler{
    "none": func(_ []IndValue) interface{} { return int64(-1) },
    "some": func(args []IndValue) interface{} {
        n, _ := AsInt(args[0])
        return n
    },
})
// result == int64(5)
```

## Adding a new inductive type

```go
// Tree := leaf | node Tree int Tree
intT := k.internString("int")        // parameter placeholder
treeName := k.internString("Tree")    // self-ref sentinel
tree := MakeInductive(k, "Tree", nil, []*ConstructorDef{
    {CtorName: "leaf", CtorIndex: 0},
    {CtorName: "node", CtorIndex: 1, ArgTypes: []NodeID{treeName, intT, treeName}},
})

leaf := MakeConstructor(k, tree, "leaf", nil)
node := MakeConstructor(k, tree, "node",
    []NodeID{leaf, k.internTrivialInt(7), leaf})
```

The inductive recipe is interned — defining the same `Tree` shape twice
returns the same NodeID (content-addressing). Constructors of an inductive
are reachable via `ConstructorNames(k, tree)`; index lookup via
`ConstructorIndex(k, tree, "node")`.

## Composition with QUOTIENT

The integers `Z` arise as `(Nat × Nat) / equiv`, where `equiv (a₁, b₁) (a₂, b₂)`
holds iff `a₁ + b₂ = a₂ + b₁`. The substrate expresses this through two
arms in concert:

1. INDUCTIVE `Nat` (this arm — built-in).
2. INDUCTIVE `Pair := mkPair Nat Nat` — a product type carrying two Nats.
3. RBasic.QUOTIENT (slot 70 — see `quotient.go`) wrapping the pair type
   with the `integer-from-nat-pair` equivalence recipe.

Because both arms produce content-addressed recipes, the resulting `Z` is
a single substrate cell that any kernel — TS, Go, Rust, Python — can
address by NodeID without re-deriving its shape. The same pattern
composes rationals (`Q = Z × Z* / equiv`), free groups, etc.

In Go:

```go
// Carrier
inds := InstallBuiltinInductivesTyped(k)
pair := MakeInductive(k, "Pair", nil, []*ConstructorDef{
    {CtorName: "mkPair", CtorIndex: 0,
     ArgTypes: []NodeID{inds.Nat, inds.Nat}},
})

// Once quotient.go is on this branch, the following composes Z:
//   lib := BuildQuotientLibrary(k)
//   Z   := MakeQuotientRecipe(k, pair, lib.EquivIntegerFromNatPair.NodeID)
//   v31 := InternQuotientValue(k, Z, []NodeID{NatOf(k,inds,3), NatOf(k,inds,1)})
//   v53 := InternQuotientValue(k, Z, []NodeID{NatOf(k,inds,5), NatOf(k,inds,3)})
//   // v31 == v53  (both project to +2 under canonicalization)
```

The `TestPairCarrierForQuotient` test in `inductive_test.go` exercises
the carrier side without depending on `quotient.go`: it verifies that
uncanonicalized pairs are distinct cells, and that identical pair
applications intern to the same NodeID — the contract QUOTIENT relies on.

## Slot assignments

Cross-kernel contract (TS / Python / Go / Rust):

| Arm                  | Slot |
|----------------------|------|
| `RBasicQuotient`     | 70   |
| `RBasicInductive`    | 71   |
| `RBasicConstructor`  | 72   |
| `RBasicChoiceMatch`  | 35   |
| `TrivConstructorTag` | 15   |

Constructor name vocabulary (builtin):
`zero`, `succ`, `nil`, `cons`, `none`, `some`, `ok`, `err`, `true`, `false`.

Inductive name vocabulary (builtin):
`Nat`, `Bool`, `Option`, `Result`, `List`.

## Totality-checking semantics

When `WalkChoice` dispatches on a scrutinee:

1. The scrutinee is walked; the walker expects a `*CtorValue`.
2. The `Inductive` field of that ctor names the type's NodeID.
3. If the kernel resolves that NodeID to an INDUCTIVE recipe, every
   constructor declared on the type must appear as an arm. Missing names
   panic with `choice: non-total — missing constructor(s): …`.
4. Arms dispatch by name. Arm bodies are walked via `WalkValue` —
   trivials become `NodeValue`, ctors become `*CtorValue`, other recipes
   pass through as `NodeValue`.
5. If no arm matches (shouldn't happen after the totality check), the
   walker panics.

The check happens at walk time in this proof-of-shape. Compile-time
totality — emitting a diagnostic before walking — is deferred to
multi-target codegen, where the inductive's constructor set is statically
known at the call site.

## What's deferred

- **Dependent inductives** — constructor arg types depending on values,
  not just type parameters.
- **Higher inductive types** — constructors for equality paths.
- **GADTs** — per-constructor refinement of the return type.
- **Coinductive types** — a separate arm (corecursive).
- **Form-language surface syntax** — currently inductives are built
  through the Go API; surface-syntax `defn-inductive` lands when the
  reader supports the shape.
