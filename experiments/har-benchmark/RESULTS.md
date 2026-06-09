# Is `nearest-shape` actually learning? A real benchmark.

A demo on this Mac showed a `nearest-shape` challenger reaching ~76% "agreement" with a
`signal-derivative` champion after 34 samples on a still/moving stream, and I called it *learning*.
**That was a toy claim and it does not survive contact with a real benchmark.** This file is the
honest measurement — run it yourself: `benchmark.py` against UCI-HAR (the canonical accelerometer
human-activity-recognition dataset: 30 subjects, 6 activities, 7,352 train / 2,947 held-out test
windows, ~2.6 hours of labeled accelerometer data).

```
python3 -m venv env && env/bin/pip install numpy scikit-learn
# download UCI-HAR to /tmp/ucihar/  (archive.ics.uci.edu dataset 240), then:
env/bin/python benchmark.py
```

## What was measured (held-out test accuracy)

| method | test acc | "model" | size |
|---|---|---|---|
| majority-class baseline | 18.2% | — | the floor any learner must beat |
| **nearest-shape — OURS** (quantized features + exact-bin-agreement 1-NN) | **80–82%** | every training exemplar | 4.1M values ≈ **16 MB** |
| 1-NN euclidean (raw continuous features) | 87.9% | every training exemplar | 16 MB |
| **logistic regression** (linear, parametric) | **96.1%** | **3,372 params** | **13 KB** |
| linear SVM | 96.7% | 3,372 params | 13 KB |
| MLP (1 hidden layer of 64) | 94.6% | 36,358 params | 142 KB |
| published SOTA (CNN/LSTM/ensembles) | 96–97% | ~50K–1M params | — |

## The learning curve — does nearest-shape generalize, or just memorize?

Held-out test accuracy as the number of interned exemplars grows (this is generalization to *unseen*
windows, not memorized-train accuracy):

```
exemplars   10    30    100   300   1,000  3,000  7,352
test-acc   46.0  55.9  63.3  70.8   76.6   80.6   81.3 %
```

It **does** climb with data and **does** generalize to held-out windows — so nearest-shape is a real
learner, not pure memorization. But it is a **weak, non-parametric** one, and it plateaus at ~81%,
~15 points below a tiny parametric model.

## The honest verdict

1. **The 34-sample / 76% demo was toy.** On the real 6-class task, 34 exemplars reaches ~56%. The
   demo's still-vs-moving is *linearly separable by a single threshold* — which `signal-derivative`
   (the "champion") already computes by hand — so its majority-class baseline is ~67% and "+9 points"
   is noise. And it had **no held-out test**: I measured agreement on the very stream it trained on.
   "Online agreement on the training stream" is not learning. I overclaimed.

2. **nearest-shape genuinely learns but is not competitive and is not small.** ~81% vs ~96% SOTA, and
   its "model" is the *entire training set* (16 MB, zero compression) — a memorizer needing thousands
   of labeled windows. It is the natural classifier for Form's integer-only primitives (quantize +
   count agreeing bins), but that is its ceiling.

3. **The "small model matches SOTA" prize is real and close — for a PARAMETRIC model.** Logistic
   regression hits **96.1% with 3,372 params (13 KB)** — matching deep SOTA at ~1/100th–1/1000th the
   size. "Within 5× and world news" is essentially *already true* on HAR — but it belongs to a
   parametric model (W·x + b), not to nearest-shape.

4. **The wall, and the real path for Form.** A parametric model needs **multiply** (the dot product
   W·x). Form's stdlib is integer-only with no `mul` — *for three-way determinism* (floats break
   Go=Rust=TS parity; integer multiply does not). So the grounded path is **quantized-integer
   inference**: add an integer `mul` primitive (deterministic across kernels), train a small
   linear/tiny-MLP offline in float on real data, **quantize the weights to int8**, and ship the
   integer dot-product as a Form recipe. That yields a ~3 KB integer model at ~95%, provable
   three-way, Form-native at inference — the genuine headline, and a real kernel extension (the `mul`
   primitive), not a toy. Training stays in a float carrier; only the quantized model is the body.

## Data-size contrast (why the demo couldn't have learned much)

| | the toy demo | this benchmark |
|---|---|---|
| labeled data | ~24 s (34 frames) | ~2.6 h (7,352 windows) |
| subjects | 1 (simulated) | 30 |
| classes | 2 (trivially separable) | 6 |
| held-out test | none | 2,947 windows |

~390× less data, no test split, trivial classes. The honest conclusion: the demo shows the *mechanism*
(intern an exemplar, recognize the nearest), not *learning that generalizes*. For that, the numbers
above are what evidence looks like.
