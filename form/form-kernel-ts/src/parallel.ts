// parallel.ts — high-level parallel pattern recipes (TILE, PARALLELIZE,
// VECTORIZE).
//
// These are recipe-level annotations the compiler reads to dispatch into
// the target's native parallel primitive. They DON'T change semantics —
// the inner op stays the same. They DO change emission:
//
//   tile(op, N)         ⇒ backend chunks the iteration space in tiles of N
//   parallelize(op, P)  ⇒ backend dispatches across P threads / workgroups
//   vectorize(op, W)    ⇒ backend widens the inner op to W-wide SIMD
//
// Each is a wrapper recipe whose first child is the inner op-recipe and
// whose remaining children carry the integer parameter as a trivial:
//
//   TILE         children: [ inner-op, tile_size ]
//   PARALLELIZE  children: [ inner-op, num_threads ]
//   VECTORIZE    children: [ inner-op, simd_width ]
//
// Content-addressed: same inner-op + same parameter ⇒ same NodeID, so
// the same loop annotated tile(8) interns identically every time. The
// 5 downstream codegen backends (#10-14) read these via category-type
// dispatch and emit:
//
//   • WebGPU: tile→workgroup_size, parallelize→@compute dispatch,
//             vectorize→vec<T,W> SPIR-V types
//   • CUDA:   tile→tile_partition, parallelize→<<<grid,block>>>,
//             vectorize→float4 / int2 vector types
//   • Metal:  tile→threadgroup, parallelize→dispatchThreadgroups,
//             vectorize→simdgroup_<op>
//   • WASM:   tile→loop blocking, parallelize→Web Workers,
//             vectorize→v128 intrinsics
//   • MLIR:   tile→linalg.tile, parallelize→scf.parallel,
//             vectorize→vector.transfer

import {
  Kernel,
  Level,
  RBasic,
  type NodeID,
} from "./kernel.ts";

// ---------------------------------------------------------------------------
// Constructors — intern parallel-pattern recipes.
// ---------------------------------------------------------------------------

function makePatternRecipe(
  k: Kernel,
  patternType: number,
  inner: NodeID,
  param: number,
): NodeID {
  if (param <= 0 || (param | 0) !== param) {
    throw new Error(`parallel pattern: parameter must be positive integer, got ${param}`);
  }
  const cat: NodeID = {
    pkg: 1,
    level: Level.BASIC,
    type: patternType,
    inst: param, // category instance carries the parameter for fast inspection
  };
  return k.intern(cat, [inner, k.internTrivialInt(param)]);
}

// tile — chunk the inner op's iteration space in tiles of `tile_size`.
// Backends fall back to a no-op tile if `tile_size === 1`.
export function tile(k: Kernel, op: NodeID, tile_size: number): NodeID {
  return makePatternRecipe(k, RBasic.TILE, op, tile_size);
}

// parallelize — dispatch the inner op across `num_threads` workers.
// Backends without thread-level parallelism (single-thread WASM, simple
// JS) read this as a hint and execute serially.
export function parallelize(k: Kernel, op: NodeID, num_threads: number): NodeID {
  return makePatternRecipe(k, RBasic.PARALLELIZE, op, num_threads);
}

// vectorize — lower the inner op to `simd_width`-wide SIMD. Distinct from
// makeVectorFormat: the format describes a value's lane structure;
// vectorize() annotates an operation that should be widened. They compose:
// vectorize(addVecRecipe, 8) tells the backend "emit an 8-wide-add" for
// a recipe that already operates on lane-arrays.
export function vectorize(k: Kernel, op: NodeID, simd_width: number): NodeID {
  return makePatternRecipe(k, RBasic.VECTORIZE, op, simd_width);
}

// ---------------------------------------------------------------------------
// Readers — recover the (inner-op, parameter) pair from a stored recipe.
// ---------------------------------------------------------------------------

export interface ParallelPatternView {
  readonly patternType: number; // RBasic.TILE / PARALLELIZE / VECTORIZE
  readonly inner: NodeID;
  readonly parameter: number;
}

export function readParallelPattern(k: Kernel, node: NodeID): ParallelPatternView {
  const cat = k.category(node);
  if (
    cat.type !== RBasic.TILE &&
    cat.type !== RBasic.PARALLELIZE &&
    cat.type !== RBasic.VECTORIZE
  ) {
    throw new Error(
      `readParallelPattern: not a parallel-pattern recipe (type=${cat.type})`,
    );
  }
  const kids = k.children(node);
  if (kids.length < 2) {
    throw new Error(`readParallelPattern: malformed recipe (${kids.length} children)`);
  }
  const paramTriv = k.trivialValue(kids[1]!);
  if (paramTriv.kind !== "int") {
    throw new Error("readParallelPattern: parameter child malformed");
  }
  return {
    patternType: cat.type,
    inner: kids[0]!,
    parameter: paramTriv.int,
  };
}

// isParallelPattern — quick check for code that wants to skip over the
// annotation layer and reach the inner op.
export function isParallelPattern(k: Kernel, node: NodeID): boolean {
  if (node.level !== Level.BASIC) return false;
  const cat = k.category(node);
  return (
    cat.type === RBasic.TILE ||
    cat.type === RBasic.PARALLELIZE ||
    cat.type === RBasic.VECTORIZE
  );
}

// unwrapPatterns — strip all parallel-pattern annotations to reveal the
// underlying op. Backends use this when they want the un-annotated form
// (e.g. for cross-target fallback emission).
export function unwrapPatterns(k: Kernel, node: NodeID): NodeID {
  let cur = node;
  while (isParallelPattern(k, cur)) {
    const view = readParallelPattern(k, cur);
    cur = view.inner;
  }
  return cur;
}
