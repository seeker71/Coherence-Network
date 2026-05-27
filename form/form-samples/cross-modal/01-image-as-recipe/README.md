# 01 — Image as Recipe

**Discovery**: an image can be a Form recipe in its own right. The recipe is
human-readable; the image is derived. Because the kernel is deterministic and
content-addressed, the same recipe always produces the same bytes.

## Run

```bash
cd <repo-root>
go build -o /tmp/form-kernel-go ./form/form-kernel-go
/tmp/form-kernel-go form/form-samples/cross-modal/01-image-as-recipe/gradient-circles.fk
```

This emits `gradient-circles.svg` next to the recipe and prints the byte length
of the generated SVG.

## What's reachable today

- **Procedural image as a tree of Form recipes.** `svg-circle`, `svg-text`,
  `svg-defs`, `svg-bg`, `svg-document` are ordinary Form functions. The body
  composes them.
- **Determinism = content-addressing in practice.** Two runs produce
  byte-identical SVG (`sha256sum` matches). The recipe NodeID is the image's
  identity; the SVG bytes are one possible emission.
- **Tiny surface area.** Only `str_concat`, `int_to_str`, `write_file_text` are
  needed from the kernel. Everything else is composition.

## What surprised

The kernel's strictness on function arity caught a real bug in the first draft
(calling a 7-arg helper with 5 args). The error pointed at the exact call site.
Form's discipline isn't decoration — it's the same proprioception the substrate
gives to source files at the recipe altitude.

## What's not reachable today

- **No SVG → recipe roundtrip yet.** The `image-bmf.fk` grammar (under
  `form/form-stdlib/grammars/`) describes image *metadata* (format, width,
  height, frames) as Form objects, not pixel-or-vector-shape content. Parsing
  an arbitrary SVG back into the structural tree of circles/text would need
  an SVG-content grammar — a separate breath.
- **Raster output.** No PPM/PNG emission from Form today. The kernel has
  `write_file_bytes` but the recipe would need a much larger composition to
  produce valid PNG chunks. A small PPM (header + RGB bytes) is reachable; PNG
  needs zlib (not present as a native).

## The teaching

When the body says "image as recipe," it doesn't mean "render an image from
code" (every templating language does that). It means **the recipe is the
canonical form and the image is one emission**. Same recipe → same NodeID →
same bytes, every kernel, every host. The lineage that ties this to the body's
existing teaching: `lc-parsers-as-recipes`, `lc-the-kernel-knows-itself`.

## Generated artifact

[`gradient-circles.svg`](gradient-circles.svg) — 658 bytes, sha256
`86920289a88c175f4c8b7fcea66ae14600c0ec201a58fa227dae31af9e5cfac0`.

## Parameterized — same recipe, five outputs

The sibling recipe [`gradient-circles-seeded.fk`](gradient-circles-seeded.fk)
takes the same compositional shape and adds one input cell: an integer
**seed**. From that one cell, four visible dimensions of the image are
derived:

| derivation | formula |
|---|---|
| palette index   | `(mod seed 5)`            — selects one of 5 hand-picked color triples |
| circle count    | `3 + (mod (div seed 5) 4)` — 3..6 circles |
| circle radius   | `40 + (mod (div seed 7) 30)` — 40..69 px |
| y-baseline      | `120 + (mod (div seed 23) 60)` — vertical row offset |

Running the recipe with five seeds yields five visibly distinct SVGs that
all share the same enclosing document, the same gradient defs, the same
text-label shape. The structural prefix is shared; the divergent part is
exactly the seed-derived sub-tree.

| seed | palette         | count | radius | y   | bytes | sha256 |
|------|-----------------|-------|--------|-----|-------|--------|
| 5    | clay/sage/dusk  | 4     | 40     | 120 | 670   | `4ea82ca835100c7c6e25437dfe76db9ac6ffee15657ad1b6d70bc13e1c82df1e` |
| 17   | rose/berry/violet | 6   | 42     | 120 | 774   | `e148d2b9289a22d0ce845ff297c2462d5e544f188996553207a73cd81c38fd4b` |
| 86   | gold/saddle/slate | 4   | 52     | 123 | 671   | `6ca82307da089588ab942932a391e0364e16caf3b652082935483a8c7334b655` |
| 138  | mint/aqua/sea     | 6   | 59     | 126 | 775   | `2718828b32b3bd602542930a155a14562fdc01d95fe535b87eb3b89d9778d241` |
| 254  | sun/ember/brick   | 5   | 46     | 131 | 724   | `6ed1434f29460c971c08805240da4fa1c0b0a43d27d76912276f3a732475daa1` |

Total emitted: 3614 bytes across the five files. Three-way verified —
Go, Rust, and TypeScript kernels produce byte-identical SVGs for every
seed.

### The structural claim

The recipe `(gen-circles seed)` is one function. Every invocation walks
the same Form tree: `svg-document → svg-defs + svg-bg + circle-row + svg-text`.
The only cell that differs across the five invocations is the integer
literal passed as `seed`. Everything downstream — palette lookup, count,
radius, y-base, label text — is *derived* from that single cell through
pure integer arithmetic and table lookup.

This is what *the recipe IS the parameter space* means in practice:

- **One Blueprint for the recipe.** `gen-circles` has one structural identity.
- **One Blueprint per output.** Each emission's Blueprint differs from the
  recipe's only by the bound value of `seed` and the values its arithmetic
  produces. The shape — `svg → defs + bg + row + text` — is identical.
- **Content-addressing scales to families.** Two artifacts share lineage
  via their recipe + seed pair, not via byte-level overlap. The five SVGs
  have five distinct SHAs, but they share one structural ancestor.

The substrate would surface this by interning `gen-circles` once and the
five `(gen-circles N)` call sites as five sibling Recipes with shared
parent. The deep proof — running `04-universal-diff` over two of these
SVGs and showing the diff highlights *only* the parameter cell, not the
hundreds of byte-positions that moved — is forward-map walk #7 (image
structural diff). This walk lays the parameter space; #7 will measure it.

### Generated artifacts

- [`gen-circles-5.svg`](gen-circles-5.svg)   — palette 0, 4 circles
- [`gen-circles-17.svg`](gen-circles-17.svg) — palette 2, 6 circles
- [`gen-circles-86.svg`](gen-circles-86.svg) — palette 1, 4 circles
- [`gen-circles-138.svg`](gen-circles-138.svg) — palette 3, 6 circles
- [`gen-circles-254.svg`](gen-circles-254.svg) — palette 4, 5 circles
