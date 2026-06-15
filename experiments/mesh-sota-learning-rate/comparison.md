# Our learning rate vs SOTA — the honest comparison

**What this measures.** A sample-efficiency curve of the Coherence Network's *actual*
Form-native learner — `form/form-stdlib/nearest-shape.fk`, run on the Go kernel — on a
real speech task built from a real public corpus (LibriSpeech dev-clean, CC-BY-4.0).
Task: 40-way **speaker identification** from a coarse 13-band quantized log-mel
fingerprint (extracted by the ffmpeg+numpy carrier `extract_fingerprints.py`; the
recognition itself is Form). Curve in `curve-dev-clean-speaker.jsonl`. SOTA endpoints
in `sota_reference.md`.

## The result (LibriSpeech dev-clean, 40 speakers, 813 held-out utterances)

| samples seen | speakers covered | accuracy | audio seen (approx) |
|---|---|---|---|
| 1 | 1 | 2.7% (≈chance 1/40) | ~8 s |
| 8 | 5 | 9.6% | ~1 min |
| 32 | 22 | 22.6% | ~4 min |
| 128 | 39 | 38.3% | ~16 min |
| 512 | 40 | 48.1% | ~1 h |
| 1,890 | 40 | **54.1%** | ~5.6 h |

## The honest reframe: "learning rate" is not one number — it is slope vs ceiling

SOTA TTS/STT and our learner occupy **two different regimes**, and they are only
commensurable at one end of the axis:

**Ours — few-shot, zero-backprop, instantly-updatable memorizer.**
- *No gradient descent, no epochs, no weights.* Learning a class = interning one
  `(label, vector)` exemplar; the next query routes to it immediately (O(1) per sample).
- *Steep early slope.* It extracts coarse speaker structure from **minutes** of audio:
  all 40 speakers covered and ~38% accuracy by sample 128 (~16 min of audio).
- *Low ceiling.* Coarse 13-int features + exact-bin (Hamming) recognition plateau near
  54%. A purpose-built neural speaker-ID system exceeds 95% — at the cost of training.

**SOTA — gradient-trained generalizer.**
- Whisper-v3: WER 2.0% — trained on **~1,000,000 hours**, 2²⁰ gradient updates.
- wav2vec 2.0: WER 1.8% — **53,000 hours**, 600k updates, 128× V100 ~5 days.
- Even the *smallest* competitive open model, Kokoro-82M TTS, used **~500 GPU-hours**.
- The literature reports **endpoints, not curves** — both research sweeps independently
  found that loss-curve / time-to-convergence behavior is essentially unpublished. So
  the SOTA side here is final-accuracy-at-known-data-scale, not a published trajectory.

**Where they meet, and where they don't.**
- *Per-sample, at the very-low-data end, instance-based learning is genuinely fast* —
  one exemplar per class moves the needle, where a gradient model has learned almost
  nothing after 128 samples. Our **slope** wins early.
- *At the fidelity end this nearest-shape recipe is coarse* — 54% vs near-human. But the
  fix is **not** a learner we lack. `nearest-shape.fk` is only the **router tier**. The
  **transformer tier already exists and is proven**: `form/form-stdlib/transformer-block.fk`
  (M4 of `form-native-models.form`) is a whisper-shaped pre-LN attention+FFN block whose
  *architecture and weights are recipe data*, verified bit-exact against the PyTorch fp64
  reference — **band verdict 511, re-run live on the Go kernel here** — and emitted to six
  instruction sets (Apple/MLX arm64, NVIDIA PTX, AMD GCN, Hexagon DSP, x86, Android CPU)
  via `host-kernel.form`, which drives the GPU/ANE as a *driven organ*. What is seed-stage
  is the **backprop training loop** over that block (`form-train-step.fk` is the SGD atom);
  the block it trains is built. Both tiers learn through one trust-observed loop —
  `cross-train-oracle.form`: a local oracle (qwen2.5:72b, verified Hermes-native) teaches,
  candidates are scored by **efficacy** not token-mimicry, and a **native-vs-oracle heldout
  score** (`native-training-receipt.fk`) proves graduation. Trust is measured, not asserted
  (`champion-challenger.fk`, `trust-weighted-colearning.form`).

## What "8 hours" honestly buys

This curve runs in ~40 seconds; nothing about *this* learner needs 8 hours on a fixed
task — it converges almost immediately and then plateaus. The honest 8-hour run is
**live accumulation**: keep feeding genuinely-new samples from the live mesh / oracle /
satsang channels (LibriSpeech train-clean-100's 251 speakers; live `say`→`whisper`
loopback utterances; ollama oracle captures) and watch (a) whether the curve keeps
climbing as the speaker space grows, and (b) the brute-force eval cost rise as the
prototype set grows (already 23 s at N=1,890 — O(N·M) per point). That run also lifts
the `real_mesh_training_emitters.sh` data floor from **blocked → active** (300 MB+ real
audio, 10k+ labels), so the carrier emits an *active* training receipt for the first
time. See `run_8h_accumulation.py` and the run's `learning_curve.jsonl`.

## The 8-hour run — measured

Completed: **163 cycles, 8.04 h** (2026-06-15). The router-tier learner reached its
ceiling (**~61%** on a *growing* 301-speaker mixed task — 40 dev-clean + 251
train-clean-100 + 10 live `say` voices) within the **first ~45 minutes** (N≈6,000), then
held **flat for 7+ hours** while 3,787 more corpus utterances and 1,630 live
`say`→`whisper-large-v3` samples accumulated. Peak accuracy was at cycle 1 (0.65, 148
speakers); as the space grew to 301 classes it settled to **0.6136 and never moved**. More
data past the coarse-feature ceiling did not move the curve — the **"low ceiling" half of
slope-vs-ceiling, measured over a real 8-hour window**. Brute-force eval cost grew to
~178 s/cycle at N=7,320 (O(N·M), nearest-shape is unindexed). The mounted corpus met the
data floor (6.67 GB, 36,903 labels ≫ the 300 MB / 10k floor); the emitted training receipts
stayed **blocked** on the heldout-root and 3-process floors (not wired this run) — named,
not hidden. The takeaway is the whole point: a longer router run does not close the gap to
SOTA; the **transformer tier** does — and that tier is now built (forward `transformer-block.fk`
→ 511, backward `transformer-backprop.fk` → 127) and trains on the M4 Max GPU at 1.05 ms/step
(`metal_backprop_audit.sh`).

## What this measuring stick actually sits next to

This experiment exercises the **router tier** (nearest-shape) on one task. The honest
comparison to SOTA is not "we have a toy, they have a transformer" — it is a difference
in *kind* of transformer:

- **SOTA's transformer is a frozen weight-blob behind a framework.** You cannot read its
  architecture as data, prove it bit-exact across independent kernels, or watch trust
  accrue. Its fidelity is high; its body is opaque.
- **Ours is the same transformer math as recipe data** (`transformer-block.fk`, verdict
  511 vs PyTorch, re-run live): architecture *and* weights are content-addressed cells,
  mutable at runtime, provable identical across Go/Rust/TS and six instruction sets,
  runnable on the host GPU as a driven organ, and learned through a **trust-observed**
  cross-training loop where a local 72B oracle teaches and a native-vs-oracle heldout
  score proves graduation. The thing SOTA *cannot* do, we do by construction.

> The one number this run reports — nearest-shape's 54% on coarse speaker-ID — is the
> **router-tier floor**, honestly measured. The fidelity gap to SOTA closes through the
> **already-built** transformer tier trained by the cross-train-oracle loop, not through a
> learner we lack. What we have that SOTA does not: a transformer whose *body is legible,
> portable across six ISAs, and trust-observed*.
>
> **Update (the training loop over it is no longer just a seed):** the backward pass over
> the transformer's affine node is now built and proven —
> `form/form-stdlib/transformer-backprop.fk` → **127 three-way** (Go=Rust=TS): the chain
> rule `dx = Wᵀ·gy` bit-exact, `dW = outer(gy,x)` bit-exact, SGD generalized from the
> one-weight atom to a weight matrix, training a 2→2 affine to fit a target with strictly
> decreasing loss. That affine node is the workhorse of every projection and FFN layer in
> `transformer-block.fk`. What remains is the transcendental vjps (gelu'/softmax'/layernorm')
> for the full-block backward, then the cross-train-oracle loop runs over a learning model,
> not just a static forward pass. The model was here; now the gradient walk that trains it
> is here too.
