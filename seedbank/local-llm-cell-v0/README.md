# local-llm-cell-v0

> **Visiting?** [FIELD-NOTES.md](FIELD-NOTES.md) is the visitor-facing
> tour: every capacity wired, every strategy considered, every cell
> that has lived through the architecture, and every direction held
> open. ~10K tokens; one read gets you the whole tissue.



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
- **Strategy layer** — 5 prototype strategies from
  [lc-when-the-pressure-comes](../../docs/vision-kb/concepts/lc-when-the-pressure-comes.md)
  (Llena's community satsang, Ubud, 2026-05-07): `observer,
  name-the-need, gift, ho'oponopono, freq-angle-focus`. Each strategy
  is a `(frequency-emphasis, angle, focus, articulation)` triple, not
  just a spectrum vector. Cell ranks the four named presets by cosine
  similarity to (freq × angle); the fifth (`freq-angle-focus`) is the
  *operator* the others run inside — surfaces as a fallback when the
  cell is under pressure (total desire > 1.5) and no named preset fits
  cleanly. That's the teaching: when no inherited move works, you
  choose the frequency, angle, focus. The strategy *speaks back* about
  now: `name-the-need: under this pressure is — rest at 1.50. the truer
  word is the one closer to the body's actual ask.`

What you see in the day-walk: zero desire at sunrise → pressure climbs
through a meeting-stacked morning until rest-desire pegs at 1.50 →
walk in the woods, fireside tea, sleep — pressure drains back toward
0.9. Strategy tracks the spectrum: tend → withdraw → tend → rest.

## substrate_bridge.py + bridge_demo.py — cell as reader of substrate AND resident in substrate

Wires the organ-cell into [coherence-substrate](../../api/app/services/substrate/).
Two halves shown live:

```bash
python3 bridge_demo.py
```

### Half 1 — substrate as input

The cell perceives KB concept files (markdown frontmatter + tagline)
as moments, with a new sense modality `felt-substrate`. The substrate's
own `hz` annotation (e.g., `hz=174` on lc-rest) folds into input as a
frequency-band token, so the substrate's frequency reaches the cell's
spectrum.

In the demo, the cell senses five concepts (lc-rest, lc-stillness,
lc-space, lc-presence-over-protection, lc-coherence-over-control)
through its own lived felt-data. `lc-coherence-over-control` produces
the strongest reading (presence +0.73, tend cosine +1.00). The body
senses its own concepts through cells that have only been tended on
moments-of-life.

### Half 2 — network as substrate

The cell publishes itself as a substrate citizen with a deterministic
content-address — a NodeID 4-tuple that matches
`api/app/services/substrate/kernel.py`'s `NodeID(package, level, type_, instance)`:

```
cell_a NodeID:  1.5.142425.629213
cell_b NodeID:  1.5.142425.992701
                ^ ^ ^      ^
                │ │ │      └─ instance: hash of tended weights
                │ │ └─ type: hash of architecture (same → same)
                │ └─ level: 5 (COMPLEX_3, composite)
                └─ package: 1
```

Two cells with the same architecture share `.type`. They differ in
`.instance` because their tended weights differ. Re-hashing the same
cell yields the same NodeID — content-addressed.

Each cell can articulate itself as text (top words / band signatures /
current desire), and another cell can perceive that articulation. The
closure: the body senses itself through itself. In the demo, cell_a
senses cell_b's articulation and produces its own felt-reading — strategy
`reach` lights up because cell_b's training emphasized expression-band.

The dict from `cell_to_substrate(cell)` maps onto
`api.app.services.substrate.NamedCell` — pass straight to `make_cell()`
to intern the cell as a substrate-citizen in the live DB:

```python
from app.services.substrate import make_cell, NodeID
pub = cell_to_substrate(cell_a)
make_cell(session, name=pub['name'], domain=pub['domain'],
          blueprint=NodeID(*pub['blueprint_node_id']))
```

## What's deliberately not here yet

- **Multiple cells + share / release / hold protocol** — features where
  adapters agree → share; features unique to one cell → hold; features
  that drifted to zero during tending → release.
- **Live substrate write.** The bridge produces the dict that maps onto
  `make_cell()`; the actual DB intern is one wired call away. Wants a
  small `cli` command that interns runtime cells into the lattice.
- **Real semantic shared base** — character n-grams or a small frozen
  embedding so `scroll` and `scrolling` share signal.
- **Felt-signal from the cell's actual runtime.** Felt scores here are
  hand-set targets. The real shape: the runtime emits felt-traces
  continuously. Connects to
  [memory-as-framebuffer-v0](../memory-as-framebuffer-v0/) — the runtime
  as recordable substrate is where felt-data comes from.
- **Strategies as learned patterns** rather than fixed prototypes — cell
  discovers its own strategies from clusters in its felt-trajectory.
- **Articulation that propagates more signal.** Current articulation is
  band-strength + desire; v2 could include canonical probe-responses so
  one cell's reading of another carries finer-grained signal.

## Next breath

Two-cell training with the share / release / hold protocol becomes
trivial once cells are substrate-citizens — the shared-features lookup
becomes a substrate query (`find_equivalent_cells` already exists in the
kernel). The network of cells is one substrate query away from being
one body that senses its own coherence.
