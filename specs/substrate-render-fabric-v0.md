---
idea_id: substrate-as-render-fabric
status: draft
source:
  - file: api/app/services/substrate/render_kernels.py
    symbols: [register_render_kernel, lookup_render_kernel, RenderKernelRecord]
  - file: api/app/routers/substrate_render.py
    symbols: [POST /api/substrate/render-kernels, GET /api/substrate/render-kernels/{blueprint_hash}]
  - file: api/app/models/substrate_render.py
    symbols: [RenderKernelCreate, RenderKernelOut, RenderKernelEdge]
  - file: experiments/memory-as-framebuffer-v0/src/substrate_bridge.rs
    symbols: [SubstrateClient, blueprint_hash_for_type_tag, fetch_recipe_for_blueprint, push_provenance]
  - file: experiments/memory-as-framebuffer-v0/src/lib.rs
    symbols: [Tracked — extended to compute Blueprint hash at construction]
  - file: api/tests/test_substrate_render_kernels.py
    symbols: [test_register_kernel, test_lookup_by_blueprint_hash, test_render_edge_persists]
  - file: experiments/memory-as-framebuffer-v0/tests/substrate_bridge_smoke.rs
    symbols: [test_provenance_uses_substrate_hash, test_render_kernel_fetched_from_api]
requirements:
  - "Add Blueprint-hash computation to Tracked<T> construction: each Tracked allocation produces a Blueprint hash (Blake3 of the type's structural form: type-name + size + field layout) and stores that as the cell's type tag (extended from 16-bit primitive tag to a 64-bit hash, with a 16-bit fast-path lookup table for the v0 primitives)."
  - "Provenance plane writes substrate cell hashes (64-bit) instead of crc32(file:line). The substrate cell at that hash represents the source location with file/line/symbol metadata content-addressed."
  - "POST /api/substrate/render-kernels accepts a RenderKernelCreate { blueprint_hash, recipe_content, kernel_kind } and creates a substrate cell + (Blueprint)-[:rendered_by]->(Recipe) edge in the existing graph DB."
  - "GET /api/substrate/render-kernels/{blueprint_hash} returns the registered Recipe (kernel content) for that Blueprint, or 404 if no override is registered. The default-render fallback path kicks in when 404 is returned."
  - "experiments/memory-as-framebuffer-v0/src/substrate_bridge.rs adds a SubstrateClient that, at framebuffer init, fetches all registered render kernels for the Blueprints present in the program and caches them locally. Cache misses (new Blueprint encountered mid-run) trigger an async refresh; cells render with default until the refresh lands."
  - "Cross-language type identity test: a Python type with the same structural form as a Rust type produces the same Blueprint hash, and registering a kernel for that hash in either language causes both to render with that kernel."
  - "Hallucination-bounded check: if a Tracked allocation produces a Blueprint hash not in substrate, the framebuffer auto-registers a minimal Blueprint cell (structural metadata only, no Recipe) so substrate stays in sync with what's actually being rendered."
done_when:
  - "cargo run --release --example fizzbuzz writes provenance hashes that resolve via the substrate API to source-location cells (file/line/symbol)."
  - "POST /api/substrate/render-kernels creates a kernel; the Rust example's next render cycle picks up the new kernel and the matrix3x3 cells render through it (when v1-render-trait is also live)."
  - "test_substrate_render_kernels.py passes: register, lookup, edge persistence."
  - "tests/substrate_bridge_smoke.rs passes: provenance hash resolution, kernel fetch."
test: "cd api && .venv/bin/pytest -q tests/test_substrate_render_kernels.py && cd ../experiments/memory-as-framebuffer-v0 && cargo test --release substrate_bridge"
constraints:
  - "Builds on memory-as-framebuffer-v0 (Rust crate) and the existing coherence-substrate (Python). The substrate cell schema and graph DB are already in place — this spec uses them, does not redefine them."
  - "Type-tag widening from u16 to u64 is a breaking change to the v0 storage layout. Document migration; v0 mp4s remain replayable, but the v0 binary format is bumped to v0.2.0."
  - "Async substrate fetch must not block the render thread. If the Recipe is not cached, fall back to default render and refresh in the background; never freeze the snapshot loop on network."
  - "API authentication uses the existing api-key keystore convention. The Rust client reads the same ~/.coherence-network/keys.json; the bridge is opt-in (env var MFB_SUBSTRATE_URL must be set for the bridge to activate)."
  - "Provenance hash format: 64-bit Blake3-of(file_abs_path + ':' + line + ':' + col). Substrate cell at that hash is created lazily on first reference."
---

# Spec: Substrate as Render Fabric — v0

## Purpose

Bridge the memory-as-framebuffer crate to the existing coherence-substrate so that **render kernels are substrate Recipes**, **type identity is Blueprint hash**, **pointers are substrate cell hashes**, and **provenance is a substrate edge** rather than process-local data. Once this lands, the visualizer is no longer a tool that lives beside the program — it's a face of substrate. Two consequences immediately follow: (1) cross-language type identity (a Rust struct and a Python class with the same structural form share a Blueprint hash and render with the same kernel — register once, both languages get it); (2) the visualization grammar registers in substrate alongside concepts, ideas, and presences, so adding a custom kernel for `Tree<T>` is just adding a Recipe cell + `(Blueprint)-[:rendered_by]->(Recipe)` edge. This is the v0 of that bridge: minimal, scoped to the existing v0 primitives + the Matrix3x3 example, async-friendly so it can't degrade the framebuffer's runtime sovereignty.

## Requirements

- [ ] **R1 — Blueprint hash computation**: extend `Tracked<T>::new()` in `src/lib.rs` to compute a 64-bit Blake3 hash of the type's structural form (type-name string + size + alignment + for composite types, the recursive Blueprint hash of each field). For the nine primitives, the hash is precomputed; the cell's type tag is extended from u16 to u64 (storage bump v0.1 → v0.2). The first 16 bits remain the fast-path primitive tag for compatibility.

- [ ] **R2 — Substrate-keyed provenance**: extend `track!` macro to write a 64-bit hash `Blake3(file_abs_path + ":" + line + ":" + col)` into the (now u64-wide) provenance plane. On first reference, the Rust client lazily creates a substrate cell at that hash containing the source-location metadata.

- [ ] **R3 — Render-kernel API**: in `api/app/routers/substrate_render.py`:
  - `POST /api/substrate/render-kernels` — body `{blueprint_hash: str (hex), recipe_content: str (kernel source/spec), kernel_kind: "rust" | "python" | "wasm"}` — creates a Recipe cell + `(Blueprint)-[:rendered_by]->(Recipe)` edge in the graph DB. Returns the created Recipe's substrate hash.
  - `GET /api/substrate/render-kernels/{blueprint_hash}` — returns the registered Recipe content for that Blueprint, or 404.
  - Both endpoints require api-key auth (same convention as POST /api/ideas).

- [ ] **R4 — Rust substrate client**: `src/substrate_bridge.rs` adds a `SubstrateClient` that:
  (a) at framebuffer init, reads `MFB_SUBSTRATE_URL` env var (e.g. `https://api.coherencycoin.com`) and `~/.coherence-network/keys.json` for api-key.
  (b) prefetches render kernels for the nine v0 primitives + any user-registered Blueprints by issuing `GET /api/substrate/render-kernels/{hash}` per known Blueprint at startup.
  (c) caches results in-memory (HashMap<u64, Option<RenderKernel>>).
  (d) on cache miss mid-run (new Blueprint encountered), spawns an async fetch and falls back to default render until the response lands.
  (e) `push_provenance()` lazily creates substrate cells for source-location hashes that haven't been seen before.

- [ ] **R5 — Cross-language type identity test**: in `api/tests/test_substrate_render_kernels.py`, register a kernel for a Blueprint hash via the API. Compute the same Blueprint hash from a Python type with matching structure (e.g. `@dataclass class Point: x: float; y: float` matching Rust `struct Point { x: f32, y: f32 }`). Assert the GET endpoint returns the same kernel for that hash regardless of language origin.

- [ ] **R6 — Hallucination-bounded check**: if a Tracked allocation produces a Blueprint hash not yet in substrate, the bridge auto-creates the Blueprint cell (structural metadata only, no Recipe) via an internal POST. This ensures substrate stays in sync with what's actually being rendered — nothing renders that doesn't have a substrate cell.

- [ ] **R7 — Smoke tests**: 
  - Rust side: `tests/substrate_bridge_smoke.rs` — provenance hash → substrate cell resolution; kernel fetch hits cache after prefetch; cache miss triggers async fetch without blocking.
  - Python side: `api/tests/test_substrate_render_kernels.py` — register, lookup, edge persistence in graph DB, 404 on unknown Blueprint, auth required.

## Files to Create/Modify

- `api/app/services/substrate/render_kernels.py` — new service
- `api/app/routers/substrate_render.py` — new router (registered in main.py)
- `api/app/models/substrate_render.py` — Pydantic models
- `api/app/main.py` — register new router
- `api/tests/test_substrate_render_kernels.py` — new tests
- `experiments/memory-as-framebuffer-v0/src/substrate_bridge.rs` — new module
- `experiments/memory-as-framebuffer-v0/src/lib.rs` — extend Tracked + track! for u64 tag/provenance
- `experiments/memory-as-framebuffer-v0/src/allocator.rs` — widen cell layout (type tag 2→8 bytes, payload 14→8 bytes; or keep payload 14 and grow cell to 24 bytes — TBD by implementer, document choice)
- `experiments/memory-as-framebuffer-v0/Cargo.toml` — add blake3, reqwest (or ureq for sync fallback), serde_json
- `experiments/memory-as-framebuffer-v0/tests/substrate_bridge_smoke.rs`
- `experiments/memory-as-framebuffer-v0/README.md` — add Substrate Bridge section, env-var docs
- `api/app/routers/INDEX.md` — add line for substrate_render.py
- `api/app/services/INDEX.md` — add line for render_kernels.py

## Acceptance Tests

- `cd api && .venv/bin/pytest -q tests/test_substrate_render_kernels.py` passes — register/lookup/edge/auth.
- `cd experiments/memory-as-framebuffer-v0 && cargo test --release substrate_bridge` passes — provenance resolution and kernel fetch (uses a mock substrate URL or a docker-compose'd local API).
- Manual validation: `MFB_SUBSTRATE_URL=https://api.coherencycoin.com cargo run --release --example fizzbuzz` writes provenance to substrate; the substrate API confirms the source-location cells exist after the run.

## Verification

```bash
# API side
cd api && .venv/bin/pytest -q tests/test_substrate_render_kernels.py

# Crate side (with mock substrate URL)
cd experiments/memory-as-framebuffer-v0
cargo test --release substrate_bridge

# End-to-end (production substrate)
MFB_SUBSTRATE_URL=https://api.coherencycoin.com cargo run --release --example fizzbuzz
curl -sS https://api.coherencycoin.com/api/substrate/render-kernels/<expected_blueprint_hash> | python3 -m json.tool
```

## Out of Scope

- Substrate-Recipe-keyed render kernel **execution** — v0 of this spec stores the Recipe content and serves it on lookup. Actually executing a Python or WASM Recipe inside the Rust crate is a v1 concern (`substrate-render-fabric-v1-execution`).
- Live mutation of registered kernels with hot-reload — kernels are fetched at startup; mid-run kernel changes are a v1 concern.
- Distributed pointers (a Rust pointer cell on machine A pointing at a substrate cell on machine B) — the data layout supports it (substrate hash is global) but the rendering bridge needs richer infrastructure; v1 concern.
- Render kernels at additional kinds (e.g. Lisp, Skia paths, GLSL fragments). v0 supports kind: "rust" | "python" | "wasm" as enum strings; only the lookup path matters for v0, execution is v1.
- The 5th-axis resonance overlay (cells with similar Blueprints rendered in resonance-space) — `substrate-render-fabric-v1-resonance-axis`.

## Risks and Assumptions

- **Storage layout bump from u16 to u64 type tag** — breaks v0 mp4s' binary format if anyone is parsing them post-hoc; mp4s themselves remain watchable. Document.
- **Network dependency** — the Rust crate now depends on substrate API availability at startup. Mitigation: env var is opt-in (no MFB_SUBSTRATE_URL → bridge inactive, v0 default render). When active, async cache-and-fallback ensures no render-loop blocking on network.
- **Auth and api-key handling in Rust** — reqwest + reading keys.json adds dependencies. ureq is lighter; document choice.
- **Substrate cell creation race** — two concurrent Rust processes hitting the same source-location hash both try to create the cell. The substrate service must handle idempotent creation (POST is upsert-by-hash, returning existing cell on conflict).
- **Blueprint hash stability across compilers** — Rust compiler version, generic monomorphization, and feature flags can shift type sizes/layouts. Document that Blueprint hashes are stable per (rust-version, target, feature-set); cross-version comparison is best-effort.

## Known Gaps and Follow-up Tasks

- Follow-up: `substrate-render-fabric-v1-execution` — actually run Python/WASM Recipes from inside the Rust crate (sandboxed embedded interpreter).
- Follow-up: `substrate-render-fabric-v1-resonance-axis` — the 5th-axis visualization where cells cluster by Blueprint structural similarity.
- Follow-up: distributed pointer rendering (cross-machine pointer cells) — needs the substrate bridge to handle remote cells in the render path.
- Follow-up: hot-reload of kernels mid-run — requires kernel-changed event subscription via the substrate WebSocket.
- Follow-up: Blueprint-hash stability across Rust compiler versions — investigate using a normalized structural form (sorted field names + canonical type names) rather than raw `std::any::TypeId`.
