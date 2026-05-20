// observer.test.ts — observer-relative canonicalization (task #27).
//
// Two observers, same input, different canonical NodeIDs because they
// carry different active quotients. The underlying value-relations are
// preserved: both observers see the same raw children go in, and the
// canonicalize functions are pure (deterministic given the input).
//
// Run: tsx src/observer.test.ts

import {
  Kernel,
  Level,
  RBasic,
  nodeKey,
  type NodeID,
} from "./kernel.ts";
import {
  makeObserver,
  makeQuotient,
  internAs,
  canonicalForObserver,
  type CanonicalizeFn,
} from "./observer.ts";

let failures = 0;

function check(label: string, cond: boolean, detail = ""): void {
  if (cond) {
    process.stdout.write(`  ok   ${label}\n`);
  } else {
    failures++;
    process.stdout.write(`  FAIL ${label}${detail ? " — " + detail : ""}\n`);
  }
}

function nodesEqual(a: NodeID, b: NodeID): boolean {
  return (
    a.pkg === b.pkg &&
    a.level === b.level &&
    a.type === b.type &&
    a.inst === b.inst
  );
}

// ---------------------------------------------------------------------------
// Test setup — a category for "pair" values + two quotients.
//
// commutative: sort children by their packed NodeID key so (a,b) and (b,a)
//   collapse to the same canonical tuple.
//
// identity-right: drop a trailing identity element. Here we use the int
//   trivial 0 as the identity (matches PLUS's right-identity in the
//   symmetry doc).
// ---------------------------------------------------------------------------

const k = new Kernel();

// A test category — reuse RBasic.LIST so we don't need a new slot.
const CAT: NodeID = {
  pkg: 1,
  level: Level.BASIC,
  type: RBasic.LIST,
  inst: 99, // distinct from observer.ts's inner LIST inst
};

const ZERO = k.internTrivialInt(0);
const ONE = k.internTrivialInt(1);
const TWO = k.internTrivialInt(2);
const THREE = k.internTrivialInt(3);

function nodeOrderKey(n: NodeID): string {
  return `${n.pkg}.${n.level}.${n.type}.${n.inst}`;
}

const commutativeSort: CanonicalizeFn = (_k, raw) => {
  const sorted = raw.slice().sort((a, b) =>
    nodeOrderKey(a).localeCompare(nodeOrderKey(b)),
  );
  return sorted;
};

const dropTrailingZero: CanonicalizeFn = (_k, raw) => {
  const out = raw.slice();
  while (out.length > 0) {
    const last = out[out.length - 1]!;
    if (
      last.level === Level.TRIVIAL &&
      last.type === ZERO.type &&
      last.inst === ZERO.inst
    ) {
      out.pop();
    } else {
      break;
    }
  }
  return out;
};

const Q_COMMUTATIVE = makeQuotient(k, "test-commutative-sort", commutativeSort);
const Q_IDENTITY = makeQuotient(k, "test-drop-trailing-zero", dropTrailingZero);

// ---------------------------------------------------------------------------
// Observer A — empty active set. Sees raw structure.
// Observer B — { commutative }. Sees order-insensitive structure.
// Observer C — { commutative, drop-trailing-zero }. Sees both reductions.
// ---------------------------------------------------------------------------

const obsA = makeObserver(k, "alice-raw", []);
const obsB = makeObserver(k, "bob-commutative", [Q_COMMUTATIVE.nodeID]);
const obsC = makeObserver(k, "carol-both", [
  Q_COMMUTATIVE.nodeID,
  Q_IDENTITY.nodeID,
]);

process.stdout.write("observer cells are substrate-resident\n");

check(
  "obsA has a NodeID",
  obsA.nodeID.level === Level.BASIC && obsA.nodeID.type === RBasic.OBSERVER,
);
check(
  "obsB has a NodeID",
  obsB.nodeID.level === Level.BASIC && obsB.nodeID.type === RBasic.OBSERVER,
);
check(
  "obsC has a NodeID",
  obsC.nodeID.level === Level.BASIC && obsC.nodeID.type === RBasic.OBSERVER,
);
check(
  "observers with different active sets have different NodeIDs",
  !nodesEqual(obsA.nodeID, obsB.nodeID) &&
    !nodesEqual(obsB.nodeID, obsC.nodeID) &&
    !nodesEqual(obsA.nodeID, obsC.nodeID),
);
check(
  "observer NodeIDs are deterministic — same name + active set re-interns to same NodeID",
  nodesEqual(
    obsB.nodeID,
    makeObserver(k, "bob-commutative", [Q_COMMUTATIVE.nodeID]).nodeID,
  ),
);

// ---------------------------------------------------------------------------
// Core claim: same input, different canonical NodeIDs per observer.
// ---------------------------------------------------------------------------

process.stdout.write("\nsame input ⇒ different canonical NodeIDs per observer\n");

// Same input: (TWO, ONE) — a pair where order matters to A but not to B/C.
const inA = internAs(k, obsA, CAT, [TWO, ONE]);
const inB = internAs(k, obsB, CAT, [TWO, ONE]);
const inC = internAs(k, obsC, CAT, [TWO, ONE]);

check(
  "observer A interns (TWO, ONE) — raw order preserved",
  !nodesEqual(inA, inB) || !nodesEqual(inA, inC),
  `A=${nodeKey(inA)} B=${nodeKey(inB)} C=${nodeKey(inC)}`,
);
// A and B should differ because B sorts: (ONE, TWO) ≠ raw (TWO, ONE).
check(
  "A (raw) and B (sort) give different canonical NodeIDs for (TWO, ONE)",
  !nodesEqual(inA, inB),
  `A=${nodeKey(inA)} vs B=${nodeKey(inB)}`,
);

// Same input again — (ONE, TWO). Under B this collapses with (TWO, ONE).
const inA_swapped = internAs(k, obsA, CAT, [ONE, TWO]);
const inB_swapped = internAs(k, obsB, CAT, [ONE, TWO]);

check(
  "observer A: (TWO, ONE) and (ONE, TWO) are DIFFERENT (order matters to A)",
  !nodesEqual(inA, inA_swapped),
);
check(
  "observer B: (TWO, ONE) and (ONE, TWO) are the SAME (commutative collapse)",
  nodesEqual(inB, inB_swapped),
);

// ---------------------------------------------------------------------------
// Quotient stacking: C applies commutative THEN drop-trailing-zero.
// (THREE, ZERO) → commutative-sort → (ZERO, THREE) → drop-trailing-zero
// does NOT pop ZERO (it's leading, not trailing). So C sees (ZERO, THREE).
// (ZERO, THREE) and (THREE, ZERO) collapse to the same NodeID under C.
// ---------------------------------------------------------------------------

process.stdout.write("\nquotient stacking on observer C\n");

const c1 = internAs(k, obsC, CAT, [THREE, ZERO]);
const c2 = internAs(k, obsC, CAT, [ZERO, THREE]);
check(
  "observer C: (THREE, ZERO) and (ZERO, THREE) collapse under commutative+identity",
  nodesEqual(c1, c2),
  `c1=${nodeKey(c1)} c2=${nodeKey(c2)}`,
);

// Observer D: identity-only — strips a trailing ZERO. (THREE, ZERO) → (THREE,).
const obsD = makeObserver(k, "dave-identity-only", [Q_IDENTITY.nodeID]);
const d_with_zero = internAs(k, obsD, CAT, [THREE, ZERO]);
const d_without = internAs(k, obsD, CAT, [THREE]);
check(
  "observer D: (THREE, ZERO) and (THREE) collapse under drop-trailing-zero",
  nodesEqual(d_with_zero, d_without),
);
check(
  "observer A: (THREE, ZERO) and (THREE) DO NOT collapse (raw)",
  !nodesEqual(
    internAs(k, obsA, CAT, [THREE, ZERO]),
    internAs(k, obsA, CAT, [THREE]),
  ),
);

// ---------------------------------------------------------------------------
// canonicalForObserver: re-canonicalize an existing node under a different
// observer. The underlying relations (raw children) are observer-
// independent; the canonical form is observer-indexed.
// ---------------------------------------------------------------------------

process.stdout.write(
  "\ncanonicalForObserver — same source node, different canonical NodeID per observer\n",
);

const source = internAs(k, obsA, CAT, [TWO, ONE]);
const sourceUnderA = canonicalForObserver(k, obsA, source);
const sourceUnderB = canonicalForObserver(k, obsB, source);
check(
  "canonicalForObserver(A, source) returns the source itself (A is empty-quotient)",
  nodesEqual(sourceUnderA, source),
);
check(
  "canonicalForObserver(B, source) differs from source (commutative sort applies)",
  !nodesEqual(sourceUnderB, source),
);
check(
  "canonicalForObserver(B, source) equals what B would have interned directly",
  nodesEqual(sourceUnderB, internAs(k, obsB, CAT, [TWO, ONE])),
);

// Trivials are their own canonical form regardless of observer.
const trivialUnderA = canonicalForObserver(k, obsA, TWO);
const trivialUnderC = canonicalForObserver(k, obsC, TWO);
check(
  "trivial NodeIDs are observer-independent (TWO is TWO for everyone)",
  nodesEqual(trivialUnderA, TWO) && nodesEqual(trivialUnderC, TWO),
);

// ---------------------------------------------------------------------------
// Invariant: underlying value-relations preserved across observers.
//
// The raw inputs and the canonicalize functions are pure; running the
// same canonicalize_fn on the same input always returns the same output.
// Two different observers that happen to share an active quotient set
// (modulo name) produce the same canonical form for the same input.
// ---------------------------------------------------------------------------

process.stdout.write("\nunderlying relations are observer-independent\n");

const obsB2 = makeObserver(k, "bob-prime", [Q_COMMUTATIVE.nodeID]);
check(
  "two observers with same active-quotient list produce identical canonical NodeIDs",
  nodesEqual(
    internAs(k, obsB, CAT, [THREE, ONE]),
    internAs(k, obsB2, CAT, [THREE, ONE]),
  ),
);

// ---------------------------------------------------------------------------
// Summary
// ---------------------------------------------------------------------------

process.stdout.write(
  `\n${failures === 0 ? "PASS" : "FAIL"} — ${failures} failure${failures === 1 ? "" : "s"}\n`,
);
process.exit(failures === 0 ? 0 : 1);
