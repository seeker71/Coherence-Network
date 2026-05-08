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

- **Cell 0** (top-left, single 4×4 px block): the current `i` (1..=10000).
  Its inner color is the `u32` palette entry; brightness pulses with the
  payload's nonzero-byte count.
- **Cells 1..99** (the rest of the top row): the rolling fizz/buzz history.
  As the loop runs, tag values shift down the strip: `1=plain`, `2=fizz`,
  `3=buzz`, `4=fizzbuzz`. Inner color is the same palette entry (all `u32`),
  but brightness varies with the value.
- **Halos** (outer ring of every 4×4 block): the provenance hash. The four
  branches of the fizzbuzz `match` (`write_plain`, `write_fizz`, `write_buzz`,
  `write_fizzbuzz`) each live at a distinct `file:line`, so each branch's
  halo color is distinct. You should see the strip's halos shimmer between
  four colors as the loop progresses.

## Tests

```bash
cargo test --release
```

The smoke test runs the example as a subprocess, validates the mp4 exists,
extracts the first frame with `ffmpeg`, and asserts the rendered image has
color variance. Without `ffmpeg` on `PATH` the test prints `SKIP` and returns.

## v0 / v1 boundary

**In v0 (this crate)**:

- 1 MB fixed heap (256×256 grid, 16-byte cells)
- Nine primitive types via deterministic 2-byte tags
- `track!(field, expr)` macro stamps `crc32(file:line)` provenance
- Snapshot thread + `ffmpeg` subprocess
- 2D top-down render (1024×1024 RGBA, 60 fps default)
- Single-mutator-thread mutator + one internal snapshot thread

**Not in v0** (sibling specs):

- Pointer-window rendering
- 3D / LOD / camera navigation
- Substrate (cell lattice / phase trinity) integration
- GPU rendering
- Multi-mutator concurrency

## Configuration

- `MFB_FPS` env var overrides the snapshot rate (default 60).
- `init_framebuffer(path)` chooses the output mp4 (default `framebuffer.mp4`
  if you call it that way; the example passes `"fizzbuzz.mp4"`).
