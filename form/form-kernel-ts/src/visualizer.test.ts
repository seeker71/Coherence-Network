// visualizer tests — substrate → grid → recipe → WGSL.
//
// Self-contained runner (mirrors bench.ts shape). Run with:
//   npx tsx src/visualizer.test.ts
//
// Verifies:
//   • nodeIDToColor is deterministic (same NodeID → same RGBA across calls).
//   • Two cells with the same Blueprint (pkg.level.type) share visual
//     identity under the "blueprint" scheme — structural sameness is
//     visible in the framebuffer.
//   • The "instance" scheme distinguishes siblings with different inst.
//   • renderSubstrate returns a recipe NodeID and a position list.
//   • Position list never exceeds the grid capacity.
//   • CPU rasterizer produces width*height*4 bytes with the expected
//     background and per-cell colors at expected offsets.
//   • compileToWGSL produces a WGSL source string with the load-bearing
//     scaffold: @compute, @workgroup_size, @group/@binding, an entry-
//     point fn, and at least one per-cell branch.

import { Kernel, Level, RBasic, RBlock } from "./kernel.ts";
import {
  DEFAULT_CONFIG,
  collectCells,
  compileToWGSL,
  mapCellsToGrid,
  nodeIDToColor,
  rasterize,
  renderSubstrate,
  renderToRGBA8,
  visualizeToWGSL,
  type VisualizerConfig,
} from "./visualizer.ts";

interface Result {
  name: string;
  ok: boolean;
  msg?: string;
}

const results: Result[] = [];

function check(name: string, cond: boolean, msg?: string): void {
  results.push({ name, ok: cond, msg });
}

function assertEq<T>(name: string, actual: T, expected: T): void {
  const ok = actual === expected;
  check(name, ok, ok ? undefined : `expected ${String(expected)}, got ${String(actual)}`);
}

// -- 1. nodeIDToColor determinism -----------------------------------------

const node = { pkg: 1, level: 2, type: 9, inst: 42 };
const c1 = nodeIDToColor(node, "blueprint");
const c2 = nodeIDToColor(node, "blueprint");
check(
  "nodeIDToColor deterministic",
  c1[0] === c2[0] && c1[1] === c2[1] && c1[2] === c2[2] && c1[3] === c2[3],
);

// -- 2. blueprint scheme collapses inst ----------------------------------

const sibA = { pkg: 1, level: 2, type: 9, inst: 1 };
const sibB = { pkg: 1, level: 2, type: 9, inst: 2 };
const cA = nodeIDToColor(sibA, "blueprint");
const cB = nodeIDToColor(sibB, "blueprint");
check(
  "blueprint scheme: same shape ⇒ same color",
  cA[0] === cB[0] && cA[1] === cB[1] && cA[2] === cB[2],
);

// -- 3. instance scheme distinguishes siblings --------------------------

const cAi = nodeIDToColor(sibA, "instance");
const cBi = nodeIDToColor(sibB, "instance");
check(
  "instance scheme: different inst ⇒ different color (typically)",
  cAi[0] !== cBi[0] || cAi[1] !== cBi[1] || cAi[2] !== cBi[2],
);

// -- 4. level scheme gives categorical colors ---------------------------

const lvlA = nodeIDToColor({ pkg: 1, level: 1, type: 2, inst: 0 }, "level");
const lvlB = nodeIDToColor({ pkg: 1, level: 2, type: 9, inst: 0 }, "level");
check(
  "level scheme: different level ⇒ different red channel",
  lvlA[0] !== lvlB[0],
);
assertEq("level scheme alpha pinned 255", lvlA[3], 255);

// -- 5. collectCells reads the lattice ----------------------------------

const k = new Kernel();
// Build a small substrate: a SEQUENCE containing two LET bindings.
const blockCat = { pkg: 1, level: Level.BASIC, type: RBasic.BLOCK, inst: RBlock.SEQUENCE };
const letCat = { pkg: 1, level: Level.BASIC, type: RBasic.BLOCK, inst: RBlock.LET };
const nameA = k.internString("a");
const nameB = k.internString("b");
const letA = k.intern(letCat, [nameA, k.internTrivialInt(7)]);
const letB = k.intern(letCat, [nameB, k.internTrivialInt(8)]);
const seq = k.intern(blockCat, [letA, letB]);
void seq;

const cells = collectCells(k);
check("collectCells returns at least the composite nodes", cells.length >= 3);

// -- 6. mapCellsToGrid layout ------------------------------------------

const positions = mapCellsToGrid(k, cells, 8, 8, "instance");
check(
  "mapCellsToGrid: positions ≤ grid capacity",
  positions.length <= 64,
);
check(
  "mapCellsToGrid: every position inside the grid",
  positions.every((p) => p.col >= 0 && p.col < 8 && p.row >= 0 && p.row < 8),
);

const depthPositions = mapCellsToGrid(k, cells, 8, 8, "depth");
check(
  "mapCellsToGrid: depth layout produces positions",
  depthPositions.length > 0,
);

// -- 7. renderSubstrate produces a recipe + positions ------------------

const program = renderSubstrate(k, {
  ...DEFAULT_CONFIG,
  width: 32,
  height: 32,
  gridCols: 8,
  gridRows: 8,
});
check(
  "renderSubstrate: recipe NodeID has BASIC level",
  program.recipe.level === Level.BASIC,
);
check(
  "renderSubstrate: positions non-empty",
  program.positions.length > 0,
);

// -- 8. rasterize produces width*height*4 bytes ------------------------

const cfg: VisualizerConfig = {
  width: 32,
  height: 32,
  gridCols: 8,
  gridRows: 8,
  colorScheme: "blueprint",
  layout: "instance",
  background: [10, 20, 30, 255],
};
const buf = renderToRGBA8(k, cfg);
assertEq("rasterize: byte length = width*height*4", buf.length, 32 * 32 * 4);
// Probe the bottom-right pixel (likely background — fewer cells than grid).
const lastOff = (31 * 32 + 31) * 4;
const bgMatch =
  buf[lastOff] === 10 &&
  buf[lastOff + 1] === 20 &&
  buf[lastOff + 2] === 30 &&
  buf[lastOff + 3] === 255;
check("rasterize: empty tile shows background color", bgMatch);

// -- 9. blueprint scheme: two cells with same shape paint same color --

const k2 = new Kernel();
// Two LET bindings with identical structural shape ⇒ different instance
// counters but same Blueprint (level=BASIC, type=BLOCK, inst=LET).
const letC = k2.intern(letCat, [k2.internString("x"), k2.internTrivialInt(1)]);
const letD = k2.intern(letCat, [k2.internString("y"), k2.internTrivialInt(1)]);
check("two LET cells differ by instance", letC.inst !== letD.inst);
const colC = nodeIDToColor(letC, "blueprint");
const colD = nodeIDToColor(letD, "blueprint");
check(
  "same Blueprint ⇒ same color (structural sameness visible)",
  colC[0] === colD[0] && colC[1] === colD[1] && colC[2] === colD[2],
);

// -- 10. rasterize with one explicit position --------------------------

const oneCell = [{ node: letC, col: 0, row: 0 }];
const tiny = rasterize(oneCell, {
  width: 8,
  height: 8,
  gridCols: 4,
  gridRows: 4,
  colorScheme: "instance",
  layout: "instance",
  background: [0, 0, 0, 255],
});
const expected = nodeIDToColor(letC, "instance");
const topLeftMatch =
  tiny[0] === expected[0] &&
  tiny[1] === expected[1] &&
  tiny[2] === expected[2] &&
  tiny[3] === expected[3];
check("rasterize: single-cell tile matches nodeIDToColor", topLeftMatch);

// -- 11. compileToWGSL produces a valid-looking shader -----------------

const wgsl = compileToWGSL(k, program);
check("WGSL: contains @compute", wgsl.includes("@compute"));
check("WGSL: contains @workgroup_size", wgsl.includes("@workgroup_size"));
check("WGSL: contains storage binding", wgsl.includes("@group(0) @binding(0)"));
check("WGSL: contains entry point fn main", wgsl.includes("fn main"));
check("WGSL: contains pack_rgba8", wgsl.includes("pack_rgba8"));
check(
  "WGSL: has at least one per-cell branch",
  wgsl.includes("if (gid.x >="),
);
check(
  "WGSL: backend seam unused-but-accepted",
  compileToWGSL(k, program, {
    backend: { emitExpression: (_k, _n) => "0u" },
  }).includes("@compute"),
);

// -- 12. visualizeToWGSL one-shot --------------------------------------

const one = visualizeToWGSL(k, cfg);
check("visualizeToWGSL: program present", one.program.positions.length > 0);
check("visualizeToWGSL: rgba8 length", one.rgba8.length === 32 * 32 * 4);
check("visualizeToWGSL: wgsl non-empty", one.wgsl.length > 100);

// -- Report --------------------------------------------------------------

let passed = 0;
let failed = 0;
for (const r of results) {
  if (r.ok) {
    passed++;
    console.log(`  ok    ${r.name}`);
  } else {
    failed++;
    console.log(`  FAIL  ${r.name}${r.msg ? `: ${r.msg}` : ""}`);
  }
}
console.log(`\n${passed} passed, ${failed} failed (${results.length} total)`);
if (failed > 0) {
  process.exit(1);
}
