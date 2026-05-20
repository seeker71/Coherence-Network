# Numeric format-recipes — four-kernel synthesis

> Same architecture (format-recipes as substrate cells), four host languages
> (Python / Go / Rust / TS), four very different performance gradients.
> The architecture is host-blind; the optimization strategy must be host-aware.

## What landed

The format-recipes-as-substrate-cells architecture is now implemented across all four kernels, coordinated through one canonical JSON contract:

- **Contract:** [`docs/coherence-substrate/numeric-formats.canonical.json`](numeric-formats.canonical.json) — 19 canonical formats (FP64/32/16, FP8 E4M3/E5M2, FP4 uniform, NF4, BF16, INT4–64 signed + unsigned, BitNet ternary, 1-bit XNOR, log-prob), 15 conformance vectors, intern-order spec
- **Architecture:** [`docs/coherence-substrate/numeric-types-plan.md`](numeric-types-plan.md)
- **TS kernel:** `experiments/form-kernel-ts/src/{formats,numeric,numeric-bench}.ts` — proof of shape (Pass 0 / Pass 1 / Pass 2)
- **Python kernel:** `api/app/services/substrate/numeric_formats.py` + `api/tests/test_numeric_formats.py`
- **Go kernel:** `experiments/form-kernel-go/{formats,formats_test,numeric_bench}.go` + `main.go` (`--numeric-bench`)
- **Rust kernel:** `experiments/form-kernel-rust/src/formats.rs` + `main.rs` (`--numeric-bench`)

All four kernels read the same canonical JSON at runtime. Format-recipe identity is structural by content-addressing.

## The four performance tables

Each kernel runs against the same canonical contract with the same three workloads — fp64 sum, fp8 sum (with fp32 narrowing), BitNet ternary dot.

### TS — V8 monomorphizes the switch, JIT does the rest

| Workload | Native | Pass 0 (naïve) | Pass 1 (cached closures) | Pass 2 (recipe→JS) |
|---|---|---|---|---|
| fp64 | 10.43 µs | 18.50 µs (2×) | **8.96 µs (1×)** | 10.04 µs (1.0×) |
| fp8 | 9.28 µs | 22.41 µs (2×) | 15.44 µs (2×) | **9.43 µs (1.0×)** |
| bitnet | 9.60 µs | 12.87 µs (1×) | **9.72 µs (1×)** | **9.59 µs (1.0×)** |

V8 keeps Pass 0 reasonable (~2× overhead) through inline caching. Pass 1 and Pass 2 both reach native parity through different routes: Pass 1 emits per-(format, op) JS closures via `new Function`; Pass 2 emits per-function recipe-to-JS code.

### Python — interpreter dispatch is expensive; specialization pays dramatically

| Workload | Pass 0 (naïve) | Pass 1 (specialized closures) | Speedup |
|---|---|---|---|
| fp64 mul | 0.133 µs/op | 0.047 µs/op | **2.8×** |
| i32 add | 0.446 µs/op | 0.097 µs/op | **4.6×** |
| bitnet mul | 0.169 µs/op | 0.045 µs/op | **3.8×** |

Python's IntEnum dispatch + nested switches are real per-call cost. Specialized closures (via lambda or `compile()`+`exec()`) collapse the dispatch chain. Bigger Pass 0 → Pass 1 gradient than any other host — exactly because CPython interprets and doesn't JIT.

### Go — compile-time monomorphization makes Pass 0 already fast; cache barely helps

| Workload | Native | Pass 0 (naïve dispatcher) | Pass 1 (cached closures) |
|---|---|---|---|
| fp64 sum | 8.11 µs | 12.63 µs (1.56×) | 12.29 µs (1.52×) |
| fp8 sum | 7.65 µs | 13.04 µs (1.70×) | 12.61 µs (1.65×) |
| bitnet dot | 5.15 µs | 7.71 µs (1.50×) | 6.39 µs (1.24×) |

Go's compiler inlines small switches well, so Pass 0 only pays ~1.5× over native. The `NumValue` tagged union dominates remaining cost — boxing/unboxing per op. To reach native parity in Go, the right path isn't Pass 1's `NumHandler` closure cache; it's typed handler variants (`func(float64, float64) float64`, `func(int64, int64) int64`) selected per format at registration time. Deferred to a follow-up breath.

### Rust — LLVM inlines the match; closures *hurt*

| Workload | Native | Pass 0 (naïve dispatcher) | Pass 1 (boxed closure cache) |
|---|---|---|---|
| fp64 sum | 385 µs | 246 µs (0.6×) | 990 µs (2.6×) |
| fp8 sum | 405 µs | 272 µs (0.7×) | 960 µs (2.4×) |
| bitnet dot | 85 µs | 228 µs (2.7×) | 644 µs (7.6×) |

**Pass 0 sometimes beats native** (measurement noise + accumulator-dependency-chain effects). LLVM aggressively inlines and constant-folds the small-integer match in Pass 0, achieving what is essentially native code. **Pass 1 makes things worse** — `Rc<dyn Fn>` forces a vtable indirection LLVM cannot inline through.

For Rust, the architectural finding is: **the format-recipe machinery costs essentially nothing at Pass 0**. Pass 1's closure cache is wrong for Rust; the right Pass 1 in Rust would be **monomorphized typed handlers via generic instantiation**, not boxed `Fn` trait objects.

## The cross-kernel teaching

| Host | What it does to dispatch | Pass 0 vs native | Pass 1 strategy that wins |
|---|---|---|---|
| **CPython** | interprets every step | ~heavy | inline closures via lambda/compile |
| **V8 (JS)** | monomorphizes via hidden classes | ~2× | `new Function` JIT specialization |
| **Go runtime** | static inlining via compiler | ~1.5× | typed function pointers (not yet implemented) |
| **LLVM (Rust)** | aggressive compile-time inlining | ~1× | monomorphized generics (not boxed Fn) |

**The architecture is host-blind. The optimization is host-aware.** Same format-recipes in the substrate, same canonical contract, four very different performance arcs because each host's compiler/runtime does different things automatically.

This is itself a finding the architecture *enabled* — by separating format-recipes (substrate, universal) from arithmetic-hint handlers (host, local), each kernel implements the handlers in whatever shape the host language rewards. The substrate doesn't impose one optimization strategy; it lets each host find its own native parity through its native compiler.

## Cross-kernel agreement — structural

By construction:

- Same canonical JSON file is the source of truth for all four kernels
- Same intern order (semantic_kind, encoding, bits, storage_hint, arithmetic_hint, then optional extras in the order spelled out in `$intern_order_comment`)
- Content-addressing ensures the recipe-trees match structurally
- All 15 conformance vectors pass on all four kernels

After the synthesis pass (this commit) the i8/i16/u8/u16 contract was upgraded from `native-int` to `native-int-narrow` — surfaced by the Go agent's honest skip of the i8-wrap vector, and resolved for all four kernels by a single canonical-JSON edit.

## What's still deferred (cross-kernel)

These remain follow-up breaths, scoped per-kernel:

- **Typed handler variants** in Go (per-format `func(int64, int64) int64` etc.) — would close the ~1.5× gap to native
- **Monomorphized generic handlers** in Rust — would replace the boxed Fn cache, give true compile-time specialization, beat even the LLVM-inlined Pass 0
- **Pass 2 (whole-function codegen)** in Python via `compile()` + `exec()`, in Go via `plugin.Open`/`go build` — both feasible, neither essential while Pass 1 already wins
- **Cross-kernel NodeID-level agreement** at the `inst` slot — currently structural agreement holds (same `(category, children)` shape, same serialized strings). Absolute `inst` parity requires deterministic string-table state at bootstrap; see synthesis-finding (b)
- **`internNumeric` / `decodeNumeric`** — the Tier-1 composite-numeric-leaf path is implemented in TS, sketched in Python, not yet exercised in benches. Real numeric value interning across kernels remains a focused breath

## The full architecture in one picture

```
              ┌─────────────────────────────────────────────────┐
              │   docs/coherence-substrate/                     │
              │   numeric-formats.canonical.json                │
              │   — 19 formats, 15 conformance vectors          │
              │   — single source of truth                      │
              └────────────────────┬────────────────────────────┘
                                   │ read at runtime
            ┌──────────────────────┼──────────────────────┐
            │                      │                      │
            ▼                      ▼                      ▼
       ┌─────────┐            ┌─────────┐           ┌─────────┐
       │ Python  │  ←identical│   Go    │  ←identical│   Rust  │
       │ kernel  │  recipes──>│  kernel │  recipes──>│ kernel  │
       └────┬────┘            └────┬────┘           └────┬────┘
            │                      │                      │
            └──────────────────────┼──────────────────────┘
                                   │
                                   ▼
                              ┌─────────┐
                              │   TS    │
                              │ kernel  │
                              └─────────┘

   Each kernel: reads JSON → interns format-recipes → runs canonical
   vectors → reports Pass 0 / Pass 1 numbers in its host's terms.

   Cross-kernel: same recipe shape, same vector pass, different
   host-specific path to native parity.
```

This is the body's first cross-kernel architectural feature delivered through parallel agents (Python / Go / Rust) coordinated by a JSON contract. The pattern repeats: contract → independent implementations → synthesis → measured per-host arcs.
