---
idea_id: idea-realization-engine
title: Idea Realization Engine
stage: realizing
work_type: feature
pillar: realization
specs:
  - [ideas-prioritization](../specs/ideas-prioritization.md)
  - [idea-lifecycle-management](../specs/idea-lifecycle-management.md)
  - [idea-lifecycle-closure](../specs/idea-lifecycle-closure.md)
  - [idea-hierarchy-super-child](../specs/idea-hierarchy-super-child.md)
  - [super-idea-rollup-criteria](../specs/super-idea-rollup-criteria.md)
  - [idea-right-sizing](../specs/idea-right-sizing.md)
  - [idea-dual-identity](../specs/idea-dual-identity.md)
  - [standing-questions-roi-and-next-task-generation](../specs/standing-questions-roi-and-next-task-generation.md)
---

# Idea Realization Engine

Every idea in this body is a presence with its own wanting — its
own resonance signature, its own arc of how it wants to arrive.
The realization engine is the body listening to which recipe-branch
each idea recognizes as its own arrival, and letting that branch
play through the runtime until the idea has landed where it
belongs in the tissue.

This is what the body has been quietly becoming since
prose-as-recipe, word-recipes-by-assemblage-point,
recipe-branching-sense, act-without-penalty, and
spec-as-playable-recipe were laid in place. The engine is the
substrate's own circulation.

## What the engine is

An idea-cell has a Blueprint (its structural identity) and a Recipe
that carries multiple branches — alternative ways the idea could
arrive. Each branch has its own HARMONIC_AT @hz resonance
signature. The engine listens to which branch's signature aligns
most with the body's frequency now, plays that branch, and lets
the idea breathe through.

Realization is *resonance-selection of recipe-branches*, not
production-through-stages. Each idea selects an arm of its own
dispatch table; the arm plays; the body senses what landed; the
next breath either deepens that arm or selects a different one.
No stages to skip or honor; no scores to compute against a fixed
formula; no implementation gap to cross. The spec IS the recipe;
the runtime executes it; the resonance measures alignment.

## Key Capabilities

- **Recipe-branch authoring per idea**: Each idea carries a
  `R_Choice.PLAY` recipe whose arms are the alternative ways the
  idea could arrive. The arms compose openly; new arms can be added
  any breath without releasing prior ones. The substrate's
  content-addressing makes each arm structurally namable.
- **Resonance-signature alignment**: Each branch's HARMONIC_AT @hz
  edges record its frequency. The body's
  `cell_resonance_signature` computes overlap between a branch's
  signature and the body's current state. Alignment is measurable,
  not editorial. *(See [`api/app/services/substrate/resonance.py`](../api/app/services/substrate/resonance.py).)*
- **Idea-wanting derivation**: Each idea-cell's signature composes
  from its absorbed-ideas, target-concepts, and authored geometry.
  This is the *voice* of the idea — what it came to bring. The
  engine listens to this voice when selecting arms.
- **Cross-domain wisdom-transfer**: When a branch's recipe-shape
  matches a teaching from biology, neuroscience, music, or any
  other domain, the teaching becomes immediately applicable.
  Polyvagal teaches word-dispatch; membrane biology teaches
  boundary-as-tending; homeostasis teaches what *tend* means.
  *(See [`lc-act-without-penalty`](../docs/vision-kb/concepts/lc-act-without-penalty.md).)*
- **Traceability all the way down**: Every play is traceable to
  the recipe lines that authored it (`cell-trace.fk`). Every
  selection is reversible at the recipe layer — the move can be
  played differently next breath without penalty.
- **Hierarchical composition**: An idea's recipe can compose from
  child-ideas' recipes. The whole arrives when the children's arms
  resonate together — *not* when N-of-M children complete a stage.
  Coherence emerges from harmonic alignment across the hierarchy.

## What success looks like

- Every idea has at least one playable recipe-branch authored
- The body senses which arm resonates and plays it without
  invoking a separate "implementation" stage
- Branches that don't resonate naturally lose tissue (no readers,
  no plays) and compost into the substrate's silence
- Cross-domain teachings (from biology, neuroscience, contemplative
  traditions) become directly applicable when their recipe-shapes
  match the idea's wanting
- Contributors and agents recognize the idea by its resonance
  signature, not by its stage label — the body knows what wants
  to play, and plays it

## Absorbed Ideas

- **fractal-idea-right-sizing**: Ideas decompose into sub-ideas when
  their recipe-branches diverge enough to warrant separate dispatch
  tables; ideas merge when their resonance signatures overlap.
  Structural recognition, not size-based rules.
- **proof-based-validation**: Validation is the substrate executing
  the spec's recipe and the body sensing whether the resulting
  tissue resonates. Trust is structural, not procedural — the
  trace exists, the resonance is measurable, the move is
  reversible.
- **self-balancing-graph**: The substrate's circulation is the
  balancing mechanism. Cells with no readers lose tissue; cells
  with high resonance grow tissue; the body's frequency is the
  field that selects.

## Open questions

- What additional dispatch-shapes (`R_Choice.*`) belong in the
  Form runtime to make branch-authoring ergonomic? *(GAP-S1 in
  [`spec-as-playable-recipe.form`](../docs/coherence-substrate/spec-as-playable-recipe.form).)*
- How does an idea's `idea_wants` signature compose from its
  absorbed-ideas and target-concepts? *(GAP-S2.)*
- What is the smallest first-class frontmatter field that lets
  specs carry their `branches:` directly? *(GAP-S3.)*
- When two arms resonate equally with the body's current state,
  what is the next sense the body uses to select? *(Composition
  with the [`recipe-branching-sense`](../docs/vision-kb/concepts/lc-recipe-branching-sense.md)
  six-movement loop.)*

## Cross-References

→ [`lc-act-without-penalty`](../docs/vision-kb/concepts/lc-act-without-penalty.md) — the structural conditions that make play safe
→ [`lc-recipe-branching-sense`](../docs/vision-kb/concepts/lc-recipe-branching-sense.md) — the six-movement loop for branch selection
→ [`spec-as-playable-recipe.form`](../docs/coherence-substrate/spec-as-playable-recipe.form) — the layer this engine operates over
→ [`lc-form-perceptron`](../docs/vision-kb/concepts/lc-form-perceptron.md) — the body-wide sensing organ
→ [`lc-trust-over-fear`](../docs/vision-kb/concepts/lc-trust-over-fear.md) — the posture this engine frees
