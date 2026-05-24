// symmetry.ts — symmetry-aware canonicalization for the form-kernel-ts substrate.
//
// Registers algebraic symmetry rules (commutative, associative, distributive,
// identity, idempotent, antisymmetric) against specific (RBasic-arm, op-inst)
// pairs. The `internWithSymmetries` wrapper applies these canonicalizations at
// content-addressing time so that structurally-equivalent recipes collapse to
// the same NodeID:
//
//   (+ 1 2)           ≡ (+ 2 1)              under COMMUTATIVE
//   (+ (+ 1 2) 3)     ≡ (+ 1 (+ 2 3))        under ASSOCIATIVE
//   (* 2 (+ 1 3))     ≡ (+ (* 2 1) (* 2 3))  under DISTRIBUTIVE_LEFT
//   (+ x 0)           ≡ x                    under IDENTITY (right-elim)
//   (and p p)         ≡ p                    under IDEMPOTENT
//
// This is the REAL unlock for higher math: operations that SHOULD be commutative
// become EQUAL at the substrate level — no proof required, no rewrite step in
// the walker. Structural identity carries the algebraic semantics.
//
// Design notes:
//   • Additive only — the regular `intern()` path is untouched. Opt-in via
//     `internWithSymmetries` (or pass a SymmetryRegistry to a hook layer).
//   • No new RBasic slots — rules live as plain SymmetryRule records inside a
//     SymmetryRegistry. (A future move could persist them as substrate cells
//     under an INDUCTIVE-typed value or a dedicated symmetry-recipe inside
//     RBasic.LIST, but that's an orthogonal concern.)
//   • Eager canonicalization for cheap rules (sort children, flatten nests,
//     drop identities, dedupe idempotents). Lazy / opt-in for distributive
//     (expanding `(* a (+ b c))` ⇒ `(+ (* a b) (* a c))` blows up size and is
//     only worth doing when asked).
//   • The canonical form chosen for distributivity is the SUM-OF-PRODUCTS
//     (fully-expanded) form. Both representations canonicalize to the same
//     NodeID; the rule normalizes products-over-sums into sums-of-products.

import {
  Kernel,
  NodeID,
  Level,
  RBasic,
  RMath,
  RCmp,
  RLogic,
  Triv,
  nodeKey,
} from "./kernel.ts";

// ---------------------------------------------------------------------------
// Symmetry kinds — declarative, content-addressable, substrate-resident.
// ---------------------------------------------------------------------------

export const SymmetryKind = {
  COMMUTATIVE: 1,        // (op a b)    ≡ (op b a)
  ASSOCIATIVE: 2,        // (op (op a b) c) ≡ (op a (op b c))  — flatten n-ary
  DISTRIBUTIVE_LEFT: 3,  // (op_outer a (op_inner b c)) ≡ (op_inner (op_outer a b) (op_outer a c))
  DISTRIBUTIVE_RIGHT: 4, // ((op_inner a b) op_outer c) ≡ (op_inner (op_outer a c) (op_outer b c))
  IDENTITY_LEFT: 5,      // (op e a) ≡ a
  IDENTITY_RIGHT: 6,     // (op a e) ≡ a
  ANTISYMMETRIC: 7,      // (op a b) and (op b a) — exchange flips a polarity (for COMPARE.LT/GT pairing); informational
  IDEMPOTENT: 8,         // (op a a) ≡ a
} as const;
export type SymmetryKindT = (typeof SymmetryKind)[keyof typeof SymmetryKind];

// A SymmetryRule is a flat record. The companion `op_inner_inst` field is only
// used for DISTRIBUTIVE_* — it names the inner operation that distributes out.
// The `identity` field is only used for IDENTITY_* — a NodeID for the identity
// element (e.g., the integer 0 trivial for PLUS, 1 for MUL, true for AND).
export interface SymmetryRule {
  readonly arm: number;       // RBasic.MATH / RBasic.LOGIC / RBasic.COMPARE
  readonly op_inst: number;   // RMath.PLUS / RLogic.AND / etc.
  readonly kind: SymmetryKindT;
  // Optional, kind-dependent fields:
  readonly op_inner_arm?: number;
  readonly op_inner_inst?: number;
  readonly identity?: NodeID;
}

// ---------------------------------------------------------------------------
// Registry
// ---------------------------------------------------------------------------

export class SymmetryRegistry {
  // Indexed by `arm:op_inst` for fast dispatch.
  private byOp = new Map<string, SymmetryRule[]>();

  register(rule: SymmetryRule): void {
    const key = `${rule.arm}:${rule.op_inst}`;
    const list = this.byOp.get(key);
    if (list) list.push(rule);
    else this.byOp.set(key, [rule]);
  }

  rulesFor(arm: number, op_inst: number): readonly SymmetryRule[] {
    return this.byOp.get(`${arm}:${op_inst}`) ?? [];
  }

  // The arms that have any registered rules — used to short-circuit the
  // wrapper for categories that nobody declared symmetries on.
  hasAny(arm: number, op_inst: number): boolean {
    return this.byOp.has(`${arm}:${op_inst}`);
  }
}

// Convenience for the spec deliverable's wording: `registerSymmetry(k, rule)`.
// The Kernel itself doesn't hold the registry (we want intern unchanged); the
// registry is a sidecar attached to the Kernel via a WeakMap.
const REGISTRIES = new WeakMap<Kernel, SymmetryRegistry>();

export function registryFor(k: Kernel): SymmetryRegistry {
  let reg = REGISTRIES.get(k);
  if (!reg) {
    reg = new SymmetryRegistry();
    REGISTRIES.set(k, reg);
  }
  return reg;
}

export function registerSymmetry(k: Kernel, rule: SymmetryRule): void {
  registryFor(k).register(rule);
}

// ---------------------------------------------------------------------------
// Canonicalization — pure on (kernel, arm, op_inst, children) → children
//
// Composes in this order:
//   1. ASSOCIATIVE: flatten nested same-op into n-ary.
//   2. IDENTITY_LEFT/RIGHT: drop identity-element children.
//   3. IDEMPOTENT: dedupe adjacent identical children (after sorting).
//   4. COMMUTATIVE: sort children by canonical key for stable order.
//   5. DISTRIBUTIVE_LEFT/RIGHT: expand sums-of-products. (Only applied when a
//      rule is registered; eager — fixpointed at intern time.)
//
// The output is the list of children for the canonicalized recipe at the
// SAME (arm, op_inst). If a single child remains and the op is n-ary (PLUS,
// MUL, AND, OR), the caller should collapse to that single child (degenerate
// arity). That collapse happens in `canonicalIntern` below.
// ---------------------------------------------------------------------------

function isSameOp(
  k: Kernel,
  node: NodeID,
  arm: number,
  op_inst: number,
): boolean {
  if (node.level === Level.TRIVIAL) return false;
  const cat = k.category(node);
  return cat.type === arm && cat.inst === op_inst;
}

function flattenAssociative(
  k: Kernel,
  arm: number,
  op_inst: number,
  children: readonly NodeID[],
): NodeID[] {
  const out: NodeID[] = [];
  for (const c of children) {
    if (isSameOp(k, c, arm, op_inst)) {
      // Inline grandchildren. Recursive flatten in case nesting is deep.
      const grand = flattenAssociative(k, arm, op_inst, k.children(c));
      for (const g of grand) out.push(g);
    } else {
      out.push(c);
    }
  }
  return out;
}

function dropIdentity(
  children: readonly NodeID[],
  identity: NodeID,
): NodeID[] {
  return children.filter((c) => nodeKey(c) !== nodeKey(identity));
}

function sortCommutative(children: readonly NodeID[]): NodeID[] {
  const copy = children.slice();
  copy.sort((a, b) => {
    const ka = nodeKey(a);
    const kb = nodeKey(b);
    return ka < kb ? -1 : ka > kb ? 1 : 0;
  });
  return copy;
}

function dedupeIdempotent(children: readonly NodeID[]): NodeID[] {
  // Assumes children are already sorted (commutative pass ran first).
  // For non-commutative idempotents this would need a different shape; the
  // built-in library only registers IDEMPOTENT together with COMMUTATIVE.
  const out: NodeID[] = [];
  let last = "";
  for (const c of children) {
    const key = nodeKey(c);
    if (key !== last) out.push(c);
    last = key;
  }
  return out;
}

// Distribute: outer-op over inner-op, left-distribution.
//   (outer a (inner b c d)) ⇒ (inner (outer a b) (outer a c) (outer a d))
// We look for the FIRST inner-typed child; if multiple, the recursion through
// canonicalIntern lifts them all because the result is re-canonicalized.
function distributeLeft(
  k: Kernel,
  outer_arm: number,
  outer_op_inst: number,
  inner_arm: number,
  inner_op_inst: number,
  children: readonly NodeID[],
  reg: SymmetryRegistry,
): NodeID[] | null {
  // Find an inner-typed child. If none, nothing to do.
  let innerIdx = -1;
  for (let i = 0; i < children.length; i++) {
    if (isSameOp(k, children[i]!, inner_arm, inner_op_inst)) {
      innerIdx = i;
      break;
    }
  }
  if (innerIdx === -1) return null;

  const innerNode = children[innerIdx]!;
  const innerKids = k.children(innerNode);
  // Build (inner …) where each leg is (outer …rest, innerKid)
  const newOuterCat: NodeID = {
    pkg: 1,
    level: Level.BASIC,
    type: outer_arm,
    inst: outer_op_inst,
  };
  const newInnerCat: NodeID = {
    pkg: 1,
    level: Level.BASIC,
    type: inner_arm,
    inst: inner_op_inst,
  };
  const rest = children.filter((_, i) => i !== innerIdx);
  const legs: NodeID[] = innerKids.map((ik) => {
    const legKids = [...rest, ik];
    return canonicalIntern(k, newOuterCat, legKids, reg);
  });
  // Return the children of the new outer (inner …legs) — caller will rebuild
  // the recipe at (inner_arm, inner_op_inst) and recanonicalize.
  return [
    canonicalIntern(k, newInnerCat, legs, reg),
  ];
  // Note: returning a length-1 array signals the caller to REPLACE the
  // current op entirely (the outer-op vanished). See canonicalIntern.
}

// Canonicalize children for (arm, op_inst). May change the OPERATION (e.g.
// distributive promotes outer to inner). Returns one of:
//   { kind: "same",    children }     — keep (arm, op_inst), use these children
//   { kind: "collapse", node }        — use this single node as the result
type CanonResult =
  | { kind: "same"; children: NodeID[] }
  | { kind: "collapse"; node: NodeID };

export function canonicalizeUnderSymmetries(
  k: Kernel,
  arm: number,
  op_inst: number,
  children: readonly NodeID[],
  reg: SymmetryRegistry = registryFor(k),
): CanonResult {
  const rules = reg.rulesFor(arm, op_inst);
  if (rules.length === 0) {
    return { kind: "same", children: children.slice() };
  }

  let kids: NodeID[] = children.slice();

  // 1. Associative flatten.
  if (rules.some((r) => r.kind === SymmetryKind.ASSOCIATIVE)) {
    kids = flattenAssociative(k, arm, op_inst, kids);
  }

  // 2. Distributive — eager expansion. Outer (this op) distributes over inner.
  //    Apply to a fixpoint: after expansion, the new tree is rebuilt under the
  //    inner-op, which has its own canonicalization.
  for (const r of rules) {
    if (
      r.kind === SymmetryKind.DISTRIBUTIVE_LEFT ||
      r.kind === SymmetryKind.DISTRIBUTIVE_RIGHT
    ) {
      const inner_arm = r.op_inner_arm;
      const inner_inst = r.op_inner_inst;
      if (inner_arm === undefined || inner_inst === undefined) continue;
      const distributed = distributeLeft(
        k,
        arm,
        op_inst,
        inner_arm,
        inner_inst,
        kids,
        reg,
      );
      if (distributed !== null) {
        // distribution succeeded; the result is a SINGLE inner-op node that
        // replaces the entire outer-op. Return collapse.
        return { kind: "collapse", node: distributed[0]! };
      }
    }
  }

  // 3. Identity elimination.
  for (const r of rules) {
    if (
      (r.kind === SymmetryKind.IDENTITY_LEFT ||
        r.kind === SymmetryKind.IDENTITY_RIGHT) &&
      r.identity !== undefined
    ) {
      kids = dropIdentity(kids, r.identity);
    }
  }

  // 4. Commutative — sort children for stable ordering.
  const isCommutative = rules.some((r) => r.kind === SymmetryKind.COMMUTATIVE);
  if (isCommutative) {
    kids = sortCommutative(kids);
  }

  // 5. Idempotent dedupe (post-sort).
  if (rules.some((r) => r.kind === SymmetryKind.IDEMPOTENT)) {
    kids = dedupeIdempotent(kids);
  }

  // Degenerate arity: if a single child remains for an n-ary op, collapse
  // to that child. (Empty children: collapse to identity if one is known,
  // else the empty recipe.)
  if (kids.length === 1) {
    return { kind: "collapse", node: kids[0]! };
  }
  if (kids.length === 0) {
    // Use identity if any IDENTITY_* rule provided one; otherwise empty op.
    for (const r of rules) {
      if (
        (r.kind === SymmetryKind.IDENTITY_LEFT ||
          r.kind === SymmetryKind.IDENTITY_RIGHT) &&
        r.identity !== undefined
      ) {
        return { kind: "collapse", node: r.identity };
      }
    }
  }
  return { kind: "same", children: kids };
}

// canonicalIntern — produce a NodeID at (arm, op_inst) with children
// canonicalized. May return a node at a DIFFERENT (arm, op_inst) when
// distribution or collapse re-categorizes the result.
export function canonicalIntern(
  k: Kernel,
  category: NodeID,
  children: readonly NodeID[],
  reg: SymmetryRegistry = registryFor(k),
): NodeID {
  // Recursively canonicalize children FIRST — bottom-up — so nested
  // symmetries propagate. We only re-canonicalize children whose category
  // has registered rules; others are passed through unchanged.
  const canonChildren = children.map((c) => recanonicalize(k, c, reg));

  const arm = category.type;
  const op_inst = category.inst;
  const result = canonicalizeUnderSymmetries(k, arm, op_inst, canonChildren, reg);
  if (result.kind === "collapse") return result.node;
  return k.intern(category, result.children);
}

// recanonicalize — walk an existing node and re-emit it under the symmetry
// registry. Trivials pass through. Composites are rebuilt bottom-up.
export function recanonicalize(
  k: Kernel,
  node: NodeID,
  reg: SymmetryRegistry = registryFor(k),
): NodeID {
  if (node.level === Level.TRIVIAL) return node;
  const recipe = k.recipeAt(node);
  if (!recipe) return node;
  const category = recipe.category;
  const arm = category.type;
  const op_inst = category.inst;
  // Fast path: nothing registered for this arm/op_inst AND no children need
  // recanonicalization. We still recurse into children because grandchildren
  // might.
  const newKids = recipe.children.map((c) => recanonicalize(k, c, reg));
  if (!reg.hasAny(arm, op_inst)) {
    // Children may have changed; if so we need a fresh intern at the same
    // category. If none changed, return the existing node.
    let changed = false;
    for (let i = 0; i < newKids.length; i++) {
      if (nodeKey(newKids[i]!) !== nodeKey(recipe.children[i]!)) {
        changed = true;
        break;
      }
    }
    return changed ? k.intern(category, newKids) : node;
  }
  const result = canonicalizeUnderSymmetries(k, arm, op_inst, newKids, reg);
  if (result.kind === "collapse") return result.node;
  return k.intern(category, result.children);
}

// internWithSymmetries — the opt-in wrapper. Drop-in replacement for
// `k.intern(category, children)` that applies the registered symmetries
// (top-level AND inside the children, bottom-up).
export function internWithSymmetries(
  k: Kernel,
  category: NodeID,
  children: readonly NodeID[],
  reg: SymmetryRegistry = registryFor(k),
): NodeID {
  return canonicalIntern(k, category, children, reg);
}

// ---------------------------------------------------------------------------
// Built-in symmetry library.
//
// Registers the standard algebraic identities for MATH, LOGIC, and COMPARE.
// Idempotent — calling twice is safe (rules will be duplicated, which is OK
// because canonicalization is idempotent; but it costs cycles). Prefer to call
// once per Kernel.
// ---------------------------------------------------------------------------

export function installBuiltinSymmetries(k: Kernel): void {
  const reg = registryFor(k);

  // Identity elements (interned once, reused by rules).
  const ZERO = k.internTrivialInt(0);
  const ONE = k.internTrivialInt(1);
  const TRUE = k.internTrivialBool(true);
  const FALSE = k.internTrivialBool(false);

  // ---- MATH.PLUS: commutative, associative, identity 0 -------------------
  reg.register({ arm: RBasic.MATH, op_inst: RMath.PLUS, kind: SymmetryKind.COMMUTATIVE });
  reg.register({ arm: RBasic.MATH, op_inst: RMath.PLUS, kind: SymmetryKind.ASSOCIATIVE });
  reg.register({
    arm: RBasic.MATH,
    op_inst: RMath.PLUS,
    kind: SymmetryKind.IDENTITY_RIGHT,
    identity: ZERO,
  });
  reg.register({
    arm: RBasic.MATH,
    op_inst: RMath.PLUS,
    kind: SymmetryKind.IDENTITY_LEFT,
    identity: ZERO,
  });

  // ---- MATH.MUL: commutative, associative, identity 1, distributes over PLUS
  reg.register({ arm: RBasic.MATH, op_inst: RMath.MUL, kind: SymmetryKind.COMMUTATIVE });
  reg.register({ arm: RBasic.MATH, op_inst: RMath.MUL, kind: SymmetryKind.ASSOCIATIVE });
  reg.register({
    arm: RBasic.MATH,
    op_inst: RMath.MUL,
    kind: SymmetryKind.IDENTITY_RIGHT,
    identity: ONE,
  });
  reg.register({
    arm: RBasic.MATH,
    op_inst: RMath.MUL,
    kind: SymmetryKind.IDENTITY_LEFT,
    identity: ONE,
  });
  reg.register({
    arm: RBasic.MATH,
    op_inst: RMath.MUL,
    kind: SymmetryKind.DISTRIBUTIVE_LEFT,
    op_inner_arm: RBasic.MATH,
    op_inner_inst: RMath.PLUS,
  });

  // ---- LOGIC.AND: commutative, associative, identity true, idempotent ----
  reg.register({ arm: RBasic.LOGIC, op_inst: RLogic.AND, kind: SymmetryKind.COMMUTATIVE });
  reg.register({ arm: RBasic.LOGIC, op_inst: RLogic.AND, kind: SymmetryKind.ASSOCIATIVE });
  reg.register({
    arm: RBasic.LOGIC,
    op_inst: RLogic.AND,
    kind: SymmetryKind.IDENTITY_LEFT,
    identity: TRUE,
  });
  reg.register({
    arm: RBasic.LOGIC,
    op_inst: RLogic.AND,
    kind: SymmetryKind.IDENTITY_RIGHT,
    identity: TRUE,
  });
  reg.register({ arm: RBasic.LOGIC, op_inst: RLogic.AND, kind: SymmetryKind.IDEMPOTENT });
  // AND distributes over OR.
  reg.register({
    arm: RBasic.LOGIC,
    op_inst: RLogic.AND,
    kind: SymmetryKind.DISTRIBUTIVE_LEFT,
    op_inner_arm: RBasic.LOGIC,
    op_inner_inst: RLogic.OR,
  });

  // ---- LOGIC.OR: commutative, associative, identity false, idempotent ----
  reg.register({ arm: RBasic.LOGIC, op_inst: RLogic.OR, kind: SymmetryKind.COMMUTATIVE });
  reg.register({ arm: RBasic.LOGIC, op_inst: RLogic.OR, kind: SymmetryKind.ASSOCIATIVE });
  reg.register({
    arm: RBasic.LOGIC,
    op_inst: RLogic.OR,
    kind: SymmetryKind.IDENTITY_LEFT,
    identity: FALSE,
  });
  reg.register({
    arm: RBasic.LOGIC,
    op_inst: RLogic.OR,
    kind: SymmetryKind.IDENTITY_RIGHT,
    identity: FALSE,
  });
  reg.register({ arm: RBasic.LOGIC, op_inst: RLogic.OR, kind: SymmetryKind.IDEMPOTENT });
  // OR distributes over AND (dual of the above).
  // NOTE: enabling both AND-over-OR and OR-over-AND simultaneously creates a
  // canonicalization loop (sum-of-products vs product-of-sums). We register
  // the CNF/DNF dual but treat it as informational — see symmetry.md. Only
  // AND-over-OR is eagerly expanded; OR-over-AND is left as a future option
  // gated by an explicit canonical-form flag.
  // (Not registered here to avoid the loop. The teaching is in the md file.)

  // ---- COMPARE.EQ: commutative (== is symmetric) -------------------------
  reg.register({ arm: RBasic.COMPARE, op_inst: RCmp.EQ, kind: SymmetryKind.COMMUTATIVE });
  // COMPARE.NE: commutative
  reg.register({ arm: RBasic.COMPARE, op_inst: RCmp.NE, kind: SymmetryKind.COMMUTATIVE });

  // Antisymmetric pairing for LT/GT and LE/GE — informational; not used by
  // the canonicalizer (LT and GT are different op-instances; flipping
  // children would also flip the op, which is a structural transform we
  // don't apply eagerly). Recorded so query-time tools can reason about it.
  reg.register({ arm: RBasic.COMPARE, op_inst: RCmp.LT, kind: SymmetryKind.ANTISYMMETRIC });
  reg.register({ arm: RBasic.COMPARE, op_inst: RCmp.GT, kind: SymmetryKind.ANTISYMMETRIC });
  reg.register({ arm: RBasic.COMPARE, op_inst: RCmp.LE, kind: SymmetryKind.ANTISYMMETRIC });
  reg.register({ arm: RBasic.COMPARE, op_inst: RCmp.GE, kind: SymmetryKind.ANTISYMMETRIC });

  // Silence unused-binding warnings — Triv is re-exported by the kernel and
  // some downstream consumers expect to import these constants alongside.
  void Triv;
}
