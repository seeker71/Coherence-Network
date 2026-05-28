# 33-go-jit — Form recipe → host-native Go via `go build -buildmode=plugin`

> *"we want just primitives in the kernel. and form native code to
> host native assembly using JIT to have generic cross kernel
> functions with host native performance for channel protocol and
> other core support"* — Urs

This walk lands the Go kernel's `jit_compile` backend. Sibling kernels:

| Kernel | `jit_compile` returns | Dispatch path | Mechanism |
|--------|----------------------:|---------------|-----------|
| Go     | **`1` (this walk)**   | Loaded plugin function | recipe → Go source → `go build -buildmode=plugin` → `plugin.Open` → `plugin.Lookup("Fn")` |
| Rust   | `0` (next walk)       | Recipe walked         | Cranelift integration is the planned shape: Form-AST → cranelift IR → x86_64/aarch64 |
| TS     | `1`                   | Compiled JS function  | `compileNode` emits JS via `new Function(src)`; V8 JITs to native machine code |

The recipe is canonical truth. Every kernel produces the same answer
regardless of which dispatch path it took — that's the sibling-parity
attestation.

## What walked

```
$ ./validate.sh form-samples/cross-modal/33-go-jit/go-jit.fk
  ✓  go-jit.fk → recipe-walk: 30
                  compile-attempted: 1
                  post-jit-call: 30
                  post-jit-10: 110
                  3
  1 ok, 0 divergent — kernels agree on every sample.
```

The Go kernel actually loaded a plugin and dispatched through it twice;
the trace verb confirms `jit-go-dispatch: 2`. The other two kernels
got to the same answer through their respective paths.

## The mechanism (Go side)

```
                ┌─ Form recipe ─┐
                │ (defn double-│
                │  and-sum (n)  │
                │  ...)         │
                └───────┬───────┘
                        │
              (jit_compile "double-and-sum")
                        │
                        ▼
            ┌─ jit.go: emitGoExpr ─┐
            │ Walks the body NodeID│
            │ tree, emits Go source│
            │ string per node:     │
            │ • add/sub/mul/div/mod│
            │   → int64 ops        │
            │ • eq/lt/le/gt/ge/ne  │
            │   → bool IIFE → int64│
            │ • if / if-else       │
            │   → ternary IIFE     │
            │ • let-bindings       │
            │   → fresh Go vars    │
            │ • param refs         │
            │   → p0, p1, ...      │
            │ • recursive self     │
            │   → fn_self(...)     │
            └────────────┬─────────┘
                         │
                  os.MkdirTemp +
                  os.WriteFile main.go,
                  os.WriteFile go.mod
                         │
                         ▼
        ┌─ exec.Command("go", "build",        ┐
        │   "-buildmode=plugin",              │
        │   "-o", "plugin.so", "main.go") ─── │
        └───────────────┬─────────────────────┘
                        │
                        ▼
            ┌─ plugin.Open(plugin.so) ─┐
            │ plugin.Lookup("Fn")     │
            │   → func([]int64) int64 │
            └────────────┬────────────┘
                         │
              k.jitCompiledGo[bodyKey] = fn
                         │
                         ▼
            FNCALL closure dispatch (in walk)
            checks the map on every call;
            marshals int64 args, calls fn,
            boxes int64 result back to VInt
```

The generated `main.go` for the `double-and-sum` sample looks like:

```go
package main

func fn_self(p0 int64) int64 {
    return (func() int64 {
        if ((func() int64 { if (p0 == 0) { return 1 }; return 0 }())) != 0 {
            return (0)
        }
        return (((p0 * 2) + fn_self(int64((p0 - 1)))))
    }())
}

func Fn(args []int64) int64 {
    if len(args) != 1 {
        panic("form-jit: arity mismatch")
    }
    return fn_self(args[0])
}
```

`fn_self` is the closure body lowered into Go; `Fn` is the exported
plugin entry point. Compare to TS's compiler.ts — same shape, different
host. Both compile-paths converge to the same int64 result.

## Plugin caching

The map key is the closure's body NodeID (canonical-form `"pkg.level.type.inst"`).
A second `(jit_compile "name")` on a recipe shape we've already lowered
hits the map and returns 1 without rebuilding.

This is the same content-addressing pattern the rest of the substrate
uses — two recipes with the same body shape resolve to the same .so,
even if their Form-level names differ.

## What this is NOT yet

- **int64-only signatures.** The plugin contract is `func([]int64) int64`.
  Closures whose body wants a float, string, or list result fall back to
  walker (the dispatch hook checks arg kinds and skips the JIT path if
  any arg isn't a VInt).
- **No native calls inside the compiled body.** The emitter only knows
  arithmetic, compare, cond, let, recursive self-call. Anything else
  raises `unsupported` during emission; the native returns 0 (honest
  fallback) and the recipe keeps walking.
- **No closure-over-outer-state.** Free identifiers that aren't params
  surface as `unsupported`. The walker, which threads frames through,
  handles those correctly.
- **Linux-only by Go-plugin design.** `plugin.Open` doesn't work on
  Windows; on macOS it has known cross-toolchain ABI restrictions. The
  honest answer on those platforms is `jit_compile → 0`, and the
  walker keeps the recipe alive.
- **No timing in the sample.** The output is functional only. A
  benchmark sample would surface the speedup; that's not the focus
  of this breath.

## Cross-refs

- [`form-kernel-go/jit.go`](../../../form-kernel-go/jit.go) — the recipe→Go emitter + plugin loader
- [`form-kernel-ts/src/compiler.ts`](../../../form-kernel-ts/src/compiler.ts) — sibling TS implementation
- [`22-form-to-host-asm`](../22-form-to-host-asm/) — the original JIT lattice sample (TS-only until this walk)
- [`16-jit-registry`](../16-jit-registry/) — the `register_jit` API the JIT path complements
- `lc-divergence-is-the-doorway` — per-kernel backend differences are the substrate's signal
- `lc-form-kernel-runtime-visualizer` — the Python → kernel → framebuffer arc
