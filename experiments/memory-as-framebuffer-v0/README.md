# memory-as-framebuffer v0

The runtime as a recordable video.

A 256×256 grid of 16-byte cells (1 MB heap) holds `Tracked<T>` values for nine
primitive types. A parallel `u32` plane stores `crc32(file:line)` for each
cell's last write — provenance. A snapshot thread renders both planes to RGBA
frames at 60 fps and pipes them to `ffmpeg`, producing an mp4 of the heap
breathing.

## Prerequisites

- Rust 1.75+ (this crate developed against 1.95)
- `ffmpeg` on `PATH` (with `libx264`)

## Run

```bash
cargo run --release --example fizzbuzz
```

This produces `fizzbuzz.mp4` in the crate directory (~30 seconds, 1024×1024,
60 fps, h264).

## What you'll see

The fizzbuzz example only allocates 100 cells out of the 65,536-cell heap.
With deterministic next-free-slot allocation, those 100 cells live at
indices 0..99 — which on the 256×256 grid is **the very top row** at
y ∈ [0, 4) px. So you're looking at a thin **400×4 px lit strip** along
the top edge of the 1024×1024 frame, with the rest correctly black
(free cells render as black). LOD-zoom — the v1-3d sibling spec — is the
proper UX answer for "show me where the activity actually is"; v0
renders the heap honestly at fixed 1:1 scale.

What's happening in that strip:

- **Cell 0** (top-left, single 4×4 px block): the current `i` (1..=10000).
  Inner color is the `u32` palette entry, modulated within a 0.7..1.0
  brightness range so it stays clearly visible at any value; a CRC-driven
  channel offset gives value-change flicker.
- **Cells 1..99** (the rest of the top strip): the rolling fizz/buzz
  history. As the loop runs, tag values shift down the strip: `1=plain`,
  `2=fizz`, `3=buzz`, `4=fizzbuzz`. Inner color is the same palette entry
  (all `u32`); the CRC-driven flicker per-value gives a perceptible drift.
- **Halos** (outer ring of every 4×4 block): the provenance hash. The
  four branches of the fizzbuzz `match` (`write_plain`, `write_fizz`,
  `write_buzz`, `write_fizzbuzz`) each live at a distinct `file:line`, so
  each branch's halo color is distinct. You should see the strip's halos
  shimmer between four colors as the loop progresses.

## Tests

```bash
cargo test --release
```

The smoke test runs the example as a subprocess, validates the mp4 exists,
extracts the first frame with `ffmpeg`, and asserts the rendered image has
color variance. Without `ffmpeg` on `PATH` the test prints `SKIP` and returns.

## Pointers — the first piece of the Superliminal grammar

Layered on top of v0: pointer cells render as **transparent surfaces** that
show the pointed-at cell's live state through their own face, rather than
holding an opaque address. Looking at a pointer is looking at what it points
at; the pointer-kind is encoded as the frame around the view.

### Kind frames

Each pointer cell carries a 2-byte type tag in one of four pointer-kind
slots:

| Kind | Tag      | Halo (outer ring)                            |
|------|----------|----------------------------------------------|
| raw  | `0x000A` | plain provenance hash-color (like a primitive) |
| Box  | `0x000B` | solid white border                            |
| Rc   | `0x000C` | dotted (alternating bright/dim) border         |
| Weak | `0x000D` | half-brightness provenance hash-color          |

The inner 2×2 px of every pointer cell is read from the *target* cell's
inner color — that's the transparent-surface effect. Aliasing (two
pointers to the same target) renders pixel-identical inner regions on the
same frame; the halos differ because the two pointer cells live at
different `file:line` provenance origins.

### Glass corridor (linked_list example)

```bash
cargo run --release --example linked_list
```

Allocates 20 `Tracked<u32>` value cells and 20 `Pointer<u32>` cells linking
them in order; a head pointer lives at cell index 0. The pointer chain
stays static while the loop mutates value cells, so the colors flowing
through the pointers' transparent inner regions visibly drift down the
corridor. The wrap-around edge (`ptr[N-1] -> values[0]`) is also targeted
by `head`, demonstrating aliasing — same inner color, different halos.

### Branching glass (binary_tree example)

```bash
cargo run --release --example binary_tree
```

Allocates 15 nodes in a balanced depth-4 binary tree. Each internal node
holds two `Pointer<u32>` cells (`left`, `right`) targeting its children's
value cells. The loop mutates only the 8 leaf values; each internal node's
two pointers show their respective subtree colors through their faces.

### Cycle handling

Render-time follow is capped at **`POINTER_FOLLOW_CAP = 4` hops**. If a
cycle is detected (visited-set during follow) or a chain exceeds the cap,
the inner region renders the reserved **cycle terminator shade**
(`CYCLE_TERMINATOR_RGB = [70, 60, 90]`), which is deliberately distinct
from every primitive palette entry and from black-free. Cycles render as
bounded glass-tunnels rather than infinite recursion.

### Aliasing legibility note

Aliasing is most visible when the two pointer cells are spatially near
each other in the grid; cells far apart on the 256×256 grid may not read
as "obviously the same color" even when their inner pixels match. The
linked-list example places the head and tail pointers nearby on purpose.

## v0 / v1 boundary

**In v0 (this crate)**:

- 1 MB fixed heap (256×256 grid, 16-byte cells)
- Nine primitive types via deterministic 2-byte tags
- `track!(field, expr)` macro stamps `crc32(file:line)` provenance
- Snapshot thread + `ffmpeg` subprocess
- 2D top-down render (1024×1024 RGBA, 60 fps default)
- Single-mutator-thread mutator + one internal snapshot thread

**In v1-pointers (this crate, additive)**:

- Four pointer-kind tags (raw / Box / Rc / Weak)
- Transparent-surface rendering via target-color resolution
- `POINTER_FOLLOW_CAP = 4` hop ceiling at render time
- Cycle-terminator shade for visited-set / depth-overflow cases
- `examples/linked_list.rs` and `examples/binary_tree.rs`

**Not yet** (sibling specs):

- Refcount enforcement / GC visualization (v2-refcount)
- 3D / LOD / camera navigation (v1-3d)
- Door mode — walking through a pointer (v2-door-mode)
- Substrate (cell lattice / phase trinity) integration
- GPU rendering
- Multi-mutator concurrency

## Configuration

- `MFB_FPS` env var overrides the snapshot rate (default 60).
- `init_framebuffer(path)` chooses the output mp4 (default `framebuffer.mp4`
  if you call it that way; the example passes `"fizzbuzz.mp4"`).
