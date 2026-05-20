# Markov blanket recipes — `RBasic.BLANKET` (slot 80)

> Status: additive landing. The kernel walker does not interpret BLANKET
> recipes today — they exist as substrate-resident declarations, queried by
> code that wants to predict a cell from its boundary. Generative-model
> evaluation and free-energy-aware intern come later (#26, #29).

A **Markov blanket** declares a cell's boundary. Borrowed from Friston's
free-energy framework: a system that maintains itself against entropy must
distinguish *inside* from *outside*, and the boundary between them is a
statistical screen — internal states only encounter external states through
the boundary, never directly.

In the Coherence-substrate, every cell can carry a blanket recipe naming
four sets of NodeIDs:

| Channel    | Meaning                                                        |
|------------|----------------------------------------------------------------|
| `exposed`  | NodeIDs the cell makes visible to its environment              |
| `internal` | NodeIDs the cell keeps private                                 |
| `sensory`  | NodeIDs the cell receives at the boundary (inputs)             |
| `active`   | NodeIDs the cell can emit across the boundary (outputs)        |

Cross-cell communication crosses the blanket. A cell predicts another's
behavior by reading its blanket recipe — what's exposed, what kind of
sensory it expects, what kind of active it produces — *without* needing
access to the other cell's internal state.

## Architecture

A BLANKET recipe has five children in fixed order:

```
intern( category=(BASIC, BLANKET, 0),
        children=[ cell,
                   internList(exposed),
                   internList(internal),
                   internList(sensory),
                   internList(active) ] )
```

Each per-channel `internList` is an `RBasic.LIST` recipe whose children are
the NodeIDs on that channel. Because the kernel's `intern` is
content-addressed, **two cells whose blankets have the same shape share the
same blanket NodeID** — structural equivalence for free.

The cell → blanket association is held in a per-kernel registry (a
`WeakMap<Kernel, Map<nodeKey, NodeID>>`). Keeping the association outside
the recipe tree lets the same blanket-recipe be referenced by multiple cells
that share an identical boundary, and lets cells declare their boundary
without forcing the boundary to live inside the cell's own recipe.

The kernel walker does **not** interpret BLANKET. Encountering one in walk
position is a hard error today; that slot is reserved for the generative-
model arm landing in #26. BLANKET recipes are *data the substrate carries*,
not *code the walker executes*.

## Declaring a blanket — pattern

A cell's blanket is a substrate write that happens once at cell-creation
time:

```typescript
import { makeBlanket } from "./blanket.ts";

const blanket = makeBlanket(
  kernel,
  myCell,
  /* exposed  */ [publicAPIid, eventStreamId],
  /* internal */ [privateStateId, memoBufId],
  /* sensory  */ [inboundQueueId],
  /* active   */ [outboundChannelId],
);
```

After this call:

- `blanketOf(kernel, myCell)` returns the same blanket.
- `exposedFrom(kernel, blanket)`, `internalFrom`, `sensoryFrom`, `activeFrom`
  return the four NodeID lists.
- The blanket's NodeID is content-addressed: a second `makeBlanket` call
  with the same arguments returns the same NodeID.

### Validation: `coversAll`

When authoring a blanket by hand, `coversAll(kernel, blanket, touched)` is
the debug check: given `touched` — the set of every NodeID this cell
actually interacts with — does the blanket account for all of them?

```typescript
const touched = enumerateAllReferences(myCell);
if (!coversAll(kernel, blanket, touched)) {
  throw new Error("blanket declaration is incomplete — untracked surface");
}
```

In Friston's framing an untracked surface is a **free-energy leak**: states
that participate in the cell's dynamics without being represented in the
boundary cannot be predicted from outside the cell. The substrate stays
honest only when every interacting NodeID has a named home.

## Multi-scale composition — `unionBlankets`

Friston's framework allows blankets at multiple scales: cells compose into
larger cells, and the larger cell's boundary is derived from the parts'
boundaries. `unionBlankets` is the basic composition operation.

```typescript
const cellAB = makeCompositeCell(cellA, cellB);
const blanketAB = unionBlankets(
  kernel,
  cellAB,
  blanketOf(kernel, cellA)!,
  blanketOf(kernel, cellB)!,
);
```

Per-channel semantics are set union (deduplicated by content-address):

```
exposed(A∪B)  = exposed(A)  ∪ exposed(B)
internal(A∪B) = internal(A) ∪ internal(B)
sensory(A∪B)  = sensory(A)  ∪ sensory(B)
active(A∪B)   = active(A)   ∪ active(B)
```

Each channel's union is emitted in **canonical sorted order** (ascending by
`nodeKey`). Stable canonical order is what makes the operation
*content-addressable*: two structurally-identical compositions hash to the
same NodeID regardless of which side absorbed which.

Consequences:

- **Commutative**: `unionBlankets(k, c, a, b).node === unionBlankets(k, c, b, a).node`
- **Associative**: `unionBlankets(k, c, unionBlankets(k, c, a, b), x).node === unionBlankets(k, c, a, unionBlankets(k, c, b, x)).node`
- **Idempotent on shape**: `unionBlankets(k, c, a, a)` produces a blanket
  whose four channels are the same content-addressed sets as `a`'s
  (modulo the canonical-order normalization). The new blanket's NodeID
  differs from `a.node` only because the composite cell differs.

These laws are verified in `blanket.test.ts`.

> **Note on real-world boundary composition.** Pure set-union is the
> simplest aggregation; Friston's framework also studies cases where
> internal states of one cell become exposed at the composite scale, or
> where sensory/active channels collapse when two parts cease to need
> direct communication. Those are richer composition operators that build
> on top of `unionBlankets`. Slot 80 carries the structural primitive;
> richer operators are user-space.

## What's deferred

- **#26 — generative models.** The walker arm that *uses* a blanket to
  predict another cell's behavior. Today a blanket is data; in #26 the
  walker learns to read it. This adds a new RBasic slot (CHOICE=35 is
  already reserved) and likely a `GENERATIVE` recipe pointing at a
  blanket plus an inference recipe.
- **#29 — free-energy-aware intern.** When intern is asked to store a
  large recipe, it consults nearby blankets to compute the free-energy
  cost of the addition. Cells whose blankets predict the new recipe well
  absorb it cheaply; cells whose blankets *don't* predict it incur a
  surface-area cost. This turns intern into a thermodynamic operator and
  is what makes the substrate self-organizing rather than merely
  content-addressed.

## Slot reservations near 80

The free-energy / holographic arms cluster in adjacent slots so a quick
glance at `RBasic` shows the family:

| Slot | Arm          | Status        |
|------|--------------|---------------|
| 35   | CHOICE       | reserved      |
| 60   | LANGUAGE     | reserved      |
| 70   | QUOTIENT     | reserved      |
| 71   | INDUCTIVE    | reserved      |
| 72   | CONSTRUCTOR  | reserved      |
| 80   | BLANKET      | **this PR**   |

Cross-kernel agreement (form-kernel-go, form-kernel-rust) requires the
numeric slot to be identical across kernels. When a sibling kernel adds its
own BLANKET, slot 80 is the contract.

## Files

- `kernel.ts` — single-line addition of `RBasic.BLANKET = 80`.
- `blanket.ts` — interface, constructors, accessors, validation, union.
- `blanket.test.ts` — 21 assertions across five scenarios.
- `blanket.md` — this document.
