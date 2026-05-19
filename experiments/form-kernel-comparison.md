# form-kernel — Go vs Rust, three optimization breaths each

Two implementations of the smallest host that lets Form-on-top write the rest. Both ship: NodeID + content-addressed intern + recipe walker (22 RBasic arms) + frame/closure system + native primitives + S-expression bootstrap reader. Both read real `.fk` source files end-to-end.

This doc captures the optimization arc: idiomatic v0, three focused breaths each, what each breath cost and what it bought.

## End-state — all five samples, both kernels

```
closure.fk     → 15          fact.fk    → 3628800     fib.fk    → 6765
list-sum.fk    → 15          string-walk.fk → 5
```

Both produce identical results on every sample. Both stay under 1000 lines. Both are best-in-class idiomatic code — no `unsafe` in Rust, no `interface{}` boxing in Go, no hacks.

## Benchmark — kernel vs native, both languages

After three optimization breaths each. Each kernel also runs the same workload as a *native* compiled function (recursive, identical shape to the Form version, with opacity barriers to prevent constant-folding). The **overhead column** is `kernel / native` — what walking the recipe costs vs letting the compiler see the algorithm directly.

| Workload | Native Go | Kernel Go | Go overhead | Native Rust | Kernel Rust | Rust overhead |
|---|---|---|---|---|---|---|
| fib(28) | 1.40 ms | 240 ms | **171×** | 0.80 ms | 304 ms | **381×** |
| fact(12) | 16 ns | 3.9 µs | 245× | 11 ns | 5.7 µs | 522× |
| sum 1..1000 | 5.5 µs | 409 µs | 75× | 6.6 µs | 413 µs | 63× |
| ackermann(3,6) | 573 µs | 58 ms | 102× | 651 µs | 71 ms | 109× |

| | Go v0 | Go v3 | Rust v0 | Rust v3 |
|---|---|---|---|---|
| Source lines | 854 | 920 | 737 | 797 |
| Release binary | 2.6 MB | 2.6 MB | 535 KB | 517 KB |
| Baseline speedup | — | **1.70×** | — | **2.27×** |

**Three readings of the data:**

1. **Native is honestly competitive between languages.** Rust wins fib28 by 1.75×; Go wins sum1000 marginally; ackermann is a tie. The compilers are mature; the language choice barely matters at the native level for these recursive integer workloads.

2. **Kernel overhead is 60-500×.** That's the cost of "recipes as runtime data" vs "instructions the CPU recognizes directly." It's in the normal range for unoptimized tree-walking interpreters (Lua's interpreter is ~30×, Python's is ~50-100×, the V8 ignition tier is ~10× before JIT). Our kernels are slower than those but they're also under 1000 lines each with no JIT, no caching, no specialization.

3. **The Rust kernel pays *more* overhead than Go's**, despite (slightly) faster native code. Rust's safety mechanisms — even arena-based, even with `Rc<Closure>` — carry runtime cost that Go's GC + slice semantics + simple pointer chasing don't. The overhead ratio (381× vs 171× on fib28) tells the story: same algorithm, same compiler quality, but the kernel architecture in Rust pays a heavier per-step price.

**What 60-500× actually means.** For a substrate that processes maybe a few thousand recipes per second on a daily workload, 100× overhead is invisible. For a tight inner loop running a million times, it's two orders of magnitude. The kernel is the right floor for *describing* what the body does, not for hot inner loops — those should fall through to native primitives.

## The three breaths, breath-by-breath

### Rust

**Breath 1 — Slice returns, kill the per-walk clone.**
*Change:* `fn children(&self, n: NodeID) -> Vec<NodeID>` → `&[NodeID]`. Same for `ident_name() -> &str`.
*Numbers:* 693ms → 402ms on fib28 (1.7× alone).
*Friction:* 4 borrow-checker errors, ~5 min. The non-trivial one: `&k` + `&mut k` overlap in `defn` — fixed by collecting names eagerly into a `Vec<String>`.

**Breath 2 — `NameID` (u32) end-to-end.**
*Change:* `Frame: HashMap<String, _>` → `HashMap<NameID, _>`; identifier nodes carry `u32` `inst` directly; natives keyed by `NameID`.
*Numbers:* 402ms → 361ms on fib28 (1.1× alone).
*Friction:* Mostly mechanical (~10 min). The architectural insight: identifier *references* stay wrapped in an `Ident` composite, identifier *definitions* (in LET/FNDEF) become bare string trivials. The asymmetry is intentional: definitions name a slot, references read one.

**Breath 3 — Arena frames, kill `Rc<RefCell<Frame>>`.**
*Change:* Split `Kernel` (immutable substrate) from `Arena` (mutable frames). Closures hold `FrameId: u32`. Linear-scan bindings (`Vec<(NameID, Value)>`).
*Numbers:* 361ms → 306ms on fib28 (1.18× alone).
*Friction:* ~25 minutes — the real Rust conversation. **First attempt failed** by putting frames on the Kernel, forcing `&mut Kernel` through the walker, which forced re-cloning of children (undoing Breath 1!). Performance regressed to 497ms. The fix was architectural: split into Kernel + Arena so children can stay borrowed AND frames can stay mutable. The borrow checker forced a better architecture; the cost was 15 wasted minutes plus 10 to recover.

**Rust optimization arc:** 693ms → 402 → 361 → 306. The big win was Breath 1 (clones). The big *insight* was Breath 3 (architectural split).

### Go

**Breath 1+2 — `NameID` + linear-scan frames (combined).**
*Change:* `map[string]Value` → `[]binding` linear scan; `map[string]NativeFn` → `map[NameID]NativeFn`.
*Numbers:* 411ms → 300ms on fib28 (1.37× alone).
*Friction:* ~15 minutes — but almost all of it was a self-inflicted sed disaster. The pattern `s/^\t}$/\t})/` over-applied and turned every closing brace in the file into `})`. The compiler caught it immediately but recovery was tedious. **The optimization itself was frictionless** — type substitution, no ownership conversation.

**Breath 3 — One lookup per walk step.**
*Change:* Fold `category(n)` + `children(n)` (two map ops) into `recipeAt(n)` (one map op). Pre-size call frames to param arity.
*Numbers:* 300ms → 242ms on fib28 (1.24× alone).
*Friction:* ~5 minutes, 8 lines changed. Local, low-friction.

**Go optimization arc:** 411ms → 300 → 242. Each breath was small, additive, no architectural drama.

## What the friction shapes told me

The numbers are one story. The *shape of the friction* is another.

### Rust's friction is architectural

Three breaths produced three architecturally-distinct conversations:
1. **Lifetimes / borrowing** — "this borrow conflicts with that mutation"
2. **Type system** — "this NameID is what; that NameID is what"
3. **Ownership splits** — "Kernel reads, Arena writes; they need to be separate things"

Each conversation taught me something about the kernel's structure. After three breaths, the Rust code IS a better-described kernel — the type signatures document who-owns-what, who-mutates-what, when-is-this-valid. The borrow checker is documentation that the compiler enforces.

The cost: ~45 minutes total, with one major detour. The wrong path (Breath 3 first attempt) burned 15 minutes and produced a regression; the recovery was a real architectural insight that wouldn't have surfaced if the borrow checker had let me write the wrong code.

### Go's friction is operational

Three breaths produced almost no architectural conversation. The code was already pretty optimal in its idiomatic shape; the breaths were local refactors:
1. **Type swap** — `string → NameID` everywhere
2. **Data structure swap** — `map → linear-scan slice`
3. **Reduce lookups** — fold two map ops into one

The big friction event was a sed mistake, not a language conversation. Go's compiler didn't push back on anything I did. That's the gift: high velocity. That's the risk: the discipline lives entirely in human attention and tests.

### Both arrived at "best-in-class code we can be proud of"

Both files now read cleanly top-to-bottom: substrate → walker → frames → natives → bootstrap reader → main. Both have clear narratives. Both have intent-revealing names. Both stay under 1000 lines. Neither has dead code, comments-explaining-what, or premature abstraction.

The Rust file is 123 lines shorter. The Go file is faster.

## The honest read — keep both, use them as each other's witness

The "which to keep" question dissolved. **Both stay.** The kernels are written in different languages with different optimization choices and different bug profiles; their failure modes are unlikely to align. When both kernels agree on a Form program's output, that agreement is a far stronger correctness signal than either kernel alone. When they disagree, exactly one of three things is true:

1. The Go kernel has a bug
2. The Rust kernel has a bug
3. The Form spec has an undocumented corner

All three are findable. None of them are findable if only one implementation exists.

This is **differential testing built into the architecture, not bolted on**. The validation harness [`form-kernel-validate.sh`](form-kernel-validate.sh) is the gate. Every new `.fk` source file joins the diff. Every breath of Form-on-top (lexer, parser, stdlib, query, persistence) gets validated by both kernels simultaneously.

**The runtime difference becomes a feature, not a verdict.** Go is faster on most workloads; Rust is smaller and safer. When the kernel ships to edge cells via WASM, Rust is chosen automatically. When the kernel runs the daily substrate workload, Go is chosen automatically. The Python `api/` embedding picks whichever has the cleaner FFI story for the target.

The path forward lives in [`form-kernel-roadmap.md`](form-kernel-roadmap.md): seven breaths that walk **all of Form, written in Form, on top of both kernels**, with the validation gate green at every step. The pivotal one — Breath 2 — is **grammar as data**: a template registry (pattern + template primitives, the body's idiomatic shape from `form_rules.py`/`form_builders.py`/`self_host.py`) plus two engines (classic lex-then-parse + BMF-style streaming-emit) that both consult it. Same source × same registry × 2 engines × 2 kernels = **four implementations** of the same parse, cross-validated by content-addressing. Adding a new keyword becomes one Form file, picked up by all four implementations simultaneously. **The parser doesn't change when the grammar grows** — that's what self-hosting actually means.

## What's still ahead

After the choice is made:

1. **Form-surface-syntax parser written in Form.** Loaded by the S-expr bootstrap reader, then takes over. `defn fact(n) = if n <= 1 then 1 else n * fact(n-1)` → same recipes the bootstrap produces today.
2. **Query layer in Form** — `?equivalent`, `|>`, `?cells`. Pure Form code reading the substrate.
3. **Substrate persistence integration** — recipes round-trip through Postgres/Neo4j.
4. **Embed the kernel in `api/`** — PyO3 (Rust) or cgo (Go) replacing Python `form_runtime.py`.

## Run

```bash
# Both kernels accept the same .fk source files
./form-kernel-go      experiments/form-samples/fact.fk        # → 3628800
./form-kernel-rust    experiments/form-samples/fact.fk        # → 3628800

# Inline
./form-kernel-go   --expr "(add 2 (mul 3 4))"                 # → 14
./form-kernel-rust --expr "(add 2 (mul 3 4))"                 # → 14

# Benchmark
./form-kernel-go   --bench
./form-kernel-rust --bench
```
