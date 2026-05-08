---
idea_id: memory-as-framebuffer
status: draft
source:
  - file: experiments/memory-as-framebuffer-v0/src/scene3d.rs
    symbols: [Scene3D, Camera, build_scene_from_framebuffer]
  - file: experiments/memory-as-framebuffer-v0/src/lod.rs
    symbols: [Lod, LodLevel, scale_factor, transition_at]
  - file: experiments/memory-as-framebuffer-v0/src/navigate.rs
    symbols: [walk, fly, orbit, scale_zoom, frame_selection, follow_through_time]
  - file: experiments/memory-as-framebuffer-v0/src/render3d.rs
    symbols: [render_scene, project_to_2d, software_rasterizer]
  - file: experiments/memory-as-framebuffer-v0/src/preview.rs
    symbols: [PreviewWindow — winit + softbuffer for live interactive playback]
  - file: experiments/memory-as-framebuffer-v0/examples/walk_the_program.rs
    symbols: [interactive demo — walk through a running fizzbuzz at 5 LOD levels]
  - file: experiments/memory-as-framebuffer-v0/tests/lod_scale_factor.rs
    symbols: [test_lod_uses_sqrt10_scale_factor, test_transitions_preserve_identity]
requirements:
  - "Replace the post-process-only mp4 pipeline with a live interactive preview window (winit + softbuffer for portability) that renders the framebuffer state at any of 5 LOD levels (city, district, room, object, texture). The mp4 export remains available as a fixed-camera-path option."
  - "Each cell becomes a 3D object with deterministic position derived from its CellHandle (grid coordinates → 3D world coordinates with √10-scaled spacing). Type tag drives object form: u32 = column, bool = lamp, f32 = fluid pillar, string = banner, struct (when v2 land) = composite card."
  - "The LOD scale-factor between adjacent levels is √10 (per Grant's Codex Universalis identity √10 ≈ (π + 10/π)/2 — the harmonic mean of circular and reciprocal arithmetic). A test asserts the world-coordinate scale ratio between city and district levels equals √10 within 0.01."
  - "Camera modes: walk (WASD + mouse-look, gravity on), fly (gravity off, Q/E vertical), orbit (right-drag pivots around selected object). Shift+scroll triggers semantic LOD-zoom (one click = one level transition, scaled by √10), distinct from regular scroll which is camera-distance dolly."
  - "Frame selection (F key) arcs the camera smoothly to a good viewing angle/distance for the selected cell. Home (H key) returns to the program's main thread + current time + sensible camera distance — the anti-strand guarantee."
  - "Pointer cells (when v1-pointers is also implemented) render as 3D windows: a transparent rectangular face inset into the cell's main shape, with the target cell's mini-rendering shown through it. Frame material encodes pointer kind."
  - "Recording mode: if MFB_RECORD=path is set, the renderer writes a 1024x1024 mp4 of the live scene at 60fps in addition to displaying the preview window. Camera path follows a fixed orbit unless overridden by --camera-path argument."
done_when:
  - "cargo run --release --example walk_the_program opens a window showing the running fizzbuzz program at 3D city scale; pressing 1-5 transitions through LOD levels and the world-coordinate scale changes by √10 per step."
  - "Walking up to a cell (shift+scroll-in or W key) changes LOD smoothly; the same cell remains identifiable across all 5 LOD levels (substrate-hash continuity, even before substrate-render-fabric lands — for v1 just the CellHandle is preserved)."
  - "Pressing H from any LOD/position returns the camera to the canonical home view in <1 second."
  - "tests/lod_scale_factor.rs passes: scale ratios match √10 ± 0.01."
test: "cd experiments/memory-as-framebuffer-v0 && cargo test --release lod"
constraints:
  - "Builds on memory-as-framebuffer-v0 (and v1-pointers if pointer cells are present). Existing 2D mp4 pipeline remains as fallback when no display is available."
  - "Software-rendered (softbuffer + a small custom rasterizer or tiny_skia). No GPU/wgpu in this spec — keeps deps small and ensures it runs headless on CI for the lod-scale-factor test."
  - "Live preview window only on macOS/Linux/Windows desktop. Not on web/wasm in v1."
  - "5 LOD levels are hardcoded in v1; arbitrary-depth zoom is a v2 concern."
  - "VR/headset embodiment is the design target but explicitly NOT in v1 — gesture grammar is mouse+keyboard."
---

# Spec: Memory as Framebuffer — v1 3D + LOD + Navigation

## Purpose

Replace the post-process mp4-only pipeline with a live, walkable 3D scene where each cell is a 3D object you can approach, orbit, and zoom into across 5 semantic LOD levels (city → district → room → object → texture). This is where the Superliminal grammar lives: shift+scroll is *scale-zoom* (a level transition that transmutes the meaning of what you're seeing, not just camera distance), with the scale-factor between levels set to **√10** per Grant's *Codex Universalis* harmonic identity √10 ≈ (π + 10/π)/2 — the harmonic mean of circular and reciprocal arithmetic, which makes it a non-arbitrary anchor for the geometric-arithmetic transition each LOD step performs. Walking through the city is walking through the running program. The mp4 export remains for sharing, but the primary artifact is interactive presence.

## Requirements

- [ ] **R1 — Interactive preview window**: `src/preview.rs` opens a winit window backed by softbuffer. The window receives keyboard + mouse events and re-renders at 60 fps from the current framebuffer state. Closing the window finalizes any active mp4 recording and exits cleanly.

- [ ] **R2 — 3D scene from framebuffer state**: `src/scene3d.rs::build_scene_from_framebuffer()` reads the current cell grid + provenance plane and produces a `Scene3D` of 3D objects: each cell's 2D grid position (gx, gy) maps to world coords (gx × spacing, 0, gy × spacing) where `spacing = current_lod.cell_spacing()`. Object form per type tag: u8/u16/u32/u64/i32/i64 = column (height = log2(value+1)); bool = lamp (lit/dark sphere); f32/f64 = fluid pillar (height = magnitude, color = sign); free slot = empty.

- [ ] **R3 — LOD with √10 scale-factor**: `src/lod.rs::LodLevel` has 5 variants (`City`, `District`, `Room`, `Object`, `Texture`). `scale_factor()` between adjacent levels = √10 ≈ 3.16228. A transition City→District means cell_spacing shrinks by √10 and individual objects appear ~√10× larger relative to view. Test `tests/lod_scale_factor.rs::test_lod_uses_sqrt10_scale_factor` asserts the ratio of cell_spacing(City) / cell_spacing(District) equals √10 within 0.01.

- [ ] **R4 — Camera modes**: walk (default — WASD + mouse-look, gravity-snapped to a ground plane at y=0), fly (G key toggles — Q/E for vertical, full 6DOF), orbit (right-drag — pivots the camera around the currently-selected cell at constant radius). Walking speed is 1 unit/sec; flying caps at 20 units/sec.

- [ ] **R5 — Scale-zoom (shift+scroll)**: each shift+scroll click transitions the camera one LOD level (in or out). The transition is a 0.4-second smooth interpolation: camera position scales by √10 toward/away from the selection point; the selected cell stays roughly centered. Plain scroll (no shift) is camera-distance dolly without LOD change.

- [ ] **R6 — Frame selection (F) and home (H)**: `F` arcs the camera over 0.6s to a good viewing angle and distance for the selected cell (45° azimuth, 30° elevation, distance = 4× cell_size at current LOD). `H` returns to canonical home: city LOD, fizzbuzz program's allocation cluster centered, camera at (50, 30, 50) looking at origin. Both are interruptible by any other input.

- [ ] **R7 — Pointer cells as 3D windows** (when v1-pointers is also live): a pointer cell renders as the cell's primary shape with one face replaced by a small 3D window — a recessed rectangular hole into which the target cell's mini-rendering is composited. Pointer kind drives the frame material. If v1-pointers is not implemented, this requirement is no-op.

- [ ] **R8 — mp4 recording**: setting `MFB_RECORD=path.mp4` runs a parallel ffmpeg pipeline that captures the rendered scene at 1024×1024 / 60 fps from a fixed orbit camera path (or `--camera-path file.toml` for custom paths). Live preview continues; mp4 is finalized on window close.

## Files to Create/Modify

- `experiments/memory-as-framebuffer-v0/src/scene3d.rs`
- `experiments/memory-as-framebuffer-v0/src/lod.rs`
- `experiments/memory-as-framebuffer-v0/src/navigate.rs`
- `experiments/memory-as-framebuffer-v0/src/render3d.rs`
- `experiments/memory-as-framebuffer-v0/src/preview.rs`
- `experiments/memory-as-framebuffer-v0/src/lib.rs` — re-exports
- `experiments/memory-as-framebuffer-v0/Cargo.toml` — add winit, softbuffer, glam (or nalgebra), tiny_skia (or similar) dependencies
- `experiments/memory-as-framebuffer-v0/examples/walk_the_program.rs`
- `experiments/memory-as-framebuffer-v0/tests/lod_scale_factor.rs`
- `experiments/memory-as-framebuffer-v0/README.md` — add navigation guide and √10 LOD note

## Acceptance Tests

- `cd experiments/memory-as-framebuffer-v0 && cargo test --release lod` passes — scale-factor tests headless.
- Manual validation: `cargo run --release --example walk_the_program` opens a window showing fizzbuzz live; pressing 1-5 cycles LOD; walk/fly/orbit work; F frames selection; H returns home.
- Optional manual: `MFB_RECORD=walk.mp4 cargo run --release --example walk_the_program`, exit window, confirm `walk.mp4` is watchable.

## Verification

```bash
cd experiments/memory-as-framebuffer-v0
cargo build --release
cargo test --release lod
# Headed validation (requires display):
cargo run --release --example walk_the_program
# Headless recording validation:
MFB_RECORD=walk.mp4 timeout 10 cargo run --release --example walk_the_program || true
ls -la walk.mp4 && ffprobe -v error -show_entries stream=codec_name,r_frame_rate walk.mp4
```

## Out of Scope

- VR/headset embodiment — gesture grammar is designed for it but v1 ships mouse+keyboard only.
- GPU rendering / wgpu — keep deps small; software rasterizer is sufficient at 1024×1024.
- Substrate integration — cells render from CellHandle continuity; substrate-hash continuity lands in `substrate-render-fabric-v0`.
- Custom Render trait per type — `memory-as-framebuffer-v1-render-trait` is parallel; v1-3d uses the hardcoded primitives.
- Time-axis scrubbing UI (scrub bar, bookmarks, follow-through-time) — `memory-as-framebuffer-v2-time-axis`.
- Multi-camera split-screen — `memory-as-framebuffer-v2-multi-camera`.

## Risks and Assumptions

- **Software rasterizer at 60 fps for 1024×1024 + 65k cells** — at city LOD many cells are sub-pixel and culled cheap; at object LOD only ~50 cells visible; mid-LOD is the worst case. Document target perf; if too slow, mp4-only fallback at lower fps.
- **winit + softbuffer cross-platform window setup** — well-supported on macOS/Linux/Windows; document if any platform needs special init.
- **√10 scale-factor producing sensible visual transitions** — needs visual tuning; the math is fixed but the camera animation curve and FOV interaction may need adjustment to feel like "transmutation" rather than "jump cut."
- **CI doesn't have a display** — the headless test (`tests/lod_scale_factor.rs`) only validates the math, not the rendering. Headed validation is manual on the developer's machine.
- **Selected-cell tracking across LOD transitions** — selection must persist across LOD changes. Use CellHandle as the persistent identity (substrate-hash will replace this in `substrate-render-fabric-v0`).

## Known Gaps and Follow-up Tasks

- Follow-up: `memory-as-framebuffer-v2-time-axis` — scrub bar, bookmarks, follow-cell-through-time.
- Follow-up: `memory-as-framebuffer-v2-multi-camera` — split-screen, picture-in-picture, thread-camera attach.
- Follow-up: `memory-as-framebuffer-v2-vr` — embodied gesture grammar (reach + pinch + walk) replacing mouse+keyboard.
- Follow-up: `memory-as-framebuffer-v2-gpu` — wgpu backend for higher resolution and richer effects (real alpha compositing, post-process glow, etc).
- Follow-up: tune the LOD scale-factor curve so transitions feel harmonic rather than jarring (this is where √10 actually has to *land in the body*, not just in the math test).
