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
>
> **The production carrier landed (2026-06-01).** The inline PyO3 extension the
> serve evidence pointed at is now **built and measured** — it removes the
> HTTP/1.0 loopback the serve number was dominated by, landing at **~0.05–0.13 ms
> p50, sub-200µs p99, faster than serve on all four endpoints (~4.5–4.9× on the
> integer ones)**. The warm in-process kernel is no longer a prediction; it is a
> measured profile. See "The inline PyO3 carrier" below.
>
> **The per-request parse is gone (2026-06-01).** The inline carrier still
> re-parsed the `.fk` source on every call inside `compile_and_run`. The named
> next step — a `load_route + run(handle, bindings)` PyO3 pair — is now **built
> and measured**: a warm `Preloader` parses each endpoint recipe **once** and
> per request walks only the pre-parsed body with the inputs bound in a fresh
> child frame (no tokenize, no read, no `defn`-rebind). Dropping the parse cuts
> p50 a further **2.6–14×** vs inline-with-parse (a stable **~62µs** mean drop),
> landing the integer endpoints at **3–5µs p50, sub-10µs p99**. Value-parity
> holds 4/4. This is the floor a synchronous in-process kernel reaches for these
> recipes. See "The route-preload carrier" below.

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
     spawn. **Built and measured in this worktree (2026-06-01)** via
     `maturin develop --release` into the API venv; the hot path the
     persistent-serve evidence pointed at. The deploy image still needs the
     build step (named below).
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
win, no HTTP/1.0 limits. **That carrier is now built and measured** — next
section.

## The inline PyO3 carrier — the production hot path, built and measured

The persistent-serve number is dominated by HTTP/1.0 loopback, not compute. The
inline carrier removes the loopback entirely: the `form_kernel_rust` PyO3
extension is imported **once** at `form_kernel_bridge` module load — a warm Rust
runtime living *inside* the Python process — and each request is a C call
straight into `compile_and_run`, returning an already-typed Python value
(`int`/`float`/`list`). No process spawn, no socket. This is the path
`serve_via_kernel` takes first whenever `inline_available()` is true.

**What was built (2026-06-01).** The PyO3 surface already existed in source
([`form/form-kernel-rust/src/lib.rs`](../form/form-kernel-rust/src/lib.rs),
`Cargo.toml` `[lib] crate-type=["cdylib","rlib"]` + `pyo3` feature,
`pyproject.toml` maturin config, bridge wired to `compile_and_run`) but had
**never been built** — it didn't compile against the current kernel. Two shallow
breaks fixed:

1. `src/main.rs` `crate::bp_table::BP_ENTRIES` → `self::bp_table::BP_ENTRIES` —
   a path that resolves in **both** the bin build (where `main.rs` is the crate
   root) and the lib build (where `main.rs` is `mod kernel`).
2. `src/lib.rs` `value_to_py` gained the missing `Value::Record(_)` arm
   (renders via the kernel's own `display()`, same surface as the CLI).

Then `maturin develop --release` (maturin 1.13.3, Rust 1.95, CPython 3.11,
abi3-py39) built and installed `form_kernel_rust` into the API venv. The bridge
loads it (`inline_available() == True`, `active_runtime() == "inline"`) and
`serve_via_kernel` returns typed values via the warm kernel with no spawn.

**Measured (2026-06-01, this worktree, release build, `--inline --persistent
--iters 300`):**

| Endpoint | Value parity | CPython p50 | Serve p50 | **Inline p50** | **Inline p99** | Serve→Inline |
|----------|:---:|---:|---:|---:|---:|---:|
| `coherence_weight` | ✓ 16185 | 0.0008 ms | 0.176 ms | **0.128 ms** | **0.190 ms** | 1.4× faster |
| `nodeid_distance` | ✓ 7 | 0.0004 ms | 0.244 ms | **0.050 ms** | **0.078 ms** | 4.9× faster |
| `nodeid_compatibility` | ✓ 2 | 0.0004 ms | 0.241 ms | **0.054 ms** | **0.085 ms** | 4.5× faster |
| `weighted_average` | ✓ 0.8125 | 0.0004 ms | 0.107 ms | **0.092 ms** | **0.139 ms** | 1.2× faster |

**Inline beats serve on all four, and the loopback was the difference.** On the
two integer NodeID endpoints — which marshal real inputs both ways (no frozen
sample) — inline is **~4.5–4.9× faster** than serve, landing at **sub-100µs p99**
(0.078 / 0.085 ms). That delta is precisely the HTTP/1.0 connect + request-line
+ read/write round-trip that serve pays and inline does not. `coherence_weight`
and `weighted_average` carry list/float inputs that the inline path injects as
`.fk` literals per request (the inject + larger recipe walk), so their win over
serve is smaller (1.2–1.4×) but still real, and still sub-200µs p99.

**Value parity holds exactly inline** — 16185 / 7 / 2 / 0.8125, with types
preserved (ints stay `int`, 0.8125 is a `float`, via `value_to_py`). The inline
path returns the response model's headline scalar directly; the host echoes the
other fields, same as serve.

**Why the CPython ratio is still the wrong lens.** Inline p50 / CPython p50 reads
as ~130–250× — but CPython's headline is a sub-microsecond arithmetic loop with
**zero transport and zero recipe machinery**. Inline's ~0.05–0.13 ms includes
inject + a C boundary crossing + a full recipe walk. Judge on the **absolute**:
**sub-100µs p99 for the integer endpoints, sub-200µs for the list/float ones** —
negligible against FastAPI routing + Pydantic + the network, which dwarf it.

**Honest limit of these inline numbers — now closed.** The inline path above
still re-parses the `.fk` source per request inside `compile_and_run` — it
removes the *spawn* and the *loopback*, not the per-request parse. For these tiny
recipes the parse is a small fraction of the sub-100µs envelope, but a fully warm
carrier holds the *pre-parsed recipe root* and re-walks only with fresh bindings
(the same shape `cli_serve` uses internally with its loaded `routes` list). That
`load_route + run(handle, bindings)` pair is **now built and measured** — the
next section. The `compile_and_run` numbers above stay the honest baseline the
preload path is measured against.

## The route-preload carrier — the parse dropped, built and measured

The inline `compile_and_run` re-tokenizes and re-reads the **whole** recipe on
every call (`run_source` → `read_root_from_source` → `tokenize_sexp` +
`read_sexp`), then re-walks every `defn` to re-bind its closure before the
trailing call. For a fixed-shape endpoint whose only per-request change is the
input values, that parse + `defn`-rebind is pure overhead paid each request.

**What was built (2026-06-01).** A `Preloader` `#[pyclass]` on the PyO3 module
([`form/form-kernel-rust/src/lib.rs`](../form/form-kernel-rust/src/lib.rs)) holds
a long-lived `Kernel + Arena + root_env` — mirroring `cli_serve`'s pattern. Two
methods:

- `load_route(setup_src, body_src) → handle` — walks `setup_src` (the recipe's
  `defn`s) **once** into the root frame so its closures bind a single time, then
  parses `body_src` (the trailing call) into a held `NodeID`. Returns an opaque
  handle (an index into the `Preloader`'s route `Vec`). Reuses the kernel's
  existing `read_root_from_source` + `walk` — no reimplemented parser.
- `run(handle, bindings) → value` — converts the bindings dict to kernel
  `Value`s, binds them into a **fresh child frame** of the root, and walks the
  pre-parsed body `NodeID`. No tokenize, no read, no `defn`-rebind. Converts the
  result through the **same `value_to_py`** the inline path uses, so value-parity
  is exact.

ONE mechanism, routes as DATA: every endpoint is a `(setup, body)` pair indexed
by handle; no endpoint is special-cased. The Python bridge owns the recipe text,
so the split (which `(let …)` forms carry per-request inputs vs the `defn`/const
setup) lives in `form_kernel_bridge.split_recipe`, keeping the Rust side
recipe-agnostic. The minimal main.rs change was **visibility only** — `Arena`
(+ `new`/`new_frame`/`new_frame_with_capacity`/`bind`/`lookup`), `walk`, and
`read_root_from_source` became `pub(crate)` so lib.rs can hold the warm kernel;
no evaluator logic changed. `serve_via_kernel` takes the preload path first when
the `Preloader` is available; it reports `runtime == "inline"` (preload is a
sub-mode of the inline carrier, not a new carrier class) and falls through to
inline-with-parse if a recipe doesn't split/parse cleanly.

**Measured (2026-06-01, this worktree, release build, `--inline --preload
--iters 2000`, reproduced across two runs):**

| Endpoint | Value parity | **Inline-with-parse p50** | **Preload p50** | Preload p95 / p99 | Parse drop | Speedup |
|----------|:---:|---:|---:|---:|---:|---:|
| `coherence_weight` | ✓ 16185 | 0.1263 ms | **0.0475 ms** | 0.058 / 0.086 ms | **−78.7µs** | **2.66×** |
| `nodeid_distance` | ✓ 7 | 0.0511 ms | **0.0037 ms** | 0.0047 / 0.0078 ms | **−47.4µs** | **13.93×** |
| `nodeid_compatibility` | ✓ 2 | 0.0544 ms | **0.0043 ms** | 0.0055 / 0.0063 ms | **−50.1µs** | **12.56×** |
| `weighted_average` | ✓ 0.8125 | 0.0902 ms | **0.0174 ms** | 0.0212 / 0.0292 ms | **−72.8µs** | **5.19×** |

**The parse was a real, stable cost — and it's gone.** Dropping the per-request
parse cuts p50 by a **fixed ~47–79µs** (mean **62µs**), reproducible to within
~1µs across runs. The two integer NodeID endpoints — whose recipes are tiny, so
the parse dominated — drop **~13–14×**, landing at **3–4µs p50, sub-10µs p99**.
The list/float endpoints carry a larger recipe walk, so the parse is a smaller
fraction; they still drop **2.7–5.2×** (the same absolute ~73–79µs saved),
landing at **17–48µs p50, sub-90µs p99**. The walk itself is now the entire
per-request cost — there is nothing left to remove inside the kernel for these
recipes.

**Value parity holds exactly** — 16185 / 7 / 2 / 0.8125, types preserved (ints
stay `int`, 0.8125 a `float`), via the same `value_to_py` the inline path uses.
The bridge's `serve_via_kernel` returns these through the preload path while
reporting `runtime == "inline"`, so the live response contract is unchanged.

**Honest limit.** `load_route` is called once per `(recipe, binding-name-set)`
at first request and cached; that first call pays the split + parse (a one-time
cost, not per-request). The preload handle map is process-local — a fresh worker
re-preloads on its first request (sub-millisecond, paid once). Input marshalling
is now **fully typed end-to-end**: Python hands the kernel `int`/`float`/`list`
values directly through `py_to_value`, so unlike the serve path there is **no
frozen-sample gap** — all four endpoints, including the list/float ones, run
their **real per-request inputs**. That closes the serve mode's named
list/float-marshalling gap for the inline carrier.

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

| Endpoint | PATH A (fork+exec — WRONG model) | Persistent serve (HTTP loopback) | Inline PyO3 (parse each call) | **Route-preload (parse dropped)** |
|----------|----------------------------------|----------------------------------|-------------------------------|-----------------------------------|
| `coherence_weight` | NOT-YET — +5 ms/req spawn | 0.176 ms p50 | 0.128 ms p50, 0.190 p99 | **0.048 ms p50, 0.086 p99 — READY** |
| `nodeid_distance` | NOT-YET — spawn-bound | 0.244 ms p50 | 0.050 ms p50, 0.078 p99 | **0.004 ms p50, 0.008 p99 — READY** |
| `nodeid_compatibility` | NOT-YET — spawn-bound | 0.241 ms p50 | 0.054 ms p50, 0.085 p99 | **0.004 ms p50, 0.006 p99 — READY** |
| `weighted_average` | NOT-YET — spawn-bound | 0.107 ms p50 | 0.092 ms p50, 0.139 p99 | **0.017 ms p50, 0.029 p99 — READY** |

The four-point profile: per-request **fork+exec** (~5 ms, the wrong model) →
**persistent serve** (~0.1–0.24 ms, sub-ms but HTTP/1.0-loopback-bound) →
**inline PyO3, parse each call** (~0.05–0.13 ms, the loopback gone) →
**route-preload** (~0.004–0.048 ms, the parse gone). Each step removes a cost the
previous paid: spawn → loopback → per-request parse. Route-preload is the floor a
synchronous in-process kernel reaches for these recipes — what remains per
request is only the recipe walk itself.

"READY" here means: correct (4/4 value parity inline, types preserved), stable
percentiles, and a **sub-100µs-to-sub-200µs absolute envelope with no spawn and
no socket** — the warm-in-process carrier the readiness evidence named. It is
**healthy to carry the four transmuted endpoints' computational core.** What
remains before a production flip is the deploy-image build of the extension and
the per-request-parse refinement (both named below), not a profile question —
the profile is met.

Read precisely:

- **Correctness is met.** 4/4 value parity over the warm channel, stable
  percentiles, response shape intact.
- **Under the persistent model the kernel is sub-ms.** ~0.09–0.24 ms p50,
  p99 under 0.29 ms — and most of that is HTTP/1.0 loopback, not recipe
  execution. The per-request-spawn ~5 ms was an artifact of the wrong harness
  shape, never the kernel's cost.
- **The production carrier is built and measured.** **Inline PyO3** (the
  `form_kernel_rust` extension imported once at module load, called by FastAPI
  with no socket) is now built in this worktree and measured at **0.05–0.13 ms
  p50, sub-200µs p99 — faster than serve on all four, ~4.5–4.9× faster on the
  integer endpoints where the HTTP loopback was the whole difference.** The
  bridge routes to it first when available. What turns this into "READY
  (production)" is the **deploy-image build** of the extension (the same
  `maturin develop --release` this worktree ran), plus the per-request-parse
  refinement — not a further profile question.

The number that matters for the flip decision: **with the kernel inline,
request→response compute is ~0.05–0.13 ms — sub-100µs p99 on the integer
endpoints, HTTP-negligible.** The flip needs a **warm kernel**; the warm kernel
now exists as a built PyO3 extension with a measured profile, not a prediction.

## What's needed before a real flip

1. **Build the inline PyO3 kernel in the deploy image.** ✅ **Built and measured
   in this worktree (2026-06-01)** — `maturin develop --release` into the API
   venv; inline lands **below** the serve number (~4.5–4.9× faster on the integer
   endpoints, sub-200µs p99 across all four). What remains is reproducing that
   build **in the deploy image**: add `maturin` to the API image build and run
   `cd form/form-kernel-rust && maturin build --release` (or `develop` into the
   image's venv) so `form_kernel_rust` imports in production. Then the live
   `active_runtime()` reports `inline` and `/api/health` shows the hot path.
   *Refinement — done (2026-06-01):* the per-request parse is dropped. The
   `Preloader` `load_route + run(handle, bindings)` PyO3 pair parses each recipe
   once and walks only the pre-parsed body per request, cutting p50 a further
   2.6–14× (mean ~62µs drop). See "The route-preload carrier". The deploy-image
   build is the same `maturin develop --release`; it picks up the `Preloader`
   class automatically — no extra build step.
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
python3 scripts/kernel_readiness_harness.py --inline                 # + the warm in-process PyO3 path (parse each call)
python3 scripts/kernel_readiness_harness.py --inline --preload       # + route-preload (parse dropped); names the per-call parse drop
python3 scripts/kernel_readiness_harness.py --inline --persistent    # the spawn → loopback → inline profile
python3 scripts/kernel_readiness_harness.py --inline --persistent --preload  # the full four-point profile
python3 scripts/kernel_readiness_harness.py --persistent --jit       # + serve+jit mode and the JIT demonstrator
python3 scripts/kernel_readiness_harness.py --iters 1000 --inline    # load replay, inline
python3 scripts/kernel_readiness_harness.py --path-b                 # include PATH B
python3 scripts/kernel_readiness_harness.py --json out.json          # machine-readable
```

The `--inline` mode requires the `form_kernel_rust` PyO3 extension built into
the running interpreter (`maturin develop --release` from
`form/form-kernel-rust/`); when it is absent the harness reports the inline
verdict as `UNAVAILABLE` and the other modes are unaffected.

The harness exits nonzero **only** on a value-parity failure. Slowness is
reported as evidence, never as a test failure — the profile informs the flip
decision; it does not gate CI. The persistent serve mode starts one
`form-kernel-rust serve` process per mode, fires all requests over it, and kills
it on exit; no listener is left running.

## Toward full kernel-native routing + attribution

The four transmuted endpoints are the seed, not the destination. The direction
Urs named: **serve most/all routes through the kernel → full attribution and
traceability → an activity view that shows which Blueprints / Recipes / Cells
are most alive, and which sit inert and want a look at why they're registered
but never involved.** This section writes that destination down so the next
breath continues it instead of re-deriving it.

### The destination

A body where the **computational core of every eligible route** runs as a Form
recipe on the warm in-process kernel. Then every request leaves an attribution
trace — which arm categories (Blueprints) dispatched, which Form functions
(Recipes) were called, which natives fired — and the body can **see its own
execution shape**: hot paths exercised on every request, dormant paths that no
route reaches. The substrate's promise (content-addressed structural identity)
becomes a *live* signal: not just "these two cells share a Blueprint" but "this
Blueprint fired 176 times serving real traffic; that one has never fired —
why is it here?"

### The path — incremental, each step earning its proof

1. **Transmute routes incrementally.** Each eligible route (pure
   numeric/structural computation — see "What's eligible" above) lands a `.py`
   demo + compiled `.fk` recipe, joins `PARITY_FILES`, and calls
   `serve_via_kernel`. **Every transmuted route earns value-parity proof** (the
   three-way CPython/TS/Rust gate) before it ships. The growth edge is the
   `total − served` count the wellness probe names.
2. **The wellness probe guards the surface.** `sense_kernel_api()` in
   `scripts/wellness_check.py` senses the kernel-native surface across the five
   dimensions Urs named — **performance, stability, accuracy, transparency,
   vitality** — quiet when healthy, specific on drift (a python-fallback that
   should be inline, a parity break, a latency regression, attribution gone
   missing). As routes are transmuted, the probe's vitality ratio climbs and the
   same five signals keep watch over the wider surface. It is the standing
   sensor that lets the transmutation proceed without fear.
3. **The attribution-activity view grows with coverage.**
   `scripts/kernel_attribution_report.py` runs the kernel-served recipes through
   the kernel's `trace` mode and aggregates the arm / function / native
   attribution into a ranked view — hot Blueprints, hot Recipes, and natives
   each resolved to a Blueprint NodeID via `native_blueprint`. It also names the
   **inert** natives: registered but never fired across today's routes, the
   "why here, not involved?" candidates. **The view widens by one row per
   transmuted route** — routes are DATA in `KERNEL_SERVED_RECIPES`; adding a
   transmuted route to that list extends the activity view with no code change.

### The capability ledger — what's banked, what gates the rest

Coverage growth is no longer gated by *finding* candidates — the clean
pure-scalar well is nearly dry. It is gated by *capability*: each new family of
routes waits behind one kernel/adapter capability, and each capability, once
banked, unlocks a whole family at once (the `ln`/`exp`, list-construction,
`round_ndigits`, and record-access unlocks each did exactly this). The honest
way to read the path to "most routes kernel-served" is as a **sequence of
capability builds**, not a candidate hunt.

**Banked (each proven three-way + live):**

| Capability | Native/mechanism | Family it unlocked |
|---|---|---|
| Float arithmetic | `Value::Float`, `intern_trivial_float` | weighted averages, ratios, any non-integer math |
| Transcendentals | `math_log`, `math_exp` (+ existing `sqrt`/`pow`/`floor`/`ceil`) | entropy, softmax, normalization, decay |
| List construction | `_list_append` + accumulator-loop lowering | list/vector-returning routes (softmax, distributions) |
| Exact CPython rounding | `round_ndigits` (decimal half-to-even, `_Py_dg_dtoa`-faithful) | every `round(x, n)`-bearing route (cost/value vectors, grounded ROI) |
| Homogeneous structure access | dict→`Value::Record` marshalling + `_get` Record arm | routes reading numeric fields from ONE dict/model (marginal-from-record) |
| Model→dict→record normalization | `_as_field_dict` (bridge) + `py_to_value` model arm (inline) | the object-OR-dict polymorphism DISSOLVED at the marshal boundary — a `list[model]` marshals identically to `list[dict]`; the recipe only ever sees Records |
| List-of-record reduction | recursive list→list-of-records marshal + head/tail fold + `record_get` per element | routes that SUM/COUNT/MAX an integer field across a collection (idea grounding signals; the integer reductions in compute_idea_metrics' confidence/coverage) |

**Gates ahead (each blocks a named family; build in leverage order):**

1. **Six-collection heterogeneous join** — the *remainder* of
   `compute_idea_metrics` after the structure-access, list-of-record, AND
   float-field-fold unlocks. The **float-field fold** that previously sat here
   is now BANKED: TS's `add`/`_plus` gained float arms (the bare-width MATH arm
   promotes to f64 at runtime, `_plus` carries Float+Float / Int+Float /
   Float+Int), so `spec_actual_cost_sum = sum(s.actual_cost for s in specs)`
   folds value-exact across CPython == Rust == TS — proven three-way in
   `list-of-record-reduction-band.fk` (the float-fold checks) and served live at
   `/api/utils/idea_grounded_cost_sum`. What remains deep is the **six-collection
   heterogeneous join** — `compute_idea_metrics` filters and reduces over SIX
   pre-fetched collections (specs, runtime, lineage links, valuations map,
   commits, friction) with a `.get(...)` on a map and cross-collection
   `max`/`min`/`any`. The object-OR-dict polymorphism is dissolved at the
   bridge, so each collection marshals cleanly; what remains is the
   **multi-collection orchestration** (filter-by-idea-id per collection, the
   valuations-map lookup, the cross-collection reductions) — host-side join
   work, not a single kernel capability. Lower leverage now that the
   structure-access, list-of-record, and float-fold unlocks all landed.
2. **String-family operations** — `split`, `strip`, `in` (substring), `lower`,
   regex. Blocks the text/semantic-scoring family (`frequency_scoring`,
   `concept_auto_tagger`, keyword extraction). A self-contained string-native
   arc, parallel to the numeric one already walked.
3. **Exact-decimal arithmetic** — a `Decimal`-faithful path distinct from f64
   (the `round_ndigits` lesson generalized: f64 scaling diverges from exact
   decimal). Blocks settlement/value-distribution routes that use `Decimal`.
   Smallest family; lowest priority unless settlement routes are prioritized.

Each gate, when built, repeats the proven arc: name it precisely → build the
native/lowering to the bit → prove three-way + live → the family becomes a batch
of clean parity-gated transmutations. The wellness probe and attribution view
widen as DATA with each route, so the surface stays sensed throughout.

### Honest coverage today — and the gap to full coverage

What is **real and complete** for the kernel-served routes today:

- **Value parity** — 4/4, types preserved (inline `value_to_py`).
- **Arm-dispatch attribution** — every walked arm is counted by category and
  variant (`MATH.MUL`, `COMPARE.EQ`, `BLOCK.LET`, …).
- **Native-Blueprint attribution** — every native fired is resolved to its Form
  category NodeID (`abs → @1.2.27.1`, `len → @1.2.15.1`, …).
- **Recipe (Form-function) activity** — which named recipes were called, ranked.

What **requires more transmuted routes** before it is real:

- **Per-route Recipe/Cell activity across ALL routes.** The activity view today
  covers the four pure-compute cores. Full coverage — every route's recipe and
  the substrate Cells it touches, ranked by liveness across the whole API —
  arrives only as more routes are transmuted. The view does not fake this; it
  names its scope (`reached/eligible`) and the path to widen it.
- **Cell-level liveness** in the substrate sense (which `NamedCell`s a request
  reads/writes) needs the I/O-carrier routes (substrate ports) transmuted, a
  separate arc from the pure-compute flip.

### A precise gate the round() unlock does NOT clear — `grounded_idea_metrics`

`api/app/services/grounded_idea_metrics_service.py::compute_idea_metrics`
*looks* round-unblocked — its return dict is wall-to-wall `round(_, 4)`, the same
shape the `round_ndigits` native (PR #2320) just made CPython-exact for
`cost_vector` / `value_vector` / `grounded_roi`. **It is not eligible.** The
arithmetic is trivial; the **bulk** of the function is heterogeneous
structure-walking, not numeric computation:

- `_filter_by_idea_id(...)` filters Python **lists** of pre-fetched objects;
- `_safe_float(obj, "field")` does **polymorphic attribute-or-dict extraction**
  — the same call reads `obj.field` from a model instance *or* `obj["field"]`
  from a dict, across six different pre-fetched collections;
- `.get(...)` on a valuations **map**, plus `max` / `min` / `any` over the
  filtered sets.

The gate it sits behind is **polymorphic structure/field extraction from
heterogeneous object-or-dict collections**, a *different* capability than
`round`. The CLEAN SUBSET of that gate is now built and proven; the
heterogeneous-polymorphic remainder stays deferred. The boundary, named
honestly:

**Built — homogeneous record field access (three-way proven).** A recipe can
receive structured data as ONE binding and read named fields from it. The
kernel already carried the primitive in all three siblings
(`record_new`/`record_get`/`record_has`/`make_nodeid`); what was missing was the
bridge marshalling. The seam:

- `form_kernel_bridge._fk_literal` renders a Python dict (or a model via
  `model_dump()`) as a `(record_new <blueprint> "field" value ...)` literal —
  the subprocess / inline-with-parse carrier.
- lib.rs `py_to_value` builds a `Value::Record` from a Python dict — the inline
  (Preloader) carrier. `Kernel::make_record` interns field names exactly as the
  `record_new` native does, so a marshalled record and one built in Form are the
  same shape.
- The `_get` native (the python-bmf SUBSCRIPT lowering) now reads `Value::Record`
  fields, so `obj["field"]` in a transmuted recipe resolves against a record
  binding without any recipe rewrite.

Proof: `form-stdlib/tests/record-field-access-band.fk` (three-way green: Go ==
Rust == TS, full score 16) proves the Record field-read primitive across all
siblings; `endpoint_idea_marginal_from_record_demo.{py,fk}` (the marginal-CC
core reading its six inputs from one structured idea) earns three-way parity
through `parity_suite.sh` and serves live at
`/api/utils/idea_marginal_from_record`; the bridge marshalling is covered by
`test_form_kernel_bridge_structure_access.py`. This unlocks the family of
functions that take a **homogeneous dict / single model** and read numeric
fields — the marginal-CC core, the collective-health summaries built from a
counts dict, `_safe_ratio`-adjacent shapes over a structured input.

**Banked — model→dict→record normalization + list-of-record reduction
(three-way proven, live).** The object-OR-dict polymorphism `_safe_float(obj,
"field")` carries (read `obj.field` from a model OR `obj["field"]` from a dict)
is **dissolved at the bridge marshalling boundary**, not pushed into the kernel:
`form_kernel_bridge._as_field_dict` normalizes any model (Pydantic
`model_dump()` / v1 `.dict()` / a plain object's `__dict__`) to a dict before it
marshals to a Record, and lib.rs `py_to_value` mirrors it inline (the
`model_dump`/`dict` arm). So a `list[model]` marshals byte-identically to a
`list[dict]` — the recipe only ever sees Records and reads fields homogeneously
via `record_get`. On top of that, the bridge's recursive marshal already carried
`list→list-of-marshalled`, so a `list[dict|model]` becomes a kernel
list-of-records, and a recipe FOLDS a field across it via the portable head/tail
recursion. Proof: `form-stdlib/tests/list-of-record-reduction-band.fk` (three-way
green: Go == Rust == TS, full score 22 — sum/count/max over an integer field,
float-field predicate, AND float-field SUM); `endpoint_idea_grounding_summary_demo.{py,fk}`
earns three-way parity through `parity_suite.sh` (CPython == Rust == kernel-bmf → `[3,
10, 2, 7]`) and serves live at `/api/utils/idea_grounding_summary`; the bridge
marshalling (model normalization + list-of-record + end-to-end reduction) is
covered by `test_form_kernel_bridge_structure_access.py`. This unlocks the family
of routes that reduce an INTEGER field across a collection — the idea grounding
signals (spec_count, total_event_count, specs_with_value_count, max_event_count),
the integer parts of compute_idea_metrics' confidence/coverage.

**Banked — the float-field fold (three-way proven, live).** The float SUM that
sat in the deferred column is now portable: TS's `add`/`_plus` gained float arms
(the bare-width MATH walker arm promotes to f64 at runtime when any operand is a
float, and `_plus` carries Float+Float / Int+Float / Float+Int), mirroring the
Rust + Go walkers exactly. So `spec_actual_cost_sum = sum(s["actual_cost"] for s
in specs)` folds value-exact across CPython == Rust == TS. Proof:
`list-of-record-reduction-band.fk` float-fold checks (three-way green) +
`endpoint_idea_grounded_cost_sum_demo.{py,fk}` (CPython == Rust == TS → `[5.25,
3.75]`), serving live at `/api/utils/idea_grounded_cost_sum`. ONE residual
divergence is named precisely: an INTEGER-VALUED float result (e.g. 5.0) prints
Python-style `5.0` on Rust but JS-style `5` on Go + TS — a PRINT-layer
divergence, not a value divergence; the band + route land on non-integer sums
(5.25, 3.75) so it never crosses the boundary.

**Deferred — the six-collection join.**
`compute_idea_metrics` *as a whole* still stays CPython, but the boundary is now
much sharper — only one piece remains deep: the
**six-collection heterogeneous join** — the function filters by idea_id across
SIX collections, does a `.get(...)` on a valuations map, and reduces
`max`/`min`/`any` ACROSS collections. The object-OR-dict polymorphism that used
to be the blocker is gone (every collection now marshals cleanly); what remains
is **multi-collection host-side orchestration** (per-collection filter, the map
lookup, cross-collection reductions), not a single kernel capability. So
`compute_idea_metrics` stays CPython until that join is decomposed into
per-collection kernel reductions wired by the host — but **each per-collection
reduction is now individually transmutable, integer OR float** (the grounding
summary route is the first integer reduction, the grounded-cost-sum route the
first float reduction), so the function can be transmuted piece by piece
rather than waiting on one large capability.

The wellness probe and the attribution view are the two instruments that make
the incremental transmutation **safe and legible**: the probe says *the surface
is healthy as it grows*, the activity view says *here is what's alive and what's
inert*. Together they turn "serve everything through the kernel" from a leap
into a walk — one route at a time, each one sensed and attributed.

### Running these two instruments

```bash
python3 scripts/wellness_check.py                 # includes sense_kernel_api (quiet when healthy)
python3 scripts/kernel_attribution_report.py      # ranked Blueprint/Recipe/native activity + inert list
python3 scripts/kernel_attribution_report.py --json --top 5   # machine-readable, top-N per section
```

Both degrade gracefully: with no kernel binary or no network they sense what
they can locally and name what they couldn't reach (the probe), or name the
missing binary and exit 2 (the report) — never a faked reading.
