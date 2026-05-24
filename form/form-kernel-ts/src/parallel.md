# Parallel patterns — TILE / PARALLELIZE / VECTORIZE

> Task #9 — second half. Annotations the codegen backends read to
> dispatch into the target's native parallel primitive.

## What this is

`parallel.ts` adds three high-level pattern recipes that **annotate**
an inner op without changing its semantics. The walker reads them as
opaque (returns the NodeID); the codegen backend reads them as
emission directives.

| Pattern          | RBasic slot | Parameter      | Emission                                       |
|------------------|-------------|----------------|------------------------------------------------|
| `tile`           | `TILE=84`   | `tile_size`    | chunk iteration space into tiles of N          |
| `parallelize`    | `PARALLELIZE=85` | `num_threads` | dispatch op across N threads / workgroups |
| `vectorize`      | `VECTORIZE=86` | `simd_width` | lower op to W-wide SIMD                       |

## The shape

```
RBasic.TILE / PARALLELIZE / VECTORIZE
  inst = parameter         (tile_size / num_threads / simd_width)
  children:
    [0] inner-op recipe
    [1] parameter-trivial  (int trivial; redundant with inst for read robustness)
```

Constructors:

```ts
tile(k, op, 8)          // tile by 8
parallelize(k, op, 16)  // 16 threads
vectorize(k, op, 8)     // 8-wide SIMD
```

Readers:

```ts
readParallelPattern(k, node) ⇒ { patternType, inner, parameter }
isParallelPattern(k, node)   ⇒ boolean
unwrapPatterns(k, node)      ⇒ inner-op (strips all annotations)
```

## Backend dispatch table

Each backend reads the same three slots and emits its target's parallel
primitive:

| Backend   | TILE              | PARALLELIZE                | VECTORIZE                  |
|-----------|-------------------|----------------------------|----------------------------|
| WebGPU    | `workgroup_size`  | `@compute` dispatch        | `vec<T,W>` SPIR-V types    |
| CUDA      | `tile_partition`  | `<<<grid, block>>>`        | `float4` / `int2` types    |
| Metal     | `threadgroup`     | `dispatchThreadgroups`     | `simdgroup_<op>`           |
| WASM      | loop blocking     | Web Workers                | `v128` intrinsics          |
| MLIR      | `linalg.tile`     | `scf.parallel`             | `vector.transfer`          |

A backend that can't realize a given primitive (e.g. single-threaded
WASM can't truly parallelize) treats the pattern as a hint and falls
back to sequential execution. The recipe stays the same; only the
emission changes.

## Composition

The three patterns compose freely — the inner op of one can be another:

```ts
const op    = ...someComputeRecipe...
const tiled = tile(k, op, 8)
const par   = parallelize(k, tiled, 4)
const vec   = vectorize(k, par, 8)
// vec is "8-wide SIMD across 4 threads, with the inner loop tiled by 8"
```

`unwrapPatterns` peels all wrappers to reach the underlying op — useful
for backends emitting a fallback sequential form.

## Content-addressing

Same `(inner-op, parameter)` ⇒ same NodeID. Two source files annotating
the same op with `tile(8)` intern to the same recipe; the substrate
recognizes the structural equality without a textual comparison.

Different parameters or different op trees produce distinct NodeIDs.
The three pattern types are also distinct from each other — a `tile(8)`
and a `vectorize(8)` are not the same recipe even though they share a
parameter.

## Walker behaviour

`walk()` on any of the three returns the recipe's own NodeID. Pattern
recipes are structural metadata, not executable code. Downstream
modules (cells reading the annotation, backends emitting code) reach
in via `readParallelPattern` / `unwrapPatterns`.

## How this fits with VECTOR

`vector.ts` describes a **value's lane structure** (this is a
`Vec<FP32, 8>` stored as `simd-avx2`). `parallel.ts` describes an
**operation's emission strategy** (lower this op to 8-wide SIMD,
across 4 threads, with tile size 16). They compose orthogonally —
a vectorized op operates on VECTOR-formatted values.
