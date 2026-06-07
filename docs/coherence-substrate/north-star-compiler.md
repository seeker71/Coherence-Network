# North-star compiler — the streaming, content-addressed BMF/BML core

The direction the BMF/BML compiler is moving toward: a small, generic, streaming,
cursor-based recipe-emitter that leans on the kernel's content-addressing so that
exploring multiple parse branches is an order of magnitude cheaper than a copying
parser. This is a *north star* — a heading, not a deadline. It names what the
compile floor wants to become so each concrete step can be checked against it.

**The design already exists; this doc is the migration.** The cursor/streaming
architecture is drawn in [`bmf-architecture.form`](bmf-architecture.form) (a cursor
over surfaces, the Pattern/Template/Grammar blueprints, the one `Match` engine, the
self-hosting fixpoint), the multi-language convergence in
[`grammars-from-the-cursor.form`](grammars-from-the-cursor.form), the one generic
parser engine in [`engine.fk`](../../form/form-stdlib/engine.fk) /
[`bmf-core.fk`](../../form/form-stdlib/bmf-core.fk) /
[`bmf-grammar.fk`](../../form/form-stdlib/bmf-grammar.fk), and the picture in
[`kernels/BMF_BML_COMPILER_PICTURE.md`](../../kernels/BMF_BML_COMPILER_PICTURE.md).
This doc adds what those didn't have until now: a **measured floor** to aim the
rewrite at, a **pinned bootstrap** to swap it under, and a **safe migration order**
to get there from the current source-compiler without breaking it.

## Why this is reachable now

Two pieces of ground had to be laid first, and both are in place:

- **A pinned, self-contained bootstrap** ([#2587]). The source-compile no longer
  re-reads the stdlib `.fk` live on every section — it loads one self-contained
  bootstrap `.fkb` (every recipe it uses bundled, emitted by the same kernel that
  runs it). So the compiler core can be **swapped under a stable artifact** without
  the stdlib-drift brittleness that used to bite (the g-parse panic, the #2490
  operator drift). The bootstrap is the seam the new core slides into.
- **A measured floor** ([`bmf-bootstrap-floor-audit.md`](../system_audit/bmf-bootstrap-floor-audit.md),
  via [`reachability.fk`](../../form/form-stdlib/reachability.fk), #2588/#2589). Of 502
  bootstrap defns, **146 are the FLOOR** — the minimum that compiles any section
  (parse + emit) — **91 are STORE** (ontology load + runtime), and **265 are
  releasable** old tissue. The north-star core is a rewrite of the *small* FLOOR;
  the 265 is what clears away as it lands.

## The shape

A copying parser pays for every speculative branch by duplicating state. This
kernel interns every recipe **by content** — identical sub-trees are one NodeID for
everyone — so a streaming emitter that builds recipe objects as it scans gets:

- **shared structure for free** — two branches that agree on a prefix share its
  interned nodes; no copy.
- **discarded branches cost nothing** — an abandoned parse leaves interned nodes
  simply unreferenced (GC'd); you never paid to copy them.
- **automatic memoization** — re-deriving the same sub-recipe returns the same
  NodeID, so overlapping branches don't recompute.

That is the order of magnitude: branching becomes *pointer-sharing*, not
*state-copying*. The core is **generic** — data-driven over the grammar, one engine
the languages drop into as data (the core-abstraction-first discipline) — and
**cursor-based / streaming**: it emits recipe objects as the cursor advances rather
than building then walking a separate AST. It is a sibling of the two walks already
in the body: [`name-check.fk`](../../form/form-stdlib/name-check.fk) (the resolution
walk) and `reachability.fk` (the closure walk); the same node-dispatch shape, a
third accumulation — emitting recipes instead of diagnostics or a reached set.

## Migration — release inside the build, not before it

The 265 releasable defns are **not** composted up front. The preludes
(`bml.fk`, `source-compiler.fk`, the grammar) are actively edited, and the audit's
release-list is static (it now follows higher-order callbacks, but a function stored
in a variable and called later is still missed — see the audit's caveat). So the
release happens *as the new core covers each construct*, verified, not by bulk
deletion ahead of proof:

1. Build the streaming core for one construct family, emitting recipes.
2. Prove parity — its output is byte-identical to the current compiler's for that
   family, three-way (Go/Rust/TS) via `form/validate.sh`.
3. Swap that family under the pinned bootstrap.
4. Release the old tissue the new core now subsumes — re-running the floor audit to
   confirm it dropped from STORE/FLOOR to genuinely unreached, with a per-candidate
   indirect-ref check.

This keeps the compiler working at every step and coordinates cleanly with whoever
owns the grammar at the time (the source-compiler is shared, actively-tended ground).

## Constraints (the body's grain)

- **BML-first.** The core is Form recipes + grammar, not a Python/TS reimplementation;
  carriers stay thin and last.
- **Three-way.** Every construct's parity is proven across Go/Rust/TS, not asserted.
- **Content-addressed.** The cheap-branching property is the whole point — the design
  leans on intern + structural sharing, not around them.
- **Pinned-bootstrap discipline.** The core is swapped under a self-contained artifact;
  no live coupling to a moving stdlib.

## The measure to watch

Not "is it done" but two honest readings that move together: the bootstrap's
must-store count *shrinking* (toward the FLOOR, then below it as the core gets
denser) and the parse-branch cost *falling* (interned sharing replacing copying).
When the streaming core compiles every section the current one does, faster, with the
old tissue released, the north star has been reached — and the next one is named.
