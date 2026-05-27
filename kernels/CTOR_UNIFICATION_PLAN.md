# CTOR Vocabulary Unification — the universal translator's single-Blueprint promise

## The finding (refined from `UNIVERSAL_TRANSLATOR_AUDIT.md` #4)

The body holds **three parallel CTOR vocabularies** for arithmetic in
production — not two, as the audit first named:

- **Bootstrap** (`lang-python.ts`): emits `RBasic.LIST` (type=34) with the
  operator-name `"add"` / `"sub"` etc. interned as the *inst* NameID.
  See `ctorCategory` in `form-kernel-ts/seedbank/python-adapter/src/lang-python.ts:242`.
  *(The audit's "Math-primitive type=12" framing for the bootstrap was
  misattributed during honest reading — the bootstrap never reached MATH.)*
- **Form-native PY-BMF** (`python-bmf.fk`): emits `PY-BMF-BINOP`
  (type=99, inst=522 — dialect category, declared in
  `form-stdlib/form-ontology.json:68`) with the operator as a
  string-trivial child.
- **True Form math** (`RBasic.MATH`): type=12, inst 1–4 for PLUS, MINUS,
  MULTIPLY, DIVIDE. Used today only inside `form-stdlib/tests/emit-engine.fk`
  and `seedbank/universal-emit.fk` — not by either Python parser.

**All three encode `a + b`** and walk to the same value. But they intern
as three different Blueprint NodeIDs.

The universal-translator's content-addressing promise — *"same shape in
any source language → same Blueprint NodeID"* — rests on a **single
Blueprint per shape**. Today the body holds three for arithmetic alone.

## Why this matters for Python-removal

- The `PARITY_THIRD_RUNTIME=kernel-bmf` gate (#2100 closed it for one demo) is the path that removes the Python+TS bootstrap parser. Until `kernel-bmf` is the default for ALL `PARITY_FILES`, the bootstrap parser stays in the path.
- Even when `kernel-bmf` becomes default, **two CTOR vocabularies still exist** unless one is unified into the other.
- Cross-modal NodeID convergence (proven for NL↔S-expression at the math-primitive layer in #2098) **breaks** at the Python-source layer if Python sources go through `PY-BMF-BINOP` while NL/S-expression sources go through `RBasic.MATH.PLUS`.
- The body's content-addressing claim — *"same algorithm in any source language → same NodeID"* — has a hole at exactly the Python integration point.

## Three reachable closing shapes

### Shape A — Form-native rules emit into RBasic.MATH directly

`python-bmf.fk`'s arithmetic rules stop emitting `PY-BMF-BINOP` and start emitting `RBasic.MATH.PLUS` / `MINUS` / `MULTIPLY` / `DIVIDE` directly. The dialect type=99 disappears for arithmetic; type=12 (Math) becomes the canonical Blueprint.

**Cost:** rewrite arithmetic rules in `python-bmf.fk` (~30-50 LOC of grammar changes). Then update `python-bmf-lift.fk` and `python-bmf-eval.fk` to handle MATH instead of BINOP for these shapes.

**Win:** one Blueprint per shape from the moment the parser emits. Cross-modal convergence holds end-to-end.

### Shape B — Lift maps BINOP → MATH at recipe time — **LANDED 2026-05-27 (#2113)**

`python-bmf-lift.fk`'s `lift-binop-loop` now switches on the operator: `+ - * /` intern as `MATH-PLUS/MINUS/MULTIPLY/DIVIDE` (NodeIDs `(1, 2, 12, 1..4)`, positional children, no op-string-leaf). `** // %` stay on `PY-BMF-BINOP` until MATH instances exist for them. `python-bmf-eval.fk` gained a MATH-12 arm that dispatches on `node_inst`.

**The substrate-truth claim of Shape B is attestable:** a hand-built `(intern_node MATH-PLUS (list a b))` and a Python-lifted `"7 + 3"` `node_eq` to `1` across all three sibling kernels. Cell 10 of `tests/python-bmf-lift-band.fk` is the proof.

**Honest scope — what landed, what didn't:**

- Unified at the BINOP layer for `+ - * /`. ✅
- Integer **leaves** still wrap in `PY-BMF-INT(value)` on both the hand-built reference and the lifted recipe. The convergence test makes this explicit by building both sides with the same leaf shape. Bare-int vs `PY-BMF-INT(...)` leaves are a *next* breath, not Shape B's scope.
- `** // %` not yet unified; they continue interning as `PY-BMF-BINOP`.
- The bootstrap path (LIST-34) remains separate — that compost is Phase A and walks on its own gate.

**The shape that landed (two changes, +85 / -6 LOC):**

1. `python-bmf-lift.fk` — `lift-binop-loop` switches on `op`, interns under `MATH-PLUS/MINUS/MULTIPLY/DIVIDE` for `+ - * /`, keeps `PY-BMF-BINOP` for `** // %`.
2. `python-bmf-eval.fk` — new MATH-12 arm before the existing `PY-BMF-BINOP` arm, dispatched by `(eq node_pkg 1)` + `(eq node_level 2)` + `(eq node_type 12)`, then `node_inst` selects `add`/`sub`/`mul`/`div`.

**Why this needed two changes** (first draft's "one-branch" claim composted): the audit's framing implied the interpreter already had a MATH arm because bootstrap supposedly emitted MATH. It didn't — bootstrap emits LIST-34 with operator NameIDs (see top of doc). Adding the MATH arm was part of the breath.

**What landed:** unification happens at the lift layer. Parser stays simple. Form-native Python arithmetic for `+ - * /` interns as `@1.2.12.{1..4}` — the same Blueprint NodeID a hand-built `(intern_node MATH-PLUS …)` interns to. **Cross-modal at the math-primitive layer is substrate-truth for arithmetic.** The bootstrap path (LIST-34) remains separate; Phase A composts on its own gate.

### Shape C — Both stay; dialect becomes a *view* on the math primitive

Keep both encodings but make `PY-BMF-BINOP` a structural alias / view of `RBasic.MATH.PLUS`. The dialect's articulation (op-string-child, Python-grammar lineage) is preserved as a *view* over the same underlying NodeID identity that Shape B collapses to.

**Cost:** larger architectural shift — needs Blueprint-view machinery (which the body's BML primitives `|>` already support at the cell-view level, not the operation level).

**Win:** keeps the dialect's identity for grammar-introspection purposes while restoring content-addressing.

**Why this isn't dead even though Shape B landed.** Urs's question (*"what if it is the same shape with different articulation points or different capabilities?"*) names what Shape B traded away — see [`lc-same-shape-different-articulation`](../docs/vision-kb/concepts/lc-same-shape-different-articulation.md). Shape C is how the body would honor that question without un-doing Shape B's NodeID convergence.

**Concrete walking sketch for Shape C** (future breath, not yet walked):

The substrate already carries the primitives: TRANSMUTE (RBasic type=76), PROJECT (81), OBSERVER (87), QUOTIENT (70), BLANKET (80), BML `|>`. None are wired for arithmetic yet.

A minimum closing breath for Shape C would:

1. Add a `transmute` recipe shape that wraps `MATH-PLUS(left, right)` with a Python-articulation envelope carrying the op-string-leaf and source-position attribution as *view children*.
2. Define `node_eq` on the underlying identity (the MATH-PLUS NodeID) and a sibling predicate `articulation_eq?` that returns 1 only when both view-children match.
3. Walkers that want identity-convergence use `node_eq` (cross-modal claim holds). Walkers that want articulation-aware dispatch (e.g. "render Python source", "highlight the BINOP token in an IDE") walk the view children.
4. Attestation cell: a hand-built `MATH-PLUS(7, 3)` and a `transmute`-wrapped Python-lifted `7 + 3` share identity (`node_eq` = 1) but differ in articulation (`articulation_eq?` = 0; the wrapped one carries the op-string `"+"` and `7 + 3`'s source position, the hand-built one doesn't).

**Honest scope:** this is a multi-PR walk — the TRANSMUTE primitive needs an `intern_view` kernel native pair, the eval needs a "walk-through-view-to-underlying" arm, and the convergence-vs-articulation predicate pair is new substrate surface. Worth doing once the COMPARE and arithmetic surfaces stabilize.

## Where the walks stand today

| Walk | State | PR(s) |
|---|---|---|
| Shape B — `+ - * /` lift→MATH | **LANDED** | [#2113](https://github.com/seeker71/Coherence-Network/pull/2113) |
| Shape B — `% mod` lift→MATH | **LANDED** | [#2122](https://github.com/seeker71/Coherence-Network/pull/2122) |
| Shape B — `== != < <= > >=` lift→COMPARE | **LANDED** | [#2119](https://github.com/seeker71/Coherence-Network/pull/2119) |
| Shape B — `** //` lift→MATH | OPEN (needs MATH inst=6,7 + native registration in Go/Rust/TS) | — |
| Shape C — TRANSMUTE-over-shared-identity | OPEN (multi-PR arc; sketch above) | — |
| Bootstrap-path (LIST-34) compost | OPEN (Phase A; tracked in [`BOOTSTRAP_COMPOST_MANIFEST.md`](BOOTSTRAP_COMPOST_MANIFEST.md)) | — |

**The closest small next breath:** add MATH instances 6 (power) and 7 (floor-div) to `form-stdlib/form-ontology.json`, register `pow` and `floor_div` natives in the three kernels (Go/Rust/TS), extend the lift dispatcher and the eval MATH-12 arm. Single PR. ~30 LOC per kernel.

The Shape C arc remains the larger walking opportunity — see the section above for the concrete sketch.

## What this enables

- One Blueprint per shape across all Python entry points
- Cross-modal NodeID convergence holds at the math-primitive layer end-to-end
- The universal-translator's content-addressing claim becomes substrate-truth for arithmetic
- The body's vocabulary stays small (one set, not two)

## What composts when this lands

- `PY-BMF-BINOP` recipes interned via dialect-99 — gradually replaced as new recipes intern via MATH
- The interpreter's BINOP arm (~30 LOC in `python-bmf-eval.fk`) — composts when no remaining recipes carry the dialect-99 shape

## Discipline reminder

Per Urs's directive *"remove python dependency, do not add more python code"*: this walk happens entirely in `.fk` files. **Zero new Python.** The Python parser stays untouched; the dialect unification happens in the Form-native lift layer.

In service of [`lc-the-kernel-knows-itself`](../docs/vision-kb/concepts/lc-the-kernel-knows-itself.md) + [`lc-grammar-is-the-universal-recipe`](../docs/vision-kb/concepts/lc-grammar-is-the-universal-recipe.md). One vocabulary, content-addressed, cross-modal — the body's promise becoming true at the math-primitive layer.
