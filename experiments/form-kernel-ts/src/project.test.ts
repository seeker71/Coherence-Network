// Tests for the holographic PROJECT operation.
//
// Run:  npx tsx src/project.test.ts
//
// No external test runner — small, self-contained assertions so the file
// runs cleanly in any kernel-conformance harness later.

import {
  Kernel,
  Level,
  RBasic,
  RMath,
  RBlock,
  type NodeID,
  nodeKey,
} from "./kernel.js";
import {
  compositionalDepth,
  projectDown,
  projectUp,
  makeProjection,
  structuralShape,
  findContainer,
  findAllContainers,
} from "./project.js";

let failures = 0;
let passes = 0;

function eq(actual: unknown, expected: unknown, msg: string): void {
  const ok = JSON.stringify(actual) === JSON.stringify(expected);
  if (ok) {
    passes++;
    process.stdout.write(`  ok  ${msg}\n`);
  } else {
    failures++;
    process.stdout.write(
      `  FAIL  ${msg}\n        actual=${JSON.stringify(actual)}\n        expected=${JSON.stringify(expected)}\n`,
    );
  }
}

function assert(cond: boolean, msg: string): void {
  if (cond) {
    passes++;
    process.stdout.write(`  ok  ${msg}\n`);
  } else {
    failures++;
    process.stdout.write(`  FAIL  ${msg}\n`);
  }
}

// ---------------------------------------------------------------------------
// Builders — construct a small, nested level-5 cell for testing
// ---------------------------------------------------------------------------

function mathCat(op: number): NodeID {
  return { pkg: 1, level: Level.BASIC, type: RBasic.MATH, inst: op };
}

function blockCat(op: number): NodeID {
  return { pkg: 1, level: Level.BASIC, type: RBasic.BLOCK, inst: op };
}

// Build:  (do (+ (+ 1 2) (+ 3 4)) (* 5 6))
// Depth:  DO -> MATH(+) -> MATH(+) -> int (4 levels with leaves)
function buildNestedCell(k: Kernel): NodeID {
  const i1 = k.internTrivialInt(1);
  const i2 = k.internTrivialInt(2);
  const i3 = k.internTrivialInt(3);
  const i4 = k.internTrivialInt(4);
  const i5 = k.internTrivialInt(5);
  const i6 = k.internTrivialInt(6);

  const innerAdd1 = k.intern(mathCat(RMath.PLUS), [i1, i2]); // depth 2
  const innerAdd2 = k.intern(mathCat(RMath.PLUS), [i3, i4]); // depth 2
  const outerAdd = k.intern(mathCat(RMath.PLUS), [innerAdd1, innerAdd2]); // depth 3
  const mul = k.intern(mathCat(RMath.MUL), [i5, i6]); // depth 2
  const root = k.intern(blockCat(RBlock.DO), [outerAdd, mul]); // depth 4
  return root;
}

// Build the same structural shape with different values
function buildIsomorphicCell(k: Kernel): NodeID {
  const i7 = k.internTrivialInt(7);
  const i8 = k.internTrivialInt(8);
  const i9 = k.internTrivialInt(9);
  const i10 = k.internTrivialInt(10);
  const i11 = k.internTrivialInt(11);
  const i12 = k.internTrivialInt(12);

  const innerAdd1 = k.intern(mathCat(RMath.PLUS), [i7, i8]);
  const innerAdd2 = k.intern(mathCat(RMath.PLUS), [i9, i10]);
  const outerAdd = k.intern(mathCat(RMath.PLUS), [innerAdd1, innerAdd2]);
  const mul = k.intern(mathCat(RMath.MUL), [i11, i12]);
  return k.intern(blockCat(RBlock.DO), [outerAdd, mul]);
}

// Build a structurally-different cell (different category-tree) with
// coincidentally identical leaf values.
function buildDifferentShapeCell(k: Kernel): NodeID {
  const i1 = k.internTrivialInt(1);
  const i2 = k.internTrivialInt(2);
  // MINUS instead of PLUS — different category, different shape.
  const sub = k.intern(mathCat(RMath.MINUS), [i1, i2]);
  return k.intern(blockCat(RBlock.DO), [sub]);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

function testCompositionalDepth(): void {
  process.stdout.write("compositionalDepth\n");
  const k = new Kernel();
  const triv = k.internTrivialInt(42);
  eq(compositionalDepth(k, triv), 1, "trivial has depth 1");

  const cell = buildNestedCell(k);
  // DO -> [PLUS -> [PLUS -> [int, int], PLUS -> [int, int]], MUL -> [int, int]]
  // depth 4 along the deepest branch (DO, PLUS, PLUS, int)
  eq(compositionalDepth(k, cell), 4, "nested cell depth = 4");
}

function testProjectDownStripsValues(): void {
  process.stdout.write("projectDown strips values\n");
  const k = new Kernel();
  const cell = buildNestedCell(k);

  // Project to the deepest level — preserves full structure, but trivial
  // values are still replaced with category-only shape tokens (the value
  // erasure is unconditional, level only controls collapse).
  const full = projectDown(k, cell, 4);
  const fullDepth = compositionalDepth(k, full);
  assert(fullDepth <= 4, `depth of full projection (${fullDepth}) <= 4`);

  // The root category survives.
  eq(k.category(full), k.category(cell), "root category preserved");
}

function testProjectDownCollapses(): void {
  process.stdout.write("projectDown collapses deep subtrees\n");
  const k = new Kernel();
  const cell = buildNestedCell(k);

  // Project to depth 2 — root + one level of children, deeper collapses.
  const shallow = projectDown(k, cell, 2);
  const d = compositionalDepth(k, shallow);
  assert(d <= 2, `shallow projection depth (${d}) <= 2`);
  // Root category should still be DO BLOCK.
  eq(
    k.category(shallow).type,
    RBasic.BLOCK,
    "root remains BLOCK after projectDown",
  );
}

function testStructuralShapeEquivalence(): void {
  process.stdout.write("structuralShape — equivalence across values\n");
  const k = new Kernel();
  const a = buildNestedCell(k);
  const b = buildIsomorphicCell(k);
  const c = buildDifferentShapeCell(k);

  const shapeA = structuralShape(k, a);
  const shapeB = structuralShape(k, b);
  const shapeC = structuralShape(k, c);

  eq(
    nodeKey(shapeA),
    nodeKey(shapeB),
    "two semantically-different but structurally-identical cells share shape NodeID",
  );
  assert(
    nodeKey(shapeA) !== nodeKey(shapeC),
    "structurally-different cells produce different shape NodeIDs",
  );
}

function testProjectUpFindsContainers(): void {
  process.stdout.write("projectUp finds containing recipes\n");
  const k = new Kernel();
  const i1 = k.internTrivialInt(100);
  const i2 = k.internTrivialInt(200);
  const inner = k.intern(mathCat(RMath.PLUS), [i1, i2]);
  const outer = k.intern(blockCat(RBlock.DO), [inner]);

  // projectUp from inner should reach outer.
  const up = projectUp(k, inner, 4);
  eq(nodeKey(up), nodeKey(outer), "projectUp(inner) reaches outer");

  // From the leaf, projectUp should at minimum step to inner.
  const leafUp = projectUp(k, i1, 2);
  // Could be inner (if inner is the lowest-inst container).
  const containers = findAllContainers(k, i1);
  assert(
    containers.some((c) => nodeKey(c) === nodeKey(inner)),
    "leaf i1's containers include inner",
  );
  assert(
    nodeKey(leafUp) === nodeKey(inner) || nodeKey(leafUp) === nodeKey(outer),
    `projectUp(leaf) → known ancestor (got ${nodeKey(leafUp)})`,
  );
}

function testProjectUpStopsWhenNoContainer(): void {
  process.stdout.write("projectUp returns source when nothing contains it\n");
  const k = new Kernel();
  const root = k.intern(blockCat(RBlock.DO), [k.internTrivialInt(1)]);
  const up = projectUp(k, root, 5);
  eq(nodeKey(up), nodeKey(root), "uncontained root projects to itself");
}

function testMakeProjectionIsContentAddressed(): void {
  process.stdout.write("makeProjection — content-addressed\n");
  const k = new Kernel();
  const cell = buildNestedCell(k);
  const p1 = makeProjection(k, cell, 2);
  const p2 = makeProjection(k, cell, 2);
  eq(nodeKey(p1), nodeKey(p2), "same (source, level) → same projection NodeID");

  const p3 = makeProjection(k, cell, 3);
  assert(
    nodeKey(p1) !== nodeKey(p3),
    "different levels → different projection NodeIDs",
  );

  // The projection recipe's category is PROJECT.
  eq(k.category(p1).type, RBasic.PROJECT, "projection category is RBasic.PROJECT");
}

function testFindContainerOnUncontainedReturnsUndefined(): void {
  process.stdout.write("findContainer — uncontained returns undefined\n");
  const k = new Kernel();
  const lonely = k.intern(mathCat(RMath.PLUS), [
    k.internTrivialInt(1),
    k.internTrivialInt(2),
  ]);
  // Nothing has been built that contains `lonely`.
  const c = findContainer(k, lonely);
  eq(c, undefined, "lonely recipe has no container");
}

function testProjectDownBelowDepthIsIdempotent(): void {
  process.stdout.write("projectDown — idempotent at structural-shape level\n");
  const k = new Kernel();
  const cell = buildNestedCell(k);
  const s1 = structuralShape(k, cell);
  const s2 = structuralShape(k, s1);
  eq(nodeKey(s1), nodeKey(s2), "shape of shape == shape (idempotent)");
}

function testPROJECTSlot(): void {
  process.stdout.write("RBasic.PROJECT slot\n");
  eq(RBasic.PROJECT, 81, "RBasic.PROJECT = 81");
}

function main(): void {
  testCompositionalDepth();
  testProjectDownStripsValues();
  testProjectDownCollapses();
  testStructuralShapeEquivalence();
  testProjectUpFindsContainers();
  testProjectUpStopsWhenNoContainer();
  testMakeProjectionIsContentAddressed();
  testFindContainerOnUncontainedReturnsUndefined();
  testProjectDownBelowDepthIsIdempotent();
  testPROJECTSlot();

  process.stdout.write(`\n${passes} passed, ${failures} failed\n`);
  if (failures > 0) process.exit(1);
}

main();
