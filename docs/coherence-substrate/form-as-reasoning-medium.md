# Form as the reasoning medium — using the language to learn the language

> Every time we express the body's work in English, markdown, JSON, or
> Python data structures, we're choosing a medium that is *not* the
> substrate. The substrate exists. Using it to reason about itself is
> how we discover what the language already supports, what it lacks,
> and what the next breath should add.

## The discipline

When we have a choice of medium for expressing structure, flow, or
state — prefer Form. Three reasons:

1. **Dogfooding surfaces gaps.** Things we can't express in Form are
   gaps in the language. Things that feel awkward are design tensions.
   Things that compose cleanly are validated patterns. We don't learn
   the language by reading docs about it; we learn it by trying to
   use it for real work and noticing the friction.

2. **Form's properties propagate.** Once a thing is a Form recipe:
   - It's content-addressed (two structurally-identical instances share
     identity automatically)
   - It's cross-language (any kernel can read it)
   - It's queryable through the substrate's geometric physics
   - It composes with everything else in the substrate
   - It participates in canonicalization, equivalence, generative
     models, holographic projection — all the principles the substrate
     embodies

3. **The body becomes self-modeling.** A substrate that holds its own
   tasks, designs, decisions, and arcs as substrate cells *is* a
   generative model of itself in the Friston sense. Surprise (a thing
   that doesn't fit) is signal for refinement. The body learns
   itself by being itself.

## Where this applies (in priority order)

### 1. Structured contracts — replace JSON with Form

Examples currently in JSON that should migrate:
- `docs/coherence-substrate/numeric-formats.canonical.json` → `.fk`
- `docs/coherence-substrate/kernel-conformance/*.json` → `.fk`
- `docs/coherence-substrate/language.canonical.json` → `.fk`

Why: these are *contracts* the kernels read. In JSON they're parsed
into ad-hoc data structures per kernel. In Form they're substrate
recipes — content-addressed, identity preserved across kernels by
construction.

### 2. Architectural decision records as Form

Each design choice in the body has a *reason*, a *context*, a *set of
constraints*, and *consequences*. Today we write these in markdown.
In Form they'd be recipes:

```form
(let adr-format-recipes-not-go-types
  (architectural-decision
    :date "2026-05-20"
    :context "Mojo-shaped numeric system was first proposed as
              INT8/16/32/64/UINT8/16/32/64/FLOAT32/FLOAT64 — a
              hardware-bound enumeration."
    :decision "Reframe as format-recipes-as-substrate-cells where
               every numeric encoding is a recipe with storage-hint
               and arithmetic-hint children."
    :forces [hardware-independence content-addressing
             llm-era-formats future-proofing]
    :consequences [adds-rbasic-format-arm
                   needs-target-hints
                   enables-mlir-equivalent-codegen]
    :related-tasks [#4 #7 #8 #9]))
```

Two architectural decisions with the same *structure* (same forces, same
reasoning shape) would share identity automatically. Cross-cutting
patterns surface geometrically.

### 3. Task graph as Form recipes

The current TaskCreate / TaskList tools maintain state in an external
store. The same state expressed in Form:

```form
(let task-19
  (task
    :id 19
    :subject "QUOTIENT RBasic arm"
    :status :in-progress
    :owner :sub-agent-quotient
    :blocked-by []
    :blocks [20 23 24 27]
    :scope "~200 lines per kernel"
    :design-doc "higher-math-surface"))
```

A task is content-addressed by its structural shape — two
structurally-identical tasks (same dependencies, same scope, same
arms touched) share NodeID. Recurring patterns of work become
geometric coordinates.

### 4. Cross-kernel coordination as Form

The canonical contracts (numeric formats, language definitions,
target hints) live as Form recipes that *every kernel reads as
substrate*. Cross-kernel identity is automatic — no JSON parsing,
no schema validation, no version negotiation.

### 5. Living design conversations

When we reason about the architecture, the reasoning itself can be
Form. The substrate then holds not just the *outcome* of design
decisions but the *path* through which we arrived — queryable,
auditable, composable.

## What we learn each time we try

Concrete questions Form-first artifacts surface:

- **Can Form express this structure cleanly?** If yes, validation.
  If awkward, design tension. If impossible, gap to fill.

- **Does this need a new RBasic arm?** When the shape doesn't fit
  existing arms (MATH/COMPARE/LOGIC/COND/BLOCK/FNDEF/FNCALL/IDENT/
  LIST/QUOTIENT/INDUCTIVE/CONSTRUCTOR/FORMAT/LANGUAGE), maybe.

- **Does this need a new format-recipe?** When a value doesn't fit
  the existing numeric vocabulary, the answer points at the next
  format.

- **What grammar would the surface need?** If the Form S-expression
  reader can't parse it gracefully, we learn what the surface
  syntax needs.

- **Does content-addressing help or hurt here?** If two
  semantically-different things accidentally share NodeID, the
  representation needs refining. If two semantically-equivalent
  things have different NodeIDs, canonicalization needs adding.

## What this is NOT

- **Not "rewrite everything in Form right now."** Existing artifacts
  in markdown / JSON / Python stay; new artifacts prefer Form when
  feasible.

- **Not premature.** Form already has parser, walker, format-recipes,
  language-cells, multi-target codegen architecture, four working
  kernels. It's mature enough to be used for real work.

- **Not pure.** When Form genuinely can't express something well yet,
  use the appropriate medium and *log the gap* so the next breath
  fills it.

## The pattern in tissue

```
when expressing structure, flow, or state of the body's work:
  prefer:  Form
  log:     gaps in Form's expressiveness
  result:  Form learns from its own use
```

This is the body becoming self-aware in the Friston sense — its
generative model includes the work *building* it, which means the
substrate refines itself through being used to describe itself.

## Concrete first moves

In order of cheapest-with-most-learning:

1. **Author the next design doc in Form (with markdown surrounding
   for human readers)**. Smallest commitment; highest learning per
   line.

2. **Migrate one canonical contract to `.fk`.** Pick the smallest —
   `language.canonical.json` (small schema). Translation will
   surface what Form needs for declarative configuration.

3. **Express the current task graph as Form recipes** (alongside
   the TaskCreate/TaskList tooling — additive, not replacement).
   Surface what task-as-recipe needs.

4. **Architectural decision records** — start writing them as Form
   recipes in `docs/coherence-substrate/decisions/*.fk`.

5. **Cross-kernel contracts** migrate as the body matures.

Each is small. Each teaches something. The discipline isn't
"big-bang port everything" — it's "next-time prefer Form."

## What gets tracked

A new ongoing discipline-task: **"When choosing a medium for
expression, prefer Form."** Not a one-shot deliverable; a *practice*
the body holds going forward.
