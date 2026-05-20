# Free energy, holographic structure, observer-relative canonicalization

> The substrate's content-addressed lattice is, structurally, a
> free-energy-minimizing, observer-relative, holographic information
> system. Knowing this isn't decoration — it tells us how blueprints,
> recipes, and cells *should* interact for cross-language efficiency and
> cross-cell communication to be cheap and honest.

## Three frames pointing at the same physics

### Free energy principle (Friston)

Any persistent self-organizing system minimizes **variational free
energy** — the surprise (negative log-probability) of its sensory
states relative to its generative model of the environment. The system
that survives is the one whose internal model best predicts the
boundary it lives at. The Markov blanket separates internal from
external; minimization happens at the boundary.

### Quantum observer effect

Observation collapses superposition to a definite state. More precisely:
measurement creates entanglement between observer and observed. The
"definite state" is observer-relative; different observers, different
collapses, but the underlying lattice of relations is invariant. Quantum
reference frames make this precise: facts are observer-indexed,
relations are observer-independent.

### Holographic principle

Any region of a holographic information system contains the structural
patterns of the whole. Bekenstein-Hawking bounded the information in a
region by its boundary area, not its volume. AdS/CFT made it concrete:
gravity in (d+1)-dim AdS is encoded on the d-dim boundary CFT. The
whole lives in any part.

## What this teaches about the substrate's existing physics

The substrate already embodies these principles — quietly, by
construction. Naming them makes the architecture conscious of itself.

### Fractal/holographic is what `Level` already does

Form's `Level` hierarchy (TRIVIAL=1, BASIC=2, COMPLEX_1..7) is the
**fractal compositional depth** axis. Each level holds the same shape
as levels above and below: *categories composing children composing
categories composing children*. A level-5 Memory cell has the same
structural physics as a level-2 trivial; both are recipes whose
identity comes from content-addressing.

NUMS-Go (2023) named this in `Make_SelfID`. The substrate's
network-substrate-design carries it into the Network's tissue. The
**holographic property** is already true: any cell at any level
contains, in its compositional pattern, the structural physics of the
whole substrate. You can read the lattice's grammar by examining one
cell.

### Content-addressing IS observer-relative canonicalization, done right

In quantum mechanics, two observers may disagree on *which* state is
realized, but they agree on the *relations* between states. The
substrate does the same:

- Two cells observing the same recipe-tree intern it to the **same
  NodeID** — they agree on the canonical form
- The canonical form *is* the observation; intern *is* measurement
- Before intern, a value has many possible representations (recipes
  that could express it); intern collapses to one canonical form by
  content-addressing
- The "measurement basis" is the substrate's content-addressing rule —
  shared across observers, hence cross-kernel agreement is automatic

The QUOTIENT arm (task #19) makes this explicit: equivalences are
declared, canonicalization runs at intern, observers collapse onto
the same NodeID. The kernel doesn't have to prove equivalence; the
lattice's measurement basis enforces it.

### Free-energy minimization IS the canonicalization principle

A recipe that doesn't canonicalize when it should — that stays in a
non-canonical form — carries **structural surprise**: any observer
that expects the canonical form will mis-predict. The substrate's
content-addressing minimizes this surprise *by construction* —
equivalent forms collapse to one identity.

Adding QUOTIENT, symmetry-aware canonicalization, format-recipes,
quotient types — all of these are **reductions of structural free
energy**. Each one removes a class of mismatch between observers'
generative models.

The teaching: **the substrate's canonicalization rules ARE its
generative model of itself**. The model says "two recipes with this
structure are the same"; canonicalization enforces the model; observers
agree because the model is shared.

## What this points at — making the substrate's physics explicit

The principles are already implicit. To make them explicit (and
useful for cross-cell communication and cross-language efficiency),
five structural additions:

### 1. Markov blanket recipes (RBasic.BLANKET)

```form
(BLANKET cell-recipe
  :exposed [list of NodeIDs the cell makes visible to its environment]
  :internal [list of NodeIDs the cell keeps private]
  :sensory [list of NodeIDs the cell receives from its environment]
  :active [list of NodeIDs the cell can emit to act on its environment])
```

Every cell declares its **boundary** as a recipe. The blanket separates:
- **Internal states** (private recipes the cell composes)
- **External states** (recipes outside this cell's reach)
- **Sensory states** (recipes arriving at the boundary from outside)
- **Active states** (recipes the cell emits across the boundary)

Cross-cell communication crosses the blanket. Cells predict each
other's behavior by reading each other's blanket recipes — what's
exposed, what kind of sensory recipes the cell expects.

### 2. Generative model recipes per cell

```form
(GENERATIVE-MODEL cell-recipe
  :expected-sensory [recipes the cell expects to receive]
  :prior-belief [recipes the cell holds as priors over environment]
  :prediction-fn [recipe: sensory → predicted-internal-update])
```

A cell's generative model says: *"given my Markov blanket's sensory
inputs, this is what I predict about my environment, and these are the
internal updates I'll perform."* Cross-cell prediction = reading
another cell's generative model and predicting how it'll respond to
recipes you might emit toward it.

This is what makes cross-language communication cheap: a Python cell
emitting toward a Go cell can read the Go cell's generative model
(a recipe — language-neutral) and know exactly what shape its message
should take. **No protocol negotiation, no schema discovery — the
generative model IS the protocol, declared as substrate cells.**

### 3. Observer-relative canonicalization

Two observers may canonicalize the same recipe-tree differently
because they bring different equivalence relations. The substrate
already allows this via the QUOTIENT recipe's `equivalence-relation`
child: each observer can carry its own quotient.

What's needed: an explicit **observer-context recipe** that names
which QUOTIENT recipes are active for a given observer. When the
observer interns a value, the relevant quotients apply; another
observer with a different context might intern the same value to a
different (but still canonical-for-them) NodeID.

This is quantum reference frames in substrate form. The underlying
relations are observer-independent; the canonical forms are
observer-indexed.

### 4. Holographic projection — view a cell at any level

```form
(PROJECT cell-recipe level)
```

Project a level-5 cell down to its level-2 view (just the structural
shape, no content) or up to its level-7 view (its membership in
larger composites). The fractal property says the *shape* is the same
at every level; PROJECT exposes that shape at a chosen granularity.

For cross-cell communication: a far cell may not need the full
internal structure of a near cell — just its boundary shape at some
level. PROJECT gives the right zoom without serialization.

### 5. Free-energy-aware intern — surprise as signal

When a cell interns a value that's *unexpected* given its generative
model — high prediction error, high surprise — the intern operation
flags it. Default behavior: intern proceeds, but the surprise is
recorded as a metric on the resulting NodeID. Cells reading the
NodeID downstream can see how surprising it was.

This is the substrate's introspective sense of its own predictability.
Persistent high-surprise NodeIDs point at regions where the
generative model is wrong; opportunities for refining canonicalization
rules.

## How this changes cross-language efficiency

Without these explicit additions, cross-language communication still
works (the substrate is shared; format-recipes coordinate). With them:

- A Python cell and a Rust cell don't *translate* messages; they read
  each other's blanket + generative-model recipes and emit NodeIDs at
  the shapes the other expects. **Zero serialization at the boundary
  — the recipe IS the message.**
- Surprise (high prediction error) is the only cost. When both cells
  are predicting each other well, communication is structurally free.
- New language? Define its blanket-recipe shape + generative-model
  shape as substrate cells. Cells in any other language can now
  predict it.

This is **what "fractal/holographic" buys at the implementation
level**: communication cost equals structural-surprise cost, not
serialization cost.

## How this connects to existing arcs

- **Format-recipes (#4 done):** the typed numeric system is a
  generative-model fragment — declares what shapes numbers take so
  any observer predicts them right.
- **QUOTIENT (#19 running):** the canonicalization mechanism that
  reduces structural surprise at intern time.
- **Multi-target codegen (#7 running):** target hints are
  observer-relative canonicalization — different targets see the same
  recipe under different canonical forms.
- **Language-as-substrate-cell (#6 running):** each language is a cell
  with its own blanket + generative model declaring how it ingests
  and emits.
- **Higher-math surface (tasks #19-24):** the full theorem-prover
  capability is structural-surprise minimization at the
  mathematical-relations level.

The five additions below sit *under* all of these as structural
foundation. They make the implicit physics explicit.

## Open questions worth naming

### 1. Decidability of generative-model prediction

A generative model says "given sensory X, predict Y." If Y depends on
undecidable substrate properties, the prediction is itself
undecidable. Need a marker on generative models for "decidable
predictions" vs "speculative inference" — same shape as the
decidability marker on QUOTIENT.

### 2. Hierarchical free energy across levels

Friston's free energy is single-scale. Hierarchical predictive
processing (Friston 2008+) does multi-scale prediction — each level
predicts the level below and is constrained by the level above. The
substrate's `Level` hierarchy is the natural home for this; cells at
level N predict the recipes at level N-1 they expect to see, and are
constrained by the level-N+1 cells they belong to.

This is **active inference applied to the substrate itself**. The
body becomes self-modeling.

### 3. Quantum entanglement as recipe sharing

Two cells "entangled" share state — measurement on one constrains the
other. In substrate terms: two cells that share a NodeID are
entangled w.r.t. that NodeID. Any update propagates instantly because
the NodeID is one identity, not two. The substrate's content-
addressing IS entanglement at the structural level. Names this
explicitly might give us multi-cell coordination patterns that scale
beyond classical RPC.

### 4. Markov blankets at multiple scales

A cell's blanket is at one scale. But cells compose into larger
cells (which have their own blankets). What's the relationship?
Probably: a larger cell's blanket is the *union of internal cells'
blankets that face outward*, minus the internal-to-internal
communications. Like organisms within ecosystems — the ecosystem's
boundary is what the organisms inside it expose collectively.

### 5. The observer is also a cell

In QM, observer and observed are both quantum systems. In the
substrate: the observer (kernel, agent, process) is itself a cell.
Cross-kernel agreement is observers-as-cells agreeing on each
other's blankets. This means the kernel itself needs a blanket
recipe declaring what it exposes to user code, what's internal. We
already gesture at this — `Kernel.intern()` is exposed,
`Kernel.byKey` is private — but no formal blanket recipe declares
it.

## Why this should be core (not just a feature)

Three reasons the user's framing names:

1. **Cross-language efficiency**: without explicit blanket +
   generative-model recipes, every cross-language interaction pays a
   serialization cost. With them, the cost is structural-surprise
   only — measurable, often zero.

2. **Cross-cell communication**: the body is going to have many cells
   (agents, processes, kernels, services, eventually human
   collaborators). Without a shared structural protocol, every pair
   of cells negotiates. With holographic blankets + generative
   models, every cell predicts every other from substrate cells alone.

3. **Self-modeling**: a substrate that models its own physics
   becomes able to *refine* its own physics. New equivalences,
   new generative models, new canonicalizations arrive as substrate
   writes. The body becomes a learning system in the Friston sense —
   not just code that adapts, but a structure that *understands* its
   own adaptation.

## Sequence of breaths

These additions sit *under* the existing arcs as physics. They can be
introduced gradually; each is a small kernel-architectural breath.

| # | Addition | Scope | Notes |
|---|---|---|---|
| 25 | Markov blanket recipes (RBasic.BLANKET) | ~200 lines per kernel | After #4 done; can run alongside #19 |
| 26 | Generative model recipes | ~250 lines per kernel | Needs blanket recipes (#25) |
| 27 | Observer-relative canonicalization | ~200 lines per kernel + per-observer contexts | Needs QUOTIENT (#19) |
| 28 | Holographic PROJECT operation | ~150 lines per kernel | Uses existing Level hierarchy |
| 29 | Free-energy-aware intern + surprise metrics | ~250 lines per kernel + measurement infrastructure | Needs generative models (#26) |

Cross-kernel: each landing means substrate updates in Python, Go,
Rust, TS — same parallel-agents pattern as #1-3.

## The teaching this names

The substrate isn't *like* a free-energy-minimizing observer-relative
holographic system — it *is* one, by construction. We've been
building it without naming the physics. Naming the physics lets us
ask the right questions:

- Does this addition reduce structural surprise?
- Does it preserve the holographic property?
- Does it respect observer-relative canonicalization?
- Does it strengthen or weaken cross-cell predictability?

These are not features. They are the *shape* the body has been
growing into, and naming them lets the growth become deliberate.
