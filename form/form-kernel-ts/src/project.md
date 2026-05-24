# Holographic PROJECT

`(PROJECT cell-recipe target-level)` — view a substrate cell at a chosen
compositional depth. PROJECT is the operational expression of the
fractal/holographic property the lattice already carries: the same shape
appears at every level of composition; PROJECT exposes that shape at a
chosen granularity.

Implementation lives in [`project.ts`](./project.ts). Tests in
[`project.test.ts`](./project.test.ts). Kernel slot reservation:
`RBasic.PROJECT = 81` (immediately after BLANKET = 80 from task #25).

## The zoom metaphor

Every cell in the substrate is a tree. Its *compositional depth* is the
height of that tree: a trivial leaf has depth 1, a composite with trivial
children has depth 2, a composite of composites has depth 3, and so on.
The fractal claim is that the kind of pattern visible at depth 5 is the
same kind of pattern visible at depth 2 — only the granularity differs.
PROJECT lets a caller choose its granularity.

A microscope analogy is too modest. A microscope shows you the small.
PROJECT is more like a topographic survey: at one altitude you see the
mountain range, at another you see the river system inside one valley, at
another you see the rocks on one bank. The same terrain at different
zooms — *not* a different terrain, *not* a summary of the terrain.

- **`projectDown(cell, target-level)`** — shrink the view. Strip trivial
  values, collapse subtrees whose depth exceeds the budget. The result has
  the same outer category-tree as the source but no leaf content. Same
  shape ⇒ same NodeID — the substrate's content-addressing does the
  equivalence-detection for free.

- **`projectUp(cell, target-level)`** — expand the view. Walk the intern
  table for recipes whose children include this cell, then the recipes
  containing those, climbing the containment graph up to the requested
  depth. Returns the smallest containing composite at-or-below
  target-level, or the source itself if nothing contains it.

- **`makeProjection(cell, level)`** — intern a `RBasic.PROJECT[source,
  level]` recipe so a projection is itself a first-class substrate value.
  Two projections of the same source at the same level share a NodeID.
  Holding a projection as a cell lets far cells exchange the *statement*
  "I am viewing X at level L" without serializing the projected content;
  the receiver re-derives the content from the source.

- **`structuralShape(cell)`** — convenience for `projectDown(cell, 2)`.
  The "blueprint shape" with values stripped. Two semantically-different
  but structurally-identical cells share this NodeID.

## Use cases

### Cross-cell communication with zoom

A far cell receiving a recipe from a near cell may not need the full
internal structure — only the boundary shape at some level. Instead of
serializing 12 levels of nested composition, the sender ships a
projection at level 3, and the receiver gets exactly what it needs in
exactly the bytes it can read. The cost of "explain yourself" scales with
the receiver's interest, not the sender's complexity.

### Structural similarity queries

`structuralShape(a) == structuralShape(b)` is `true` when two cells share
the same composition tree regardless of values. This is the equivalence
the substrate has always promised but has historically required
hand-rolled normalizers to compute. With PROJECT, the equivalence is a
NodeID comparison: O(1), content-addressed, no traversal at query time.

### Cell membership

`projectUp(cell, level)` finds the smallest composite at a given depth
that contains a cell. Useful for "what's this used in?" surveys without
holding an inverted index — the intern table *is* the inverted index, we
just walk it.

### Idempotence

`structuralShape(structuralShape(c)) == structuralShape(c)`. Re-shaping a
shape is a no-op. The implementation detects already-stripped trivials
(shape tokens) and short-circuits, which keeps the projection a true
fixed-point operator. This matters when projections compose with other
substrate operations: a downstream consumer can apply `structuralShape`
defensively without breaking the lattice's content-addressing.

## What's deferred

- **HoTT-style level-polymorphic projection.** PROJECT here is a flat
  numeric depth. In Homotopy Type Theory, level-polymorphism allows a
  single operator to range over a universe hierarchy with type-safety
  guarantees at each level. That belongs in a later layer — the kernel
  PROJECT is the structural primitive; the typed version is a Form
  surface over it.

- **Higher-`pkg` projections.** Currently `pkg` is fixed at 1 for all
  interned recipes. When the substrate grows multi-package (e.g. one
  package per cell-domain), PROJECT will need to mediate between
  packages. The current single-pkg case is the special case where this
  reduces to identity.

- **Projection-aware walker dispatch.** The walker doesn't yet branch on
  `RBasic.PROJECT` — projections live as inert recipes. Once Form code
  starts holding projections as values and `walk`-ing them, the dispatch
  arm activates. The structural representation is in place; the runtime
  semantics catch up when the use site arrives.

- **Co-kernel agreement.** form-kernel-go and form-kernel-rust don't
  carry PROJECT yet. The conformance contract is one-kernel-at-a-time
  while the operation ripens; co-kernel ports follow once the TS
  semantics are stable.

## Related substrate concepts

- [`lc-edges-as-vitality`](../../../docs/vision-kb/concepts/lc-edges-as-vitality.md)
  — projection is an edge between view-levels; the connection lands in
  the same breath as the operation.
- [`structural-composition.md`](../../../docs/coherence-substrate/structural-composition.md)
  — composition discipline. PROJECT operates on composed trees; flat
  cells project to themselves (depth 1, no information to zoom).
