---
idea_id: memory-as-framebuffer
status: draft
source:
  - file: experiments/memory-as-framebuffer-v0/Cargo.toml
    symbols: [crate manifest with image, crc32fast deps]
  - file: experiments/memory-as-framebuffer-v0/src/lib.rs
    symbols: [Tracked, track!, init_framebuffer, Framebuffer]
  - file: experiments/memory-as-framebuffer-v0/src/allocator.rs
    symbols: [SlabFramebuffer, Cell, CellHandle, alloc_cell, free_cell]
  - file: experiments/memory-as-framebuffer-v0/src/snapshot.rs
    symbols: [SnapshotThread, capture_frame, FrameRgba]
  - file: experiments/memory-as-framebuffer-v0/src/render.rs
    symbols: [render_frame, type_palette, modulate_brightness, provenance_halo]
  - file: experiments/memory-as-framebuffer-v0/src/ffmpeg.rs
    symbols: [FfmpegPipe, spawn, write_frame, finalize]
  - file: experiments/memory-as-framebuffer-v0/examples/fizzbuzz.rs
    symbols: [fizzbuzz demo with 100 tracked u32 cells]
  - file: experiments/memory-as-framebuffer-v0/tests/smoke.rs
    symbols: [test_fizzbuzz_produces_nonempty_mp4, test_two_distinct_pixel_colors]
  - file: experiments/memory-as-framebuffer-v0/README.md
    symbols: [run instructions, expected visuals, v0/v1 boundary]
requirements:
  - "Slab allocator lays out tracked values on a fixed 256x256 cell grid (16 bytes each = 1MB heap). Each cell stores a 2-byte type tag + 14 bytes payload."
  - "Tracked<T> wrapper for u8/u16/u32/u64/i32/i64/bool/f32/f64 records every write into a parallel u32 provenance plane via a track! macro that captures hash(file!() + line!()) at each call site."
  - "A snapshot thread reads both planes every 1000/FPS ms (default FPS = 60, configurable via MFB_FPS env var) and produces RGBA frames where type tag picks a palette color, payload modulates brightness, and provenance hash colors a 1-pixel halo."
  - "Frames are piped to a child ffmpeg process producing an H.264 mp4 at the same FPS; on Framebuffer drop, stdin closes and the child is awaited cleanly."
  - "An example program (fizzbuzz over n=1..=10000 with 100 Tracked<u32> cells) runs to completion and produces a non-empty mp4 in under 30 seconds of wall time."
  - "Smoke test asserts the mp4 exists with non-zero size, decodes its first frame, and verifies at least two pixels have distinct RGB values (proving type-tagging renders)."
  - "README documents prerequisites (Rust 1.75+, ffmpeg on PATH), run command, expected visuals, and the explicit v0/v1 boundary (no pointers/3D/LOD/substrate in v0)."
done_when:
  - "cargo run --release --example fizzbuzz produces fizzbuzz.mp4 in the crate dir, watchable in any video player."
  - "The watched mp4 visibly shows distinct colored regions for the 100 cells, brightness modulation as values change through the loop, and provenance halos shifting between fizz/buzz/fizzbuzz code paths."
  - "cargo test --release passes the smoke test."
  - "If ffmpeg is not on PATH, the smoke test skips with an actionable error rather than failing."
test: "cd experiments/memory-as-framebuffer-v0 && cargo test --release"
constraints:
  - "Single language (Rust). No FFI to C/C++ besides the ffmpeg subprocess. No GPU integration in v0 — software-rendered RGBA frames only."
  - "No substrate integration in v0. The provenance plane uses a u32 hash of file:line; substrate-cell linkage is a sibling spec."
  - "No pointer-window rendering, no 3D, no LOD, no camera navigation. v0 is a 2D top-down view only."
  - "Heap size fixed at 1MB (256x256x16 bytes). Out-of-space allocations panic with a clear message. Realloc/grow is a v1 concern."
  - "Single-threaded mutator only. Cross-thread tracking is a v1 concern."
---

# Spec: Memory as Framebuffer — v0

## Purpose

The smallest concrete proof that a program's runtime can be recorded as a video by treating its heap as a graphics framebuffer. A Rust crate provides a slab allocator that lays out tracked values on a fixed 2D grid, a parallel provenance plane that records source-location hashes per write, and a snapshot thread that captures both planes as RGBA frames piped to ffmpeg. The demo: a small fizzbuzz program runs and produces an mp4 you can open in any video player to watch the heap breathe — distinct colored regions for distinct types, brightness modulating as values change, provenance halos shifting when different code sites write. No instrumentation overhead on the program itself beyond a thin wrapper macro; no GPU; no pointer-windows yet; no 3D yet; no substrate integration yet. The point is to demonstrate that "memory as framebuffer" is a buildable artifact, not a thought experiment, and to produce a watchable video that grounds the larger vision in something you can hand to someone and say "look."

## Requirements

- [ ] **R1 — Slab framebuffer**: `experiments/memory-as-framebuffer-v0/src/allocator.rs` provides a `SlabFramebuffer` with a fixed 256×256 grid of 16-byte cells (1 MB total). Each cell: 2 bytes type tag + 14 bytes payload. `alloc_cell()` returns a `CellHandle`; `free_cell(handle)` zeros the cell and frees the slot. Out-of-space allocations panic with a clear message. Allocation order is deterministic (next-free-slot scan from index 0) so cell positions are stable across runs.

- [ ] **R2 — Tracked<T> + track! macro**: `src/lib.rs` exposes `Tracked<T>` for the primitive types u8, u16, u32, u64, i32, i64, bool, f32, f64. Constructing a `Tracked<T>` allocates a cell, writes the type tag (one of nine deterministic 2-byte values), and stores the initial payload. The `track!(value, expr)` macro wraps every write so it (a) updates the cell's payload bytes and (b) writes `crc32(file!() + line!())` into the parallel provenance plane (`Vec<u32>` of length 256×256).

- [ ] **R3 — Snapshot thread**: `src/snapshot.rs` spawns a thread on `init_framebuffer()` that reads both planes every `1000/FPS` ms (default FPS = 60, override via `MFB_FPS` env var). Each captured frame is a `Vec<[u8;4]>` of length 256×256 (RGBA). Type tag → base color via a deterministic 9-entry palette plus a reserved "free slot" color. Payload bytes → brightness/saturation modulation (high entropy → bright; zero → dim). Provenance hash → a 1-pixel halo color around each cell rendered at sub-cell resolution (each cell renders as a 4×4 block with the inner 2×2 as the value and the outer ring as the halo).

- [ ] **R4 — ffmpeg pipeline**: `src/ffmpeg.rs` spawns `ffmpeg -f rawvideo -pix_fmt rgba -s 1024x1024 -r {FPS} -i - -c:v libx264 -pix_fmt yuv420p -y {OUTPUT}` as a child process (1024 = 256 cells × 4 px each). The snapshot thread writes RGBA frames to its stdin. On `Framebuffer::drop`, stdin closes and the child is awaited; non-zero exit logs the ffmpeg stderr and returns a clear error. If ffmpeg is not on PATH, init returns an error with installation guidance.

- [ ] **R5 — fizzbuzz example**: `examples/fizzbuzz.rs` initializes the framebuffer, allocates 100 `Tracked<u32>` cells, and runs a fizzbuzz loop for n=1..=10000 with cell[0] holding the current `i`, cells 1–99 holding a rolling history of recent fizz/buzz/fizzbuzz tags (encoded as 0/1/2/3). The loop yields after each iteration so the snapshot thread captures meaningful change. On completion the framebuffer is dropped (finalizing the mp4) and the program exits.

- [ ] **R6 — Smoke test**: `tests/smoke.rs` runs the fizzbuzz example as a subprocess via `cargo run --example fizzbuzz`, asserts `fizzbuzz.mp4` exists with non-zero size, uses `ffmpeg -i fizzbuzz.mp4 -vframes 1 frame.png` to dump the first frame, decodes it with the `image` crate, and asserts at least two pixels have distinct RGB values. If `ffmpeg` is not on PATH, the test prints a clear skip message and returns Ok(()).

- [ ] **R7 — README**: `experiments/memory-as-framebuffer-v0/README.md` documents: prerequisites (Rust 1.75+, ffmpeg on PATH), how to run (`cargo run --release --example fizzbuzz`), what to expect visually (cell 0 pulses through brightness as the loop counter increments; cells 1–99 shift hue based on the recent fizz/buzz/fizzbuzz tag history; halos change between the three code paths because each writes from a different `file!:line!`), and the v0/v1 boundary (no pointers, no 3D, no LOD, no substrate yet — those are sibling specs).

## Files to Create/Modify

- `experiments/memory-as-framebuffer-v0/Cargo.toml`
- `experiments/memory-as-framebuffer-v0/src/lib.rs`
- `experiments/memory-as-framebuffer-v0/src/allocator.rs`
- `experiments/memory-as-framebuffer-v0/src/snapshot.rs`
- `experiments/memory-as-framebuffer-v0/src/render.rs`
- `experiments/memory-as-framebuffer-v0/src/ffmpeg.rs`
- `experiments/memory-as-framebuffer-v0/examples/fizzbuzz.rs`
- `experiments/memory-as-framebuffer-v0/tests/smoke.rs`
- `experiments/memory-as-framebuffer-v0/README.md`

Also update `MANIFEST.md` to add a one-line pointer to the experiments directory and `ideas/memory-as-framebuffer-v0` cross-reference if the idea graduates from raw to curated.

## Acceptance Tests

- `cd experiments/memory-as-framebuffer-v0 && cargo test --release` passes — the smoke test in `tests/smoke.rs` validates mp4 existence, non-zero size, decodable first frame, and pixel-color distinctness.
- Manual validation: `cargo run --release --example fizzbuzz` produces `fizzbuzz.mp4`. Opening it in any video player visibly shows the heap breathing — counter cell pulses, history cells shift, halos change between fizz/buzz/fizzbuzz paths.

## Verification

```bash
cd experiments/memory-as-framebuffer-v0
cargo build --release
cargo test --release
cargo run --release --example fizzbuzz
ls -la fizzbuzz.mp4
ffprobe -v error -show_entries stream=codec_name,r_frame_rate,nb_frames fizzbuzz.mp4
```

Expect: build clean, tests pass, mp4 written (>10 KB), ffprobe reports `h264` codec at 60 fps with > 100 frames.

## Out of Scope

- Pointer-window / Superliminal portal rendering — sibling spec: `memory-as-framebuffer-v1-pointers`.
- 3D rendering, LOD scale-zoom, camera navigation — sibling spec: `memory-as-framebuffer-v1-3d`.
- Substrate integration (provenance plane → substrate cell hash; render kernel as Recipe) — sibling spec: `substrate-render-fabric-v0`.
- GPU-resident framebuffer with live preview window. v0 produces post-process mp4 only.
- Custom per-type render kernels via a `Render` trait. v0 has nine hardcoded primitives.
- Multi-threaded program tracking. v0 assumes a single mutator thread.
- Realloc, heap growth, GC awareness, refcount visualization. v0 has fixed 1 MB.
- Source-location hash → AST / function / module resolver. v0 stores `crc32(file:line)` but does not resolve back.
- Harmonic constants in the layout (√10 LOD scale-factor, harmonic-mean cell sizing per Grant's Codex Universalis). Those land naturally at the LOD spec, not v0.

## Risks and Assumptions

- **ffmpeg on PATH** — assumed; smoke test skips cleanly with an actionable error if missing; README documents the install step.
- **Snapshot thread timing** — at 60 FPS we capture ~16 ms of writes per frame. Sub-frame writes blur correctly (the visual idiom matches the semantic idiom: hot cells shimmer, cold cells sit still), but bursty hot loops may aliasing-flicker. README documents expected behavior.
- **Hash collisions in provenance** — `crc32(file:line)` has ~1-in-4-billion collision risk; acceptable for the v0 demo. v1 needs a wider hash, tracked as a follow-up.
- **Cell layout determinism** — required for comparable rendered frames across runs. Insertion-order placement is sufficient; documented in `allocator.rs`.
- **Color palette accessibility** — nine hardcoded colors may not meet contrast targets for colorblind viewers. Palette tuning is a follow-up; v0 prioritizes legibility on black background.
- **Mutex contention on the framebuffer** — tracked writes take a brief lock. For a fizzbuzz loop the cost is negligible, but the README documents that v0 is not zero-overhead in microbenchmarks (the runtime cost lives in the writer-side macro, not in instrumentation infrastructure).

## Known Gaps and Follow-up Tasks

- Follow-up task: `memory-as-framebuffer-v1-render-trait` — custom `Render` trait per type, replacing the hardcoded nine primitives.
- Follow-up task: `memory-as-framebuffer-v1-pointers` — pointer-window rendering with transparent surfaces showing pointed-at cells live.
- Follow-up task: `substrate-render-fabric-v0` — link the provenance plane to substrate cells; allow render kernels to be substrate Recipes.
- Follow-up task: `memory-as-framebuffer-v1-3d` — 3D rendering, semantic LOD-zoom, camera navigation; the harmonic scale-factor (√10 candidate per Grant's Codex Universalis) lands here.
- Follow-up task: `memory-as-framebuffer-v1-live` — GPU-resident framebuffer with real-time preview window, replacing the post-process-only v0 pipeline.
- Follow-up task: wider provenance hash (64-bit or content-addressed) replacing `crc32` to eliminate practical collision risk.
