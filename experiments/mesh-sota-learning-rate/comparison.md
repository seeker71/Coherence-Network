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
- *At the fidelity end they diverge completely.* SOTA's **ceiling** is near-human; ours
  is coarse. Closing that gap is not "more samples" for this learner — it is a different
  learner: the gradient-trained transformer that `form-train-step.fk` is the SEED of
  (`docs/coherence-substrate/freq-check-model.form`, the ~100M-param target, named but
  not yet built).

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

## The one-line truth

> On the axis SOTA is measured on — fidelity from data — our learner is **not**
> competitive (54% coarse speaker-ID vs near-human STT/TTS). On the axis SOTA does **not**
> publish — accuracy *per sample* at the low-data frontier — our zero-backprop memorizer
> learns each new class from a *single* exemplar, which a gradient model cannot. The gap
> to SOTA fidelity is owned, not waved at: it is the gradient-trained transformer the
> SGD atom is the seed of. This experiment is the measuring stick that makes that gap
> legible instead of asserted.
