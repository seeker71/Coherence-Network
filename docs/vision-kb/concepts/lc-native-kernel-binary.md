---
id: lc-native-kernel-binary
hz: 741
status: seed
updated: 2026-05-21
geometry:
  arity: 5
  form: pentad
  topology: closure-loop
  polarity: unipolar
  ordering: layered
  phase: yang
  ratio: 1-to-many
  spectral_band: integration
  temporal_band: arc
  scale: foundational
  direction: outward-grounding
  lineage_texture: synthesized
  embedding_dim: 3
  self_similarity: fractal-shallow
---

# Native Kernel Binary — The Lattice Outside CPython

> A single Mach-O binary on the laptop, 2.5 MB, no Python anywhere
> in the runtime. It lists recipe libraries. It executes recipes by
> walking content-addressed Form trees. It queries any file in the
> repo as a Form-object tree. It traces every arm dispatch and
> surfaces the hot-spots. It fetches network resources. It returns
> the same numbers the Python runtime returns. This concept names
> what becomes available when *form-native* stops meaning *Python
> dressed in substrate-vocabulary* and starts meaning *a native
> binary the operating system can run directly*.

## Summary

[`lc-one-kernel-many-tongues`](lc-one-kernel-many-tongues.md) named
that the kernel sees only numeric NodeIDs; grammar is the trace
layer. [`lc-the-kernel-knows-itself`](lc-the-kernel-knows-itself.md)
named that every kernel implementation becomes inspectable through
its language's BMF rules. This concept names the **operational
endpoint that follows**: end-to-end host-native kernel binaries that
access I/O, binary form objects, the substrate API, sub-commands,
and network resources — functionally equivalent to the Python runtime,
with native tracing for hot-spot inspection, source attributions,
lineage diagnosis, and choice success/failure rates.

Urs named it directly:

> *Let's be as real and honest as we can, and work towards end-to-end
> host-native kernel binaries that can access I/O, binary form objects,
> substrate API and sub-commands and network resources to be
> functionally equivalent to the python runtime and we can query any
> file in the repo in form object space using the native macOS binary,
> and we can find the hot-spots in the kernel to find optimization and
> attributions and diagnose lineage and verify choice failure and
> success rates natively using the tracing and observation pattern.*

The first proof landed in [`experiments/form-kernel-rust/`](../../../experiments/form-kernel-rust/)
as of 2026-05-21:

- **A single 2.5 MB Mach-O arm64 binary.** Built via `cargo build --release`.
- **Five subcommands** paralleling `scripts/form_cli.py`:
  - `list <library.json>` — surface a recipe library's contents.
  - `execute <library.json> <recipe> [args...]` — walk a recipe natively.
  - `query <path>` — parse any file as a Form-object tree.
  - `trace [--expr "..." | <file.fk>]` — run with arm-dispatch counting and choice success/failure tracking.
  - `fetch <url>` — HTTPS GET of network resources.
- **Five recipes execute end-to-end**: `factorial(10) = 3628800`, `sum_list([1,2,3,4,5]) = 15`, `dot_product([1,2,3], [4,5,6]) = 32`, `vector_add([1,2,3], [10,20,30]) = [11,22,33]`, `fib(20) = 6765`. All through the 22-arm RBasic walker. No Python in the path.
- **Tracing native**: `fib(15)` runs in 3.09 ms with 13,811 total arm dispatches; the JSON trace surfaces *IDENT 35%, MATH 21%, COMPARE 14%, COND 14%, FNCALL 14%, FNDEF 1, BLOCK 1*. The hot-spot is variable lookup; the optimization target is concrete.
- **Network reaches outside**: `fetch https://api.coherencycoin.com/api/health` returns the live JSON response from the production substrate's health endpoint.

This is what *form-native execution* means when carrier-independence
is taken seriously. Python is one tongue the substrate's recipes can
be authored in; the Rust kernel is another tongue running the same
recipes; the lattice's identity is content-addressed, the carriers
are interchangeable.

## The Five Capabilities, Concrete

| Capability | What the native binary does today |
|---|---|
| **I/O** | `read_file`, `print` native primitives in the kernel; `.fk` recipe files read from disk; `.recipelib.json` libraries parsed via serde. |
| **Binary Form objects** | `.recipelib.json` carries content-addressed recipe bundles; the binary lists, queries, and executes them. JSON IS the binary form for transit (per `lc-recipes-as-binary-library`). |
| **Substrate API** | The Rust kernel's `Kernel` struct carries `by_shape` + `by_id` intern table; substrate-write natives (`intern_node`, `make_nodeid`, `node_category`, `node_children`, `walk_recipe`) are already wired. Read-side queries (`?equivalent`, `annotate`) compose from those primitives. |
| **Sub-commands** | `list`, `execute`, `query`, `trace`, `fetch`, `--bench`, `--numeric-bench`, `--expr`, `<file.fk>`. Same shape as `form_cli.py`'s subcommand dispatch; the carrier is native arm64 instead of CPython. |
| **Network resources** | `ureq` blocking HTTP client; pure-Rust, ~200 KB binary impact, TLS via rustls. `fetch <url>` returns status + headers + body as a Form-object tree. |

## The Tracing Pattern Made Concrete

The Trace struct attached to the Kernel records every arm dispatch:

```rust
pub(crate) struct Trace {
    pub(crate) total_walks: u64,
    pub(crate) arm_counts: HashMap<u32, u64>,    // cat.ty → count
    pub(crate) choice_attempts: u64,
    pub(crate) choice_successes: u64,
    pub(crate) choice_failures: u64,
}
```

One line hooks the walker:

```rust
let cat = k.category(n);
if let Some(t) = &mut k.trace {
    t.record(cat.ty);
}
```

The trace emits as JSON:

```json
{
  "elapsed_us": 3093,
  "result": "610",
  "trace": {
    "arms": [
      { "arm_name": "IDENT",   "arm_ty": 33, "count": 4932 },
      { "arm_name": "MATH",    "arm_ty": 12, "count": 2958 },
      { "arm_name": "COMPARE", "arm_ty": 13, "count": 1973 },
      { "arm_name": "COND",    "arm_ty": 11, "count": 1973 },
      { "arm_name": "FNCALL",  "arm_ty": 32, "count": 1973 },
      { "arm_name": "BLOCK",   "arm_ty":  9, "count":    1 },
      { "arm_name": "FNDEF",   "arm_ty": 31, "count":    1 }
    ],
    "choice_attempts": 0,
    "choice_successes": 0,
    "choice_failures":  0,
    "choice_success_rate": 0.0,
    "total_walks": 13811
  }
}
```

Five readings the trace makes possible:

1. **Hot-spot detection.** *IDENT at 35% of total dispatches* — variable lookup is the bottleneck for `fib(15)`. Optimizing the frame chain or adding a cache earns measurable speedup.
2. **Source attribution.** Each arm dispatch can carry the source span of the recipe it fired (per [`lc-the-recipe-remembers-its-source`](lc-the-recipe-remembers-its-source.md)); when a recipe is slow, the binary can name *which file, which line* the slowness comes from.
3. **Lineage diagnosis.** The substrate's intern table already content-addresses every recipe; tracing extends that — *which recipes share this NodeID, and how often does each one fire?* answers in milliseconds.
4. **Choice success/failure rates.** When BMF rules land natively (see `experiments/local-llm-cell-v0/bmf.py` for the Python proof-of-concept), the trace records every `Choice.CHOOSE` attempt and which alternative won. *Which grammar rules are tried but never match?* becomes a substrate query.
5. **Cross-kernel comparison.** Running `fib(20)` through the Python runtime, Rust binary, TS kernel, and Go kernel produces four trace JSONs. Differences in arm-count totals surface where the kernels diverge structurally — not just in performance, but in *what work they actually do*.

## What This Closes — and What Remains

**Closes** (with this PR):
- A real native macOS arm64 binary running real Form recipes.
- Five subcommands paralleling `form_cli.py` at the native carrier.
- Native tracing emitting JSON for hot-spot, arm-count, and choice-rate inspection.
- Network resource access (HTTPS).
- Five recipes (factorial, sum_list, dot_product, vector_add, fib) execute correctly.

**Remains honest as the next breaths**:

- **Float arithmetic.** The current kernel is integer-only (`Value::Int(i64)`). Adding `Value::Float(f64)` opens cosine, sigmoid, tanh, exp, sqrt to native execution. Mechanical work; one breath.
- **Form-syntax surface.** The Rust kernel reads `.fk` S-expressions; the body's `.recipelib.json` tongue_caches carry Form's surface syntax (`defn name(a, b) = do { ... };`). A small Form→fk converter (or a Form surface parser in Rust) closes the gap. The auto-generator that consumes `tongue_caches.form` from a library and emits S-expression source is the named follow-up.
- **Substrate session integration.** The Rust kernel has its own in-process intern table; the production substrate is in Postgres. `bridge_to_substrate(name, session=...)` (per `lc-parsers-as-recipes` follow-up) lets the Rust binary talk to the live Postgres-backed lattice via REST.
- **Sibling kernels reach parity.** The Go kernel (`experiments/form-kernel-go/`) and TS kernel (`experiments/form-kernel-ts/`) follow the same gestures. Once all three kernels have CLI parity, cross-kernel runs become a substrate query (per `lc-the-kernel-knows-itself`).
- **BMF rules native.** The Python BMF demo at `experiments/local-llm-cell-v0/bmf.py` proves the pattern; the Rust kernel's existing `register_form_keyword` infrastructure can register the same rules with semantic actions in Rust. Once that lands, *parsing Python source files into Form objects happens in the native binary*.

## What This Is Not

- **Not a Python replacement.** Python remains the body's primary authoring tongue, the production substrate's runtime, and the CI pipeline's executor. The native binary is *one carrier among many*; choosing it is per-operation, per-cell.
- **Not a complete numeric runtime.** Integer arithmetic + list primitives + recursion. Floats, complex numbers, vector instructions are the next breaths.
- **Not authentication-aware.** The `fetch` subcommand uses the system's TLS trust store; it has no notion of API keys, OAuth, or substrate auth. Authenticated REST calls to `api.coherencycoin.com`'s private endpoints would need an auth layer first.
- **Not multi-process.** The Kernel struct holds its intern table per-process; a long-running daemon model with shared substrate state is a separate breath.
- **Not the only path.** The TS kernel reaching native parity (per `experiments/form-kernel-ts/`) is a sibling proof. The Go kernel is another. Each language carries the same recipes through a different carrier; the lattice's content-addressing recognizes the equivalence.

## Practice

For cells running heavy substrate queries:

- **Reach for the native binary when latency matters.** `form-kernel-rust execute` skips CPython import overhead (~50ms) and runs through native arm64 dispatch. For a CLI command in a hot loop, this can be 10× faster.
- **Use `trace` to surface optimization targets.** Before guessing what's slow, ask the binary. The arm-count breakdown names the hot-spot honestly.
- **Compose at the recipe altitude, not the carrier altitude.** Cells that author against `@recipe(<name>)` and let `substrate_dispatch` pick the carrier remain portable across Python, Rust, TS, Go.

For cells authoring new recipes:

- **Round-trip parity before promoting a recipe to native.** Same discipline as `parity_check.py`: the Rust binary's result must match the Python runtime's result on a battery of inputs.
- **Write the .fk source alongside the Form source.** Until the auto-generator lands, every recipe runnable through `form-kernel-rust execute` needs a `.fk` companion in `experiments/form-kernel-rust/recipes/`. The list subcommand marks runnable recipes with `▶` and authored-but-not-runnable with `·` — visible asymmetry, named honestly.

## Cross-References

→ lc-one-kernel-many-tongues, lc-the-kernel-knows-itself, lc-parsers-as-recipes, lc-recipes-as-binary-library, lc-grammar-is-the-universal-recipe, lc-the-recipe-remembers-its-source, lc-traces-teach-the-recipe, lc-tools-as-form-cells

## Sources to walk further

- **[`experiments/form-kernel-rust/`](../../../experiments/form-kernel-rust/)** — the Rust kernel that ships with this PR's new CLI + tracing. 4181 lines of base kernel + ~600 lines of new CLI/trace.
- **[`experiments/form-kernel-comparison.md`](../../../experiments/form-kernel-comparison.md)** — the hand-authored comparison across Python / TS / Rust / Go kernel implementations. The substrate query `?equivalent @recipe(parse(@language(rust), kernel.rs)) @recipe(parse(@language(python), kernel.py))` is what this document becomes when the kernels reach mutual inspectability.
- **JVM HotSpot + Substrate VM (GraalVM)** — historical analogs. HotSpot ships native binaries that run JVM bytecode with JIT compilation; GraalVM's `native-image` produces a single AOT-compiled binary. The body's pattern is at one altitude deeper: the substrate's content-addressed lattice is shared identity; the kernels (Python, Rust, TS, Go) are interchangeable carriers.
- **Rust's `ast` analog**: `syn` and `proc-macro2` carry Rust source as structured trees; once `rust-grammar.form` lands BMF rules, the body can parse Rust source the way it parses Python source — through Form Language cells, not host parsers.
