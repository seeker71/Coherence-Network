# form-kernel-ts — vertical-slice host for Form-on-top, in TypeScript

Third sibling kernel beside [`form-kernel-go`](../form-kernel-go/) (920 lines) and
[`form-kernel-rust`](../form-kernel-rust/) (797 lines). Same surface, content-addressed
identity, conformance contract.

The TS kernel earns its place in exactly one role the Go and Rust kernels can't reach
without paying multi-megabyte WASM tax: **the browser**. ~1000 lines of TS minifies to
~30-50KB; Go-WASM minimum runtime is 2-5MB. For interactive client-side Form
evaluation (the FormPlayground, in-page editors, live inspectors), TS is the only
kernel that ships at a reasonable bundle size with full type integration.

Secondary surfaces: Node.js server-side (Next.js server components, route handlers),
React Native (mobile), edge runtimes (Cloudflare Workers, Vercel Edge). All native
targets for TS without cross-compile.

## What ships

**Full vertical-slice surface** — same 9 RBasic dispatch arms Go and Rust
implement (the Python kernel's 22 arms are its territory; vertical-slice
kernels carry the load-bearing ones):

- `NodeID` 4-tuple identity (pkg, level, type, inst)
- Content-addressed intern table (same shape ⇒ same NodeID)
- String table with NameID for fast identifier lookup
- Tagged `Value` union (null, int, str, bool, list, closure, nodeid)
- Walker with all 9 RBasic arms — `MATH`, `COMPARE`, `LOGIC`, `COND`
  (IF_THEN and IF_THEN_ELSE), `BLOCK` (DO/SEQUENCE/LET), `IDENT`, `FNDEF`,
  `FNCALL`, `LIST`
- Native primitives — `print`, `str_len`, `substring`, `char_at`,
  `str_concat`, `str_eq`, `int_to_str`, `str_to_int`, `ord`, `list`,
  `cons`, `head`, `tail`, `len`, `nth`, `empty`, `read_file`, substrate-
  write surface (`make_nodeid`, `intern_trivial_int`, `intern_trivial_string`,
  `intern_node`, `node_category`, `node_children`, `node_value`,
  `walk_recipe`), `trace`
- S-expression bootstrap reader with `buildVerb`-style name dispatch
  (matches Go/Rust exactly — `add`, `sub`, `mul`, `eq`, `le`, ... all
  intern to the same NodeIDs across kernels)
- **Recipe → JS compiler** — emits JS source from recipe trees, compiles
  via `new Function`, V8 JITs the result. Brings overhead from 100–500×
  native down to 1× for arithmetic recursion.
- **Shared conformance runner** — executes the same question-effect,
  builtins, infix, control-flow, and loop vectors as Python, Rust, and Go
  through `scripts/verify_kernel_conformance.py --kernel typescript`.

## Performance — bench numbers

Three of four canonical workloads at **1× native overhead** with the
compiled path. See
[`form-kernel-ts-comparison.md`](../form-kernel-ts-comparison.md) for the
full analysis.

| Workload | Native TS | Walker | walk-over | Compiled | comp-over |
|---|---|---|---|---|---|
| `fib(28)` | 1.97 ms | 590 ms | 300× | **2.25 ms** | **1×** |
| `fact(12)` | 31 ns | 14 µs | 454× | 377 ns | 12× |
| `sum(1000)` | 7.46 µs | 780 µs | 105× | **7.83 µs** | **1×** |
| `ackermann(3,6)` | 773 µs | 135 ms | 174× | **832 µs** | **1×** |

```sh
npx tsx src/main.ts --bench       # walker + compiled side-by-side
npx tsx src/main.ts --compiled "(do (defn fib (n) (if (le n 1) n (add (fib (sub n 1)) (fib (sub n 2))))) (fib 28))"
npx tsx src/conformance.ts ../../docs/coherence-substrate/kernel-conformance/form-loop-mutation.json
```

## What's still ripening

- Browser build target (currently Node.js / `tsx` only)
- Form-on-top stack from `experiments/form-stdlib/` running on TS
- Compiler LIST literal emission (currently walker-fallback)
- Compiler closure-over-outer-frame optimization (currently
  `frame.lookup` slow path)

## RBasic constants

Aligned with `api/app/services/substrate/category.py` and the Go/Rust kernels.
Cross-kernel NodeID agreement is the conformance contract; same input must produce
the same NodeIDs in every implementation.

## Usage

```sh
cd experiments/form-kernel-ts
npm install                                    # zero runtime deps; tsx for dev
npx tsx src/main.ts --expr "(+ 1 2)"           # → 3
npx tsx src/main.ts --expr "(if (< 1 2) 'yes' 'no')"   # → "yes"
npx tsx src/main.ts ../form-samples/fact.fk    # when stdlib loads, runs samples
npm run conformance -- ../../docs/coherence-substrate/kernel-conformance/agent-question-effects.json
```

## Lineage

This kernel is the third sibling in the conformance circle. The Python kernel
(`api/app/services/substrate/`) holds the body's DB-backed lattice. The Go and
Rust kernels prove portability — same NodeIDs regardless of host language, because
content-addressing is geometric. The TS kernel extends that circle into the
browser.

See [`docs/coherence-substrate/form-language.md`](../../docs/coherence-substrate/form-language.md)
for the language and [`experiments/form-kernel-comparison.md`](../form-kernel-comparison.md)
for the benchmark + optimization arc on Go and Rust.
