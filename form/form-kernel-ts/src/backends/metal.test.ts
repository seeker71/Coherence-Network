// Smoke tests for MetalBackend — exercise kernel emission shape, basic
// arithmetic, vector lane types, and the simdgroup_matrix bf16/fp16 path.
//
// Run via:
//     npx tsx --test src/backends/metal.test.ts

import { strict as assert } from "node:assert";
import { test } from "node:test";

import { Kernel } from "../kernel.ts";
import { readForm } from "../reader.ts";
import { MetalBackend } from "./metal.ts";

test("MetalBackend declares its target_hints", () => {
  assert.equal(MetalBackend.name, "metal");
  assert.ok(MetalBackend.target_hints.has("gpu-metal"));
  assert.ok(MetalBackend.target_hints.has("gpu-metal-simdgroup"));
  assert.equal(MetalBackend.target_hints.size, 2);
});

test("emits a scalar kernel with metal_stdlib header", () => {
  const k = new Kernel();
  const expr = readForm(k, "(+ 1 2)");
  const out = MetalBackend.emit(k, expr);

  assert.match(out.source, /#include <metal_stdlib>/);
  assert.match(out.source, /using namespace metal;/);
  assert.match(out.source, /kernel void form_kernel\(/);
  assert.match(out.source, /\[\[thread_position_in_grid\]\]/);
  // The arithmetic body should appear in the output assignment.
  assert.match(out.source, /\(float\(1\)\) \+ \(float\(2\)\)/);
  assert.equal(out.hasFallback, false);
  assert.equal(out.resolved.scalar, "float");
  assert.equal(out.resolved.vectorize, 1);
});

test("respects a custom kernel name", () => {
  const k = new Kernel();
  const expr = readForm(k, "(+ 1 2)");
  const out = MetalBackend.emit(k, expr, { name: "saxpy_step" });
  assert.match(out.source, /kernel void saxpy_step\(/);
});

test("grid parallelize emits thread_position_in_grid bounds check", () => {
  const k = new Kernel();
  const expr = readForm(k, "(+ 1 2)");
  const out = MetalBackend.emit(k, expr, {
    parallelize: { kind: "grid", size: 1024 },
  });
  assert.match(out.source, /if \(tid >= 1024\) return;/);
  assert.match(out.source, /out\[tid\] =/);
});

test("threadgroup parallelize exposes thread_position_in_threadgroup", () => {
  const k = new Kernel();
  const expr = readForm(k, "(+ 1 2)");
  const out = MetalBackend.emit(k, expr, {
    parallelize: { kind: "threadgroup", grid: 256, threadgroup: 32 },
  });
  assert.match(out.source, /\[\[thread_position_in_grid\]\]/);
  assert.match(out.source, /\[\[thread_position_in_threadgroup\]\]/);
  assert.match(out.source, /grid=256, threadgroup=32/);
});

test("inputs surface as device const* buffer params indexed by tid", () => {
  const k = new Kernel();
  const expr = readForm(k, "(+ a b)");
  const out = MetalBackend.emit(k, expr, {
    inputs: ["a", "b"],
    parallelize: { kind: "grid", size: 4 },
  });
  assert.match(out.source, /device const float\* a \[\[buffer\(0\)\]\]/);
  assert.match(out.source, /device const float\* b \[\[buffer\(1\)\]\]/);
  assert.match(out.source, /device float\* out \[\[buffer\(2\)\]\]/);
  assert.match(out.source, /\(a\[tid\]\) \+ \(b\[tid\]\)/);
  assert.equal(out.hasFallback, false);
});

test("vectorize=4 emits simd_float4 / simd_packed_float4 types", () => {
  const k = new Kernel();
  const expr = readForm(k, "(+ a b)");
  const out = MetalBackend.emit(k, expr, {
    scalar: "float",
    vectorize: 4,
    inputs: ["a", "b"],
    parallelize: { kind: "grid", size: 4 },
  });
  assert.match(out.source, /simd_packed_float4\*/);
});

test("vectorize=2 + half scalar emits simd_half2", () => {
  const k = new Kernel();
  const expr = readForm(k, "(* a b)");
  const out = MetalBackend.emit(k, expr, {
    scalar: "half",
    vectorize: 2,
    inputs: ["a", "b"],
    parallelize: { kind: "grid", size: 8 },
  });
  assert.match(out.source, /simd_packed_half2\*/);
});

test("simdgroup matrix path triggers for bfloat scalar", () => {
  const k = new Kernel();
  const expr = readForm(k, "(+ a b)");
  const out = MetalBackend.emit(k, expr, {
    scalar: "bfloat",
    simdgroupMatrix: true,
    inputs: ["a", "b"],
    parallelize: { kind: "threadgroup", grid: 64, threadgroup: 64 },
  });
  assert.match(out.source, /simdgroup_matrix<bfloat, 8, 8>/);
  assert.match(out.source, /threadgroup bfloat tg_scratch\[8 \* 8\];/);
  assert.equal(out.resolved.simdgroupMatrix, true);
});

test("simdgroup matrix path triggers for half scalar", () => {
  const k = new Kernel();
  const expr = readForm(k, "(* a b)");
  const out = MetalBackend.emit(k, expr, {
    scalar: "half",
    simdgroupMatrix: true,
    inputs: ["a", "b"],
    parallelize: { kind: "grid", size: 128 },
  });
  assert.match(out.source, /simdgroup_matrix<half, 8, 8>/);
});

test("simdgroup matrix path stays off for float scalar (no SIMD bf16/fp16)", () => {
  const k = new Kernel();
  const expr = readForm(k, "(+ a b)");
  const out = MetalBackend.emit(k, expr, {
    scalar: "float",
    simdgroupMatrix: true,
    inputs: ["a", "b"],
  });
  assert.equal(out.resolved.simdgroupMatrix, false);
  assert.doesNotMatch(out.source, /simdgroup_matrix/);
});

test("comparison ops emit C-style operators", () => {
  const k = new Kernel();
  const expr = readForm(k, "(< a b)");
  const out = MetalBackend.emit(k, expr, {
    scalar: "int",
    inputs: ["a", "b"],
    parallelize: { kind: "grid", size: 4 },
  });
  assert.match(out.source, /\(a\[tid\]\) < \(b\[tid\]\)/);
});

test("if/else emits ternary", () => {
  const k = new Kernel();
  const expr = readForm(k, "(if (< 1 2) 10 20)");
  const out = MetalBackend.emit(k, expr, { scalar: "int" });
  assert.match(out.source, /\? \(10\) : \(20\)/);
});

test("integer scalar path uses int literals (no float cast)", () => {
  const k = new Kernel();
  const expr = readForm(k, "(+ 1 2)");
  const out = MetalBackend.emit(k, expr, { scalar: "int" });
  // Should NOT contain a float() cast of integer literals.
  assert.doesNotMatch(out.source, /float\(1\)/);
  assert.match(out.source, /\(1\) \+ \(2\)/);
});

test("modulo on float scalar uses fmod()", () => {
  const k = new Kernel();
  const expr = readForm(k, "(mod a b)");
  const out = MetalBackend.emit(k, expr, {
    scalar: "float",
    inputs: ["a", "b"],
    parallelize: { kind: "grid", size: 4 },
  });
  assert.match(out.source, /fmod\(/);
});

test("modulo on int scalar uses % operator", () => {
  const k = new Kernel();
  const expr = readForm(k, "(mod a b)");
  const out = MetalBackend.emit(k, expr, {
    scalar: "int",
    inputs: ["a", "b"],
    parallelize: { kind: "grid", size: 4 },
  });
  assert.match(out.source, /\(a\[tid\]\) % \(b\[tid\]\)/);
});

test("local fn definition emits inline MSL function", () => {
  const k = new Kernel();
  const expr = readForm(
    k,
    "(do (defn sqr (x) (* x x)) (sqr a))",
  );
  const out = MetalBackend.emit(k, expr, {
    inputs: ["a"],
    parallelize: { kind: "grid", size: 4 },
  });
  assert.match(out.source, /inline float fn_/);
  // sqr is called inside the kernel body with a[tid] as argument.
  assert.match(out.source, /fn_\w+\(a\[tid\]\)/);
});

test("unsupported subtree produces a fallback marker and sets the flag", () => {
  const k = new Kernel();
  // A string literal has no MSL representation — should fall back.
  const expr = readForm(k, '"hello"');
  const out = MetalBackend.emit(k, expr);
  assert.match(out.source, /fallback: string trivial/);
  assert.equal(out.hasFallback, true);
});
