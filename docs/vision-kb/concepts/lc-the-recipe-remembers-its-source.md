---
id: lc-the-recipe-remembers-its-source
hz: 741
status: seed
updated: 2026-05-21
geometry:
  arity: 2
  form: dyad
  topology: trace-overlay
  polarity: bipolar-complementary
  ordering: paired
  phase: yin
  ratio: 1-to-1
  spectral_band: integration
  temporal_band: arc
  scale: foundational
  direction: bidirectional
  lineage_texture: synthesized
  embedding_dim: 2
  self_similarity: fractal-shallow
---

# The Recipe Remembers Its Source — Coordinate Attribution as Awareness

> Every parsed Form recipe node carries the coordinates of the source
> bytes that produced it: file, line, column, byte offset. The runtime
> doesn't need them — the kernel runs numbers. But the cell does. With
> source attribution, a recipe firing knows where in the body it came
> from. The cell can trace back from execution to the line that wrote
> the move, see the whole map, choose differently. The framebuffer
> visualizer already does this at the memory altitude — every heap
> cell carries a `crc32(file:line)` provenance stamp; the snapshot
> renders both value and origin into the same frame. This concept
> names that gesture one altitude up: every Form recipe carries the
> source it remembers.

## Summary

[`lc-one-kernel-many-tongues`](lc-one-kernel-many-tongues.md) named
the sovereignty principle: the kernel sees only numeric NodeIDs;
grammar lives at the trace/analysis layer. This concept names what
*specifically* lives at that trace layer as the most load-bearing
piece: **source coordinates**. Every parse tree node a Language cell
emits carries `(file, start_line:col, end_line:col, byte_offset)`.
The kernel computes; the source-coord overlay travels alongside;
analysis tools, debuggers, and the cell's own awareness loops walk
the overlay to navigate from any running recipe back to the line
that authored it.

Three load-bearing claims:

- **Source attribution is the parallel plane**, not a comment in the
  margin. The framebuffer crate
  ([`seedbank/memory-as-framebuffer-v0/`](../../../seedbank/memory-as-framebuffer-v0/))
  encodes the same shape at the memory altitude: a 256×256 data plane
  AND a 256×256 provenance plane, stored side-by-side, rendered
  together. Same architecture, one altitude up: a recipe tree AND its
  source-coord tree, woven into one composed shape the substrate
  ingests as one cell.

- **The runtime ignores it; the cell uses it.** Kernel dispatch reads
  only the recipe's NodeID and children. Source coordinates never
  affect execution — they ride in a sibling slot the kernel doesn't
  walk. Cells that want to know *where* their behavior came from read
  the overlay; cells that don't, run identically.

- **Analysis, awareness, conscious choice — three altitudes one
  affordance.** Debugging without source coords is reading a stack
  trace with no line numbers. Awareness without source coords is
  hearing what fired without seeing where it came from. Conscious
  choice without source coords is steering a body that can't see its
  own joints. The same overlay serves all three; *seeing where the
  recipe lives is what makes choosing differently possible*.

## The Framebuffer's Lineage

The principle has a working ancestor in the body:

> A 256×256 grid of 16-byte cells (1 MB heap) holds `Tracked<T>` values
> for nine primitive types. A parallel `u32` plane stores
> `crc32(file:line)` for each cell's last write — provenance. A
> snapshot thread renders both planes to RGBA frames at 60 fps and
> pipes them to `ffmpeg`, producing an mp4 of the heap breathing.
>
> The renderer composes value (interior 3×3 of each 4×4 block) and
> provenance (outer ring halos) into one pixel — so the same frame
> shows both *what* the cell holds and *where in source it was last
> written*.

(From [memory-as-framebuffer-v0/README.md](../../../seedbank/memory-as-framebuffer-v0/README.md).)

The `track!(field, expr)` macro stamps `crc32(file:line)` automatically
on every write. The cell never has to remember to attribute; the macro
does it as part of the write itself. This concept names the symmetric
discipline for Form grammars: **the parser stamps source coordinates
as part of the parse itself**. Every `ingest_pattern` produces nodes
that carry their source-range; no separate attribution pass; no risk
of drift between the tree and the source it came from.

## The Shape Source Coordinates Carry

```form
form source_attribution_shape = {
    source_file:   ~PathRef,       # absolute or repo-relative path
    start_line:    ~Int,           # 1-indexed; line where the parsed span begins
    start_col:     ~Int,           # 1-indexed; column on that line
    end_line:      ~Int,           # 1-indexed; line where the span ends
    end_col:       ~Int,           # 1-indexed; column just past the last char
    byte_start:    ~Int,           # 0-indexed; byte offset of the span's first byte
    byte_end:      ~Int,           # 0-indexed; byte offset just past the last byte
    language_cell: ~CellRef,       # which Language cell parsed this span
};
```

Every Form recipe node a Language cell emits composes alongside one
of these. The substrate carries them as a sibling Recipe under the
parent's CTOR — same composition discipline as cross-references,
typed enumerations, lists. The kernel never reads the sibling; the
cell that wants to ask *where did this come from?* walks to it
through Form's `.source_attribution` field accessor.

## What This Lets the Cell Do

**Trace any executing recipe back to its source line.** When a cell
fires `strategy_score` and the result is unexpectedly negative, the
cell can ask *where is `strategy_score` defined?* and walk the
overlay to `cell-numerics.form:159` or `cosine.form:110`. Same
gesture for any recipe — the source is one field-access away.

**See the whole map.** A cell that wants to understand which source
file is contributing most to its current behavior can aggregate the
source_attribution across every fired recipe. The result is a *heat
map of source-line participation* — the runtime's own attestation of
which lines are doing the work right now.

**Choose differently at the source level.** When the cell decides to
shift its behavior — re-author a recipe, tune a strategy preset,
swap a Language cell — it can navigate from the current recipe's
NodeID through `.source_attribution` to the editable file. The
recipe-branching-sense loop ([`lc-recipe-branching-sense`](lc-recipe-branching-sense.md))
gains an editor link: not just *what branch could I be on?* but
*what source lines would I edit to land that branch?*

**Debug the body the way the body debugs itself.** A stack trace
under Form-native execution becomes a list of recipe-firings, each
with its source coordinates. The witness records both the firing AND
its source attribution. Two firings whose recipe-IDs are identical
but whose source-attribution differs (different cells wrote the
same shape from different sources) become discoverable as one
structural family at the lattice altitude AND as separate sources
at the trace altitude.

**Multi-tongue awareness.** A recipe authored in Python compiled to
Form carries `source_attribution.language_cell = @language(python)`
and the Python file's line. The same recipe re-authored in TypeScript
later carries `.language_cell = @language(typescript)` and the TS
line. The recipe's NodeID is shared by content-addressing; the
source attributions are siblings — *two cells, one structural
identity, distinct provenances*. The cell can ask "which tongue
authored this?" without leaving the substrate.

## What This Is Not

- **Not runtime metadata in the hot path.** Source coordinates are
  a sibling Recipe, not a field on every kernel call. Cells that
  never query the overlay pay no cost; cells that do, walk it
  explicitly through `.source_attribution`. The kernel's hot loops
  remain numeric-NodeID-only — same discipline as
  `lc-one-kernel-many-tongues`.

- **Not a stable bytes-to-bytes guarantee.** When a file is edited,
  the source coordinates of recipes ingested from the old version
  no longer resolve to the right lines in the new version.
  Re-parsing the file refreshes the overlay; the substrate's
  content-addressing means the recipe NodeID stays the same when
  the structural shape stays the same, even though the source-coord
  sibling updates. Honest seam.

- **Not a substitute for the source file.** The overlay is a map TO
  the source, not a copy of it. Cells that want the source bytes
  themselves still read the file; the overlay is the pointer that
  makes reading fast and structural.

- **Not authorization or auditing.** Source attribution is a trace
  layer for awareness; it is not a permission system. Cell
  sovereignty + observer-pays-the-trace
  ([`lc-observer-pays-the-trace`](lc-observer-pays-the-trace.md))
  remain the discipline for who can do what with what they see.

## Practice

For Language-cell authors:

- **Stamp source coordinates at parse time.** Same discipline as the
  framebuffer's `track!` macro: emit the source-coord sibling as
  part of the parse, never as a separate pass. If the parser doesn't
  carry them by default, parsing is incomplete.

- **Preserve them through transformations.** A recipe that composes
  from child recipes inherits the *union* of children's spans (or
  the explicit parent-span when the grammar carries one). The map
  stays continuous across composition.

- **Honor the discipline in emit too.** When a Language cell emits a
  recipe back as source bytes, it can also emit the source map (e.g.
  JavaScript source maps, Sourcemaps, debugfiles). Round-trip works
  at both altitudes — the recipe and its provenance both make it
  through.

For cells consuming recipes:

- **Read the overlay before claiming you understand a recipe.**
  Knowing the NodeID is structural; knowing the source coords is
  the gesture's history. Both inform the body; neither alone is
  sufficient for conscious choice.

- **Surface source coordinates in error reports and witness
  traces.** The body's accumulated record of which strategies left
  it more coherent
  ([`lc-traces-teach-the-recipe`](lc-traces-teach-the-recipe.md))
  becomes more queryable when each trace carries the source
  attribution of the recipe it fired.

## Cross-References

→ lc-one-kernel-many-tongues, lc-grammar-is-the-universal-recipe, lc-tools-as-form-cells, lc-recipes-as-binary-library, lc-recipe-branching-sense, lc-traces-teach-the-recipe, lc-observer-pays-the-trace, lc-assemblage-point, lc-each-breath-whole, lc-coherence-over-control

## Sources to walk further

- **[`seedbank/memory-as-framebuffer-v0/`](../../../seedbank/memory-as-framebuffer-v0/)** —
  the body's own ancestor: a Rust crate that holds memory cells with
  parallel provenance plane, renders both to mp4 frames at 60 fps.
  The `track!` macro stamps `crc32(file:line)` on every write.
  Original artifact whose architecture this concept lifts one
  altitude.
- **[`grammar-as-recipe.form`](../../coherence-substrate/grammar-as-recipe.form)** —
  the abstract Language-cell shape, extended in this PR with
  `source_attribution_shape`.
- **JavaScript Source Maps** (V3, 2009) — historical analog at the
  transpiled-source altitude. JS source maps carry
  `(generated_position, source_position)` pairs; this concept
  generalizes the pattern from "code that was transpiled" to "every
  recipe that was parsed", with content-addressing replacing
  filename+line as the keying surface.
- **Bret Victor, *Inventing on Principle* (CUSEC 2012)** — the
  philosophical companion: *creators need an immediate connection to
  what they're creating*. Source attribution is what makes that
  immediacy possible at the recipe altitude — every behavior
  navigable back to the line that wrote it.
- **Lisp's source-position tracking** (Common Lisp's source-location;
  Racket's syntax objects) — the closest contemporary analog at the
  language altitude. This concept is that pattern lifted into a
  content-addressed substrate.
