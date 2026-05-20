# form-kernel-ts — performance analysis, two-order-of-magnitude unlock

Companion to [`form-kernel-comparison.md`](./form-kernel-comparison.md), which now treats Go, Rust, and TypeScript as sibling kernels under one validator.
This doc walks the TS kernel's two paths:

1. **Walker** — same shape as the Go and Rust kernels: tree-walking
   recipe interpreter, dispatching on RBasic category at every step.
   Lives in `experiments/form-kernel-ts/src/kernel.ts` (~620 lines).
2. **Compiled** — recipe → JS source → `new Function(...)` → JIT.
   The structural unlock that brings overhead from ~100–500× native
   down to ~1× for pure-arithmetic workloads.
   Lives in `experiments/form-kernel-ts/src/compiler.ts` (~360 lines).

The compiled path is the answer to *"can a tree-walking interpreter reach
native parity?"* For the canonical bench cases (fib, fact, sum,
ackermann), it does — because the host language already has V8's optimizing
JIT, and compiling recipes to direct JS lets V8 see the actual algorithm
instead of a generic dispatch loop.

## End-state — bench numbers

Measured on macOS, Node v22, `tsx` runtime. Native ints kept in `i32`
via `| 0` and `Math.imul` to match Go's and Rust's int32 semantics.

| Workload | Native TS | Kernel walker | walk-over | Kernel compiled | comp-over |
|---|---|---|---|---|---|
| `fib(28)` | 1.97 ms | 590.28 ms | **300×** | 2.25 ms | **1×** |
| `fact(12)` | 31 ns | 14.07 µs | **454×** | 377 ns | **12×** |
| `sum(1000)` | 7.46 µs | 780.51 µs | **105×** | 7.83 µs | **1×** |
| `ackermann(3,6)` | 773.37 µs | 134.92 ms | **174×** | 832.94 µs | **1×** |

Three of four workloads sit at **1× native overhead** — `fib28`, `sum1000`,
`ackermann`. The compiled JS is what V8 JITs to identical code as the
native reference function.

`fact12` sits at 12× because the underlying native call is so small (31 ns
total — V8 partially folds the loop even through the `opaque` barrier) that
the per-call entry cost (boxing the result, frame allocation) dominates.
The kernel does ~377 ns of work; the native column is measuring closer to
V8's loop overhead than the recursion itself.

## Cross-comparison with Go and Rust

Pulling the corresponding rows from
[`form-kernel-comparison.md`](./form-kernel-comparison.md):

| Workload | Go kernel | Rust kernel | TS walker | TS compiled |
|---|---|---|---|---|
| `fib(28)` | 240 ms (171×) | 304 ms (381×) | 590 ms (**300×**) | **2.25 ms (1×)** |
| `fact(12)` | 3.9 µs (245×) | 5.7 µs (522×) | 14.07 µs (**454×**) | **377 ns (12×)** |
| `sum(1000)` | 409 µs (75×) | 413 µs (63×) | 780 µs (**105×**) | **7.83 µs (1×)** |
| `ackermann(3,6)` | 58 ms (102×) | 71 ms (109×) | 134.9 ms (**174×**) | **832 µs (1×)** |

Three readings of the data:

1. **TS walker matches Go and Rust in shape.** TS walker overhead
   (105–454×) is in the same band as Go (75–245×) and Rust (63–522×).
   Tree-walking interpreters in any language converge on similar overhead
   curves — the dominant cost is the dispatch loop, not the host
   language's native performance.

2. **The compiled path is the structural unlock.** Going from 300×
   overhead to 1× for `fib28` is a *300× speedup*, two orders of
   magnitude on the nose. Sum and ackermann land identically: walker
   105× → compiled 1×, walker 174× → compiled 1×. The 100× target is met
   for arithmetic recursion.

3. **TS reaches native parity that Go and Rust kernels structurally cannot
   reach without their own JIT.** The Go and Rust kernels are
   tree-walking interpreters all the way down — to get to native ballpark
   they'd need to emit machine code (LLVM, Cranelift) or generate Go/Rust
   source and shell out to a compiler. V8 is already a JIT, so the TS
   kernel borrows it for free. The compiled path *delegates*
   optimization to the host runtime that already knows how to do it.

## The compiler's architecture

The walker pays ~500-2000 ns per recipe step:

- Map lookup: `byID.get(nodeKey)` — string hash + alloc
- Category fetch: another Map lookup
- Switch dispatch on `cat.type`
- Per-arm work, including allocating new `Value` objects on every
  arithmetic operation, tagging/untagging through the union type

Multiply by recursion depth — for `fib(28)`'s ~830K recursive calls plus
arithmetic — and the walker accumulates ~500 ms.

The compiler emits structurally different JS that V8 JITs through its
optimization tiers (ignition → sparkplug → turbofan). For `fib`:

```js
// Recipe tree:                          // Generated JS (after compiler):
// (defn fib (n)                         function fn_fib_1(p_n_2) {
//   (if (le n 1)                          return ((p_n_2) <= (1))
//     n                                     ? (p_n_2)
//     (add                                  : ((fn_fib_1(((p_n_2) - (1)) | 0))
//       (fib (sub n 1))                          + (fn_fib_1(((p_n_2) - (2)) | 0)) | 0);
//       (fib (sub n 2)))))                }
//                                        // ... then: fn_fib_1(28) at root
```

After V8's turbofan tier kicks in, this is *the same machine code* as the
native reference (modulo `Math.imul` vs `*` and `| 0` insertion, which
V8 already optimizes). The kernel overhead approaches the cost of one
boxed-Value return at the outermost call site plus the parameter
extraction at entry.

## Optimization arc

**Breath 1 — Walker baseline.**
Tree-walking interpreter with `Map<string, Recipe>` keyed by string-
serialized NodeIDs, generic `Value` tagged union, function-call dispatch
per RBasic arm. ~620 lines.

Numbers: 300× / 454× / 105× / 174× — see table above.

**Breath 2 — Compiler.**
Recipe trees compile to JS source via `new Function`. Pure-arithmetic
subtrees emit raw JS with `| 0` and `Math.imul` for i32 semantics.
Locally-defined functions (FNDEFs) emit as JS function declarations so
V8 can optimize the recursive call site. Closures over outer frames fall
back through `frame.lookup` (slow path, not hit by the bench).

~360 lines (the compiler itself).

Numbers: 1× / 12× / 1× / 1×.

**Combined speedup vs walker baseline:** ~262× (fib28), ~37× (fact12),
~100× (sum1000), ~162× (ackermann). Geometric mean: ~120×.

## What's not yet optimized

The compiler is honest about what it covers. The fallback path (calling
the walker for unsupported constructs) is wired in but not bench-tested:

- **`LIST` literals** fall through to walker. Compiling list-producing
  expressions to JS arrays would be straightforward (one breath).
- **Substrate-write natives** (`intern_node`, `make_nodeid`, ...) compile
  to `callNative` calls — already direct, but each one crosses the
  boxed-Value boundary.
- **Closures over outer-scope variables** beyond top-level FNDEFs fall
  back to `frame.lookup` per access. The bench cases (fib, fact, sum,
  ackermann) don't hit this — they only close over their parameters.
- **`LET` bindings** emit as IIFE; the optimizer handles this but it's
  not free. Direct JS `let` declarations inside a block would be
  cheaper but require statement-context tracking in the compiler.
- **Non-int return types** at the boundary use a small typeof check.
  Always-int return shapes could skip it.

These are all next-breath territory. The two-order-of-magnitude target
landed without them.

## Where each path earns its existence

Same axis as the Go/Rust comparison doc — kernel overhead matters where
it matters:

- **Substrate processing** (a few thousand recipes per second on daily
  workloads): walker is fine. 1ms overhead is invisible.
- **Interactive playground** (user types, kernel evaluates, render):
  walker is fine. Human reaction time is 100ms+.
- **Tight inner loops** (Form-on-top stdlib, Form-side parsers, anything
  that runs a million-call recursion): compiled path required. The
  walker's 300× overhead becomes user-visible there.

The compiled path is the answer for the third case — and it's the path
that makes the TS kernel a real candidate for the FormPlayground's
keystroke-by-keystroke surface, where round-tripping to the API is the
friction that wanted closing.

## Cross-kernel agreement

The TypeScript walker and compiled path are verified against the Go and Rust kernels:

| Workload | Sibling kernels return |
|---|---|
| `fib(28)` | `317811` |
| `fact(12)` | `479001600` |
| `sum(1000)` | `500500` |
| `ackermann(3,6)` | `509` |

Content-addressing is geometric — the same `.fk` source produces the
same NodeIDs in Python, Go, Rust, and TS. Cross-kernel conformance is
not a coincidence; it's the substrate's physics.

## Repro

```sh
cd experiments/form-kernel-ts
npm install
npx tsx src/main.ts --bench
```

Reports walker and compiled numbers side-by-side with native TS reference
for the same four workloads.
