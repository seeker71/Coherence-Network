# JIT vector — the optimization slot the goal named

> *"JIT optimized recipe execution flow with minimal tracing overhead
> that put the tracing cost on the observer / tracer not the tracing
> emitting recipe coordinates"* — Urs, 2026-05-22

This document names the JIT slot the architecture already supports
and shows the minimal version that ships today as proof. Real native
code generation is a downstream optimization; the **shape that lets
JIT slot in** is what matters.

## Why JIT is possible here

Three properties of the existing architecture make JIT natural:

1. **Content-addressed Recipes.** Every Recipe has a stable NodeID
   determined by its shape. Same shape = same NodeID = same
   compiled artifact would apply. Cache keys are free.

2. **Source attribution on every cell.** The framebuffer
   (`framebuffer-events`, `node_source`) identifies which recipes
   are hot — observers walking the framebuffer find recipes worth
   compiling.

3. **Observer-side tracing.** Emitters pay no extra overhead beyond
   the existing `intern_node_at` hashmap insert. The hot-spot
   analysis runs in `tracer.fk` — only when an observer asks.

## What ships today as the minimal JIT shape

Three new kernel natives — **memoization JIT**:

- **`walk-cached(nid)`** — caller asserts the recipe is pure (no
  I/O, no external state). Result is cached by recipe NodeID.
  Subsequent calls return in O(1) instead of re-walking the tree.

- **`walk-cache-clear`** — reset the memoization cache (use when
  substrate state changes invalidate cached results).

- **`walk-cache-size`** — observability — paired with
  `framebuffer-events` lets tooling compare "recipes seen" vs
  "recipes JIT-cached" to measure hot-path coverage.

This is JIT-via-memoization. Real native compilation replaces the
cached `Value` with compiled machine code; the architectural slot
stays identical — same NodeID key, same return shape, lookup is
still O(1).

## The progression toward native code generation

| Stage | What | Status |
|---|---|---|
| 1 — interpretation | `walk_recipe(nid)` — recursive tree walk every call | shipped |
| 2 — memoization | `walk-cached(nid)` — cache result by NodeID | **shipped today** |
| 3 — typed annotations | recipes carry hardware-type hints (I32, F64, etc.) | future |
| 4 — bytecode | compile typed recipes to a kernel bytecode | future |
| 5 — native | compile bytecode to machine code per architecture | future |

Stage 3 unlocks stages 4-5 because the kernel needs to know what
machine-level operations a recipe maps to. Without types, recipes
stay generic (interpretation or memoization). With types, hot
recipes compile.

The framebuffer + tracer.fk shipped earlier this arc identifies
the candidates. The walk-cache shipped today is the first real
optimization. Subsequent breaths can add hardware-type annotations
and a bytecode/codegen layer when needed.

## Pairing with the observation surface

The same observer pattern that supports flow + hotspot analysis
naturally drives JIT decisions:

```form
;; Observer walks the framebuffer, identifies recipes seen N+ times.
(defn hot-recipes (events threshold)
    (filter (defn (cell) (gt (recipe-count cell) threshold))
            events))

;; Hot recipes get cached.
(defn jit-warm (events)
    (foreach (hot-recipes events 100)
             (defn (cell) (walk-cached cell))))
```

The architecture is symmetric: emitter writes once per intern,
observer reads when curious, JIT caches when hot. No layer pays for
what another wants.

## Verified

- Both Go and Rust kernels implement `walk-cached` + `walk-cache-clear`
  + `walk-cache-size`. Sibling parity verified at sum 124 on the
  smoke probe (100+23 evaluation + 1 cache entry + 0 after clear).

The goal's tracing + JIT pieces are now both in the body. The
remaining work — typed annotations and native code generation — is
a separate arc that builds on this foundation.
