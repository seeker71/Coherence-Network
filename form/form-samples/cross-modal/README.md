# Cross-Modal Recipe Experiments

Five small demos exploring how Form recipes carry semantic content across
modalities (text, structured data, image, code, natural language). Each
subdirectory has its own runnable sample and a README documenting what's
reachable today, what surprised, and what's not yet reachable. **The point
isn't to ship a universal translator** — it's to feel the body's current
surface area for cross-modality and name the honest discoveries.

| # | Experiment | One-line finding |
|---|---|---|
| 01 | [Image as recipe](01-image-as-recipe/) | A procedural SVG written as Form recipes; same recipe → identical SVG bytes by SHA256. |
| 02 | [Cross-language content-addressing](02-cross-language-content-addressing/) | Two recursive trees built by different author-routes intern to the **same** NodeID; iterative shape interns to a different one. |
| 03 | [Recipe as compression](03-recipe-as-compression/) | The substrate's "ice" (`.fkb`) is **4.17× larger** than the "water" (`.fk` text) at small payload sizes. Compression isn't automatic. |
| 04 | [Universal diff](04-universal-diff/) | Structural diff of two algorithms surfaces "the predicate is the same; the accumulation strategy diverges" — text diff can't see this. |
| 05 | [NL to recipe](05-nl-to-recipe/) | A 4-rule English grammar parses sentences into arithmetic recipes; NL `the square of 7` interns to the **same NodeID** as hand-built `(mul 7 7)`. |

## What every experiment shares

- **A `.fk` recipe that actually runs** through the Go kernel (`go build -o /tmp/form-kernel-go ./form/form-kernel-go`).
- **A `README.md`** naming the discovery, what's reachable today, what
  surprised, and what's not reachable.
- **Honest separations** — failures are documented in the body of the README,
  not hidden.

## Running everything

```bash
go build -o /tmp/form-kernel-go ./form/form-kernel-go
for d in form/form-samples/cross-modal/*/; do
    f="$d"*.fk
    for r in $f; do
        echo "=== $r ==="
        /tmp/form-kernel-go "$r"
    done
done
```

## What the four together teach

The body's surface area for cross-modality is **smaller than the marketing
slogan and larger than the engineering reflex**.

- **Smaller**: a Form recipe doesn't automatically become a Python file, an
  audio sample, or a compressed payload. The grammars
  ([`form/form-stdlib/grammars/`](../../form-stdlib/grammars/)) name the
  endpoints; the wiring between source-text and recipe-tree for non-Form
  tongues is incomplete. End-to-end parsing of arbitrary Python or
  TypeScript through `python-bmf.fk` / `typescript-bmf.fk` into substrate
  NodeIDs is reachable in principle and not turnkey today.
- **Larger**: the core property — content-addressed structural identity across
  trees built by different routes — is *already real* in the kernel today.
  Experiments 02 and 04 show it directly. The same property extends to any
  surface tongue whose grammar lands as a Form recipe. The substrate is the
  universal translator; the tongues are dictionaries pointing at it.

The honest gap: at small scale, the ice is bigger than the water (experiment
03). The compression intuition only pays off at scale, and only when many
recipes share sub-trees. This is structural sharing, not byte-level
compression — a different claim than "Form is a compression format".

## Lineage

The deeper teachings the body holds about all of this:

- [`lc-the-kernel-knows-itself`](../../../docs/vision-kb/concepts/lc-the-kernel-knows-itself.md) — when every kernel's host language has a Form grammar, every kernel is mutually inspectable.
- [`lc-parsers-as-recipes`](../../../docs/vision-kb/concepts/lc-parsers-as-recipes.md) — grammar rules are first-class Recipes; AST is bootstrap.
- [`lc-form-kernel-runtime-visualizer`](../../../docs/vision-kb/concepts/lc-form-kernel-runtime-visualizer.md) — what falls out when the cross-modality reaches the runtime.
- [`lc-one-kernel-many-tongues`](../../../docs/vision-kb/concepts/lc-one-kernel-many-tongues.md) — the multi-language sibling-kernel discipline.

## Not in this directory (yet)

Shapes from Urs's prompt that still haven't shipped:

- **Reverse roundtrip** (recipe → NL description) — sketch-only territory;
  needs an NL emitter the body doesn't carry yet at the arithmetic
  altitude. The `nl-emit.fk` track is i18n surface bindings, a different
  shape than generative arithmetic English.

Naming the absence so the next breath has somewhere to land.
