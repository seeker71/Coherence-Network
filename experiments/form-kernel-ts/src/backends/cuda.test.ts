// Smoke tests for the CUDA emit backend.
//
// Uses Node's built-in test runner (node:test) — no extra deps. Run with:
//   npx tsx --test src/backends/cuda.test.ts
//
// The tests verify *string shape* of the emit, not GPU execution. They
// confirm:
//   • A __global__ kernel function gets emitted for each recipe
//   • Arithmetic on FP32 uses native operators
//   • Arithmetic on FP16 uses __hadd / __hmul intrinsics
//   • LIST literals pack into float4 / half2
//   • A length-3 MUL on FP16 triggers the Tensor Core path (wmma::mma_sync)
//   • PARALLELIZE binds threadIdx/blockIdx
//   • VECTORIZE binds __ldg with a 4-wide load
//   • target_hints contains the two expected hint strings

import { strict as assert } from "node:assert";
import { test } from "node:test";

import {
  Kernel,
  Level,
  RBasic,
  RBlock,
  RMath,
  Triv,
  type NodeID,
} from "../kernel.ts";
import { CudaBackend } from "./cuda.ts";

// Helpers — build category and recipe nodes the way the reader / compiler
// would, but without dragging the S-expr reader into the test.

function cat(level: number, type: number, inst = 0): NodeID {
  return { pkg: 1, level, type, inst };
}

function intern(
  k: Kernel,
  categoryNode: NodeID,
  children: readonly NodeID[],
): NodeID {
  return k.intern(categoryNode, children);
}

function mathPlus(k: Kernel, kids: NodeID[]): NodeID {
  return intern(k, cat(Level.BASIC, RBasic.MATH, RMath.PLUS), kids);
}

function mathMul(k: Kernel, kids: NodeID[]): NodeID {
  return intern(k, cat(Level.BASIC, RBasic.MATH, RMath.MUL), kids);
}

function listNode(k: Kernel, kids: NodeID[]): NodeID {
  return intern(k, cat(Level.BASIC, RBasic.LIST, 0), kids);
}

function block(k: Kernel, op: number, kids: NodeID[]): NodeID {
  return intern(k, cat(Level.BASIC, RBasic.BLOCK, op), kids);
}

// PARALLELIZE / VECTORIZE — reserved RBlock instances 8 and 9.
const RBLOCK_PARALLELIZE = 8;
const RBLOCK_VECTORIZE = 9;

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test("CudaBackend identity — name and target_hints", () => {
  assert.equal(CudaBackend.name, "cuda");
  assert.equal(CudaBackend.target_hints.has("gpu-cuda"), true);
  assert.equal(CudaBackend.target_hints.has("gpu-cuda-tensorcore"), true);
  assert.equal(CudaBackend.target_hints.size, 2);
});

test("emits a __global__ kernel function and dispatch hint", () => {
  const k = new Kernel();
  const expr = mathPlus(k, [k.internTrivialInt(1), k.internTrivialInt(2)]);
  const src = CudaBackend.emit(k, expr);
  assert.match(src, /__global__ void form_kernel\(/);
  assert.match(src, /<<<dim3\(1, 1, 1\), dim3\(32, 1, 1\)>>>/);
  assert.match(src, /#include <cuda_runtime\.h>/);
  assert.match(src, /__form_result/);
});

test("kernel name and launch shape come from opts", () => {
  const k = new Kernel();
  const expr = mathPlus(k, [k.internTrivialInt(1), k.internTrivialInt(2)]);
  const src = CudaBackend.emit(k, expr, {
    kernel_name: "saxpy",
    grid: [256, 1, 1],
    block: [128, 1, 1],
  });
  assert.match(src, /__global__ void saxpy\(/);
  assert.match(src, /<<<dim3\(256, 1, 1\), dim3\(128, 1, 1\)>>>/);
});

test("FP32 arithmetic uses native operators", () => {
  const k = new Kernel();
  const expr = mathPlus(k, [k.internTrivialInt(2), k.internTrivialInt(3)]);
  const src = CudaBackend.emit(k, expr);
  assert.match(src, /2\.0f.*\+.*3\.0f/s);
  // No FP16 intrinsics on the default path
  assert.equal(src.includes("__hadd"), false);
});

test("FP16 arithmetic uses __hadd / __hmul intrinsics", () => {
  const k = new Kernel();
  const a = k.internTrivialInt(2);
  const b = k.internTrivialInt(3);
  const expr = mathMul(k, [a, b]);
  const src = CudaBackend.emit(k, expr, { dtype: "fp16", tensor_core: false });
  assert.match(src, /#include <cuda_fp16\.h>/);
  assert.match(src, /__hmul\(/);
  assert.match(src, /__float2half\(2\.0f\)/);
});

test("FP16 MUL with 3-arg form emits Tensor Core mma fragment", () => {
  const k = new Kernel();
  const a = k.internTrivialInt(1);
  const b = k.internTrivialInt(2);
  const c = k.internTrivialInt(3);
  const expr = mathMul(k, [a, b, c]);
  const src = CudaBackend.emit(k, expr, { dtype: "fp16" });
  assert.match(src, /#include <mma\.h>/);
  assert.match(src, /using namespace nvcuda;/);
  assert.match(src, /wmma::fragment<wmma::matrix_a/);
  assert.match(src, /wmma::mma_sync\(/);
});

test("FP8 dtype pulls in fp8 header", () => {
  const k = new Kernel();
  const expr = mathPlus(k, [k.internTrivialInt(1), k.internTrivialInt(2)]);
  const src = CudaBackend.emit(k, expr, { dtype: "fp8" });
  assert.match(src, /#include <cuda_fp8\.h>/);
});

test("LIST of 4 floats packs into make_float4", () => {
  const k = new Kernel();
  const expr = listNode(k, [
    k.internTrivialInt(1),
    k.internTrivialInt(2),
    k.internTrivialInt(3),
    k.internTrivialInt(4),
  ]);
  const src = CudaBackend.emit(k, expr);
  assert.match(src, /make_float4\(1\.0f, 2\.0f, 3\.0f, 4\.0f\)/);
});

test("LIST of 2 halves packs into __halves2half2", () => {
  const k = new Kernel();
  const expr = listNode(k, [k.internTrivialInt(1), k.internTrivialInt(2)]);
  const src = CudaBackend.emit(k, expr, { dtype: "fp16", tensor_core: false });
  assert.match(src, /__halves2half2\(/);
});

test("PARALLELIZE emits threadIdx / blockIdx binding", () => {
  const k = new Kernel();
  const body = mathPlus(k, [k.internTrivialInt(1), k.internTrivialInt(2)]);
  const par = block(k, RBLOCK_PARALLELIZE, [body]);
  const src = CudaBackend.emit(k, par);
  assert.match(src, /const int tid = threadIdx\.x;/);
  assert.match(src, /const int bid = blockIdx\.x;/);
  assert.match(src, /const int gid = blockIdx\.x \* blockDim\.x \+ threadIdx\.x;/);
  // Single-thread guard is dropped once a parallelize block appears
  assert.equal(src.includes("single-thread fallback"), false);
});

test("non-parallelized recipe gets a single-thread guard", () => {
  const k = new Kernel();
  const expr = mathPlus(k, [k.internTrivialInt(1), k.internTrivialInt(2)]);
  const src = CudaBackend.emit(k, expr);
  assert.match(src, /single-thread fallback/);
  assert.match(src, /if \(threadIdx\.x != 0 \|\| blockIdx\.x != 0\) return;/);
});

test("VECTORIZE binds __ldg with float4", () => {
  const k = new Kernel();
  const srcName = k.internString("input");
  const body = k.internTrivialInt(0);
  const vec = block(k, RBLOCK_VECTORIZE, [srcName, body]);
  const src = CudaBackend.emit(k, vec);
  assert.match(src, /__ldg\(reinterpret_cast<const float4\*>\(input\) \+ gid\)/);
});

test("VECTORIZE on fp16 uses half2", () => {
  const k = new Kernel();
  const srcName = k.internString("input");
  const body = k.internTrivialInt(0);
  const vec = block(k, RBLOCK_VECTORIZE, [srcName, body]);
  const src = CudaBackend.emit(k, vec, { dtype: "fp16", tensor_core: false });
  assert.match(src, /__ldg\(reinterpret_cast<const half2\*>\(input\) \+ gid\)/);
});

test("LET binding emits a typed declaration in the kernel body", () => {
  const k = new Kernel();
  const name = k.internString("x");
  const value = mathPlus(k, [k.internTrivialInt(1), k.internTrivialInt(2)]);
  const letNode = block(k, RBlock.LET, [name, value]);
  const src = CudaBackend.emit(k, letNode);
  assert.match(src, /float let_x_\d+ = /);
});

test("emit is a pure string — stable across repeated calls", () => {
  const k = new Kernel();
  const expr = mathPlus(k, [k.internTrivialInt(1), k.internTrivialInt(2)]);
  const a = CudaBackend.emit(k, expr);
  const b = CudaBackend.emit(k, expr);
  assert.equal(a, b);
});
