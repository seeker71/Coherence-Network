# CTOR Vocabulary Unification — the universal translator's single-Blueprint promise

## The finding (from `UNIVERSAL_TRANSLATOR_AUDIT.md` #4)

The body holds **two parallel CTOR vocabularies** in production:

- **`CTOR.add` (type=12)** — bootstrap path: `lang-python.ts` parses Python arithmetic and emits `CTOR.add` via the existing Math-primitive vocabulary
- **`PY-BMF-BINOP` (type=99)** — Form-native path: `python-bmf.fk` rules produce `PY-BMF-BINOP` recipes (dialect type 99) carrying the operator as a string-trivial child

**Both encode `a + b`.** They walk to the same value when executed. But they have **different Blueprint NodeIDs**.

The universal-translator's content-addressing promise — *"same shape in any source language → same Blueprint NodeID"* — rests on a **single Blueprint per shape**. Today we have two.

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

### Shape B — Lift maps BINOP → MATH at recipe time

`python-bmf-lift.fk` (already exists from #2100) translates statement-tree → PY-BMF recipes. Extend it: when it sees a BINOP shape, intern as `RBasic.MATH.PLUS` (etc.) instead of `PY-BMF-BINOP`.

**Cost:** minimal — one branch addition in `python-bmf-lift.fk`. Doesn't touch the parser.

**Win:** unification happens at the lift layer. Parser stays simple. NodeIDs converge at the recipe level.

### Shape C — Both stay; rename dialect-99 to be a *view* on MATH

Keep both encodings but make `PY-BMF-BINOP` a structural alias / view of `RBasic.MATH.PLUS`. Cross-references the same Blueprint through different lenses.

**Cost:** larger architectural shift — needs Blueprint-view machinery (which the body's BML primitives `|>` already support at the cell-view level, not the operation level).

**Win:** keeps the dialect's identity for grammar-introspection purposes while restoring content-addressing.

**Recommendation:** Shape B (lift-time mapping) — smallest closing breath, restores content-addressing immediately, doesn't require parser-grammar surgery.

## Concrete next breath

In `form/form-stdlib/python-bmf-lift.fk`:

```form
;; Where BINOP is lifted today (probably around lift-binary-op):
;; (intern_node @PY-BMF-BINOP (list operator left right))

;; Change to:
;; (let math-arm (case operator
;;     "+" @RBasic.MATH.PLUS
;;     "-" @RBasic.MATH.MINUS
;;     ...))
;; (intern_node math-arm (list left right))
```

The `python-bmf-eval.fk` interpreter's BINOP arm composts; the existing MATH arm picks up the work.

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
