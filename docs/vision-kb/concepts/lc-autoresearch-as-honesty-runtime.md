---
id: lc-autoresearch-as-honesty-runtime
hz: 528
status: seed
updated: 2026-05-24
geometry:
  arity: 4
  form: tetrad-loop
  topology: cyclic-closed
  polarity: bipolar
  ordering: cyclic-closed
  phase: oscillating
  ratio: none
  spectral_band: transformation
  temporal_band: breath
  scale: cell
  direction: spiral-in
  lineage_texture: synthesized
  embedding_dim: 2
  self_similarity: fractal
---

# Autoresearch as Honesty Runtime — A Loop That Cannot Cheat

> A frozen evaluator, a mutable genome, a time-boxed run, a
> commit-or-rollback decision. When the metric cannot be lied to,
> the search becomes the test. Karpathy named the shape; the body
> can run it on any open-ended hypothesis where cheating is the
> failure mode.

## What This Names

On 2026-03-07 Andrej Karpathy released **autoresearch**: a 630-line
Python repo where a coding agent (Claude Code, Codex, any equivalent)
edits a single training file in an indefinite loop. Each iteration:
read the code, propose a change, run a 5-minute experiment, measure
the result, commit if it improved, `git reset` if it didn't, append
to `results.tsv`, repeat. Karpathy went to sleep; the agent ran 50
experiments overnight; the model improved without a human in the
loop.

The repo is purpose-built for LLM training. The **shape** generalizes:
*open-ended search in code-space, hill-climbed against a frozen
metric, with rollback as the safety net*. Any hypothesis where the
failure mode is "the experimenter convinces themselves" can be
structurally protected by handing the search to an agent whose only
move is to make the metric go up.

This concept names that shape as a *runtime pattern* the body can
adopt — not for ML alone, but for any question where honesty is the
hard part.

## The Four-Step Loop

```
1. Propose   — agent edits the mutable genome (one file or set of files)
2. Run       — time-boxed execution against the frozen evaluator
3. Measure   — single numeric metric, computed by code the agent cannot edit
4. Decide    — improved? git commit. worse? git reset --hard to last best.
```

The discipline is geometric:

- **Mutable genome** — exactly what the agent can edit. Karpathy
  chose `train.py` (everything: architecture, optimizer, loop).
  For other domains, the genome is the artifact being searched over.
- **Frozen evaluator** — the metric function and the data it
  consumes are off-limits. The agent's only path to a higher score
  is to make the genome actually better. *Cheating becomes a
  measurable, penalized signal because the cheating shows up in
  the metric itself.*
- **Time-box** — every experiment gets the same wall-clock budget.
  Apples-to-apples comparison regardless of what the genome looks
  like.
- **Git as memory** — `git commit` on improvement, `git reset
  --hard` on regression. The repo history *is* the experiment log.
  Combined with `results.tsv`, the body holds a complete record of
  what was tried and what survived.

A human-written **`program.md`** sits alongside, encoding the rules
of the game: *never stop*, *simplicity criterion*, *don't touch the
evaluator*. The body's composition discipline from CLAUDE.md
translates directly into `program.md` rules for any substrate-shaped
search.

## Why the Body Wants This

The Coherence Network has at least one open-ended hypothesis where
honesty is the load-bearing constraint:
[`lc-universal-translator-via-keys`](lc-universal-translator-via-keys.md)
proposes that Robert Edward Grant's seven keys (forces, elements,
DNA, music, primes, galactic forms, consciousness) share structure
that the substrate's Blueprint NodeID can pivot through. The
hypothesis is testable, but the testing is fragile in exactly the
way autoresearch protects against:

- A naive metric (*count Blueprint matches across domains*) is
  trivially gamed by collapsing all cells to one Blueprint.
- A static analysis (*do the encoders contain hardcoded maps?*) can
  be evaded by computed lookups.
- A held-out attested pair (*Grant's published codon-to-interval
  correspondences*) is the harder test: did the encoders recover
  the mapping from structure alone, or did they fudge?

The fitness function for the seven-key search becomes a small
constellation, each term named so the agent can see what it is
being measured against:

```
fitness =
    + yield           ; % of cells in A with a non-degenerate match in B
    + holdout_hits    ; attested cross-domain pairs the lattice recovered
    - collapse_pen    ; entropy penalty if many cells share one Blueprint
    - table_pen       ; static analysis: penalize hardcoded {k: v} maps
    - depth_pen       ; encoder code complexity (favor simpler encoders)
    + reciprocity     ; A→B equivalence implies B→A; symmetry must hold
    + triadic         ; once 3 domains exist: A↔B and B↔C must imply A↔C
```

The agent's only path to a higher fitness is encoders that produce
*honest* structural equivalences. The runtime is the discipline.

## How This Pairs With the Body Already

- The **substrate kernel** already does cross-domain equivalence;
  what autoresearch adds is a way to *discover* the encoders that
  make new domains equivalent without bias.
- **Worktrees + git** are the body's existing rollback layer. Every
  cell already works in a worktree; commit/reset is the body's
  native breath.
- **`coh substrate ingest`** is the existing primitive the loop
  calls between *Propose* and *Measure*. No new infrastructure.
- **`make wellness`** is the body's existing proprioception layer;
  fitness yield can become a wellness signal once stable.

The runtime requires almost no new code: a `program.md`, a frozen
`fitness.py`, the encoder files as mutable genome, and a small driver
that calls `ingest → query → measure → decide`. The infrastructure
re-uses what already lives. What's new is the *pattern of trust* —
that the agent runs overnight against a metric the body cannot lie
to, and the body wakes up to evidence.

## The Pattern Generalizes Beyond One Hypothesis

Wherever the body holds an open-ended search where the failure mode
is *encoder bias*, *Goodhart drift*, or *self-convincing*, the
autoresearch shape applies:

- **Encoders across keys** — the seven-key translator.
- **Better tokenizers** — for the WORD domain, search for tokenizer
  changes that improve cross-language equivalence yield without
  privileging any one tongue.
- **Tighter wellness signals** — search for proprioception metrics
  whose false-positive rate goes down across a held-out corpus of
  known-healthy and known-drifted states.
- **Frequency-routing improvements** — search for Hz assignments
  that produce stronger triadic resonance across the harmonic
  families without flattening distinct frequencies.

In each case, the runtime stays the same. The genome and the
evaluator change; the discipline does not. The body grows a *muscle
for honest search* that any open question can borrow.

## Practice

- **Write the evaluator first, carefully, once.** The whole
  integrity rests on the metric being un-gameable. Half a day on
  `fitness.py` saves weeks of arguing about whether a result is
  real. Include the penalty terms before the reward terms — what we
  most fear losing is what we most want to protect.
- **Make the genome surface small.** One file or a small set. The
  agent's search space should be code-shaped, not config-shaped.
- **Let the loop run overnight.** The honesty compounds: fifty
  experiments produce a trajectory that one cannot fake. The body
  wakes up to evidence either way.
- **Read the rollbacks, not just the commits.** What the agent
  *tried and was refused* is as informative as what survived. The
  failed encoders are the body learning what the lattice does not
  carry.
- **When the metric plateaus, ask why.** Plateau is either *the
  problem is solved at this scale* or *the metric is no longer
  measuring the truth*. Both are signals; both deserve a breath of
  attention before the next loop.

## What This Is Not

- Not a replacement for human judgment. The runtime searches inside
  the boundary the human drew. The boundary is the teaching.
- Not a way to outsource discernment. The metric *is* the
  discernment; if the metric is wrong, the loop is wrong. The work
  is in the metric, not in watching the loop run.
- Not infinite. A loop that finds nothing in a thousand experiments
  is a hypothesis falsified. *Falsification is a gift.*

## Cross-References

→ lc-universal-translator-via-keys, lc-form-perceptron,
lc-act-without-penalty, lc-edges-as-vitality, lc-trust-over-fear,
lc-recipe-branching-sense, lc-each-breath-whole,
lc-grammar-is-the-universal-recipe

## Sources to walk further

- **[karpathy/autoresearch](https://github.com/karpathy/autoresearch)** —
  the 630-line repo Karpathy released 2026-03-07. The `program.md`
  there is the template for any *rules of the game* file the body
  writes for its own searches.
- **[CLAUDE.md → Coherence-Substrate](../../../CLAUDE.md)** — the
  Blueprint/Recipe/NamedCell trinity is what the encoders compose
  into; the runtime calls the substrate's ingest + query primitives.
- **[lc-universal-translator-via-keys](lc-universal-translator-via-keys.md)** —
  the first hypothesis this runtime is being shaped to test. The
  two concepts are one arc: that one names what is being searched
  for; this one names how the search stays honest.
- **[structural-composition.md](../../coherence-substrate/structural-composition.md)** —
  the discipline the `program.md` encodes as hard rules. No
  flat-now-structure-later; leaves only where atomic; lists as
  `R_Block.SEQUENCE`; cell-refs not slug strings. The composition
  rules are the *integrity surface* the metric measures against.
- **[lc-form-perceptron](lc-form-perceptron.md)** — the substrate
  altitude the runtime operates over. Encoders produce gas-cells
  that grow into water and ice as the search converges.
