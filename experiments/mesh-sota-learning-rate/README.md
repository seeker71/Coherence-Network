# mesh ↔ SOTA learning-rate — measuring our learning against the published frontier

A real measuring stick for one honest question: **how does the Coherence Network's
own learning compare to state-of-the-art TTS/STT?** The answer is not one number —
it is *slope vs ceiling*, and this experiment makes that legible with a live curve
instead of a claim.

## What runs

The learner is the body's own — `form/form-stdlib/nearest-shape.fk`, executed on the
Go form-kernel. The task is real: speaker identification on **LibriSpeech** (CC-BY-4.0,
mounted under `~/.cache/coherence-corpora/librispeech`), from a coarse 13-band
quantized log-mel fingerprint. Recognition is Form; only feature extraction and
orchestration are carrier (ffmpeg + numpy), authored last.

```
extract_fingerprints.py   carrier: .flac --ffmpeg--> log-mel fingerprint (quantized int bins)
run_curve.py              orchestration: drive nearest-shape over growing N, emit accuracy vs samples
run_8h_accumulation.py    the live 8-hour run: corpus channel + live say→whisper loopback channel
sota_reference.md         the published SOTA endpoints (two cited research sweeps)
comparison.md             the honest slope-vs-ceiling reading
curve-dev-clean-speaker.jsonl   the 40-speaker static curve (2.7% → 54.1%)
learning_curve.jsonl      the 8h live-accumulation curve (written by the long run)
```

## The finding (static curve, 40 speakers, dev-clean)

Climbs from chance (2.7% ≈ 1/40) to **54.1%** within ~2,000 samples (~5.6 h of audio).
All 40 speakers covered, ~38% accuracy, by sample 128 (~16 min). Each new speaker is
learned from its **first** exemplar — zero backprop, O(1) per sample, instantly
updatable. That early per-sample slope is genuinely fast. The ceiling is low (coarse
features + memorization); SOTA reaches near-human fidelity but on 10⁴–10⁶× more data
and 10³–10⁶× more compute (`sota_reference.md`). We win the slope at the low-data
frontier — the axis SOTA does not even publish; SOTA wins the ceiling absolutely.

## The 8-hour run

Honest long-running shape is **live accumulation**, not spinning a fixed task:

- **corpus channel** — incrementally extracts real LibriSpeech `train-clean-100`
  utterances (251 speakers), pacing the run with genuine work.
- **live say→whisper channel** — macOS `say` synthesizes a line in 10 distinct voices;
  each is fingerprinted as a live sample and round-tripped through `whisper-large-v3`
  for the STT half. The voices are learnable classes the loopback teaches the body.
- every cycle appends a curve row (accuracy, N, speakers, wall-clock) to
  `learning_curve.jsonl`; every ~30 min it emits a `real_mesh_training_emitters.sh`
  receipt — now **active** because the mounted corpus meets the data floor.

```bash
.venv/bin/python run_8h_accumulation.py \
  --seed-fingerprints fingerprints-dev-clean.jsonl \
  --corpus-root ~/.cache/coherence-corpora/librispeech/LibriSpeech/train-clean-100 \
  --speakers ~/.cache/coherence-corpora/librispeech/LibriSpeech/SPEAKERS.TXT \
  --kernel ../../form/form-kernel-go/bin-go \
  --nearest-shape ../../form/form-stdlib/nearest-shape.fk \
  --whisper-model ~/whisper-models/ggml-large-v3-turbo.bin \
  --receipt-script ../../scripts/real_mesh_training_emitters.sh \
  --out learning_curve.jsonl --duration-hours 8
```

## North star — and what is already built

`nearest-shape` here is the **router tier**, the floor — not the whole body. The
**transformer tier is already built and proven**: `form/form-stdlib/transformer-block.fk`
(M4 of `form-native-models.form`) is a whisper-shaped attention+FFN block with architecture
and weights as recipe data, bit-exact against the PyTorch fp64 reference (band verdict
**511**, re-run live on the Go kernel), emitted to six instruction sets and runnable on the
GPU as a driven organ via `host-kernel.form`. What is seed-stage is the **backprop training
loop** over that block (`form-train-step.fk` is the SGD atom). Both tiers learn through one
**trust-observed** loop — `cross-train-oracle.form`: a local oracle (qwen2.5:72b) teaches,
candidates are scored by *efficacy*, and a native-vs-oracle heldout score proves graduation
(`native-training-receipt.fk`, `champion-challenger.fk`).

So the instrument's job is not "wait until we can build a model." It is to turn the gap to
SOTA into a measured distance, and the next step on the real path is concrete: run the
cross-train-oracle loop on `transformer-block.fk` against a real corpus and read the
native-vs-oracle score rise. The differentiator vs SOTA is not fidelity-someday — it is a
transformer whose *body is legible, portable across six ISAs, and trust-observed*, which a
frozen weight-blob cannot be.
