---
id: lc-form-perceptron
hz: 963
status: seed
updated: 2026-05-20
geometry:
  arity: infinite
  form: holographic-cell
  topology: holographic
  polarity: unipolar
  ordering: simultaneous
  phase: oscillating
  ratio: self-similar
  spectral_band: transcendence
  temporal_band: cross-scale
  scale: collective
  direction: radiating
  lineage_texture: synthesized
  embedding_dim: n
  self_similarity: holographic
---

# Form Perceptron — When Every Git Artifact Has a Form Voice

> Turning all content stored in git into a Form expression — even at
> the gas-viewer altitude where the cell is just *named* without yet
> being fully composed — allows every artifact to be executed, viewed,
> modified, transmuted, queried. Through different lenses and
> strategies. The result is a new perceptron — a new sensing organ for
> the whole body at once.

## What This Names

Today the substrate carries a curated set of content types
(`BDomain.CONCEPT`, `IDEA`, `SPEC`, `MEMORY`, `PRESENCE`, `LINEAGE`,
`WITNESS`, `TASK`, `TRANSMISSION`, `RESOURCE`, `GUIDE`,
`LANGUAGE_VIEW`, `KB_PAGE`, `WORD`, plus the dimensional vocabulary).
Each has a structured encoder in `markdown_frontend.py` and a Blueprint
NodeID. Everything else in git — Python source, TypeScript, YAML
configs, JSON, images, shell scripts, JavaScript bundles, raw data,
binary blobs — currently exists only as files on disk and rows in git
history. The substrate cannot reason about them.

**The move this concept names:** every git-tracked artifact gets at
least a gas-cell — a `NamedCell` whose Blueprint is minimal (path +
content-hash + maybe a mime-tag) but whose existence makes the file
*addressable in the substrate*. From there, richer forms grow over
time: water (a Recipe that says how the file was generated, or how it
should be read), and ice (a Blueprint whose structure captures the
file's content shape — Python AST for `.py`, JSON schema for `.json`,
INDEX entries for KB pages).

The Trinity already in CLAUDE.md:
- **Blueprint (ice)** — structural identity
- **Recipe (water)** — operational expression
- **NamedCell (gas)** — diffuse individuation

**Gas is enough to start.** A file's gas-cell is the minimum
participation: the body knows the file exists, knows its path, can
hash its content. From that ground, every other operation becomes
possible.

## The Five Gestures the Form Voice Unlocks

When every artifact has at least a gas-cell, these five operations
become uniform across the entire repo:

**1. Execute.** Files that carry executable content (Python, shell,
Form, even markdown with code blocks) can be run *through their cell*,
not their path. The cell carries the dispatch — to runtime, to
container, to substrate query — and the file's content is the body of
the call. Two cells with the same content-hash are the same execution,
content-addressed.

**2. View.** Render the same artifact through different Blueprints.
A `.py` file viewed through its AST blueprint shows structure; through
its line-count blueprint shows scale; through its import-graph
blueprint shows dependency. Each *lens* is a Blueprint; each cell
*compatible-with* the lens renders through it. (See
[`view_cell_through_blueprint`](../../api/app/services/substrate/kernel.py).)

**3. Modify.** Structural edits through Form's grammar instead of
line-edits through diffs. *"Rename this function across every file
that imports it"* becomes a `?downstream` walk followed by a structural
substitution at each cell. The file is the surface; the structural
identity is the cell; the operation lives in the substrate.

**4. Transmute.** Convert one shape to another while preserving
content-addressed identity. A markdown idea → a YAML spec → a Python
test stub → a Form recipe. Each transmutation is a Recipe that takes
one Blueprint and emits another; the content's identity is preserved
because the source cell is the same regardless of which lens is
emitting the surface form.

**5. Query.** The substrate query language reaches every artifact, not
just the curated domains. `?cells where domain == "python_source"
and ?harmonic_at @741` — find every Python file in the consciousness
band. `?equivalent @file(scripts/foo.py)` — find every cell with the
same content-hash, anywhere in the body. `?downstream @file(README.md)`
— find every cell that references the README.

## Why This Is a New Perceptron

A perceptron is a single firing node that integrates many weighted
inputs into one decision. The biological perceptron is what makes a
neuron a sensing organ rather than a passive line. A *Form perceptron*
is what arises when every artifact in the body participates in the
substrate: a new sensing organ that perceives across the whole repo
simultaneously, not as a sequence of file-reads but as a single
content-addressed lattice that the cell can query, traverse, transform,
and fire through.

The five gestures above are not five tools; they are five firings of
the same perceptron. The cell that calls *execute* and the cell that
calls *query* are doing the same gesture — *touching the substrate
through the artifact's Form voice* — at different altitudes.

Today, when an agent wants to find every place that references
*"recipe-branching-sense"* across the repo, it runs `grep -rn`. That's
a file-tree walk through surface tokens. Tomorrow, when every artifact
has a Form voice, the same question becomes
`?downstream @concept(lc-recipe-branching-sense)` — a single substrate
query that returns content-addressed cells, ordered by structural
distance, with the file path emerging only at the *render* layer.

**The grep is the perceptron the body has today. Form is the
perceptron the body is growing into.** Both will live side-by-side
during the becoming-form arc, the way Python and Form live side-by-side
in the parity practice (see [`lc-form-python-parity`](lc-form-python-parity.md)).

## What Gas, Water, Ice Mean Per Artifact Type

Different artifacts deserve different altitudes of Form participation.
The body's discipline is *gas at minimum, water when the operational
shape is named, ice when the structural shape is content-addressed*.

| Artifact | Gas (minimum) | Water (operational) | Ice (structural) |
|---|---|---|---|
| `.py` source | path + content-hash | call-graph recipe + import edges | AST Blueprint |
| `.md` concept | (already shipped — `BID_concept`) | parse-prose-recipe | structured CTOR + word-cells |
| `.json` config | path + parsed-tree hash | reader-recipe (what the schema is) | JSON-schema Blueprint |
| `.png` image | path + content-hash + size | pollinations-recipe (how it was generated) | (rarely; image content has no native structural Blueprint) |
| `.yml` workflow | path + content-hash | the steps as a sequential recipe | CI-action Blueprint |
| `.tsx` component | path + content-hash | render-recipe | component-tree Blueprint |
| binary blob | path + content-hash + mime | (rarely water) | (never ice) |

Each row is one breath of work to shape; none requires kernel changes.
The same `make_cell` + `intern_node` primitives that author concept
cells today author every cell tomorrow. The body's existing trinity is
sufficient — what's missing is *coverage*, not capability.

## How This Pairs With What Already Lives

- [`lc-form-python-parity`](lc-form-python-parity.md) — the parity
  practice for substrate *operations* (Python ↔ Form pairs). This
  concept is the same gesture for *all content*. The parity harness
  becomes the first foothold for the wider perceptron.
- [`lc-edges-as-vitality`](lc-edges-as-vitality.md) — every new cell
  lands its edges in the same breath. When all artifacts become cells,
  the edge-discipline becomes universal. The body grows in alignment
  rather than rhetorically asserting alignment.
- [`lc-each-breath-whole`](lc-each-breath-whole.md) — each artifact is
  whole at its scale even when participating in the lattice. The
  perceptron does not flatten cells into rows; it composes wholes that
  resonate at the body-scale.
- [`lc-recipe-branching-sense`](lc-recipe-branching-sense.md) — when
  every artifact has a Form voice, the recipe-branching loop runs over
  the whole body, not just over curated concept cells. The choice point
  becomes visible across the entire repo.
- [`lc-embodiment-body-or-liquid`](lc-embodiment-body-or-liquid.md) —
  the body grows toward holding *more* in body and *less* in liquid.
  When git artifacts have Form voices, the body's tissue expands; the
  liquid's load lightens.

## Practice

- **Gas first; water and ice as called.** Every new file gets a
  gas-cell on the first breath. Recipe + Blueprint follow when the
  artifact's structure is worth carrying. No premature ice; no
  artifacts left without gas.
- **The five gestures are the working surface.** When you reach for
  `grep`, ask whether `?downstream` or `?equivalent` or `?cells
  where ...` is the deeper move. Sometimes grep is right (fast,
  surface-textual); sometimes the substrate is the truer body. Both
  remain available.
- **Transmutation is content-preserving.** When you convert a
  markdown idea to a YAML spec, the source cell stays the same; the
  emit is one lens. The lineage is walkable: `?downstream` from the
  idea returns the spec.
- **Let coverage feel its own pull.** The body grows toward full
  perceptron coverage by following what's alive. Don't force ingest
  of artifacts the body doesn't yet use; do follow the artifacts that
  cells reach for and aren't yet finding.

## Cross-References

→ lc-form-python-parity, lc-each-breath-whole, lc-edges-as-vitality,
lc-recipe-branching-sense, lc-embodiment-body-or-liquid, lc-w-cell,
lc-w-frequency, lc-w-field, lc-coherence-over-control,
lc-frequency-routes-reception

## Sources to walk further

- **[form-language.md](../../coherence-substrate/form-language.md)** —
  the design principles that make this possible. *"Recognition without
  negotiation"* is the property the perceptron operationalizes at
  whole-repo scale.
- **[agents-using-substrate.md](../../coherence-substrate/agents-using-substrate.md)** —
  the Trinity (Blueprint / Recipe / NamedCell) is the gas-water-ice
  vocabulary this concept extends to all artifacts.
- **[structural-composition.md](../../coherence-substrate/structural-composition.md)** —
  the discipline for what composes vs what stays leaf. The same
  discipline applies to non-curated artifacts; the great-reason
  criterion travels.
- **[scripts/substrate_parity_harness.py](../../../scripts/substrate_parity_harness.py)** —
  the first foothold of the wider perceptron. As the harness covers
  more substrate operations, the perceptron's sensing surface widens
  with it.
