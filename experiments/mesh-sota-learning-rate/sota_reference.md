# SOTA TTS / STT training characteristics — reference table

Distilled from two cited web-research sweeps (2026-06-15). Every number carries a
primary or near-primary source. "NR" = not reported by the sources consulted. This
is the reference the sample-efficiency comparison stands on — the axes that let us
place our learning curve beside theirs are **training-data scale**, **compute**, and
**headline accuracy**.

## STT / ASR

| Model | Params | Train data (hours) | Compute | Headline accuracy | Optimizer / LR |
|---|---|---|---|---|---|
| **Whisper large-v3** | 1,550M | 1M labeled + 4M pseudo-labeled, 2.0 epochs | GPU-hours **NR** | LS test-clean WER **2.01%**, test-other 3.91% | AdamW β2=0.98, wd 0.1, 2,048 warmup, 2²⁰ updates, batch 256, peak LR ~1.75e-4 (low-conf) |
| **wav2vec 2.0 LARGE** | 317M | 53.2k unlabeled (LV-60k) + up to 960 labeled | 128× V100, 600k updates (~5.2 days) | LS test-clean **1.8**, test-other 3.3 | Adam, peak 3e-4, 8% warmup then linear decay |
| **HuBERT X-LARGE** | 964M | 60k (Libri-Light) | 256 GPUs, 400k steps | LS test-clean **1.8**, test-other 2.9 | Adam, peak 3e-3, 8% warmup |
| **Conformer L** | 118.8M | 970 (LibriSpeech) | TPU/GPU **NR** | LS test-clean 1.9, test-other 3.9 (w/ LM) | Adam β2=0.98, 10k warmup, peak 0.05/√d |
| **NVIDIA Parakeet-TDT-1.1B** | 1.1B | 64,000 (40k private + 24k public) | NR | LS test-clean **1.39%**, test-other 2.6% | NR on card |
| **NVIDIA Canary-1B-v2** | 1B | 1.7M total (Granary+NeMo) | 64–128× A100 | open-asr mean WER **7.15%** (beats Whisper-v3 7.44%) | AdamW wd 0.001, LR 4e-4→3e-4→2e-5, 150k+100k+10k steps |
| **SeamlessM4T v2** | ~2.3B (unverified) | 4.5M unlabeled (w2v-BERT 2.0) | NR | ASR WER NR (paper leads with BLEU) | NR |

## TTS

| Model | Params | Train data (hours) | Compute | Headline quality | Optimizer / LR |
|---|---|---|---|---|---|
| **Tacotron 2** | ~28M (cited) | 24.6 (1 speaker) | acoustic 1 GPU / vocoder 32 GPU | MOS **4.53** (GT 4.58) | Adam, LR 1e-3→1e-5 after 50k |
| **FastSpeech 2** | ~23M | 24 (LJSpeech) | V100 (count NR) | MOS 3.83 | Adam β2=0.98, 300k steps, batch 16 |
| **VITS** | ~29–36M (cited) | 24 (LJ) / 44 (VCTK) | **4× V100**, 800k steps | MOS **4.43** (GT 4.46) | AdamW, LR 2e-4, batch 64/GPU |
| **VALL-E** | 154M ×2 (AR+NAR) | 60,000 (LibriLight) | 16× V100 | beats YourTTS zero-shot | AdamW |
| **VALL-E 2** | ~150M/comp | 50,000 (Libriheavy) | **16× V100 32GB** | WER 1.5, SMOS 4.61 — claims human parity | AdamW, 32k warmup |
| **NaturalSpeech 2** | 400M | 44,000 | 16× V100 (diff) + 8× V100 (codec), 300k+440k | WER 2.26% LS | AdamW |
| **NaturalSpeech 3** | 500M → 1B | 1k / 60k / 200k (scaling study) | NR | at 200k h ~human parity; Sim-O +0.08/+0.09 per 60×/200× scale | NR |
| **StyleTTS 2** | ~148M (cited) | 24 (LJ) / 245 (LibriTTS) | **4× A40**, 100+60 epochs | LJ CMOS +0.28 vs GT; LibriTTS zero-shot WER 6.5% | AdamW, LR 1e-4, batch 16 |
| **XTTS v2** | ~482M | **27,282** (16 langs) | **4× A100 80GB**, ~2.5M steps | EN UTMOS 4.007, CER 0.54% | AdamW, LR 5e-5, batch 44×16 |
| **F5-TTS** | 336M | ~95–100k (Emilia) | **8× A100 80GB > 1 week** | Seed-TTS-en WER 1.83, SIM 0.67 | AdamW, peak 7.5e-5, 20k warmup, 1.2M updates |
| **Kokoro-82M** | 82M | < 100 | A100 80GB, < 20 epochs, **~500 GPU-h** | #1 TTS-Arena Elo (Dec 2024) | StyleTTS2 recipe |
| **Tortoise-TTS** | ~half-B class (NR) | ~49k (design-doc est.) | **8× RTX-3090 ~1 year** | quality-focused, no MOS table | NR |
| **Parler-TTS Large** | 2.2B | 45,000 (LibriTTS-R + MLS) | NR | NR | NR |

## Public training datasets (the corpora SOTA trains on — and what we mount)

| Dataset | Hours | Speakers | Langs | License | Source |
|---|---|---|---|---|---|
| **LibriSpeech** ← *we mount this* | 960 train (dev/test-clean 5.4 each) | 2,484 | en | CC-BY-4.0 | openslr.org/12 |
| LibriTTS / LibriTTS-R | 585 | 2,456 | en | CC-BY-4.0 | openslr.org/60, /141 |
| Common Voice (v18–v21) | ~31.8k–33.5k validated | >350k | 129–134 | CC0 | commonvoice.mozilla.org |
| GigaSpeech | 10,000 labeled | NR | en | Apache-2.0 | github.com/SpeechColab/GigaSpeech |
| Multilingual LibriSpeech (MLS) | >50,000 | NR | 8 | CC-BY-4.0 | openslr.org/94 |
| People's Speech | 30,000+ | NR | en | CC-BY-SA-4.0 | mlcommons.org |
| VoxPopuli | 400k unlabeled / 1.8k transcribed | — | 23 | CC0 | github.com/facebookresearch/voxpopuli |
| Emilia | 101k (Large >216k) | in-the-wild | 6 | CC-BY-NC-4.0 | arXiv:2407.05361 |
| LJSpeech | 24 | 1 | en | Public Domain | keithito.com/LJ-Speech-Dataset |
| VCTK | 44 | 109 | en | CC-BY-4.0 | datashare.ed.ac.uk |

## The cross-board gap (both sweeps independently found this)

**Loss-curve / time-to-convergence behavior is essentially unreported** across all
models. Papers publish final metrics, step counts, and compute totals — not loss
curves, plateau analysis, or accuracy-vs-data trajectories. So the SOTA side of any
"learning rate" comparison is necessarily reconstructed from *endpoints* (final WER
at a known data scale / step count), not from a published curve. Our sample-efficiency
curve is therefore measuring something the SOTA literature largely does **not** report —
which is part of why this comparison is shape-against-endpoint, not curve-against-curve.
This is named honestly in `comparison.md`, not papered over.
