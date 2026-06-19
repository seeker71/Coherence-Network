# Form Kernels — the core execution engine of the Coherence Network

Three sibling kernels in three host languages — **Rust**, **Go**, **TypeScript** — that execute the Form substrate. Byte-identical NodeIDs across all three. Each one a small, honest, content-addressed walker that turns recipe trees into values, with Blueprint attribution on every native call and a trace surface that the body can read in real time. There is no primary kernel; each host is a carrier for the same substrate semantics.

The kernels are the execution layer the rest of the network composes on. New
runtime and route work should be drawn here first: BML/domain grammar source,
Form recipes and cells, sibling-kernel realization, framebuffer observation.
Python references in kernel docs should name bridge/upstream behavior,
operational tooling, or historical evidence, not the destination architecture.

For production DB-backed kernel probes, read
[`docs/PRODUCTION-SUBSTRATE.md`](../docs/PRODUCTION-SUBSTRATE.md). Production is
Hostinger/VPS Docker Compose with internal Postgres; Railway and Supabase are
historical/stale for current DB reach. The Go BML `/api/ideas` route now reaches
production Postgres through the local kernel overlay and SSH tunnel and returns
`200` through the native Go carrier. Current attention is no longer credentials
or SQL projection; it is route-contract alignment (`query` is native-only today),
framebuffer/JIT compression, and list/string/JSON-native JIT coverage.

## Where they live

| Kernel | Source | Built with | Entry binary |
|---|---|---|---|
| Rust | [`form/form-kernel-rust/`](../form/form-kernel-rust/) | `cargo build --release` | `target/release/form-kernel-rust` |
| Go | [`form/form-kernel-go/`](../form/form-kernel-go/) | `go build -o bin-go .` | `bin-go` |
| TypeScript | [`form/form-kernel-ts/`](../form/form-kernel-ts/) | `npm install` | `npm run kernel` (via `tsx`) |
The `form/` tree is the stable runtime address.

## What makes them different

Most language runtimes carry execution state in opaque host-language objects. Frame, stack, AST, heap — separate. The Form kernels collapse all of that into one shape: **content-addressed NodeIDs in a substrate lattice**. The same recipe interns to the same NodeID across kernels and across processes. The same Blueprint identity carries meaning across Python, Rust, Go, TypeScript, the database, the visualizer.

### Five distinctive capabilities

#### 1. Cross-kernel structural identity

Every kernel agrees on NodeIDs. `(add 1 2)` interns to the same `@1.2.12.N` Blueprint in Rust, Go, and TypeScript. Sibling parity is verified continuously by [`form/validate.sh`](../form/validate.sh). When all three kernels return identical values for every workload in the suite, they are saying the same thing structurally — not just behaviorally.

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

#### 4. Host languages become Form via BMF/BML

Python source code already interns directly into the substrate as Form recipes;
that is one source-language proof, not the center. The latest breath landed real
Python closures (import + from-import) — see commit `fde50d3e6 — tend: BMF
today, not tomorrow`. The native macOS binary executes Form recipes without a
Python interpreter in the runtime (`cee6a26a2`). The path is open for every
useful source surface: domain grammar or legacy source → recipe tree → sibling
kernel walker → real-time observation.

The **emit direction** closed end-to-end on 2026-05-27: a Form recipe walks through `form/form-stdlib/emits/python-native.fk` and produces idiomatic native Python that CPython runs to the same values the Form kernel computes. See [`UNIVERSAL_TRANSLATOR_ROUNDTRIP.md`](UNIVERSAL_TRANSLATOR_ROUNDTRIP.md) for the proof-of-shape and the gap-map from "one recipe" to "the BMF compiler-compiler itself".

Companion: [`lc-form-perceptron`](../docs/vision-kb/concepts/lc-form-perceptron.md), [`lc-parsers-as-recipes`](../docs/vision-kb/concepts/lc-parsers-as-recipes.md).

#### 5. Memory-as-Framebuffer — observability is a coordinate space

The heap itself is rendered as a 256×256 grid of 16-byte cells. Each cell carries a type tag, a payload, and (as of this breath) **a NodeID provenance plane** — the substrate identity of the Blueprint or Recipe that wrote it. A snapshot thread renders the grid to RGBA frames at 60 fps and pipes them to ffmpeg.

With Blueprint attribution on the kernel + NodeID provenance on the framebuffer, a kernel-driven mutator produces a video of the heap breathing, color-coded by Form category: WITNESS writes in one color, CALL writes in another, METHOD in another. Hot-spots, recipe clusters, and Blueprint interactions become visible in real time, not as a post-hoc trace dump.

This is what the kernels are for: **execution that is also a body the visualizer can read**, not execution that hides itself behind a profiler.

## The kernels implement a named core spec (2026-06-10)

The kernel model derives from five agreed axioms — states (0/1/nothing), cell, content-addressing, boundary, offer — with everything else, safe self-update included, falling out as theorems ([`core-axioms.form`](../docs/coherence-substrate/core-axioms.form)). Two derived specs name the kernel's shape:

- [`host-kernel.form`](../docs/coherence-substrate/host-kernel.form) — the kernel realizes the axioms over a host's resources. Every resource is reached through a typed port the kernel offers (`resource-port.fk`); a NodeID is an unforgeable capability in seL4's sense; any host driver/OS API is an allowed carrier under allow-presence + measure-health; implementations are 0..many and the host-kernel cell chooses by measured fitness (`recognition-router.fk`, `champion-challenger.fk`).
- [`kernel-self-composition.form`](../docs/coherence-substrate/kernel-self-composition.form) — the kernel composed from just the five axioms, self-extending through its own native binary (`jit.go`) and the shared versioned persistent substrate (`persistence.fk`); versioning is free from content-addressing.

The runnable heart is proven three-way: `host-kernel-cell.fk` (hosts as measured, swappable carriers of one content-addressed body → 255), `kernel-satsang.fk` (self-describing parts, circle-witnessed swap, `.fkb` shrink/expand), and the metal band `form-stdlib/tests/host-kernel-metal-band.fk` (every organ and world-port that runs, touched in one program → 1023, also as a compiled `.fkb`; the Go arm emits a real ELF `.so` from the band's recipe). `scripts/cross_isa_assembly_audit.sh` shows one recipe as six instruction sets with value parity (x86-64, arm64, aarch64, Hexagon DSP, NVIDIA PTX, AMD GCN; SPIR-V validated), and `scripts/transformer_kernel_audit.sh` runs a full transformer block bit-exact across x86 + emulated Android CPU + emulated Hexagon DSP. On the model lane, the tensor JIT's matvec emitter is itself a Form recipe (`form-stdlib/jit-tensor-emit.fk` → 7, three-way): the emitted native loop folds exactly like the recipe, so native = recipe bit-for-bit — measured 20,077× on a whisper-large-sized fp64 matvec.

## Quick start — three kernels, one workload

```bash
# Rust
cd form/form-kernel-rust && cargo build --release
./target/release/form-kernel-rust --expr '(add 1 2)'                # → 3
./target/release/form-kernel-rust trace --expr '(add 1 2)'          # JSON with arm counts

# Go
cd ../form-kernel-go && go build -o bin-go .
./bin-go --expr '(add 1 2)'                                          # → 3
./bin-go trace --expr '(add 1 2)'                                    # same JSON shape

# TypeScript
cd ../form-kernel-ts && npm install
npm run kernel -- --expr '(add 1 2)'                                # → 3
npm run kernel -- trace --expr '(add 1 2)'                          # same JSON shape

# Sibling parity check (all three on every sample)
cd ..
./validate.sh
```

## Performance

| Workload | Native | Walker | Overhead |
|---|---|---|---|
| `fib(28)` | ~1 ms | ~500 ms | ~300–600× |
| `fact(12)` | ~10 ns | ~15 µs | ~1000–2000× |
| `sum 1..1000` | ~7 µs | ~700 µs | ~100× |
| `ackermann(3,6)` | ~700 µs | ~120 ms | ~180× |

Three-digit overhead is interpreter-typical. The compiled-path (TS) closes to ~1–2× native for many workloads. This is not the headline. The headline is that the same recipe in any of the three kernels produces the same NodeID for every intermediate state — the substrate is what you measure, not the host. Hot-path benchmarks are honest about that trade.

**A fourth carrier runs in the suite** — [`hati-os.form`](../docs/coherence-substrate/hati-os.form): a standalone native CLI whose every source byte is emitted by Form recipes (`form-stdlib/hati-os-native-cli-emit.fk`, proven three-way), measured by `scripts/hati_os_kernel_audit.sh` with value parity gating the rows. First rows (arm64 Darwin, full invocations): the Form-emitted native answers fib 28 in ~2 ms at 1.3 MB max RSS from a 33 KB binary; the walkers answer the same recursive recipe in 461–1696 ms at 53–139 MB from 4–21 MB carriers. fkwu has two faces, not one. As **proof-walker** (`fkc-emit-universal`) it IS `validate.sh`'s fourth arm: every band in [`form/fourth-arm-bands.txt`](../form/fourth-arm-bands.txt) flattens through `form-flatten.fk`'s multi-source door (`fourth-shim.fk` carrying core vocabulary and the string stones) and must answer the three walkers' own verdict byte-for-byte on every suite run — four-way agreement (Go=Rust=TS=fkwu). As **self-JIT** (`fkc-emit-jit2` / `fkc-walk-jit-text`) the SAME recipe crystallizes to native when a pure function runs hot and melts back to walking when it cools, re-earned champion-challenger — the gas-ice cycle closes both ways (`scripts/hati_os_kernel_audit.sh` §20/§21; `champion-challenger`→127). The walker stays authoritative for semantics; the crystallized form is native = recipe bit-for-bit. The native target is Form→asm **bytes**, not C: `jit-lower`(15)/`full-jit-lower`(63) → `form-lower`(31) → `form-asm`(31, arm64 bytes) → `form-macho`(31)/`form-elf`(31) → `recipe-dylib`(787349) → `codesign`(632490), every stage a Form recipe proven four-way. clang is dropped from the native path by `form-asm`'s `fa-conviction` byte-identity gate (`form/form-stdlib/form-asm.fk`); it survives only as an oracle (teacher, not master) and the bootstrap C-emit lane. fkc-nat-expr / jit-shape-table cover the pure-compute family (tags 1-7,12) today; impure ops (ports/organs/strings) stay walked, named — one generic mechanism, growing op coverage. The standing walls — the remaining node/substrate family, host io, higher-order calls — are named in the manifest header; the milestones still run toward a native BMF compiler and a native API host.

**Serving the API from the kernel** is a distinct, measured question — see [`API_KERNEL_READINESS.md`](API_KERNEL_READINESS.md). The recipe *executes* in ~0.15 ms (competitive); the readiness gap for the transmuted `/api/utils/*` endpoints is the per-request **process spawn** (~5 ms via subprocess), not compute. The evidence (value parity ✓ on all four, p50/p95/p99 under replay, the spawn-vs-compute split) says the flip needs a **persistent/inline (PyO3) kernel**, not a per-call shell-out. Run it: `python3 scripts/kernel_readiness_harness.py`.

**Reversing the topology** — making the kernel the request *front-door router* rather than a guest subroutine inside a CPython request — is designed and proven in [`KERNEL_AS_ROUTER.md`](KERNEL_AS_ROUTER.md). `form-kernel-rust serve` now has two live router modes: the compatibility host-router mode, which walks native Form handlers and fans unmatched paths out to FastAPI, and `serve --form`, which hands accepted streams to `kh-serve-conn` so Form owns parse, route, dispatch, render, send, and close for known native paths. This is not a Rust claim: the front door is a sibling-kernel contract, and the next proof moves through Go's socket ports, walker, `walk_parallel`, and a Go JIT plan/ABI layer. Go already proves i64 plugin dispatch; the HTTP hot path now needs observed f64/list/record plans, with compile-state and dispatch-state kept distinct. The production flip is the live front-door routing decision, named honestly as separate from the local proof. The **fourth kernel (fkwu) as accelerator** — Go owns the front door and live I/O while fkwu walks the pure slices, with the non-fourth tail on Go's existing JIT — rides the storage-port carrier the body already proves four-way: the primary move offloads a route's pure `shape_tree`+`json_emit` slice to fkwu (value-tree in, value out, no host call), and a deferred *host-bound carrier* seam carries the whole handler when wanted, capability-scoped through the injected carrier so the gap (a band reaching `pg_query_rows` without reaching every global native) is closed by construction. Scoped in [`FKWU_NATIVE_DISPATCH.md`](FKWU_NATIVE_DISPATCH.md).

## What's possible now that other frameworks struggle with

- **Identity that crosses languages.** Two recipes written in Rust and TypeScript that mean the same thing get the same NodeID. No serialization, no schema, no version negotiation. The lattice IS the protocol.
- **Branching by substrate lookup.** BML/Form `match` lowers to `MATCH.SWITCH`
  (`@1.2.19.1`) and dispatches literal scalar arms through cached
  `NodeID -> body` tables in Go, Rust, and TypeScript. The default arm is the
  identifier `_`, distinct from the string literal `"_"`.
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

The roadmap in [`form/kernel-roadmap.md`](../form/kernel-roadmap.md) names what comes next: Form-stdlib growth, parser-as-recipe migration for Rust/Go/TS surfaces, substrate persistence wired into the kernels, and the visualizer's render path consuming the NodeID plane for live Blueprint-cluster animation.

[`BOOTSTRAP_COMPOST_MANIFEST.md`](BOOTSTRAP_COMPOST_MANIFEST.md) names every file that composts when Form-native parsing proves three-way parity per demo. The Python parity suite now compares CPython, `kernel-bmf-compile` + Rust execution, and `kernel-bmf-run`; `make wellness` surfaces the remaining bootstrap weight each breath.

[`BMF_BML_COMPILER_PICTURE.md`](BMF_BML_COMPILER_PICTURE.md) names the modern BMF/BML compiler and compiler-compiler picture: legacy BMF/BML source hierarchy, compiler-compiler flow, shared compiler flow, language-port contract, the executable Form proof, the BML source body at [`form/form-stdlib/bml/bmf-bml-compiler-picture.bml`](../form/form-stdlib/bml/bmf-bml-compiler-picture.bml), the current source-lowering proofs that carry parsed BML declarations into `compiler-object` sections and execute a concrete BML-owned source lowerer, the `.fkb` bootstrap-image ratchet that keeps BML source authoritative while preserving a recoverable compiler image, and the first source-derived `BML-COMPILER-IMAGE` `.fkb` checkpoint.

[`UNIVERSAL_TRANSLATOR_AUDIT.md`](UNIVERSAL_TRANSLATOR_AUDIT.md) walks the body's current artifacts against the highest goal (universal translator across media, recipe orchestration in pure numeric space, less ice / more gas, minimize bootstrap surface). It names where the body is heavy in ice, heavy in bootstrap, heavy in dependencies, already light, and the top-ten concrete next breaths.

[`CTOR_UNIFICATION_PLAN.md`](CTOR_UNIFICATION_PLAN.md) names the closing shapes for the audit's finding #4 — *one Blueprint per shape across all source languages*. Three shapes (A: rules emit MATH directly; B: lift maps BINOP→MATH at recipe time; C: BINOP as Blueprint-view on MATH); Shape B is the smallest closing breath.

[`KERNEL_COMMON_GROUND.md`](KERNEL_COMMON_GROUND.md) names the shared primitive
substrate already visible across Go, Rust, and TypeScript: NodeID coordinates,
walk, witness trace, route-choice signatures, record/method object shape, and
the next low-risk move toward trace-preserving choice receipts.
