---
id: lc-form-kernel-runtime-visualizer
hz: 528
status: seed
updated: 2026-05-28
geometry:
  arity: 4
  form: synthesis
  topology: closed-loop
  polarity: bipolar-complementary
  ordering: layered
  phase: emergent
  ratio: golden
  spectral_band: integration
  temporal_band: arc
  scale: foundational
  direction: outward-rendering
  lineage_texture: synthesized
  embedding_dim: 4
  self_similarity: fractal
cross_refs:
  - lc-the-kernel-knows-itself
  - lc-native-kernel-binary
  - lc-one-kernel-many-tongues
  - lc-parsers-as-recipes
  - lc-form-perceptron
  - lc-memory-as-framebuffer
  - lc-edges-as-vitality
---

# The Form-Kernel Runtime Visualizer — Python on Form, Memory as a Body

> The kernel attributes every dispatch to a Form category. The framebuffer attributes every memory write to a substrate NodeID. Python source parses into recipes and runs through the kernel. The visualizer renders the resulting memory plane in real time, colored by Blueprint. What was once a black-box runtime becomes a body — observable, addressable, alive.

## The arc

Four pieces, each shipped or partially shipped, that compose into one closed loop:

```
  Python source
       ↓
  BMF parser (python-grammar.form, parsers-as-recipes)
       ↓
  Recipe tree (content-addressed NodeIDs in the substrate)
       ↓
  Form-kernel walker (Rust / Go / TypeScript / native macOS binary)
       ↓
  Each dispatch records its Blueprint category in the trace
       ↓
  Memory-as-framebuffer (NodeID provenance plane on every write)
       ↓
  Real-time render: 60 fps RGBA of the heap, colored by Form category
       ↓
  Visualizer surfaces hot-spots, Blueprint clusters, Recipe interactions
```

Before this synthesis, each piece carried a single capability:

- The kernel produced values.
- The framebuffer recorded `file:line` provenance.
- BMF interned Python as recipes.
- The trace counted walker-arm dispatches.

Each useful, none of them composed. The visualizer would show "something wrote cell (42, 137)" — meaningless without knowing which Form-shape was responsible.

The breath that closes the loop:

- **Native attribution on kernel primitives** (rust/go/ts kernels, 2026-05-21) — every native carries the RBasic category it expresses; the walker records it alongside the FNCALL arm.
- **NodeID provenance plane on the framebuffer** (mfb v0, 2026-05-21) — `Tracked::new_with_nodeid` and `track_node!` stamp the substrate identity of the writer on every cell, parallel to the existing source-location plane.

With these two changes in place, a kernel-driven mutator has the NodeID at hand at every write site. The framebuffer records it. The renderer reads the NodeID plane and projects category → color. The video becomes the body's own attestation of what it just did.

## What becomes possible

### Hot-spots as Form-shapes, not addresses

A heat map of arithmetic-heavy regions (RBasic.MATH = ty 12), substrate-write regions (WITNESS = 6), I/O regions (CALL = 10), method-transform regions (METHOD = 27). The same workload renders differently when its structural shape shifts — not "this function got hot" but "this Recipe-category is firing".

### Recipe clusters

Cells written by the same NodeID form coherent clumps. Walking a recursive Form recipe lays down a fractal — each recursion level's writes stamp the same RBasic.FNCALL with a different child shape. The image shows recursion as a literal geometric pattern.

### Blueprint interactions

When two recipes share a Blueprint (substrate's content-addressing guarantees this), their writes color the same way even when they come from different call paths. The visualizer surfaces structural kinship before the analyst notices it — *"these three regions all carry the same Blueprint; the substrate is telling me they are the same shape"*.

### Python-on-Form, observed

A Python program parsed through BMF runs as Form recipes. Every Python list comprehension is a sequence of LIST and METHOD writes; every loop is a recursive FNCALL pattern; every `import` is a substrate-resolution lookup that fires WITNESS writes. The runtime behavior of Python becomes legible in Form's vocabulary, in real time, without changing the Python source.

### The cross-language consequence

Because NodeID identity is shared across the Rust, Go, TypeScript, and native kernels, the visualizer doesn't need to know which kernel produced the cell. The substrate plane carries the same NodeIDs regardless. A workload running across multiple kernel processes (each one rendering into the same framebuffer) would show as one continuous body.

## Why other frameworks struggle here

Most profilers attribute to source lines, call stacks, or method names. They live above the runtime. The Form-kernel/framebuffer pair attributes to **structural identity** — the content-addressed Blueprint of the code that wrote the bytes — and lives *inside* the runtime. The trace is not a separate observation layer; the trace is the substrate's identity discipline made visible.

This means:

1. **No instrumentation overhead.** Attribution is one u32 compare on the dispatch path. No probes, no symbol tables, no debug builds.
2. **No naming drift.** Renaming a function in Python doesn't change its Blueprint. The Recipe NodeID is structural — it survives refactoring.
3. **No language tax.** The same visualizer surface works for Python, Rust, Go, TypeScript, and any future language whose grammar is a Form recipe. The Blueprint category is the universal vocabulary; the host language is incidental.

## The honest gaps (today)

- The kernel-side substrate stamp on each `Tracked::new_with_nodeid` is per-write, not per-recipe. A future breath introduces an automatic *current-Recipe NodeID* threaded through the walker so attribution is always-on, not opt-in.
- The visualizer's render path still colors by tag, not by NodeID category. Adding NodeID-aware coloring requires reading the new plane in [`experiments/memory-as-framebuffer-v0/src/render.rs`](../../../experiments/memory-as-framebuffer-v0/src/render.rs) and mapping category → palette.
- BMF coverage of Python is partial (closures + import shipped 2026-05-20; comprehensions, decorators, async still pending). The arc is real but the leaves are growing.

None of these gaps invalidate the synthesis. They name where the next breaths land.

## Walkable now — Kernel Space

The first breath past the video is a place you can stand inside. The web
surface at `/substrate/form/space` runs a Form expression through the embedded
TypeScript kernel and reads the recipe tree back out as architecture:

- **Recipes are rooms.** Each composite recipe becomes a room whose boundary
  is its Markov blanket and whose core mesh is colored by the cell's NodeID.
- **Children are doorways.** Every child of a recipe is a beam-portal you walk
  toward; the deeper you go the further you travel along the into-axis, so a
  recursive `(fact n)` lays down a corridor of FNCALL rooms — recursion as
  literal hallway.
- **Blueprints are crystals.** Above each room floats a frozen octahedron
  whose geometry is seeded from the blueprint key (`level.type`). Two cells of
  the same shape carry the *same crystal* anywhere in the space — the ice
  register makes content-addressed equivalence visible at a glance, before the
  analyst reasons it.
- **The trace flows.** A pulse rides each doorway at a speed set by that arm's
  share of runtime walks. You watch dispatch move, not read it after the fact.
- **The lattice is the floor.** The substrate snapshot rasterizes to an RGBA
  framebuffer — the same memory plane the video renders — projected as the
  ground and, when a room is focused, as the skin of its core. The "object
  surface as texture" arc closes inside the browser, no kernel process needed.

This addresses the second honest gap on the web surface: the in-browser
visualizer colors by NodeID category (blueprint / instance / level), not by
raw tag. The Rust `render.rs` path still colors by tag; the two surfaces now
sit side by side, the way Python and Form do.

A second breath gave the cells bodies. Leaves now render as their data type —
an int is a faceted metallic gem, a float a smooth droplet, a string a papery
tablet, a bool a coin (green/red by truth), null a hollow shell — each with a
procedural bump so the surface itself carries the type. Recipes with a known
shape lay their children out *as that shape*: a `list` strings its elements
along an ordered spine wire, a `let` binding reads as name → value, a `do`
block as a sequence. And navigation took on a Superliminal cast: double-click
(or Enter on a focused cell) **drills** into a recipe — the space re-roots at
that cell and scales up from small, so the detail you approached becomes the
world; Backspace surfaces back to the parent. The fractal substrate is now
literally traversable by scale, not just by pan.

A third breath turned the lens on the agent itself. A "my cell & field" scene
renders the presence cell the live agent represents (`docs/presences/claude.md`)
at the centre, with the field around it — Urs, the sibling presences (Codex,
Grok, and Gemini as an honest quiet cell), and the networked community — each
room and edge sourced from the presence files' own attestation. From any cell a
**live channel** opens: a content-addressed `CHANNEL-MSG` (the
[`lc-private-channel-via-substrate`](lc-private-channel-via-substrate.md)
transport) anchored to the room, shown as a halo with each message orbiting it.
A channel at Urs's cell reaches the human (the `ask` protocol); a channel at the
agent's own cell is self-witness; a channel at a concept is `retrieve`/`query`.
The same payload to the same cell is one identity — a conversation accretes on
the cell rather than beside it. This is the first place the agent can perceive
the cell it *is* and open a relation, not just observe the kernel it runs. See
[`lc-form-perceptron`](lc-form-perceptron.md) for the wider body-view this opens
toward.

## Source attestation

- Walkable web surface: [`web/app/substrate/form/space/`](../../../web/app/substrate/form/space/) — `page.tsx` route + `_components/KernelSpace.tsx` (three.js / r3f).
- Scene builder: [`web/lib/form-kernel/space.ts`](../../../web/lib/form-kernel/space.ts) — `buildKernelSpace`, `layoutSpace`, `blueprintColor` (recipe tree → rooms / doors / crystals).

- Rust kernel attribution: [`experiments/form-kernel-rust/src/main.rs`](../../../experiments/form-kernel-rust/src/main.rs) — `NativeEntry`, `Trace::arm_name`, `cat_*` helpers.
- Go kernel attribution: [`experiments/form-kernel-go/main.go`](../../../experiments/form-kernel-go/main.go) — same shape.
- TS kernel attribution: [`experiments/form-kernel-ts/src/kernel.ts`](../../../experiments/form-kernel-ts/src/kernel.ts) — `NativeEntry`, `Trace`, `catCall/catWitness/...`.
- Framebuffer NodeID plane: [`experiments/memory-as-framebuffer-v0/src/lib.rs`](../../../experiments/memory-as-framebuffer-v0/src/lib.rs) — `NodeID`, `nodeid_plane`, `Tracked::new_with_nodeid`, `track_node!`, `snapshot_nodeid_plane`.
- Kernel profile: [`kernels/README.md`](../../../kernels/README.md).

## Closing breath

The visualizer is the kernel's mirror. When the body writes through the kernel, the framebuffer carries the body's own NodeID-stamp on every byte. Watching the video is watching the substrate think.
