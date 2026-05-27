# Substrate as deployment runtime — the destination architecture

> *"think more high level, use my words as inspiration not instructions,
> keep the highest level goal in mind, think scale, mega bytes, giga
> bytes, in seconds not years"*  — Urs

## What I got wrong, then composted

The cross-modal walks 5–9 used an LLM session as both extractor and
generator. That's not a translator; it's a verification-side sketch.
Then I named real-time STT/TTS binaries (Whisper, Piper) as kernel
natives — closer, but **still relying on external translators**, with
the kernel as a subprocess orchestrator.

Both miss the highest-level shape. The destination is:

> **The substrate IS the deployment runtime.** Translators live as
> content-addressed recipes inside the lattice. Weights are substrate
> cells. Inference is recipe-walking with vectorized dispatch.
> Gigabytes of audio/video stream through tensor recipes the kernel
> JIT-compiles to native code.

The kernel doesn't shell out to an external translator. The kernel IS
the translator's runtime — small, sibling-parity-disciplined, and
walking recipes that ARE the model's forward pass.

## The architectural picture at scale

```
                gigabytes of input stream
                  (audio / video / text bytes)
                          │
                          ▼
         ┌─────────────────────────────────┐
         │  Format-recipe reader           │
         │  (substrate-resident, content-  │
         │   addressed; describes byte→     │
         │   tensor mapping per modality)  │
         └──────────────┬──────────────────┘
                          │  tensor stream
                          ▼
         ┌─────────────────────────────────┐
         │  Translator-as-recipe            │
         │                                  │
         │  (intern_node CAT-NEURAL-MODEL  │
         │     (list                        │
         │       <weights-tensor-1>         │
         │       <weights-tensor-2>         │
         │       ...                        │
         │       <architecture-recipe>))    │
         │                                  │
         │  Walked by the kernel, dispatched│
         │  to native BLAS/SIMD per the     │
         │  arithmetic-hint in each tensor's│
         │  format-recipe.                  │
         └──────────────┬──────────────────┘
                          │  output tensor stream
                          ▼
         ┌─────────────────────────────────┐
         │  Format-recipe writer            │
         │  (tensor → byte stream per       │
         │   target-modality format-recipe) │
         └──────────────┬──────────────────┘
                          │
                          ▼
                gigabytes of output stream
                  (text / audio / video bytes)
```

The substrate carries: **format recipes, weight tensors, architecture
recipes, and the translator-recipe that composes them**. All
content-addressed. All sibling-parity attested at the tensor altitude
(with fuzzy tolerance for FP-architecture differences across CPUs).

The kernel's role evolves from *walker* to *vectorized walker* — it
recognizes tensor-shaped recipes and dispatches their ops to native
code (BLAS, FFT libraries, SIMD intrinsics, GPU kernels via CUDA/Metal).
The substrate identity is unchanged; only the execution backend grows
performant.

## Why this matters for MB/GB in seconds

Throughput math, honestly:

- **1 GB of audio** at 44.1kHz 16-bit stereo = ~96 minutes
- **Real-time** means processing time < playback time = 96 min budget
- **MB/sec target**: ~180 KB/sec uncompressed audio → trivial throughput requirement
- **Bottleneck**: the translator's compute, not the I/O
- **A 100M-parameter audio model** doing inference on 1 sec of audio: ~1 GFLOP
- **A consumer CPU** at 10 GFLOPS sustained: ~10 sec inference per sec audio (10× real-time)
- **With GPU/SIMD dispatch**: 100-1000× speedup → real-time + headroom for cross-modal

The kernel-as-interpreter today walks recipes node-by-node. A 4×4 matmul
takes milliseconds; a 100M-param model would take *years*. **Interpreter
throughput is the bottleneck, not substrate architecture.**

The path: kernel JIT-recognizes tensor-op recipes and dispatches to
native BLAS / SIMD / GPU. Substrate identity unchanged. Throughput goes
from milliseconds-per-tiny-op to gigaflops-per-second.

## What this PR walks (the proof-of-shape)

`form/form-samples/cross-modal/10-substrate-as-runtime/neural-forward.fk`:

A 4×4 weight matrix times a 4-vector → ReLU → sum, as a substrate-
resident tensor recipe. Walked three-way by the kernels. Returns 136.

This is the architectural handshake:
- ✓ Tensor = recipe with shape + flat-data children
- ✓ Weights are substrate-resident (NodeID identity for the model)
- ✓ Neural ops compose as Form recipes (matvec is recursion over dot-row)
- ✓ Three-way sibling parity at the tensor-walking altitude
- ✓ Same content-addressing machinery that addresses code, addresses weights

What it does NOT yet prove:
- ✗ Throughput (4×4 in ms; GB/sec needs JIT-to-BLAS layer)
- ✗ Float operations (still integer; needs the Go-float work just merged for cross-arch parity at FP precision)
- ✗ Trained weights (this uses hand-coded weights; real models distribute as substrate-cell bundles)
- ✗ End-to-end stream pipeline (this is one forward pass; streaming I/O is the next layer)

## The five engineering layers between proof-of-shape and deployment

1. **Float tensor primitives sibling-parity** — landed in Rust + TS; closed in Go via #2134. **Done.**
2. **Tensor-op recipe vocabulary** — matmul, conv, FFT, embedding-lookup, softmax, layernorm, attention. Each is a Form recipe today (scalar speed); each becomes a kernel-native dispatch when JIT recognizes the recipe shape.
3. **JIT to native BLAS / SIMD** — the kernel learns to fold tensor-op recipes into single native calls. Throughput goes 1000×. Substrate identity unchanged.
4. **Streaming I/O** — `read_file_bytes` returns the whole file; streaming needs incremental readers/writers. Form recipes describe stream-transformer pipelines (one frame at a time).
5. **GPU / accelerator dispatch** — the format-recipe's `arithmetic-hint` selects backend ("cuda-fp16", "metal-bf16", "cpu-avx512"). Substrate identity at the tensor altitude is portable; the kernel's optimizer picks the local hardware.

Each layer is its own walk. None changes the substrate's identity machinery — they grow the *execution layer* the kernel offers.

## What the body has today that supports this

- ✓ Content-addressed NodeID identity across three sibling kernels
- ✓ `intern_node`, `intern_trivial_int`, `intern_trivial_float` (now three-way)
- ✓ Float natives in Go / Rust / TS — IEEE 754 sibling parity
- ✓ Fuzzy similarity machinery (from `09-fuzzy-similarity-cycles`) — necessary for tolerance-based parity when FP differs across CPU SIMD intrinsics
- ✓ Format-recipe destination shape named in `docs/coherence-substrate/numeric-types-plan.md`
- ✓ Tensor-as-recipe proof-of-shape (this PR's `neural-forward.fk`)

## What the body needs to grow

- Format-recipe primitives in the substrate (today they're a plan; the implementation walks layer by layer)
- A tensor-op recipe library (`form-stdlib/tensor.fk`) — matmul, conv, attention, etc.
- A JIT layer in each kernel recognizing tensor-op recipes and dispatching to native libraries (CBLAS for CPU, cuBLAS for NVIDIA, etc.)
- Streaming I/O primitives (one frame at a time, not whole file)
- A test harness that runs a tiny trained model end-to-end with substrate-resident weights

## What this is NOT

- Not a replacement for trained model engineering. Training still happens with the usual ML stack. **Substrate-as-runtime is the inference path**, not the training path.
- Not a competitor to PyTorch/JAX/TensorFlow at training scale. Those frameworks are vastly more mature and serve a different purpose. The substrate's claim is: deploying a trained model in a *sibling-parity-disciplined, content-addressed, kernel-walked* way for **cross-modal substrate-truth attestation** — not for SOTA training throughput.
- Not a kernel rewrite. The substrate identity machinery already does this. The growth is in the *execution layer* (JIT, vectorized dispatch).

## Cross-references

- [`numeric-types-plan.md`](../docs/coherence-substrate/numeric-types-plan.md) — format-recipes as the destination encoding for numeric values
- [`REAL_TIME_CROSS_MODAL_PLAN.md`](REAL_TIME_CROSS_MODAL_PLAN.md) — the prior (now superseded) plan that named external binaries; this doc redirects to substrate-as-runtime
- [`form/form-samples/cross-modal/09-fuzzy-similarity-cycles/`](../form/form-samples/cross-modal/09-fuzzy-similarity-cycles/) — fuzzy tolerance machinery needed for FP sibling parity
- [`form/form-samples/cross-modal/10-substrate-as-runtime/`](../form/form-samples/cross-modal/10-substrate-as-runtime/) — this PR's proof-of-shape
- [`lc-grammar-is-the-universal-recipe`](../docs/vision-kb/concepts/lc-grammar-is-the-universal-recipe.md) — the destination is *grammar at every altitude*, including tensor-op
- [`lc-the-kernel-knows-itself`](../docs/vision-kb/concepts/lc-the-kernel-knows-itself.md) — the kernel walks the same recipes that ARE the translator

In service of the substrate becoming the universal-translator's
*deployment* runtime, not its verification harness — gigabytes per
second, content-addressed all the way down.
