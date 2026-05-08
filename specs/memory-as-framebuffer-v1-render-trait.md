---
idea_id: memory-as-framebuffer
status: draft
source:
  - file: experiments/memory-as-framebuffer-v0/src/render_trait.rs
    symbols: [Render, RenderCtx, RenderOp, register_kernel, lookup_kernel]
  - file: experiments/memory-as-framebuffer-v0/src/render.rs
    symbols: [render_frame — extended to dispatch through Render trait]
  - file: experiments/memory-as-framebuffer-v0/examples/custom_renderer.rs
    symbols: [Matrix3x3 type with custom Render impl showing grid of cells]
  - file: experiments/memory-as-framebuffer-v0/tests/render_trait_smoke.rs
    symbols: [test_default_render_matches_v0, test_custom_render_overrides, test_kernel_registry]
requirements:
  - "Define a `Render` trait with `fn render(&self, ctx: &mut RenderCtx, lod: Lod)` where RenderOp captures intent (rect, color, halo, transparency, etc.) abstracted from the actual frame buffer. Default impl reads the cell's type tag and produces v0-equivalent output (palette color + brightness + halo)."
  - "User-defined types implement Render to override default behavior. A registry (HashMap<u16, Box<dyn Render>>) maps a 16-bit user-type-tag (range 0x1000..0xFFFF, reserved away from primitive tags 0x0001..0x000F and pointer tags 0x000A..0x000D) to its render impl."
  - "register_kernel(tag, impl) is called at program startup; the rendering pipeline dispatches based on the cell's type tag — if it's a registered user-tag, call its custom render; otherwise fall back to the default primitive renderer."
  - "Example: examples/custom_renderer.rs defines a Matrix3x3 type backed by 9 Tracked<f32> cells with a custom Render impl that renders the matrix as a 3x3 visible grid (each entry as a small colored square within the matrix's allocated region) plus a labelled border."
  - "The default rendering for v0 primitives MUST match v0's output exactly (the default Render impl is a refactor, not a behavior change). Smoke test asserts pixel-equivalence for a fizzbuzz-equivalent run."
  - "Render trait works at all 5 LOD levels (when v1-3d is also live) — the lod parameter lets implementations cheap-out at distance and bloom into detail up close."
done_when:
  - "cargo run --release --example custom_renderer produces matrix3x3.mp4 where the matrix renders as a 3x3 visible grid rather than as 9 separate primitive cells."
  - "tests/render_trait_smoke.rs passes: default-render-matches-v0 (pixel equivalence within tolerance), custom-render-overrides (registered kernel beats default), kernel-registry (registering twice errors, lookup hits return Some)."
  - "v0 fizzbuzz example continues to produce identical mp4 output after refactoring through the Render trait dispatch."
test: "cd experiments/memory-as-framebuffer-v0 && cargo test --release render_trait"
constraints:
  - "Builds on memory-as-framebuffer-v0. The v0 fizzbuzz mp4 must remain pixel-equivalent (within H.264 tolerance) after refactor; this is a structural change, not a visual one."
  - "User-type-tag range 0x1000..0xFFFF reserved for custom kernels. Primitives 0x0001..0x000F. Pointer kinds 0x000A..0x000D. Substrate-hash-tags (when substrate-render-fabric-v0 lands) take a separate range."
  - "Trait objects (Box<dyn Render>) — slight indirection cost per cell at render time. Acceptable; document for the perf-sensitive."
  - "Registry is global, behind a Mutex (or RwLock). Registration happens at program startup before init_framebuffer; mid-run registration is undefined behavior in v1."
  - "RenderOp is intentionally LOD-aware but not 3D-aware in v1. v1-3d's scene-builder consumes RenderOps and projects to 3D; v1-render-trait stays renderer-agnostic."
---

# Spec: Memory as Framebuffer — v1 Render Trait

## Purpose

Replace the hardcoded nine-primitive renderer with a `Render` trait that any user-defined type can implement to override how its cells appear on screen. Library authors get a way to make their types beautiful from across the city. The default impl preserves v0 behavior exactly (palette color + brightness + halo), so this is structurally a refactor with an extension point — not a visual change to existing programs. The example is a `Matrix3x3` type that implements Render to draw itself as a labeled 3×3 grid rather than as nine disconnected float cells, demonstrating that the same underlying tracked storage can render as either "raw cells" or "the type the storage represents." Once Render is in place, every subsequent visualization improvement (custom struct silhouettes, bespoke renders for AST/Tree/Color/Image/Quaternion) is just an impl, not an engine change.

## Requirements

- [ ] **R1 — Render trait definition**: `src/render_trait.rs` defines `pub trait Render: Send + Sync { fn render(&self, ctx: &mut RenderCtx, lod: Lod); }`. `RenderCtx` exposes: cell position (grid coords), current LOD, write buffer (RGBA), helper methods (`fill_rect`, `draw_halo`, `composite_target_color` for pointer-style transparency). `Lod` is an enum imported from `lod.rs` (or a placeholder if v1-3d isn't yet live: in that case Lod has only one variant `Default`).

- [ ] **R2 — Default impl for primitives**: a `DefaultPrimitiveRender(u16)` struct implementing Render that takes the type tag and produces v0-equivalent output (palette base color + payload-derived brightness + provenance halo). The renderer dispatches every cell through this default unless a user kernel is registered.

- [ ] **R3 — Kernel registry**: `pub fn register_kernel(tag: u16, kernel: Box<dyn Render>)` adds an entry. Tag must be in 0x1000..=0xFFFF; lower ranges return `Err(ReservedTag)`. Re-registering an existing tag returns `Err(AlreadyRegistered)`. `pub fn lookup_kernel(tag: u16) -> Option<&'static dyn Render>` for the renderer dispatch.

- [ ] **R4 — Renderer dispatch**: extend `src/render.rs::render_frame()` so for each cell with type tag `t`: if `lookup_kernel(t)` is Some, call its `render()`; else call `DefaultPrimitiveRender(t).render()`. Pointer-kind tags (0x000A..0x000D) continue to use the v1-pointers transparent-surface render.

- [ ] **R5 — Matrix3x3 example**: `examples/custom_renderer.rs` defines `struct Matrix3x3 { entries: [Tracked<f32>; 9] }` and registers a `Matrix3x3Render` kernel under user-tag 0x1001. The Render impl draws the matrix as a 3×3 visible grid: each entry is a small colored square (sign → hue, magnitude → brightness), with a labeled border around the whole matrix. Demo program runs a small linear-algebra loop (matrix multiplication or SVD step) for n=1..=10000 producing `matrix3x3.mp4`.

- [ ] **R6 — v0 pixel equivalence**: smoke test `tests/render_trait_smoke.rs::test_default_render_matches_v0` runs the v0 fizzbuzz example before and after the refactor (using a snapshot of v0 output) and asserts decoded first-frame pixel equivalence within ±2 RGB tolerance.

- [ ] **R7 — README extension**: extend the README with a "Custom kernels" section showing how to implement Render and register a kernel, with the Matrix3x3 example as a worked walkthrough.

## Files to Create/Modify

- `experiments/memory-as-framebuffer-v0/src/render_trait.rs`
- `experiments/memory-as-framebuffer-v0/src/render.rs` — refactor to dispatch through Render trait
- `experiments/memory-as-framebuffer-v0/src/lib.rs` — re-exports
- `experiments/memory-as-framebuffer-v0/examples/custom_renderer.rs`
- `experiments/memory-as-framebuffer-v0/tests/render_trait_smoke.rs`
- `experiments/memory-as-framebuffer-v0/tests/v0_fizzbuzz_snapshot.png` — committed reference frame for pixel-equivalence test
- `experiments/memory-as-framebuffer-v0/README.md` — add Custom Kernels section

## Acceptance Tests

- `cd experiments/memory-as-framebuffer-v0 && cargo test --release render_trait` passes — default-equivalence, custom-override, registry behavior.
- Manual validation: `cargo run --release --example custom_renderer` produces `matrix3x3.mp4` where the matrix is visibly a 3×3 grid, not nine separate primitive cells.
- Manual validation: `cargo run --release --example fizzbuzz` (v0 example) produces output visually identical to pre-refactor.

## Verification

```bash
cd experiments/memory-as-framebuffer-v0
cargo build --release
cargo test --release render_trait
cargo run --release --example fizzbuzz
cargo run --release --example custom_renderer
ls -la matrix3x3.mp4 fizzbuzz.mp4
ffprobe -v error -show_entries stream=codec_name,nb_frames matrix3x3.mp4
```

## Out of Scope

- Hot-reload of registered kernels mid-run — registration is startup-only in v1.
- Cross-language kernel registration (substrate-Recipe-keyed kernels) — `substrate-render-fabric-v0`.
- Render kernels that span multiple cells via pointer relationships (e.g. a Tree kernel that follows children) — that needs v1-pointers and the Render trait's RenderCtx extended to allow pointer-following; tracked as a follow-up.
- 3D-aware RenderOp (volumetric shapes, normals) — v1-3d builds on the 2D RenderOp; volumetric is a v2 concern.
- Animation hooks (a kernel that animates between frames based on value-deltas) — v2.

## Risks and Assumptions

- **Trait-object dispatch cost** — one indirect call per cell per frame. At 256×256 = 65k cells × 60 fps = 3.9M dispatches/sec. Modern CPUs handle this trivially; document.
- **Pixel-equivalence tolerance** — H.264 + YUV420p subsampling can shift colors by a few units; ±2 tolerance is empirical. If the test flakes, widen tolerance with documented justification rather than tightening it past the codec's reach.
- **Registry locking contention** — render thread reads, mutator never writes after init. Use `OnceCell<HashMap>` or `Lazy<RwLock<HashMap>>` to make the read path lock-free post-init.
- **User-tag range collisions across libraries** — two libraries claiming the same tag will conflict. v1 documents the convention (libraries should use a hash of their crate name modulo the user range); v2 may add a substrate-hash-keyed registry.

## Known Gaps and Follow-up Tasks

- Follow-up: composite kernels that follow pointer relationships (a `Tree<T>` kernel that walks children to render the whole tree) — depends on v1-pointers' RenderCtx extensions.
- Follow-up: substrate-Recipe-keyed kernels (cross-language type identity) — `substrate-render-fabric-v0`.
- Follow-up: animation hooks for between-frame interpolation — `memory-as-framebuffer-v2-animation`.
- Follow-up: 3D-aware RenderOp for v1-3d — currently RenderOp is 2D; v1-3d's scene builder projects RenderOps into 3D, but volumetric kernels need a richer op vocabulary.
- Follow-up: kernel hot-reload for live development — likely requires dynamic libraries (cdylib) and is a v2 concern.
