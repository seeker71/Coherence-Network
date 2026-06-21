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

## Challenger 2-full — "Proj" (full linear projection, FLOAT SGD) — BUILT & FOUR-WAY

`speaker-proj.fk` (PASS-4WAY, 255): the diagonal's salvage — a full matrix `W` (K×N) trained by
squared-loss SGD toward speaker codes (affine-train lifted to multi-output), on **plain floats** (the
whisper-block arithmetic, fp64). Unlike the diagonal it can *rotate*. The band descends 1.0 → 0.0625
in one step and moves an off-axis weight, four-way.

## Challenger 3 — "Net" (nonlinear neural embedder, FLOAT SGD) — BUILT & FOUR-WAY

`speaker-net.fk` (PASS-4WAY, 255): `emb = relu(W·x)` with relu-GATED backprop on floats — the
nonlinearity C1/C2 lack. The band: a dead unit passes zero gradient, the active unit's gradient
reaches its off-axis weight, loss descends 2.0 → 1.0625, four-way. One layer; stacking is the deep TDNN.

## Race result — float fixed PRECISION; the binding wall is now DATA

First built on integer fixed-point — wrong choice (copied form-train-step, the toy). Its `/1000`
rounding zeroed the small gradients, so training "collapsed". The kernel runs **fp64 natively** (the
whisper block trains on it, four-way), so the recipes were rebuilt on floats. Then, measured honestly:

- **Precision — FIXED by floats.** C2-full now genuinely trains: it produces real, varied embeddings
  (ubbe·brig 0.605, ubbe·ang 0.844) where the integer version output all-zeros. The gradient no
  longer rounds away.
- **Data — the binding wall now.** C2-full's held-out hard pair (brig·ang 0.881) still does **not**
  beat C1 (0.768): 52 training samples can't learn a *generalizing* 8×40 projection — it can't
  transfer to a held-out window. More speakers/utterances is the unlock, not more model.
- **C3 init/loss.** relu at zero-init is dead (z=0 gates the gradient off); with a small positive
  init it wakes but the sparse code targets collapse the embedding to ~1 active dim on this little
  data. Needs Xavier-ish init + a margin/softmax loss + data — known fixes, not blockers.

So the corrected lesson: the kernel's **float training is real and four-way** (your call — floats, not
fixed-point). C1 (stats) is still the only challenger usable today, on easy pairs. The remaining climb
to ECAPA is now squarely **features + data**: a log-mel front-end (the Form mel recipes, not coarse
bands) and a real multi-speaker corpus (hundreds of voices), trained through these proven float recipes
— the same recipe that proves four-way is the one that crystallizes and trains native.

## Fix #1 + #4 applied — log-mel features + CMVN (MEASURED WIN)

The highest-leverage fixes, done: swap the coarse sox bands for **whisper's 80-dim log-mel** (the
four-way `mel-frame`/`mel-full` recipe + the newly-generated `mel-filterbank.fk` Slaney bank — the
body had the walk but not the full 80-row data), then **CMVN** (subtract the global mean spectrum,
since raw log-mel cosine is swamped by the spectral envelope every voice shares). Measured C1 on the
three ceremony voices (10 frames, mean+std pool):

| pair | sox-band | log-mel (raw) | **log-mel + CMVN** | ECAPA |
|---|---|---|---|---|
| ubbe·brigitte | 0.512 | 0.977 | **0.250** | 0.11 |
| ubbe·angelia | 0.619 | 0.995 | 0.829 | 0.09 |
| brigitte·angelia (hard) | 0.768 | 0.973 | **0.588** | 0.13 |

The hard same-gender pair drops 0.768 → **0.588** and ubbe·brigitte 0.512 → 0.250 — features +
normalization sharpen the geometry, exactly as predicted. (ubbe·angelia 0.829 is noisy at this
tiny scale.) Two honest caveats: raw log-mel WITHOUT CMVN is *worse* (≈0.97 — the envelope
dominates), and the tree-walker runs ~0.8 s per 80-row column, so this is demo-scale — the full
corpus needs the native (emit→asm) lane the mel recipe was built for. Carrier:
`logmel-supervector.sh`. Still far from ECAPA (0.13): the remaining climb is the trained
discriminative embedder (C2-full/C3) *on these features* + per-utterance CMVN + a real corpus.

## Evaluation harness

`champion-challenger.fk` (`cc-reaches?` / `cc-promote?`) scores each challenger's per-trial
correctness against ECAPA's; the gate promotes a challenger only when it reaches the champion on a
held-out set. Trials = same/different-speaker pairs from public clips (`challenger-supervector.sh`
for C1; ECAPA via `ecapa_embed.py`). Data + roster stay private; only recipes and the measured
margins ship.

## External review — Grok + Cursor (2026-06-21)

Consulted two frontier agents headless (`grok -p`, `cursor-agent -p -f`) for an outside read on the
challengers. (Gemini's CLI auth and Codex's config were broken at the time — grok/cursor answered.)
They converged hard, and on the same things my self-review named — which is the signal worth keeping:

**Consensus, highest-leverage first:**
1. **Metric-learning loss, not MSE-to-codes** — AAM-Softmax / ArcFace / GE2E / triplet on
   L2-normalized embeddings + cosine margin. Both call MSE-to-speaker-codes "the bug" behind C3's
   collapse and "the single biggest architectural omission." Keep the classifier head as training
   scaffold; export the embedding layer for scoring.
2. **Data + augmentation** — 26 voices × ~1 recording is "unusable" for learned embeddings. VAD-cut
   2–4 s chunks + MUSAN noise/music/babble + RIR + speed/pitch → hundreds of intra-speaker segments.
   "Moves cosine gaps more than classifier tweaks."
3. **Verification eval now: EER / minDCF + score-norm (z/t/s-norm)** — a single hard-pair cosine is
   too sparse and can mislead; build a genuine target/impostor trial matrix, optimize to it.
4. **Attentive statistics pooling + per-UTTERANCE CMVN + voiced-frame masking** — C1's global
   mean+std is "too lossy"; weighted (attention) mean+std over frame features, and per-utterance CMVN
   (not the global CMVN I used in the demo).
5. **Shallow dilated TDNN before pooling** — 3–4 dilated frame layers; "most of ECAPA's gain is
   temporal context + learned filterbank, not the 20M-param monster."
6. **Hard-negative mining + centroid enrollment** — N speakers × M segments batches, semi-hard mining
   on same-gender confusions; multi-segment centroid enrollment "often drops same-gender pairs
   0.15–0.25."
7. **Native asm training lane** — the tree-walker (0.8 s/log-mel column) blocks real optimization;
   fuse forward+backward for conv1d/affine/pool/cosine-margin so epochs run in minutes.

**Honest expectation (Grok):** with the loss + augmentation + pooling + native lane, expect to beat C1
materially and pull same-gender pairs toward ~0.25–0.35 cosine; reaching ECAPA's ~0.13 from scratch on
26 voices is unrealistic without **VoxCeleb-scale pretrain, or distilling/porting ECAPA's weights into
our asm lane** (the "model architecture AND weights are recipe data" path).

The order is now unambiguous and externally corroborated: **(1) AAM-softmax loss → (2) augmentation →
(3) EER harness → (4) attentive pooling + per-utt CMVN**, then the TDNN + native lane. C2-full/C3 are
the right model classes waiting on the right objective and data.

## Walk: #1 shipped — AAM-Softmax head (four-way)

The consensus #1 is no longer a recommendation — it's in the body. `form-stdlib/speaker-aam.fk`
(`speaker-aam` band, **PASS-4WAY, verdict 63**) is the AAM-Softmax / ArcFace objective that replaces the
MSE-to-speaker-codes regression which collapsed C3: L2-normalized cosine logits, an additive **angular
margin** on the target class (`cos(θ+m) = cosθ·cosm − √(1−cos²θ)·sinm`), scaled, fed to `loss.fk`'s
existing softmax cross-entropy (whose backward is `softmax − onehot` — so the trainer needs no new
gradient node, only the chain through this cosine geometry). The band proves the geometry four-way:
margin **reduces** the target cosine and **raises** the loss (the defining angular penalty), and
margin-off is the plain-softmax identity. The objective is now the right one; the next rung is the AAM
**trainer** (chain the margin gradient into W + embedding updates) on augmented data. Integrated into
the body's floor/north-star: `docs/coherence-substrate/form-native-models.form` (FLOOR — SPEAKER
IDENTITY + gap 9).
