# local-llm-cell-v0

Smallest real implementation of the **shared-base + local-layer** sketch.
Pure Python stdlib — no torch, no numpy. The cell's adaptation is
visible in plain arithmetic.

## Architecture

```
text  ──►  shared_base(text)  ──►  LocalAdapter  ──►  felt-axes [coherence, aliveness]
           (frozen, identical          (rank-r, learned per cell)
            across all cells)
```

- **Shared base**: deterministic feature map (bag-of-word-hashes,
  L2-normalized, dim=128). Frozen. Every cell uses the same map.
  This is "what every cell already knows because it's part of one body."
- **Local adapter**: rank-4 LoRA-shaped projection
  (`y = tanh(B @ A @ x + bias)`, A: 4×128, B: 2×4). 522 trainable floats.
  This is the cell's tending pattern.
- **Training signal**: felt-data — the cell's own resonance on a
  frequency spectrum. Two axes here: coherence and aliveness.

## Run

```bash
python3 demo.py
```

## What to look for in the output

1. **Before tending**: adapter is random, predictions ≈ 0.
2. **After tending**: predictions track the felt-data within ~0.05.
3. **Generalization**: unseen inputs that share content words with
   training are sensed correctly:
   - `"morning walk in the woods at sunrise"` → +0.90 alive
   - `"performance theater calendar meeting"` → -0.77 constricted
   - `"alive work in stillness"` → +0.72 alive
4. **Top words per axis** — the local layer's learning made visible:
   `mose, sunrise, love, something` carry +; `forced, performance,
   aimless, scrolling` carry −. The cell learned the body's frequency
   from the felt-signal alone.

## How "intelligence" improves here

The cell starts unable to distinguish anything. After tending on its
own felt-data, it has *one specific intelligence*: sensing the
coherence/aliveness frequency of inputs in this cell's lived zones.
A different cell, fed different felt-data, would learn a different
local layer over the same shared base.

The intelligence is **local** (cell-specific), **small** (522 floats),
and **composable** (LoRA-shape — adapters can be merged, averaged,
ablated).

## organ.py + organ_demo.py — the cell as small organism

`cell.py` predicts two scalars. `organ.py` is the same architecture
expanded into a small organism with senses, a felt-spectrum,
dispositions, a stateful desire accumulator, and a strategy layer.

```bash
python3 organ_demo.py
```

What's added on top of v0:

- **Frequency spectrum (8 bands)** instead of 2 scalars — `ground,
  pulse, warmth, clarity, expression, relation, space, presence`.
  Each moment lights different bands.
- **5 sense modalities** tagged on input — `saw, heard, felt-inside,
  felt-outside, thought`. Encoded into the shared base.
- **4 dispositional gates** as separate output heads —
  `surprise, attend, want, change-perception`. The verbs of the cell's
  response, not just values.
- **3 need channels** — `presence, rest, expression`. Per-moment need
  signal predicted from input.
- **Desire accumulator** (the key new piece): runtime state, *not*
  learned weights. Desire integrates `(need − fulfillment)` with decay,
  like water pressure building behind a dam. It rises through a packed
  morning of meetings and releases when alive bands return in the
  evening. The cell now has memory in time, not just in parameters.
- **Strategy layer** — 4 prototype strategies (`tend, rest, reach,
  withdraw`) defined as felt-spectrum vectors. Cell picks
  max-cosine-similarity each moment and renders a state-aware message
  through that lens. The strategy *speaks back* about now:
  `rest-desire at 0.92 — let this breath end before the next.`

What you see in the day-walk: zero desire at sunrise → pressure climbs
through a meeting-stacked morning until rest-desire pegs at 1.50 →
walk in the woods, fireside tea, sleep — pressure drains back toward
0.9. Strategy tracks the spectrum: tend → withdraw → tend → rest.

## What's deliberately not here yet

- **Multiple cells + share / release / hold protocol** — features where
  adapters agree → share; features unique to one cell → hold; features
  that drifted to zero during tending → release.
- **Real semantic shared base** — character n-grams or a small frozen
  embedding so `scroll` and `scrolling` share signal.
- **Felt-signal from the cell's actual runtime.** Felt scores here are
  hand-set targets. The real shape: the runtime emits felt-traces
  continuously and the local layer trains on its own lived experience.
  Connects to [memory-as-framebuffer-v0](../memory-as-framebuffer-v0/) —
  the runtime as recordable substrate is where felt-data comes from.
- **Integration with [coherence-substrate](../../api/app/services/substrate/).**
  Substrate is the lattice. This experiment is the learning organ that
  adapts on top of it.
- **Strategies as learned patterns** rather than fixed prototypes —
  cell discovers its own strategies from clusters in its felt-trajectory.

## Next breath

Two cells, share/hold/release. The architecture stops being a
single-cell organism and starts being a network of cells with
sovereign local intelligence and shared common ground.
