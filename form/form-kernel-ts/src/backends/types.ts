// backends/types.ts — minimal CodegenBackend interface.
//
// Anticipates #7 (BackendRegistry). Each backend is a recipe walker that
// emits its target language as text — same pattern as compiler.ts emits
// JS, with the output language varying. The registry will key on
// `target_hints` to pick the most specific backend for a given target.
//
// Backends added without registry land:
//   #10 WebGPU (WGSL)   target: gpu-webgpu
//   #11 WASM SIMD       target: wasm-simd       (this file)
//   #12 MLIR            target: mlir-linalg / mlir-vector
//   #13 CUDA            target: gpu-cuda
//   #14 Metal           target: gpu-metal
//
// See docs/coherence-substrate/multi-target-codegen.md for the role this
// plays in the codegen architecture.

import type { Kernel, NodeID } from "../kernel.ts";

// CodegenBackend — minimal contract. A backend declares which target hints
// it covers and exposes an `emit` function that lowers a Form recipe to
// the backend's target language as a string.
export interface CodegenBackend {
  // Human-readable backend name, e.g. "wasm-simd", "wgsl", "mlir".
  readonly name: string;

  // target_hints — the set of format-recipe target hints this backend
  // satisfies. A format-recipe whose `target_hints` array intersects this
  // set can be emitted by this backend; otherwise the registry should
  // fall through to a portable encoding or raise.
  readonly target_hints: ReadonlySet<string>;

  // emit — lower the given recipe to the backend's target language. The
  // returned string is target-language source text (WAT, WGSL, MLIR, ...).
  emit(kernel: Kernel, recipe: NodeID): string;
}
