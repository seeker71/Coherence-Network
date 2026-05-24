// symmetry.test.ts — verify symmetry-aware canonicalization at intern time.
//
// Runs under tsx with no test framework. Each test is a `check(...)` call that
// throws on mismatch; main() reports pass/fail counts and exits nonzero on any
// failure. This matches the existing form-kernel-ts style (no Jest/Vitest dep).

import {
  Kernel,
  NodeID,
  Level,
  RBasic,
  RMath,
  RLogic,
  nodeKey,
} from "./kernel.ts";
import {
  registerSymmetry,
  registryFor,
  installBuiltinSymmetries,
  internWithSymmetries,
  recanonicalize,
  SymmetryKind,
} from "./symmetry.ts";

let pass = 0;
let fail = 0;
const failures: string[] = [];

function check(name: string, cond: boolean, detail = ""): void {
  if (cond) {
    pass++;
    process.stdout.write(`  ok   ${name}\n`);
  } else {
    fail++;
    failures.push(`${name}${detail ? "  — " + detail : ""}`);
    process.stdout.write(`  FAIL ${name}${detail ? "  — " + detail : ""}\n`);
  }
}

function eqNode(a: NodeID, b: NodeID): boolean {
  return nodeKey(a) === nodeKey(b);
}

// Category constructors for tests.
function catMath(op: number): NodeID {
  return { pkg: 1, level: Level.BASIC, type: RBasic.MATH, inst: op };
}
function catLogic(op: number): NodeID {
  return { pkg: 1, level: Level.BASIC, type: RBasic.LOGIC, inst: op };
}

// ---------------------------------------------------------------------------
// 1. Commutative MATH.PLUS
// ---------------------------------------------------------------------------
function testCommutativePlus(): void {
  process.stdout.write("commutative MATH.PLUS\n");
  const k = new Kernel();
  registerSymmetry(k, {
    arm: RBasic.MATH,
    op_inst: RMath.PLUS,
    kind: SymmetryKind.COMMUTATIVE,
  });

  const one = k.internTrivialInt(1);
  const two = k.internTrivialInt(2);

  // (+ 1 2)
  const ab = internWithSymmetries(k, catMath(RMath.PLUS), [one, two]);
  // (+ 2 1)
  const ba = internWithSymmetries(k, catMath(RMath.PLUS), [two, one]);

  check("(+ 1 2) ≡ (+ 2 1)", eqNode(ab, ba), `${nodeKey(ab)} vs ${nodeKey(ba)}`);

  // Regular `intern` path must remain unaffected.
  const ab_plain = k.intern(catMath(RMath.PLUS), [one, two]);
  const ba_plain = k.intern(catMath(RMath.PLUS), [two, one]);
  check(
    "plain intern: (+ 1 2) ≠ (+ 2 1)",
    !eqNode(ab_plain, ba_plain),
    `${nodeKey(ab_plain)} vs ${nodeKey(ba_plain)}`,
  );
}

// ---------------------------------------------------------------------------
// 2. Associative MATH.PLUS — nesting flattens to same NodeID.
// ---------------------------------------------------------------------------
function testAssociativePlus(): void {
  process.stdout.write("associative MATH.PLUS\n");
  const k = new Kernel();
  registerSymmetry(k, {
    arm: RBasic.MATH,
    op_inst: RMath.PLUS,
    kind: SymmetryKind.ASSOCIATIVE,
  });

  const one = k.internTrivialInt(1);
  const two = k.internTrivialInt(2);
  const three = k.internTrivialInt(3);

  // (+ (+ 1 2) 3)
  const inner_l = internWithSymmetries(k, catMath(RMath.PLUS), [one, two]);
  const left = internWithSymmetries(k, catMath(RMath.PLUS), [inner_l, three]);

  // (+ 1 (+ 2 3))
  const inner_r = internWithSymmetries(k, catMath(RMath.PLUS), [two, three]);
  const right = internWithSymmetries(k, catMath(RMath.PLUS), [one, inner_r]);

  check(
    "(+ (+ 1 2) 3) ≡ (+ 1 (+ 2 3))",
    eqNode(left, right),
    `${nodeKey(left)} vs ${nodeKey(right)}`,
  );
}

// ---------------------------------------------------------------------------
// 3. Distributive: (* 2 (+ 1 3)) ≡ (+ (* 2 1) (* 2 3))
// ---------------------------------------------------------------------------
function testDistributive(): void {
  process.stdout.write("distributive MUL over PLUS\n");
  const k = new Kernel();
  installBuiltinSymmetries(k);

  const one = k.internTrivialInt(1);
  const two = k.internTrivialInt(2);
  const three = k.internTrivialInt(3);

  // (* 2 (+ 1 3))
  const sum = internWithSymmetries(k, catMath(RMath.PLUS), [one, three]);
  const product = internWithSymmetries(k, catMath(RMath.MUL), [two, sum]);

  // (+ (* 2 1) (* 2 3))
  const p1 = internWithSymmetries(k, catMath(RMath.MUL), [two, one]);
  const p3 = internWithSymmetries(k, catMath(RMath.MUL), [two, three]);
  const expanded = internWithSymmetries(k, catMath(RMath.PLUS), [p1, p3]);

  check(
    "(* 2 (+ 1 3)) ≡ (+ (* 2 1) (* 2 3))",
    eqNode(product, expanded),
    `${nodeKey(product)} vs ${nodeKey(expanded)}`,
  );
}

// ---------------------------------------------------------------------------
// 4. Identity elimination: (+ x 0) ≡ x
// ---------------------------------------------------------------------------
function testIdentity(): void {
  process.stdout.write("identity elimination\n");
  const k = new Kernel();
  installBuiltinSymmetries(k);

  // x is an identifier — represented as a string trivial here (the natural
  // identifier shape in the kernel).
  const x = k.internString("x");
  const zero = k.internTrivialInt(0);

  // (+ x 0)
  const r = internWithSymmetries(k, catMath(RMath.PLUS), [x, zero]);

  check("(+ x 0) ≡ x", eqNode(r, x), `${nodeKey(r)} vs ${nodeKey(x)}`);

  // (+ 0 x) — left-identity elimination
  const r2 = internWithSymmetries(k, catMath(RMath.PLUS), [zero, x]);
  check("(+ 0 x) ≡ x", eqNode(r2, x), `${nodeKey(r2)} vs ${nodeKey(x)}`);

  // (* 1 x) — multiplicative identity
  const one = k.internTrivialInt(1);
  const r3 = internWithSymmetries(k, catMath(RMath.MUL), [one, x]);
  check("(* 1 x) ≡ x", eqNode(r3, x), `${nodeKey(r3)} vs ${nodeKey(x)}`);
}

// ---------------------------------------------------------------------------
// 5. LOGIC.AND: commutative + idempotent
// ---------------------------------------------------------------------------
function testLogicAnd(): void {
  process.stdout.write("logic AND commutative + idempotent\n");
  const k = new Kernel();
  installBuiltinSymmetries(k);

  const p = k.internString("p");
  const q = k.internString("q");

  // (and p q) ≡ (and q p)
  const pq = internWithSymmetries(k, catLogic(RLogic.AND), [p, q]);
  const qp = internWithSymmetries(k, catLogic(RLogic.AND), [q, p]);
  check("(and p q) ≡ (and q p)", eqNode(pq, qp));

  // (and p p) ≡ p
  const pp = internWithSymmetries(k, catLogic(RLogic.AND), [p, p]);
  check("(and p p) ≡ p", eqNode(pp, p), `${nodeKey(pp)} vs ${nodeKey(p)}`);

  // (and p true) ≡ p
  const tru = k.internTrivialBool(true);
  const pt = internWithSymmetries(k, catLogic(RLogic.AND), [p, tru]);
  check("(and p true) ≡ p", eqNode(pt, p), `${nodeKey(pt)} vs ${nodeKey(p)}`);
}

// ---------------------------------------------------------------------------
// 6. Existing `intern` path is untouched (NodeID inequality preserved).
// ---------------------------------------------------------------------------
function testInternUntouched(): void {
  process.stdout.write("plain intern semantics preserved\n");
  const k = new Kernel();
  installBuiltinSymmetries(k);

  const one = k.internTrivialInt(1);
  const two = k.internTrivialInt(2);

  const a = k.intern(catMath(RMath.PLUS), [one, two]);
  const b = k.intern(catMath(RMath.PLUS), [two, one]);
  check(
    "plain intern remains structural (no symmetry collapse)",
    !eqNode(a, b),
  );

  // And the structural identity for the SAME shape still holds:
  const a2 = k.intern(catMath(RMath.PLUS), [one, two]);
  check("plain intern still content-addressed for identical shape", eqNode(a, a2));
}

// ---------------------------------------------------------------------------
// 7. recanonicalize re-emits a previously-interned tree under symmetries.
// ---------------------------------------------------------------------------
function testRecanonicalize(): void {
  process.stdout.write("recanonicalize existing tree\n");
  const k = new Kernel();

  // Build the tree WITHOUT symmetries first.
  const one = k.internTrivialInt(1);
  const two = k.internTrivialInt(2);
  const three = k.internTrivialInt(3);

  // Plain (+ (+ 1 2) 3) and plain (+ 1 (+ 2 3)) — should differ.
  const innerL = k.intern(catMath(RMath.PLUS), [one, two]);
  const treeL = k.intern(catMath(RMath.PLUS), [innerL, three]);
  const innerR = k.intern(catMath(RMath.PLUS), [two, three]);
  const treeR = k.intern(catMath(RMath.PLUS), [one, innerR]);
  check("plain trees distinct pre-symmetry", !eqNode(treeL, treeR));

  // Install rules AFTER construction, recanonicalize.
  installBuiltinSymmetries(k);
  const canL = recanonicalize(k, treeL);
  const canR = recanonicalize(k, treeR);
  check(
    "recanonicalize: (+ (+ 1 2) 3) ≡ (+ 1 (+ 2 3))",
    eqNode(canL, canR),
    `${nodeKey(canL)} vs ${nodeKey(canR)}`,
  );
}

// ---------------------------------------------------------------------------
// 8. registryFor returns the same registry per Kernel.
// ---------------------------------------------------------------------------
function testRegistryStability(): void {
  process.stdout.write("registry per-kernel stability\n");
  const k1 = new Kernel();
  const k2 = new Kernel();
  const r1a = registryFor(k1);
  const r1b = registryFor(k1);
  const r2 = registryFor(k2);
  check("same kernel ⇒ same registry", r1a === r1b);
  check("different kernels ⇒ different registries", r1a !== r2);
}

// ---------------------------------------------------------------------------
// main
// ---------------------------------------------------------------------------
function main(): void {
  testCommutativePlus();
  testAssociativePlus();
  testDistributive();
  testIdentity();
  testLogicAnd();
  testInternUntouched();
  testRecanonicalize();
  testRegistryStability();

  process.stdout.write(`\n${pass} passed, ${fail} failed\n`);
  if (fail > 0) {
    process.stdout.write("failures:\n");
    for (const f of failures) process.stdout.write(`  - ${f}\n`);
    process.exit(1);
  }
}

main();
