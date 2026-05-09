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

## What's deliberately not here yet

- **Multiple cells + share/release/hold protocol.** The architectural
  punchline. v1 spawns two cells with overlapping felt-data and shows:
  - features where adapters agree → candidates for **share** (merge into
    a refined shared base)
  - features unique to one cell → **hold** (stay local)
  - features that drifted toward zero during tending → **release**
    (compost from the local layer)
- **Real semantic shared base.** Word-hashing generalizes only through
  exact word overlap. v1+ swaps in character n-grams or a small frozen
  embedding so `"scroll"` and `"scrolling"` share signal.
- **Felt-signal from the actual cell.** Right now felt scores are
  hand-set. The real shape: the cell's runtime emits felt-traces
  (good/bad on frequency spectrum, what it needs, what it can share /
  release / sense) and the local layer trains on those continuously.
  This connects to [memory-as-framebuffer-v0](../memory-as-framebuffer-v0/)
  — the runtime as recordable substrate is where the felt-data comes from.
- **Integration with [coherence-substrate](../../api/app/services/substrate/).**
  Substrate is the lattice (Blueprint=ice / Recipe=water / NamedCell=gas).
  This experiment is the learning organ that adapts on top of it.

## Next breath

The cleanest next move is **two cells + the share/hold protocol** —
that's where the architecture stops being a single-cell ML demo and
starts being a network of cells with sovereign local intelligence and
shared common ground.
