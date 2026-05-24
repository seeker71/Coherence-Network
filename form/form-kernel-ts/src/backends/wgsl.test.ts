// WGSL backend tests — Task #10.
//
// Run with: npx tsx --test src/backends/wgsl.test.ts
//
// Tests use Node's built-in test runner. The "WGSL parser" is a
// pragmatic regex-based syntax check — enough to catch obvious malformed
// output without dragging in a real WGSL compiler (naga, tint) as a
// dependency. The four shapes exercised are:
//
//   1. scalar add(a, b)              — plain fn
//   2. vector add(a, b) with vec4   — vectorized
//   3. parallelized buffer kernel   — @compute + workgroup dispatch
//   4. reduction kernel             — workgroupBarrier + tree-shuffle

import { test } from "node:test";
import { strict as assert } from "node:assert";
import { Kernel } from "../kernel.ts";
import { readForm } from "../reader.ts";
import { WgslBackend, type FormatRecipe } from "./wgsl.ts";

// ---------------------------------------------------------------------------
// Minimal WGSL syntax check — regex-based, catches the obvious failures
// ---------------------------------------------------------------------------
//
// A valid WGSL compute shader source for our emitted forms should:
//   • have matched braces and parens
//   • contain at least one `fn` declaration
//   • not have stray `undefined`, `NaN`, or unresolved templates
//   • have balanced angle brackets if vectors are emitted
//
// This is not a full parser; it's a guardrail against the easy mistakes
// the emitter could regress on.

function assertWgslShape(src: string): void {
  assert.match(src, /\bfn\s+\w+\s*\(/, "expected at least one fn declaration");
  // No JS-isms leaking through.
  assert.doesNotMatch(src, /\bundefined\b/, "stray 'undefined' in WGSL output");
  assert.doesNotMatch(src, /\bNaN\b/, "stray 'NaN' in WGSL output");
  assert.doesNotMatch(src, /\bnull\b/, "stray 'null' in WGSL output");
  // Brace balance.
  const opens = (src.match(/\{/g) ?? []).length;
  const closes = (src.match(/\}/g) ?? []).length;
  assert.equal(opens, closes, `brace mismatch: ${opens} open, ${closes} close`);
  // Paren balance.
  const pOpens = (src.match(/\(/g) ?? []).length;
  const pCloses = (src.match(/\)/g) ?? []).length;
  assert.equal(
    pOpens,
    pCloses,
    `paren mismatch: ${pOpens} open, ${pCloses} close`,
  );
  // Angle-bracket balance for vector/storage types — only count those
  // that show up as type-arg openers (preceded by a letter), to avoid
  // confusing them with comparison operators in arithmetic.
  const typeOpens = (src.match(/[A-Za-z_]</g) ?? []).length;
  const typeCloses = (src.match(/>/g) ?? []).length;
  // The closes count is fuzzy because `>` is also a comparison
  // operator. We just assert "closes >= opens" — every type-arg open
  // must be balanced by at least one `>`.
  assert.ok(
    typeCloses >= typeOpens,
    `angle-bracket type args unbalanced: opens=${typeOpens} closes=${typeCloses}`,
  );
}

// ---------------------------------------------------------------------------
// Shared fixtures
// ---------------------------------------------------------------------------

const FP32_SCALAR: FormatRecipe = { scalar: "f32", lanes: 1 };
const FP32_VEC4: FormatRecipe = { scalar: "f32", lanes: 4 };
const I32_SCALAR: FormatRecipe = { scalar: "i32", lanes: 1 };

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test("WgslBackend: target_hints includes gpu-webgpu", () => {
  assert.ok(
    WgslBackend.target_hints.has("gpu-webgpu"),
    "expected 'gpu-webgpu' in target_hints",
  );
  assert.equal(WgslBackend.name, "wgsl");
});

test("emits a simple add(a, b) recipe as a scalar fn", () => {
  const k = new Kernel();
  // (defn add (a b) (+ a b))  then call add — but the backend takes the
  // body recipe directly, with params named "a", "b" via opts.params.
  const recipe = readForm(k, "(+ a b)");
  const src = WgslBackend.emit(k, recipe, {
    params: ["a", "b"],
    return_format: FP32_SCALAR,
  });
  assertWgslShape(src);
  // Expect the two parameters to show up in a fn signature.
  assert.match(
    src,
    /fn\s+kernel_main\s*\(\s*p_a_\d+:\s*f32\s*,\s*p_b_\d+:\s*f32\s*\)\s*->\s*f32/,
    "expected 'fn kernel_main(p_a, p_b: f32) -> f32' signature",
  );
  // Body should contain the addition (parenthesisation allowed).
  assert.match(src, /p_a_\d+\)\s*\+\s*\(p_b_\d+/);
});

test("emits a recipe with i32 format using i32 types", () => {
  const k = new Kernel();
  const recipe = readForm(k, "(+ a 1)");
  const src = WgslBackend.emit(k, recipe, {
    params: ["a"],
    return_format: I32_SCALAR,
  });
  assertWgslShape(src);
  assert.match(src, /->\s*i32/, "expected i32 return type");
  assert.match(src, /p_a_\d+:\s*i32/, "expected i32 parameter");
});

test("vectorize lifts scalar add to vec4 arithmetic", () => {
  const k = new Kernel();
  const recipe = readForm(k, "(+ a b)");
  const src = WgslBackend.emit(k, recipe, {
    params: ["a", "b"],
    vectorize: { format: FP32_VEC4 },
  });
  assertWgslShape(src);
  // The fn signature should use vec4<f32>.
  assert.match(
    src,
    /fn\s+kernel_vec\s*\(\s*p_a_\d+:\s*vec4<f32>\s*,\s*p_b_\d+:\s*vec4<f32>\s*\)\s*->\s*vec4<f32>/,
    "expected vec4<f32> parameters and return",
  );
  assert.match(src, /\/\/ vectorize lanes=4/);
});

test("vectorize lanes=8 chunks to vec4 with a comment", () => {
  const k = new Kernel();
  const recipe = readForm(k, "(+ a b)");
  const src = WgslBackend.emit(k, recipe, {
    params: ["a", "b"],
    vectorize: { format: { scalar: "f32", lanes: 8 } },
  });
  assertWgslShape(src);
  assert.match(src, /\/\/ vectorize lanes=8 → emitted as vec4 chunks/);
  assert.match(src, /vec4<f32>/);
});

test("parallelize emits @compute dispatch with workgroup_size", () => {
  const k = new Kernel();
  // Body is `x * 2` — applied per element across the input buffer.
  const recipe = readForm(k, "(* x 2)");
  const src = WgslBackend.emit(k, recipe, {
    params: ["x"],
    parallelize: {
      workgroup_size: [64, 1, 1],
      buffer_format: FP32_SCALAR,
    },
  });
  assertWgslShape(src);
  assert.match(src, /@compute\s+@workgroup_size\(64,\s*1,\s*1\)/);
  assert.match(src, /@builtin\(global_invocation_id\)/);
  assert.match(src, /array<f32>/);
  assert.match(src, /@group\(0\)\s+@binding\(0\)/);
  assert.match(src, /@group\(0\)\s+@binding\(1\)/);
  assert.match(src, /out_buf\[idx\]\s*=\s*kernel_body/);
});

test("tile pattern emits workgroup-shared array and barrier", () => {
  const k = new Kernel();
  const recipe = readForm(k, "(* x 3)");
  const src = WgslBackend.emit(k, recipe, {
    params: ["x"],
    tile: { tile_size: 32, format: FP32_SCALAR },
  });
  assertWgslShape(src);
  assert.match(
    src,
    /var<workgroup>\s+tile:\s*array<f32,\s*32>/,
    "expected workgroup-shared tile array",
  );
  assert.match(src, /workgroupBarrier\(\)/);
  assert.match(src, /@workgroup_size\(32\)/);
});

test("reduce pattern emits tree-shuffle in workgroup memory", () => {
  const k = new Kernel();
  // The per-element body is identity: just (+ x 0) to exercise the
  // emitter without depending on parser nuances.
  const recipe = readForm(k, "(+ x 0)");
  const src = WgslBackend.emit(k, recipe, {
    params: ["x"],
    reduce: {
      op: "add",
      format: FP32_SCALAR,
      workgroup_size: 64,
    },
  });
  assertWgslShape(src);
  assert.match(src, /var<workgroup>\s+partial:\s*array<f32,\s*64>/);
  assert.match(src, /workgroupBarrier\(\)/);
  assert.match(src, /fn\s+combine\s*\(a:\s*f32,\s*b:\s*f32\)/);
  assert.match(src, /a\s*\+\s*b/);
  assert.match(src, /stride\s*>>\s*1u/);
  assert.match(src, /@workgroup_size\(64\)/);
});

test("reduce with op=max emits max() combine", () => {
  const k = new Kernel();
  const recipe = readForm(k, "(+ x 0)");
  const src = WgslBackend.emit(k, recipe, {
    params: ["x"],
    reduce: { op: "max", format: FP32_SCALAR, workgroup_size: 32 },
  });
  assertWgslShape(src);
  assert.match(src, /return\s+max\(a,\s*b\);/);
});

test("FP64 throws — WGSL does not support f64", () => {
  const k = new Kernel();
  const recipe = readForm(k, "(+ a b)");
  assert.throws(
    () =>
      WgslBackend.emit(k, recipe, {
        params: ["a", "b"],
        return_format: { scalar: "f64", lanes: 1 },
      }),
    /f64 is not natively supported/,
  );
});

test("conditional emits select() expression", () => {
  const k = new Kernel();
  // (if (< a b) a b) — pick the smaller of two
  const recipe = readForm(k, "(if (< a b) a b)");
  const src = WgslBackend.emit(k, recipe, {
    params: ["a", "b"],
    return_format: FP32_SCALAR,
  });
  assertWgslShape(src);
  assert.match(src, /select\(/, "expected select() for COND");
});

test("FNDEF lifts inner function declarations", () => {
  const k = new Kernel();
  // (do (defn double (x) (* x 2)) (double 21))
  const recipe = readForm(k, "(do (defn double (x) (* x 2)) (double 21))");
  const src = WgslBackend.emit(k, recipe, {
    return_format: FP32_SCALAR,
  });
  assertWgslShape(src);
  // The inner fn declaration should be lifted to its own `fn`.
  assert.match(src, /fn\s+fn_double_\d+\s*\(\s*p_x_\d+:\s*f32\s*\)\s*->\s*f32/);
  assert.match(src, /fn_double_\d+\(\s*21\.0\s*\)/);
});

test("WGSL builtin (sqrt x) maps through directly", () => {
  const k = new Kernel();
  const recipe = readForm(k, "(sqrt x)");
  const src = WgslBackend.emit(k, recipe, {
    params: ["x"],
    return_format: FP32_SCALAR,
  });
  assertWgslShape(src);
  assert.match(src, /sqrt\(p_x_\d+\)/);
});

test("unsupported native raises a clear error", () => {
  const k = new Kernel();
  // `print` has no WGSL analog (no I/O surface in compute shaders).
  const recipe = readForm(k, "(print 1)");
  assert.throws(
    () => WgslBackend.emit(k, recipe, { return_format: FP32_SCALAR }),
    /print.*has no WGSL analog/,
  );
});
