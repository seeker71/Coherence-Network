// Tests for the WASM SIMD emit backend.
//
// Standalone runnable via `tsx src/backends/wasm.test.ts`. Same harness
// pattern as vector.test.ts — each `test(...)` throws on failure, first
// failure aborts.
//
// We assert on the emitted WAT structure via regex — the backend's job
// is to produce well-formed WAT, not to round-trip through a binary
// toolchain. Cross-target structural checks (does an i32.add appear
// where we expect, does a v128.f32x4.add appear when we VECTORIZE) keep
// the backend honest without pulling in wat2wasm.

import {
  Kernel,
  Level,
  RBasic,
  RBlock,
  RCond,
  RMath,
  Triv,
  type NodeID,
} from "../kernel.ts";
import { buildFormatLibrary } from "../formats.ts";
import { makeVectorFormat } from "../vector.ts";
import { vectorize } from "../parallel.ts";
import { WasmSimdBackend } from "./wasm.ts";

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

function assertMatch(actual: string, pattern: RegExp, msg = ""): void {
  if (!pattern.test(actual)) {
    throw new Error(
      `${msg ? msg + ": " : ""}expected /${pattern.source}/ to match, got:\n${actual}`,
    );
  }
}

function assertEq<T>(actual: T, expected: T, msg = ""): void {
  if (actual !== expected) {
    throw new Error(
      `${msg ? msg + ": " : ""}expected ${JSON.stringify(String(expected))}, got ${JSON.stringify(String(actual))}`,
    );
  }
}

// ---------------------------------------------------------------------------
// Helpers — minimal Form recipe constructors via the kernel.
// ---------------------------------------------------------------------------

function mathRecipe(k: Kernel, op: number, ...args: NodeID[]): NodeID {
  return k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.MATH, inst: op },
    args,
  );
}

function condRecipe(k: Kernel, op: number, ...args: NodeID[]): NodeID {
  return k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.COND, inst: op },
    args,
  );
}

function blockRecipe(k: Kernel, op: number, ...args: NodeID[]): NodeID {
  return k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.BLOCK, inst: op },
    args,
  );
}

function fnDefRecipe(
  k: Kernel,
  name: string,
  params: string[],
  body: NodeID,
): NodeID {
  const paramsBlock = k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.BLOCK, inst: RBlock.SEQUENCE },
    params.map((p) => k.internString(p)),
  );
  return k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.FNDEF, inst: 0 },
    [k.internString(name), paramsBlock, body],
  );
}

function fnCallRecipe(k: Kernel, name: string, ...args: NodeID[]): NodeID {
  return k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.FNCALL, inst: 0 },
    [k.internString(name), ...args],
  );
}

function identRecipe(k: Kernel, name: string): NodeID {
  return k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.IDENT, inst: 0 },
    [k.internString(name)],
  );
}

// ---------------------------------------------------------------------------
// 1. Backend identity
// ---------------------------------------------------------------------------

test("backend declares wasm-simd target hint", () => {
  assertEq(WasmSimdBackend.name, "wasm-simd");
  assertEq(WasmSimdBackend.target_hints.has("wasm-simd"), true);
});

// ---------------------------------------------------------------------------
// 2. Module skeleton
// ---------------------------------------------------------------------------

test("emit wraps body in a (module ...) with $main export", () => {
  const k = new Kernel();
  const expr = k.internTrivialInt(42);
  const wat = WasmSimdBackend.emit(k, expr);
  assertMatch(wat, /^\(module/m);
  assertMatch(wat, /\(func \$main \(export "main"\) \(result i32\)/);
  assertMatch(wat, /\(i32\.const 42\)/);
});

// ---------------------------------------------------------------------------
// 3. Scalar math
// ---------------------------------------------------------------------------

test("MATH.PLUS emits i32.add", () => {
  const k = new Kernel();
  const expr = mathRecipe(
    k,
    RMath.PLUS,
    k.internTrivialInt(2),
    k.internTrivialInt(3),
  );
  const wat = WasmSimdBackend.emit(k, expr);
  assertMatch(wat, /\(i32\.add \(i32\.const 2\) \(i32\.const 3\)\)/);
});

test("MATH.MINUS / MUL / DIV / MOD emit corresponding i32 opcodes", () => {
  const k = new Kernel();
  const a = k.internTrivialInt(10);
  const b = k.internTrivialInt(3);
  const sub = WasmSimdBackend.emit(k, mathRecipe(k, RMath.MINUS, a, b));
  const mul = WasmSimdBackend.emit(k, mathRecipe(k, RMath.MUL, a, b));
  const div = WasmSimdBackend.emit(k, mathRecipe(k, RMath.DIV, a, b));
  const mod = WasmSimdBackend.emit(k, mathRecipe(k, RMath.MOD, a, b));
  assertMatch(sub, /\(i32\.sub/);
  assertMatch(mul, /\(i32\.mul/);
  assertMatch(div, /\(i32\.div_s/);
  assertMatch(mod, /\(i32\.rem_s/);
});

test("left-fold of >2 args composes nested ops", () => {
  const k = new Kernel();
  const expr = mathRecipe(
    k,
    RMath.PLUS,
    k.internTrivialInt(1),
    k.internTrivialInt(2),
    k.internTrivialInt(3),
  );
  const wat = WasmSimdBackend.emit(k, expr);
  // ((1 + 2) + 3) — outer add wraps inner add
  assertMatch(
    wat,
    /\(i32\.add \(i32\.add \(i32\.const 1\) \(i32\.const 2\)\) \(i32\.const 3\)\)/,
  );
});

// ---------------------------------------------------------------------------
// 4. Conditional
// ---------------------------------------------------------------------------

test("COND.IF_THEN_ELSE emits a WAT if/else with (result i32)", () => {
  const k = new Kernel();
  const expr = condRecipe(
    k,
    RCond.IF_THEN_ELSE,
    k.internTrivialBool(true),
    k.internTrivialInt(1),
    k.internTrivialInt(2),
  );
  const wat = WasmSimdBackend.emit(k, expr);
  assertMatch(
    wat,
    /\(if \(result i32\) \(i32\.const 1\) \(then \(i32\.const 1\)\) \(else \(i32\.const 2\)\)\)/,
  );
});

test("COND.IF_THEN supplies a zero else branch", () => {
  const k = new Kernel();
  const expr = condRecipe(
    k,
    RCond.IF_THEN,
    k.internTrivialBool(false),
    k.internTrivialInt(7),
  );
  const wat = WasmSimdBackend.emit(k, expr);
  assertMatch(
    wat,
    /\(if \(result i32\) \(i32\.const 0\) \(then \(i32\.const 7\)\) \(else \(i32\.const 0\)\)\)/,
  );
});

// ---------------------------------------------------------------------------
// 5. Block / let
// ---------------------------------------------------------------------------

test("BLOCK.LET declares a local and set/get-reads it", () => {
  const k = new Kernel();
  const letExpr = blockRecipe(
    k,
    RBlock.LET,
    k.internString("x"),
    k.internTrivialInt(99),
  );
  const wat = WasmSimdBackend.emit(k, letExpr);
  // A local declaration and a (local.set ...) / (local.get ...) pair
  assertMatch(wat, /\(local \$let_/);
  assertMatch(wat, /\(local\.set \$let_/);
  assertMatch(wat, /\(local\.get \$let_/);
  assertMatch(wat, /\(i32\.const 99\)/);
});

// ---------------------------------------------------------------------------
// 6. FNDEF + FNCALL
// ---------------------------------------------------------------------------

test("FNDEF hoists to module-level (func ...) with parameters", () => {
  const k = new Kernel();
  // defn add(a, b) = a + b
  const body = mathRecipe(
    k,
    RMath.PLUS,
    identRecipe(k, "a"),
    identRecipe(k, "b"),
  );
  const fn = fnDefRecipe(k, "add", ["a", "b"], body);
  const wat = WasmSimdBackend.emit(k, fn);
  // Module-level func declaration for add
  assertMatch(wat, /\(func \$fn_add_\d+ \(param \$p_a_\d+ i32\) \(param \$p_b_\d+ i32\) \(result i32\)/);
  // Body references the parameter locals via local.get
  assertMatch(wat, /\(i32\.add \(local\.get \$p_a_\d+\) \(local\.get \$p_b_\d+\)\)/);
});

test("FNCALL emits (call $fn_... args)", () => {
  const k = new Kernel();
  const body = mathRecipe(
    k,
    RMath.PLUS,
    identRecipe(k, "a"),
    identRecipe(k, "b"),
  );
  const seq = blockRecipe(
    k,
    RBlock.SEQUENCE,
    fnDefRecipe(k, "add", ["a", "b"], body),
    fnCallRecipe(k, "add", k.internTrivialInt(4), k.internTrivialInt(5)),
  );
  const wat = WasmSimdBackend.emit(k, seq);
  assertMatch(wat, /\(call \$fn_add_\d+ \(i32\.const 4\) \(i32\.const 5\)\)/);
});

// ---------------------------------------------------------------------------
// 7. SIMD vectorization
// ---------------------------------------------------------------------------

test("VECTORIZE(MATH.PLUS, 4) emits v128 f32x4.add with splatted scalars", () => {
  const k = new Kernel();
  const add = mathRecipe(
    k,
    RMath.PLUS,
    k.internTrivialInt(1),
    k.internTrivialInt(2),
  );
  const vec = vectorize(k, add, 4);
  const wat = WasmSimdBackend.emit(k, vec);
  assertMatch(wat, /\(f32x4\.add /);
  assertMatch(wat, /\(f32x4\.splat \(i32\.const 1\)\)/);
  assertMatch(wat, /\(f32x4\.splat \(i32\.const 2\)\)/);
});

test("VECTORIZE width=2 picks f64x2 shape", () => {
  const k = new Kernel();
  const add = mathRecipe(
    k,
    RMath.PLUS,
    k.internTrivialInt(1),
    k.internTrivialInt(2),
  );
  const vec = vectorize(k, add, 2);
  const wat = WasmSimdBackend.emit(k, vec);
  assertMatch(wat, /\(f64x2\.add /);
});

test("VECTORIZE width=8 falls to i32 lane integer shape", () => {
  const k = new Kernel();
  const mul = mathRecipe(
    k,
    RMath.MUL,
    k.internTrivialInt(3),
    k.internTrivialInt(4),
  );
  const vec = vectorize(k, mul, 8);
  const wat = WasmSimdBackend.emit(k, vec);
  // width=8 with i32 element falls through to i16x8 SIMD lane shape
  assertMatch(wat, /\(i16x8\.mul /);
});

test("VECTOR-format leaf emits a v128.const placeholder", () => {
  const k = new Kernel();
  const lib = buildFormatLibrary(k);
  const vfmt = makeVectorFormat(k, lib.FP32, 4, "wasm-simd");
  const wat = WasmSimdBackend.emit(k, vfmt.nodeID);
  assertMatch(wat, /v128\.const i32x4 0 0 0 0/);
  assertMatch(wat, /vector width=4 hint=wasm-simd/);
});

// ---------------------------------------------------------------------------
// 8. Structure: well-formed module
// ---------------------------------------------------------------------------

test("emitted WAT has balanced parens (basic well-formedness)", () => {
  const k = new Kernel();
  const body = mathRecipe(
    k,
    RMath.PLUS,
    identRecipe(k, "a"),
    identRecipe(k, "b"),
  );
  const seq = blockRecipe(
    k,
    RBlock.SEQUENCE,
    fnDefRecipe(k, "add", ["a", "b"], body),
    fnCallRecipe(k, "add", k.internTrivialInt(40), k.internTrivialInt(2)),
  );
  const wat = WasmSimdBackend.emit(k, seq);
  let depth = 0;
  for (const ch of wat) {
    if (ch === "(") depth++;
    else if (ch === ")") depth--;
    if (depth < 0) throw new Error("unbalanced: extra )");
  }
  assertEq(depth, 0, "module-level paren balance");
});

// ---------------------------------------------------------------------------

process.stdout.write(`\n${passed} passed, ${failed} failed\n`);
if (failed > 0) process.exit(1);
