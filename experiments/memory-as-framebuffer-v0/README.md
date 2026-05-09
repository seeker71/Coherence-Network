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

The renderer **auto-zooms** to the bounding box of currently-allocated
cells (with a small margin and a minimum-side floor), scaling that
viewport to fill the 1024×1024 output frame. So the active heap fills
the screen regardless of how few cells exist or where the allocator
happened to put them. Free cells around the edges render as opaque
black; the lit region is the live heap, large and obvious.

For fizzbuzz: 100 cells active at grid row 0, columns 0..99 → viewport
is `(0, 0, 104)` (104-cell side, 100 cells + 2 margin on each side) →
each cell renders at ~9 px instead of 4 px and the strip fills the
top of the frame instead of being a 4 px sliver.

What's happening in that lit strip:

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
- `MFB_CAPTURE=path.mfb` triggers lossless substrate capture alongside the
  preview mp4. See "Substrate vs preview" below.
- `init_framebuffer(path)` chooses the output mp4 (default `framebuffer.mp4`
  if you call it that way; the example passes `"fizzbuzz.mp4"`).

## Substrate vs preview — the .mfb capture sidecar

The mp4 the snapshot thread produces is a **preview**. h264 + yuv420p chroma
subsampling is lossy, and the renderer itself mixes (tag, payload entropy,
provenance) into a single color per pixel — irreversible. Set
`MFB_CAPTURE=path.mfb` and the snapshot thread *also* writes a lossless
binary capture: every snapshot's raw `(data_plane, provenance_plane)`
recorded with delta encoding (only cells that changed since last frame).

```bash
MFB_CAPTURE=fizzbuzz.mfb cargo run --release --example fizzbuzz
```

Any future renderer (3D, Superliminal, hover-to-inspect HTML, frequency
chart) reads the .mfb and reconstructs the substrate state per frame:

```rust
use mfb::CaptureReader;

for frame in CaptureReader::open("fizzbuzz.mfb")? {
    let frame = frame?;
    // frame.data: 1 MB of (tag, payload) bytes
    // frame.provenance: 65,536 source-location hashes
    // frame.frame_index, frame.timestamp_us: timing
    render_my_view(&frame);
}
```

See [`src/capture.rs`](src/capture.rs) for the binary format. The current
mp4 stays as the gestalt preview; the .mfb is canonical.

## HTML replay viewer (mfb-html)

The first downstream renderer that consumes .mfb. Generates a single
self-contained HTML file (no server, no install — open in any browser)
with playback + hover-to-inspect:

```bash
MFB_CAPTURE=fizzbuzz.mfb cargo run --release --example fizzbuzz
cargo run --release --bin mfb-html -- fizzbuzz.mfb fizzbuzz.html
open fizzbuzz.html  # macOS — or just double-click
```

What you get:

- **Heap as a CSS grid** auto-sized to the active bounding box, with the
  same color palette as the v0 mp4 renderer (so type identity carries over)
- **Cell inspector** on hover: index, grid (x,y), tag name, *decoded
  value* (u32 reads as a number, pointers read as "→ cell N", floats as
  floats, bool as true/false), and provenance hash
- **Timeline scrubber + play/pause** at the foot, plus left/right arrow
  keys for frame-by-frame stepping and space to toggle play
- **Aspect-aware layout**: a 10×10 fizzbuzz heap renders square; a 41×1
  linked-list renders as a horizontal strip

The viewer reconstructs full state from the .mfb's delta-encoded frames —
stepping forward applies deltas, stepping backward replays from the start.
For 6-second captures (~390 frames) the HTML lands ~250–700 KB; opens
instantly. Easily shareable as a single artifact.

### Vitality mode + recipe leaderboard

A header toggle switches the viewer between **Identity** mode (the
default — cells colored by type tag, side panel shows the cell inspector)
and **Vitality** mode (cells colored by total write count, side panel
shows ranked recipes by total cell-writes).

For the recipe leaderboard to label entries with `examples/fizzbuzz.rs:42`
instead of raw hex hashes, the runtime writes a `{capture}.provmap` JSON
sidecar at `shutdown_framebuffer()` that maps every observed provenance
hash back to its `(file, line)`. The mfb-html bin auto-loads it next
to the `.mfb` if present.

Vitality mode is what surfaces *busy areas of the heap* and *which recipe
is most alive in this run*. For fizzbuzz: the shift loop at
`examples/fizzbuzz.rs:42` dominates with ~24,000 writes (visiting each
of 99 history cells per snapshot frame), with the four fizz/buzz/fizzbuzz
branch sites visible at realistic ratios (plain > fizz > buzz > fizzbuzz).
Click any recipe in the list to highlight every cell that recipe writes
to in the current frame.

The cell inspector also shows the resolved source location (`Source:
examples/fizzbuzz.rs:34`) and the cell's lifetime write count, both
read from the same provmap + write-count tables embedded in the HTML.
