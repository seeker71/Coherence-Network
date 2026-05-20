# Universe polymorphism in FNDEF (task #22)

## What this delivers

A surface for writing FNDEFs that are **generic over Level** — the
substrate's universe ladder (`TRIVIAL`, `BASIC`, `COMPLEX_1..7`). Where
task #8 introduced parametric formats (`T: Format`), this layer adds
parametric levels (`L: Level`). The author writes one function:

```text
defn id[L: Level] (x: Recipe[L]) -> Recipe[L] = x
```

…and gets specialized FNDEFs at every concrete level for free,
content-addressed and ready for the walker.

## Why it composes with what's already here

The substrate has always been level-aware — every `NodeID` carries a
level in its 4-tuple, and `Kernel.intern` propagates `category.level`
to the resulting node. What was missing was a surface for authors to
write one function generic over which level its recipe arguments live
at. Universe polymorphism is the smallest surface that lifts that
constraint without touching the walker.

The implementation is **additive**:

- The walker is untouched. Specialized FNDEFs are ordinary FNDEFs.
- The kernel's `Level` enum gained `COMPLEX_1..7` as named constants;
  the numeric values were already legal in NodeIDs.
- All new code lives in `universe.ts`. No other source file changed
  except for the additive enum extension in `kernel.ts`.

## The shape

`ParameterizedFnDef` is a small bundle:

```ts
interface ParameterizedFnDef {
  name: NameID;
  levelParams: readonly LevelParam[];   // <-- the new surface
  valueParams: readonly ValueParam[];   // <-- placeholder for #8
  fnDef: NodeID;                        // <-- ordinary FNDEF
}
```

`LevelParam` carries a name and a `LevelConstraint` — either `{ kind:
"any" }` or `{ kind: "oneOf"; levels: LevelValue[] }`. `ValueParam`
carries a name and an optional `levelBinding`, which is the seat
where #8's `Format` parameterization will land alongside this layer's
`Level` parameterization.

`parameterizedByLevel(k, name, levelParams, valueParams, body)` builds
the FNDEF NodeID (using the same three-child shape the walker expects)
and returns the bundle. The level params do not enter the FNDEF's
params-SEQUENCE — they live out-of-band on the bundle until
specialization rewrites them into the body.

`specializeByLevel(k, fn, bindings)` is a pure rewrite:

1. Check that every level-param in `fn.levelParams` is bound and that
   the binding respects the constraint (raises on violation).
2. Walk `fn.fnDef`'s body, replacing any IDENT reference to a
   bound level-param NameID with an int-trivial NodeID whose `inst` is
   the bound level value.
3. Re-intern the FNDEF with the rewritten body. Content-addressing
   means an identical specialization returns the same NodeID — the
   second call is free.

The resulting bundle has `levelParams: []` (fully specialized) and a
fresh `fnDef` NodeID that walks like any other FNDEF.

## Samples

`makeId`, `makeApply`, and `makeCompose` are the three canonical
combinators, lifted into universe-polymorphic form:

| Surface                          | Body                |
|----------------------------------|---------------------|
| `id[L] (x) = x`                  | `x`                 |
| `apply[L] (f, x) = (f x)`        | `(f x)`             |
| `compose[L] (f, g, x) = (f (g x))` | `(f (g x))`       |

In each case the level param is captured in the metadata; the body
makes no reference to `L` and so specialization is a structural no-op.
This is the right behavior — these combinators are *uniformly*
polymorphic over level. A function that does reference `L` (like the
`level_of` test in `universe.test.ts`) gets the level value baked
into its body as an int trivial at specialization time.

## What's still ahead

- Integration with #8's `parameterizedFnDef` once that lands — the
  `valueParams[*].levelBinding` field is the seat where #8's
  format binding will pair with this layer's level binding, producing
  the full `T: Format & L: Level` parameterization surface from the
  task spec.
- A surface-syntax extension to the bootstrap reader so
  `defn id[L: Level] (x) = x` parses straight into a
  `ParameterizedFnDef` without manual recipe construction. Today the
  three samples build their bodies via direct intern calls; that's
  fine for the kernel layer, but Form code at the top of the stack
  will want the syntactic ergonomics.
- Cross-kernel parity: replicate `LevelParam` + `specializeByLevel`
  in `form-kernel-go` and `form-kernel-rust` so the conformance circle
  agrees on the rewrite. Same content → same NodeIDs across all three
  kernels, just like every other piece of the substrate.

## Files

- `src/universe.ts` — the implementation
- `src/universe.test.ts` — 8 tests covering authoring, specialization,
  constraint enforcement, and content-addressing
- `src/kernel.ts` — added `COMPLEX_1..7` to the `Level` enum and the
  `LevelValue` type alias

## Running

```sh
cd experiments/form-kernel-ts
npm install
npm run check
npx tsx --test src/universe.test.ts
```
