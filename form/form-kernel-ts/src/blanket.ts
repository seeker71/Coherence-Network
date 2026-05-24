// Markov blanket recipes — RBasic.BLANKET (slot 80).
//
// A blanket declares a cell's boundary as a substrate-resident recipe carrying
// four NodeID lists:
//
//   (BLANKET cell
//     :exposed   [NodeIDs the cell makes visible to its environment]
//     :internal  [NodeIDs the cell keeps private]
//     :sensory   [NodeIDs the cell receives at the boundary]
//     :active    [NodeIDs the cell can emit across the boundary])
//
// The blanket itself is content-addressed: two cells whose blankets have the
// same exposed/internal/sensory/active shape share the same blanket NodeID.
// That is the substrate's promise: structural identity for free, hallucination
// bounded by what NodeIDs exist.
//
// The cell → blanket association is held in a per-kernel WeakMap-keyed
// auxiliary registry (here: a Map keyed by nodeKey(cell)). It is intentionally
// kept outside the recipe tree so a blanket can be looked up by any cell that
// declares one, and so the same blanket-recipe can be shared across cells
// without forcing them into the same recipe.
//
// What's deferred: generative models that read a blanket and predict another
// cell's behavior (#26), and free-energy-aware intern (#29) that uses blanket
// surface area as a cost signal.
//
// See ./blanket.md for architecture, ./blanket.test.ts for the contract.

import {
  Kernel,
  Level,
  RBasic,
  nodeKey,
  type NodeID,
} from "./kernel.ts";

// ---------------------------------------------------------------------------
// Shape
// ---------------------------------------------------------------------------

// A MarkovBlanket is the NodeID of a BLANKET-category recipe. The recipe's
// children are five entries, in fixed order:
//
//   [0] cell      — the NodeID this blanket belongs to
//   [1] exposed   — a LIST recipe of NodeIDs
//   [2] internal  — a LIST recipe of NodeIDs
//   [3] sensory   — a LIST recipe of NodeIDs
//   [4] active    — a LIST recipe of NodeIDs
//
// The interface is a structural alias: callers hold a NodeID and use the
// accessors below. We keep it nominal-ish via a branded type so a stray
// NodeID isn't accidentally accepted where a blanket is expected.
export interface MarkovBlanket {
  readonly __blanket: true;
  readonly node: NodeID;
}

const BLANKET_CHILD_COUNT = 5;

// Fixed indices into a blanket recipe's children.
const IDX_CELL = 0;
const IDX_EXPOSED = 1;
const IDX_INTERNAL = 2;
const IDX_SENSORY = 3;
const IDX_ACTIVE = 4;

// ---------------------------------------------------------------------------
// Category constructors
// ---------------------------------------------------------------------------

// Category NodeID for a BLANKET recipe. Built once per kernel surface; the
// recipe's `category` field carries (BASIC, BLANKET, 0). Other arms use 0 as
// a "no sub-op" instance — blankets don't have variants today.
function blanketCategory(): NodeID {
  return {
    pkg: 1,
    level: Level.BASIC,
    type: RBasic.BLANKET,
    inst: 0,
  };
}

// Category NodeID for a LIST recipe (used for each of the four boundary
// lists). Mirrors how reader.ts / compiler.ts build list recipes.
function listCategory(): NodeID {
  return {
    pkg: 1,
    level: Level.BASIC,
    type: RBasic.LIST,
    inst: 0,
  };
}

// internList — interns a LIST recipe holding the given NodeIDs as children.
// Same items in the same order ⇒ same NodeID.
function internList(k: Kernel, items: readonly NodeID[]): NodeID {
  return k.intern(listCategory(), items);
}

// ---------------------------------------------------------------------------
// Cell → blanket registry
// ---------------------------------------------------------------------------

// One registry per Kernel instance. We keep it module-local instead of a
// kernel field so the kernel.ts surface stays additive-only: BLANKET is just
// another slot in the RBasic enum; everything else lives here.
const registries = new WeakMap<Kernel, Map<string, NodeID>>();

function registryFor(k: Kernel): Map<string, NodeID> {
  let m = registries.get(k);
  if (m === undefined) {
    m = new Map();
    registries.set(k, m);
  }
  return m;
}

// ---------------------------------------------------------------------------
// Public surface
// ---------------------------------------------------------------------------

// makeBlanket — intern a BLANKET recipe for `cell` and register the
// cell → blanket association.
//
// Content-addressing: two calls with the same cell + same four sorted-or-
// not item lists yield the same NodeID. We do NOT sort the input lists —
// order is a declared property of the boundary (e.g. sensory channels often
// have meaningful order). Callers wanting set-semantics should sort before
// passing.
export function makeBlanket(
  k: Kernel,
  cell: NodeID,
  exposed: readonly NodeID[],
  internal: readonly NodeID[],
  sensory: readonly NodeID[],
  active: readonly NodeID[],
): MarkovBlanket {
  const exposedNode = internList(k, exposed);
  const internalNode = internList(k, internal);
  const sensoryNode = internList(k, sensory);
  const activeNode = internList(k, active);

  const node = k.intern(blanketCategory(), [
    cell,
    exposedNode,
    internalNode,
    sensoryNode,
    activeNode,
  ]);

  registryFor(k).set(nodeKey(cell), node);
  return { __blanket: true, node };
}

// blanketOf — look up the blanket associated with a cell. Returns undefined
// if the cell has not declared one in this kernel.
export function blanketOf(
  k: Kernel,
  cell: NodeID,
): MarkovBlanket | undefined {
  const node = registryFor(k).get(nodeKey(cell));
  if (node === undefined) return undefined;
  return { __blanket: true, node };
}

// asBlanket — view a NodeID as a blanket (no registry lookup). Throws if the
// NodeID is not actually a BLANKET recipe with the expected child count.
// Used by code that received a blanket NodeID through some other channel
// (e.g. a recipe field) and wants typed access.
export function asBlanket(k: Kernel, node: NodeID): MarkovBlanket {
  validateBlanket(k, node);
  return { __blanket: true, node };
}

function validateBlanket(k: Kernel, node: NodeID): void {
  if (node.level !== Level.BASIC || node.type !== RBasic.BLANKET) {
    throw new Error(
      `blanket: expected BLANKET recipe, got ${nodeKey(node)}`,
    );
  }
  const kids = k.children(node);
  if (kids.length !== BLANKET_CHILD_COUNT) {
    throw new Error(
      `blanket: malformed (expected ${BLANKET_CHILD_COUNT} children, got ${kids.length})`,
    );
  }
}

// cellOf — the cell this blanket belongs to.
export function cellOf(k: Kernel, blanket: MarkovBlanket): NodeID {
  const kids = k.children(blanket.node);
  return kids[IDX_CELL]!;
}

// Accessors — each returns the NodeID list at the named index. The returned
// array is a fresh slice; callers may not mutate the kernel's child storage.
export function exposedFrom(k: Kernel, blanket: MarkovBlanket): NodeID[] {
  return listItems(k, blanket, IDX_EXPOSED);
}

export function internalFrom(k: Kernel, blanket: MarkovBlanket): NodeID[] {
  return listItems(k, blanket, IDX_INTERNAL);
}

export function sensoryFrom(k: Kernel, blanket: MarkovBlanket): NodeID[] {
  return listItems(k, blanket, IDX_SENSORY);
}

export function activeFrom(k: Kernel, blanket: MarkovBlanket): NodeID[] {
  return listItems(k, blanket, IDX_ACTIVE);
}

function listItems(
  k: Kernel,
  blanket: MarkovBlanket,
  childIndex: number,
): NodeID[] {
  const kids = k.children(blanket.node);
  const listNode = kids[childIndex];
  if (listNode === undefined) {
    throw new Error(
      `blanket: missing child ${childIndex} on ${nodeKey(blanket.node)}`,
    );
  }
  return k.children(listNode).slice();
}

// ---------------------------------------------------------------------------
// Validation
// ---------------------------------------------------------------------------

// coversAll — predicate: do the blanket's four sets together cover `touched`?
//
// `touched` is the set of every NodeID the cell actually interacts with —
// the caller computes it from whatever ground truth is available (the cell's
// recipe children, an edge index, a Form runtime trace). coversAll reports
// whether every NodeID in `touched` appears in at least one of exposed,
// internal, sensory, or active.
//
// Used during validation when authoring a blanket — if coversAll returns
// false, the boundary declaration is incomplete and the cell has untracked
// surface area (a free-energy leak in Friston's framing).
export function coversAll(
  k: Kernel,
  blanket: MarkovBlanket,
  touched: readonly NodeID[],
): boolean {
  const covered = new Set<string>();
  for (const n of exposedFrom(k, blanket)) covered.add(nodeKey(n));
  for (const n of internalFrom(k, blanket)) covered.add(nodeKey(n));
  for (const n of sensoryFrom(k, blanket)) covered.add(nodeKey(n));
  for (const n of activeFrom(k, blanket)) covered.add(nodeKey(n));
  for (const n of touched) {
    if (!covered.has(nodeKey(n))) return false;
  }
  return true;
}

// ---------------------------------------------------------------------------
// Composition
// ---------------------------------------------------------------------------

// unionBlankets — combine two blankets into a single composite blanket. Used
// when two cells compose into a larger cell and the larger cell's boundary
// is the disjoint union of the parts' boundaries.
//
// Semantics:
//   - exposed_union   = exposed(a)  ∪ exposed(b)
//   - internal_union  = internal(a) ∪ internal(b)
//   - sensory_union   = sensory(a)  ∪ sensory(b)
//   - active_union    = active(a)   ∪ active(b)
//   - cell            = the composite cell NodeID (caller-supplied — the two
//                       parts' cells need not be the composite's cell).
//
// Sets are deduplicated by content-address (nodeKey) and emitted in a stable
// canonical order: sorted ascending by nodeKey. Stable order is what makes
// the composition content-addressable: two structurally-identical unions
// produce the same NodeID regardless of which side they came from, so the
// operation is commutative AND associative under the substrate's intern map.
export function unionBlankets(
  k: Kernel,
  compositeCell: NodeID,
  a: MarkovBlanket,
  b: MarkovBlanket,
): MarkovBlanket {
  const merged = (
    xs: readonly NodeID[],
    ys: readonly NodeID[],
  ): NodeID[] => {
    const m = new Map<string, NodeID>();
    for (const n of xs) m.set(nodeKey(n), n);
    for (const n of ys) m.set(nodeKey(n), n);
    return [...m.values()].sort((p, q) =>
      nodeKey(p) < nodeKey(q) ? -1 : nodeKey(p) > nodeKey(q) ? 1 : 0,
    );
  };

  return makeBlanket(
    k,
    compositeCell,
    merged(exposedFrom(k, a), exposedFrom(k, b)),
    merged(internalFrom(k, a), internalFrom(k, b)),
    merged(sensoryFrom(k, a), sensoryFrom(k, b)),
    merged(activeFrom(k, a), activeFrom(k, b)),
  );
}
