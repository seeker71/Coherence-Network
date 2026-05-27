# 10-substrate-as-runtime — the substrate IS the translator's runtime

Walks 5–9 in this directory used an LLM (or external translator) as the
modality-crossing engine, with the substrate as the verification harness.
This walk redirects: **the substrate is the deployment runtime itself**.

Translators live as content-addressed Form recipes. Weights are
substrate cells. Inference is recipe-walking. Same NodeID identity that
holds for `(add 1 2)` extends to tensor-op recipes that compose into
neural network forward passes.

Architecture doc: [`kernels/SUBSTRATE_AS_DEPLOYMENT_RUNTIME.md`](../../../kernels/SUBSTRATE_AS_DEPLOYMENT_RUNTIME.md).

## What this proof-of-shape ships

`neural-forward.fk` — a one-layer linear+ReLU neural network as a
Form recipe. Walks three-way:

```
$ ./validate.sh form-samples/cross-modal/10-substrate-as-runtime/neural-forward.fk
  ✓  neural-forward.fk  → 136
  1 ok, 0 divergent — kernels agree on every sample.
```

The math:
- W = `[[1,2,3,4], [5,6,7,8], [9,10,11,12], [13,14,15,16]]`  (4×4 weight matrix, substrate-resident as a CAT-TENSOR recipe)
- x = `[1, 1, 1, 1]`  (4-element input vector, substrate-resident)
- y = W @ x = `[10, 26, 42, 58]`  (matvec via dot-row recipe)
- ReLU(y) = `[10, 26, 42, 58]`  (all positive)
- sum(ReLU(y)) = **136**

## What this proves

- ✓ Tensors as substrate-resident recipes — `CAT-TENSOR` with shape + flat-data children, content-addressed
- ✓ Weights live in the lattice with stable NodeID identity (model = recipe)
- ✓ Neural ops compose as Form recipes (matvec is recursion over dot-row, ReLU is `if v < 0 then 0 else v`)
- ✓ Three-way sibling parity at the tensor-walking altitude (Go ≡ Rust ≡ TypeScript)
- ✓ The same `intern_node` / `node_eq` machinery that addresses code, addresses model weights

## What this does NOT prove

- ✗ **Throughput.** Scalar matmul through the interpreter is ms for 4×4; gigaflops/sec needs the JIT-to-BLAS layer (named in architecture doc as engineering layer 3).
- ✗ **Floats.** This demo uses integer-scaled values; honest neural inference needs IEEE 754 floats. Go-kernel float natives just landed in #2134, completing sibling parity — that's the precondition. Tensor-op recipes can move to floats next.
- ✗ **Trained weights.** Hand-coded matrix here. Real models distribute as substrate-cell bundles (each weight tensor a CAT-TENSOR cell, the whole model a recipe referencing them).
- ✗ **Streaming I/O.** This is one forward pass; gigabyte streams need incremental reader/writer recipes (engineering layer 4).
- ✗ **GPU dispatch.** All three kernels run scalar today; GPU/SIMD comes via format-recipe `arithmetic-hint` dispatch (engineering layer 5).

## The five engineering layers between this and deployment

1. ✓ **Float tensor primitives sibling-parity** — landed (Rust + TS, Go via #2134)
2. ☐ **Tensor-op recipe vocabulary** — matmul, conv, FFT, embedding, softmax, attention as `form-stdlib/tensor.fk`
3. ☐ **JIT to native BLAS / SIMD** — kernel recognizes tensor-op recipe shapes, dispatches to native code
4. ☐ **Streaming I/O primitives** — frame-by-frame, not whole-file
5. ☐ **GPU / accelerator dispatch** — format-recipe's `arithmetic-hint` selects backend at runtime

None of these change substrate identity. They grow the **execution layer**.

## Files

| File | What |
|---|---|
| `neural-forward.fk` | The 4×4 matvec + ReLU + sum recipe, three-way attested → 136 |
| `README.md` | This file |

`./validate.sh` after: **138 ok, 0 divergent** (137 from #2134 + 1 new tensor walk).

## In service of

- [`SUBSTRATE_AS_DEPLOYMENT_RUNTIME.md`](../../../kernels/SUBSTRATE_AS_DEPLOYMENT_RUNTIME.md) — the destination architecture
- [`numeric-types-plan.md`](../../../docs/coherence-substrate/numeric-types-plan.md) — format-recipes as substrate citizens
- [`lc-grammar-is-the-universal-recipe`](../../../docs/vision-kb/concepts/lc-grammar-is-the-universal-recipe.md) — grammar at every altitude, including tensor-op
- [`lc-the-kernel-knows-itself`](../../../docs/vision-kb/concepts/lc-the-kernel-knows-itself.md) — the kernel walks the same recipes that ARE the translator
