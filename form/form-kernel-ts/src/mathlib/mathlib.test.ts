// mathlib.test.ts — first-wave mathlib bootstrap verification.
//
// Run: npx tsx src/mathlib/mathlib.test.ts
//
// Confirms:
//   1. Z's content-addressing — (3,1) and (5,3) intern to the SAME NodeID
//      (both represent the integer +2 under the quotient).
//   2. Q's content-addressing — (3,6) and (1,2) intern to the SAME NodeID
//      (both represent 1/2 after gcd-reduction + sign-normalization).
//   3. Algebraic structures recognized geometrically — the same (Z,+,0)
//      built twice shares NodeID; (Nat,+,0) is a different cell.
//   4. PROOF for "∀n. 0 + n = n" by induction validates.
//   5. Composition of bijections is bijective (proof composes).
//   6. Worked proof: forall-intro on an atomic P.
//   7. Worked proof: ¬¬P ⊢ P (classical double-negation).

import { Kernel, type NodeID } from "../kernel.ts";
import { nat_to_int } from "../inductive.ts";
import { valid } from "../proof.ts";
import {
  buildMathlib,
  make_abelian_group,
  make_monoid,
  nat_add,
  nat_le,
  nat_mul,
  nat_of,
} from "./algebra.ts";
import {
  buildFunctionCells,
  compose_bijections,
  make_bijection,
  make_function,
  make_injection,
} from "./functions.ts";
import {
  buildOrderCells,
  make_partial_order,
  make_total_order,
} from "./order.ts";
import {
  prove_compose_bijective,
  prove_forall_intro_applied,
  prove_not_not_elim,
  prove_zero_add,
} from "./proofs.ts";

let passed = 0;
let failed = 0;

function check(name: string, ok: boolean, detail?: string): void {
  if (ok) {
    passed++;
    console.log(`  PASS  ${name}`);
  } else {
    failed++;
    console.log(`  FAIL  ${name}${detail ? ` — ${detail}` : ""}`);
  }
}
function header(s: string) { console.log(`\n${s}`); }

function eqNode(a: NodeID, b: NodeID): boolean {
  return a.pkg === b.pkg && a.level === b.level && a.type === b.type && a.inst === b.inst;
}
function key(n: NodeID): string {
  return `${n.pkg}.${n.level}.${n.type}.${n.inst}`;
}

// ---------------------------------------------------------------------------
// Test 1 — Z's content-addressing under the integer-from-nat-pair quotient.
// ---------------------------------------------------------------------------

header("Test 1: Z is a substrate quotient (structural integer-equality)");
{
  const k = new Kernel();
  const M = buildMathlib(k);

  const z31 = M.Z.z_of(3, 1);   // 3 − 1 = 2
  const z53 = M.Z.z_of(5, 3);   // 5 − 3 = 2
  const z97 = M.Z.z_of(9, 7);   // 9 − 7 = 2
  const z20 = M.Z.z_of(2, 0);   // canonical (2, 0)
  const z03 = M.Z.z_of(0, 3);   // −3
  const z14 = M.Z.z_of(1, 4);   // 1 − 4 = −3

  check("Z: (3,1) ≡ (5,3) — both encode +2", eqNode(z31, z53),
    `${key(z31)} vs ${key(z53)}`);
  check("Z: (3,1) ≡ (9,7) — transitive equivalence", eqNode(z31, z97));
  check("Z: (3,1) ≡ (2,0) — canonical match", eqNode(z31, z20));
  check("Z: (0,3) ≡ (1,4) — negative integers also collapse", eqNode(z03, z14));
  check("Z: (3,1) ≠ (0,3) — distinct integers stay distinct", !eqNode(z31, z03));
}

// ---------------------------------------------------------------------------
// Test 2 — Q's content-addressing under the rational-from-int-pair quotient.
// ---------------------------------------------------------------------------

header("Test 2: Q is a substrate quotient (structural rational-equality)");
{
  const k = new Kernel();
  const M = buildMathlib(k);

  const q12 = M.Q.q_of(1, 2);
  const q36 = M.Q.q_of(3, 6);
  const q_neg = M.Q.q_of(-1, -2);
  const q_other = M.Q.q_of(2, 3);

  check("Q: (1,2) ≡ (3,6) — gcd-reduced match", eqNode(q12, q36));
  check("Q: (1,2) ≡ (-1,-2) — sign-normalized match", eqNode(q12, q_neg));
  check("Q: (1,2) ≠ (2,3) — distinct rationals stay distinct", !eqNode(q12, q_other));
}

// ---------------------------------------------------------------------------
// Test 3 — Algebraic structures: (Z,+,0) AbelianGroup recipe matches itself.
// ---------------------------------------------------------------------------

header("Test 3: algebraic structures recognized geometrically");
{
  const k = new Kernel();
  const M = buildMathlib(k);

  // Rebuild (Z,+,0) AbelianGroup from the same carrier/op/id — should
  // share NodeID with M.ZAdditiveAbelianGroup.
  const zPlus = k.internString("z-plus");
  const zNeg = k.internString("z-neg");
  const zZero = M.Z.z_from_int(0);
  const rebuilt = make_abelian_group(
    k, M.structures, M.Z.Z_quotient, zPlus, zZero, zNeg,
  );
  check(
    "(Z,+,0) AbelianGroup — rebuild interns to same NodeID",
    eqNode(rebuilt.cell, M.ZAdditiveAbelianGroup.cell),
    `rebuilt=${key(rebuilt.cell)} vs original=${key(M.ZAdditiveAbelianGroup.cell)}`,
  );

  // (Nat, +, 0) Monoid — should differ from (Z, +, 0) AbelianGroup.
  const natPlus = k.internString("nat-plus");
  const natZero = nat_of(k, M.inductives, 0);
  const m2 = make_monoid(k, M.structures, M.inductives.Nat, natPlus, natZero);
  check(
    "Monoid (Nat,+,0) — rebuild interns to same NodeID",
    eqNode(m2.cell, M.NatPlusMonoid.cell),
  );
  check(
    "Monoid (Nat,+,0) ≠ AbelianGroup (Z,+,0)",
    !eqNode(M.NatPlusMonoid.cell, M.ZAdditiveAbelianGroup.cell),
  );

  // Field axiom recipe self-matches.
  const QField2 = M.QField;
  check(
    "Field (Q,+,*,0,1) — cell present + non-trivial",
    QField2.cell.inst > 0,
  );
}

// ---------------------------------------------------------------------------
// Test 4 — Nat operations on the constructor-Value shape.
// ---------------------------------------------------------------------------

header("Test 4: Nat operations (add, mul, le)");
{
  const k = new Kernel();
  const M = buildMathlib(k);
  const I = M.inductives;

  const two = nat_of(k, I, 2);
  const three = nat_of(k, I, 3);

  // We need Value-shaped operands. Walk via existing helpers in a
  // lightweight way — build Values from constructor recipes manually.
  function natValue(n: number): import("../kernel.ts").Value {
    if (n === 0) {
      return {
        kind: "ctor",
        inductive: I.Nat,
        ctor_name: "zero",
        ctor_index: 0,
        args: [],
      };
    }
    return {
      kind: "ctor",
      inductive: I.Nat,
      ctor_name: "succ",
      ctor_index: 1,
      args: [natValue(n - 1)],
    };
  }

  const v2 = natValue(2);
  const v3 = natValue(3);

  const sum = nat_add(k, I, v2, v3);
  check("nat_add(2, 3) = 5", nat_to_int(sum) === 5);

  const prod = nat_mul(k, I, v2, v3);
  check("nat_mul(2, 3) = 6", nat_to_int(prod) === 6);

  const z = natValue(0);
  const sum_zero_left = nat_add(k, I, z, v3);
  check("nat_add(0, 3) = 3 — left identity", nat_to_int(sum_zero_left) === 3);

  check("nat_le(2, 3) = true", nat_le(k, I, v2, v3));
  check("nat_le(3, 2) = false", !nat_le(k, I, v3, v2));
  check("nat_le(2, 2) = true (reflexive)", nat_le(k, I, v2, v2));

  // Avoid unused-warning by referencing the NodeID forms.
  void two; void three;
}

// ---------------------------------------------------------------------------
// Test 5 — Proof: ∀n. 0 + n = n by induction.
// ---------------------------------------------------------------------------

header("Test 5: PROOF for 0 + n = n by induction on n");
{
  const k = new Kernel();
  const M = buildMathlib(k);

  const zero = nat_of(k, M.inductives, 0);
  // The "add" operator is a substrate symbol; for the PROOF we use the
  // shared "nat-plus" string trivial so the proposition's content is
  // stable.
  const addOp = k.internString("nat-plus");
  const { proof } = prove_zero_add(k, M.inductives.Nat, zero, addOp);

  check("zero_add: proof construction valid", valid(k, proof));

  // The conclusion's proposition should be a ∀-recipe applied to ?n on
  // the (0 + n = n) body. We don't decode it deeply; valid() already
  // re-verified the rule application.
  check("zero_add: proof carries non-null proposition", proof.proposition.inst > 0);
}

// ---------------------------------------------------------------------------
// Test 6 — Worked proof: forall-intro on an atomic proposition.
// ---------------------------------------------------------------------------

header("Test 6: forall-intro applied to atomic P");
{
  const k = new Kernel();
  const { proof, conclusion } = prove_forall_intro_applied(k, "P");
  check("forall-intro: proof is valid", valid(k, proof));
  check("forall-intro: conclusion non-trivial", conclusion.inst > 0);
}

// ---------------------------------------------------------------------------
// Test 7 — Worked proof: ¬¬P ⊢ P (classical double-negation elimination).
// ---------------------------------------------------------------------------

header("Test 7: ¬¬P ⊢ P (classical double-negation)");
{
  const k = new Kernel();
  const { proof } = prove_not_not_elim(k);
  check("not-not-elim: proof is valid", valid(k, proof));
}

// ---------------------------------------------------------------------------
// Test 8 — Functions + bijection composition.
// ---------------------------------------------------------------------------

header("Test 8: functions + bijection composition");
{
  const k = new Kernel();
  const M = buildMathlib(k);
  const fnCells = buildFunctionCells(k);

  // Three carriers (atoms standing in for sets A, B, C).
  const A = k.internString("A");
  const B = k.internString("B");
  const C = k.internString("C");

  // Function rules as named symbols.
  const fRule = k.internString("f-rule");
  const gRule = k.internString("g-rule");

  const f = make_bijection(k, fnCells, A, B, fRule);
  const g = make_bijection(k, fnCells, B, C, gRule);
  const gof = compose_bijections(k, fnCells, g, f);

  check("compose_bijections: domain matches f's domain", eqNode(gof.domain, A));
  check("compose_bijections: codomain matches g's codomain", eqNode(gof.codomain, C));

  // Same composition recomputed should intern to the same cell.
  const gof2 = compose_bijections(k, fnCells, g, f);
  check("compose_bijections: idempotent under re-construction", eqNode(gof.cell, gof2.cell));

  // Proof: composition of bijections is bijective.
  const { proof } = prove_compose_bijective(k, fRule, gRule);
  check("compose_bijective: proof is valid", valid(k, proof));

  // Also check basic function variants.
  const fn1 = make_function(k, fnCells, A, B, fRule);
  const inj1 = make_injection(k, fnCells, A, B, fRule);
  check("Function (A→B,f) cell present", fn1.cell.inst > 0);
  check("Injection (A→B,f) cell distinct from plain Function", !eqNode(fn1.cell, inj1.cell));

  void M;
}

// ---------------------------------------------------------------------------
// Test 9 — Order / PartialOrder / TotalOrder distinct cells.
// ---------------------------------------------------------------------------

header("Test 9: order structures");
{
  const k = new Kernel();
  const ordCells = buildOrderCells(k);

  const carrier = k.internString("nat");
  const le = k.internString("nat-le");
  const po = make_partial_order(k, ordCells, carrier, le);
  const to = make_total_order(k, ordCells, carrier, le);

  check("PartialOrder cell present", po.cell.inst > 0);
  check("TotalOrder cell distinct from PartialOrder", !eqNode(po.cell, to.cell));

  // Same construction shares NodeID.
  const to2 = make_total_order(k, ordCells, carrier, le);
  check("TotalOrder content-addressed", eqNode(to.cell, to2.cell));
}

// ---------------------------------------------------------------------------
// Summary
// ---------------------------------------------------------------------------

console.log(`\n[summary] ${passed}/${passed + failed} passed`);
if (failed > 0) process.exit(1);
