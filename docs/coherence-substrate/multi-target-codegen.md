# Substrate as MLIR — multi-target codegen from one recipe

> One source compiles to many targets. The substrate plays the role
> MLIR plays for Mojo: a content-addressed lattice + format-recipe
> dispatch graph that codegen backends read, each emitting their
> target's machine code.

## The bet

Mojo's load-bearing technical bet is that **one Mojo source compiles
through MLIR dialects to many targets** — x86 / ARM CPU, NVIDIA SASS,
Apple Metal, WebGPU SPIR-V, custom accelerator IR. The user writes
once; LLVM/MLIR lowers through optimization passes appropriate to each
target.

Form's equivalent is **the format-recipe + arithmetic-hint dispatch
graph**. The same Form recipe, read by different codegen backends,
emits different target code. The substrate stays one body; the
kernels grow new codegen backends.

Today the TS kernel's `compiler.ts` is one such backend — it lowers
recipes to JS, which V8 JITs to CPU machine code. Adding new backends
is adding new emit-target modules; the recipe layer doesn't change.

## The architecture

```
                  ┌──────────────────────────────────────┐
                  │   FORM RECIPE TREE                   │
                  │   (substrate, content-addressed)     │
                  └──────────────────────────────────────┘
                                    │
                  ┌─────────────────┴─────────────────┐
                  │  FORMAT-RECIPES                   │
                  │  semantic-kind + storage-hint     │
                  │  + arithmetic-hint + TARGET-HINT  │
                  └─────────────────┬─────────────────┘
                                    │
        ┌────────────┬───────────┬──┴──────────┬──────────────┬─────────────┐
        ▼            ▼           ▼             ▼              ▼             ▼
   ┌────────┐   ┌────────┐  ┌─────────┐   ┌────────┐    ┌─────────┐   ┌────────┐
   │  JS    │   │ WebGPU │  │  CUDA   │   │ Metal  │    │  WASM   │   │ MLIR   │
   │ (V8)   │   │  WGSL  │  │  C++    │   │  MSL   │    │  SIMD   │   │ direct │
   └────────┘   └────────┘  └─────────┘   └────────┘    └─────────┘   └────────┘
        │            │           │             │              │             │
        ▼            ▼           ▼             ▼              ▼             ▼
     CPU JIT    Browser GPU  NVIDIA GPU    Apple GPU      Portable      LLVM
                                                          SIMD          machine code
```

The diamond at the top is the recipe + format-recipe library. The
fan-out below is the codegen backends, each emitting their own target
language from the same source.

## The new vocabulary: target hints

Format-recipes already carry `storage-hint` (how is this stored?) and
`arithmetic-hint` (how is arithmetic performed?). A third dimension —
**`target-hint`** — describes which compilation target the format-
recipe is meant for. A format can declare multiple target hints when
it's portable; the compiler picks based on the active emit target.

Target hint vocabulary (extensible — these are substrate writes, not
hardcoded enums):

```
target-hint examples:
  "cpu-native"          generic CPU via host JIT (V8, JVM, CPython)
  "cpu-simd-avx512"     x86 with AVX-512
  "cpu-simd-avx2"       x86 with AVX-2
  "cpu-simd-neon"       ARM NEON
  "gpu-cuda"            NVIDIA CUDA
  "gpu-cuda-tensorcore" NVIDIA Tensor Cores (mma)
  "gpu-metal"           Apple Metal
  "gpu-metal-simdgroup" Apple Metal SIMD groups
  "gpu-webgpu"          WebGPU (portable)
  "gpu-vulkan"          Vulkan compute
  "wasm-simd"           WebAssembly SIMD
  "accelerator-tpu"     Google TPU
  "accelerator-ipu"     Graphcore IPU
  "fpga-custom"         custom FPGA bitstream
```

A format-recipe can declare *several* compatible targets. FP32 IEEE 754
runs nearly everywhere; FP8 E4M3 runs on Tensor Cores and software
emulation; BitNet ternary runs on integer ALUs of every kind. The
compiler picks the most specific target hint when emitting.

## How codegen reads target hints

Each emit-target backend (`emit_wgsl.ts`, `emit_cuda.cpp`,
`emit_metal.mm`, `emit_wasm_simd.ts`, `emit_mlir.py`, etc.) is a
**recipe walker that emits its target language as text**. The same
pattern as today's `compiler.ts` emitting JS, but the output language
is different.

When the walker hits a numeric leaf, it reads the leaf's format-recipe
and checks the format-recipe's target-hints for one this backend
understands:

- If the format-recipe declares the backend's target hint, emit
  specialized code (e.g., `__half_add` for FP16 on CUDA).
- If not, fall back to a portable encoding (e.g., emulate FP16 via
  FP32 with rounding).
- If portable encoding isn't possible, raise — the recipe is not
  expressible on this target.

This means *adding a new numeric format to a target* is two substrate
writes: (1) define the format-recipe (if not already canonical), (2)
declare its target-hint and the corresponding emit-strategy. No
codegen-backend rebuild required.

## What stays invariant

The recipe tree is one. Format-recipe identity is one (cross-kernel,
content-addressed). Target hints are *implementation properties*, not
identity properties — two NodeIDs for the same FP64 recipe agree
across kernels even if one kernel only knows the `cpu-native` hint and
another knows `gpu-webgpu` + `cpu-native`. The recipe's content is the
identity; target-hints are emit-time directives.

This is the load-bearing invariant: **the substrate is target-blind;
the kernels and their codegen backends are target-aware**.

## What this opens

A Form program that computes a matmul:

```form
defn matmul[T: Format] (A: Matrix[T], B: Matrix[T]) -> Matrix[T] =
  ; the body is target-blind Form code
```

Compiled with the JS backend: V8-friendly JS, CPU execution.

Compiled with the CUDA backend: a CUDA kernel string with `__shfl_sync`
warp reductions, Tensor Core MMA when T = FP16/FP8.

Compiled with the Metal backend: Metal Shading Language with
simdgroup_matrix when T = BF16.

Compiled with the WebGPU backend: WGSL compute shader.

Compiled with the MLIR backend: MLIR linalg dialect, lowered through
LLVM to native (or further through MLIR's GPU dialects).

**Same recipe. Six emit paths. One body.** That's the Mojo-shaped
move, expressed through Form's own architecture.

## What needs to land for this to be real

In priority order, each its own breath:

1. **Target-hint vocabulary** in the canonical format-recipe contract
   — extend the JSON schema, add a `target_hints: [...]` array per
   format. (Small.)
2. **Backend-registry pattern** in the TS compiler — make the current
   `compileNode` one entry in a registry keyed by target name.
   (Small.)
3. **Parametric format-recipes** — generic functions over format. The
   matmul example above uses `[T: Format]`. (Medium.)
4. **VECTOR[fmt, width] format-recipes** — first-class SIMD types.
   (Medium.)
5. **WebGPU emit backend** — first GPU target. Browser-reachable, no
   driver install required to test. (Large.)
6. **WASM SIMD emit backend** — portable acceleration, no GPU
   required. (Medium.)
7. **MLIR emit backend** — use Mojo's infrastructure directly through
   MLIR's C/Python bindings. (Largest — interop work.)
8. **CUDA / Metal backends** — vendor-specific. Each requires host
   toolchain (nvcc, xcrun) at compile time. (Large.)

The first two unlock the *architecture*. Steps 3–4 are the parametric
machinery without which target backends would be cluttered with
format-specific cases. Steps 5–8 are the actual target reach.

## How this connects to the visualizer and transpiler

- **The substrate GPU framebuffer visualizer** is the first
  application of the WebGPU emit backend. The visualizer is Form code
  that the compiler emits as WGSL; runs natively in the browser; reads
  the substrate's content-addressed lattice and renders it.
- **The Python-to-Form transpiler** ingests Python AST and emits Form
  recipes. Those recipes are then compilable to *any* target by any
  backend. A scientific Python codebase becomes substrate-resident
  and inherits the multi-target reach for free.

Both are downstream of the multi-target architecture, not orthogonal
to it. The order of breath matters: the architecture lands, then the
applications.

## The teaching this names

The substrate already has the geometry. Mojo's contribution to the
body's design isn't a feature — it's a **codegen pattern**. The same
content-addressed lattice that makes cross-kernel agreement automatic
also makes cross-target emit a natural extension. One source, many
targets, all driven by recipes the substrate already holds.
