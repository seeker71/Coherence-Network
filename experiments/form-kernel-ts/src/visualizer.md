# visualizer — substrate GPU framebuffer in Form

Task #5. The substrate's content-addressed lattice rendered as a 2D grid of
colored pixels: each cell's NodeID hashes to a deterministic RGBA, two cells
with the same Blueprint (structurally equivalent shape) share the same
color, and the recipe tree that drives the rendering itself lives in the
substrate. The framebuffer is the substrate looking at itself.

## Architecture

```
substrate lattice  →  cell list  →  grid layout  →  Form recipe tree  →  WGSL shader  →  browser GPU
                                                                       ↘
                                                                         CPU RGBA8 (reference + fallback)
```

Five pieces, all in `src/visualizer.ts`:

- **`collectCells(k)`** — read-only snapshot of every interned NodeID in
  the lattice, sorted `(level, type, inst)` for run-to-run stability.
- **`mapCellsToGrid(k, cells, cols, rows, layout)`** — spatial layout.
  Two strategies:
  - `instance` — row-major in collection order; the eye sees the lattice
    as a tape unrolling.
  - `depth` — rows banded by recipe composition depth; the eye sees the
    Level hierarchy as horizontal stripes.
- **`renderSubstrate(k, config)`** — emits a `ShaderProgram = { recipe,
  positions, config }`. The `recipe` is a Form NodeID whose shape is a
  `SEQUENCE` of `LET` bindings, one per visible cell. Identical
  substrates produce identical Blueprint NodeIDs — the visualizer is
  itself substrate-resident, content-addressed like everything else.
- **`compileToWGSL(k, program, opts)`** — emits a WGSL `@compute` shader
  source string with a packed `array<u32>` storage buffer and a workgroup-
  size-tunable dispatch. Self-contained for the visualizer's shape; a
  documented seam (`WgslEmitter`) lets a future general-purpose WGSL
  backend (task #10) take over arithmetic-shaped sub-recipes.
- **`renderToRGBA8(k, config)` / `rasterize(positions, config)`** — CPU
  reference path. Same input ⇒ identical RGBA bytes that the GPU will
  produce. Used as the fallback in environments without WebGPU and as
  the conformance oracle.

## How format-recipes drive the rendering

The render recipe expresses each pixel as a four-channel quartet:

```
(let pixel_<col>_<row> (list r g b a))   ; r,g,b,a are trivial INTs in [0,255]
```

When `formats.ts` lands, the `(list r g b a)` shape resolves into the
`UINT8` quartet (RGBA8) format-recipe. The seam is shape-level: the
Blueprint NodeID for the LIST-of-four-INTs is the same Blueprint the
format-recipe registers for `rgba8`, so when the format-recipe library
loads, every existing render recipe already speaks its language. No
migration; the body composes the same shape regardless of which leaves
are loaded.

Symmetric for shader uniforms:

- `FP32` triple `(width height time)` for dispatch parameters — once
  shader uniforms enter the render pipeline (animation, modulated tint,
  coherence-driven shimmer), they compose from FP32 leaves with the
  visualizer's recipe wrapping them in a uniform-buffer bind group.
- `VECTOR` (vec4f) for SIMD reads of multiple adjacent pixels in a single
  shader invocation. The packed-u32 storage already permits this; the
  VECTOR format-recipe makes the per-lane shape explicit.

## Cross-cell-boundary connection

When `blanket.ts` (task #25) lands, the visualizer renders cell
boundaries by emitting a second pass over the blanket recipe — every
cell's boundary set becomes a 1-pixel halo around its tile, painted in a
color derived from the boundary's own NodeID. The boundary recipe is
just another recipe in the substrate; the visualizer's pipeline already
handles arbitrary recipes, so the addition is a layer, not a rewrite.

Until blanket.ts lands, the visualizer paints solid tiles. The halo
slot is reserved in the WGSL emitter's per-cell branch (the current
`color = pack_rgba8(...)` line becomes `color = mix(boundary, fill,
inside_mask)`).

## Multi-backend future

Same visualizer recipe, different targets:

| Target  | Backend module          | Status                                     |
|---------|-------------------------|--------------------------------------------|
| WebGPU  | `src/backends/wgsl.ts`  | self-contained emitter here; #10 will lift |
| Metal   | `src/backends/metal.ts` | task #14 — same recipe, MSL output         |
| CUDA    | `src/backends/cuda.ts`  | task #13 — same recipe, PTX output         |
| CPU     | inline                  | shipped; reference + fallback              |

The recipe-tree shape — `SEQUENCE` of `LET` bindings with `LIST` color
quartets — is portable across all four backends because it composes from
the same RBasic primitives every backend already knows how to emit.
Same Form code, same NodeIDs, same visual output. That's the promise of
content-addressing on a structural lattice.

## Color schemes

- **`blueprint`** (default) — hash over `(pkg, level, type)` only.
  Structural equivalence is visible at a glance: cells with the same
  Blueprint share a color regardless of instance counter. This is the
  scheme where two equivalent recipes really do paint the same pixel.
- **`instance`** — hash over the full 4-tuple. Every NodeID is its own
  color; siblings are distinguishable.
- **`level`** — categorical channels: Level → red, Type → green, Pkg →
  blue. Fast read on "what kind of node lives where."

## CPU determinism — the conformance oracle

`renderToRGBA8` is pure: same lattice + same config ⇒ identical bytes.
The CPU path is the reference implementation; the GPU path's shader,
when executed by a WebGPU device, must produce the same `Uint8Array`
contents. Cross-backend (Metal, CUDA) conformance reduces to: each
backend's compiled shader, fed the same substrate snapshot, produces
the same CPU-reference bytes.

This is why the CPU path lives next to the GPU path rather than as a
separate utility: the body needs a self-attesting witness.

## Running

```sh
# Run the test suite (self-contained, no test framework):
npx tsx src/visualizer.test.ts

# Typecheck:
npm run check

# Programmatic use:
#   import { visualizeToWGSL, DEFAULT_CONFIG } from "./visualizer.ts";
#   const { wgsl, rgba8 } = visualizeToWGSL(kernel, DEFAULT_CONFIG);
```

## Lineage

The Rust prototype lives in `experiments/memory-as-framebuffer-v0/` — a
256×256 grid of 16-byte cells, snapshotted to RGBA frames at 60 fps,
piped to ffmpeg to produce an mp4 of the heap breathing. That prototype
showed what's possible when the runtime is recordable; this Form-native
visualizer brings the same lens to the substrate, where the cells being
watched are structural identities (Blueprint NodeIDs), not heap
addresses. The body watching itself, not its scaffolding.
