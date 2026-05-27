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

### Shape B — Lift maps BINOP → MATH at recipe time

`python-bmf-lift.fk` (already exists from #2100) translates statement-tree → PY-BMF recipes. Extend it: when it sees a BINOP shape with `+ - * /`, intern as `RBasic.MATH` (1, 2, 12, 1–4) instead of `PY-BMF-BINOP`.

**Cost (refined honestly):** *not* the one-branch change the first draft claimed.
The honest closing breath is **two changes**:
1. `python-bmf-lift.fk:206` — in `lift-binop-loop`, switch on `op` and intern
   under `MATH-PLUS/MINUS/MULTIPLY/DIVIDE` for `+ - * /`; keep
   `PY-BMF-BINOP` for `** // %` (no MATH instances exist for those today).
2. `python-bmf-eval.fk:322` — add a MATH-12 arm that dispatches on the
   instance (1=add, 2=sub, 3=mul, 4=div) and walks the two children.
   The existing `PY-BMF-BINOP` arm stays for `** // %` until those land
   in MATH too.

**Why the refinement:** the audit's first framing implied the interpreter
already had a MATH arm (because bootstrap supposedly emitted MATH). It
doesn't — bootstrap emits LIST-34 with operator NameIDs (see top of doc).
Adding the MATH arm is part of the breath.

**Win:** unification happens at the lift layer. Parser stays simple.
Form-native Python arithmetic interns as `@1.2.12.{1..4}` — the same
Blueprint NodeID the (pure-Form) `(intern_node CAT-PLUS …)` interns to.
**Cross-modal at the math-primitive layer becomes substrate-truth for
arithmetic.** The bootstrap path (LIST-34) remains separate until Phase A
composts — but that compost is named and walking.

### Shape C — Both stay; rename dialect-99 to be a *view* on MATH

Keep both encodings but make `PY-BMF-BINOP` a structural alias / view of `RBasic.MATH.PLUS`. Cross-references the same Blueprint through different lenses.

**Cost:** larger architectural shift — needs Blueprint-view machinery (which the body's BML primitives `|>` already support at the cell-view level, not the operation level).

**Win:** keeps the dialect's identity for grammar-introspection purposes while restoring content-addressing.

**Recommendation:** Shape B (lift-time mapping) — smallest closing breath, restores content-addressing immediately, doesn't require parser-grammar surgery.

## Concrete next breath

In `form/form-stdlib/python-bmf-lift.fk:206` (the `lift-binop-loop` intern site
that emits `PY-BMF-BINOP` for every `op`):

```form
;; Today:
;; (intern_node PY-BMF-BINOP (list left (intern_trivial_string op) rhs))

;; Replace with a math-or-binop choice. Numeric NodeIDs for MATH (type=12):
;; (let MATH-PLUS     (make_nodeid 1 2 12 1))
;; (let MATH-MINUS    (make_nodeid 1 2 12 2))
;; (let MATH-MULTIPLY (make_nodeid 1 2 12 3))
;; (let MATH-DIVIDE   (make_nodeid 1 2 12 4))
;;
;; (let new-left
;;     (if (str_eq op "+")  (intern_node MATH-PLUS     (list left rhs))
;;     (if (str_eq op "-")  (intern_node MATH-MINUS    (list left rhs))
;;     (if (str_eq op "*")  (intern_node MATH-MULTIPLY (list left rhs))
;;     (if (str_eq op "/")  (intern_node MATH-DIVIDE   (list left rhs))
;;     ;; ** // % stay on PY-BMF-BINOP until MATH gets those slots
;;     (intern_node PY-BMF-BINOP
;;         (list left (intern_trivial_string op) rhs)))))))

;; Then in form/form-stdlib/python-bmf-eval.fk:322, add a MATH arm before
;; the existing PY-BMF-BINOP arm:
;;
;; (if (and (eq (node_type cat) 12)
;;          (eq (node_pkg cat) 1)
;;          (eq (node_level cat) 2))
;;     (let lhs-val (py-eval (nth (node_children r) 0) env))
;;     (let rhs-val (py-eval (nth (node_children r) 1) env))
;;     (let inst (node_inst cat))
;;     (if (eq inst 1) (add lhs-val rhs-val)
;;     (if (eq inst 2) (sub lhs-val rhs-val)
;;     (if (eq inst 3) (mul lhs-val rhs-val)
;;     (if (eq inst 4) (div lhs-val rhs-val) (head (empty)))))))
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
