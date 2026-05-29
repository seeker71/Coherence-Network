# Compiler Gap Queue — Python→Form coverage, one construct per breath

> Why this exists: the strategy for `api/app/services/substrate/*.py` is
> **compile, don't rewrite** — feed each `.py` through the Form-native
> Python compiler to produce a `.fkb` that runs identically on the Form
> kernel or CPython. That is bullet 3 of Urs's 2026-05-21 directive
> ([`PYTHON_PIPELINE_STATUS.md`](PYTHON_PIPELINE_STATUS.md)). The blocker
> is **compiler coverage**: every Python construct the lifter can't handle
> is a file it can't compile. This queue tracks closing that gap, one
> construct per breath, each independently shippable.

## The pipeline (destination path, not the TS bootstrap)

```
.py source → form-stdlib/grammars/python-bmf.fk   (scanner + BMF rules — parses ~all of Python already)
           → form-stdlib/python-bmf-lift.fk        (statement/expr tree → PY-BMF-* recipes)   ← most gaps live HERE
           → form-stdlib/python-bmf-eval.fk        (walk PY-BMF-* recipes → runtime value)    ← some arms already shipped
```

The grammar already parses nearly every Python construct. The gaps are
almost all **lift** (and sometimes **eval**), never the scanner. That is
what makes each construct a small, isolated breath.

## The proven template (copy-paste, from the aug-assign breath #2168)

Adding one construct end-to-end is three edits:

1. **Lift** (`python-bmf-lift.fk`): write a `lift-X` that consumes the
   statement-tree / token list and returns `(intern_node PY-BMF-X children)`.
   For statements, add a dispatch branch in `lift-statement` (before the
   `kind "expr"` fallthrough). For expressions, add to `lift-primary`.
   - Token accessors: `tok-kind`, `tok-value`, `tok-op?`, `tok-name?`,
     `tok-int?`. Tokens are BMF objects.
   - `drop`, `nth`, `head`, `tail`, `reverse` available from core.fk.
   - A statement's classification: `python-statement-tree-kind` (first-token
     classifier) + `python-statement-tree-cpython-rule` (richer rule name).
     Probe an unknown construct with a `trace` to see what it classifies as
     before writing the branch — e.g. `x += 3` is `kind "expr"` /
     `rule "star_expressions"`, NOT its own kind. The lifter must catch it
     by token shape before the bare-expr arm.

2. **Eval** (`python-bmf-eval.fk`): if no arm exists, add
   `(if (node_eq cat PY-BMF-X) <arm> <rest>)` in `py-eval` (expressions,
   returns a value) or `py-eval-statement` (statements, returns
   `(py-stmt-result value env)`). Many arms are **already shipped** ahead of
   their lift — check the EVAL list below first; if it's there, you only
   write lift (the cheapest breath — this is exactly what aug-assign was).
   - `py-binop-apply` handles `+ - * / % //`; `py-compare-apply` handles
     `== != < <= > >=`. Reuse them — lift emits the **base** op string.

3. **Test** (`python-bmf-lift-band.fk`): add `(let cellN-value
   (py-bmf-run-text "…python…"))` + `(let cellN-score (if (eq cellN-value
   EXPECTED) POINTS 0))`, and add `cellN-score` to the final `(sum …)`.
   Expected value must match CPython. Per-cell offsets make a regression
   name itself.

### Validating locally (IMPORTANT — read before trusting a red)

`./validate.sh <band.fk>` in **explicit single-file mode does NOT read the
`; preludes:` header** — it runs only the files you name, so a band run that
way reports everything `unbound`. That is not a failure of your code.

- **Local gate:** compile the three `section [` preludes (`core.fk`,
  `compiler.fk`, `grammars/python-bmf.fk`) via `form-source-compile-file`,
  then run the full prepared chain through Go + Rust. The band returns its
  aggregate integer; both kernels must agree.
- **Authoritative three-way (incl. TypeScript):** CI's no-arg
  `validate-thread-process` suite — it walks `form-stdlib/tests/*.fk`,
  reads each band's `; preludes:` header, and runs Go/Rust/TS. Trust CI's
  green over a local red from explicit-mode invocation.

See [[self_form_kernel_local_toolchain]] (memory) for the full trap.

## Coverage snapshot (2026-05-29, after #2168)

**Eval arms shipped (14):** AUG-ASSIGN, ASSIGN, CALL, DEF, DICT, IDENT, IF,
INT, LIST, MODULE, RETURN, STRING, SUBSCRIPT, WHILE
**Lift branches shipped:** AUG-ASSIGN, IF, INT, LIST, MODULE, PASS,
SUBSCRIPT, WHILE (+ ASSIGN/RETURN/DEF/CALL/BINOP/COMPARE/IDENT/STRING via
dedicated lifters)

## The queue

### Batch 1 — cheap (lift-only; eval already shipped or trivial). Do first.

| Construct | Why cheap | Independence |
|---|---|---|
| **dict literal `{k: v}`** | `PY-BMF-DICT` **eval already shipped**; only `lift-primary` branch missing — exact aug-assign situation | edits `lift-primary` (shared) |
| `for x in xs:` | reuses `py-eval-body-loop`; iterator over LIST | new `lift-for` + `py-eval-statement` arm — disjoint helpers |
| unary `-x` / `not x` | small `lift-primary` branch + small `py-eval` arm | edits `lift-primary` + `py-eval` |
| boolean `and` / `or` | precedence-climb extension + short-circuit eval arm | edits `lift-binop-loop` + `py-eval` |

### Batch 2 — substrate-critical heavy (constructs the target files use most)

Ranked by frequency across `api/app/services/substrate/*.py`:

| Construct | Hits in substrate | Notes |
|---|---|---|
| **f-strings** | `form_runtime.py` 62, `form.py` 32 | grammar parses; lift + eval (string-build over interpolations) |
| **`class` + `@dataclass`** | `form.py` 50, `category.py` 34 | plain-class eval exists; dataclass + dunders are the real work |
| **decorators** | `form.py` 50 | lift wraps the decorated def in a call chain |
| **`try`/`except`** | `form_runtime.py` 12 | needs an exception-stack data shape in eval |
| **comprehensions** | `form_runtime.py` 10 | desugar to a fold over the iterable |
| **`from … import` as module** | 28 files | needs module-system semantics; ORM calls also need the Form persistence runtime, not SQLAlchemy |

### Not a compiler gap — a runtime gap

`kernel.py` (49 ORM hits), `orm.py`, `markdown_frontend.py` (43) call
`session.query(...)`/`Column(...)`. Even fully compiled, those bind to a
runtime the kernel doesn't have. They compile only after their `session.*`
calls are rebound to the Form persistence runtime (`cell-put`/`lookup-cell`,
[`form-stdlib/persistence.fk`](../form/form-stdlib/persistence.fk), Breath 5)
— NOT SQLAlchemy. Compile the pure-computation files first
(`form_eval.py`, `category.py`, `numeric_formats.py`, `inductive.py` — the
zero-ORM ones); the ORM-bound files wait on the runtime.

## Parallelization

Disjoint helper functions can be authored in parallel worktrees; the shared
**dispatch** points serialize (last writer rebases the if-chain branch):
- `lift-statement` if-chain — every new *statement* kind adds a branch
- `py-eval` / `py-eval-statement` if-chains — every new arm
- `lift-primary` — every new *expression* atom

So: implement the `lift-X`/`py-eval-X` *bodies* in parallel, then land the
one-line dispatch branches in series. The band's per-cell offsets keep
merges honest — a dropped construct subtracts its unique value from the sum.

## Done

| Date | PR | Construct | Aggregate |
|---|---|---|---|
| 2026-05-29 | [#2168](https://github.com/seeker71/Coherence-Network/pull/2168) | augmented assignment `x += y` (lift; eval pre-existing) | 75000 → 85000 |
