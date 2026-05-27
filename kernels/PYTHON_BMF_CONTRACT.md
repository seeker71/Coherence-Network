# Python-BMF driven parse — what works now, what the next breath needs

This doc names the surface contract for parsing Python via Form-native BMF
rules in `form/form-stdlib/grammars/python-bmf.fk`. It lives next to
`PYTHON_PIPELINE_STATUS.md` so the Python adapter's compost trajectory is
legible from one place.

## What works right now

End-to-end, on every sibling kernel (Go, Rust, TypeScript), with no
TypeScript on the parse path:

```
source text  →  python-source-scan-text     →  BMF object stream
            →  python-parse-module-tree-*   →  statement-tree
            →  python-bmf-lift.fk           →  PY-BMF-* recipe (NodeID)
            →  python-bmf-eval.fk (py-run)  →  Python-runtime value
```

Proved by:

- `form/form-stdlib/tests/python-bmf-arithmetic-band.fk` (returns `25304`
  on all three kernels) — flat-rule arithmetic recipes are content-
  addressed and round-trip to source.
- `form/form-stdlib/tests/python-bmf-eval-band.fk` (returns `28000`) —
  recipe-walker (G4) covers the 9 arms.
- `form/form-stdlib/tests/python-bmf-lift-band.fk` (returns `21000`) —
  source-string → PY-BMF recipe → value round-trip across six cells,
  including factorial(6) = 720.
- `kernel-bmf-run examples/python_bridge_demo.py` returns `720` — three-way
  parity with CPython and the bootstrap Rust path.

What's already in `python-bmf.fk` and reachable today:

- A complete Python source scanner (`python-source-scan-text`,
  `python-source-scan-file`, `python-source-scan-text-with-layout`)
  that emits BMF objects: `py-keyword`, `py-name`, `py-op`, `py-int`,
  `py-float`, `py-string`, `py-bytes`, `py-fstring`, `py-tstring`,
  `py-layout` (NEWLINE/INDENT/DEDENT/ENDMARKER).
- ~180 BMF rules covering arithmetic, comparisons, imports, defs,
  classes, control flow, comprehensions, decorators, async, match/case,
  f-strings, slices, walrus, unary ops, attr access, subscripts.
- A reverse-emitter (`<=`) on most rules — recipes round-trip back to
  source-object lists.
- A rule registry (`python-bmf-rules`) keyed by name, walked by
  `apply-python-bmf-rule rule-name object-stream`.

## What is still bootstrap-dependent

The pieces below currently live in `form/form-kernel-ts/seedbank/python-adapter/`
(TS) and have no Form-native equivalent yet. Each is one focused breath
the body has not yet taken.

### G1 — Statement dispatch over a parsed tree — **CLOSED 2026-05-27**

Closure shape: rather than dispatch over a flat rule-index of object-stream
rules, the bridge dispatches over the **statement-tree** that
`python-parse-module-tree-object` already builds (G2 territory). The tree
groups tokens by indent and exposes each statement's `kind` (first-token
classifier) and `cpython-rule` (rule-name based on token shape).

Lives at `form/form-stdlib/python-bmf-lift.fk`. The `lift-statement` arm
dispatches by both:

```form
(if (str_eq kind "def")        (lift-def statement-tree)
(if (str_eq kind "return")     (lift-return statement-tree)
(if (str_eq rule "assignment") (lift-assign statement-tree)
(if (str_eq kind "expr")       (lift-expr-stmt statement-tree) ...)))))
```

Each branch consumes the statement's tokens (and, for `def`, its nested
children-statements) and emits a `PY-BMF-*` recipe via `intern_node` — the
exact constructors `python-bmf-eval.fk`'s arms expect. The `PY-BMF-MODULE`
recipe wraps the per-statement recipes so `py-eval-module-loop` threads the
env across `ASSIGN` and `DEF`.

**What G1 does NOT close yet:** statement kinds beyond the four above
(`class` / `while` / `for` / `try` / `with` / `import` / `from-import`)
fall through to `PY-BMF-PASS` with a `trace` naming the shape. Each is one
focused breath: add the lift dispatch branch + the matching interpreter arm.

### G2 — Statement-level grouping — **CLOSED (existing)**

`python-parse-module-tree-object` and friends already grouped tokens into
statement-trees by indent. G1's lifter consumes them directly; no separate
slicer was needed.

### G3 — Expression precedence climbing — **CLOSED 2026-05-27**

Closure shape: **recursive-descent expression parser in
`python-bmf-lift.fk`** sitting alongside G1's statement dispatch.
`lift-expr` calls `lift-primary` for the leftmost token, then
`lift-binop-loop` climbs by precedence, then attaches a trailing
`x if cond else y` (the Python conditional expression) by lifting to
`PY-BMF-IF`.

Precedence table (higher = tighter):

| Prec | Ops |
|---|---|
| 50 | `**` (right-assoc) |
| 40 | `* / // %` |
| 30 | `+ -` |
| 20 | `== != < <= > >=` |

`lift-primary` handles integer literals → `PY-BMF-INT`, identifiers →
`PY-BMF-IDENT`, `f(args)` → `PY-BMF-CALL` (with `lift-args` reading
comma-separated expressions until `)`), and parenthesised expressions for
grouping.

**What G3 does NOT close yet:** unary minus on non-trivial expressions,
boolean `and` / `or` / `not`, bitwise / shift ops, `in` / `is` /
`is not` / `not in`, attribute access `obj.field`, subscripts `xs[i]`,
slices `xs[a:b:c]`, walrus `:=`, lambdas, comprehensions, f-strings.

### G4 — Closure/scope at the recipe layer — **CLOSED 2026-05-27**

Closure shape: **Form-side interpreter with alist-scope and self-named
closures.** Lives at `form/form-stdlib/python-bmf-eval.fk` (~270 LOC).
Three-way sibling parity (Go, Rust, TypeScript) on `python-bmf-eval-band.fk`
returns `28000`.

What walks today:

- `PY-BMF-INT` → `node_value` of the trivial-int leaf
- `PY-BMF-IDENT` → alist lookup against the current env
- `PY-BMF-BINOP` → recursive eval of left/right + op dispatch
  (`+ - * / % ** //`)
- `PY-BMF-COMPARE` → recursive eval + op dispatch
  (`== != < <= > >=`)
- `PY-BMF-IF` → branch on condition (0 = false; the standard Form convention)
- `PY-BMF-RETURN` → eval the inner expression
- `PY-BMF-ASSIGN` → extend env with a new binding; returns extended env
- `PY-BMF-DEF` → build a closure capturing the env at def-site; bind name →
  closure in env
- `PY-BMF-CALL` → look up callee by name, extend captured env with
  `(self-name → closure)` to tie the recursive knot, bind args, walk body
- `PY-BMF-MODULE` → fold over statements, threading the env through ASSIGN
  and DEF; returns last statement's value

The interpreter is recipe-as-input: a band-test builds PY-BMF recipes via
`intern_node` directly (the way `python-bmf-arithmetic-band.fk` does) and
walks them. That lets G4 be proven in isolation, ahead of G1/G3. Once G1
(rule dispatch over a token stream) lands and produces PY-BMF recipes
from source text, the `kernel-bmf-run` driver can swap its
`(len statements)` call for `(py-run (python-parse-module-file path))`
without changing the orchestration shape.

What does NOT walk yet (each is its own focused breath):

- `PY-BMF-CLASS`, method invocation, attribute access (`obj.field`)
- `PY-BMF-WHILE`, `PY-BMF-FOR`, `PY-BMF-LIST`, `PY-BMF-DICT`,
  `PY-BMF-SUBSCRIPT` (mutable iteration + collection ops)
- `PY-BMF-LAMBDA`, `PY-BMF-TUPLE`, `PY-BMF-AUG-ASSIGN`
- `PY-BMF-TRY`, `PY-BMF-RAISE` (exception handling)
- `PY-BMF-IMPORT`, comprehensions, slices, walrus, async/await
- Float arithmetic (the band-test uses integer-only operands)
- Mutual recursion + general `letrec` (current self-ref only ties the
  single function being called; mutual cycles need a second pass)

Each arm above is a small extension to `py-eval` (one new `(if (node_eq
cat PY-BMF-X) ...)` branch) plus, where needed, a Form-side data shape
(e.g., dict-as-alist for `PY-BMF-DICT`).

### G5 — Sibling-agent overlap (template-machinery, Breath 2e) — **RESOLVED**

PR #2076 (`claude/template-machinery-breath-2e`) attested that Breath 2e
is **already landed**. The primitives that would let `python-bmf.fk`'s
rule shape be expressed as data are alive: `mk-cstream`, `cs-peek-cp`,
`cs-advance`, `cm-char`, `cm-char-range`, `cm-string`, `cm-not`,
`cm-peek`, `cm-match-{sequence,choice,star,opt,capture,rule}`,
`cm-parse`, plus `make_nodeid`, `intern_trivial_int`, `intern_node`,
`walk_recipe`, `node_eq`, `node_children`, `node_value`. The agent's
load-bearing proof in `form-stdlib/tests/grammar-chars-demo.fk` parses
`"3+4+5"` end-to-end on three sibling kernels and walks to 12.

G1's dispatcher can now be written. G5 is no longer a blocker.

### G6 — Binary entry-point orchestration — **CLOSED 2026-05-27**

Closure shape: **wrapper script** (the first of the three reachable shapes
named below). Lives at
`form/form-kernel-ts/seedbank/python-adapter/scripts/kernel-bmf-run`.
The script pre-compiles each surface-syntax prelude through the Go kernel
(`form-source-compile-file`), then invokes the Rust kernel with the
compiled artifacts plus an inline driver that calls
`python-parse-module-file` against the target `.py`.

`parity_suite.sh` puts its own `scripts/` directory on `PATH` before the
`command -v kernel-bmf-run` check, so `PARITY_THIRD_RUNTIME=kernel-bmf
bash parity_suite.sh` runs end-to-end with no operator-side install.

What the driver computes today (with G1 + G3 + G4 all closed): the
program's CPython runtime value, for any `.py` file whose shapes fit the
9 PY-BMF arms shipped. The preludes load `python-bmf-eval.fk` and
`python-bmf-lift.fk`; the driver expression is `(py-bmf-run-file path)`.

`kernel-bmf-run form-kernel-ts/seedbank/python-adapter/examples/python_bridge_demo.py`
returns `720` (factorial of 6) — three-way sibling parity green, matching
CPython.

Demos that use shapes outside the 9 arms (lists, dicts, classes, while/for,
comprehensions, attribute access, subscripts, etc.) still surface honest
traces from `py-env-lookup` or `lift-statement: unsupported kind/rule`.
Each unsupported shape is one focused breath: add the lift dispatch
branch in `python-bmf-lift.fk` + the matching interpreter arm in
`python-bmf-eval.fk`. The contract scales linearly with surface coverage;
no further orchestration breath is needed.

**Three reachable shapes for G6 (kept for record; #1 was taken):**

1. **Wrapper script** *(taken)* — `kernel-bmf-run` is a bash script that
   runs the same pre-compile dance `validate.sh` does (Go-kernel compiles
   the source-syntax preludes → Rust kernel reads the compiled artifacts
   + the target `.py`'s parse expression). Cheapest; most fragile under
   load-order drift.

2. **Pre-shipped compiled artifacts** — `python-bmf.fk` + its prelude
   chain ship as pre-compiled `.fkb` (Form binary) artifacts in the repo;
   `kernel-bmf-run` invokes the Rust kernel with the `--binary` flag and
   feeds it those. Cleaner; introduces a build-step artifact.

3. **Native binary load-step** — extend the Rust kernel to detect
   surface-syntax `.fk` files and run the source-compile internally
   (embedding the same path `validate.sh` walks externally). Deepest;
   single-binary entry on PATH.

**Repro of the closure:**

```bash
cd form
form-kernel-ts/seedbank/python-adapter/scripts/kernel-bmf-run \
    form-kernel-ts/seedbank/python-adapter/examples/python_demo.py
# → 15  (top-level statement count, sibling-parity ✓)

# Same value through validate.sh, confirming three-kernel agreement:
./validate.sh form-stdlib/core.fk form-stdlib/json.fk form-stdlib/cache.fk \
              form-stdlib/form-ontology-loader.fk form-stdlib/engine.fk \
              form-stdlib/compiler.fk form-stdlib/source-compiler.fk \
              form-stdlib/grammars/python-bmf.fk /tmp/parse-demo.fk
# → 15 on go, rust, typescript
```

`PARITY_THIRD_RUNTIME=kernel-bmf` is now runnable. The parity rows still
go honest-red against CPython at every demo until G1 + G3 ship the
source → PY-BMF-recipe path — G4 is alive (`python-bmf-eval-band.fk`
returns `28000` across three kernels) but `kernel-bmf-run` cannot yet
feed it real `.py` files. No faked green. The compost gate for Phase A's
parser+emitter+test triple (~3,585 LOC, per
`kernels/PHASE_A_FIRING_QUESTIONS.md`) is downstream of G1+G3 wiring G4
into `kernel-bmf-run`, then greening every `PARITY_FILES` row.

## Parity discipline (do not compost yet)

- Don't modify `lang-python.ts` or `lang-python-fk.ts` in this PR.
- Don't delete them when G1–G4 land either — wait until parity holds
  across the full Python surface, not just arithmetic.
- The bootstrap-compost-manifest sibling (`claude/bootstrap-compost-manifest`)
  is naming the deletion order; that branch is the source of truth for
  "what is safe to remove when."
- Strict NodeID equality between bootstrap and BMF paths is **not**
  achievable on the same source — bootstrap emits `CTOR.add/sub/mul`
  (Math-primitive type=12), BMF emits `PY-BMF-BINOP` (dialect type=99,
  with the operator as a string-trivial child). They are semantically
  equivalent representations, structurally distinct by intent.
  The honest parity gate is "BMF produces a recipe whose value walks to
  the same Python-runtime result as bootstrap's recipe," not NodeID
  equality. That gate sits behind G4.

## How to run the proof

```bash
cd form
./validate.sh form-stdlib/core.fk \
              form-stdlib/json.fk form-stdlib/cache.fk \
              form-stdlib/form-ontology-loader.fk \
              form-stdlib/engine.fk form-stdlib/compiler.fk \
              form-stdlib/source-compiler.fk \
              form-stdlib/grammars/python-bmf.fk \
              form-stdlib/tests/python-bmf-arithmetic-band.fk
# → 25304 on go, rust, typescript
```
