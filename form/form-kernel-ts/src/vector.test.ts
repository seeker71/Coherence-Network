// Tests for VECTOR format-recipes + per-lane MATH dispatch + reductions.
//
// Standalone runnable via `tsx src/vector.test.ts`. Each `test(...)`
// throws on failure; first failure aborts the run. Designed to live next
// to the existing kernel files until this surface grows a real harness.

import { Kernel, RBasic, type NodeID } from "./kernel.ts";
import { buildFormatLibrary } from "./formats.ts";
import {
  addVec,
  divVec,
  dotVec,
  makeVectorFormat,
  maxVec,
  minVec,
  modVec,
  mulVec,
  popcountVec,
  readVectorFormat,
  subVec,
  sumVec,
  VectorWidth,
} from "./vector.ts";

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

// ---------------------------------------------------------------------------
// 1. Construction + content-addressing
// ---------------------------------------------------------------------------

test("makeVectorFormat: builds a RBasic.VECTOR recipe", () => {
  const k = new Kernel();
  const lib = buildFormatLibrary(k);
  const v = makeVectorFormat(k, lib.FP32, VectorWidth.W8);
  assertEq(v.nodeID.type, RBasic.VECTOR, "category type");
  if (v.nodeID.inst <= 0) {
    throw new Error(`expected positive inst, got ${v.nodeID.inst}`);
  }
  assertEq(v.width, 8);
  assertEq(v.storageHint, "scalar-array");
});

test("makeVectorFormat: width is reflected in category inst", () => {
  const k = new Kernel();
  const lib = buildFormatLibrary(k);
  const v4 = makeVectorFormat(k, lib.FP32, 4);
  const v8 = makeVectorFormat(k, lib.FP32, 8);
  // Category inst carries width.
  assertEq(v4.width, 4);
  assertEq(v8.width, 8);
  // Distinct NodeIDs.
  if (v4.nodeID.inst === v8.nodeID.inst) {
    throw new Error("4-wide and 8-wide should have distinct NodeIDs");
  }
});

test("makeVectorFormat: content-addressed (same args ⇒ same NodeID)", () => {
  const k = new Kernel();
  const lib = buildFormatLibrary(k);
  const a = makeVectorFormat(k, lib.FP64, 4, "gpu-vec4");
  const b = makeVectorFormat(k, lib.FP64, 4, "gpu-vec4");
  assertNodeEq(a.nodeID, b.nodeID, "intern should dedup");
});

test("makeVectorFormat: storage hint differentiates NodeID", () => {
  const k = new Kernel();
  const lib = buildFormatLibrary(k);
  const a = makeVectorFormat(k, lib.FP32, 8, "simd-avx2");
  const b = makeVectorFormat(k, lib.FP32, 8, "simd-avx512");
  if (a.nodeID.inst === b.nodeID.inst) {
    throw new Error("different storage-hints should produce distinct NodeIDs");
  }
});

test("makeVectorFormat: rejects non-positive width", () => {
  const k = new Kernel();
  const lib = buildFormatLibrary(k);
  assertThrows(() => makeVectorFormat(k, lib.FP32, 0), "width=0");
  assertThrows(() => makeVectorFormat(k, lib.FP32, -4), "width=-4");
  assertThrows(() => makeVectorFormat(k, lib.FP32, 1.5), "width=1.5");
});

test("readVectorFormat: round-trips through substrate", () => {
  const k = new Kernel();
  const lib = buildFormatLibrary(k);
  const v = makeVectorFormat(k, lib.FP32, 16, "simd-avx512");
  const view = readVectorFormat(k, v.nodeID);
  assertEq(view.width, 16);
  assertEq(view.storageHint, "simd-avx512");
  assertNodeEq(view.elementNodeID, lib.FP32.nodeID);
});

test("readVectorFormat: rejects non-VECTOR recipes", () => {
  const k = new Kernel();
  const lib = buildFormatLibrary(k);
  assertThrows(() => readVectorFormat(k, lib.FP32.nodeID), "non-vector node");
});

// ---------------------------------------------------------------------------
// 2. Per-lane arithmetic
// ---------------------------------------------------------------------------

test("addVec: lanes-wise float addition (FP64)", () => {
  const k = new Kernel();
  const lib = buildFormatLibrary(k);
  const v = makeVectorFormat(k, lib.FP64, 4);
  const out = addVec(v, [1, 2, 3, 4], [10, 20, 30, 40]);
  assertEq(out[0], 11, "lane 0");
  assertEq(out[1], 22, "lane 1");
  assertEq(out[2], 33, "lane 2");
  assertEq(out[3], 44, "lane 3");
});

test("addVec: lanes-wise integer addition (INT32 native-int)", () => {
  const k = new Kernel();
  const lib = buildFormatLibrary(k);
  const v = makeVectorFormat(k, lib.INT32, 4);
  const out = addVec(v, [1, 2, 3, 4], [10, 20, 30, 40]);
  assertEq(out[0], 11);
  assertEq(out[3], 44);
});

test("subVec / mulVec: lanes-wise", () => {
  const k = new Kernel();
  const lib = buildFormatLibrary(k);
  const v = makeVectorFormat(k, lib.FP64, 4);
  const sub = subVec(v, [10, 20, 30, 40], [1, 2, 3, 4]);
  assertEq(sub[0], 9);
  assertEq(sub[3], 36);
  const mul = mulVec(v, [1, 2, 3, 4], [10, 10, 10, 10]);
  assertEq(mul[0], 10);
  assertEq(mul[3], 40);
});

test("divVec / modVec: lanes-wise", () => {
  const k = new Kernel();
  const lib = buildFormatLibrary(k);
  const v = makeVectorFormat(k, lib.FP64, 4);
  const div = divVec(v, [10, 20, 30, 40], [2, 4, 5, 8]);
  assertEq(div[0], 5);
  assertEq(div[3], 5);
  const v2 = makeVectorFormat(k, lib.INT32, 4);
  const mod = modVec(v2, [10, 20, 30, 41], [3, 6, 7, 8]);
  assertEq(mod[0], 1);
  assertEq(mod[3], 1);
});

test("vec ops: shape mismatch throws", () => {
  const k = new Kernel();
  const lib = buildFormatLibrary(k);
  const v = makeVectorFormat(k, lib.FP32, 4);
  assertThrows(() => addVec(v, [1, 2, 3], [4, 5, 6, 7]), "lhs short");
  assertThrows(() => addVec(v, [1, 2, 3, 4], [4, 5, 6]), "rhs short");
});

test("addVec: INT8 narrows per lane (overflow)", () => {
  const k = new Kernel();
  const lib = buildFormatLibrary(k);
  const v = makeVectorFormat(k, lib.INT8, 4);
  // 100 + 100 = 200 → narrows to int8 (200 - 256 = -56)
  const out = addVec(v, [100, 100, 1, 2], [100, 100, 1, 2]);
  assertEq(out[0], -56, "int8 overflow narrows");
  assertEq(out[2], 2);
});

// ---------------------------------------------------------------------------
// 3. Reductions
// ---------------------------------------------------------------------------

test("sumVec: float", () => {
  const k = new Kernel();
  const lib = buildFormatLibrary(k);
  const v = makeVectorFormat(k, lib.FP64, 4);
  assertEq(sumVec(v, [1, 2, 3, 4]), 10);
});

test("sumVec: integer", () => {
  const k = new Kernel();
  const lib = buildFormatLibrary(k);
  const v = makeVectorFormat(k, lib.INT32, 8);
  assertEq(sumVec(v, [1, 2, 3, 4, 5, 6, 7, 8]), 36);
});

test("maxVec / minVec: float lanes", () => {
  const k = new Kernel();
  const lib = buildFormatLibrary(k);
  const v = makeVectorFormat(k, lib.FP64, 4);
  assertEq(maxVec(v, [3, 1, 4, 1]), 4);
  assertEq(minVec(v, [3, 1, 4, 1]), 1);
});

test("maxVec / minVec: single lane", () => {
  const k = new Kernel();
  const lib = buildFormatLibrary(k);
  const v = makeVectorFormat(k, lib.FP64, 1);
  assertEq(maxVec(v, [42]), 42);
  assertEq(minVec(v, [42]), 42);
});

test("dotVec: classic inner product", () => {
  const k = new Kernel();
  const lib = buildFormatLibrary(k);
  const v = makeVectorFormat(k, lib.FP64, 4);
  // 1*10 + 2*20 + 3*30 + 4*40 = 10 + 40 + 90 + 160 = 300
  assertEq(dotVec(v, [1, 2, 3, 4], [10, 20, 30, 40]), 300);
});

test("dotVec: shape mismatch throws", () => {
  const k = new Kernel();
  const lib = buildFormatLibrary(k);
  const v = makeVectorFormat(k, lib.FP64, 4);
  assertThrows(() => dotVec(v, [1, 2, 3], [10, 20, 30, 40]));
});

test("popcountVec: counts nonzero lanes", () => {
  const k = new Kernel();
  const lib = buildFormatLibrary(k);
  const v = makeVectorFormat(k, lib.BIT_1, 8);
  assertEq(popcountVec(v, [1, 0, 1, 0, 1, 1, 0, 1]), 5);
  assertEq(popcountVec(v, [0, 0, 0, 0, 0, 0, 0, 0]), 0);
  assertEq(popcountVec(v, [1, 1, 1, 1, 1, 1, 1, 1]), 8);
});

// ---------------------------------------------------------------------------
// 4. Width-family identity
// ---------------------------------------------------------------------------

test("common widths intern at distinct NodeIDs", () => {
  const k = new Kernel();
  const lib = buildFormatLibrary(k);
  const widths = [VectorWidth.W4, VectorWidth.W8, VectorWidth.W16, VectorWidth.W32, VectorWidth.W64];
  const seen = new Set<number>();
  for (const w of widths) {
    const v = makeVectorFormat(k, lib.FP32, w);
    if (seen.has(v.nodeID.inst)) {
      throw new Error(`width ${w} interned at duplicate inst ${v.nodeID.inst}`);
    }
    seen.add(v.nodeID.inst);
  }
  assertEq(seen.size, widths.length);
});

test("storage hints span the target backends", () => {
  const k = new Kernel();
  const lib = buildFormatLibrary(k);
  const hints = ["simd-avx2", "simd-avx512", "simd-neon", "gpu-vec4", "wasm-simd"] as const;
  for (const h of hints) {
    const v = makeVectorFormat(k, lib.FP32, 4, h);
    assertEq(v.storageHint, h);
  }
});

// ---------------------------------------------------------------------------
// 5. Walker doesn't crash on VECTOR recipes
// ---------------------------------------------------------------------------

test("walk: VECTOR recipe returns its own NodeID (structural)", async () => {
  const { walk, Frame } = await import("./kernel.ts");
  const k = new Kernel();
  const lib = buildFormatLibrary(k);
  const v = makeVectorFormat(k, lib.FP32, 8);
  const result = walk(k, v.nodeID, new Frame(null));
  assertEq(result.kind, "nodeid");
  if (result.kind === "nodeid") {
    assertNodeEq(result.nodeid, v.nodeID);
  }
});

// ---------------------------------------------------------------------------

process.stdout.write(`\n${passed} passed, ${failed} failed\n`);
if (failed > 0) process.exit(1);
