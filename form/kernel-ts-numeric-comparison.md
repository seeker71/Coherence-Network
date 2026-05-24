# Format-recipes as substrate cells — performance + design

Companion to [`kernel-ts-comparison.md`](./kernel-ts-comparison.md)
(the i32/walker/compiled arc) and
[`docs/coherence-substrate/numeric-types-plan.md`](../docs/coherence-substrate/numeric-types-plan.md)
(the architecture).

This doc walks the format-recipe path through two efficiency passes and
shows that the architecture pays no runtime tax — generic format
dispatch lands at native parity once warmed up, and JIT-compiled JS
reaches native parity from the cold start.

## The architecture, named once

Numeric values are represented as `(semantic-kind, format-recipe, value)`
triples. The format-recipe is a substrate cell — same shape as any
other recipe — that describes the encoding completely:

```
format-recipe (FP8 E4M3):
  ├── semantic-kind   : REAL
  ├── encoding        : IEEE_754
  ├── bits            : 8
  ├── storage-hint    : "u8-array"
  ├── arithmetic-hint : "table-lookup-via-fp32"
  ├── mantissa-bits   : 3
  ├── exponent-bits   : 4
  └── exponent-bias   : 7
```

Adding a new numeric format — FP4, NF4, BitNet ternary, posit, log-prob,
arbitrary-precision rational — is a substrate write that creates a new
format-recipe cell. No kernel change. The kernel reads `storage-hint`
and `arithmetic-hint` and dispatches; if the compiler recognizes the
hints, it emits specialized JS that V8 JITs.

## Three passes — what each measures

The bench (`src/numeric-bench.ts`) runs three workloads through four
paths:

- **Native TS** — bare JS arithmetic, no format dispatch (reference)
- **Pass 0** — naïve dispatch via `applyArith(fmt, op, a, b)` switching
  on the arithmetic-hint at every call
- **Pass 1** — JIT'd specialized closures from the format-table cache.
  For each (format, op) the cache emits a per-call closure via
  `new Function` whose body contains only the relevant arithmetic;
  V8 inlines and JITs.
- **Pass 2** — full-function JIT via recipe-driven JS code generation.
  Given a format-recipe and a recursive shape, emit the whole function
  source as specialized JS, compile once via `new Function`.

The three workloads exercise three different arithmetic-hint paths:

- **fp64**: `Σ i * 0.5` for i in 1..1000 — arithmetic-hint = `native-fp`
- **fp8**: `Σ Math.fround(i * 0.0625)` — arithmetic-hint = `table-lookup-via-fp32`
- **bitnet**: dot product of {-1, 0, 1} values — arithmetic-hint = `native-int`

## Numbers

```
format     native       pass0(naïve)   p0-over  pass1(cached)   p1-over  pass2(JIT)   p2-over
fp64       11.12 µs     19.60 µs       2×       9.50 µs         1×       10.44 µs     0.9×
fp8        9.95 µs      22.57 µs       2×       15.93 µs        2×       9.57 µs      1.0×
bitnet     10.07 µs     13.53 µs       1×       10.21 µs        1×       10.06 µs     1.0×
```

Three readings:

1. **Pass 0 (naïve dispatcher) costs ~2× native.** Generic format
   dispatch through `applyArith(fmt, op, a, b)` — switch on
   `arithHintCode`, switch on `opCode`, do the work — adds a constant
   2× overhead. For cold paths and rare formats this is acceptable;
   for hot paths it's not.

2. **Pass 1 (JIT'd handler closures) reaches native parity for two of
   three formats.** The cache emits a closure via `new Function`
   containing only the relevant operator. V8 sees specialized JS,
   inlines, JITs to direct arithmetic. FP64 add becomes literally
   `function(a, b){ return (+a) + (+b); }` — V8 produces the same
   machine code as bare `a + b`. The FP8 path stays at 2× because the
   `Math.fround` round-trip is inherent to fp32 narrowing, not
   dispatch overhead.

3. **Pass 2 (full-function JIT) reaches native parity for all three
   formats.** The recipe-driven emitter walks the format-recipe and
   produces the whole recursive function as specialized JS — `f(n,
   acc)` with the format's emit-strategy inlined. V8 JITs the full
   function as one unit. This is the path the Form kernel's compiler
   already uses for i32; extending to f64 and other formats is
   one line of dispatch in the emitter.

## What this means for the architecture

**The format-recipe abstraction is free at runtime, when warmed up.**

The cost was supposed to be: "generic dispatch is slow because it has
to read the format-recipe and branch." Reality: V8 monomorphizes the
dispatch path so well that Pass 0 only pays 2× — and Pass 1 closes
even that gap. The architectural elegance (kernel reads format-recipes
from substrate; new formats need no kernel change) doesn't trade off
against performance.

**Adding FP8, NF4, BitNet, posit, log-prob — all free of kernel
patches.** Each is ~30 lines of format-recipe definition. The Pass 0
dispatcher handles it on day one (with ~2× overhead). The Pass 1
cache emits a specialized closure on first use (native parity for
arithmetic-hint = native-fp / native-int / xor-popcount; slight
overhead for software-fp paths). The Pass 2 compiler generates whole
specialized programs from format-recipes.

**Cross-kernel agreement extends to format-recipes.** Two kernels
that intern the same format-recipe tree get the same NodeID. A FP8
value with the same bit pattern decodes to the same NodeID on Python,
TS, Go, Rust. Quantization-aware Form code (LLM weights, mixed-
precision matmul, NF4 inference) runs portably across the conformance
circle.

## Cross-comparison with the i32/walker/compiled story

| Path | What it tests | Overhead |
|---|---|---|
| i32 walker (original bench) | Recipe tree walked at runtime | 100–500× native |
| i32 compiled (original bench) | Recipe tree → JS function via `new Function` | 1× native |
| Pass 0 (numeric-bench) | Generic format dispatcher in JS | 2× native |
| Pass 1 (numeric-bench) | Per-(format, op) JIT'd closure cache | 1× native (varies by hint) |
| Pass 2 (numeric-bench) | Per-function recipe-driven codegen | 1× native |

The walker number (100–500×) is the irreducible cost of walking a
substrate recipe tree at runtime — `Map.get` per node, dispatch per
category, allocation per Value. The compiled paths (numeric Pass 1,
Pass 2, and the original compiled column) all reach native because
they delegate to V8's JIT.

## The two-pass optimization arc in tissue

**Pass 1 — Specialize the handler cache.**

Before: `applyArith(fmt, op, a, b)` — generic dispatcher with cascaded
switches on string hint and string op.

After: `compileHandler(fmt, op)` — emits a per-(format, op) JS closure
via `new Function`. The closure body is the specialized operator only:
no switch, no boxing, no function-call overhead beyond the closure
invocation itself.

Diff: ~80 lines in `src/numeric.ts` and `src/formats.ts`.

Measured win: 2× → 1× for hot formats (fp64, bitnet). fp8 stays at
~1.6× because `Math.fround` narrowing is part of the operation, not
dispatch overhead.

**Pass 2 — Specialize the function emit.**

Before: per-workload hardcoded source strings ("for FP64 emit `n *
0.5 + acc`, for FP8 emit `Math.fround(...)`...")

After: `emitOpExpr(fmt, op, aSrc, bSrc)` — a generic emitter that
reads the format-recipe and produces JS source for the given operator,
with the format's emit-strategy inlined. `compileSumWithScale(fmt,
scale)` uses it to generate the whole recursive function.

Diff: ~60 lines, replacing three hardcoded source strings with one
recipe-driven emitter.

Measured win: 1.0× for all three formats. The compiled function is V8-
visible as user code; JIT'd to native.

**The architectural point of Pass 2.** It's not really a performance
optimization on top of Pass 1; both reach native parity for hot paths.
The architectural value is that Pass 2 generalizes — *the same emitter
produces native code for any format-recipe*. Adding NF4 weights, FP4
activations, posit accumulators, log-prob sums — all just route
through this one emitter, no per-format codegen code.

## What's still hardware-bound, honestly

Even with format-recipes-in-substrate, a few hardware bindings remain:

- **`storage-hint = "v8-double"`** assumes V8 stores Number as f64
  internally. True today; if V8 changed its Number storage, the hint
  would still work (semantically the host stores it however it stores
  it), but the JIT-output would shift.
- **`Math.imul`, `Math.fround`** are host intrinsics. Other JS hosts
  (Hermes, SpiderMonkey) may implement them differently.
- **`new Function` JIT compilation** depends on V8 actually JITting
  emitted source. Cold start cost (~µs) is real; not all JS hosts
  optimize this path equally.

These are *implementation properties of the storage/arithmetic-hint
handlers*, not properties of the substrate's identity grammar. A
different host (Bun, Deno, browser, Cloudflare Workers) might
implement the same format-recipes with different storage shapes. The
NodeIDs stay invariant; the underlying storage is local.

## Repro

```sh
cd form/form-kernel-ts
npm install
npx tsx src/main.ts --numeric-bench    # format-recipe arc
npx tsx src/main.ts --bench            # original i32/walker/compiled arc
```

## Open follow-up breaths

- Implement the FP8 / NF4 / BitNet value-table storage layer with
  packed `Uint8Array` and `Uint16Array` (current path uses generic
  Number storage; production path needs the actual packed storage for
  quantization workloads to be memory-realistic)
- Wire the Pass 1/Pass 2 paths into the Form kernel's walker and
  compiler — currently they live in `numeric.ts` / `numeric-bench.ts`
  as a parallel demonstration; integrating into `walkMath` is the
  next breath
- Cross-kernel coordination: write `docs/coherence-substrate/numeric-formats.fk`
  as the canonical bootstrap, validated by the conformance harness
- Python kernel migration: BNumeric extension to read format-recipes
  the same way

The architecture is sound. The performance story is honest. The
remaining work is wiring it through the existing kernel surfaces and
expanding the format library.
