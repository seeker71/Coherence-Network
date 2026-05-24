// quotient.test.ts — QUOTIENT arm proof-of-shape tests.
//
// Verifies the core promise: two representatives equivalent under a
// quotient's relation receive the SAME NodeID. Run with:
//
//   npx tsx src/quotient.test.ts
//
// Lightweight assertion harness so we don't pull in Jest/Vitest for the
// quotient conformance folder. Exits non-zero on failure; prints PASS/FAIL lines.

import { Kernel, Level, RBasic, nodeKey, type NodeID } from "./kernel.ts";
import {
  buildQuotientLibrary,
  canonical_form,
  Decidability,
  getHandler,
  intern_quotient_value,
  make_quotient_recipe,
  makeEquivalence,
  quotient_equal,
  quotient_parts,
  registerHandler,
  resolve_equivalence,
  CanonStrategy,
} from "./quotient.ts";

let failures = 0;
let passes = 0;

function ok(name: string, cond: boolean, detail = ""): void {
  if (cond) {
    passes++;
    console.log(`PASS  ${name}`);
  } else {
    failures++;
    console.log(`FAIL  ${name}${detail ? ` — ${detail}` : ""}`);
  }
}

function eqNode(a: NodeID, b: NodeID): boolean {
  return (
    a.pkg === b.pkg &&
    a.level === b.level &&
    a.type === b.type &&
    a.inst === b.inst
  );
}

// ---------------------------------------------------------------------------
// Test 1 — RBasic.QUOTIENT constant value (no collision with INDUCTIVE)
// ---------------------------------------------------------------------------

ok(
  "RBasic.QUOTIENT is slot 70",
  (RBasic as Record<string, number>).QUOTIENT === 70,
  `actual = ${(RBasic as Record<string, number>).QUOTIENT}`,
);

// ---------------------------------------------------------------------------
// Test 2 — Integer-from-nat-pair: (3,1) and (5,3) share NodeID
// ---------------------------------------------------------------------------

{
  const k = new Kernel();
  const lib = buildQuotientLibrary(k);
  // Carrier: just use a placeholder list-recipe.
  const carrier = k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.LIST, inst: 0 },
    [],
  );
  const Q = make_quotient_recipe(
    k,
    carrier,
    lib.EQUIV_INTEGER_FROM_NAT_PAIR.nodeID,
  );

  const v31 = intern_quotient_value(k, Q, [
    k.internTrivialInt(3),
    k.internTrivialInt(1),
  ]);
  const v53 = intern_quotient_value(k, Q, [
    k.internTrivialInt(5),
    k.internTrivialInt(3),
  ]);
  const v97 = intern_quotient_value(k, Q, [
    k.internTrivialInt(9),
    k.internTrivialInt(7),
  ]);

  ok(
    "integer-from-nat-pair: (3,1) ≡ (5,3) [both represent +2]",
    eqNode(v31, v53),
    `${nodeKey(v31)} vs ${nodeKey(v53)}`,
  );
  ok(
    "integer-from-nat-pair: (3,1) ≡ (9,7) [transitivity]",
    eqNode(v31, v97),
  );

  // Negative integer: (1, 3) → diff = -2; (2, 4) → diff = -2 → same NodeID
  const vn13 = intern_quotient_value(k, Q, [
    k.internTrivialInt(1),
    k.internTrivialInt(3),
  ]);
  const vn24 = intern_quotient_value(k, Q, [
    k.internTrivialInt(2),
    k.internTrivialInt(4),
  ]);
  ok(
    "integer-from-nat-pair: (1,3) ≡ (2,4) [both represent -2]",
    eqNode(vn13, vn24),
  );

  // Non-equivalent: +2 vs -2 → DIFFERENT NodeID
  ok(
    "integer-from-nat-pair: +2 ≠ -2 NodeID",
    !eqNode(v31, vn13),
  );

  // quotient_equal helper
  ok(
    "quotient_equal: (3,1) == (5,3) via helper",
    quotient_equal(k, v31, v53),
  );
}

// ---------------------------------------------------------------------------
// Test 3 — Rational-from-int-pair: (2,4) and (1,2) share NodeID
// ---------------------------------------------------------------------------

{
  const k = new Kernel();
  const lib = buildQuotientLibrary(k);
  const carrier = k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.LIST, inst: 0 },
    [],
  );
  const Q = make_quotient_recipe(
    k,
    carrier,
    lib.EQUIV_RATIONAL_FROM_INT_PAIR.nodeID,
  );

  const v24 = intern_quotient_value(k, Q, [
    k.internTrivialInt(2),
    k.internTrivialInt(4),
  ]);
  const v12 = intern_quotient_value(k, Q, [
    k.internTrivialInt(1),
    k.internTrivialInt(2),
  ]);
  const v36 = intern_quotient_value(k, Q, [
    k.internTrivialInt(3),
    k.internTrivialInt(6),
  ]);
  const v_neg2_4 = intern_quotient_value(k, Q, [
    k.internTrivialInt(-2),
    k.internTrivialInt(4),
  ]);
  const v_2_neg4 = intern_quotient_value(k, Q, [
    k.internTrivialInt(2),
    k.internTrivialInt(-4),
  ]);

  ok("rational-from-int-pair: 2/4 ≡ 1/2", eqNode(v24, v12));
  ok("rational-from-int-pair: 3/6 ≡ 1/2 [reduce]", eqNode(v36, v12));
  ok(
    "rational-from-int-pair: -2/4 ≡ 2/-4 [sign normalization]",
    eqNode(v_neg2_4, v_2_neg4),
  );
  ok(
    "rational-from-int-pair: 1/2 ≠ -1/2 NodeID",
    !eqNode(v12, v_neg2_4),
  );
}

// ---------------------------------------------------------------------------
// Test 4 — Commutative-pair: (a,b) ≡ (b,a)
// ---------------------------------------------------------------------------

{
  const k = new Kernel();
  const lib = buildQuotientLibrary(k);
  const carrier = k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.LIST, inst: 0 },
    [],
  );
  const Q = make_quotient_recipe(
    k,
    carrier,
    lib.EQUIV_COMMUTATIVE_PAIR.nodeID,
  );

  const aRaw = k.internTrivialInt(7);
  const bRaw = k.internTrivialInt(42);

  const vab = intern_quotient_value(k, Q, [aRaw, bRaw]);
  const vba = intern_quotient_value(k, Q, [bRaw, aRaw]);

  ok("commutative-pair: (7,42) ≡ (42,7)", eqNode(vab, vba));

  // Different pairs stay distinct.
  const cRaw = k.internTrivialInt(99);
  const vac = intern_quotient_value(k, Q, [aRaw, cRaw]);
  ok("commutative-pair: (7,42) ≠ (7,99) NodeID", !eqNode(vab, vac));
}

// ---------------------------------------------------------------------------
// Test 5 — Round-trip: canonical form decodes back to valid representative
// ---------------------------------------------------------------------------

{
  const k = new Kernel();
  const lib = buildQuotientLibrary(k);
  const carrier = k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.LIST, inst: 0 },
    [],
  );
  const Q = make_quotient_recipe(
    k,
    carrier,
    lib.EQUIV_INTEGER_FROM_NAT_PAIR.nodeID,
  );

  const v = intern_quotient_value(k, Q, [
    k.internTrivialInt(7),
    k.internTrivialInt(2),
  ]);
  const canonical = canonical_form(k, v);
  // canonical's children: [quotient_recipe, canonical-a, canonical-b]
  const kids = k.children(canonical);
  ok(
    "round-trip: canonical form has [quotient, canon-a, canon-b] shape",
    kids.length === 3,
  );
  const ca = k.trivialValue(kids[1]!);
  const cb = k.trivialValue(kids[2]!);
  ok(
    "round-trip: canonical-a == diff (7-2=5)",
    ca.kind === "int" && ca.int === 5,
  );
  ok(
    "round-trip: canonical-b == 0",
    cb.kind === "int" && cb.int === 0,
  );

  // Re-intern from canonical form lands at same NodeID
  const v2 = intern_quotient_value(k, Q, [kids[1]!, kids[2]!]);
  ok("round-trip: canonical re-intern is idempotent", eqNode(v, v2));
}

// ---------------------------------------------------------------------------
// Test 6 — Substrate-cell content-addressing for equivalence-recipes
// ---------------------------------------------------------------------------

{
  const k = new Kernel();
  const a = buildQuotientLibrary(k);
  const b = buildQuotientLibrary(k);
  // Same kernel, same bootstrap → same NodeIDs across calls.
  ok(
    "equivalence cells are content-addressed across calls",
    eqNode(
      a.EQUIV_INTEGER_FROM_NAT_PAIR.nodeID,
      b.EQUIV_INTEGER_FROM_NAT_PAIR.nodeID,
    ),
  );

  // Resolve back from cell NodeID
  const resolved = resolve_equivalence(
    k,
    a.EQUIV_INTEGER_FROM_NAT_PAIR.nodeID,
  );
  ok(
    "resolve_equivalence: round-trips equivalence name",
    resolved.equivalence_name === "integer-from-nat-pair",
  );
  ok(
    "resolve_equivalence: round-trips decidability",
    resolved.decidability === Decidability.DECIDABLE_CHEAP,
  );
}

// ---------------------------------------------------------------------------
// Test 7 — Decidability policy: cheap → EAGER, heavy → LAZY
// ---------------------------------------------------------------------------

{
  const k = new Kernel();
  registerHandler(
    "test-heavy",
    (_k, raw) => raw, // identity for the test
  );
  registerHandler(
    "test-undecidable",
    (_k, raw) => raw,
  );

  const heavy = makeEquivalence(k, {
    equivalence_name: "test-heavy",
    decidability: Decidability.DECIDABLE_HEAVY,
    handler_name: "test-heavy",
  });
  const undec = makeEquivalence(k, {
    equivalence_name: "test-undecidable",
    decidability: Decidability.UNDECIDABLE,
    handler_name: "test-undecidable",
  });

  ok(
    "policy: DECIDABLE_HEAVY → LAZY strategy",
    heavy.strategy === CanonStrategy.LAZY,
  );
  ok(
    "policy: UNDECIDABLE → LAZY strategy",
    undec.strategy === CanonStrategy.LAZY,
  );
  ok(
    "policy: UNDECIDABLE → is_decidable=false",
    !undec.is_decidable,
  );
}

// ---------------------------------------------------------------------------
// Test 8 — Lazy strategy still produces equal canonical forms
// ---------------------------------------------------------------------------

{
  const k = new Kernel();
  registerHandler(
    "lazy-integer-pair",
    (kk, raw) => {
      // Same logic as the eager handler — just registered as heavy.
      const av = kk.trivialValue(raw[0]!);
      const bv = kk.trivialValue(raw[1]!);
      if (av.kind !== "int" || bv.kind !== "int") {
        throw new Error("bad children");
      }
      return [kk.internTrivialInt(av.int - bv.int), kk.internTrivialInt(0)];
    },
  );
  const lazyEq = makeEquivalence(k, {
    equivalence_name: "lazy-integer-pair",
    decidability: Decidability.DECIDABLE_HEAVY,
    handler_name: "lazy-integer-pair",
  });
  const carrier = k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.LIST, inst: 0 },
    [],
  );
  const Q = make_quotient_recipe(k, carrier, lazyEq.nodeID);

  const v31 = intern_quotient_value(k, Q, [
    k.internTrivialInt(3),
    k.internTrivialInt(1),
  ]);
  const v53 = intern_quotient_value(k, Q, [
    k.internTrivialInt(5),
    k.internTrivialInt(3),
  ]);

  // Lazy: raw NodeIDs differ (different inst=3 entries with different children)
  ok("lazy: raw NodeIDs differ pre-canonicalization", !eqNode(v31, v53));
  // But canonical-form merges them
  ok(
    "lazy: canonical_form merges (3,1) and (5,3)",
    eqNode(canonical_form(k, v31), canonical_form(k, v53)),
  );
  ok(
    "lazy: quotient_equal works regardless of strategy",
    quotient_equal(k, v31, v53),
  );
}

// ---------------------------------------------------------------------------
// Test 9 — quotient_parts inspection
// ---------------------------------------------------------------------------

{
  const k = new Kernel();
  const lib = buildQuotientLibrary(k);
  const carrier = k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.LIST, inst: 0 },
    [],
  );
  const Q = make_quotient_recipe(
    k,
    carrier,
    lib.EQUIV_COMMUTATIVE_PAIR.nodeID,
  );

  const parts = quotient_parts(k, Q);
  ok("quotient_parts: extracts carrier", eqNode(parts.carrier, carrier));
  ok(
    "quotient_parts: extracts equivalence",
    eqNode(parts.equivalence, lib.EQUIV_COMMUTATIVE_PAIR.nodeID),
  );
}

// ---------------------------------------------------------------------------
// Test 10 — Handler registry is queryable
// ---------------------------------------------------------------------------

{
  // Force bootstrap by building a library
  const k = new Kernel();
  buildQuotientLibrary(k);
  ok(
    "registry: integer-from-nat-pair handler registered",
    getHandler("integer-from-nat-pair") !== undefined,
  );
  ok(
    "registry: unknown handler returns undefined",
    getHandler("does-not-exist") === undefined,
  );
}

// ---------------------------------------------------------------------------
// Summary
// ---------------------------------------------------------------------------

console.log("");
console.log(`Results: ${passes} passed, ${failures} failed`);
if (failures > 0) process.exit(1);
