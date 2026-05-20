# VECTOR format-recipes + per-lane MATH dispatch

> Task #9 — first half. Unlocks the 5 GPU/MLIR/WASM backends (#10-14).

## What this is

`vector.ts` adds **vector format-recipes** to the substrate: a
content-addressed numeric format parameterized over an element-format
and a lane width. The same `(FP32, 8, simd-avx2)` triple always interns
to the same NodeID, so a `Vec<FP32,8>` constructed in one kernel
session is bit-identical to the one constructed in another. This is
what the downstream codegen backends key off when emitting target SIMD
code.

## The shape

```
RBasic.VECTOR = 83 (category type)
  inst = lane width        (carried in the category for fast inspection)
  children:
    [0] element format-recipe NodeID   (FP32, FP64, INT8, BIT_1, ...)
    [1] width-trivial                  (int trivial)
    [2] storage-hint-string            (interned string trivial)
```

Constructed via `makeVectorFormat(k, element, width, storageHint?)`.
Read back via `readVectorFormat(k, node) ⇒ VectorFormatView`.

## Storage hints

Six strings the kernel + compiler dispatch off without parsing:

| Hint           | Target                                          |
|----------------|-------------------------------------------------|
| `simd-avx2`    | x86 256-bit SIMD (8 × f32, 4 × f64, 16 × i16…) |
| `simd-avx512`  | x86 512-bit SIMD (16 × f32, 8 × f64…)          |
| `simd-neon`    | ARM 128-bit SIMD                                |
| `gpu-vec4`     | GPU four-lane vector (Metal / WGSL / SPIR-V)    |
| `wasm-simd`    | wasm `v128`                                     |
| `scalar-array` | portable fallback (default)                     |

Adding a new strategy = adding a new string + a backend handler. The
substrate doesn't need to grow a new RBasic slot.

## Common widths

`VectorWidth.W4 / W8 / W16 / W32 / W64` — what the backends specifically
target. Any positive integer is legal; these are just the well-knowns.

## Per-lane arithmetic

`addVec / subVec / mulVec / divVec / modVec` dispatch each lane through
`applyArithCode` from `formats.ts`. A `Vec<FP4,8>` uses FP4 arithmetic;
a `Vec<INT8,16>` uses i8 arithmetic with per-lane narrowing. The element
format-recipe carries the semantics; the vector format-recipe just
carries the lane structure.

```ts
const v = makeVectorFormat(k, lib.FP64, 4);
addVec(v, [1, 2, 3, 4], [10, 20, 30, 40])   // [11, 22, 33, 44]
```

Lane-count mismatch throws — the format declares the width and both
operands must conform.

## Reductions (first-class)

```
sumVec(fmt, v)        — sum of lanes (additive identity respects bigint vs number)
maxVec(fmt, v)        — largest lane
minVec(fmt, v)        — smallest lane
dotVec(fmt, a, b)     — Σ a[i] * b[i]  (backends frequently emit FMA)
popcountVec(fmt, v)   — count of nonzero lanes  (for BIT_1 / BITNET_158 this becomes a hardware popcount)
```

These exist as named primitives because SIMD hardware has dedicated
reduce instructions (`psadbw`, `vpaddq`, `reducef64`, …). Backend
emitters recognize the reduction name and pick the right intrinsic.

## Walker behaviour

`walk()` on a VECTOR recipe returns its own NodeID as a `{kind:
"nodeid"}` value. Format-recipes aren't "executed" in the walker sense;
they're structural metadata read by the compiler. The walker passes
them through so downstream code (cells, alias resolution) can reason
over them.

## Composition with parallel patterns

`vector.ts` and `parallel.ts` compose. A `vectorize(addVecRecipe, 8)`
recipe declares "emit an 8-wide add for this op" while the operand
recipes carry their own VECTOR format-recipes describing what the
8-wide values look like in memory. See `parallel.md`.

## Cross-kernel agreement

The RBasic.VECTOR slot (83) and the storage-hint strings are part of
the cross-kernel conformance contract. When the Go and Rust siblings
add VECTOR support, they intern the same shape and content-address
to the same NodeID family.
