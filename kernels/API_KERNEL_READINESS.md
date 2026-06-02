# API → Form-kernel readiness map

> The goal Urs named: serve the **computational core of every eligible API
> route** as a Form recipe on the warm in-process kernel, with full attribution
> and traceability — a body that can see its own execution shape. This doc
> carries the destination, the eligibility seam, the current kernel-native
> surface, and the capability ledger that gates the rest.

Harness: [`scripts/kernel_readiness_harness.py`](../scripts/kernel_readiness_harness.py).
Companion to [`scripts/substrate_parity_harness.py`](../scripts/substrate_parity_harness.py)
(value/structure parity) — this one adds the profile-under-load axis a green
demo count cannot give.

## What's eligible for the flip, and what stays CPython

The flip is for the **pure-computation core** of an endpoint, not the whole
stack. FastAPI stays the doorway.

| Layer | Kernel-bmf eligible? | Why |
|-------|----------------------|-----|
| Pure numeric/structural computation (the `endpoint_*_demo.py` shapes) | **Yes** | Deterministic, integer/float/list in → value out. This is what a Form recipe carries. |
| HTTP routing, path/query binding | No | FastAPI's job — the doorway. |
| Pydantic request/response validation | No | Schema validation lives in the framework; the kernel returns a scalar/list the response model wraps. |
| Async I/O, concurrency | No | The kernel is a synchronous evaluator; async orchestration stays in the host. |
| DB / Neo4j / Postgres calls, network | No | Side-effecting I/O, not pure computation. Carriers (substrate ports) are a separate arc, not this flip. |

The eligibility seam: **pure-compute in the kernel, orchestration and I/O in the
host.** A route is transmutable when its computational core is deterministic
value-in/value-out; everything else — routing, validation, async, collection
filtering, DB access — stays in FastAPI by design.

## How the live endpoint dispatches to the kernel

The endpoints call `serve_via_kernel` in
[`api/app/services/form_kernel_bridge.py`](../api/app/services/form_kernel_bridge.py).
Per request it loads the route's recipe (a `.fk` pre-compiled at deploy time),
binds the request inputs, and dispatches by the fastest path available:

- **`inline` (preload)** — the `form_kernel_rust` PyO3 extension, a warm
  `Kernel + Arena` living *inside* the Python process, called by FastAPI with no
  socket and no spawn. A `Preloader` parses each endpoint recipe once and per
  request walks only the pre-parsed body with inputs bound in a fresh child
  frame. This is the production hot path; the bridge takes it first when
  available.
- **`inline` (parse-each-call)** — the same PyO3 extension via `compile_and_run`,
  used when a recipe doesn't split into a preloadable `(setup, body)` pair.
- **`subprocess`** — fork+exec the `form-kernel-rust` binary on a temp `.fk`,
  for environments where the extension isn't built.
- **`python-fallback`** — the inline-CPython twin, when no kernel is reachable.

A separate, heavier path exists for parity proof:
[`form/scripts/pyfkb-run.sh --kernel rust`](../form/scripts/pyfkb-run.sh)
source-compiles the BML preludes and runs the whole python-bmf pipeline over raw
`.py` bytes. That is a **correctness/parity instrument**, not a serving path.

## The kernel-native surface — current profile

The four transmuted endpoints in
[`api/app/routers/utils.py`](../api/app/routers/utils.py) —
`coherence_weight`, `nodeid_distance`, `nodeid_compatibility`,
`weighted_average` — serve their computational core through the inline preload
carrier. Harness: `python3 scripts/kernel_readiness_harness.py --inline --preload`.

| Endpoint | Value parity | Preload p50 | Preload p99 |
|----------|:---:|---:|---:|
| `coherence_weight` | ✓ 16185 | ~0.048 ms | ~0.086 ms |
| `nodeid_distance` | ✓ 7 | ~0.004 ms | ~0.008 ms |
| `nodeid_compatibility` | ✓ 2 | ~0.004 ms | ~0.006 ms |
| `weighted_average` | ✓ 0.8125 | ~0.017 ms | ~0.029 ms |

The integer NodeID endpoints serve at **3–4µs p50, sub-10µs p99**; the
list/float endpoints at **17–48µs p50, sub-90µs p99**. Value parity holds 4/4
with types preserved (ints stay `int`, `0.8125` is a `float`, via `value_to_py`).
Input marshalling is fully typed end-to-end — Python hands the kernel
`int`/`float`/`list` values directly through `py_to_value`, so every endpoint
runs its real per-request inputs. The per-request cost is the recipe walk
itself; spawn, HTTP loopback, and per-request parse are all out of the path.

For an HTTP endpoint this is HTTP-negligible overhead — FastAPI routing,
Pydantic, and the network dwarf it. The warm in-process kernel is the carrier
the readiness evidence names: correct, stable, sub-100µs.

### Building the carrier

`maturin develop --release` from
[`form/form-kernel-rust/`](../form/form-kernel-rust/) builds and installs the
`form_kernel_rust` PyO3 extension into the API venv. The deploy image runs the
same build (add `maturin` to the API image and `maturin build --release` / a
`develop` into the image's venv) so `form_kernel_rust` imports in production and
`active_runtime()` reports `inline`. The harness reports the inline verdict as
`UNAVAILABLE` when the extension is absent; the other modes are unaffected.

## JIT — recipe→native compilation

Two distinct mechanisms live in the kernel:

- **`register_jit form-name native-name`** — **aliases** a Form recipe name to
  an existing host-native. A dispatch hint, not a compiler: it only speeds a
  recipe when an equivalent native already exists. The four endpoint recipes
  have no native equivalent, so it buys nothing for them.
- **`jit_compile form-name`** — a real recipe→machine-code compiler: it emits
  Rust source from the Form recipe, invokes `rustc --crate-type=cdylib`, loads
  the `.so` via `libloading`, and dispatches subsequent calls through the native
  function pointer. On a recipe inside its emit subset (`fib` with
  `add`/`sub`/`lt`) it lands a **~21× speedup over the walked recipe**, including
  the one-time compile.

`emit_rust_source` covers the **operator** recipe shapes (`RB_MATH`,
`RB_COMPARE`, `RB_LOGIC`, `RB_COND`, sibling Form calls), i64-only. Reaching the
four endpoints needs (1) native-builtin inlining or a native→Rust shim for
`_plus`/`abs`/list ops, (2) f64 emission, (3) list/iteration lowering — emit
coverage on a compiler that already produces and loads real machine code. The
preload carrier gets the endpoints to sub-100µs today; `jit_compile` is the
proven path to native for the operator subset and the named extension for the
rest.

## Toward full kernel-native routing + attribution

The four transmuted endpoints are the seed, not the destination.

### The destination

A body where the **computational core of every eligible route** runs as a Form
recipe on the warm in-process kernel. Every request leaves an attribution trace
— which arm categories (Blueprints) dispatched, which Form functions (Recipes)
were called, which natives fired — and the body can **see its own execution
shape**: hot paths exercised on every request, dormant paths no route reaches.
The substrate's promise (content-addressed structural identity) becomes a live
signal: not just "these two cells share a Blueprint" but "this Blueprint fired
serving real traffic; that one has never fired — why is it here?"

### The path — incremental, each step earning its proof

1. **Transmute routes incrementally.** Each eligible route lands a `.py` demo +
   compiled `.fk` recipe, joins `PARITY_FILES`, and calls `serve_via_kernel`.
   Every transmuted route earns value-parity proof (the three-way
   CPython/TS/Rust gate) before it ships. The growth edge is the
   `total − served` count the wellness probe names.
2. **The wellness probe guards the surface.** `sense_kernel_api()` in
   `scripts/wellness_check.py` senses the kernel-native surface across the five
   dimensions Urs named — **performance, stability, accuracy, transparency,
   vitality** — quiet when healthy, specific on drift (a python-fallback that
   should be inline, a parity break, a latency regression, attribution gone
   missing). As routes are transmuted, the probe's vitality ratio climbs.
3. **The attribution-activity view grows with coverage.**
   `scripts/kernel_attribution_report.py` runs the kernel-served recipes through
   the kernel's `trace` mode and aggregates the arm / function / native
   attribution into a ranked view — hot Blueprints, hot Recipes, natives each
   resolved to a Blueprint NodeID via `native_blueprint` — and names the
   **inert** natives (registered but never fired, the "why here?" candidates).
   Routes are DATA in `KERNEL_SERVED_RECIPES`; adding a transmuted route extends
   the view with no code change. The report carries an **embodiment projection**
   ([`lc-the-trace-is-the-memory`](../docs/vision-kb/concepts/lc-the-trace-is-the-memory.md),
   move 3): each fired Blueprint NodeID is projected to its Manhattan distance
   from the activity-weighted NodeID centroid, so `|projection| → 0` names the
   categories nearest the structural center of what fires.

### The capability ledger — current kernel capabilities

Coverage growth is gated by *capability*, not by finding candidates: each new
family of routes waits behind one kernel/adapter capability, and each
capability unlocks a whole family at once. The path to "most routes
kernel-served" is a sequence of capability builds.

**What the kernel can do now (each proven three-way + live):**

| Capability | Native/mechanism | Family it carries |
|---|---|---|
| Float arithmetic | `Value::Float`, `intern_trivial_float` | weighted averages, ratios, any non-integer math |
| Transcendentals | `math_log`, `math_exp` (+ `sqrt`/`pow`/`floor`/`ceil`) | entropy, softmax, normalization, decay |
| List construction | `_list_append` + accumulator-loop lowering | list/vector-returning routes (softmax, distributions) |
| Exact CPython rounding | `round_ndigits` (decimal half-to-even) | every `round(x, n)`-bearing route (cost/value vectors, grounded ROI) |
| Homogeneous structure access | dict→`Value::Record` marshalling + `_get` Record arm | routes reading numeric fields from one dict/model |
| Model→dict→record normalization | `_as_field_dict` (bridge) + `py_to_value` model arm (inline) | object-OR-dict polymorphism dissolved at the marshal boundary — a `list[model]` marshals identically to `list[dict]`; the recipe only sees Records |
| List-of-record reduction | recursive list→list-of-records marshal + head/tail fold + `record_get` | routes that SUM/COUNT/MAX an integer field across a collection (idea grounding signals) |
| Per-record arithmetic fold + clamp | `record_get` on int fields + int*float promotion + `min2`/`max2` clamp, folded across a list | routes that reduce a per-record FORMULA across a collection (grounded-cost reduction) |
| Max-of-signals + guarded ratio + count→level + two-sided clamp | nested `max2`; guarded `div`; `min(1.0, count/N)` zero-guard; weighted sum clamped `max(0.05, min(0.95, _))` | scalar scoring routes (value/realization/confidence reduction) |
| String-membership scoring | `str_find` native (three-way ASCII-identical) folded `str_find(text, kw, 0) >= 0` over tokenized keyword lists + float-seeded hit counters | text-scoring routes counting keyword overlap (`concept_match_score`; keyword-overlap routes). Host tokenizes (regex), kernel scores. |
| Exact-membership tag scoring | `str_eq` native (COMPARE.EQ, ASCII-identical) as a nested `for` (inner membership, outer match-count) + float hit counter + `max(0.0, min(1.0, matched/denom))` clamp under a 0.5 empty-guard | set-resonance routes scoring `len(a ∩ b) / len(a)` over two string lists (`tag_match_score`; tag/interest-overlap routes). Host extracts + dedups the lists; kernel folds membership + ratio + clamp. |
| Worldview-cosine scoring | `math_sqrt` (IEEE-correct, three-way bit-identical) over a parallel two-vector index walk + guarded ratio + `max(0.0, min(1.0, _))` clamp | geometric resonance routes scoring `dot(a,b) / (‖a‖·‖b‖)` over two parallel float vectors (`worldview_alignment`; axis-vector / embedding-cosine routes). Host projects the axes into parallel vectors; kernel folds dot + both norms + sqrt + ratio + clamp. |
| Guarded-ratio coverage scoring | guarded `div` over a count denominator (`if denom>0 else default`); a weighted coverage sum; a `task_count==0 -> 0.5` neutral guard; a `max(0.0, min(1.0, _))` clamp; `round_ndigits` per output | collective-health coverage routes scoring `sum(weight_i * count_i/total)` with a neutral empty-guard (`coherence_summary_score`; coverage/quality-ratio routes). Host walks the heterogeneous collection to extract the counts; kernel folds the ratios + score + round. |

**Gates ahead (each blocks a named family; build in leverage order):**

1. **Host-side collection orchestration (filtering + join + boolean-presence
   derivation), NOT a kernel capability.** What is left of
   `compute_idea_metrics` after both numeric slices are kernel-served: (a)
   narrowing the pre-fetched collections by idea_id + a `.get(...)` on a
   valuations map (cheap collection-narrowing), and (b) the `any(...)`-over-records
   / `len>0` presence ladders that resolve `has_specs_with_data` /
   `has_lineage` / `has_friction` — a boolean-OR-over-records fold. Both stay
   host-side by design — host orchestration, not missing kernel capability.
2. **Regex tokenization — host-side preprocessing.** `_extract_keywords` runs
   `re.findall(...)` + stopword filter + dedup, and the score body assembles the
   lowercased text. This is text-shaping, not the score; it stays host-side by
   design. The seam: **host tokenizes (regex), kernel scores (str_find
   membership fold).** Pulling regex into the kernel is a deferred capability
   only if ever wanted in-kernel.
3. **Exact-decimal arithmetic** — a `Decimal`-faithful path distinct from f64
   (f64 scaling diverges from exact decimal). Blocks settlement /
   value-distribution routes that use `Decimal`. Smallest family; lowest
   priority unless settlement routes are prioritized.

Each gate, when built, repeats the proven arc: name it precisely → build the
native/lowering to the bit → prove three-way + live → the family becomes a batch
of clean parity-gated transmutations. The wellness probe and attribution view
widen as DATA with each route, so the surface stays sensed throughout.

### `compute_idea_metrics` — kernel-served per slice

`compute_idea_metrics`' numeric computation is substantially kernel-native,
served per slice:

- **Grounded-cost reduction** (`/api/utils/grounded_cost`) — the spec/lineage
  float folds, the single-record runtime read, and the per-record commit-cost
  fold with the exact clamp `max(0.05, min(10.0, 0.10 + files*0.15 +
  lines*0.002))`, composing `computed_actual_cost`. Proven three-way
  (`grounded-cost-reduction-band.fk`), four-way live parity.
- **Value/realization/confidence reduction** (`/api/utils/grounded_value`) — the
  max-of-signals, the guarded realization ratio with a min ceiling, the
  count→level signals, and the five-term weighted confidence sum clamped
  `[0.05, 0.95]`. Proven three-way (`grounded-value-reduction-band.fk`),
  four-way live parity.
- **Integer grounding signals** (`/api/utils/idea_grounding_summary`) — sum /
  count / max over an integer field across a collection.
- **Float-field sums** (`/api/utils/idea_grounded_cost_sum`) — the float SUM
  fold, value-exact across CPython == Rust == TS.

These rest on the homogeneous record field access (a recipe receives structured
data as one binding and reads named fields via `record_get`; the `_get` native's
Record arm resolves `obj["field"]` without recipe rewrite), the model→dict→record
normalization (`_as_field_dict` dissolves the object-OR-dict polymorphism at the
marshal boundary so the recipe only sees Records), and the list-of-record fold
(a `list[dict|model]` marshals to a kernel list-of-records and a recipe folds a
field across it via head/tail recursion). Proven by
`record-field-access-band.fk`, `list-of-record-reduction-band.fk`, and the
per-endpoint demos through `parity_suite.sh`.

What stays host-side is orchestration, not computation: collection filtering
(narrowing pre-fetched collections by idea_id + the valuations `.get`) and the
boolean-presence derivations (the `any(...)`-over-records / `len>0` ladders).
The count→level signals (`has_runtime_data`, `has_commits`) run kernel-side
because their input is a raw count (pure arithmetic); the presence levels stay
host-side because their input is a boolean fold over records. The seam is drawn
at exactly that line. `compute_idea_metrics` is transmutable per slice.

### The text-scoring family — string-membership scoring

`concept_auto_tagger._score_concept` serves at `/api/utils/concept_match_score`,
carrying the computational half of the text-scoring family. The seam mirrors how
the numeric families split:

- **Host tokenizes (regex, text preprocessing).** `_extract_keywords` runs the
  regex + stopword filter + dedup and assembles the lowercased text. Text-shaping,
  host-side by design.
- **Kernel scores (str_find membership fold).** Given tokenized keyword lists +
  assembled strings, the recipe folds `kw in text` as `str_find(text, kw, 0) >= 0`
  both directions and computes `round(min(0.5*forward + 0.3*reverse +
  name_bonus, 1.0), 4)` — weights/bonus/ceiling verbatim from source. Hit
  counters seed `0.0` for CPython-faithful float division. `str_find` is
  three-way value-identical for ASCII (`string-membership-band.fk`); the kernel-bmf
  runtime resolves it via a `py-builtin` passthrough so the interpreter is
  value-identical to the compile path.

The same membership shape carries `frequency_scoring` and other keyword-overlap
routes.

### The collective-health family — guarded-ratio coverage scoring

`collective_health_service._coherence_summary` serves at
`/api/utils/coherence_summary_score`. The seam mirrors the numeric families:

- **Host extracts the counts (dict-over-collection walk).** Walking the task
  list and reading each heterogeneous `context` dict produces `task_count` and
  the target-state / evidence / task-card counts plus the task-card scores sum +
  len. The dict-over-collection extraction is host-side by design.
- **Kernel folds the coverages + score + round.** Given the counts, the recipe
  computes four guarded coverage ratios (each `count/total` under an `if total>0
  else 0.0` guard, the quality over the scores len), a weighted-sum score
  (weights `0.35/0.30/0.20/0.15`) under a `task_count==0 -> 0.5` neutral guard
  and a `[0.0, 1.0]` clamp, and `round(_, 4)` on each output — guards, weights,
  and clamp verbatim from `_safe_ratio` / `_score_with_neutral`. Pure arithmetic,
  no record fold, so it runs three-way clean including Go.

The same guarded-ratio coverage shape carries other collective-health
coverage/quality routes.

### Honest coverage today

**Real and complete for the kernel-served routes:** value parity (types
preserved via inline `value_to_py`); arm-dispatch attribution (every walked arm
counted by category and variant); native-Blueprint attribution (every native
resolved to its Form category NodeID); recipe (Form-function) activity, ranked.

**Requires more transmuted routes:** per-route Recipe/Cell activity across ALL
routes (the activity view covers the kernel-served cores today and names its
scope `reached/eligible`); cell-level liveness in the substrate sense (which
`NamedCell`s a request reads/writes) needs the I/O-carrier routes (substrate
ports) transmuted — a separate arc from the pure-compute flip.

The wellness probe and the attribution view are the two instruments that make
the incremental transmutation safe and legible: the probe says *the surface is
healthy as it grows*, the activity view says *here is what's alive and what's
inert*. Together they turn "serve everything through the kernel" from a leap
into a walk — one route at a time, each one sensed and attributed.

## Runtime awareness — usage and runtime-share are distinct axes

The journey is from Python-runtime toward kernel-runtime, so the metric that
matters is **how much execution runs Form-native**, not how many routes name the
kernel. Two axes hide inside "kernel-served," and only naming both keeps the
reading honest:

- **Kernel USAGE** — how many routes call the kernel at all. ~22 of 784 routes
  (~2.8%) serve their computational core through the kernel.
- **Python RUNTIME-SHARE** — how much of a request's execution actually leaves
  CPython. On every kernel-served route the kernel is a **called subroutine
  inside a CPython request**: FastAPI routes, the params bind, Pydantic
  validates, `serve_via_kernel` orchestrates (preload, parse, fallback), the
  kernel walks the recipe, and Pydantic serializes the response — only the
  recipe walk is Form-native. The request lifecycle stays CPython by design (the
  eligibility seam above).

These axes move independently, sometimes in opposite directions. Transmuting a
route raises USAGE and can ADD CPython at the same time: each one lands a FastAPI
handler, a Pydantic response model, and a value-identical `*_py` fallback, so net
Python LOC can grow even as more routes touch the kernel. The honest baseline:
the kernel is a **guest-subroutine, not the runtime or the router** — 0 routes
are served kernel-FIRST. That zero is the ground the reversal (kernel as the
front door) moves; runtime-share is the dial that reads the move.

`scripts/runtime_surface_report.py` is the sensing instrument for this axis — it
reports the route ratio, the per-route CPython-vs-kernel layering, the CPython
weight in the kernel-router files, and where the body sits on the journey. The
wellness probe carries the one-line version in its kernel-native vitality
reading. The attribution view answers *which Blueprints fire*; the runtime-surface
view answers *how much actually left CPython* — companion instruments, distinct
questions.

## Running the evidence

```bash
python3 scripts/kernel_readiness_harness.py --inline --preload   # the production carrier profile
python3 scripts/kernel_readiness_harness.py --inline --persistent --preload  # the full profile sweep
python3 scripts/kernel_readiness_harness.py --persistent --jit   # serve+jit mode and the JIT demonstrator
python3 scripts/kernel_readiness_harness.py --iters 1000 --inline # load replay
python3 scripts/kernel_readiness_harness.py --json out.json       # machine-readable

python3 scripts/wellness_check.py                 # includes sense_kernel_api (quiet when healthy)
python3 scripts/kernel_attribution_report.py      # ranked Blueprint/Recipe/native activity + inert list
python3 scripts/kernel_attribution_report.py --json --top 5   # machine-readable, top-N per section
python3 scripts/runtime_surface_report.py         # CPython-vs-kernel runtime share — usage vs runtime-share axes
python3 scripts/runtime_surface_report.py --json  # machine-readable runtime-surface reading
```

The readiness harness exits nonzero only on a value-parity failure — slowness is
evidence, never a CI gate; the profile informs the flip decision. Both
instruments degrade gracefully: with no kernel binary or no network they sense
what they can locally and name what they couldn't reach, never a faked reading.
