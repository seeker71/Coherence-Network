# North-star compiler — the streaming, content-addressed BMF/BML core

The north star — a small, generic, streaming, cursor-based recipe-emitter whose
content-addressing makes exploring parse branches an order of magnitude cheaper than a
copying parser — **is already the live BML compile path.** It is not a future rewrite.
`g-parse`, the `Match` engine in [`bmf-grammar.fk`](../../form/form-stdlib/bmf-grammar.fk)
over [`bmf-core.fk`](../../form/form-stdlib/bmf-core.fk)'s pure-functional cursor, sits
**inside the compile FLOOR**: `fsc-compile-section-recipe` parses every high-level
section through it (`g-parse(bml-grammar)`), and it is proven three-way by the
`bmf-core` / `bmf-grammar` / `bmf-langs` / `literals` bands.

So this doc records what is **already reached**, and names honestly what **remains** —
which is not building the engine, but *releasing the old tissue it made redundant* and
*densifying its coverage*.

## Already reached

- **The engine is the compile path.** `g-parse`, `g-rule`, `cur-peek`, `cur-advance`
  are all in the FLOOR (`reachable-from fsc-compile-section-recipe`). The BML compile
  doesn't *move toward* the cursor engine — it *runs on* it. The architecture is drawn
  in [`bmf-architecture.form`](bmf-architecture.form) (a cursor over surfaces, the
  Pattern/Template/Grammar blueprints, the one `Match` engine, the self-hosting
  fixpoint); the multi-language convergence in
  [`grammars-from-the-cursor.form`](grammars-from-the-cursor.form), proven by
  `bmf-langs-band` — six languages' function + `if` rules all intern to one `~Function`
  / one `~Cond` NodeID. The whole-picture map is
  [`kernels/BMF_BML_COMPILER_PICTURE.md`](../../kernels/BMF_BML_COMPILER_PICTURE.md).
- **The cheap branching is structural, not aspirational.** `bmf-core.fk`'s cursor is
  pure-functional: every advance returns a new cursor, a checkpoint *is* an earlier
  cursor value, restore *is* returning to it, and backtracking leaves no sediment
  because nothing was mutated. A copying parser pays for every speculative branch by
  duplicating state; this engine doesn't copy — and because the kernel interns every
  recipe **by content**, the emit side shares too:
  - **shared structure for free** — two branches that agree on a prefix share its
    interned nodes; no copy.
  - **discarded branches cost nothing** — an abandoned parse leaves interned nodes
    unreferenced (GC'd); you never paid to copy them.
  - **automatic memoization** — re-deriving the same sub-recipe returns the same NodeID.

  That *is* the order of magnitude: branching is pointer-sharing, not state-copying.
- **It is a sibling of the two walks already in the body.**
  [`name-check.fk`](../../form/form-stdlib/name-check.fk) (the resolution walk) and
  [`reachability.fk`](../../form/form-stdlib/reachability.fk) (the closure walk) share
  the same node-dispatch shape; the compile emitter is the third — accumulating recipes
  instead of diagnostics or a reached set.

## The ground that made it swappable and measurable

Two pieces laid recently turn "the engine is the compile path" into "the engine can
evolve safely":

- **A pinned, self-contained bootstrap** ([#2587]). The source-compile no longer
  re-reads the stdlib `.fk` live on every section — it loads one self-contained
  bootstrap `.fkb` (every recipe it uses bundled, emitted by the same kernel that runs
  it). So the core can be **densified under a stable artifact** without the stdlib-drift
  brittleness that used to bite (the g-parse panic, the #2490 operator drift). The
  bootstrap is the seam.
- **A measured floor** ([`bmf-bootstrap-floor-audit.md`](../system_audit/bmf-bootstrap-floor-audit.md),
  via `reachability.fk`, #2588/#2589). Of 502 bootstrap defns, **146 are the FLOOR**
  (the minimum that compiles any section — and the cursor engine is in it), **91 are
  STORE** (ontology load + runtime), and **265 are releasable** old tissue. The floor
  is the engine; the 265 is what clears away.

## What remains — release and densify, not rewrite

The work is *release inside the build*, never bulk deletion ahead of proof. The 265
releasable defns are static-analysis candidates (the audit now follows higher-order
callbacks, but a function stored in a variable and called later is still missed — see
the audit's caveat), and the preludes (`bml.fk`, `source-compiler.fk`, the grammar) are
actively-tended shared ground. So, per construct the old path still owns:

1. **Densify coverage** where the cursor grammar doesn't yet reach. Real gap: a
   `section [form.route]` written in TS-like member syntax (`member x: T;`, `def m(){}`,
   bare `field = expr;`, `template`) lowers to an empty recipe because the BML grammar is
   type-first — the gate from #2581 names the resulting unbound symbol. Each such surface
   variant is one bag of cursor rules added to the grammar.
2. **Prove parity** — the newly-covered construct's output is byte-identical to the
   current path's, three-way (Go/Rust/TS) via `form/validate.sh`.
3. **Release the old tissue** the cursor engine now subsumes — re-running the floor audit
   to confirm a candidate dropped to genuinely unreached, with a per-candidate
   indirect-ref check before composting.

This keeps the compiler working at every step and coordinates cleanly with whoever owns
the grammar at the time — the source-compiler is shared, actively-tended ground, so the
release happens *with* its tenders, as the engine covers each construct, not around them.

## Constraints (the body's grain)

- **BML-first.** The core is Form recipes + grammar, not a Python/TS reimplementation;
  carriers stay thin and last.
- **Three-way.** Every construct's parity is proven across Go/Rust/TS, not asserted.
- **Content-addressed.** The cheap-branching property is the whole point — the design
  leans on intern + structural sharing, not around them.
- **Pinned-bootstrap discipline.** The core is densified under a self-contained artifact;
  no live coupling to a moving stdlib.

## The measure to watch

Two honest readings that move together: the bootstrap's must-store count *shrinking*
(toward the FLOOR, then below it as releases land) and the grammar's *coverage growing*
(fewer sections that lower to empty). When every section the old tissue once handled
compiles through the cursor engine, with that tissue released, this north star is
reached — and the next one (a measured branch-cost against a copying baseline) is named.
