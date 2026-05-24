# INDUCTIVE — algebraic datatypes as substrate cells

INDUCTIVE is an additive RBasic arm (type code `71`). It lets the substrate
hold algebraic datatypes — `Nat`, `List[T]`, `Option[T]`, `Result[T, E]`, and
arbitrary user-defined ADTs — as content-addressed recipes. The companion
arm `CONSTRUCTOR` (`72`) carries both constructor *type definitions* (inside
an INDUCTIVE) and constructor *value applications* (the runtime ctor values
walked by `kernel.ts`).

The CHOICE arm (`35`) is extended with totality checking: when a match
scrutinee is a constructor of a known INDUCTIVE type, the walker verifies
every constructor of that type is covered by a match arm, and raises with
the missing names if not.

## Recipe shapes

```
INDUCTIVE
  children:
    type-name        : Triv.STRING        ; "Nat", "List", ...
    type-params      : RBasic.LIST        ; parametric types (T, E, ...)
    ctor0..ctorN     : RBasic.CONSTRUCTOR ; constructors as type definitions

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

CHOICE  (pattern match)
  children:
    scrutinee        : NodeID  ; value-recipe that walks to a ctor Value
    arm0-name        : Triv.STRING
    arm0-body        : NodeID  ; FNDEF (with ctor-arg params) or bare expr
    arm1-name        : Triv.STRING
    arm1-body        : NodeID
    ...
```

## Composition with QUOTIENT

The integers `Z` arise as `(Nat × Nat) / equiv`, where `equiv (a₁, b₁) (a₂, b₂)`
holds iff `a₁ + b₂ = a₂ + b₁`. The substrate expresses this directly:

1. INDUCTIVE `Nat` (this arm).
2. A product type — `Pair Nat Nat` — built either as another inductive
   (`Pair := mkPair Nat Nat`) or as a primitive RBasic.LIST.
3. RBasic.QUOTIENT (agent #19) wrapping the pair type with the equivalence
   recipe.

Because both arms produce content-addressed recipes, the resulting `Z` is a
single substrate cell that any kernel — TS, Go, Rust, Python — can address
by NodeID without re-deriving its shape. The same pattern composes
rationals (`Q = Z × Z* / equiv`), free groups, etc.

QUOTIENT is reserved for arm `70`; INDUCTIVE is `71`; CONSTRUCTOR is `72`.
The numeric assignment is the contract; the rest is composition.

## Adding a new inductive type

```ts
import { Kernel } from "./kernel.ts";
import { make_inductive, make_constructor } from "./inductive.ts";

const k = new Kernel();

// Tree := leaf | node Tree int Tree
const TreeName = k.internString("Tree");
const intT = /* however your kernel models int */ k.internString("int");
const Tree = make_inductive(k, "Tree", [], [
  { ctor_name: "leaf", ctor_index: 0, arg_types: [] },
  { ctor_name: "node", ctor_index: 1, arg_types: [TreeName, intT, TreeName] },
]);

// Build a value: node(leaf, 7, leaf)
const leaf = make_constructor(k, Tree, "leaf", []);
const node = make_constructor(k, Tree, "node", [leaf, k.internTrivialInt(7), leaf]);
```

The inductive recipe is interned — defining the same `Tree` shape twice
returns the same NodeID. The constructors of an inductive are reachable
via `constructorNames(k, Tree)`; the index of a constructor by name via
`constructorIndex(k, Tree, "node")`.

## Totality-checking semantics

When the CHOICE walker dispatches on a scrutinee:

1. The scrutinee is evaluated; the walker expects a `ctor` Value.
2. The `inductive` field of that Value names the type's NodeID.
3. If the kernel can resolve that NodeID to an INDUCTIVE recipe, every
   constructor declared on the type must appear as an arm. Missing names
   raise `choice: non-total match — missing constructor(s): …`.
4. Arms dispatch by name. Arm bodies are either:
   - A bare expression (no constructor-arg bindings), or
   - An FNDEF-shaped recipe whose params receive the ctor's args.
5. If no arm matches (shouldn't happen after the totality check), the
   walker raises explicitly.

The check happens at walk time in this proof-of-shape. Compile-time
totality — emitting a diagnostic before walking — is task #7's domain
(multi-target codegen), where the inductive's constructor set is statically
known at the call site.

## What's deferred

- **Dependent inductives** where constructor arg types depend on *values*,
  not just type parameters — folds into task #22 (parametric / dependent
  types).
- **Higher inductive types** (constructors for equality paths) — an open
  question; the additive numeric encoding leaves room (`73` onward).
- **GADTs** — deferred; the current encoding doesn't express the per-ctor
  refinement of the return type.
- **Coinductive types** — a separate arm (corecursive); deferred.
- **Cross-kernel ports** — this is TS-only proof-of-shape. Go / Rust /
  Python implementations follow once the numeric arm code is fixed
  (which is what this commit pins down: `71` and `72`).
