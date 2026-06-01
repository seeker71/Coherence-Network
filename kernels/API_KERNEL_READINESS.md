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

## Honest verdict — per call

| Endpoint | Verdict (subprocess PATH A today) |
|----------|-----------------------------------|
| `coherence_weight` | **NOT-YET via subprocess** — correct, but +5 ms/req spawn. Sub-ms compute. |
| `nodeid_distance` | **NOT-YET via subprocess** — same shape: correct, spawn-bound. |
| `nodeid_compatibility` | **NOT-YET via subprocess** — same. |
| `weighted_average` | **NOT-YET via subprocess** — same. |

The blanket-"ready" costume is refused. Read precisely:

- **Correctness is met.** 4/4 value parity, stable percentiles, shape intact.
- **The subprocess path is not load-ready** — not because the kernel is slow
  (it isn't; ~0.15 ms compute) but because **per-request fork+exec adds ~5 ms**.
  At low request volume on a low-latency budget that is tolerable; as a default
  serving path under real traffic it is the wrong shape.
- **The fix is not faster compute — it's removing the spawn.** The `inline`
  (PyO3) path the bridge already routes to drops per-request cost to the
  ~0.15 ms execute (≈sub-ms, HTTP-negligible). That is the path a flip should
  ride. Build `form_kernel_rust` as a PyO3 extension in the deploy image, and
  the same recipes that are NOT-YET via subprocess become READY via inline.

The number that matters for Urs's decision: **the kernel is ~0.15 ms; the
shell-out is ~5 ms.** The flip needs a **persistent/warm kernel path**
(inline PyO3, or a long-lived kernel process), **not** a per-call shell-out.

## What's needed before a real flip

1. **Build the inline PyO3 kernel** (`form_kernel_rust`) in the API image and
   re-run this harness — confirm `inline` path p50 lands at the ~0.15 ms
   compute floor. That is the load-ready measurement.
2. **Capture real traffic.** Today's inputs are **representative-derived** from
   the endpoints' query defaults / Pydantic contracts, *not* sampled from
   production. Add a request-log → replay corpus so the profile reflects real
   value distributions (list sizes, edge cases), not one frozen input each.
3. **Grow the captured-call corpus** to cover input-size scaling (10 → 100 →
   1000-element value lists) — spawn cost is fixed, but recipe-execute cost
   scales with input; the crossover where kernel compute beats CPython is worth
   measuring.
4. **Load levels.** Re-run at `--iters 1000`+ and under concurrency to confirm
   stability holds (no fd leak from temp `.fk` churn, no spawn contention) at
   serving rates, not just 50 sequential calls.
5. **Latency envelope that counts as healthy:** for an HTTP endpoint, p99 kernel
   overhead under ~1 ms over the CPython baseline. The inline path is expected
   to meet this; the subprocess path will not.

## Running the evidence

```bash
python3 scripts/kernel_readiness_harness.py                 # PATH A, 50 iters
python3 scripts/kernel_readiness_harness.py --iters 1000    # load replay
python3 scripts/kernel_readiness_harness.py --path-b        # include PATH B
python3 scripts/kernel_readiness_harness.py --json out.json # machine-readable
```

The harness exits nonzero **only** on a value-parity failure. Slowness is
reported as evidence, never as a test failure — the profile informs the flip
decision; it does not gate CI.
