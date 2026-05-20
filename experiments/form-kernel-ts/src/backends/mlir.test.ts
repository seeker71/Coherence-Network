// Smoke tests for the MLIR emit backend.
//
// Standalone runnable via `tsx src/backends/mlir.test.ts`. Each `test(...)`
// throws on failure; failure does not abort the run so the surface gets a
// full report. Matches the test convention already used by sibling kernel
// modules (vector.test.ts, parallel.test.ts).

import {
  Kernel,
  Level,
  RBasic,
  RBlock,
  RCmp,
  RCond,
  RLogic,
  RMath,
  Triv,
  type NodeID,
} from "../kernel.ts";

import { emit, MlirBackend, type MlirEmitOptions } from "./mlir.ts";

// ---------------------------------------------------------------------------
// Tiny test harness
// ---------------------------------------------------------------------------

let passed = 0;
let failed = 0;

function test(name: string, fn: () => void): void {
  try {
    fn();
    passed++;
    process.stdout.write(`  ok  ${name}\n`);
  } catch (e) {
    failed++;
    const msg = e instanceof Error ? e.stack ?? e.message : String(e);
    process.stdout.write(`  FAIL ${name}: ${msg}\n`);
  }
}

function assertContains(haystack: string, needle: string, label = ""): void {
  if (!haystack.includes(needle)) {
    throw new Error(
      `${label ? label + ": " : ""}expected to find ${JSON.stringify(needle)} in:\n${haystack}`,
    );
  }
}

function assertMatches(haystack: string, re: RegExp, label = ""): void {
  if (!re.test(haystack)) {
    throw new Error(
      `${label ? label + ": " : ""}expected ${re.toString()} to match in:\n${haystack}`,
    );
  }
}

function assertEq<T>(actual: T, expected: T, label = ""): void {
  if (actual !== expected) {
    throw new Error(
      `${label ? label + ": " : ""}expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`,
    );
  }
}

// ---------------------------------------------------------------------------
// Recipe builders — small Form-shape helpers that target the bench cases.
// ---------------------------------------------------------------------------

function basicCat(k: Kernel, type: number, inst = 0): NodeID {
  // Use the kernel's categorical NodeID convention — pkg=1, level=BASIC.
  // No need to intern; the walker / emitter only reads .type and .inst.
  return { pkg: 1, level: Level.BASIC, type, inst };
}

function mathNode(
  k: Kernel,
  op: number,
  kids: NodeID[],
): NodeID {
  return k.intern(basicCat(k, RBasic.MATH, op), kids);
}

function cmpNode(k: Kernel, op: number, a: NodeID, b: NodeID): NodeID {
  return k.intern(basicCat(k, RBasic.COMPARE, op), [a, b]);
}

function logicNode(k: Kernel, op: number, kids: NodeID[]): NodeID {
  return k.intern(basicCat(k, RBasic.LOGIC, op), kids);
}

function ifElse(k: Kernel, cond: NodeID, t: NodeID, e: NodeID): NodeID {
  return k.intern(basicCat(k, RBasic.COND, RCond.IF_THEN_ELSE), [cond, t, e]);
}

function block(k: Kernel, op: number, kids: NodeID[]): NodeID {
  return k.intern(basicCat(k, RBasic.BLOCK, op), kids);
}

function letNode(k: Kernel, name: string, value: NodeID): NodeID {
  return block(k, RBlock.LET, [k.internString(name), value]);
}

function ident(k: Kernel, name: string): NodeID {
  return k.intern(basicCat(k, RBasic.IDENT, 0), [k.internString(name)]);
}

function fndef(
  k: Kernel,
  name: string,
  params: string[],
  body: NodeID,
): NodeID {
  const paramKids = params.map((p) => k.internString(p));
  const paramsBlock = k.intern(basicCat(k, RBasic.BLOCK, RBlock.SEQUENCE), paramKids);
  return k.intern(basicCat(k, RBasic.FNDEF, 0), [
    k.internString(name),
    paramsBlock,
    body,
  ]);
}

function fncall(k: Kernel, callee: string, args: NodeID[]): NodeID {
  return k.intern(basicCat(k, RBasic.FNCALL, 0), [
    k.internString(callee),
    ...args,
  ]);
}

// ---------------------------------------------------------------------------
// 1. Backend surface
// ---------------------------------------------------------------------------

test("MlirBackend: name + target_hints", () => {
  assertEq(MlirBackend.name, "mlir", "backend name");
  const hints = MlirBackend.target_hints;
  if (!hints.has("mlir")) throw new Error("target_hints missing 'mlir'");
  if (!hints.has("cpu-via-llvm")) {
    throw new Error("target_hints missing 'cpu-via-llvm'");
  }
  if (!hints.has("gpu-via-mlir")) {
    throw new Error("target_hints missing 'gpu-via-mlir'");
  }
  assertEq(hints.size, 3, "target_hints size");
});

// ---------------------------------------------------------------------------
// 2. Module + func dialect — module wrapping is well-formed
// ---------------------------------------------------------------------------

test("emit: trivial int → module + func.func with constant return", () => {
  const k = new Kernel();
  const root = k.internTrivialInt(42);
  const out = emit(k, root);

  assertContains(out.text, "module @form_module {", "module header");
  assertContains(out.text, "func.func @form_root() -> i32", "root func");
  assertMatches(out.text, /arith\.constant\s+42\s*:\s*i32/, "i32 constant");
  assertMatches(out.text, /return\s+%c\d+\s*:\s*i32/, "return");
  assertEq(out.rootType, "i32", "rootType");
});

test("emit: module name + wrapInFunc options honored", () => {
  const k = new Kernel();
  const root = k.internTrivialInt(7);
  const opts: MlirEmitOptions = {
    moduleName: "smoke",
    wrapInFunc: true,
  };
  const out = emit(k, root, opts);
  assertContains(out.text, "module @smoke {", "module name");
});

// ---------------------------------------------------------------------------
// 3. arith dialect — integer math
// ---------------------------------------------------------------------------

test("emit: arith.addi on i32 integers", () => {
  const k = new Kernel();
  const a = k.internTrivialInt(3);
  const b = k.internTrivialInt(4);
  const root = mathNode(k, RMath.PLUS, [a, b]);
  const out = emit(k, root);
  assertMatches(
    out.text,
    /%r\d+\s*=\s*arith\.addi\s+%c\d+,\s*%c\d+\s*:\s*i32/,
    "arith.addi",
  );
});

test("emit: arith.muli + arith.subi + arith.divsi + arith.remsi", () => {
  const k = new Kernel();
  const a = k.internTrivialInt(6);
  const b = k.internTrivialInt(2);
  const mul = mathNode(k, RMath.MUL, [a, b]);
  const sub = mathNode(k, RMath.MINUS, [mul, k.internTrivialInt(1)]);
  const div = mathNode(k, RMath.DIV, [sub, k.internTrivialInt(3)]);
  const mod = mathNode(k, RMath.MOD, [div, k.internTrivialInt(2)]);
  const out = emit(k, mod);
  assertMatches(out.text, /arith\.muli/, "muli");
  assertMatches(out.text, /arith\.subi/, "subi");
  assertMatches(out.text, /arith\.divsi/, "divsi");
  assertMatches(out.text, /arith\.remsi/, "remsi");
});

// ---------------------------------------------------------------------------
// 4. arith dialect — comparison + i1 result
// ---------------------------------------------------------------------------

test("emit: arith.cmpi produces i1", () => {
  const k = new Kernel();
  const a = k.internTrivialInt(5);
  const b = k.internTrivialInt(3);
  const root = cmpNode(k, RCmp.LT, a, b);
  const out = emit(k, root);
  assertMatches(out.text, /arith\.cmpi\s+slt,\s+%c\d+,\s*%c\d+\s*:\s*i32/, "cmpi slt");
  assertEq(out.rootType, "i1", "rootType");
});

test("emit: all six compare predicates lower to slt/sle/sgt/sge/eq/ne", () => {
  const preds: Array<[number, string]> = [
    [RCmp.EQ, "eq"],
    [RCmp.NE, "ne"],
    [RCmp.LT, "slt"],
    [RCmp.LE, "sle"],
    [RCmp.GT, "sgt"],
    [RCmp.GE, "sge"],
  ];
  for (const [op, mlirPred] of preds) {
    const k = new Kernel();
    const root = cmpNode(k, op, k.internTrivialInt(1), k.internTrivialInt(2));
    const out = emit(k, root);
    assertMatches(
      out.text,
      new RegExp(`arith\\.cmpi\\s+${mlirPred},`),
      `cmpi ${mlirPred}`,
    );
  }
});

// ---------------------------------------------------------------------------
// 5. arith dialect — logic on i1
// ---------------------------------------------------------------------------

test("emit: logic AND/OR/NOT lower to andi/ori/xori on i1", () => {
  const k = new Kernel();
  const c1 = cmpNode(k, RCmp.LT, k.internTrivialInt(1), k.internTrivialInt(2));
  const c2 = cmpNode(k, RCmp.GT, k.internTrivialInt(5), k.internTrivialInt(3));
  const andNode = logicNode(k, RLogic.AND, [c1, c2]);
  const orNode = logicNode(k, RLogic.OR, [c1, c2]);
  const notNode = logicNode(k, RLogic.NOT, [c1]);

  const aOut = emit(k, andNode);
  assertMatches(aOut.text, /arith\.andi\s+%\w+,\s*%\w+\s*:\s*i1/, "andi");

  const oOut = emit(k, orNode);
  assertMatches(oOut.text, /arith\.ori\s+%\w+,\s*%\w+\s*:\s*i1/, "ori");

  const nOut = emit(k, notNode);
  assertMatches(nOut.text, /arith\.xori\s+%\w+,\s*%\w+\s*:\s*i1/, "xori (not)");
});

// ---------------------------------------------------------------------------
// 6. scf dialect — conditional
// ---------------------------------------------------------------------------

test("emit: COND IF_THEN_ELSE lowers to scf.if with both branches", () => {
  const k = new Kernel();
  const cond = cmpNode(k, RCmp.LT, k.internTrivialInt(1), k.internTrivialInt(2));
  const thenE = k.internTrivialInt(10);
  const elseE = k.internTrivialInt(20);
  const root = ifElse(k, cond, thenE, elseE);
  const out = emit(k, root);

  assertMatches(out.text, /scf\.if\s+%\w+\s+->\s+\(i32\)\s*\{/, "scf.if header");
  assertContains(out.text, "} else {", "else branch");
  assertMatches(out.text, /scf\.yield\s+%\w+\s*:\s*i32/, "scf.yield");
});

test("emit: COND IF_THEN (no else) still produces yieldable scf.if", () => {
  const k = new Kernel();
  const cond = cmpNode(k, RCmp.EQ, k.internTrivialInt(0), k.internTrivialInt(0));
  const thenE = k.internTrivialInt(7);
  const root = k.intern(basicCat(k, RBasic.COND, RCond.IF_THEN), [cond, thenE]);
  const out = emit(k, root);

  assertMatches(out.text, /scf\.if\s+%\w+\s+->\s+\(i32\)/, "scf.if header");
  // Both branches still yield i32 — the else branch yields a 0 fallback.
  const yields = out.text.match(/scf\.yield/g) ?? [];
  if (yields.length < 2) {
    throw new Error(`expected at least 2 scf.yield ops, got ${yields.length}`);
  }
});

// ---------------------------------------------------------------------------
// 7. func dialect — function definition + call
// ---------------------------------------------------------------------------

test("emit: FNDEF emits a module-scope func.func with @symbol", () => {
  const k = new Kernel();
  const body = mathNode(k, RMath.PLUS, [ident(k, "x"), k.internTrivialInt(1)]);
  const inc = fndef(k, "inc", ["x"], body);
  const callInc = fncall(k, "inc", [k.internTrivialInt(41)]);
  const root = block(k, RBlock.SEQUENCE, [inc, callInc]);
  const out = emit(k, root);

  assertMatches(
    out.text,
    /func\.func @inc\(%arg0:\s*i32\)\s*->\s*i32\s*\{/,
    "inc signature",
  );
  assertMatches(out.text, /return\s+%r\d+\s*:\s*i32/, "inc return");
  assertMatches(
    out.text,
    /func\.call\s+@inc\(%c\d+\)\s*:\s*\(i32\)\s*->\s*i32/,
    "func.call @inc",
  );
});

// ---------------------------------------------------------------------------
// 8. vector dialect — direct VECTOR recipe (when constant available)
// ---------------------------------------------------------------------------

test("emit: VECTOR recipe lowers to vector.from_elements when present", () => {
  // PR #9 introduces RBasic.VECTOR. On this branch the constant may not
  // exist; mutate the constant locally so the duck-typed extension path
  // exercises the vector dialect emit. This is purely a test fixture.
  const tweaked = RBasic as unknown as Record<string, number | undefined>;
  const had = "VECTOR" in tweaked;
  if (!had) {
    (tweaked as Record<string, number>).VECTOR = 90; // experimental code
  }
  try {
    const k = new Kernel();
    // VECTOR cat carries width in cat.inst; lane children are float constants.
    // We don't have float trivials on the substrate yet; use int trivials
    // — the emit-extension path treats them as float lanes with sitofp.
    const widthCat: NodeID = {
      pkg: 1,
      level: Level.BASIC,
      type: (RBasic as unknown as Record<string, number>).VECTOR!,
      inst: 4,
    };
    const lanes = [1, 2, 3, 4].map((n) => k.internTrivialInt(n));
    const vec = k.intern(widthCat, lanes);
    const out = emit(k, vec);
    assertMatches(
      out.text,
      /vector\.from_elements\s+.*\s*:\s*vector<4x(f16|f32|f64)>/,
      "vector.from_elements",
    );
  } finally {
    if (!had) {
      delete (tweaked as Record<string, number | undefined>).VECTOR;
    }
  }
});

test("emit: VECTORIZE pattern lowers to linalg.generic", () => {
  const tweaked = RBasic as unknown as Record<string, number | undefined>;
  const had = "VECTORIZE" in tweaked;
  if (!had) {
    (tweaked as Record<string, number>).VECTORIZE = 91;
  }
  try {
    const k = new Kernel();
    const inner = mathNode(k, RMath.PLUS, [
      k.internTrivialInt(1),
      k.internTrivialInt(2),
    ]);
    const vCat: NodeID = {
      pkg: 1,
      level: Level.BASIC,
      type: (RBasic as unknown as Record<string, number>).VECTORIZE!,
      inst: 8,
    };
    const node = k.intern(vCat, [inner]);
    const out = emit(k, node);
    assertMatches(out.text, /linalg\.generic/, "linalg.generic");
    assertMatches(out.text, /iterator_types\s*=\s*\["parallel"\]/, "parallel iter");
    assertMatches(out.text, /simd_width\s*=\s*8/, "simd_width 8");
    assertMatches(out.text, /vector<8x(f16|f32|f64)>/, "vector type");
  } finally {
    if (!had) {
      delete (tweaked as Record<string, number | undefined>).VECTORIZE;
    }
  }
});

// ---------------------------------------------------------------------------
// 9. Composition — multi-dialect module shape
// ---------------------------------------------------------------------------

test("emit: full module — arith + scf + func compose into one .mlir", () => {
  // fact(n) ⇒ if n <= 1 then 1 else n * fact(n-1)
  const k = new Kernel();
  const n = ident(k, "n");
  const one = k.internTrivialInt(1);
  const cmp = cmpNode(k, RCmp.LE, n, one);
  const nm1 = mathNode(k, RMath.MINUS, [n, one]);
  const rec = fncall(k, "fact", [nm1]);
  const mul = mathNode(k, RMath.MUL, [n, rec]);
  const body = ifElse(k, cmp, one, mul);
  const fact = fndef(k, "fact", ["n"], body);
  const call5 = fncall(k, "fact", [k.internTrivialInt(5)]);
  const root = block(k, RBlock.SEQUENCE, [fact, call5]);
  const out = emit(k, root);

  // Module wrapping
  assertContains(out.text, "module @form_module {", "module header");
  // Dialects present
  assertMatches(out.text, /func\.func @fact/, "fact func");
  assertMatches(out.text, /func\.func @form_root/, "form_root");
  assertMatches(out.text, /arith\.cmpi\s+sle/, "cmpi sle");
  assertMatches(out.text, /arith\.subi/, "subi");
  assertMatches(out.text, /arith\.muli/, "muli");
  assertMatches(out.text, /scf\.if\s+%\w+\s+->\s+\(i32\)/, "scf.if");
  assertMatches(out.text, /func\.call\s+@fact/, "recursive call");
});

// ---------------------------------------------------------------------------
// 10. LET binding flows into IDENT lookup
// ---------------------------------------------------------------------------

test("emit: LET binding reuses the bound SSA value on subsequent IDENT", () => {
  const k = new Kernel();
  const xVal = mathNode(k, RMath.PLUS, [
    k.internTrivialInt(2),
    k.internTrivialInt(3),
  ]);
  const letX = letNode(k, "x", xVal);
  const useX = mathNode(k, RMath.MUL, [ident(k, "x"), k.internTrivialInt(10)]);
  const root = block(k, RBlock.SEQUENCE, [letX, useX]);
  const out = emit(k, root);
  // The MUL's first operand should be the SSA value produced by the PLUS,
  // not a fresh constant. Find the muli line and check it references an %r.
  const muLine = out.text.split("\n").find((l) => l.includes("arith.muli"));
  if (!muLine) throw new Error("no muli line emitted");
  assertMatches(muLine, /arith\.muli\s+%r\d+,\s*%c\d+\s*:\s*i32/, "muli reuses %r");
});

// ---------------------------------------------------------------------------
// 11. MLIR text structure — global regex sanity
// ---------------------------------------------------------------------------

test("emit: MLIR text always begins with module @ and ends with closing brace", () => {
  const k = new Kernel();
  const root = k.internTrivialInt(0);
  const out = emit(k, root);
  if (!/^module @\w+ \{/.test(out.text)) {
    throw new Error(`bad header:\n${out.text}`);
  }
  if (!/\}\s*$/.test(out.text)) {
    throw new Error(`bad footer:\n${out.text}`);
  }
});

test("emit: every emitted line that defines an SSA value uses %-prefixed names", () => {
  const k = new Kernel();
  const a = k.internTrivialInt(1);
  const b = k.internTrivialInt(2);
  const c = k.internTrivialInt(3);
  const root = mathNode(k, RMath.PLUS, [a, b, c]);
  const out = emit(k, root);
  for (const line of out.text.split("\n")) {
    const trimmed = line.trim();
    // Lines that contain ` = arith.` are SSA-defining; their LHS must start
    // with %.
    if (/=\s+arith\./.test(trimmed)) {
      if (!/^%[A-Za-z0-9_]+\s*=/.test(trimmed)) {
        throw new Error(`non-%-prefixed SSA defn: ${trimmed}`);
      }
    }
  }
});

// ---------------------------------------------------------------------------
// Done
// ---------------------------------------------------------------------------

process.stdout.write(`\n${passed} passed, ${failed} failed\n`);
if (failed > 0) process.exit(1);
