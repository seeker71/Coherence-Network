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

## What v0 ships

- `NodeID` 4-tuple identity (pkg, level, type, inst)
- Content-addressed intern table (same shape ⇒ same NodeID)
- String table with NameID for fast identifier lookup
- Tagged `Value` union (null, int, str, bool, list, closure, nodeid)
- Recipe walker covering the load-bearing RBasic arms:
  - `MATH` (+ - * / mod)
  - `COMPARE` (< <= > >= == !=)
  - `LOGIC` (and or not)
  - `COND` (if/then/else)
  - `BLOCK` (sequence, do)
  - `IDENT` (variable reference)
  - `FNDEF` / `FNCALL` (closures + recursion)
- S-expression bootstrap reader (`.fk` text → recipe tree)
- CLI entry: `tsx src/main.ts --expr "(+ 1 2)"` or `tsx src/main.ts file.fk`

## What's deferred to follow-up breaths

- Remaining RBasic arms (CHOICE, STATE, EXCEPTION, DELEGATE, REVERSE, COMMON,
  METHOD, REACTIVE, PROJECTION, TRY) — the 22-arm full surface that Go and Rust
  carry
- Native primitives beyond arithmetic — string ops, list ops, file I/O
- Conformance-harness alignment (`scripts/verify_kernel_conformance.py` invokes
  the kernel as a subprocess; the TS kernel needs the same protocol)
- Browser build target (currently Node.js / `tsx` only; the actual browser-bundle
  shape comes when the web starts using it)
- Form-on-top stack from `experiments/form-stdlib/` running on TS

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
