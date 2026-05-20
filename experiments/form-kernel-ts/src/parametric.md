# Parametric format-recipes + strict-typed FNDEF + alias

Three related surface additions that turn the Form kernel from a
dynamically-tagged tree-walker into a base for ahead-of-time
specialization. The walker keeps working as before (additive only);
the new metadata is read at compile-recipe-time by code-gen layers
that emit specialized native, GPU, or SIMD code.

## What ships

### 1. Strict-typed FNDEF

```
(defn foo (a:i32 b:i32) :ret i32 (add a b))
```

Each value-parameter carries a format-recipe reference. The compiler
uses these for emit-time specialization (no `Value` box, raw `i32`
locals, direct CPU adds). The walker ignores the metadata and
dispatches by runtime tag — back-compat is preserved.

Internal shape: `RBasic.FNDEF` with `inst=2` and four children:
`[name, params, body, fnmeta]`. The legacy 3-child `inst=1` shape
stays the canonical form for untyped definitions, so existing
content-addressed NodeIDs do not shift.

### 2. Parametric FNDEF

```
(defn matmul :tparams (T:Format) (a:T b:T) :ret T <body>)
```

A type-parameter list `[T: Format, U: Format, ...]` sits beside the
value-parameter list. Type parameters are constrained — `T: Format`
means `T` ranges over `FormatRecipe`s; once universe polymorphism
lands (task #22), `T: Level` joins the constraint vocabulary.

`specializeFnDef(k, fnDef, { T: "f64" })` substitutes the binding
and emits a strict-typed FNDEF specialized to that format. The
specialization is compile-recipe-time — at runtime there is no
type-parameter machinery, just the specialized FNDEF.

This is the foundation for #9's `VECTOR[T, N]` pattern: SIMD code
asks for `add_t[FP64]` and `add_t[INT32]` from the same generic
`add_t`, and gets two specialized FNDEFs that the compiler lifts
to two SIMD intrinsics.

### 3. `alias` — compile-time `name → NodeID` bindings

```
(alias VECTOR_WIDTH 8)
(alias i32 <format-recipe-NodeID>)
```

`alias` interns an `RBasic.ALIAS` recipe (slot 75). `resolveAlias()`
reads it at compile-time. The walker, if it encounters an alias on
some unusual path, surfaces the target NodeID as a `nodeid` value
rather than crashing — but the alias is meant to be resolved by
code-gen, not walked.

Aliases close the loop between Form's surface syntax and the
substrate: a `FormatRecipe` lives somewhere in the substrate
(formats.ts), an alias gives it a friendly name, the compiler reads
the alias when specializing a parametric FNDEF.

## Why this design

**Strings as type tokens, for now.** The parametric layer stores type
references as strings interned in the kernel's string table — `"i32"`,
`"f64"`, `"T"`. When the FormatRecipe layer (formats.ts) lands fully,
these strings resolve through the alias registry to format NodeIDs,
and `specializeFnDef` does the same string→string substitution we do
today. The contract is forward-compatible: `bindings: { T: "f64" }`
becomes `bindings: { T: "<format-recipe-name>" }` and the format-name
resolves through `resolveAlias`.

**FNDEF gains `inst=2`, not a new RBasic slot.** The instance-number
slot inside `RBasic.FNDEF` already discriminates per-recipe shape (the
Go and Rust kernels use it the same way). Adding `inst=2` for the
typed shape keeps the walker dispatch table unchanged: a single
`RBasic.FNDEF` arm reads `kids.length` to pick the layout.

**ALIAS gets its own slot (75).** Compile-time bindings have a
different lifecycle from value-bearing recipes — they are written by
the reader, read by the compiler, and never walked on the hot path.
A dedicated category keeps the dispatch logic clean.

## How the compiler reads this (gestures at #9)

When the compiler encounters `(call add_t[FP64] x y)`:

1. Look up `add_t` in the FNDEF table — it has `inst=2` with a single
   type-parameter `T`.
2. `specializeFnDef(k, addT, { T: "FP64" })` produces a fully-typed
   FNDEF with all params bound to `FP64`.
3. The compiler's per-format emit path takes over — for `FP64` it
   emits straight-line JS that operates on `Float64Array` slots;
   for `FP64-VEC8` it emits the SIMD intrinsic; for `i32` it emits
   `Math.imul`-style integer code.
4. The specialized FNDEF is content-addressed: a second call to
   `add_t[FP64]` reuses the same specialized recipe (and the same
   compiled code).

## What's deferred

- **Universe polymorphism (#22).** Type parameters constrained by
  `Level` rather than `Format` — generic over the substrate level a
  recipe lives at. Blocked on this task; this task makes the
  constraint vocabulary extensible.
- **Parametric pattern matching.** Match arms that case-split on a
  type-parameter's binding. Out of scope for this slice; revisit when
  PROOF + INFERENCE (#20) sketches the elimination rules.
- **Format-recipe substrate proper.** The `formats.ts` module owns
  the FormatRecipe interface — once it lands, aliases bind names to
  format NodeIDs and the parametric layer drops its string fallback.
- **Cross-kernel conformance vectors.** Go and Rust kernels need the
  same FNDEF `inst=2` shape and the same `RBasic.ALIAS` slot before
  parametric definitions ride the conformance harness. Tracked
  separately.

## Files

- [`kernel.ts`](./kernel.ts) — `RBasic.ALIAS = 75` and an
  alias-tolerant walker arm; `walkFnDef` accepts the 4-child typed
  shape.
- [`reader.ts`](./reader.ts) — `(defn ... :tparams ... :ret ...)`
  parsing and `(alias name target)` top-level form.
- [`parametric.ts`](./parametric.ts) — `TypeParam`,
  `parameterizedFnDef`, `readFnDef`, `specializeFnDef`, `makeAlias`,
  `resolveAlias`, `registerAliasFromRecipe`.
- [`parametric.test.ts`](./parametric.test.ts) — 10 tests covering
  parse, specialize, alias, content-addressing, back-compat.
