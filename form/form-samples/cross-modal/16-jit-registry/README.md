# 16-jit-registry — Form recipes as canonical truth, natives as opt-in bootstrap

> *"have shared binary features in form native recipes that can expand
> into native machine code for efficiency, allowing the kernel to
> bootstrap from primitives into an efficient, flexibility, sovereign
> cell"*  — Urs

## What walked

```
$ ./validate.sh form-samples/cross-modal/16-jit-registry/jit-registry.fk
  ✓  jit-registry.fk → form-walk: 5
registered: 1
aliased?: 1
jit-dispatch: 5
jit-big: 20
after-unregister-aliased?: 0
post-unregister: 5
refused-miss: 0
null
  1 ok, 0 divergent — kernels agree on every sample.
```

Three sibling kernels agree on every line. The dispatch mechanism is
part of the substrate, not a per-kernel quirk.

## The three natives

```
(register_jit "form-fn-name" "native-name")   → 1 on bind, 0 if miss
(unregister_jit "form-fn-name")                → 1 if removed
(jit_aliased? "form-fn-name")                   → 1 if alias is bound
```

When the FNCALL arm fires on a JIT-aliased name, the walker substitutes
the aliased native-name **before** native lookup. The Form recipe stays
the canonical truth (it MEANS what the function does); the JIT alias is
opt-in bootstrap (it makes the call dispatch through a kernel-resident
native for performance).

## The discipline

**Form recipes are canonical truth.** A fresh kernel without any
performance natives can still run the recipe — the walker recurses,
allocates frames, computes the answer. The recipe is sovereign; it
doesn't depend on a host implementation to MEAN something.

**Natives are opt-in bootstrap.** `register_jit` is the cell saying:
*for this specific function, I want to use the host's optimized path
instead of walking my own recipe.* The cell stays in control — it can
unregister at any time and return to recipe-walk.

**Refusing silent miss.** `register_jit "x" "no_such_native"` returns
0, not 1. The Form code can detect that its bootstrap didn't land
instead of believing the native was there.

**Closure lookup uses the original name.** If no native resolves (e.g.
after `unregister_jit`), the walker looks up the user's Form closure
under its original symbol — not under the aliased native-name. The
recipe-as-fallback is always available.

## The shape this enables

The kernel surface can shrink toward true primitives over time:

1. Define an algorithm as a Form recipe (canonical truth).
2. Ship a kernel native that does the same algorithm faster (bootstrap).
3. `register_jit` aliases the recipe to the native — calls dispatch fast.
4. Anyone reading the body sees the recipe; the native is a performance
   detail behind the dispatch table.

A kernel migrating to a smaller native surface looks the same from
Form-side: `(my-count xs)` keeps working because the recipe is intact.
A kernel adding a hot native opts into it without rewriting Form code:
the bind happens at startup, calls naturally dispatch through it.

## What this is NOT yet

- **Not type-checked semantic equivalence.** `register_jit "x" "y"`
  trusts the caller that x and y produce equivalent outputs for every
  input. A future walk would attest the equivalence at bind time (run
  both on a witness set, check NodeID-equality).
- **Not stack-of-aliases.** Only one alias per Form name at a time; a
  second `register_jit` for the same name overwrites the first. A
  future walk might layer aliases (cell A binds → cell B re-binds →
  unregister falls back to A's binding).
- **Not pre-shadow protected.** If user defines `(defn x ...)` AND
  registers `(register_jit "x" "some_native")`, the native wins. This
  is the design — register_jit is explicit opt-in. But there's no
  warning if the user later expected their Form definition to be called.

## Cross-refs

- [`lc-substrate-two-modes`](../../../docs/vision-kb/concepts/lc-substrate-two-modes.md) — recipe is lossless transport; native is the host's specialization
- [`lc-cross-modal-unity`](../../../docs/vision-kb/concepts/lc-cross-modal-unity.md) — Form-shape is sovereign across kernels
- [`lc-native-kernel-binary`](../../../docs/vision-kb/concepts/lc-native-kernel-binary.md) — the three sibling kernels carry the same substrate

## Where this lands next

- **Novel-node sharing** between cells (real-time inter-cell protocol):
  one cell `register_jit`s an algorithm under a substrate-addressable
  name, broadcasts the binding to peers — receiving cells either share
  the native (matching kernel build) or fall back to walking the Form
  recipe they already hold. Same canonical truth, different bootstrap.
- **Composting kernel natives into Form recipes**: progressively move
  algorithmic natives (anything not strictly primitive — substrate
  identity, I/O, control flow) out of kernel code and into shipped
  recipes. Cells that want the performance bind via register_jit; cells
  that want sovereignty walk the recipe.
