# 34-rust-jit — Form recipe → Rust source → cdylib → libloading

> *"as it does for rust"* — Urs

## What walked

```
$ ./validate.sh form-samples/cross-modal/34-rust-jit/rust-jit.fk
  ✓  rust-jit.fk → baseline: 90
                   compile-attempted: 1
                   post-jit-10: 90
                   post-jit-50: 2450
                   3
  1 ok, 0 divergent — kernels agree on every sample.
```

Three sibling kernels each compiled (or honestly walked) the same
recursive Form recipe and produced the same answers.

| Kernel | `jit_compile` returns | Path taken |
|--------|----------------------:|------------|
| Rust   | `1` (rustc on PATH)   | **Compiled Rust cdylib** loaded via libloading, recursive calls stay inside the .so |
| TS     | `1` (compileNode hook)| Compiled JS function, V8 JITs to native on first call |
| Go     | `0` (no plugin path)  | Recipe walked (plugin.Open path is a sibling breath) |

Same recipe, same result, three different host-native toolchains — the
substrate's truth is one; the dispatch path is per-kernel.

## The Rust pipeline

```
                ┌─ Form recipe ─┐
                │ (defn d-and-s │
                │   (n) ...)    │
                └───────┬───────┘
                        │
              (jit_compile "double-and-sum")
                        │
                        ▼
            ┌─ emit_rust_source (in main.rs) ─┐
            │ Walks the body NodeID tree;     │
            │ emits a Rust source string with │
            │ each sibling defn as a regular  │
            │ `fn` and a C-ABI wrapper named  │
            │ `compiled_fn` whose params are  │
            │ i64 and whose return is i64.    │
            └────────────┬────────────────────┘
                         │
                  fs::write(lib.rs)
                         │
                         ▼
            Command::new("rustc")
              --crate-type=cdylib
              --edition=2021
              -C opt-level=2
              -o plugin.so lib.rs
                         │
                         ▼
            libloading::Library::new("plugin.so")
            library.get(b"compiled_fn") → fn ptr
                         │
                         ▼
            k.jit_compiled.insert(body_node_id, Arc<JitCompiled>)
                         │
                         ▼
            Every FNCALL whose closure body matches the
            stored NodeID dispatches through the loaded
            function pointer. Recursive calls inside the
            recipe stay inside the .so (we emitted them
            as direct Rust calls between sibling fns).
```

## What the Rust emitter handles

Tractable subset that covers most recursive arithmetic recipes:

- `add`, `sub`, `mul`, `div`, `mod` over i64 (using `wrapping_*` so the
  hot path doesn't panic on overflow — matches the walker's semantics)
- `eq`, `ne`, `lt`, `le`, `gt`, `ge` over i64
- `and`, `or`, `not` over bool
- `if` / `if-else`
- `let`-bindings inside `do` blocks
- Recursive free-function calls between sibling defns
- Parameter references, integer literals, boolean literals

The emitter walks the recipe tree once, collecting every reachable
`FNDEF` as a sibling. Each sibling becomes a regular Rust fn at the
top of the emitted crate; the target defn additionally gets a
`#[no_mangle] pub extern "C" fn compiled_fn(...)` wrapper so libloading
can resolve a single stable symbol regardless of which Form recipe it
is.

When the emitter encounters a node outside the subset (LIST, native
calls, substrate reflection, FLOAT64, strings) it returns `None`
upstream. `jit_compile` then returns `0` — honest "this recipe doesn't
fit the JIT path" — and the walker keeps running. Output stays
correct; the speedup is opportunistic.

## Library lifetime — why it's sound

`libloading::Symbol<F>` borrows the `Library` that produced it. The
moment the Library drops, the .so is dlclose'd and the function
pointer becomes a dangling reference. We sidestep this by extracting
the raw function pointer (`sym.into_raw()`) and storing it alongside
the Library in `JitCompiled`. The Library and the raw pointer share
the struct's lifetime; an `Arc<JitCompiled>` keeps both alive for
exactly as long as some caller might dispatch through the function.

`unsafe impl Send + Sync for JitCompiled` is sound here because the
loaded function is a pure i64-to-i64 transformer compiled with the
host's rustc — no shared mutable state, no threadlocals.

The temp dir (`/tmp/form-rust-jit-<pid>-<nonce>/`) holds `lib.rs` and
`plugin.so`. We sweep it in `JitCompiled::Drop`; on Linux removing
the .so file while libloading currently has it mapped is safe — the
kernel keeps the mapping until dlclose runs, and dlclose happens
immediately after our Drop returns (when the inner field drops).

## Honest failure modes

`jit_compile` returns `0` (not `-1`, not panic) when:

- `rustc` is not in PATH (`Command::new("rustc")` returns Err)
- The Form recipe contains nodes the emitter doesn't handle
- `rustc` returns non-zero exit (syntax error in generated code is a
  bug in the emitter; the kernel surfaces it as compile-failure not
  panic so the recipe keeps running)
- `libloading::Library::new` fails to load the .so
- The `compiled_fn` symbol is missing in the loaded library

In every case the walker handles the closure on the next call — Form
recipe stays canonical truth, kernel stays alive, sample's output
converges with TS and Go.

## What this is NOT yet

- **Linux/cdylib only.** macOS .dylib / Windows .dll would work with
  the same pipeline but the build flags would differ; not implemented.
- **i64 args only.** Floats, strings, lists, closures fall back to the
  walker even after a successful compile — the dispatch site checks
  every arg unboxes to i64 first.
- **No cross-process cache.** Every `jit_compile` shells out to `rustc`
  fresh; on a small recipe the compile takes ~200ms. A content-
  addressed cache keyed by the emitted source's hash would amortize
  this — a sibling breath.
- **No invalidation on recipe redefinition.** Re-binding the same name
  creates a new body NodeID; the old plugin stays in the map (cheap;
  only the new body matters for future calls).

## Cross-refs

- [`form-kernel-rust/src/main.rs`](../../../form-kernel-rust/src/main.rs)
  — `emit_rust_source`, `compile_rust_cdylib`, `jit_dispatch`,
  `JitCompiled`, and the FNCALL dispatch hook
- [`form-kernel-ts/src/compiler.ts`](../../../form-kernel-ts/src/compiler.ts)
  — the TypeScript sibling (recipe → JS via `new Function`)
- 22-form-to-host-asm — the original three-kernel shape this evolves
- 16-jit-registry — the JIT API (register_jit) the JIT path complements
- `lc-divergence-is-the-doorway` — per-kernel backend differences are
  honest signal, not error
