# Three Form-native challengers racing ECAPA-TDNN

**Champion:** ECAPA-TDNN (SpeechBrain `spkrec-ecapa-voxceleb`) — 80-d log-mel → Res2Net TDNN +
squeeze-excitation + attentive statistics pooling → 192-d embedding, trained with AAM-softmax on
VoxCeleb (~7k speakers, ~1M utterances). Cosine scoring, ~0.9% EER on VoxCeleb.

**The race:** the SAME recipe that proves four-way is the one that trains and crystallizes to
native — one engine, the champion is the oracle/teacher. All three challengers share the Form mel
front-end (`mel-frame.fk`) and the cosine recogniser (`speaker-embed.fk se-dot`); they differ in
the MODEL between features and embedding. We measure each by the cosine **margin** (same-speaker −
different-speaker) and EER on held-out trials, against ECAPA on the same trials.

Why ECAPA's <1% EER is hard, honestly: it's three things stacked — (a) a deep multi-scale
architecture, (b) **VoxCeleb-scale data**, (c) the **AAM-softmax margin** loss. A Form challenger
can match (a) and (c) as recipes; (b) — the data — is the real wall. So "anywhere close" means:
the learned challengers should reach single-digit margin separation on clear pairs and start to
crack the hard same-gender pair; matching <1% EER needs the data scale, named not hidden.

## Challenger 1 — "Stat" (zero training) — BUILT & PROVEN

`speaker-stat.fk` (PASS-4WAY, verdict 255). Pool the mel frames into a 40-d supervector:
per-band **mean** (timbre) ++ per-band **mean-absolute-deviation** (dynamics). Recognise by
cosine. No weights — the floor that pre-neural GMM/supervector systems stood on.

**Measured** on the three ceremony voices (separated stems), cosine (self ≈ 0.83):

| pair | C1 (Stat) | ECAPA | C1 margin from self |
|---|---|---|---|
| ubbe · brigitte | 0.505 | 0.113 | 0.33 |
| ubbe · angelia | 0.410 | 0.092 | 0.42 |
| brigitte · angelia (hard, same-gender) | **0.748** | 0.129 | **0.08** |

C1 separates clearly-different voices but **collapses on the hard same-gender pair** (margin 0.08).
That collapse is precisely the value learning must add.

## Challenger 2 — "Lin" (learned linear discriminant) — BUILT & MEASURED (honest negative)

`speaker-lin.fk` (PASS-4WAY, verdict 1023): a diagonal LDA over C1's supervector. The training is
Form — `sl-fisher` computes the per-dimension Fisher ratio (between-speaker / within-speaker
variance) from a grouped corpus; `sl-fisher-clamped` tames an explosive near-zero-within dimension;
`sl-center` signs the positive band features before scoring. Trained on 7 speakers × 3 windows.

**Measured — it does NOT beat C1:**

| pair | C1 | C2 (center + Fisher) |
|---|---|---|
| ubbe·brigitte | 0.512 | 0.875 |
| ubbe·angelia | 0.619 | 0.998 |
| brigitte·angelia (hard) | 0.768 | 0.885 |

The honest finding: a *diagonal* reweighting of hand-crafted band energies can't separate voices
whose identity isn't axis-aligned, and 7-speaker variance estimates are too noisy to trust — C2
moved the cosines the wrong way. This is the real lesson of the race: the value ECAPA holds is not
reweighting fixed features but **learned features + a full (rotating, nonlinear) embedder + data
scale**. A *full* projection `W` (rotation, not just per-axis scale) trained by SGD over real data
is the salvage path for a linear C2; the decisive jump is C3. Recipe + machinery are proven and
reusable; the negative result is named, not hidden.

## Challenger 3 — "Net" (small neural embedder, the real ECAPA shape) — DESIGNED

A scaled-down x-vector/ECAPA: mel frames → 2–3 time-delay (conv) layers with frame context →
statistics pooling (mean+std over time) → 1–2 dense layers → 128-d embedding, trained with
AAM-softmax (or triplet) over many speakers. This is the architecture that *is* ECAPA minus the
Res2Net/SE depth and the data scale. Built from the proven transformer-training tissue
(`transformer-corpus-train.fk`, `transformer-block.fk`, `softmax-ln.fk`, `form-train-step.fk`) —
the same recipes that train the Form whisper block four-way; native speed via the emit→asm lane.
Expectation: the closest to ECAPA — single-digit EER reachable with enough public speaker data;
the residual to <1% is the VoxCeleb-scale data wall.

## Evaluation harness

`champion-challenger.fk` (`cc-reaches?` / `cc-promote?`) scores each challenger's per-trial
correctness against ECAPA's; the gate promotes a challenger only when it reaches the champion on a
held-out set. Trials = same/different-speaker pairs from public clips (`challenger-supervector.sh`
for C1; ECAPA via `ecapa_embed.py`). Data + roster stay private; only recipes and the measured
margins ship.
