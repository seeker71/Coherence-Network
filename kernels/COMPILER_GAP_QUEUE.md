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

## Coverage snapshot (2026-05-29, after #2186 — Batch 1 + range + comprehensions)

**Eval arms shipped (17):** AUG-ASSIGN, ASSIGN, CALL, COMP, DEF, DICT, FOR,
IDENT, IF, INT, LIST, MODULE, RANGE(builtin), RETURN, STRING, SUBSCRIPT, WHILE
**Lift branches shipped:** AUG-ASSIGN, COMP, DICT, FOR, IF, INT, LIST, MODULE,
PASS, SUBSCRIPT, WHILE, unary `-`/`not`, boolean `and`/`or`
(+ ASSIGN/RETURN/DEF/CALL/BINOP/COMPARE/IDENT/STRING via dedicated lifters)
**Band aggregate:** 145000 (19 cells)
**Batch 2 status:** comprehensions DONE (#2186); f-strings BLOCKED (grammar
statement-splitter — see below); class / decorators / try-except remain.

**Desugaring wins (no new eval arm):** unary `-x` → MATH-MINUS(0,x);
`not x` → COMPARE-EQ(x,0); `a and b` → IF(a,b,a); `a or b` → IF(a,a,b).
Whenever a construct's semantics reduce to an existing recipe shape, lift
desugars and eval is untouched — the cheapest kind of breath.

## The queue

### Batch 1 — cheap (lift-only; eval already shipped or trivial). Do first.

| Construct | Why cheap | Independence | Status |
|---|---|---|---|
| **dict literal `{k: v}`** | `PY-BMF-DICT` eval shipped; `lift-primary` branch + value_eq lookup fix | edits `lift-primary` (shared) | **DONE #2174** |
| `for x in xs:` | folds over a LIST via `py-eval-body-loop` | new `lift-for` + `py-eval-statement` arm | **DONE #2175** (list iterables; `range()` pending) |
| unary `-x` / `not x` | desugars: `-x`→MATH-MINUS(0,x), `not x`→COMPARE-EQ(x,0) — pure lift, no eval arm | edits `lift-primary` | **DONE #2178** |
| boolean `and` / `or` | desugars to PY-BMF-IF (short-circuit) — pure lift, no eval arm | edits `op-prec` + `tok-binop-prec` + `lift-binop-loop` | **DONE #2179** |
| `range(n)` as iterable | `range()` builtin produces a Form list so `for i in range(n)` walks | eval-side CALL intercept (`py-range`) | **DONE #2181** (range(stop) + range(start,stop); step pending) |

**Batch 1 is complete** — the cheap (mostly lift-only) tier is done. `range()`
remains as a small follow-up that unblocks the most common substrate loop
idiom; it's eval-side (a builtin producing a list) rather than a lift gap.

### Batch 2 — substrate-critical heavy (constructs the target files use most)

Ranked by frequency across `api/app/services/substrate/*.py`:

| Construct | Hits in substrate | Notes |
|---|---|---|
| **f-strings** | `form_runtime.py` 62, `form.py` 32 | **BLOCKED at grammar layer — not lift/eval.** lift+eval are *written and proven* (see below); the real gap is statement-grouping. |
| **statement-grouping: trailing f-string stmt dropped** | — | **PREREQUISITE for f-strings.** `python-parse-module-tree-object` drops a statement whose first token is a bare `py-fstring`: `a=2; b=3; f"…"` → only 2 statements (the f-string vanishes). Fix lives in `form-stdlib/grammars/python-bmf.fk` statement grouping — it must recognize a leading `py-fstring` token as starting an expression-statement. Once fixed, the f-string lift+eval below drops straight in. |
| **`class` + `@dataclass`** | `form.py` 50, `category.py` 34 | plain-class eval exists; dataclass + dunders are the real work |
| **decorators** | `form.py` 50 | lift wraps the decorated def in a call chain |
| **`try`/`except`** | `form_runtime.py` 12 | needs an exception-stack data shape in eval |
| ~~**comprehensions**~~ | `form_runtime.py` 10 | **DONE #2186** — `[elem for var in iter]` → PY-BMF-COMP; lift peeks for `for` after first elem, eval maps elem over iter binding var per-item. Filter clauses (`if`) + nested fors pending. |
| **`from … import` as module** | 28 files | needs module-system semantics; ORM calls also need the Form persistence runtime, not SQLAlchemy |

### Parked: f-string lift+eval (proven, blocked on statement-grouping)

Attempted 2026-05-29 (PR #2184, closed without merge). The lift and eval are
**correct in isolation** — the only reason f-strings don't round-trip is the
statement-grouping bug above. Keeping the design here so the next breath drops
it in after the grammar fix, rather than re-deriving it:

- **Scanner hands a single `py-fstring` token** carrying the raw body (e.g.
  `v={name}` for `f"v={name}"`) — interpolations are NOT pre-parsed.
- **Lift** (`python-bmf-lift.fk`): a char-scanner splits the body into
  alternating segments and emits `PY-BMF-FSTRING`:
  - literal runs → `PY-BMF-STRING` leaf (via `intern_trivial_string` of the
    substring)
  - `{ expr }` → the inner expr lifted via `lift-module-text`, taking its
    module's first statement recipe.
  Helpers: `fstr-find-open`/`fstr-find-close` (scan for `{`/`}`),
  `fstr-segments` (accumulate, skip empty literal runs), `fstr-lift-inner`,
  `lift-fstring`. Add `py-fstring` + `py-string` branches to `lift-primary`
  (the plain-`py-string` literal branch is *also* currently missing — a bare
  string literal doesn't lift today; add it alongside).
- **Eval** (`python-bmf-eval.fk`): `PY-BMF-FSTRING` arm folds children via
  `py-fstring-build` — `(str_concat acc (int_to_str (py-eval seg env)))`.
  `int_to_str` is polymorphic (strings pass through, ints/bool/null render),
  so no new native is needed.
- **Verified directly** (bypassing the broken module path): `lift-fstring
  "x={5}y"` + `py-eval` → `x=5y`; `f"v={a}"`/`f"sum={a+b} end"` lift to cat-99
  with correct segment children. They fail only because the f-string
  *statement* never reaches `lift-statement`.
- **Test shape (for when it unblocks):** band cell — `a=2; b=3;
  f"sum={a + b} end"` → `"sum=5 end"`, scored via `str_eq` (result is a
  string, not an int). Format specs (`{x:.2f}`) and `{{`/`}}` escapes are a
  further breath beyond the basic round-trip.

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
| 2026-05-29 | [#2174](https://github.com/seeker71/Coherence-Network/pull/2174) | dict literal `{k: v}` + int-key lookup (`str_eq` → `value_eq`) | 85000 → 95000 |
| 2026-05-29 | [#2175](https://github.com/seeker71/Coherence-Network/pull/2175) | for-loop over a list (`lift-for` + `py-for-loop`) | 95000 → 105000 |
| 2026-05-29 | [#2178](https://github.com/seeker71/Coherence-Network/pull/2178) | unary `-x` / `not x` (desugar; no eval arm) | 105000 → 115000 |
| 2026-05-29 | [#2179](https://github.com/seeker71/Coherence-Network/pull/2179) | boolean `and` / `or` (short-circuit → IF; no eval arm) | 115000 → 125000 |
| 2026-05-29 | [#2181](https://github.com/seeker71/Coherence-Network/pull/2181) | `range()` builtin → iterable list (eval-side; no lift change) | 125000 → 135000 |
| 2026-05-29 | [#2186](https://github.com/seeker71/Coherence-Network/pull/2186) | list comprehension `[e for v in it]` → PY-BMF-COMP (Batch 2) | 135000 → 145000 |
