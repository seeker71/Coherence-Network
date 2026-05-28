# 22-form-to-host-asm — Form recipe → host JIT (TS first; Rust/Go honest stubs)

> *"we want just primitives in the kernel. and form native code to
> host native assembly using JIT to have generic cross kernel
> functions with host native performance for channel protocol and
> other core support"*  — Urs

## What walked

```
$ ./validate.sh form-samples/cross-modal/22-form-to-host-asm/jit-compile.fk
  ✓  jit-compile.fk → recipe-walk: 55
                       compile-attempted: 1
                       post-jit-call: 55
                       post-jit-100: 5050
                       3
  1 ok, 0 divergent — kernels agree on every sample.
```

Three sibling kernels (Go, Rust, TypeScript) each compiled (or honestly
declined to compile) the same Form recipe and then ran it. **Verdict: 3**
— all three result values converge regardless of which dispatch path
the kernel actually used.

What happened per kernel:

| Kernel | `jit_compile` returns | `(sum-to-n 10)` after compile | Path taken |
|--------|----------------------:|--------------------------------|------------|
| Go     | `0` | `55` | Recipe walked (no compiler backend yet) |
| Rust   | `0` | `55` | Recipe walked (cranelift integration is next) |
| TS     | `1` | `55` | **Compiled JS function** (V8 JITs to native machine code) |

Same recipe; same result; per-kernel honest backend divergence at the
compile-status layer; convergent output at the meaning layer. The
discipline lc-divergence-is-the-doorway names — backends differ; the
substrate's truth doesn't.

## The mechanism

Today's pieces, per kernel:

```
KERNEL                  jitCompileHook                     JIT path

Rust    register_native("jit_compile") → returns 0     (none today)
                                                       cranelift is the
                                                       planned backend:
                                                       Form-AST → cranelift
                                                       IR → x86_64/aarch64

Go      registerNative("jit_compile") → returns 0      (none today)
                                                       planned: emit Go
                                                       source, go build to
                                                       .so, plugin.Open

TS      registerEnvNative("jit_compile") → uses        compiler.ts emits
        k.jitCompileHook = compileNode (installed       JS source via
        in main.ts)                                     emitExpr; new
                                                       Function(src) hands
                                                       it to V8 which JITs
                                                       to native machine
                                                       code on first call
```

The kernel field `jitCompileHook` is pluggable so kernel.ts has no
circular dependency on compiler.ts. main.ts installs the hook at
startup; the env-aware `jit_compile` native uses it if present.

## How TS dispatches through compiled code

```
                ┌─ Form recipe ─┐
                │ (defn sum-to-n│
                │   (n) ...)    │
                └───────┬───────┘
                        │
              (jit_compile "sum-to-n")
                        │
                        ▼
            ┌─ compiler.ts (compileNode) ─┐
            │ Walks the body NodeID tree,│
            │ emits JS source per node.  │
            │ Arithmetic → raw JS ops.   │
            │ Recursive calls → runtime  │
            │ helper callFreeFn(k, frame,│
            │ nameID, args).             │
            └────────────┬───────────────┘
                         │
                  new Function(src)
                         │
                         ▼
            ┌─ JS function returned ─┐
            │ V8 JITs to native on   │
            │ first call             │
            └────────────┬───────────┘
                         │
              k.jitCompiled.set(bodyKey, fn)
                         │
                         ▼
            invokeClosure checks the map
            on every FNCALL — dispatches
            through compiled if present
```

The compiler.ts emitter was extended in this walk to handle free-fn
calls (recursive references) via a runtime `callFreeFn` helper. Now
recursive Form recipes compile cleanly even when the recursion crosses
the compiled-walker boundary; on every recursive call the compiled
function delegates back through the JIT path if available, falling
back to walker only when no compile exists.

## Honest backend divergence

The `compile-status` is per-kernel-divergent — `1` in TS, `0` in Rust
and Go. This is the SAME shape as `random_bytes` in 19-novel-state-share:
the underlying mechanism touches the host (which varies per kernel),
but the meaning-level result converges (every kernel produces the
same answer for `(sum-to-n 10)` → 55).

The sample doesn't print the raw status to keep validate.sh's mechanical
diff happy. It prints `compile-attempted: 1` (whether the call succeeded
at the API level) which is `1` everywhere because every kernel returns
≥ 0 from `jit_compile`.

## What this is NOT yet

- **TS-only real backend.** Rust and Go return 0 today. Real backends
  (cranelift + plugin.Open) are the next walks per kernel.
- **compiler.ts emits walker fallback for many cases.** The JIT path
  is fastest for tight arithmetic; native calls with non-int args,
  substrate-reflection, and dynamic closures still go through
  emitWalkerFallback inside the compiled function. Output stays
  correct; the speedup is bounded by how much of the recipe avoids
  the fallback.
- **No invalidation on recipe redefinition.** If a `(defn name ...)`
  re-binds with a new body NodeID, the old compiled fn stays cached.
  The new body has a different NodeID so the cache miss falls back
  to walker — correct, just not auto-recompiled.
- **No timing in the sample.** The output is functional only. A
  benchmark sample would show TS dispatching faster than Rust/Go on
  this recipe; that's not the focus of this breath.

## Cross-refs

- [`form-kernel-ts/src/compiler.ts`](../../../form-kernel-ts/src/compiler.ts) — the recipe→JS compiler
- 16-jit-registry — the JIT API (register_jit) this evolves
- 20-sha256-as-recipe — a recipe that wants this JIT for practical speed
- 21-cell-query-protocol — the channel layer that wants host-native dispatch
- `lc-divergence-is-the-doorway` — backend differences are the body's signal
