// vector.ts — VECTOR format-recipes + per-lane MATH dispatch + reductions.
//
// A VectorFormat is a format-recipe parameterized over (element-format, width).
// Content-addressed: same element-format + same width ⇒ same NodeID across
// the lattice. This is what the 5 downstream codegen backends (#10-14:
// WebGPU/CUDA/Metal/WASM-SIMD/MLIR) read to emit target SIMD code.
//
//   VectorFormat ──→ RBasic.VECTOR recipe
//     children: [ element-format-nodeID, width-trivial, storage-hint-string ]
//
// Per-lane MATH dispatch:
//   addVec(fmt, a, b)  ⇒ lanes-wise element-format arithmetic via applyArith
//   mulVec / subVec / divVec / modVec — same shape
//
// Reductions (first-class, single-pass over the lane array):
//   sumVec, maxVec, minVec, dotVec, popcountVec
//
// Storage hints describe the eventual lowering target — simd-avx2,
// simd-avx512, simd-neon, gpu-vec4, wasm-simd. They are strings in the
// substrate (content-addressed) so a backend can dispatch on equality
// without parsing.
//
// See docs/coherence-substrate/multi-target-codegen.md for the role this
// plays in the codegen architecture.

import {
  Kernel,
  Level,
  RBasic,
  type NodeID,
} from "./kernel.ts";
import {
  applyArithCode,
  ArithOpCode,
  type ArithOp,
  type FormatRecipe,
  type Numberish,
  opCode,
} from "./formats.ts";

// ---------------------------------------------------------------------------
// Storage hints — strings the kernel/compiler dispatch off, identical in
// shape to formats.ts StorageHint but for SIMD lanes.
// ---------------------------------------------------------------------------

export type VectorStorageHint =
  | "simd-avx2"     // x86 256-bit SIMD (8 × f32, 4 × f64, 16 × i16, ...)
  | "simd-avx512"   // x86 512-bit SIMD (16 × f32, 8 × f64, ...)
  | "simd-neon"     // ARM 128-bit SIMD (4 × f32, 2 × f64, 16 × i8, ...)
  | "gpu-vec4"      // GPU four-lane vector (Metal/WGSL/SPIR-V default)
  | "wasm-simd"     // wasm v128 (4 × i32 / 4 × f32 / 2 × f64)
  | "scalar-array"; // portable fallback: plain JS array of element values

// Common widths the lattice declares as well-known. Any positive integer
// works, but these are the ones the backends specifically target.
export const VectorWidth = {
  W4: 4,
  W8: 8,
  W16: 16,
  W32: 32,
  W64: 64,
} as const;

// ---------------------------------------------------------------------------
// VectorFormat — public shape mirrored from the substrate recipe.
// ---------------------------------------------------------------------------

export interface VectorFormat {
  readonly nodeID: NodeID;
  readonly element: FormatRecipe;
  readonly width: number;
  readonly storageHint: VectorStorageHint;
}

// makeVectorFormat — interns the VECTOR format-recipe; content-addressed.
// Calling with the same (element, width, storageHint) returns the same
// NodeID every time. Default storage-hint picks a sensible portable value;
// override when a target-specific lowering is wanted.
export function makeVectorFormat(
  k: Kernel,
  element: FormatRecipe,
  width: number,
  storageHint: VectorStorageHint = "scalar-array",
): VectorFormat {
  if (width <= 0 || (width | 0) !== width) {
    throw new Error(`makeVectorFormat: width must be positive integer, got ${width}`);
  }
  const cat: NodeID = {
    pkg: 1,
    level: Level.BASIC,
    type: RBasic.VECTOR,
    inst: width, // category instance carries the width for fast inspection
  };
  const children: NodeID[] = [
    { ...element.nodeID }, // element format-recipe identity
    k.internTrivialInt(width),
    k.internString(storageHint),
  ];
  const nodeID = k.intern(cat, children);
  return { nodeID, element, width, storageHint };
}

// readVectorFormat — recover a VectorFormat view from a stored NodeID.
// The element format-recipe is given back by reference (callers carry the
// FormatLibrary); this only restores the structural fields.
export interface VectorFormatView {
  readonly width: number;
  readonly storageHint: VectorStorageHint;
  readonly elementNodeID: NodeID;
}

export function readVectorFormat(k: Kernel, node: NodeID): VectorFormatView {
  const cat = k.category(node);
  if (cat.type !== RBasic.VECTOR) {
    throw new Error(`readVectorFormat: not a VECTOR recipe (type=${cat.type})`);
  }
  const kids = k.children(node);
  if (kids.length < 3) {
    throw new Error(`readVectorFormat: malformed VECTOR recipe (${kids.length} children)`);
  }
  const elementNodeID = kids[0]!;
  const widthTriv = kids[1]!;
  const hintTriv = kids[2]!;
  const width = k.trivialValue(widthTriv);
  const hint = k.trivialValue(hintTriv);
  if (width.kind !== "int" || hint.kind !== "str") {
    throw new Error("readVectorFormat: width/hint children malformed");
  }
  return {
    width: width.int,
    storageHint: hint.str as VectorStorageHint,
    elementNodeID,
  };
}

// ---------------------------------------------------------------------------
// Per-lane MATH dispatch.
// ---------------------------------------------------------------------------
//
// A vector value is a plain JS array of Numberish, length === fmt.width.
// Per-op semantics are inherited from the element format-recipe — we
// dispatch each lane through applyArithCode so a Vec<FP4> uses FP4
// arithmetic, a Vec<INT32> uses i32 arithmetic, etc.

export type VectorValue = readonly Numberish[];

function checkShape(fmt: VectorFormat, a: VectorValue, b: VectorValue): void {
  if (a.length !== fmt.width) {
    throw new Error(`vector op: lhs has ${a.length} lanes, format expects ${fmt.width}`);
  }
  if (b.length !== fmt.width) {
    throw new Error(`vector op: rhs has ${b.length} lanes, format expects ${fmt.width}`);
  }
}

export function applyVecArithCode(
  fmt: VectorFormat,
  opc: number,
  a: VectorValue,
  b: VectorValue,
): Numberish[] {
  checkShape(fmt, a, b);
  const out: Numberish[] = new Array(fmt.width);
  const el = fmt.element;
  for (let i = 0; i < fmt.width; i++) {
    out[i] = applyArithCode(el, opc, a[i]!, b[i]!);
  }
  return out;
}

export function applyVecArith(
  fmt: VectorFormat,
  op: ArithOp,
  a: VectorValue,
  b: VectorValue,
): Numberish[] {
  return applyVecArithCode(fmt, opCode(op), a, b);
}

// Per-op convenience wrappers — most callers want these by name.
export function addVec(fmt: VectorFormat, a: VectorValue, b: VectorValue): Numberish[] {
  return applyVecArithCode(fmt, ArithOpCode.ADD, a, b);
}

export function subVec(fmt: VectorFormat, a: VectorValue, b: VectorValue): Numberish[] {
  return applyVecArithCode(fmt, ArithOpCode.SUB, a, b);
}

export function mulVec(fmt: VectorFormat, a: VectorValue, b: VectorValue): Numberish[] {
  return applyVecArithCode(fmt, ArithOpCode.MUL, a, b);
}

export function divVec(fmt: VectorFormat, a: VectorValue, b: VectorValue): Numberish[] {
  return applyVecArithCode(fmt, ArithOpCode.DIV, a, b);
}

export function modVec(fmt: VectorFormat, a: VectorValue, b: VectorValue): Numberish[] {
  return applyVecArithCode(fmt, ArithOpCode.MOD, a, b);
}

// ---------------------------------------------------------------------------
// Reductions — first-class, single-pass.
// ---------------------------------------------------------------------------
//
// Reductions collapse a VectorValue to a single Numberish via repeated
// application of an associative element-format op. They are first-class
// because SIMD hardware has dedicated reduce instructions (psadbw, vpaddq,
// reducef64, ...); the backend reads these recipes and emits the right
// reduce intrinsic.

function reduce(
  fmt: VectorFormat,
  v: VectorValue,
  opc: number,
  init: Numberish,
): Numberish {
  if (v.length === 0) return init;
  let acc: Numberish = v[0]!;
  for (let i = 1; i < v.length; i++) {
    acc = applyArithCode(fmt.element, opc, acc, v[i]!);
  }
  return acc;
}

export function sumVec(fmt: VectorFormat, v: VectorValue): Numberish {
  if (v.length !== fmt.width) {
    throw new Error(`sumVec: lane count ${v.length} != format width ${fmt.width}`);
  }
  // Zero for bigint vs number — pick the right additive identity.
  const init: Numberish = typeof v[0] === "bigint" ? 0n : 0;
  return reduce(fmt, v, ArithOpCode.ADD, init);
}

function numericGreater(a: Numberish, b: Numberish): boolean {
  if (typeof a === "bigint" || typeof b === "bigint") {
    const ba = typeof a === "bigint" ? a : BigInt(Math.trunc(Number(a)));
    const bb = typeof b === "bigint" ? b : BigInt(Math.trunc(Number(b)));
    return ba > bb;
  }
  return Number(a) > Number(b);
}

export function maxVec(fmt: VectorFormat, v: VectorValue): Numberish {
  if (v.length !== fmt.width) {
    throw new Error(`maxVec: lane count ${v.length} != format width ${fmt.width}`);
  }
  if (v.length === 0) throw new Error("maxVec: empty vector has no max");
  let m: Numberish = v[0]!;
  for (let i = 1; i < v.length; i++) {
    if (numericGreater(v[i]!, m)) m = v[i]!;
  }
  return m;
}

export function minVec(fmt: VectorFormat, v: VectorValue): Numberish {
  if (v.length !== fmt.width) {
    throw new Error(`minVec: lane count ${v.length} != format width ${fmt.width}`);
  }
  if (v.length === 0) throw new Error("minVec: empty vector has no min");
  let m: Numberish = v[0]!;
  for (let i = 1; i < v.length; i++) {
    if (numericGreater(m, v[i]!)) m = v[i]!;
  }
  return m;
}

// dotVec — sum(a[i] * b[i]). Common enough to be first-class; backends
// frequently emit fused multiply-add (FMA) for this.
export function dotVec(
  fmt: VectorFormat,
  a: VectorValue,
  b: VectorValue,
): Numberish {
  checkShape(fmt, a, b);
  if (a.length === 0) return typeof a[0] === "bigint" ? 0n : 0;
  let acc: Numberish = applyArithCode(fmt.element, ArithOpCode.MUL, a[0]!, b[0]!);
  for (let i = 1; i < a.length; i++) {
    const prod = applyArithCode(fmt.element, ArithOpCode.MUL, a[i]!, b[i]!);
    acc = applyArithCode(fmt.element, ArithOpCode.ADD, acc, prod);
  }
  return acc;
}

// popcountVec — count of nonzero lanes. For BIT_1 / BITNET_158 formats the
// backend emits a true popcount intrinsic; for general formats it falls
// back to a per-lane != 0 test summed.
export function popcountVec(_fmt: VectorFormat, v: VectorValue): number {
  let c = 0;
  for (let i = 0; i < v.length; i++) {
    const x = v[i]!;
    if (typeof x === "bigint") {
      if (x !== 0n) c++;
    } else if (Number(x) !== 0) {
      c++;
    }
  }
  return c;
}
