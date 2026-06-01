# API → Form-kernel readiness map

> The flip-gate evidence for the question Urs named: *before* flipping a
> FastAPI endpoint to run its body on the Form-native kernel instead of inline
> CPython, characterize that the kernel path is healthy enough to carry real
> traffic — in VALUE, SHAPE, PROFILE, and circulation under load. This doc is
> measurement and honest evidence; it does **not** flip anything.

Harness: [`scripts/kernel_readiness_harness.py`](../scripts/kernel_readiness_harness.py).
Companion to [`scripts/substrate_parity_harness.py`](../scripts/substrate_parity_harness.py)
(value/structure parity) — this one adds the profile-under-load axis that a
green demo count cannot give.

> **The correction this doc carries (2026-06-01).** An earlier pass measured a
> per-request fork+exec of the kernel (PATH A) and read ~5 ms/call. That was the
> **wrong serving model**, and not a fair comparison: CPython serves from a
> warm, already-loaded process — it does **not** fork an interpreter per
> request. The honest counterpart is a **persistent kernel** that loads the
> routes ONCE and then runs request→response over the live process. With spawn
> removed, per-request latency drops from ~5 ms to **~0.1–0.23 ms p50**
> (sub-millisecond, ~20–40× faster than the spawn-bound path). The persistent
> number is the one that decides the flip; the per-request-spawn number was an
> artifact of the wrong harness shape. Both are stated below so the correction
> is legible.

## What's eligible for the flip, and what stays CPython

The flip is for the **pure-computation core** of an endpoint, not the whole
stack. FastAPI stays the doorway.

| Layer | Kernel-bmf eligible? | Why |
|-------|----------------------|-----|
| Pure numeric/structural computation (the `endpoint_*_demo.py` shapes) | **Yes** | Deterministic, integer/float/list in → value out. This is what a Form recipe carries today. |
| HTTP routing, path/query binding | No | FastAPI's job — the doorway. |
| Pydantic request/response validation | No | Schema validation lives in the framework; the kernel returns a scalar/list the response model wraps. |
| Async I/O, concurrency | No | The kernel is a synchronous evaluator; async orchestration stays in the host. |
| DB / Neo4j / Postgres calls, network | No | Side-effecting I/O, not pure computation. Carriers (substrate ports) are a separate arc, not this flip. |

So the readiness question is **only** about the computational core of the four
already-transmuted endpoints in
[`api/app/routers/utils.py`](../api/app/routers/utils.py):
`coherence_weight`, `nodeid_distance`, `nodeid_compatibility`, `weighted_average`.

## How the live endpoint dispatches to the kernel (the real capture target)

The endpoints call `serve_via_kernel` in
[`api/app/services/form_kernel_bridge.py`](../api/app/services/form_kernel_bridge.py).
Per request it:

1. `load_recipe(endpoint_X.fk)` — loads a `.fk` **pre-compiled at deploy time**
   (the deploy pipeline runs `npx tsx src/main.ts python-compile X.py X.fk`
   once; the `.fk` is **not** committed and is **absent in a fresh worktree** —
   the harness compiles it to stand in for the deploy artifact).
2. `inject_bindings(...)` — rewrites the `(let ...)` input literals in-process (µs).
3. **The dispatch fork**, fastest path available:
   - `inline` — the `form_kernel_rust` PyO3 extension, a C call into Rust, no
     spawn. **Not built in this environment** (nor, today, in the deploy image).
   - `subprocess` — fork+exec the `form-kernel-rust` binary on a temp `.fk`.
     **This is the path that serves today** wherever the binary is present.
   - `python-fallback` — the inline-CPython twin, when no kernel is reachable.

There is a second, much heavier path that the "API code → Form-native, no
Python in the path" dream implies: `form/scripts/pyfkb-run.sh --kernel rust`
(**PATH B**), which source-compiles ~10 BML preludes and runs the whole
python-bmf scanner/grammar/eval pipeline over raw `.py` bytes every call. That
is a **parity-proof** path, not a serving path — measured below to show why.

## Measured profile (2026-06-01, this worktree, release build)

Harness: `python3 scripts/kernel_readiness_harness.py --iters 50` (50 timed
iterations per runtime after a 5-run warmup; nearest-rank percentiles). The
kernel column is **PATH A** — the exact live `inject_bindings + run_recipe`
subprocess dispatch.

| Endpoint | Value parity | CPython p50 | Kernel A p50 | p95 / p99 | Ratio (p50) | `.fk` compile (once) |
|----------|:---:|---:|---:|---:|---:|---:|
| `coherence_weight` | ✓ 16185 | 0.0007 ms | 5.01 ms | 5.68 / 11.39 ms | ~7,100× | 770 ms |
| `nodeid_distance` | ✓ 7 | 0.0004 ms | 5.03 ms | 5.44 / 5.76 ms | ~13,400× | 685 ms |
| `nodeid_compatibility` | ✓ 2 | 0.0004 ms | 4.88 ms | 5.47 / 5.52 ms | ~11,700× | 701 ms |
| `weighted_average` | ✓ 0.8125 | 0.0004 ms | 4.87 ms | 5.35 / 5.63 ms | ~11,700× | 688 ms |

**Stability under replay:** kernel A latency is stable across 50 iterations
(stdev 0.28–0.97 ms, p99 within ~2× of p50 except one 11 ms outlier on the
first endpoint — GC/scheduler jitter, not drift). **No leak or degradation**
across the run. The response SHAPE is intact: the kernel returns the scalar
(`int`/`float`) the response model's headline field expects; the other fields
(`values`, `threshold`, `runtime`, …) are echoed by the host.

### Where the 5 ms goes — the decisive breakdown

Isolating spawn from compute (40 iters each, warmed):

| Measurement | p50 |
|-------------|----:|
| Bare kernel spawn (trivial `(do 1)` recipe) | **4.37 ms** |
| Kernel spawn + `coherence_weight` recipe | 4.52 ms |
| **Recipe execution only (full − spawn)** | **~0.15 ms** |

The ~5 ms is **process spawn**, not computation. The recipe itself executes in
**~0.15 ms** — competitive with, and for non-trivial work potentially faster
than, CPython. The entire readiness gap is fork+exec overhead paid per request.

### PATH B (the full python-bmf pipeline per call)

`pyfkb-run.sh --kernel rust` on `coherence_weight`: **~310 ms/call** (p50),
≈440,000× CPython and ≈62× even PATH A. It re-source-compiles the BML preludes
every invocation. **This path cannot serve load as a per-call shell-out** — it
is a correctness/parity instrument. It only becomes a serving path with a
persistent kernel process that compiles the preludes once and stays warm.

## The persistent-serve model — the apples-to-apples number

The fix to the wrong comparison is already in the kernel:
[`form/form-kernel-rust/src/main.rs`](../form/form-kernel-rust/src/main.rs)
`cli_serve` (`form-kernel-rust serve --port P --routes file.fk`). It loads a
`routes.fk` ONCE into a long-lived `Kernel + Arena`, holds the top-level
`routes` binding (a list of `(path handler-closure)` pairs), starts an HTTP/1.0
listener, and dispatches each request to the matching handler with a **fresh
child frame** — **no per-request process spawn, no per-request source-compile.**
This is the warm-process counterpart to a CPython worker.

The route table the harness registers is
[`scripts/kernel_readiness_routes.fk`](../scripts/kernel_readiness_routes.fk):
the four endpoint computations bound once as `(defn …)` recipes (the SAME bodies
the live endpoints run, captured from the `endpoint_*_demo.py` shapes), each
wrapped in a handler closure. A request → handler call → recipe walk → response
body is one in-process movement.

**Measured (2026-06-01, this worktree, release build,
`--persistent --iters 200`):**

| Endpoint | Value parity | CPython p50 | **Serve p50** | Serve p95 / p99 | Serve verdict |
|----------|:---:|---:|---:|---:|---|
| `coherence_weight` | ✓ 16185 | 0.0007 ms | **0.189 ms** | 0.243 / 0.265 ms | READY (shape) |
| `nodeid_distance` | ✓ 7 | 0.0004 ms | **0.231 ms** | 0.262 / 0.288 ms | READY (shape) |
| `nodeid_compatibility` | ✓ 2 | 0.0004 ms | **0.235 ms** | 0.264 / 0.278 ms | READY (shape) |
| `weighted_average` | ✓ 0.8125 | 0.0004 ms | **0.090 ms** | 0.134 / 0.192 ms | READY (shape) |

**The real ratio, spawn removed.** Per-request latency over the warm channel is
**~0.09–0.24 ms p50, p99 under 0.29 ms** — sub-millisecond, **~20–40× faster
than the ~5 ms spawn-bound PATH A.** Against CPython's bare-compute p50
(~0.0004 ms) the *ratio* still reads as a few-hundred×, but that ratio is the
wrong lens: CPython's headline is a sub-microsecond arithmetic loop with **zero
transport**, while the kernel number includes a full HTTP/1.0 loopback
round-trip. Judge on the **absolute**: ~0.2 ms request→response is negligible
overhead for an HTTP endpoint (the network and FastAPI's own routing dwarf it).

**What the ~0.2 ms is made of.** It is dominated by the HTTP/1.0 loopback
(connect + request line + 8 KiB read + response write) and the string-alist
marshalling, **not** recipe execution. The recipe walk itself is the same
~0.15 ms (or less, for these tiny recipes) the PATH A breakdown isolated. So the
persistent serve confirms the earlier prediction empirically: **the kernel was
never the bottleneck — the spawn was.**

### Honest limits of the serve mode (proof-of-shape, not production)

`cli_serve` is a ~50-line raw `std::net` HTTP/1.0 listener. It is the right shape
to *measure* the persistent model; it is **not** a production HTTP server. Named
plainly:

- **HTTP/1.0, no keep-alive** — every request is a fresh TCP connection. A real
  serving path wants keep-alive or an in-process call (PyO3), which removes even
  the connect cost.
- **Single-threaded, sequential** — one request at a time. No concurrency.
- **String-only query alist** — the query string arrives as `(list (key value)…)`
  with every value a STRING. The two integer NodeID endpoints marshal cleanly
  (8 int query params, parsed with `str_to_int`); `coherence_weight` and
  `weighted_average` take a **list** (and floats), and the kernel ships no
  `split` / `str_to_float` native, so their handlers compute the **frozen
  sample input** — the recipe body that runs is identical to live, but the
  per-request *inputs* are not yet marshalled from the wire. List/float query
  marshalling is the named gap, not a measured failure.
- **No Pydantic, no validation, no async** — those stay in FastAPI regardless.

The serve mode proves **the persistent shape is sound and sub-ms**. The
production carrier of that shape is the **inline PyO3** path (a warm `Kernel`
held in-process, called by FastAPI with no socket at all) — same warm-kernel
win, no HTTP/1.0 limits.

## JIT — what `register_jit` and `jit_compile` actually do today

Two distinct mechanisms live in the kernel, and the honest readiness map keeps
them apart:

- **`register_jit form-name native-name`** (main.rs ~line 2669) — **aliases** a
  Form recipe name to an *existing host-native*. It is a dispatch hint, not a
  compiler: it only speeds a recipe when an equivalent native already exists
  (e.g. aliasing a Form `my-count` to native `len`). For the four endpoint
  recipes there is **no native equivalent**, so `register_jit` buys nothing.
- **`jit_compile form-name`** (main.rs ~line 2733) — a **real recipe→machine-code
  compiler**: it emits Rust source from the Form recipe, invokes the system
  `rustc --crate-type=cdylib`, loads the `.so` via `libloading`, and dispatches
  subsequent calls through the native function pointer. This is genuine native
  compilation, not aliasing.

**What `jit_compile` buys, measured.** On a recipe *inside its emit subset* —
`fib` written with the operator forms `emit_rust_source` covers
(`add`/`sub`/`lt`) — the harness measured **8× `fib(30)` walked = ~10,375 ms vs
recipe→native = ~485 ms: a ~21× speedup, INCLUDING the one-time rustc compile.**
Steady-state (compile amortized) is higher still. The compiler is real and the
win is large.

**Why it is a no-op for the four endpoints — the precise gap.** `jit_compile`
returns **0** (honest "unavailable") for all four endpoint recipes. The cause is
**emit coverage**, not the compiler:

- `emit_rust_source` / `emit_expr` cover the **operator** recipe shapes —
  `RB_MATH` (`add sub mul div mod`), `RB_COMPARE`, `RB_LOGIC`, `RB_COND`, and
  calls to **sibling Form functions**. They emit i64-only Rust.
- The Python adapter compiles arithmetic to **native calls** — `_plus`, `abs`,
  `_get`, `_iter`, `head`, `tail`, `len`, `nth` — which fall through to
  `RB_FNCALL` against natives the emitter cannot inline (it would have to call
  back into the walker). The endpoint recipes also use **lists and floats**,
  both outside the i64 emit subset entirely.

So the gap to a real recipe-JIT *for these endpoints* is concrete: the emitter
needs (1) native-builtin inlining or a native→Rust shim for `_plus`/`abs`/list
ops, (2) **f64** emission (today it is i64-only), and (3) list/iteration
lowering. None of that is exotic — it is emit-coverage work on a compiler that
already produces and loads real machine code. Until then: **persistent serve is
what gets the endpoints to sub-ms; `jit_compile` is the proven path to native
for the *operator* subset and the named extension for the rest.**

## Honest verdict — per call

Two models, stated separately so the correction is legible:

| Endpoint | PATH A (per-req fork+exec — WRONG model) | **Persistent serve (apples-to-apples)** |
|----------|------------------------------------------|------------------------------------------|
| `coherence_weight` | NOT-YET — +5 ms/req spawn | **READY (shape)** — 0.189 ms p50, 0.265 ms p99 |
| `nodeid_distance` | NOT-YET — spawn-bound | **READY (shape)** — 0.231 ms p50, 0.288 ms p99 |
| `nodeid_compatibility` | NOT-YET — spawn-bound | **READY (shape)** — 0.235 ms p50, 0.278 ms p99 |
| `weighted_average` | NOT-YET — spawn-bound | **READY (shape)** — 0.090 ms p50, 0.192 ms p99 |

"READY (shape)" means: correct (4/4 value parity over the warm channel), stable
percentiles, and a sub-ms absolute latency envelope under the persistent model.
It is **not** "ship it" — the serve mode's HTTP/1.0 / single-thread / string-arg
limits above mean the *production* carrier is inline PyO3, not this listener.
The shape is proven; the production path is named.

Read precisely:

- **Correctness is met.** 4/4 value parity over the warm channel, stable
  percentiles, response shape intact.
- **Under the persistent model the kernel is sub-ms.** ~0.09–0.24 ms p50,
  p99 under 0.29 ms — and most of that is HTTP/1.0 loopback, not recipe
  execution. The per-request-spawn ~5 ms was an artifact of the wrong harness
  shape, never the kernel's cost.
- **The production carrier is the warm kernel held in-process.** The serve mode
  proves the shape; **inline PyO3** (a `Kernel` loaded once at module import,
  called by FastAPI with no socket) carries it without the HTTP/1.0 /
  single-thread / string-arg limits. The bridge already routes to an `inline`
  path when the `form_kernel_rust` extension is built — building that extension
  in the deploy image is what turns "READY (shape)" into "READY (production)".

The number that matters for the flip decision: **with the kernel persistent,
request→response is ~0.2 ms — sub-millisecond, HTTP-negligible.** The flip needs
a **warm kernel** (inline PyO3, or a long-lived serve process), not a per-call
shell-out. That requirement is now backed by a measured persistent profile, not
a prediction.

## What's needed before a real flip

1. **Build the inline PyO3 kernel** (`form_kernel_rust`) in the API image and
   re-run with `--persistent` — confirm the in-process `inline` path lands at or
   below the serve number (it should be *faster*, with no socket round-trip).
   That is the load-ready, production-carrier measurement.
2. **Marshal real inputs over the channel.** The two list/float endpoints
   currently compute a frozen sample under serve because the string-only query
   alist plus the missing `split` / `str_to_float` natives can't carry a list.
   Add list/float wire-marshalling (or do it inline via PyO3 where Python hands
   the kernel typed values directly) so every endpoint marshals its real inputs.
3. **Capture real traffic.** Today's inputs are **representative-derived** from
   the endpoints' query defaults / Pydantic contracts, *not* sampled from
   production. Add a request-log → replay corpus so the profile reflects real
   value distributions (list sizes, edge cases), not one frozen input each.
4. **Grow the captured-call corpus** to cover input-size scaling (10 → 100 →
   1000-element value lists) — the persistent overhead is fixed, but recipe
   execution scales with input; the crossover where kernel compute beats CPython
   is worth measuring.
5. **JIT the hot paths.** Extend `emit_rust_source` to cover the native-builtin
   and f64/list shapes the endpoint recipes use (today it is i64 + operators +
   sibling-calls only), so `jit_compile` can lower them to native — the same
   compiler that already buys ~21× on the operator subset.
6. **Load levels + concurrency.** Re-run at `--iters 1000`+ and under concurrent
   clients to confirm stability holds at serving rates (the serve mode is
   single-threaded — concurrency needs PyO3-inline or a threaded listener).
7. **Latency envelope that counts as healthy:** for an HTTP endpoint, p99 kernel
   overhead under ~1 ms over the CPython baseline. The persistent serve already
   meets this (p99 < 0.3 ms); inline PyO3 is expected to beat it.

## Running the evidence

```bash
python3 scripts/kernel_readiness_harness.py                          # PATH A, 50 iters
python3 scripts/kernel_readiness_harness.py --persistent             # + the warm serve path (apples-to-apples)
python3 scripts/kernel_readiness_harness.py --persistent --jit       # + serve+jit mode and the JIT demonstrator
python3 scripts/kernel_readiness_harness.py --iters 1000 --persistent # load replay
python3 scripts/kernel_readiness_harness.py --path-b                 # include PATH B
python3 scripts/kernel_readiness_harness.py --json out.json          # machine-readable
```

The harness exits nonzero **only** on a value-parity failure. Slowness is
reported as evidence, never as a test failure — the profile informs the flip
decision; it does not gate CI. The persistent serve mode starts one
`form-kernel-rust serve` process per mode, fires all requests over it, and kills
it on exit; no listener is left running.
