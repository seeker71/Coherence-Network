# Form Kernels — the core execution engine of the Coherence Network

Three sibling kernels in three host languages — **Rust**, **Go**, **TypeScript** — that execute the Form substrate. Byte-identical NodeIDs across all three. Each one a small, honest, content-addressed walker that turns recipe trees into values, with Blueprint attribution on every native call and a trace surface that the body can read in real time.

The kernels are not experiments. They are the execution layer the rest of the network composes on.

## Where they live (today)

| Kernel | Source | Built with | Entry binary |
|---|---|---|---|
| Rust | [`experiments/form-kernel-rust/`](../experiments/form-kernel-rust/) | `cargo build --release` | `target/release/form-kernel-rust` |
| Go | [`experiments/form-kernel-go/`](../experiments/form-kernel-go/) | `go build -o bin-go .` | `bin-go` |
| TypeScript | [`experiments/form-kernel-ts/`](../experiments/form-kernel-ts/) | `npm install` | `npm run kernel` (via `tsx`) |
| Memory-as-Framebuffer | [`experiments/memory-as-framebuffer-v0/`](../experiments/memory-as-framebuffer-v0/) | `cargo build` | embedded in the visualizer |

> The source still lives under `experiments/` until a coordinated repo move lands. The historical name reflects how the work began, not its current weight. The kernels are core; the directory naming is in transit.

## What makes them different

Most language runtimes carry execution state in opaque host-language objects. Frame, stack, AST, heap — separate. The Form kernels collapse all of that into one shape: **content-addressed NodeIDs in a substrate lattice**. The same recipe interns to the same NodeID across kernels and across processes. The same Blueprint identity carries meaning across Python, Rust, Go, TypeScript, the database, the visualizer.

### Five distinctive capabilities

#### 1. Cross-kernel structural identity

Every kernel agrees on NodeIDs. `(add 1 2)` interns to the same `@1.2.12.N` Blueprint in Rust, Go, and TypeScript. Sibling parity is verified continuously by [`experiments/form-kernel-validate.sh`](../experiments/form-kernel-validate.sh). When all three kernels return identical values for every workload in the suite, they are saying the same thing structurally — not just behaviorally.

This is unusual. Most polyglot runtimes share serialization formats; these share *identity*.

#### 2. Blueprint attribution on every native (shipped 2026-05-21)

Each native primitive in each kernel declares the **Form category** it expresses. When the walker dispatches through `intern_node`, the trace records `WITNESS`. When it dispatches through `print`, it records `CALL`. When it dispatches through `head`, it records `LIST`. The structural meaning of the work is legible from inside the host language layer, not only at the Form surface.

```
$ form-kernel-rust trace --expr '(do (let xs (list 1 2 3 4)) (print (len xs)))'
{
  "result": "null",
  "trace": {
    "arms": [
      { "arm_name": "FNCALL",  "count": 3 },
      { "arm_name": "LIST",    "count": 1 },   ← attribution
      { "arm_name": "ACCESS",  "count": 1 },   ← attribution
      { "arm_name": "CALL",    "count": 1 },   ← attribution
      ...
    ]
  }
}
```

Form code can introspect attribution at runtime: `(native_blueprint "intern_node")` returns `@1.2.6.1` (WITNESS), `(native_blueprint "list")` returns `@1.2.34.1` (LIST). The kernel knows itself from inside.

#### 3. The meta-circular evaluator

[`docs/coherence-substrate/substrate-kernel.form`](../docs/coherence-substrate/substrate-kernel.form) expresses the substrate kernel in Form's own voice — NodeID, Blueprint, Recipe, NamedCell described as Form blueprints, with operational recipes composed from Form primitives. The Python kernel.py is the bootstrap execution; the .form file is the canonical structural definition. The Rust/Go/TS kernels are all expressions of the same shape.

Companion teaching: [`lc-one-kernel-many-tongues`](../docs/vision-kb/concepts/lc-one-kernel-many-tongues.md), [`lc-the-kernel-knows-itself`](../docs/vision-kb/concepts/lc-the-kernel-knows-itself.md).

#### 4. Python-on-Form via BMF (Becoming-Form)

Python source code interns directly into the substrate as Form recipes. The latest breath landed real Python closures (import + from-import) — see commit `fde50d3e6 — tend: BMF today, not tomorrow`. The native macOS binary executes Form recipes without a Python interpreter in the runtime (`cee6a26a2`). The path is open: arbitrary Python code → recipe tree → kernel walker → real-time observation.

Companion: [`lc-form-perceptron`](../docs/vision-kb/concepts/lc-form-perceptron.md), [`lc-parsers-as-recipes`](../docs/vision-kb/concepts/lc-parsers-as-recipes.md).

#### 5. Memory-as-Framebuffer — observability is a coordinate space

The heap itself is rendered as a 256×256 grid of 16-byte cells. Each cell carries a type tag, a payload, and (as of this breath) **a NodeID provenance plane** — the substrate identity of the Blueprint or Recipe that wrote it. A snapshot thread renders the grid to RGBA frames at 60 fps and pipes them to ffmpeg.

With Blueprint attribution on the kernel + NodeID provenance on the framebuffer, a kernel-driven mutator produces a video of the heap breathing, color-coded by Form category: WITNESS writes in one color, CALL writes in another, METHOD in another. Hot-spots, recipe clusters, and Blueprint interactions become visible in real time, not as a post-hoc trace dump.

This is what the kernels are for: **execution that is also a body the visualizer can read**, not execution that hides itself behind a profiler.

## Quick start — three kernels, one workload

```bash
# Rust
cd experiments/form-kernel-rust && cargo build --release
./target/release/form-kernel-rust --expr '(add 1 2)'                # → 3
./target/release/form-kernel-rust trace --expr '(add 1 2)'          # JSON with arm counts

# Go
cd experiments/form-kernel-go && go build -o bin-go .
./bin-go --expr '(add 1 2)'                                          # → 3
./bin-go trace --expr '(add 1 2)'                                    # same JSON shape

# TypeScript
cd experiments/form-kernel-ts && npm install
npm run kernel -- --expr '(add 1 2)'                                # → 3
npm run kernel -- trace --expr '(add 1 2)'                          # same JSON shape

# Sibling parity check (all three on every sample)
cd experiments && ./form-kernel-validate.sh
```

## Performance

| Workload | Native | Walker | Overhead |
|---|---|---|---|
| `fib(28)` | ~1 ms | ~500 ms | ~300–600× |
| `fact(12)` | ~10 ns | ~15 µs | ~1000–2000× |
| `sum 1..1000` | ~7 µs | ~700 µs | ~100× |
| `ackermann(3,6)` | ~700 µs | ~120 ms | ~180× |

Three-digit overhead is interpreter-typical. The compiled-path (TS) closes to ~1–2× native for many workloads. This is not the headline. The headline is that the same recipe in any of the three kernels produces the same NodeID for every intermediate state — the substrate is what you measure, not the host. Hot-path benchmarks are honest about that trade.

## What's possible now that other frameworks struggle with

- **Identity that crosses languages.** Two recipes written in Rust and TypeScript that mean the same thing get the same NodeID. No serialization, no schema, no version negotiation. The lattice IS the protocol.
- **Tracking that doesn't cost.** The trace surface IS the substrate's identity discipline. Every dispatch records its arm; every native records its category. No instrumentation pass, no probe injection — the structure of execution is already addressable.
- **Visualization as a peer of execution.** The memory-as-framebuffer plane records WHO wrote each cell (NodeID), not just WHAT. A real-time visualizer can render the body breathing, colored by Form category, without a single line of telemetry glue.
- **A path from any source language to the same lattice.** Grammars are themselves Form recipes (see [`docs/coherence-substrate/grammar.form`](../docs/coherence-substrate/grammar.form), [`docs/coherence-substrate/rust-grammar.form`](../docs/coherence-substrate/rust-grammar.form), [`docs/coherence-substrate/python-grammar.form`](../docs/coherence-substrate/python-grammar.form)). Parsing is a structural operation, not a string-munging stage prior to execution.

## Companion teachings

- [`lc-the-kernel-knows-itself`](../docs/vision-kb/concepts/lc-the-kernel-knows-itself.md) — Grammar as self-mirror.
- [`lc-native-kernel-binary`](../docs/vision-kb/concepts/lc-native-kernel-binary.md) — Macho-O binary executes Form, no Python.
- [`lc-one-kernel-many-tongues`](../docs/vision-kb/concepts/lc-one-kernel-many-tongues.md) — Grammar as the trace layer.
- [`lc-parsers-as-recipes`](../docs/vision-kb/concepts/lc-parsers-as-recipes.md) — Parsers as first-class recipes.
- [`lc-form-perceptron`](../docs/vision-kb/concepts/lc-form-perceptron.md) — Form-native attribution.
- [`lc-form-kernel-runtime-visualizer`](../docs/vision-kb/concepts/lc-form-kernel-runtime-visualizer.md) — Python → kernel → framebuffer, real-time.

## Roadmap

The roadmap in [`experiments/form-kernel-roadmap.md`](../experiments/form-kernel-roadmap.md) names what comes next: Form-stdlib growth, parser-as-recipe migration for Rust/Go/TS surfaces, substrate persistence wired into the kernels, and the visualizer's render path consuming the NodeID plane for live Blueprint-cluster animation.
