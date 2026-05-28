# 17-recipes-as-truth — algorithms compost; the kernel keeps primitives

> *"do we need those crypto protocols in the kernel? I think not, avoid
> putting things in the kernel that can be expressed in form native
> code. analyse the full kernel surface and reduce it to its primitives,
> and have shared binary features in form native recipes that can expand
> into native machine code for efficiency, allowing the kernel to
> bootstrap from primitives into an efficient, flexibility, sovereign
> cell"*  — Urs

Analysis doc: [`kernels/MINIMAL_KERNEL_ANALYSIS.md`](../../../kernels/MINIMAL_KERNEL_ANALYSIS.md)

## What walked

A Form recipe that computes the same LCG byte stream as `seeded_bytes(seed, count)` — proving the native is composable and should ultimately compost.

```
$ ./form/validate.sh form-samples/cross-modal/17-recipes-as-truth/seeded-bytes-recipe.fk
      go         = 1
      rust       = 1
      typescript = 0

  0 ok, 1 divergent
```

**Go and Rust:** the recipe-LCG produces byte-identical output to the native — the composting plan is sound where Form integers are 64-bit precise.

**TypeScript:** the recipe diverges from the native, exposing a real constraint.

## The honest finding

The TS kernel uses JavaScript `Number` (IEEE 754 float64) for Form integers. Multiplication of state (~2^31) by 1103515245 (~2^30) produces intermediates near 2^61, far beyond float64's 2^53 safe-integer precision. The native `seeded_bytes` papers over this by using `BigInt` internally; the Form recipe has no such protection.

**This is the architectural cost of composting algorithm natives to Form recipes:** Form's arithmetic primitives need to host 64-bit modular operations precisely. The TS kernel's int-as-float64 representation breaks this for crypto-style algorithms (LCG, SHA-256, Ed25519 — all involve large modular arithmetic).

## Three paths forward

1. **TS kernel adopts BigInt-backed Form integers** — slower but precise; sibling-parity holds across all three kernels for 64-bit modular work
2. **Form gets fixed-width modular-multiply primitives** (`mul_mod_u32`, `mul_mod_u64`) — kernel-native compiled, narrow surface, expressive for the algorithms that need them
3. **Algorithms reformulate to stay within 2^53** — narrow expressibility, but feasible for many uses

## The composting plan this proof seeds

| Native | Composable to recipe? | Path forward |
|---|---|---|
| `seeded_bytes` | ✓ in Go/Rust; ✗ in TS (precision) | wait for TS arithmetic fix; recipe is canonical truth |
| `sum_bytes_list` | ✓ everywhere (just a fold) | low-hanging fruit; compost first |
| `sha256` | ✓ in principle; same TS precision issue | wait for TS fix |
| `ed25519_*` | ✓ in principle; field arithmetic on 2^255 — TS needs BigInt always | requires TS arithmetic upgrade |

## Why this matters

The kernel's promise: it's a **sovereign cell that bootstraps efficiency through recipe expansion + JIT compilation, not through pre-loaded algorithm natives**. The minimum kernel is ~25 primitives; the current 88 natives include ~60 that should ultimately compost back to Form recipes.

This proof-of-shape demonstrates the discipline works WHERE THE ARITHMETIC ALLOWS. The TS finding names what stands between principle and full execution.

## Cross-refs

- [`kernels/MINIMAL_KERNEL_ANALYSIS.md`](../../../kernels/MINIMAL_KERNEL_ANALYSIS.md) — the full 88-native survey + composting plan
- [`SUBSTRATE_AS_DEPLOYMENT_RUNTIME.md`](../../../kernels/SUBSTRATE_AS_DEPLOYMENT_RUNTIME.md) — recipes-as-runtime architecture
- [`numeric-types-plan.md`](../../../docs/coherence-substrate/numeric-types-plan.md) — format-recipes as the substrate's arithmetic dispatch (the JIT key)
- [`lc-grammar-is-the-universal-recipe`](../../../docs/vision-kb/concepts/lc-grammar-is-the-universal-recipe.md)
