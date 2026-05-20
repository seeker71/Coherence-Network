// algebra.ts — first-wave foundational algebra, expressed as Form recipes.
//
// Composes the higher-math arms already in tissue:
//   QUOTIENT   (../quotient.ts)   — Z and Q as quotient cells.
//   INDUCTIVE  (../inductive.ts)  — Nat constructors + algebraic structures.
//   PROOF      (../proof.ts)      — axioms and worked theorems.
//
// Discipline: each cell is content-addressed. The same axiom set with the
// same carrier interns to the same NodeID, so "(Z, +, 0) is an AbelianGroup"
// becomes a geometric statement at the substrate layer — the AbelianGroup
// recipe and the (Z,+,0)-instance recipe share structure, and equivalent
// presentations of the same group share their NodeID.
//
// Not the whole 200K-theorem mathlib. A focused first pass of:
//   • Nat operations (add, mul, le) by structural recursion on succ.
//   • Z = (Nat × Nat) / (a,b)~(c,d) iff a+d = b+c        (quotient).
//   • Q = (Z × Z*) / (p,q)~(r,s) iff p*s = q*r           (quotient).
//   • Algebraic structures (Monoid, Group, AbelianGroup, Ring, Field) as
//     single-constructor INDUCTIVEs whose constructor packs the carrier,
//     operations, identities, and axiom-propositions as children.
//   • Built-in instances: (Nat,+,0) Monoid; (Z,+,0) AbelianGroup;
//     (Q,+,*,0,1) Field.

import {
  Kernel,
  Level,
  RBasic,
  type NodeID,
  type Value,
} from "../kernel.ts";
import {
  BuiltinInductives,
  install_builtin_inductives,
  list_nil,
  list_cons,
  make_constructor,
  make_inductive,
  nat_of,
  nat_succ,
  nat_to_int,
  nat_zero,
  match_value,
} from "../inductive.ts";
import {
  buildQuotientLibrary,
  intern_quotient_value,
  make_quotient_recipe,
  type QuotientLibrary,
} from "../quotient.ts";
import { axiom, Prop, type Proof } from "../proof.ts";

// ---------------------------------------------------------------------------
// Nat operations
//
// Computed on the constructor-Value shape using the runtime walker
// `match_value`. Each operation is a JS function whose definition mirrors
// the Form-level recursion: add zero n = n; add (succ m) n = succ (add m n).
// The shape of the recursion IS the structural induction principle that
// proofs.ts then formalizes as a PROOF cell.
// ---------------------------------------------------------------------------

export function nat_add(
  k: Kernel,
  inductives: BuiltinInductives,
  m: Value,
  n: Value,
): Value {
  // Walk via match_value so totality is checked structurally.
  return match_value<Value>(k, m, [
    ["zero", (_args) => n],
    ["succ", (args) => {
      const inner = nat_add(k, inductives, args[0]!, n);
      // Re-wrap as succ at the value layer.
      return {
        kind: "ctor",
        inductive: inductives.Nat,
        ctor_name: "succ",
        ctor_index: 1,
        args: [inner],
      };
    }],
  ]);
}

export function nat_mul(
  k: Kernel,
  inductives: BuiltinInductives,
  m: Value,
  n: Value,
): Value {
  // mul zero n = zero
  // mul (succ m) n = add n (mul m n)
  return match_value<Value>(k, m, [
    ["zero", (_args): Value => ({
      kind: "ctor",
      inductive: inductives.Nat,
      ctor_name: "zero",
      ctor_index: 0,
      args: [],
    })],
    ["succ", (args): Value => {
      const rest = nat_mul(k, inductives, args[0]!, n);
      return nat_add(k, inductives, n, rest);
    }],
  ]);
}

export function nat_le(
  k: Kernel,
  inductives: BuiltinInductives,
  m: Value,
  n: Value,
): boolean {
  // le zero _    = true
  // le (succ _) zero = false
  // le (succ m') (succ n') = le m' n'
  return match_value<boolean>(k, m, [
    ["zero", (_) => true],
    ["succ", (mArgs) => match_value<boolean>(k, n, [
      ["zero", (_) => false],
      ["succ", (nArgs) => nat_le(k, inductives, mArgs[0]!, nArgs[0]!)],
    ])],
  ]);
}

// Convenience: compute (m + n) as a NodeID, given m, n as Nat NodeIDs.
// Useful for value-level arithmetic in tests.
export function nat_add_node(
  k: Kernel,
  inductives: BuiltinInductives,
  m: NodeID,
  n: NodeID,
): NodeID {
  // Read m as a count of succs.
  const count = countSuccs(k, m);
  // Re-emit as succ^count applied to n.
  let out = n;
  for (let i = 0; i < count; i++) out = nat_succ(k, inductives, out);
  return out;
}

function countSuccs(k: Kernel, nat: NodeID): number {
  let n = 0;
  let cur = nat;
  for (;;) {
    const recipe = k.recipeAt(cur);
    if (!recipe) break;
    if (recipe.category.type !== RBasic.CONSTRUCTOR) break;
    const nameNode = recipe.children[1];
    if (
      nameNode === undefined ||
      nameNode.level !== Level.TRIVIAL
    ) break;
    const nm = k.strs[nameNode.inst];
    if (nm === "succ") {
      n++;
      const arg = recipe.children[3];
      if (arg === undefined) break;
      cur = arg;
    } else {
      break;
    }
  }
  return n;
}

// ---------------------------------------------------------------------------
// Z — integers as a QUOTIENT of pairs of naturals.
//
//   Z := (N × N) / ~,  (a, b) ~ (c, d) iff a + d = b + c.
//
// Canonical representative chosen by the handler in ../quotient.ts is the
// difference-with-zero pair (n - 0, 0) when nonnegative or (0, -n) when
// negative. Two pairs encoding the same integer therefore intern to the
// SAME NodeID after the quotient runs.
// ---------------------------------------------------------------------------

export interface IntegerSurface {
  readonly Z_quotient: NodeID;
  readonly z_of: (a: number, b: number) => NodeID;
  readonly z_from_int: (n: number) => NodeID;
}

export function buildZ(k: Kernel, qLib: QuotientLibrary): IntegerSurface {
  // Carrier — a Nat-pair shape recipe (LIST with two slots). We use a
  // LIST placeholder so the carrier is content-addressed.
  const carrier = k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.LIST, inst: 0 },
    [k.internString("Z-carrier-NxN")],
  );
  const Z_quotient = make_quotient_recipe(
    k,
    carrier,
    qLib.EQUIV_INTEGER_FROM_NAT_PAIR.nodeID,
  );

  function z_of(a: number, b: number): NodeID {
    if (a < 0 || b < 0) {
      throw new Error(`z_of: nat-pair must be non-negative (got a=${a}, b=${b})`);
    }
    return intern_quotient_value(k, Z_quotient, [
      k.internTrivialInt(a),
      k.internTrivialInt(b),
    ]);
  }

  function z_from_int(n: number): NodeID {
    // Pick a representative pair encoding n.
    if (n >= 0) return z_of(n, 0);
    return z_of(0, -n);
  }

  return { Z_quotient, z_of, z_from_int };
}

// ---------------------------------------------------------------------------
// Q — rationals as a QUOTIENT of integer pairs (p, q) with q ≠ 0.
//
//   Q := (Z × Z*) / ~,  (p, q) ~ (r, s) iff p * s = q * r.
//
// Canonical representative is the gcd-reduced pair with the sign in the
// numerator. (3, 6) and (1, 2) and (-1, -2) all intern to the same NodeID.
// ---------------------------------------------------------------------------

export interface RationalSurface {
  readonly Q_quotient: NodeID;
  readonly q_of: (p: number, q: number) => NodeID;
}

export function buildQ(k: Kernel, qLib: QuotientLibrary): RationalSurface {
  const carrier = k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.LIST, inst: 0 },
    [k.internString("Q-carrier-ZxZ*")],
  );
  const Q_quotient = make_quotient_recipe(
    k,
    carrier,
    qLib.EQUIV_RATIONAL_FROM_INT_PAIR.nodeID,
  );

  function q_of(p: number, q: number): NodeID {
    if (q === 0) throw new Error("q_of: zero denominator");
    return intern_quotient_value(k, Q_quotient, [
      k.internTrivialInt(p),
      k.internTrivialInt(q),
    ]);
  }

  return { Q_quotient, q_of };
}

// ---------------------------------------------------------------------------
// Algebraic structures as INDUCTIVE recipes.
//
// Each structure is a single-constructor INDUCTIVE whose constructor packs
// the carrier, the operation(s), the identity(ies), and the axiom-
// propositions as arg-types. Two instances that share the same carrier-op-
// identity-axiom shape intern to the SAME constructor-value NodeID; that's
// the substrate's structural-equivalence guarantee surfacing as
// mathematical-structure equivalence.
//
// "Axioms" here are proposition NodeIDs — the structure carries claims, and
// proofs.ts provides constructed PROOF cells where the proposition NodeIDs
// line up. Whether the carrier actually SATISFIES the axiom is a proof
// obligation; the recipe-shape just asserts the shape.
// ---------------------------------------------------------------------------

// Common axiom-proposition builders. Atomic propositions are bare string
// trivials; the body of a proof relates to them by NodeID.
function p_assoc(k: Kernel, op: NodeID): NodeID {
  // assoc[op] := ∀a b c. op(op(a, b), c) = op(a, op(b, c))
  // We represent the proposition compactly as an FNCALL "assoc" applied to
  // the operation NodeID.
  const head = k.internString("assoc");
  return k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.FNCALL, inst: 0 },
    [head, op],
  );
}

function p_comm(k: Kernel, op: NodeID): NodeID {
  const head = k.internString("comm");
  return k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.FNCALL, inst: 0 },
    [head, op],
  );
}

function p_identity(k: Kernel, op: NodeID, e: NodeID): NodeID {
  const head = k.internString("identity");
  return k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.FNCALL, inst: 0 },
    [head, op, e],
  );
}

function p_inverse(k: Kernel, op: NodeID, e: NodeID, inv: NodeID): NodeID {
  const head = k.internString("inverse");
  return k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.FNCALL, inst: 0 },
    [head, op, e, inv],
  );
}

function p_distrib(k: Kernel, plus: NodeID, mul: NodeID): NodeID {
  const head = k.internString("distrib");
  return k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.FNCALL, inst: 0 },
    [head, plus, mul],
  );
}

export const Axioms = {
  assoc: p_assoc,
  comm: p_comm,
  identity: p_identity,
  inverse: p_inverse,
  distrib: p_distrib,
} as const;

// ---------------------------------------------------------------------------
// Structure inductives — one constructor each. The inductive's name is the
// structure name; the constructor's arg-types are the slots.
// ---------------------------------------------------------------------------

export interface StructureCells {
  Monoid: NodeID;
  Group: NodeID;
  AbelianGroup: NodeID;
  Ring: NodeID;
  Field: NodeID;
}

function placeholder(k: Kernel, label: string): NodeID {
  // A typed placeholder for an arg-type slot. We use a string trivial; the
  // INDUCTIVE recipe stores these by NodeID, so the same label re-uses the
  // same slot across structures (content-addressing).
  return k.internString(label);
}

export function buildStructures(k: Kernel): StructureCells {
  const carrier_ty = placeholder(k, "carrier");
  const op_ty = placeholder(k, "op");
  const id_ty = placeholder(k, "id");
  const inv_ty = placeholder(k, "inv");
  const plus_ty = placeholder(k, "plus");
  const mul_ty = placeholder(k, "mul");
  const zero_ty = placeholder(k, "zero");
  const one_ty = placeholder(k, "one");
  const axiom_ty = placeholder(k, "axiom");

  // Monoid = (carrier, op, id, axiom_assoc, axiom_id)
  const Monoid = make_inductive(k, "Monoid", [], [
    {
      ctor_name: "mk_monoid",
      ctor_index: 0,
      arg_types: [carrier_ty, op_ty, id_ty, axiom_ty, axiom_ty],
    },
  ]);

  // Group = (carrier, op, id, inv, axiom_assoc, axiom_id, axiom_inv)
  const Group = make_inductive(k, "Group", [], [
    {
      ctor_name: "mk_group",
      ctor_index: 0,
      arg_types: [carrier_ty, op_ty, id_ty, inv_ty, axiom_ty, axiom_ty, axiom_ty],
    },
  ]);

  // AbelianGroup = Group + commutativity axiom.
  const AbelianGroup = make_inductive(k, "AbelianGroup", [], [
    {
      ctor_name: "mk_abelian_group",
      ctor_index: 0,
      arg_types: [
        carrier_ty, op_ty, id_ty, inv_ty,
        axiom_ty, axiom_ty, axiom_ty, axiom_ty, // assoc, id, inv, comm
      ],
    },
  ]);

  // Ring = (carrier, plus, mul, zero, one, neg, axiom_*×5)
  // axioms: plus-abelian-group, mul-monoid, distrib-left, distrib-right
  const Ring = make_inductive(k, "Ring", [], [
    {
      ctor_name: "mk_ring",
      ctor_index: 0,
      arg_types: [
        carrier_ty, plus_ty, mul_ty, zero_ty, one_ty, inv_ty,
        axiom_ty, axiom_ty, axiom_ty, axiom_ty,
      ],
    },
  ]);

  // Field = Ring + commutative-mul + multiplicative-inverse-for-nonzero.
  const Field = make_inductive(k, "Field", [], [
    {
      ctor_name: "mk_field",
      ctor_index: 0,
      arg_types: [
        carrier_ty, plus_ty, mul_ty, zero_ty, one_ty, inv_ty,
        // axioms: assoc-plus, comm-plus, id-plus, inv-plus,
        //         assoc-mul,  comm-mul,  id-mul,
        //         distrib, inv-mul-nonzero
        axiom_ty, axiom_ty, axiom_ty, axiom_ty,
        axiom_ty, axiom_ty, axiom_ty,
        axiom_ty, axiom_ty,
      ],
    },
  ]);

  return { Monoid, Group, AbelianGroup, Ring, Field };
}

// ---------------------------------------------------------------------------
// Instance builders — pack a carrier + ops + identities + axiom propositions
// into the structure-constructor.
//
// The axiom-proposition NodeIDs are content-addressed: two instances with
// the same carrier, op, and identity share their axiom propositions
// (because p_assoc(op) is the same NodeID for the same op). Two instances
// presenting the same group therefore share the same instance NodeID —
// "up to isomorphism" collapses into geometric identity.
// ---------------------------------------------------------------------------

export interface MonoidInstance {
  readonly cell: NodeID;
  readonly carrier: NodeID;
  readonly op: NodeID;
  readonly id: NodeID;
}

export function make_monoid(
  k: Kernel,
  S: StructureCells,
  carrier: NodeID,
  op: NodeID,
  id: NodeID,
): MonoidInstance {
  const a_assoc = axiom(k, p_assoc(k, op));
  const a_id = axiom(k, p_identity(k, op, id));
  const cell = make_constructor(k, S.Monoid, "mk_monoid", [
    carrier, op, id, a_assoc.proposition, a_id.proposition,
  ]);
  return { cell, carrier, op, id };
}

export interface GroupInstance {
  readonly cell: NodeID;
  readonly carrier: NodeID;
  readonly op: NodeID;
  readonly id: NodeID;
  readonly inv: NodeID;
}

export function make_group(
  k: Kernel,
  S: StructureCells,
  carrier: NodeID,
  op: NodeID,
  id: NodeID,
  inv: NodeID,
): GroupInstance {
  const cell = make_constructor(k, S.Group, "mk_group", [
    carrier, op, id, inv,
    p_assoc(k, op),
    p_identity(k, op, id),
    p_inverse(k, op, id, inv),
  ]);
  return { cell, carrier, op, id, inv };
}

export interface AbelianGroupInstance extends GroupInstance {}

export function make_abelian_group(
  k: Kernel,
  S: StructureCells,
  carrier: NodeID,
  op: NodeID,
  id: NodeID,
  inv: NodeID,
): AbelianGroupInstance {
  const cell = make_constructor(k, S.AbelianGroup, "mk_abelian_group", [
    carrier, op, id, inv,
    p_assoc(k, op),
    p_identity(k, op, id),
    p_inverse(k, op, id, inv),
    p_comm(k, op),
  ]);
  return { cell, carrier, op, id, inv };
}

export interface RingInstance {
  readonly cell: NodeID;
  readonly carrier: NodeID;
  readonly plus: NodeID;
  readonly mul: NodeID;
  readonly zero: NodeID;
  readonly one: NodeID;
  readonly neg: NodeID;
}

export function make_ring(
  k: Kernel,
  S: StructureCells,
  carrier: NodeID,
  plus: NodeID,
  mul: NodeID,
  zero: NodeID,
  one: NodeID,
  neg: NodeID,
): RingInstance {
  const cell = make_constructor(k, S.Ring, "mk_ring", [
    carrier, plus, mul, zero, one, neg,
    p_assoc(k, plus),
    p_assoc(k, mul),
    p_identity(k, plus, zero),
    p_distrib(k, plus, mul),
  ]);
  return { cell, carrier, plus, mul, zero, one, neg };
}

export interface FieldInstance extends RingInstance {}

export function make_field(
  k: Kernel,
  S: StructureCells,
  carrier: NodeID,
  plus: NodeID,
  mul: NodeID,
  zero: NodeID,
  one: NodeID,
  neg: NodeID,
): FieldInstance {
  const cell = make_constructor(k, S.Field, "mk_field", [
    carrier, plus, mul, zero, one, neg,
    p_assoc(k, plus),
    p_comm(k, plus),
    p_identity(k, plus, zero),
    p_inverse(k, plus, zero, neg),
    p_assoc(k, mul),
    p_comm(k, mul),
    p_identity(k, mul, one),
    p_distrib(k, plus, mul),
    k.internString("inv-mul-nonzero"), // placeholder for multiplicative inverse axiom
  ]);
  return { cell, carrier, plus, mul, zero, one, neg };
}

// ---------------------------------------------------------------------------
// Canonical instances — (Nat,+,0) Monoid, (Z,+,0) AbelianGroup, (Q,+,*,0,1) Field.
// Built once per Kernel via buildMathlib().
// ---------------------------------------------------------------------------

export interface Mathlib {
  inductives: BuiltinInductives;
  qLib: QuotientLibrary;
  structures: StructureCells;

  Z: IntegerSurface;
  Q: RationalSurface;

  // Canonical instances.
  NatPlusMonoid: MonoidInstance;
  ZAdditiveAbelianGroup: AbelianGroupInstance;
  QField: FieldInstance;
}

export function buildMathlib(k: Kernel): Mathlib {
  const inductives = install_builtin_inductives(k);
  const qLib = buildQuotientLibrary(k);
  const structures = buildStructures(k);

  const Z = buildZ(k, qLib);
  const Q = buildQ(k, qLib);

  // (Nat, +, 0) — Monoid.
  // We name the operation with a stable string trivial "nat-plus".
  const natPlusOp = k.internString("nat-plus");
  const natZero = nat_of(k, inductives, 0);
  const NatPlusMonoid = make_monoid(
    k,
    structures,
    inductives.Nat,
    natPlusOp,
    natZero,
  );

  // (Z, +, 0) — AbelianGroup.
  const zPlusOp = k.internString("z-plus");
  const zNegOp = k.internString("z-neg");
  const zZero = Z.z_from_int(0);
  const ZAdditiveAbelianGroup = make_abelian_group(
    k,
    structures,
    Z.Z_quotient,
    zPlusOp,
    zZero,
    zNegOp,
  );

  // (Q, +, *, 0, 1) — Field.
  const qPlusOp = k.internString("q-plus");
  const qMulOp = k.internString("q-mul");
  const qNegOp = k.internString("q-neg");
  const qZero = Q.q_of(0, 1);
  const qOne = Q.q_of(1, 1);
  const QField = make_field(
    k,
    structures,
    Q.Q_quotient,
    qPlusOp,
    qMulOp,
    qZero,
    qOne,
    qNegOp,
  );

  return {
    inductives,
    qLib,
    structures,
    Z,
    Q,
    NatPlusMonoid,
    ZAdditiveAbelianGroup,
    QField,
  };
}

// Re-export the helpers that proofs.ts / mathlib.test.ts pull through.
export {
  list_cons,
  list_nil,
  nat_of,
  nat_succ,
  nat_to_int,
  nat_zero,
};
