# 17-recipes-as-truth — algorithms compost; the kernel keeps primitives

> *"do we need those crypto protocols in the kernel? I think not, avoid
> putting things in the kernel that can be expressed in form native
> code. analyse the full kernel surface and reduce it to its primitives,
> and have shared binary features in form native recipes that can expand
> into native machine code for efficiency, allowing the kernel to
> bootstrap from primitives into an efficient, flexibility, sovereign
> cell"*  — Urs

Analysis doc: [`kernels/MINIMAL_KERNEL_ANALYSIS.md`](../../../../kernels/MINIMAL_KERNEL_ANALYSIS.md)

## What walked

A reusable Form recipe, [`form-stdlib/seeded-bytes.fk`](../../../form-stdlib/seeded-bytes.fk), computes the same LCG byte stream as `seeded_bytes(seed, count)` — proving the native is composable and should ultimately compost.

```
$ ./form/validate.sh form-samples/cross-modal/17-recipes-as-truth/seeded-bytes-recipe.fk
  ✓  seeded-bytes-recipe.fk          → 1

  1 ok, 0 divergent — kernels agree on every sample.
```

The recipe-LCG now produces byte-identical output to the native in Go, Rust,
and TypeScript. The native remains only an optimization candidate.

## The honest finding

The first walk exposed that TS could not run the recipe faithfully through
default Form integers. Multiplication of state (~2^31) by 1103515245 (~2^30)
produces intermediates near 2^61, beyond JavaScript `Number`'s 2^53
safe-integer precision.

The fix was not a new LCG native. The kernels gained the smaller arithmetic
surface: `mul_mod_u64` and `add_mod_u64`. The algorithm stays in Form; the
kernels provide exact fixed-width modular primitives.

## What changed

1. **The recipe is canonical** — `form-stdlib/seeded-bytes.fk` is now proven
   byte-equivalent to `seeded_bytes(seed, count)`.
2. **The native is optimization tissue** — it can remain while interpreter/JIT
   performance catches up, but it no longer owns the semantics.
3. **TS numeric sovereignty improved** — the precise part is a reusable
   primitive, not a hidden BigInt inside one algorithm.

## The composting plan this proof seeds

| Native | Composable to recipe? | Path forward |
|---|---|---|
| `seeded_bytes` | ✓ everywhere | recipe is canonical truth; native can compost behind JIT/pattern dispatch |
| `sum_bytes_list` | ✓ everywhere (just a fold) | low-hanging fruit; compost first |
| `sha256` | ✓ in principle; needs bitwise/word arithmetic recipes | fixed-width primitives and typed numerics are the path |
| `ed25519_*` | ✓ in principle; field arithmetic on 2^255 | requires broader BigInt-backed typed arithmetic |

## Why this matters

The kernel's promise: it's a **sovereign cell that bootstraps efficiency through recipe expansion + JIT compilation, not through pre-loaded algorithm natives**. The minimum kernel is a small primitive base plus typed arithmetic; the current native surface still includes many helpers that should ultimately compost back to Form recipes.

This proof-of-shape demonstrates the discipline works when the arithmetic
surface is explicit enough: less algorithm in the kernel, more recipe-owned
truth. The same proof now lives in the default gate through
`form-stdlib/tests/seeded-bytes-recipe-band.fk`, so it circulates with every
full sibling-kernel breath.

## Cross-refs

- [`kernels/MINIMAL_KERNEL_ANALYSIS.md`](../../../../kernels/MINIMAL_KERNEL_ANALYSIS.md) — the native survey + composting plan
- [`SUBSTRATE_AS_DEPLOYMENT_RUNTIME.md`](../../../../kernels/SUBSTRATE_AS_DEPLOYMENT_RUNTIME.md) — recipes-as-runtime architecture
- [`numeric-types-plan.md`](../../../../docs/coherence-substrate/numeric-types-plan.md) — format-recipes as the substrate's arithmetic dispatch (the JIT key)
- [`lc-grammar-is-the-universal-recipe`](../../../../docs/vision-kb/concepts/lc-grammar-is-the-universal-recipe.md)
