// Tests for parallel-pattern recipes (TILE, PARALLELIZE, VECTORIZE).
//
// Standalone runnable via `tsx src/parallel.test.ts`. Each `test(...)`
// throws on failure; first failure aborts the run.

import { Frame, Kernel, Level, RBasic, walk, type NodeID } from "./kernel.ts";
import {
  isParallelPattern,
  parallelize,
  readParallelPattern,
  tile,
  unwrapPatterns,
  vectorize,
} from "./parallel.ts";

let passed = 0;
let failed = 0;

function test(name: string, fn: () => void): void {
  try {
    fn();
    passed++;
    process.stdout.write(`  ok  ${name}\n`);
  } catch (e) {
    failed++;
    const msg = e instanceof Error ? e.message : String(e);
    process.stdout.write(`  FAIL ${name}: ${msg}\n`);
  }
}

function assertEq<T>(actual: T, expected: T, msg = ""): void {
  if (actual !== expected) {
    throw new Error(
      `${msg ? msg + ": " : ""}expected ${JSON.stringify(String(expected))}, got ${JSON.stringify(String(actual))}`,
    );
  }
}

function assertNodeEq(a: NodeID, b: NodeID, msg = ""): void {
  if (a.pkg !== b.pkg || a.level !== b.level || a.type !== b.type || a.inst !== b.inst) {
    throw new Error(
      `${msg ? msg + ": " : ""}nodes differ ${JSON.stringify(a)} vs ${JSON.stringify(b)}`,
    );
  }
}

function assertThrows(fn: () => unknown, msg = ""): void {
  try {
    fn();
  } catch {
    return;
  }
  throw new Error(`${msg || "expected throw"} — no error raised`);
}

// Helper: build a dummy inner op-recipe. The simplest valid composite
// is a LIST containing one int trivial. Walker treats it as a list.
function makeDummyOp(k: Kernel): NodeID {
  const cat: NodeID = { pkg: 1, level: Level.BASIC, type: RBasic.LIST, inst: 1 };
  return k.intern(cat, [k.internTrivialInt(0)]);
}

// ---------------------------------------------------------------------------
// 1. Constructors
// ---------------------------------------------------------------------------

test("tile: builds an RBasic.TILE recipe", () => {
  const k = new Kernel();
  const op = makeDummyOp(k);
  const t = tile(k, op, 8);
  assertEq(t.type, RBasic.TILE, "category type");
  if (t.inst <= 0) throw new Error(`expected positive inst, got ${t.inst}`);
});

test("parallelize: builds an RBasic.PARALLELIZE recipe", () => {
  const k = new Kernel();
  const op = makeDummyOp(k);
  const p = parallelize(k, op, 16);
  assertEq(p.type, RBasic.PARALLELIZE, "category type");
});

test("vectorize: builds an RBasic.VECTORIZE recipe", () => {
  const k = new Kernel();
  const op = makeDummyOp(k);
  const v = vectorize(k, op, 8);
  assertEq(v.type, RBasic.VECTORIZE, "category type");
});

test("all three reject non-positive parameters", () => {
  const k = new Kernel();
  const op = makeDummyOp(k);
  assertThrows(() => tile(k, op, 0), "tile size 0");
  assertThrows(() => tile(k, op, -1), "tile size -1");
  assertThrows(() => parallelize(k, op, 0), "threads 0");
  assertThrows(() => vectorize(k, op, 0), "width 0");
  assertThrows(() => vectorize(k, op, 2.5), "width fractional");
});

// ---------------------------------------------------------------------------
// 2. Content-addressing
// ---------------------------------------------------------------------------

test("tile: same (op, size) ⇒ same NodeID", () => {
  const k = new Kernel();
  const op = makeDummyOp(k);
  const a = tile(k, op, 8);
  const b = tile(k, op, 8);
  assertNodeEq(a, b);
});

test("tile: different sizes ⇒ different NodeIDs", () => {
  const k = new Kernel();
  const op = makeDummyOp(k);
  const a = tile(k, op, 4);
  const b = tile(k, op, 8);
  if (a.inst === b.inst) throw new Error("tile(4) and tile(8) should differ");
});

test("tile / parallelize / vectorize: distinct families even with same parameter", () => {
  const k = new Kernel();
  const op = makeDummyOp(k);
  const t = tile(k, op, 8);
  const p = parallelize(k, op, 8);
  const v = vectorize(k, op, 8);
  if (t.type === p.type || p.type === v.type || t.type === v.type) {
    throw new Error("pattern types must be distinct");
  }
});

// ---------------------------------------------------------------------------
// 3. Readers
// ---------------------------------------------------------------------------

test("readParallelPattern: recovers TILE parameters", () => {
  const k = new Kernel();
  const op = makeDummyOp(k);
  const t = tile(k, op, 32);
  const view = readParallelPattern(k, t);
  assertEq(view.patternType, RBasic.TILE);
  assertEq(view.parameter, 32);
  assertNodeEq(view.inner, op);
});

test("readParallelPattern: rejects non-pattern recipes", () => {
  const k = new Kernel();
  const op = makeDummyOp(k);
  assertThrows(() => readParallelPattern(k, op), "non-pattern node");
});

test("isParallelPattern: true for all three, false for inner", () => {
  const k = new Kernel();
  const op = makeDummyOp(k);
  if (!isParallelPattern(k, tile(k, op, 4))) throw new Error("TILE not recognized");
  if (!isParallelPattern(k, parallelize(k, op, 4))) {
    throw new Error("PARALLELIZE not recognized");
  }
  if (!isParallelPattern(k, vectorize(k, op, 4))) {
    throw new Error("VECTORIZE not recognized");
  }
  if (isParallelPattern(k, op)) throw new Error("LIST mistaken for pattern");
});

// ---------------------------------------------------------------------------
// 4. Composition + unwrapping
// ---------------------------------------------------------------------------

test("patterns compose: parallelize(tile(op, 8), 4)", () => {
  const k = new Kernel();
  const op = makeDummyOp(k);
  const tiled = tile(k, op, 8);
  const par = parallelize(k, tiled, 4);
  const outer = readParallelPattern(k, par);
  assertEq(outer.patternType, RBasic.PARALLELIZE);
  assertEq(outer.parameter, 4);
  const inner = readParallelPattern(k, outer.inner);
  assertEq(inner.patternType, RBasic.TILE);
  assertEq(inner.parameter, 8);
  assertNodeEq(inner.inner, op);
});

test("unwrapPatterns: strips arbitrary nesting", () => {
  const k = new Kernel();
  const op = makeDummyOp(k);
  const wrapped = vectorize(k, parallelize(k, tile(k, op, 8), 4), 16);
  const inner = unwrapPatterns(k, wrapped);
  assertNodeEq(inner, op);
});

test("unwrapPatterns: no-op on un-wrapped recipes", () => {
  const k = new Kernel();
  const op = makeDummyOp(k);
  assertNodeEq(unwrapPatterns(k, op), op);
});

// ---------------------------------------------------------------------------
// 5. Walker passes patterns through
// ---------------------------------------------------------------------------

test("walk: TILE recipe returns its own NodeID", () => {
  const k = new Kernel();
  const op = makeDummyOp(k);
  const t = tile(k, op, 8);
  const result = walk(k, t, new Frame(null));
  assertEq(result.kind, "nodeid");
  if (result.kind === "nodeid") assertNodeEq(result.nodeid, t);
});

test("walk: PARALLELIZE recipe returns its own NodeID", () => {
  const k = new Kernel();
  const op = makeDummyOp(k);
  const p = parallelize(k, op, 16);
  const result = walk(k, p, new Frame(null));
  assertEq(result.kind, "nodeid");
  if (result.kind === "nodeid") assertNodeEq(result.nodeid, p);
});

test("walk: VECTORIZE recipe returns its own NodeID", () => {
  const k = new Kernel();
  const op = makeDummyOp(k);
  const v = vectorize(k, op, 8);
  const result = walk(k, v, new Frame(null));
  assertEq(result.kind, "nodeid");
  if (result.kind === "nodeid") assertNodeEq(result.nodeid, v);
});

// ---------------------------------------------------------------------------

process.stdout.write(`\n${passed} passed, ${failed} failed\n`);
if (failed > 0) process.exit(1);
