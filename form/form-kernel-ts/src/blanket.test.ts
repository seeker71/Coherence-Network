// blanket.test.ts — contract for Markov blanket recipes.
//
// Runs under `tsx src/blanket.test.ts`. Self-contained: prints PASS/FAIL per
// case and exits non-zero on any failure. No external test runner needed
// (matches the conformance.ts pattern already in this package).

import { Kernel, Level, RBasic, nodeKey, type NodeID } from "./kernel.ts";
import {
  asBlanket,
  activeFrom,
  blanketOf,
  cellOf,
  coversAll,
  exposedFrom,
  internalFrom,
  makeBlanket,
  sensoryFrom,
  unionBlankets,
} from "./blanket.ts";

// ---------------------------------------------------------------------------
// Tiny assert harness
// ---------------------------------------------------------------------------

let passed = 0;
let failed = 0;

function check(label: string, cond: boolean, detail?: string): void {
  if (cond) {
    passed++;
    process.stdout.write(`  PASS  ${label}\n`);
  } else {
    failed++;
    process.stdout.write(
      `  FAIL  ${label}${detail ? `\n        ${detail}` : ""}\n`,
    );
  }
}

function nidEq(a: NodeID, b: NodeID): boolean {
  return (
    a.pkg === b.pkg &&
    a.level === b.level &&
    a.type === b.type &&
    a.inst === b.inst
  );
}

function sortedKeys(ns: readonly NodeID[]): string[] {
  return ns.map(nodeKey).slice().sort();
}

// Build a small toy cell NodeID. The kernel doesn't care what RBasic.LIST is
// "really" — we just need a stable composite NodeID to stand in for "a cell".
function makeCellLike(k: Kernel, name: string): NodeID {
  const tag = k.internString(name);
  return k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.LIST, inst: 0 },
    [tag],
  );
}

function trivInt(k: Kernel, n: number): NodeID {
  return k.internTrivialInt(n);
}

// ---------------------------------------------------------------------------
// Test 1 — basic declaration + accessors
// ---------------------------------------------------------------------------

process.stdout.write("test: basic declaration + accessors\n");
{
  const k = new Kernel();
  const cell = makeCellLike(k, "cell-a");

  const e1 = trivInt(k, 100);
  const e2 = trivInt(k, 101);
  const i1 = trivInt(k, 200);
  const s1 = trivInt(k, 300);
  const a1 = trivInt(k, 400);
  const a2 = trivInt(k, 401);

  const b = makeBlanket(k, cell, [e1, e2], [i1], [s1], [a1, a2]);

  check(
    "blanket node is BLANKET category",
    b.node.type === RBasic.BLANKET && b.node.level === Level.BASIC,
  );
  check("cellOf returns the original cell", nidEq(cellOf(k, b), cell));
  check(
    "exposedFrom returns 2 items in order",
    exposedFrom(k, b).length === 2 &&
      nidEq(exposedFrom(k, b)[0]!, e1) &&
      nidEq(exposedFrom(k, b)[1]!, e2),
  );
  check(
    "internalFrom returns 1 item",
    internalFrom(k, b).length === 1 && nidEq(internalFrom(k, b)[0]!, i1),
  );
  check(
    "sensoryFrom returns 1 item",
    sensoryFrom(k, b).length === 1 && nidEq(sensoryFrom(k, b)[0]!, s1),
  );
  check(
    "activeFrom returns 2 items in order",
    activeFrom(k, b).length === 2 &&
      nidEq(activeFrom(k, b)[0]!, a1) &&
      nidEq(activeFrom(k, b)[1]!, a2),
  );

  // blanketOf round-trip
  const looked = blanketOf(k, cell);
  check(
    "blanketOf finds the cell's blanket",
    looked !== undefined && nidEq(looked.node, b.node),
  );

  // asBlanket validation
  const viewed = asBlanket(k, b.node);
  check("asBlanket validates and returns same node", nidEq(viewed.node, b.node));
}

// ---------------------------------------------------------------------------
// Test 2 — content-addressing: same shape ⇒ same NodeID
// ---------------------------------------------------------------------------

process.stdout.write("test: content-addressing\n");
{
  const k = new Kernel();
  const cell = makeCellLike(k, "cell-b");

  const e1 = trivInt(k, 1);
  const i1 = trivInt(k, 2);
  const s1 = trivInt(k, 3);
  const a1 = trivInt(k, 4);

  const b1 = makeBlanket(k, cell, [e1], [i1], [s1], [a1]);
  const b2 = makeBlanket(k, cell, [e1], [i1], [s1], [a1]);

  check("same shape ⇒ same NodeID", nidEq(b1.node, b2.node));

  // Different cell ⇒ different NodeID
  const cell2 = makeCellLike(k, "cell-c");
  const b3 = makeBlanket(k, cell2, [e1], [i1], [s1], [a1]);
  check("different cell ⇒ different NodeID", !nidEq(b1.node, b3.node));

  // Different boundary content ⇒ different NodeID
  const b4 = makeBlanket(k, cell, [e1, i1], [], [s1], [a1]);
  check("different boundary content ⇒ different NodeID", !nidEq(b1.node, b4.node));

  // Order matters in the per-channel list (sensory channels often ordered).
  const eA = trivInt(k, 10);
  const eB = trivInt(k, 11);
  const ordered1 = makeBlanket(k, cell, [eA, eB], [], [], []);
  const ordered2 = makeBlanket(k, cell, [eB, eA], [], [], []);
  check(
    "order is significant within a channel",
    !nidEq(ordered1.node, ordered2.node),
  );
}

// ---------------------------------------------------------------------------
// Test 3 — coversAll
// ---------------------------------------------------------------------------

process.stdout.write("test: coversAll\n");
{
  const k = new Kernel();
  const cell = makeCellLike(k, "cell-d");

  const x1 = trivInt(k, 50);
  const x2 = trivInt(k, 51);
  const x3 = trivInt(k, 52);
  const x4 = trivInt(k, 53);
  const orphan = trivInt(k, 99);

  const b = makeBlanket(k, cell, [x1], [x2], [x3], [x4]);

  check(
    "coversAll: all listed NodeIDs are covered",
    coversAll(k, b, [x1, x2, x3, x4]),
  );
  check(
    "coversAll: empty touched set is trivially covered",
    coversAll(k, b, []),
  );
  check(
    "coversAll: an unlisted NodeID is not covered",
    !coversAll(k, b, [x1, orphan]),
  );
}

// ---------------------------------------------------------------------------
// Test 4 — unionBlankets: commutative + associative under content-addressing
// ---------------------------------------------------------------------------

process.stdout.write("test: unionBlankets algebra\n");
{
  const k = new Kernel();
  const cellA = makeCellLike(k, "cell-A");
  const cellB = makeCellLike(k, "cell-B");
  const cellC = makeCellLike(k, "cell-C");
  const composite = makeCellLike(k, "cell-AB");
  const composite3 = makeCellLike(k, "cell-ABC");

  const eA = trivInt(k, 10);
  const eB = trivInt(k, 20);
  const eC = trivInt(k, 30);
  const iA = trivInt(k, 11);
  const iB = trivInt(k, 21);
  const iC = trivInt(k, 31);
  const sA = trivInt(k, 12);
  const sB = trivInt(k, 22);
  const sC = trivInt(k, 32);
  const aA = trivInt(k, 13);
  const aB = trivInt(k, 23);
  const aC = trivInt(k, 33);

  const ba = makeBlanket(k, cellA, [eA], [iA], [sA], [aA]);
  const bb = makeBlanket(k, cellB, [eB], [iB], [sB], [aB]);
  const bc = makeBlanket(k, cellC, [eC], [iC], [sC], [aC]);

  // Commutativity: union(ba, bb) ≡ union(bb, ba)
  const uAB = unionBlankets(k, composite, ba, bb);
  const uBA = unionBlankets(k, composite, bb, ba);
  check(
    "commutative: union(a,b).node === union(b,a).node",
    nidEq(uAB.node, uBA.node),
  );

  // Spot-check: the union contains both sides' exposed items, deduped.
  const expExposed = new Set([nodeKey(eA), nodeKey(eB)]);
  const gotExposed = new Set(exposedFrom(k, uAB).map(nodeKey));
  check(
    "union covers both exposed sets",
    expExposed.size === gotExposed.size &&
      [...expExposed].every((s) => gotExposed.has(s)),
  );

  // Dedup: union of a blanket with itself yields the same boundary.
  const uAA = unionBlankets(k, composite, ba, ba);
  check(
    "idempotent on identical inputs (sorted dedup canonical form)",
    JSON.stringify(sortedKeys(exposedFrom(k, uAA))) ===
      JSON.stringify(sortedKeys(exposedFrom(k, ba))) &&
      JSON.stringify(sortedKeys(internalFrom(k, uAA))) ===
        JSON.stringify(sortedKeys(internalFrom(k, ba))),
  );

  // Associativity: union(union(a,b), c) ≡ union(a, union(b,c))
  //
  // Two structurally-identical compositions land on the same NodeID via
  // intern: the canonical sort order in unionBlankets ensures the inner
  // result has the same shape regardless of which side absorbed which.
  const left = unionBlankets(k, composite3, uAB, bc);
  const uBC = unionBlankets(k, composite, bb, bc);
  const right = unionBlankets(k, composite3, ba, uBC);
  check("associative: (a∪b)∪c.node === a∪(b∪c).node", nidEq(left.node, right.node));
}

// ---------------------------------------------------------------------------
// Test 5 — registry isolation per kernel
// ---------------------------------------------------------------------------

process.stdout.write("test: registry isolation\n");
{
  const k1 = new Kernel();
  const k2 = new Kernel();
  // Construct a NodeID that exists in both kernels by the same numeric
  // identity (trivial ints are pkg=1/level=1/type=1/inst=N — kernel-agnostic).
  const cell = k1.internTrivialInt(7);

  const b = makeBlanket(k1, cell, [], [], [], []);
  check("k1 sees its own blanket", blanketOf(k1, cell)?.node !== undefined);
  check(
    "k2 does NOT see k1's blanket (registry per-kernel)",
    blanketOf(k2, cell) === undefined,
  );
  // Avoid unused-var lint on b
  void b;
}

// ---------------------------------------------------------------------------
// Summary
// ---------------------------------------------------------------------------

process.stdout.write(`\n${passed} passed, ${failed} failed\n`);
if (failed > 0) process.exit(1);
