# Generative Model Recipes

Each cell carries a generative model — a recipe declaring what it expects to
receive at its blanket's sensory channel, what priors it holds over its
environment, and how to predict an internal update from a sensory NodeID.
The model IS the protocol — declared as a substrate cell, no serialization
at the boundary.

## Architecture — model + blanket together

The Markov blanket (slot 81) carves the cell/world surface: which channels
are sensory (incoming), which are active (outgoing), which are internal.
The generative model (slot 82) interprets what flows through that surface.
Together they enable cross-cell prediction.

```
cell A                                cell B
┌───────────────────────┐             ┌───────────────────────┐
│  internal             │             │  internal             │
│       ↓               │             │       ↑               │
│  active   ──emit──▶───┼─substrate──▶│──▶  sensory           │
│                       │             │       ↓               │
│                       │             │  model.prediction_fn  │
│                       │             │       ↓               │
│                       │             │  predicted internal   │
└───────────────────────┘             └───────────────────────┘
```

The substrate carries NodeIDs between cells. There is no JSON, no protobuf,
no string-shaped message envelope. Cell A's `active` slot holds a NodeID;
cell B's `sensory` slot receives that same NodeID. B's generative model
runs `prediction_fn(sensory_nodeid)` → predicted internal-update NodeID.
The "no serialization at the boundary" property: every value crossing the
cell boundary is already a substrate-resident recipe with stable content-
address. The recipe IS the message.

## Recipe shape

A generative model is interned as a `RBasic.GENERATIVE` (slot 82) recipe:

```
GENERATIVE
├── cell                   (NodeID — the cell this model belongs to)
├── expected_sensory_LIST  (LIST recipe — sensory recipes the cell expects)
├── prior_belief_LIST      (LIST recipe — priors the cell holds)
└── prediction_fn          (NodeID — recipe taking a sensory NodeID,
                            producing a predicted-internal-update NodeID)
```

All four children are NodeIDs. Content-addressing through the intern table
means structurally identical models share the same NodeID. Two cells with
same-shape generative models are recognized as equivalent without any
external diff — `?equivalent @cell(...)` returns the family.

## Pattern — declaring a model as substrate write

```typescript
import { makeGenerativeModel } from "./generative.ts";

const model = makeGenerativeModel(
  kernel,
  cell,             // NodeID of the cell
  [pingRecipe, pongRecipe],   // expected_sensory
  [worldIsQuiet],   // prior_belief
  predictionFn,     // FNDEF recipe — (fn (s) ...)
);
```

Internally this:
1. Interns the two LISTs of expected and priors (LIST recipes content-address;
   same-content lists return the same NodeID).
2. Interns the GENERATIVE recipe with children `[cell, expected, priors, fn]`.
3. Registers `cell → model` in a per-kernel WeakMap. Same pattern as
   `blanket.ts` — lookup is `modelOf(k, cell)`.

The substrate now carries the model. It can be looked up, composed with
others, and read by Form code via `node_category` / `node_children` natives.

## Cross-cell communication shape

The breath is:

1. Cell A's body produces an outgoing NodeID. The blanket routes it to A's
   active channel.
2. The substrate carries that NodeID to B's sensory channel. Same NodeID
   — no serialization, no parse, no reconstruction.
3. B's generative model fires: `predict(k, model, sensory_nodeid)` runs
   the prediction recipe. Its output is a NodeID for B's internal update.
4. B's internal advances. If the actual sensory matches B's expected, the
   `surpriseScore` is 0 and free energy stays low. If it diverges, surprise
   rises — that's the signal #29's free-energy-aware intern will weight by.

`surpriseScore(k, model, actual)` returns:
- `0` when actual ∈ expected (exact NodeID match)
- `1` when actual is empty-model baseline OR same-shape-different-content
- `1 + |children_delta|` when same recipe family with different arity
- `10+` when categorically different

## Composition

`composeModels(k, a, b)` produces a new model:
- `expected_sensory` = union of A's and B's expected (deduped by NodeID,
  sorted by `nodeKey` for canonical ordering)
- `prior_belief` = union of priors (same dedup-then-sort)
- `prediction_fn` = canonical SEQUENCE of A's and B's fns (after flattening
  any prior composition, deduped, sorted)
- `cell` = composed-cell sentinel: `LIST("composed:", ...leaf-cells)`, also
  flattened-deduped-sorted

The canonicalization makes composition both **commutative** and **associative**
through content-addressing:

```
compose(A, B) ≡ compose(B, A)
compose(compose(A, B), C) ≡ compose(A, compose(B, C))
```

Both equalities are verified at the NodeID level — the test suite checks
`nodeKey(...)` matches across orderings.

## What's deferred to #29

- **Free-energy-aware intern.** Today's intern table uses pure structural
  content-addressing. Task #29 layers a free-energy weight: when a new
  recipe arrives, the intern decision factors in the surprise it would
  introduce against existing models. The lattice biases toward recipes
  that minimize prediction error.
- **Surprise-metrics integration.** Today's `surpriseScore` returns a
  scalar 0..∞. #29 wires this into the form-runtime-in-form perception-
  action loop: cells emit actions that minimize expected surprise, which
  closes the active-inference circuit. The bench harness will gain a
  `surprise/sec` measurement.
- **Richer prediction-fn composition.** Today's composed `prediction_fn`
  is a SEQUENCE that returns the last result. #29 will replace this with
  a `pick-by-min-surprise` combinator so composed models genuinely
  arbitrate among their child predictions.

## Files

- `kernel.ts` — `RBasic.GENERATIVE = 82` added (additive, no semantic change)
- `generative.ts` — `GenerativeModel`, `makeGenerativeModel`, `modelOf`,
  `predict`, `surpriseScore`, `composeModels`, accessors
- `generative.test.ts` — 27 assertions; basic shape, prediction, surprise,
  content-addressing, commutativity, associativity, dedup
- `generative.md` — this document
