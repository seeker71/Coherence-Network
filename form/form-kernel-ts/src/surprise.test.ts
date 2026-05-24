// surprise.test.ts — runnable test suite for free-energy-aware intern.
//
//   tsx src/surprise.test.ts
//
// Verifies the foundation doc §5 contract: intern proceeds, surprise is
// recorded as metric on the resulting NodeID, persistent high-surprise points
// at regions where the generative model is wrong.

import {
  Kernel,
  Level,
  RBasic,
  RBlock,
  Triv,
  nodeKey,
  NodeID,
} from "./kernel.ts";
import { makeGenerativeModel } from "./generative.ts";
import {
  internWithSurprise,
  internWithSurpriseAgainst,
  surpriseMetricsFor,
  mostSurprising,
  refineModelFromSurprise,
  allSurpriseRecords,
  clearSurpriseRegistry,
} from "./surprise.ts";

let pass = 0;
let fail = 0;

function check(name: string, cond: boolean, detail?: string): void {
  if (cond) {
    pass++;
    process.stdout.write(`  ok  ${name}\n`);
  } else {
    fail++;
    process.stdout.write(`  FAIL  ${name}${detail ? ` — ${detail}` : ""}\n`);
  }
}

// ---------------------------------------------------------------------------
// Test helpers — borrowed from generative.test.ts so the suites parallel
// ---------------------------------------------------------------------------

const LIST_CAT: NodeID = {
  pkg: 1,
  level: Level.BASIC,
  type: RBasic.LIST,
  inst: 0,
};

function makeCell(k: Kernel, marker: number): NodeID {
  return k.intern(LIST_CAT, [k.internTrivialInt(marker)]);
}

function makeSensoryShape(k: Kernel, label: string): NodeID {
  // Same shape as makeCell — LIST with one trivial child. Used so the test
  // cell's expected[] list is the same recipe-family as the values we'll
  // intern, exercising the "same-shape, different content" branch of
  // surpriseScore.
  return k.intern(LIST_CAT, [k.internString(label)]);
}

function makeIdentityFn(k: Kernel, fnName: string, paramName: string): NodeID {
  const nameTriv: NodeID = {
    pkg: 1,
    level: Level.TRIVIAL,
    type: Triv.STRING,
    inst: k.internName(fnName),
  };
  const paramTriv: NodeID = {
    pkg: 1,
    level: Level.TRIVIAL,
    type: Triv.STRING,
    inst: k.internName(paramName),
  };
  const paramsBlock = k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.BLOCK, inst: RBlock.SEQUENCE },
    [paramTriv],
  );
  const body = k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.IDENT, inst: 1 },
    [paramTriv],
  );
  return k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.FNDEF, inst: 1 },
    [nameTriv, paramsBlock, body],
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

function testMatchingInputsLowSurprise(): void {
  process.stdout.write("\n# matching inputs — surprise = 0\n");
  const k = new Kernel();
  const cell = makeCell(k, 1);
  const expectedA = makeSensoryShape(k, "ping");
  const expectedB = makeSensoryShape(k, "pong");
  const fn = makeIdentityFn(k, "id-fn", "s");

  makeGenerativeModel(k, cell, [expectedA, expectedB], [], fn);

  // Re-intern one of the expected nodes through internWithSurprise. The
  // resulting NodeID is the same one (content-addressing), and the recorded
  // surprise should be 0.
  const node = internWithSurprise(k, cell, LIST_CAT, [k.internString("ping")]);
  check(
    "intern returns the same NodeID as expected (content-addressed)",
    nodeKey(node) === nodeKey(expectedA),
  );

  const rec = surpriseMetricsFor(k, node);
  check(
    "surprise recorded as 0 for a known-shape known-content node",
    rec !== null && rec.score === 0,
    rec === null ? "no record" : `score=${rec.score}`,
  );
  check(
    "surprise record carries the cell that interned",
    rec !== null && nodeKey(rec.cell) === nodeKey(cell),
  );
}

function testMismatchedInputsHighSurprise(): void {
  process.stdout.write("\n# mismatched inputs — surprise > 0\n");
  const k = new Kernel();
  const cell = makeCell(k, 2);
  const expectedA = makeSensoryShape(k, "alpha");
  const fn = makeIdentityFn(k, "id-fn-2", "s");
  makeGenerativeModel(k, cell, [expectedA], [], fn);

  // Same shape (LIST + one string child) but different content — small surprise.
  const sameShape = internWithSurprise(k, cell, LIST_CAT, [
    k.internString("novel"),
  ]);
  const recSame = surpriseMetricsFor(k, sameShape);
  check(
    "same-shape novel content records surprise=1",
    recSame !== null && recSame.score === 1,
    recSame === null ? "no record" : `score=${recSame.score}`,
  );

  // Completely different category — high surprise.
  // Intern a CONSTRUCTOR-shaped node (different category from LIST) via the
  // surprise wrapper. We use a bare-int "trivial" node directly since the
  // surpriseScore function handles non-LIST categories with a large bound.
  const bareInt = k.internTrivialInt(42);
  // Re-record by calling internWithSurprise on an unrelated-category node.
  // Easiest path: build a CONSTRUCTOR-shaped recipe that's never been in expected.
  const ctorCat: NodeID = {
    pkg: 1,
    level: Level.BASIC,
    type: RBasic.CONSTRUCTOR,
    inst: 0,
  };
  const farNode = internWithSurprise(k, cell, ctorCat, [bareInt]);
  const recFar = surpriseMetricsFor(k, farNode);
  check(
    "unrelated-category node records high surprise (>= 10)",
    recFar !== null && recFar.score >= 10,
    recFar === null ? "no record" : `score=${recFar.score}`,
  );
}

function testNoModelNoRecord(): void {
  process.stdout.write("\n# no model registered — no record\n");
  const k = new Kernel();
  const cell = makeCell(k, 3);
  // Deliberately no makeGenerativeModel call.

  const node = internWithSurprise(k, cell, LIST_CAT, [k.internString("any")]);
  check(
    "internWithSurprise without a model still interns the node",
    node !== null && node !== undefined,
  );
  check(
    "no surprise recorded when cell has no generative model",
    surpriseMetricsFor(k, node) === null,
  );
}

function testMostSurprisingReturnsHighest(): void {
  process.stdout.write("\n# mostSurprising — top-N highest scores\n");
  const k = new Kernel();
  const cell = makeCell(k, 4);
  const expected = makeSensoryShape(k, "match");
  const fn = makeIdentityFn(k, "fn-most", "s");
  makeGenerativeModel(k, cell, [expected], [], fn);

  // Three interns: one matching (surprise=0), one same-shape novel
  // (surprise=1), one far-category (surprise=10+).
  const matched = internWithSurprise(k, cell, LIST_CAT, [
    k.internString("match"),
  ]);
  const novel = internWithSurprise(k, cell, LIST_CAT, [
    k.internString("novel-1"),
  ]);
  const ctorCat: NodeID = {
    pkg: 1,
    level: Level.BASIC,
    type: RBasic.CONSTRUCTOR,
    inst: 0,
  };
  const far = internWithSurprise(k, cell, ctorCat, [k.internTrivialInt(7)]);

  check(
    "allSurpriseRecords reports 3 distinct observations",
    allSurpriseRecords(k).length === 3,
    `got ${allSurpriseRecords(k).length}`,
  );

  const top2 = mostSurprising(k, 2);
  check("mostSurprising returns 2 records", top2.length === 2);
  check(
    "first result is the unrelated-category node (highest surprise)",
    top2[0] !== undefined && nodeKey(top2[0].node) === nodeKey(far),
    top2[0] === undefined ? "no record" : `got ${nodeKey(top2[0].node)} score=${top2[0].score}`,
  );
  check(
    "second result is the same-shape novel node",
    top2[1] !== undefined && nodeKey(top2[1].node) === nodeKey(novel),
  );
  check(
    "matched node not in top-2 (it had surprise=0)",
    !top2.some((r) => nodeKey(r.node) === nodeKey(matched)),
  );

  // top_n clamps gracefully
  check(
    "mostSurprising with top_n > observations returns all",
    mostSurprising(k, 100).length === 3,
  );
  check("mostSurprising with top_n <= 0 returns empty", mostSurprising(k, 0).length === 0);
}

function testRefineModelSuggests(): void {
  process.stdout.write("\n# refineModelFromSurprise — heuristic refinement\n");
  const k = new Kernel();
  const cell = makeCell(k, 5);
  const expected = makeSensoryShape(k, "known");
  const fn = makeIdentityFn(k, "fn-refine", "s");
  makeGenerativeModel(k, cell, [expected], [], fn);

  // No observations → null
  check(
    "refineModelFromSurprise returns null before any observations",
    refineModelFromSurprise(k, cell) === null,
  );

  // One observation isn't enough signal
  internWithSurprise(k, cell, LIST_CAT, [k.internString("novel-a")]);
  check(
    "single observation isn't enough — still null",
    refineModelFromSurprise(k, cell) === null,
  );

  // Two same-shape novel observations → mean=1, suggestion fires
  internWithSurprise(k, cell, LIST_CAT, [k.internString("novel-b")]);
  const r1 = refineModelFromSurprise(k, cell);
  check(
    "two same-shape novel observations yield a refinement proposal",
    r1 !== null,
  );
  check(
    "proposal's meanSurprise reflects the observations",
    r1 !== null && r1.meanSurprise === 1,
    r1 === null ? "no proposal" : `mean=${r1.meanSurprise}`,
  );
  check(
    "proposal suggests 2 distinct novel shapes to add to expected[]",
    r1 !== null && r1.highSurpriseNodes.length === 2,
  );
  check(
    "suggestExpected is non-empty",
    r1 !== null && r1.suggestExpected.length > 0,
  );

  // After matching observations the mean drops; with enough matches the
  // refinement should drop to null (model is predicting well on average).
  // We add 10 matching interns to weight the mean down.
  for (let i = 0; i < 10; i++) {
    internWithSurprise(k, cell, LIST_CAT, [k.internString("known")]);
  }
  const r2 = refineModelFromSurprise(k, cell);
  check(
    "after 10 matching observations, mean drops below 1 and refinement returns null",
    r2 === null,
  );
}

function testRefineRespectsTopThree(): void {
  process.stdout.write("\n# refineModelFromSurprise — caps suggestExpected at 3\n");
  const k = new Kernel();
  const cell = makeCell(k, 6);
  const expected = makeSensoryShape(k, "anchor");
  const fn = makeIdentityFn(k, "fn-cap", "s");
  makeGenerativeModel(k, cell, [expected], [], fn);

  // Five distinct same-shape novel interns → all surprise=1, all distinct.
  for (let i = 0; i < 5; i++) {
    internWithSurprise(k, cell, LIST_CAT, [k.internString(`novel-${i}`)]);
  }
  const r = refineModelFromSurprise(k, cell);
  check("refinement non-null for 5 same-shape novel interns", r !== null);
  check(
    "highSurpriseNodes contains all 5 distinct shapes",
    r !== null && r.highSurpriseNodes.length === 5,
    r === null ? "" : `got ${r.highSurpriseNodes.length}`,
  );
  check(
    "suggestExpected capped at 3",
    r !== null && r.suggestExpected.length === 3,
    r === null ? "" : `got ${r.suggestExpected.length}`,
  );
  check(
    "rationale is non-empty",
    r !== null && r.rationale.length > 0,
  );
}

function testInternWithSurpriseAgainst(): void {
  process.stdout.write("\n# internWithSurpriseAgainst — explicit model\n");
  const k = new Kernel();
  const cell = makeCell(k, 7);
  const expected = makeSensoryShape(k, "exp");
  const fn = makeIdentityFn(k, "fn-ag", "s");
  const model = makeGenerativeModel(k, cell, [expected], [], fn);

  // Intern the expected shape against the explicit model — surprise = 0.
  const { node, score } = internWithSurpriseAgainst(
    k,
    cell,
    model,
    LIST_CAT,
    [k.internString("exp")],
  );
  check(
    "expected shape against explicit model — score 0",
    score === 0 && nodeKey(node) === nodeKey(expected),
    `score=${score}`,
  );

  // Novel shape against explicit model — surprise = 1
  const r2 = internWithSurpriseAgainst(
    k,
    cell,
    model,
    LIST_CAT,
    [k.internString("ag-novel")],
  );
  check(
    "novel shape against explicit model — score 1",
    r2.score === 1,
    `score=${r2.score}`,
  );
  check(
    "internWithSurpriseAgainst also records into the registry",
    surpriseMetricsFor(k, r2.node)?.score === 1,
  );
}

function testClearRegistry(): void {
  process.stdout.write("\n# clearSurpriseRegistry — fresh slate\n");
  const k = new Kernel();
  const cell = makeCell(k, 8);
  const expected = makeSensoryShape(k, "clear");
  const fn = makeIdentityFn(k, "fn-clear", "s");
  makeGenerativeModel(k, cell, [expected], [], fn);
  internWithSurprise(k, cell, LIST_CAT, [k.internString("first")]);
  check(
    "record present before clear",
    allSurpriseRecords(k).length === 1,
  );
  clearSurpriseRegistry(k);
  check(
    "record gone after clear",
    allSurpriseRecords(k).length === 0,
  );
  check(
    "surpriseMetricsFor returns null after clear",
    surpriseMetricsFor(k, makeSensoryShape(k, "first")) === null,
  );
}

function main(): void {
  process.stdout.write("# surprise.test.ts\n");
  testMatchingInputsLowSurprise();
  testMismatchedInputsHighSurprise();
  testNoModelNoRecord();
  testMostSurprisingReturnsHighest();
  testRefineModelSuggests();
  testRefineRespectsTopThree();
  testInternWithSurpriseAgainst();
  testClearRegistry();

  process.stdout.write(`\nresults: ${pass} ok, ${fail} fail\n`);
  if (fail > 0) process.exit(1);
}

main();
