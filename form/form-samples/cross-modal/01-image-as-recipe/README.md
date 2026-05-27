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
