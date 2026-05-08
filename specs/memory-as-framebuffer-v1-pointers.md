---
idea_id: memory-as-framebuffer
status: draft
source:
  - file: experiments/memory-as-framebuffer-v0/src/pointer.rs
    symbols: [Pointer, BoxPtr, RcPtr, WeakPtr, PointerKind, render_pointer_cell]
  - file: experiments/memory-as-framebuffer-v0/src/render.rs
    symbols: [render_frame — extended for transparent surface composition]
  - file: experiments/memory-as-framebuffer-v0/src/allocator.rs
    symbols: [SlabFramebuffer — extended type tags for pointer kinds]
  - file: experiments/memory-as-framebuffer-v0/examples/linked_list.rs
    symbols: [singly-linked list of 20 nodes demonstrating glass-corridor effect]
  - file: experiments/memory-as-framebuffer-v0/examples/binary_tree.rs
    symbols: [balanced 15-node binary tree demonstrating branching glass]
  - file: experiments/memory-as-framebuffer-v0/tests/pointer_smoke.rs
    symbols: [test_pointer_renders_target_color, test_aliasing_visible, test_cycle_bounded]
requirements:
  - "Add Pointer<T> wrapper that allocates a pointer cell containing the target's CellHandle index (u16) plus a pointer-kind tag (raw, Box, Rc, Weak — one byte each, 4 reserved)."
  - "Render a pointer cell as a transparent surface: the inner 2x2 px area shows the target cell's current rendered color/brightness rather than the pointer's own value. The outer ring (halo) encodes pointer-kind: raw=plain, Box=solid white frame, Rc=dotted frame, Weak=translucent frame."
  - "Aliasing test: two pointers pointing at the same target render visually identical inner regions on the same frame. The smoke test asserts pixel-equality of the inner 2x2 across both pointer cells."
  - "Cycle handling: when rendering, follow the pointer chain at most 4 hops. A cycle therefore renders as a bounded glass-tunnel rather than infinite recursion. Test asserts a 3-cycle (A→B→C→A) renders without panic and the inner color shows depth-4 termination color (a reserved 'cycle terminator' shade)."
  - "Two example programs: examples/linked_list.rs (20-node singly-linked list, head pointer + each node holds a Pointer to next) and examples/binary_tree.rs (15-node balanced tree, each node holds two Pointers). Both produce watchable mp4s where the glass-corridor / branching-glass effect is visible."
done_when:
  - "cargo run --release --example linked_list produces linked_list.mp4 where pointer cells visibly show the next node's color through their glass face."
  - "cargo run --release --example binary_tree produces binary_tree.mp4 where each node's two pointer cells show distinct subtree colors."
  - "tests/pointer_smoke.rs passes: target-color rendering, aliasing equality, cycle bounded."
  - "An aliasing demo: two pointers to the same target are visually indistinguishable in their inner regions and visually distinct in their halos (because they live at different file:line locations and so have different provenance halos)."
test: "cd experiments/memory-as-framebuffer-v0 && cargo test --release pointer"
constraints:
  - "Builds on memory-as-framebuffer-v0. Does not break v0 examples."
  - "No 3D in this spec. Pointer rendering stays within the 2D framebuffer (transparency = inner-region color substitution, not actual alpha compositing)."
  - "Maximum follow-depth of 4 hops at render time. Documented; deeper chains render as glass-tunnels truncated at depth 4."
  - "Single-threaded mutator only. Cross-thread pointer mutation is a v2 concern."
  - "No GC, no refcount enforcement at runtime — Rc pointer-kind is purely visual; the cell stays allocated until the program drops the Pointer. v2 may add refcount visualization."
---

# Spec: Memory as Framebuffer — v1 Pointers

## Purpose

Extend the v0 framebuffer with pointer-window rendering — the Superliminal-inspired idiom where a pointer cell shows the pointed-at cell's live state through its own face, rather than holding an opaque address. Transparency *is* indirection: looking at a pointer is looking at what it points at, with the pointer-kind encoded as the frame around the view. This makes aliasing (multiple pointers to the same target render the same inner color), chained indirection (linked-list nodes form a glass corridor), and cycles (bounded glass-tunnel that terminates at depth 4) directly visible. The two example programs — a 20-node linked list and a 15-node balanced binary tree — produce watchable mp4s where the structural topology of the data is visible as the optical phenomenon it actually is. The v0 was "memory is video"; this v1 adds the first piece of the Superliminal grammar.

## Requirements

- [ ] **R1 — Pointer<T> wrapper**: `src/pointer.rs` exposes `Pointer<T>`, `BoxPtr<T>`, `RcPtr<T>`, `WeakPtr<T>` (the last three are visual variants — same data layout, different kind tag). Each pointer cell stores: 2-byte type tag (one of four pointer-kind tags 0x000A..0x000D), 2-byte target CellHandle, 12 bytes reserved.

- [ ] **R2 — Transparent-surface rendering**: extend `src/render.rs::render_frame()` so when a cell's type tag is in the pointer range, the inner 2×2 px of its 4×4 block shows the *target cell's rendered inner 2×2* rather than the pointer's own payload. The outer ring (halo) is rendered from a kind-specific frame palette: raw = plain hash-color, Box = solid white border, Rc = dotted (alternating bright/dim pixels), Weak = half-brightness.

- [ ] **R3 — Aliasing visible**: two pointers pointing at the same target render visually identical inner 2×2 regions in any given frame. Smoke test asserts pixel equality across the two pointer cells' inner regions for at least 100 consecutive frames.

- [ ] **R4 — Cycle handling with bounded depth**: pointer follow at render time is capped at 4 hops. If a cycle is detected (visited-set during follow), the inner region renders the reserved "cycle terminator" color (a deterministic shade not used by any primitive type). Test asserts a 3-cycle renders without panic, terminates by frame 1, and the terminator shade is present in the cycle nodes' inner regions.

- [ ] **R5 — Linked list example**: `examples/linked_list.rs` allocates 20 `Tracked<u32>` value cells and 20 `Pointer<u32>` cells linking them in order. The head pointer is held in cell index 0. Loop for n=1..=10000 mutates the values; the pointer chain stays static. Produces `linked_list.mp4` where the chain visibly forms a glass corridor — each pointer cell's inner color matches the next node's value color.

- [ ] **R6 — Binary tree example**: `examples/binary_tree.rs` allocates 15 nodes in a balanced tree (1 root + 2 children + 4 + 8). Each node has two pointer cells (`left`, `right`). Loop for n=1..=10000 mutates the leaf values only. Produces `binary_tree.mp4` where each internal node's two pointer cells show their subtree's average color.

- [ ] **R7 — Pointer smoke test**: `tests/pointer_smoke.rs` validates: target-color rendering (pointer's inner region matches target's inner region), aliasing equality (two pointers to same target are pixel-identical inner), cycle bounded (3-cycle renders without panic and terminator shade is present).

## Files to Create/Modify

- `experiments/memory-as-framebuffer-v0/src/pointer.rs` — new module
- `experiments/memory-as-framebuffer-v0/src/render.rs` — extended for pointer cells (transparent surface)
- `experiments/memory-as-framebuffer-v0/src/allocator.rs` — extended type tag range for pointer kinds
- `experiments/memory-as-framebuffer-v0/src/lib.rs` — re-export pointer types
- `experiments/memory-as-framebuffer-v0/examples/linked_list.rs`
- `experiments/memory-as-framebuffer-v0/examples/binary_tree.rs`
- `experiments/memory-as-framebuffer-v0/tests/pointer_smoke.rs`
- `experiments/memory-as-framebuffer-v0/README.md` — extended with pointer section

## Acceptance Tests

- `cd experiments/memory-as-framebuffer-v0 && cargo test --release pointer` passes the pointer smoke test.
- Manual validation: open `linked_list.mp4` and `binary_tree.mp4` — the glass-corridor and branching-glass effects are visible; pointer cells show next-node colors.

## Verification

```bash
cd experiments/memory-as-framebuffer-v0
cargo build --release
cargo test --release pointer
cargo run --release --example linked_list
cargo run --release --example binary_tree
ls -la linked_list.mp4 binary_tree.mp4
ffprobe -v error -show_entries stream=codec_name,r_frame_rate,nb_frames linked_list.mp4
```

## Out of Scope

- Refcount enforcement and GC visualization (RcPtr cells stay allocated until manually dropped — v2 concern).
- Actual alpha compositing (real transparency); v1 uses inner-region color substitution which conveys the idiom without a compositing engine.
- Cross-thread pointer mutation; the snapshot thread reads, the mutator writes — locking is fine for v1.
- Pointer chains deeper than 4 hops fully resolved; deeper chains visibly truncate.
- Walking-through-a-pointer (door mode); v1 stays in window mode (look through the glass without entering).

## Risks and Assumptions

- **Render-time cycle detection adds work** — for a 256×256 grid with potential cycles, the visited-set per pointer follow is small (≤4 entries) so total cost is bounded. Document.
- **Inner-region color matching is fuzzy across compression** — H.264 may slightly perturb pixel values between adjacent cells. Smoke test uses tolerance ±2 RGB rather than exact equality.
- **Kind-frame distinguishability** — four kinds × black background may be hard to tell apart in low-resolution video. Document; tune palette to ensure each kind is distinguishable.
- **Aliasing demo legibility** — two cells far apart on the grid may look unrelated even when their inner colors match. README documents that aliasing is most visible when the two pointer cells are near each other.

## Known Gaps and Follow-up Tasks

- Follow-up: refcount visualization (Rc counter visibly etched in frame, decrementing on drop) — `memory-as-framebuffer-v2-refcount`.
- Follow-up: door mode (walk through a pointer to the target's scope) — `memory-as-framebuffer-v2-door-mode` (likely 3D-only; see v1-3d).
- Follow-up: cycle visualization (mirror-tunnel optical effect) — depends on v1-3d for the perspective trick to work.
- Follow-up: smart-pointer-aware mutation (e.g. RcPtr clone increments a counter) — out of scope for v1; tracked.
