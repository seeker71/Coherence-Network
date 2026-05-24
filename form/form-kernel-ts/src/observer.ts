// observer.ts — observer-relative canonicalization (task #27).
//
// A recipe whose category is RBasic.OBSERVER has the shape:
//
//   OBSERVER[name-trivial, quotient-list-recipe]
//
// where `quotient-list-recipe` is an RBasic.LIST whose children are the
// QUOTIENT NodeIDs that are *active* for this observer. Two observers
// with different active-quotient sets canonicalize the same raw value to
// different (but each canonical-for-them) NodeIDs.
//
// This is the substrate's version of quantum reference frames:
//   • The underlying value-relations are observer-independent — both
//     observers agree on which raw children went in.
//   • The canonical form is observer-indexed — which equivalence class
//     the value lands in depends on which quotients the observer carries.
//
// See docs/coherence-substrate/free-energy-holographic-foundation.md
// (§ "Observer-relative canonicalization") for the full design.
//
// Relationship to QUOTIENT (#19) and symmetry-aware canonicalization
// (#23):
//   • The observer doesn't define new equivalences — it COMPOSES existing
//     ones. Each entry in `active_quotients` is a QUOTIENT NodeID; the
//     observer applies them in order before content-addressing the value.
//   • When quotient.ts is present, its `make_quotient_recipe` returns the
//     NodeIDs that go into `active_quotients`. Until then, this module
//     ships a minimal `Quotient` shape that callers can register directly
//     — the field-for-field contract is what convergence will hit. The
//     observer's storage of QUOTIENT NodeIDs stays unchanged either way.
//
// Constraints honored: additive (no hot-path touch), substrate-resident
// (observer + quotient cells are interned, content-addressed), typecheck
// clean under strict + noUncheckedIndexedAccess.

import {
  Kernel,
  Level,
  RBasic,
  type NodeID,
} from "./kernel.ts";

// ---------------------------------------------------------------------------
// Quotient — a minimal, self-contained shape that the observer composes.
//
// When quotient.ts is present, the same field-for-field contract holds and
// callers pass its EquivalenceRelation-backed quotient NodeIDs directly;
// see the file header for the convergence story. The `canonicalize_fn`
// returns the canonical *children-tuple* for a raw input — same shape that
// quotient.ts uses, so the two surfaces compose without translation.
// ---------------------------------------------------------------------------

export type CanonicalizeFn = (
  k: Kernel,
  rawChildren: readonly NodeID[],
) => readonly NodeID[];

export interface Quotient {
  /** Stable identifier — content-addressed name carried in the cell. */
  readonly name: string;
  /** Substrate-resident QUOTIENT NodeID — the cell the observer references. */
  readonly nodeID: NodeID;
  /** Canonicalize a raw children-tuple under this equivalence. */
  readonly canonicalize_fn: CanonicalizeFn;
}

// makeQuotient — interns a minimal QUOTIENT-cell (name trivial) and binds
// the canonicalize function to its NodeID. This is the *thin* shape; when
// quotient.ts lands, its `makeEquivalence` + `make_quotient_recipe`
// produce richer cells that fit the same Quotient interface (name +
// nodeID + canonicalize_fn).
//
// Cell shape: a one-child recipe at (level=BASIC, type=RBasic.QUOTIENT-
// equivalent slot 70, inst=1) carrying the name trivial. Two registrations
// with the same name share the same NodeID — content-addressing IS the
// quotient cell's identity. The numeric slot 70 is reserved by the higher-
// math design (quotient.ts uses it); we cite the constant locally to keep
// observer.ts standalone in HEAD until quotient.ts lands.
const QUOTIENT_CELL_TYPE = 70;

const HANDLERS = new Map<string, CanonicalizeFn>();

export function makeQuotient(
  k: Kernel,
  name: string,
  canonicalize_fn: CanonicalizeFn,
): Quotient {
  HANDLERS.set(name, canonicalize_fn);
  const nodeID = k.intern(
    { pkg: 1, level: Level.BASIC, type: QUOTIENT_CELL_TYPE, inst: 1 },
    [k.internString(name)],
  );
  return { name, nodeID, canonicalize_fn };
}

// resolveQuotient — look up a quotient by its NodeID. The observer
// stores NodeIDs (substrate-resident), so resolution happens once per
// internAs call.
function resolveQuotient(
  k: Kernel,
  nodeID: NodeID,
): Quotient {
  const kids = k.children(nodeID);
  if (kids.length < 1) {
    throw new Error("observer: malformed quotient cell — no name child");
  }
  const nameVal = k.trivialValue(kids[0]!);
  if (nameVal.kind !== "str") {
    throw new Error("observer: quotient cell name must be a string trivial");
  }
  const fn = HANDLERS.get(nameVal.str);
  if (fn === undefined) {
    throw new Error(
      `observer: quotient '${nameVal.str}' has no registered canonicalize_fn in this kernel`,
    );
  }
  return { name: nameVal.str, nodeID, canonicalize_fn: fn };
}

// ---------------------------------------------------------------------------
// Observer — substrate-resident recipe carrying active QUOTIENT NodeIDs.
// ---------------------------------------------------------------------------

export interface Observer {
  /** Human-readable handle ("euclidean", "relativistic", "agent-A"). */
  readonly name: string;
  /** Substrate-resident OBSERVER NodeID — content-addressed by name + set. */
  readonly nodeID: NodeID;
  /** Active quotient NodeIDs, in application order. */
  readonly active_quotients: readonly NodeID[];
}

// makeObserver — intern an observer-context recipe. Two observers with
// the same name + same active-quotient sequence share a NodeID
// (content-addressing). Different sequences ⇒ different observers, even
// if the underlying quotients are the same — order can matter when
// quotients don't commute (the doc names this as "different observers,
// different canonical forms").
export function makeObserver(
  k: Kernel,
  name: string,
  active_quotients: readonly NodeID[],
): Observer {
  // Inner list-recipe: the active quotients as a substrate-resident LIST.
  const listNode = k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.LIST, inst: 1 },
    active_quotients,
  );
  const nodeID = k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.OBSERVER, inst: 1 },
    [k.internString(name), listNode],
  );
  return { name, nodeID, active_quotients: active_quotients.slice() };
}

// internAs — intern children under `category` through `observer`'s active
// quotients first. Each active quotient canonicalizes the children-tuple
// in turn; the final tuple is what gets content-addressed.
//
// The order of application is the order the observer was constructed
// with. This matters when quotients don't commute — e.g. an integer
// quotient followed by a modular quotient gives a different canonical
// form than the reverse.
export function internAs(
  k: Kernel,
  observer: Observer,
  category: NodeID,
  children: readonly NodeID[],
): NodeID {
  let current: readonly NodeID[] = children;
  for (const q_nid of observer.active_quotients) {
    const q = resolveQuotient(k, q_nid);
    current = q.canonicalize_fn(k, current);
  }
  return k.intern(category, current);
}

// canonicalForObserver — given an already-interned node, recompute its
// canonical NodeID under `observer`'s active quotients. The node's
// category is preserved; only the children are re-canonicalized.
//
// For a TRIVIAL node there are no children to canonicalize — the node IS
// its canonical form (trivials are content-addressed by value).
export function canonicalForObserver(
  k: Kernel,
  observer: Observer,
  node: NodeID,
): NodeID {
  if (node.level === Level.TRIVIAL) return node;
  const cat = k.category(node);
  const kids = k.children(node);
  return internAs(k, observer, cat, kids);
}
