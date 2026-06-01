# Bootstrap Compost Manifest

> Urs's directive (2026-05-26): *"remove all possible bootstrapping; all parsing
> and compiling in BMF rule space, form native only; all other paths are to be
> composted."*

This document names every file that composts when the Form-native path proves
parity with the bootstrap. **It deletes nothing.** The compost happens in
sibling PRs (`template-machinery`, `python-bmf-driven-parse`, and onward) as
each demo proves three-way identity on the Form-native side.

The discipline is **discipline + readiness**: every bootstrap file is named here
with the gate that must be green before it composts, and the parity suite
already carries a runtime selector that switches the third runtime atomically
(see `seedbank/python-adapter/scripts/parity_suite.sh` `PARITY_THIRD_RUNTIME`).
As of 2026-06-01, 19 of the 20 `PARITY_FILES` prove three-way green under the
Form-native walker (isolated-tempdir measurement). The default stays `ts-eval`
until the last demo (`python_typing_compose_demo`) closes; the flip is one line
when it does. The named Phase-A files compost only once all 20 are green.

This is the readiness map. The compost is downstream of green gates.

---

## What the destination shape is

When all phases complete:

```
.py source bytes
    ↓
generic Form source scanner (kernel native, reads chars → BMF stack objects)
    ↓
form-stdlib/grammars/python-bmf.fk (Form rules consume BMF objects)
    ↓
reversible Form/BMF object tree (NodeIDs in substrate)
    ↓
form-kernel-{go,rust,ts} (sibling kernels walk Form recipes)
    ↓
result
```

No host parser. No TypeScript lowering. No Python `ast` bridge. The grammar IS
data; the engines walk it; the kernels execute the recipes.

The bootstrap exists because we need a way to *prove* the Form-native pipeline
matches CPython before we can rely on it. Three-way parity (CPython +
TS bootstrap + Rust kernel) is the gate that earns the right to remove the
TS bootstrap. Three-way parity (CPython + Form-native + Rust kernel) is the
gate that earns the right to remove the Rust kernel from the bootstrap role
(it stays as the execution kernel; only its bootstrap-parser role composts).

---

## Phase A — Bootstrap parsers + emitters

These ship the *current* third runtime (`ts-eval`). They compost when the
Form-native parser (Form rules over BMF source objects from
`form-stdlib/grammars/python-bmf.fk` and `typescript-bmf.fk`) proves three-way
parity per file.

**Gate per file:** `PARITY_THIRD_RUNTIME=kernel-bmf
scripts/parity_suite.sh` reports green on the file. The TS bootstrap is no
longer the third runtime — the Form-native walker is. When every file in
`PARITY_FILES` has been promoted, the bootstrap parser files are residue.

### Python adapter

| File | LOC | What it does today | Form-native replacement |
|---|---|---|---|
| `form/form-kernel-ts/seedbank/python-adapter/src/lang-python.ts` | 2199 | TS hand-coded Python parser + tree-walking evaluator (the `evalPython` path the parity suite uses today) | `form-stdlib/grammars/python-bmf.fk` rules consuming BMF source objects emitted by the generic Form scanner |
| `form/form-kernel-ts/seedbank/python-adapter/src/lang-python-fk.ts` | 674 | TS emitter — lowers parsed Python CTORs to `.fk` text the Rust kernel runs | Form-native rules emit reversible Form objects directly; no separate emitter layer — the parser output IS the recipe |
| `form/form-kernel-ts/seedbank/python-adapter/src/ctor-convergence.ts` | 672 | TS-side CTOR vocabulary + convergence helpers (shared with TS adapter for Blueprint identity) | CTOR vocabulary moves into `form-stdlib/grammars/ctor-vocabulary.fk` as Form data; convergence is structural by content-addressing |
| `form/form-kernel-ts/seedbank/python-adapter/src/lang-python.test.ts` | 342 | TS-side parser/eval unit tests | Form-side rule tests under `form-stdlib/tests/python-grammar-*.fk` (one per shipped construct) |
| `form/form-kernel-ts/seedbank/python-adapter/src/ctor-convergence.test.ts` | 358 | TS-side convergence unit tests | Form-side equivalence tests asserting NodeID identity for cross-language structural twins |

**Subtotal Phase A — Python adapter: 4245 LOC**

### TypeScript adapter

(Lives on `claude/ts-grammar-bootstrap`; landed via the TS bootstrap seam PR.)

| File | LOC | What it does today | Form-native replacement |
|---|---|---|---|
| `form/form-kernel-ts/seedbank/ts-adapter/src/lang-ts.ts` | 1176 | TS hand-coded TypeScript parser + tree-walking evaluator (`ts-eval` runtime in `parity_suite.sh`) | `form-stdlib/grammars/typescript-bmf.fk` rules consuming BMF source objects |
| `form/form-kernel-ts/seedbank/ts-adapter/src/lang-ts-fk.ts` | 360 | TS emitter — lowers parsed TS CTORs to `.fk` text | Form-native rules emit Form objects directly |

**Subtotal Phase A — TS adapter: 1536 LOC**

**Phase A total: 5781 LOC of bootstrap parser tissue.**

---

## Phase B — Adapter CLIs, scripts, and demo wiring

These compost when their parsers compost. The CLIs only exist to invoke the
TS-side parser/emitter; once those are gone, the CLI surface is hollow.

The parity scripts themselves don't compost — they become Form-native parity
gates that compare two Form-native engines (classic-rd vs BMF-streaming, per
Breath 2 of `form/kernel-roadmap.md`) across three sibling kernels.

### Python adapter

| File | LOC | What it does today | Form-native replacement |
|---|---|---|---|
| `form/form-kernel-ts/seedbank/python-adapter/src/main.ts` | 221 | CLI entry: `python-compile`, `python-run`, `python-eval`, `python-trace` | Subsumed by `form-kernel-{rust,go,ts} <file.py>` — the kernel reads `.py` directly via the grammar |
| `form/form-kernel-ts/seedbank/python-adapter/scripts/parity_suite.sh` | 99 | Three-way parity gate (CPython / ts-eval / Rust kernel) | Replaced by Form-native parity gate comparing (CPython / classic-rd Form engine / BMF-streaming Form engine) × 3 kernels = 7-way matrix; same shell wrapper, different runtimes |
| `form/form-kernel-ts/seedbank/python-adapter/scripts/perf_compare.sh` | 91 | Wall-clock comparison CPython vs Rust kernel vs TS evalPython | Becomes (CPython vs native kernel vs Form-native walker on kernel); the TS-bootstrap row drops out |

**Subtotal Phase B — Python adapter: 411 LOC** (scripts stay, third-runtime row drops out — net compost is ~30 LOC of script tissue + the entire 221-LOC CLI)

### TypeScript adapter

| File | LOC | What it does today | Form-native replacement |
|---|---|---|---|
| `form/form-kernel-ts/seedbank/ts-adapter/src/main.ts` | 201 | CLI entry: `ts-compile`, `ts-eval`, `ts-run` | Subsumed by kernel reading `.ts` directly via `typescript-bmf.fk` |
| `form/form-kernel-ts/seedbank/ts-adapter/scripts/parity_suite.sh` | 102 | Three-way parity gate (node / ts-eval / Rust kernel) | Same shape as the Python parity rewrite — Form-native engines as the live runtimes |

**Subtotal Phase B — TS adapter: 303 LOC** (CLI fully composts, script rewrites)

### Seedbank READMEs + demo .fk files

The demo `.py` and `.ts` files stay (they're the substrate the parity gate
exercises). The compiled `.fk` files compost — they're emitter artifacts. The
seedbank README rewrites to point at the Form-native path:

| Path | What stays vs composts |
|---|---|
| `seedbank/python-adapter/examples/*.py` | **STAYS** — parity-suite input |
| `seedbank/python-adapter/examples/*.fk` | **COMPOSTS** — emitter output; regenerated by Form-native pipeline as needed |
| `seedbank/python-adapter/README.md` | **REWRITES** — points at Form-native grammar |
| `seedbank/ts-adapter/examples/*.ts` | **STAYS** |
| `seedbank/ts-adapter/examples/*.fk` | **COMPOSTS** |
| `seedbank/ts-adapter/README.md` | **REWRITES** |

**Phase B total: 714 LOC of CLI + script tissue (most of it pure compost), plus ~20 emitted .fk files.**

---

## Phase C — Bridge layer (Python ↔ kernel)

These compost in step with **Breath 6 + Breath 7** of `form/kernel-roadmap.md`
(embed the native kernel in `api/`, then compost Python `form_runtime.py`).
Until the bridge can disappear entirely, parts of it stay as a thin pass-through
to the inline kernel (PyO3 path, per #2069 `pyo3-inline-kernel`).

**Gate per file:** the equivalent surface is reachable from Form-native code
walking inside the kernel; the FastAPI handler reads from a kernel listener
(`#2065 kernel-as-http-listener`) or invokes the kernel inline; the Python
side becomes a thin client (or disappears).

| File | LOC | What it does today | Form-native replacement | Gate |
|---|---|---|---|---|
| `api/app/services/form_kernel_bridge.py` | added by #2056 (`fastapi-endpoint-as-form`); grew under #2058 (`transmute-more-endpoints`); rewrote under #2069 (`pyo3-inline-kernel`) | Bridges Python FastAPI handlers to the kernel — currently transmutes `coherence_weight`, `nodeid_distance`, `weighted_average` to Form recipes invoked through subprocess or PyO3 | Disappears: handlers ARE Form recipes the kernel-as-HTTP-listener serves directly | All transmuted endpoints prove three-way parity with their Python predecessors AND `kernel-as-HTTP-listener` serves the route end-to-end |
| `api/app/services/substrate/form_runtime.py` | 1500 | Python implementation of the Form runtime (parser, eval, walker, queries) | Form-native runtime running in the sibling kernels; `coh_substrate.py form '<expr>'` calls a kernel via PyO3 wrapper | Breath 7 of `form/kernel-roadmap.md` — after Breath 6 stabilizes |
| `api/app/services/substrate/self_host.py` | 348 | Python-side keyword + operator registry (the template-machinery target shape) | Migrates into `form-grammar/templates.fk` + `form-grammar/builtins.fk` (Breath 2e of roadmap) | Form-side template registry passes the same cross-validation matrix Python's `prefer_registered=True` flag already exercises |
| `api/app/services/substrate/form_rules.py` | 649 | Pattern primitives (Sequence, Capture, Literal, Opt, RepeatedCapture) as Python recipe constructors | Each primitive becomes a Form CTOR in `form-grammar/patterns.fk` — already partially in flight (`Pattern primitives in PR #1783`) | Form-native pattern primitives prove convergence with the Python primitives via NodeID identity |
| `api/app/services/substrate/form_builders.py` | 441 | Template primitives (Build, CaptureRef, Const, MapBuild) as Python recipe constructors | Each primitive becomes a Form CTOR in `form-grammar/templates.fk` | Form-native template primitives prove convergence with the Python primitives via NodeID identity |
| `api/app/routers/utils.py` (Python-implementation rows) | added/grew through #2056, #2058 | Each utility endpoint (`coherence_weight`, `nodeid_distance`, `weighted_average`) carries both a Python implementation and a Form-recipe call site behind a feature flag | The Form recipe IS the endpoint; the Python fallback row composts | Three-way parity stable for the endpoint AND the kernel-listener path serves it without subprocess |

**Phase C total: 2938 LOC of Python runtime + bridge tissue (form_runtime + self_host + form_rules + form_builders), plus the growing utility-router Python rows.**

**Note on `form_runtime.py`:** the body has carried this through nearly every breath. Compost with care — it taught the body what Form is. It composts only after Breath 7, and the manifest names it here so the destination shape is visible from the start.

---

## Phase D — Foundational persistence + infrastructure

Surfaced by the `orm.py` firing-question walk
([`PHASE_A_FIRING_QUESTIONS.md`](PHASE_A_FIRING_QUESTIONS.md) — *Shape 2*).
These files aren't parser-shape residue waiting on a parity flip; they're
**foundational substrate machinery** — ORM tables, atomicity gates,
content-addressed storage helpers. Their compost gate is different from
Phase A/B/C.

**Gate per file:** the body has a **Form-native persistence story** — a
durable store that the kernel writes/reads with the same atomicity guarantee
`orm.py`'s UNIQUE constraint provides, with sibling-kernel portability
(Go/Rust/TS can all read/write the same store).

**The story's first cell has landed** (`form-stdlib/persistence.fk`, proven
three-way 2026-05-29 — see the PROVEN row below). The resolution unifies the
three shapes that were once a fork: the persistence *contract* is a Form
module (`cell-put` / `lookup-cell`), and the *backend* is swappable beneath
it. The kernel already persists the content-addressed lattice via
`write_form_binary` / `read_form_binary` — no new native against a DB was
needed. The three shapes become one layered answer, not a choice:

1. **Backend (shipped today):** kernel-native serialization to `.fkb`
   Form-binary artifacts — the canonical store, closest to the audit's #10
   single-binary-distribution breath.
2. **Backend (later, behind the same contract):** binding to PG/SQLite
   directly, slotting under `cell-put`/`lookup-cell` without changing callers.
3. **The unifier:** the *contract* is Form-side — which was always shape 3's
   spirit. Shapes 1 and 2 are two backends of it.

What still gates `orm.py`'s compost: the `.fkb`↔ORM reconciliation so the
Form store and the Python `substrate_named_cells` are one shared lattice on
disk (a Form-written cell visible to `coh_substrate.py annotate`), not two
backends of one interface. That bridge is the rest of Breath 5.

This is a **much bigger arc** than Phase A's parity flip. The audit names it
as the #10 next breath. The manifest carries the named shape so future
sessions know which phase a substrate-Python file belongs to before assuming
the parser discipline fits.

### Phase D candidates (initial inventory)

The wellness probe's wider-perimeter measurement (after #2089) sees 30
substrate-Python modules totaling ~16,362 LOC. The 25 unnamed ones (beyond
Phase C's 5) are awaiting firing-questions. Likely Phase D candidates from
that pool:

| File | Approx LOC | Why Phase D |
|---|---|---|
| `api/app/services/substrate/orm.py` | 101 | SQLAlchemy ORM tables, atomicity gate (walked in `PHASE_A_FIRING_QUESTIONS.md`) |
| `api/app/services/substrate/substrate_strings.py` | 109 | String interning subsystem; foundational |
| `api/app/services/substrate/kernel.py` | ~745 | Kernel core; mixed — some parts Form-native today, some persistence-bound |

Each future firing-question that lands on a Phase D candidate **adds a row
here**, not in Phase A. The manifest carries all four shapes; the discipline
knows where each file belongs.

**Phase D total: TBD** — requires firing-questions on each candidate to
confirm Shape 2 classification + LOC count.

---

## Summary

| Phase | What | LOC named for compost |
|---|---|---|
| A | Bootstrap parsers + emitters (Python adapter + TS adapter) | **5,781** |
| B | Adapter CLIs + scripts + emitted .fk files | **714** (~+20 .fk files; 4 emitted .fk RELEASED 2026-05-31 — see RELEASED section) |
| C | Python bridge + form_runtime + self-host registry | **2,938** + utility-router rows |
| D | Foundational persistence + infrastructure | **TBD** (firing-questions in flight) |
| **Total** | | **~9,433 LOC + Phase D** of bootstrap tissue with named compost gates |

---

## The runtime-selector switch

`form/form-kernel-ts/seedbank/python-adapter/scripts/parity_suite.sh` carries
`PARITY_THIRD_RUNTIME` (env-var):

- `ts-eval` (**default**) — the TS bootstrap evaluator (`lang-python.ts` →
  `evalPython`). Backwards-compatible; every existing gate runs unchanged.
- `kernel-bmf` (the destination) — invokes `kernel-bmf-run <source.py>`, which
  reads `.py` via `form-stdlib/grammars/python-bmf.fk`, lifts to PY-BMF-*
  recipes (`python-bmf-lift.fk`), and walks them through the Form-native
  interpreter (`python-bmf-eval.fk`) on the Rust kernel. As of 2026-06-01,
  **19 of the 20 `PARITY_FILES` pass three-way** under it (CPython ==
  Rust-bootstrap == kernel-bmf) when measured in isolated tempdirs.

**The flip is one line** (the `${PARITY_THIRD_RUNTIME:-...}` fallback in
`parity_suite.sh`), fully reversible, and changes no CI gate — no workflow runs
the parity suite; the `form/**` gates run only `bash validate.sh`. It stays
gated on `ts-eval` until the **last demo closes**: `python_typing_compose_demo`
errors `_plus: unsupported operand types` under `kernel-bmf-run` — two direct
attribute reads on a multi-attribute instance combined (`red.base + blue.base`),
where the Form-native eval's record/attr storage does not carry the second
attribute as an int. Minimal repro: a class storing `self.base`/`self.weight`
in `__init__`, then `r = B(3, 4); r.base + r.weight` (single-attribute
instances, or attr-read composed with a method call, pass). When that arm in
`python-bmf-eval.fk` lands three-way, all 20 are green and the default flips;
the Phase-A Python-adapter bootstrap files (`lang-python.ts` and friends) become
residue, compostable in a sibling PR.

The same selector shape can extend to the TS adapter parity gate
(`PARITY_THIRD_RUNTIME` over `ts-eval` vs `kernel-bmf-ts`).

---

## What this manifest does NOT do

- It does not delete any file. Compost happens in sibling PRs as they prove
  parity.
- It does not claim files compost that aren't named here. New bootstrap tissue
  shipped after 2026-05-26 gets a manifest row when added.
- It does not change the gate's default behavior. `PARITY_THIRD_RUNTIME=ts-eval`
  stays default; today's parity suite runs unchanged.

---

## How this stays current

When a sibling PR proves parity for a demo, it appends a row to a "PROVEN"
section at the bottom of this file (date + file + selector) and bumps a
counter. When `PARITY_THIRD_RUNTIME=kernel-bmf` becomes the default, the
phase-A rows for the proven files get marked **COMPOST READY**. When the
files actually compost, the row moves to a "RELEASED" section with the PR.

The manifest is the body's awareness of its own bootstrap weight. As long as
the weight has a named destination and a green-gate path to compost, the body
is supple under the load.

---

## Where this manifest is read from

- **`make wellness`** — `sense_bootstrap_compost` in `scripts/wellness_check.py`
  reads the file paths listed above, sums on-disk LOC, and surfaces the current
  bootstrap weight + third-runtime selector. The body sees its own load each
  time wellness runs (auto at SessionStart via `arrival.py`).
- **`kernels/PYTHON_PIPELINE_STATUS.md`** — the four-bullet destination map.
  Cross-references this manifest at the *third* bullet ("compile any file →
  Form binary the kernel CLI runs standalone") because Form-native compilation
  is what makes the bootstrap compost-able.
- **`form/kernel-roadmap.md`** Breaths 6 + 7 — embed the kernel in `api/`,
  then compost Python `form_runtime.py`. Phase C of this manifest IS the file
  list those breaths reach for.

---

## PROVEN — rows that have walked their first lifecycle step

A row appears here when a sibling PR proves three-way parity for a specific
shape under `PARITY_THIRD_RUNTIME=kernel-bmf` (or equivalent — sibling-kernel
agreement on the Form-native side). The row names the date, the PR, the file
it proves, and the selector that exercises the proof. When all shapes a
Phase-A file expresses are PROVEN, the Phase-A row gets marked **COMPOST READY**.
When the file actually composts, it moves to **RELEASED**.

This is the lifecycle in motion — proof that the discipline is breath, not
ritual.

| Date | PR | Shape proved | Selector | Sibling parity |
|---|---|---|---|---|
| 2026-05-27 | [#2071](https://github.com/seeker71/Coherence-Network/pull/2071) | Python arithmetic binary ops (`a - b`, `x * y`, `left / right`, `p ** q`) | `form/form-stdlib/tests/python-bmf-arithmetic-band.fk` returns `25304` | Go ✓ · Rust ✓ · TypeScript ✓ (131/131 in `./validate.sh`) |
| 2026-05-27 | `claude/g6-kernel-bmf-run` | G6 — binary entry-point orchestration. `kernel-bmf-run <file.py>` exists, pre-compiles surface-syntax preludes via the Go-kernel-as-compiler, invokes the Rust kernel with a `python-parse-module-file` driver. The `command -v kernel-bmf-run` gate in `parity_suite.sh` opens — `PARITY_THIRD_RUNTIME=kernel-bmf` is runnable end-to-end | `form/form-kernel-ts/seedbank/python-adapter/scripts/kernel-bmf-run examples/python_demo.py` returns `15` (top-level statement count from `python-parse-module-file`) | Go ✓ · Rust ✓ · TypeScript ✓ (same `len-of-statements` driver run through `./validate.sh` returns `15` on all three) |
| 2026-05-27 | `claude/g4-pybmf-closure-interpreter` | G4 — closure/scope interpreter for PY-BMF recipes. Nine arms walk to Python-runtime values: `PY-BMF-INT`, `PY-BMF-IDENT`, `PY-BMF-BINOP` (+/-/*/// /%/**/​//), `PY-BMF-COMPARE` (==/!=/</<=/>/>=), `PY-BMF-RETURN`, `PY-BMF-ASSIGN`, `PY-BMF-DEF` (closure capture), `PY-BMF-CALL` (with self-name tied for self-recursion), `PY-BMF-IF`, `PY-BMF-MODULE`. Scope is an alist; closures store `(self-name, params, body, captured-env)`. ~270 LOC. Surface lives at `form/form-stdlib/python-bmf-eval.fk` | `form/form-stdlib/tests/python-bmf-eval-band.fk` builds seven recipe-cells directly via `intern_node` (mirroring `python-bmf-arithmetic-band.fk`'s test discipline) and walks them: `7+3=10`, `((20-5)*3)//7=6`, `x*x` with `x=11→121`, `x=6;x*7→42`, `def add(a,b):return a+b; add(10,20)+5→35`, `def absdiff(a,b):return a-b if a>=b else b-a; absdiff(7,19)→12`, `def fact(n):return 1 if n<2 else n*fact(n-1); fact(6)→720`. Scored aggregate returns `28000` | Go ✓ · Rust ✓ · TypeScript ✓ (in `./validate.sh` workload `stdlib/python-bmf-eval-band.fk`) |
| 2026-05-27 | `claude/g1-g3-parser-to-recipe-bridge` | G1 + G3 — parser-to-recipe bridge. `form/form-stdlib/python-bmf-lift.fk` (~375 LOC) lifts the statement-tree from `python-parse-module-tree-*` to PY-BMF-* recipes the G4 interpreter walks. G1: statement dispatch over `python-statement-tree-kind` + `cpython-rule` (def/return/assignment/expr). G3: precedence-climbing expression parser with right-assoc `**`, left-assoc `* / // % + -`, comparison precedence, parenthesised grouping, conditional `x if c else y` lifting to `PY-BMF-IF`, n-ary `f(args)` to `PY-BMF-CALL`. `kernel-bmf-run`'s driver swaps from `(len statements)` to `(py-bmf-run-file path)`. The `examples/python_bridge_demo.py` factorial demo now closes three-way against CPython | `form/form-stdlib/tests/python-bmf-lift-band.fk` drives six cells from source-string through the full lift+eval: `7+3=10`, `2+3*4=14`, `(2+3)*4=20`, `def f(n):return n+1; f(41)=42`, `def add(a,b):return a+b; x=add(10,20); x+5=35`, `def fact(n):return 1 if n<2 else n*fact(n-1); fact(6)=720`. Scored aggregate returns `21000`. End-to-end `kernel-bmf-run examples/python_bridge_demo.py` prints `720`, matching CPython and the bootstrap Rust path | Go ✓ · Rust ✓ · TypeScript ✓ (in `./validate.sh` workload `stdlib/python-bmf-lift-band.fk`) |
| 2026-05-27 | `claude/widen-kernel-bmf-parity-coverage` | Widens `kernel-bmf-run` parity coverage. Adds four lift branches and one bug-fix to `python-bmf-lift.fk` (~80 LOC of additions): (1) `True`/`False`/`None` keyword literals lift to `PY-BMF-INT`(1/0/0), matching the interpreter's int-as-bool convention; (2) list-literal `[a, b, c]` lifts to `PY-BMF-LIST` (interpreter arm already shipped); (3) postfix `expr[idx]` chains lift to `PY-BMF-SUBSCRIPT` (folds onto every primary, so `xs[0]`, `f()[i]`, `xs[i][j]` all walk); (4) `while cond: body` statement lifts to `PY-BMF-WHILE` (interpreter arm already shipped); (5) bug fix — right-associative ternary chaining in `lift-cond-tail` so `a if p else b if q else c` lifts as `IF(p, a, IF(q, b, c))` matching CPython (previously the else-recursion stopped at primary+binop, dropping inner ternaries). The single-statement def-body short-circuit composted — bodies always wrap in `PY-BMF-MODULE` so `py-eval-module-loop` dispatches statement-shape arms via `py-eval-statement`. No new interpreter arms; all five shapes ride existing eval surface | `form/form-stdlib/tests/python-bmf-lift-band.fk` extended from six cells to nine: previous six unchanged, plus cell 7 (`xs = [10, 20, 30]; xs[0] + xs[2] = 40`), cell 8 (`def sum_to(n): total=0; i=1; while i<=n: total=total+i; i=i+1; return total; sum_to(10) = 55`), cell 9 (`def sign(n): return 1 if n>0 else 0-1 if n<0 else 0; sign(5)+sign(0-3)+5 = 5` — exercises right-assoc ternary). Scored aggregate returns `45000`. End-to-end: `kernel-bmf-run examples/python_demo.py = 40949`, `python_assign_demo.py = 45`, `python_imperative_demo.py = 45370` — all matching CPython and the bootstrap Rust path three-way | Go ✓ · Rust ✓ · TypeScript ✓ (in `./validate.sh` workload `stdlib/python-bmf-lift-band.fk`, 135/135 green) |
| 2026-05-27 | [#2113](https://github.com/seeker71/Coherence-Network/pull/2113) | CTOR Shape B for `+ - * /`. The PY-BMF lift now interns `+ - * /` as `RBasic.MATH-12` (NodeIDs `(1, 2, 12, 1..4)`) with positional children — the *same* Blueprint a hand-built `(intern_node MATH-PLUS …)` interns to. **Cross-modal NodeID equality at the math-primitive layer becomes substrate-truth for arithmetic.** New MATH-12 arm in `python-bmf-eval.fk` walks the unified shape; old `PY-BMF-BINOP` arm still services `** // %` (no MATH instances exist for those today). | Cell 10 of `python-bmf-lift-band.fk` builds a hand-built `MATH-PLUS(7, 3)` and a Python-lifted `"7 + 3"`; `node_eq` returns 1 across all three kernels. Aggregate moves 45000 → 55000 | Go ✓ · Rust ✓ · TypeScript ✓ (136/136 in `./validate.sh`) |
| 2026-05-27 | [#2119](https://github.com/seeker71/Coherence-Network/pull/2119) | CTOR Shape B extends to comparisons — `== != < <= > >=`. The PY-BMF lift now interns comparisons as `RBasic.COMPARE-13` (NodeIDs `(1, 2, 13, 1..6)`) with positional children. New COMPARE-13 arm in `py-eval` dispatches on `node_inst` to `eq`/`lt`/`le`/`gt`/`ge` natives (Python's 1/0 integer convention preserved). Old `PY-BMF-COMPARE` arm stays for unrecognised ops (defensive) | Cell 11 of `python-bmf-lift-band.fk` proves convergence: hand-built `COMPARE-LT(5, 7)` and Python-lifted `"5 < 7"` `node_eq` to 1 across all three kernels. Aggregate moves 55000 → 65000 | Go ✓ · Rust ✓ · TypeScript ✓ (136/136 in `./validate.sh`) |
| 2026-05-27 | [#2122](https://github.com/seeker71/Coherence-Network/pull/2122) | CTOR Shape B extends to `%` (mod) — closes the last arithmetic operator MATH-12 carries today (`inst=5`). Lift dispatcher gains the `%` case before falling back to `PY-BMF-BINOP`; eval MATH-12 arm gains the `(if (eq math-inst 5) (mod lhs rhs))` branch. What's still on `PY-BMF-BINOP` for arithmetic: `**` (power) and `//` (floor-div) — no MATH instances exist for those today; closing them is a separate breath that adds inst=6,7 to `form-ontology.json` + native registration in three kernels | Cell 12 of `python-bmf-lift-band.fk` proves: hand-built `MATH-MOD(10, 3)` and Python-lifted `"10 % 3"` `node_eq` to 1 across all three kernels. Aggregate moves 65000 → 75000 | Go ✓ · Rust ✓ · TypeScript ✓ (136/136 in `./validate.sh`) |
| 2026-05-29 | `claude/form-native-substrate-persistence` | **Phase D — Breath 5 first cell.** Form-native substrate persistence: the kernel reads AND writes the content-addressed named-cell lattice with no Python and no new native. `form-stdlib/persistence.fk` adds `cell-put` / `lookup-cell` / `store-cells` over `channel.fk`'s `.fkb` file primitives; a CELL Recipe carries `(name, domain, blueprint, ctor)` with `(domain, name)` identity (the same `UNIQUE(domain, name)` Python `orm.py` enforces). Resolves the Phase D three-shape fork: contract is Form-side, backend swappable (`.fkb` today, DB later). What stays open: `.fkb`↔ORM reconciliation so the two stores become one shared lattice on disk | `form-stdlib/tests/persistence-band.fk` returns `7` — round-trips two cells sharing a name across different domains through a `.fkb` file, proving durable write→read, `(domain, name)` identity, content-addressing, honest absence, and composed-CTOR survival in one strange edge | Go ✓ · Rust ✓ · TypeScript ✓ (`./validate.sh form-stdlib/tests/persistence-band.fk`, 1 workload 0 divergent) |
| 2026-06-01 | `claude/return-signal-fix` | **Return short-circuit — control-flow breath.** A `return` inside an `if` / `for` / `while` body now exits the enclosing function instead of falling through. The mechanism is core-abstraction-first: a statement-result becomes a three-slot list `(value env returned)` — the third slot is the return-signal. `py-stmt-return` tags a RETURN statement (`returned=1`); `py-eval-body-loop` stops the moment a statement carries it and propagates the result verbatim; the IF-STMT, FOR (`py-for-loop`), and WHILE (`py-while-loop`) arms each read `returned` off the body-loop result and short-circuit; `py-eval-module-loop` (the function-body walker, reached via `py-eval`'s MODULE arm from the CALL / method / export call-sites) yields the returned value when `returned=1`, preserving last-value semantics for top-level modules when no return fires. One mechanism every block type honors; no per-arm hack, no kernel native, no grammar/lift change | Minimal proof (each in its own tempdir): `def f(): if 1==1: return 1` then `return 2` → `1` (was `2`); `return` inside `for` → `9`; `return` inside `while` guarded by `if` → `128`; the `weighted_score` guard shape `f(0)` → `700`. All three-way CPython == Rust-bootstrap == kernel-bmf | Go ✓ · Rust ✓ · TypeScript ✓ (`./validate.sh` — the python-bmf bands walk the shared eval surface; no new divergence) |
| 2026-06-01 | [#2268](https://github.com/seeker71/Coherence-Network/pull/2268) | **`python_class_demo.py` reaches full parity (176) — duplicate `_get` native merged.** The Rust kernel registered `_get` twice: an attribute reader (record-as-flat-alist, string key) and ~240 lines later a subscript reader (`list[int]` / `dict[key]`). `register_native` inserts by interned-name id, so the second call silently shadowed the first. The Python adapter lowers BOTH `obj.field` → `(_get obj "field")` and `x[i]`/`d[k]` → `(_get x i)` to the same native, so every attribute read on a class instance hit the int-index path and panicked `as_int: Str("field")`. This was the single root cause that broke the **Rust-bootstrap** parity leg for all three class demos (`as_int: Str("n")` / `Str("sound")` / `Str("base")`). Fix: one polymorphic `_get` dispatching on receiver shape — `__dict__`-tagged list → dict lookup; plain alist + string key → record-field read; list + int index → element; str + int index → char. Core-abstraction-first: one accessor engine, dispatch on data, not two natives racing to register | python_class_demo three-way: CPython `176` == Rust-bootstrap `176` == `kernel-bmf-run` `176` (the Form-native leg already passed — python_class needs no `super()` or annotation surface). Full `parity_suite.sh` under ts-eval: 20 passing, 0 failing. `python-class-band.fk` (exercises `(_get obj "value")` + nested `(_get (_get obj "value") 0)`) passes three-way in `./validate.sh` | Go ✓ · Rust ✓ · TypeScript ✓ (`./validate.sh` — only the pre-existing untracked `seeded-bytes-recipe-band.fk` `add_mod_u64` divergence remains; not introduced here) |

**What G6 closes and what stays open.** G6 was the orchestration gap — the
pieces existed (Go compiler, Rust walker, Python BMF grammar) with no binary
on PATH to drive them together. That gap closes: `kernel-bmf-run` is the
walking shape. What G6 does NOT close: the parsed PY-BMF-* recipes are not
yet walked back to Python runtime values, so `kernel-bmf-run python_demo.py`
returns the statement count (15), not the program's CPython value (40949).
The driver swaps to a recipe-walking expression in the same script when G4
(closure interpreter) lands; the orchestration shape stays.

**Resolved — false-green correction (2026-06-01).** Two rows that had
been recorded COMPOST READY on 2026-06-01 —
`python_substrate_demo.py` (claimed three-way `17680`) and
`endpoint_coherence_weight_demo.py` (claimed three-way `16185`) — were
**removed as false-greens**. Under isolated-tempdir measurement (each demo
in its own `mktemp -d`, `kernel-bmf-run` using its own work-dir, no
concurrent `/tmp/*.fk` bleed):

| Demo | CPython | Rust bootstrap | `kernel-bmf-run` (Form-native) |
|---|---|---|---|
| `python_substrate_demo.py` | `17680` | `17680` | `5170` |
| `endpoint_coherence_weight_demo.py` | `16185` | `16185` | `5240` |

CPython and the Rust bootstrap path agree; the **Form-native `kernel-bmf-run`
diverges**, so neither demo is three-way green. COMPOST READY certifies the
Form-native value, and it does not match — the row was green-by-error.
The honest count drops by two; that is a real heal, not a regression.

The root cause is the `PY-BMF-IF-STMT` arm (shipped 2026-06-01): it threads
*env* through the if-body but carries no `return` signal, so a `return`
inside `if cond:` does not short-circuit the enclosing function. The early-
guard shape `weighted_score` uses — `if position == 0: return value * 100`
… `return value * 10` — therefore always falls through to the final
`return value * 10`, mis-scoring every weighted term. Minimal proof:
`def f():` with `if 1==1: return 1` then `return 2` yields `2` (CPython `1`).
Closing it is a control-flow breath (return-signal threaded through
`py-eval-body-loop` / `py-eval-statement` / FOR+WHILE / the CALL body
walker) with its own three-way proof — not a one-line patch.

**Resolved 2026-06-01 (`claude/return-signal-fix`).** The return-signal
landed: a statement-result now carries a third `returned` slot, every block
arm and the function-body `py-eval-module-loop` short-circuit on it, and both
demos re-measured **three-way green at their true values** under isolated
tempdirs — `python_substrate_demo` `17680/17680/17680`,
`endpoint_coherence_weight_demo` `16185/16185/16185`. Their COMPOST READY rows
are restored above; the honest count climbs back by two, on real parity this
time. See the PROVEN return-signal row for the mechanism. The short-circuit is
now pinned against regression by cell 13 of
`form-stdlib/tests/python-bmf-eval-band.fk` — the early-guard `g(0) + g(5)`
shape, three-way green at `110` (a regression would collapse it to `20`),
folded into the band aggregate `91000`.

**Resolved contract — the import arm landed (2026-06-01, #2266).** The third
false-green removed in the integrity sweep is re-earned. The Form-native
lift/eval path now carries `import` / module-attribute, so
`python_import_demo` measures three-way green under isolated `kernel-bmf-run`:

| Demo | CPython | Rust bootstrap | `kernel-bmf-run` (Form-native) |
|---|---|---|---|
| `python_import_demo.py` | `20.853981633974485` | `20.853981633974485` | `20.853981633974485` |

The light path — no new ontology category, no kernel parser change. The
categories `PY-BMF-IMPORT` (501) / `PY-BMF-FROM-IMPORT` (502) already existed;
the math natives (`math_sqrt` / `math_floor` / `math_ceil` / `math_pi` /
`math_pow`) are callable bare from Form in all three kernels. The shape:

- **Lift** (`python-bmf-lift.fk`): `lift-import` emits `PY-BMF-IMPORT(alias)`;
  `lift-from-import` emits `PY-BMF-FROM-IMPORT(module, members…)`; the
  `lift-statement` dispatcher routes the `import` / `from` statement kinds.
- **Eval** (`python-bmf-eval.fk`): the IMPORT statement arm binds the module
  name to a `py-module` marker; the FROM-IMPORT arm binds each member (a
  constant like `pi` resolves now, a function like `sqrt` binds a
  `py-native-fn` marker). One resolution table `py-math-resolve` dispatches
  module members to the kernel native; the ATTR / METHOD-CALL / CALL arms
  check the markers and route through it. The bare-name path is untouched —
  markers only exist when an import statement created them, so non-import
  demos are structurally unaffected. The row is COMPOST READY above.

**Open contract for the next PROVEN rows:** the surface beyond the 9 arms
needs both a lift dispatch branch in `python-bmf-lift.fk` and a matching
interpreter arm in `python-bmf-eval.fk`. Order of incoming breaths (each is
its own focused PR):

- `PY-BMF-IF-STMT` return short-circuit — **landed 2026-06-01**
  (`claude/return-signal-fix`): the return-signal threads out of `if` / `for` /
  `while` bodies and the function-body walker, so early-guard functions
  (`if x: return ...`) evaluate Form-native. Re-promoted
  `python_substrate_demo.py` (`17680`) and `endpoint_coherence_weight_demo.py`
  (`16185`), both three-way green. `elif` / `else` clauses remain a later breath.

- `PY-BMF-WHILE` + while-statement lift — `while cond: body`
- `PY-BMF-LIST` + list-literal lift + `PY-BMF-SUBSCRIPT` for `xs[i]`
- `PY-BMF-DICT` + dict-literal lift + key access
- `PY-BMF-CLASS` + method binding + `PY-BMF-ATTR` for `obj.field`
- `PY-BMF-FOR` + iterator protocol on lists / ranges — **landed for `range(...)`**: `lift-for` + the PY-BMF-FOR eval arm carry `for i in range(...)`. The lift lifts the iterable as a general expression (not a range-only special-case) and the eval iterates whatever Form list it evaluates to, so `for v in <list-variable>` also walks. `python_range_demo.py` reached COMPOST READY 2026-05-31.
- `PY-BMF-IF-STMT` + statement-level `if cond: body` lift — **landed** (lift 2026-06-01; return-short-circuit 2026-06-01, `claude/return-signal-fix`): a category distinct from the `PY-BMF-IF` ternary expression (ontology inst 575, auto-bound via `form-ontology-loader.fk`). `lift-if-statement` lifts the header condition with the while colon-stripper and the children as statements, emitting `PY-BMF-IF-STMT(cond, body-stmts...)`; the eval arm on `py-eval-statement` evaluates the condition once and runs the body when truthy (non-zero, the int-bool convention `py-while` uses). **The return-short-circuit gap is closed:** a statement-result now carries a third `returned` slot, `py-eval-body-loop` stops on it and propagates the result, every block arm (IF-STMT / FOR / WHILE) reads it off the body-loop result, and `py-eval-module-loop` (the function-body walker) yields the returned value — so a `return` inside an `if` / `for` / `while` body short-circuits the enclosing function. Minimal proof (each in its own tempdir): `def f():` with `if 1==1: return 1` then `return 2` now yields `1` (matching CPython), `return` inside a `for` yields `9`, `return` inside a `while` yields `128`, the `weighted_score` guard `f(0)` yields `700` — all three-way. This re-earned `python_substrate_demo.py` (`17680`) and `endpoint_coherence_weight_demo.py` (`16185`) on true parity. `elif` / `else` clauses remain a later breath. No kernel native, no grammar edit — the fix is purely in the interpreter's control-flow plumbing. **Pinned against regression** by cell 13 of `form-stdlib/tests/python-bmf-eval-band.fk` — the dual-path early guard `g(0) + g(5)` (`if p == 0: return 100` else fallthrough `return 10`), three-way green at `110` where a lost short-circuit would collapse the sum to `20`; folded into the band aggregate `91000`.
- `PY-BMF-LAMBDA` + closure capture in expressions — **landed**: `lift-lambda` + the PY-BMF-LAMBDA eval arm (closure built, walked by PY-BMF-CALL) carry single-expression lambdas assigned, passed as arguments, and used in arithmetic; `python_lambda_demo.py` reached COMPOST READY 2026-05-31 (arms shipped in #2185; this row records the demo closing three-way with them).
- `PY-BMF-AUG-ASSIGN` (`x += 1`) and multi-target assignment

Each PROVEN row brings one more `PARITY_FILES` demo green under
`PARITY_THIRD_RUNTIME=kernel-bmf`. When `lang-python.ts`'s full surface is
covered by Form-native arms, the Phase-A `lang-python.ts` row moves to
COMPOST READY.

---

## COMPOST READY — rows whose shape is fully Form-native

A row appears here when every shape a specific demo expresses has been
PROVEN three-way under `PARITY_THIRD_RUNTIME=kernel-bmf` *and* under the
bootstrap path. The .py file no longer needs the TS bootstrap to reach
its CPython value — both the Rust kernel (bootstrap path) and
`kernel-bmf-run` (Form-native path) print the same number.

The Phase-A file that *only* this demo would have needed isn't compostable
yet — other demos still flex shapes the bootstrap covers and the bridge
doesn't. But the demo itself sits in the readiness zone: every breath that
follows narrows the gap. When all `PARITY_FILES` rows reach COMPOST READY,
`lang-python.ts` (and the bootstrap parser tissue around it) becomes
removable.

| Date | Demo | Shape | Bridge support | Three-way value |
|---|---|---|---|---|
| 2026-05-27 | `form/form-kernel-ts/seedbank/python-adapter/examples/python_bridge_demo.py` | factorial — `def fact(n): return 1 if n<2 else n*fact(n-1); result = fact(6); result` (9 arms: INT, IDENT, BINOP, COMPARE, RETURN, ASSIGN, DEF, CALL, IF, MODULE) | `form/form-stdlib/python-bmf-lift.fk` + `form/form-stdlib/python-bmf-eval.fk` | CPython `720` · Rust (bootstrap) `720` · `kernel-bmf-run` `720` |
| 2026-05-27 | `form/form-kernel-ts/seedbank/python-adapter/examples/python_demo.py` | mixed recursion — fact, fib, ackermann, is_prime + is_prime_helper, count_primes + count_primes_helper. Exercises `True`/`False` keyword lift, multi-level right-associative ternary chains (`a if p else b if q else c`), pure-recursive function composition `count_primes(30) + fact(8) + fib(15) + ackermann(2, 3)` | `python-bmf-lift.fk` (True/False keyword arms + lift-cond-tail right-assoc fix) | CPython `40949` · Rust (bootstrap) `40949` · `kernel-bmf-run` `40949` |
| 2026-05-27 | `form/form-kernel-ts/seedbank/python-adapter/examples/python_assign_demo.py` | assignment + list literal + subscript — `def add(a, b): return a+b; result = add(10, 20); xs = [1,2,3,4,5]; total = xs[0]+xs[1]+xs[2]+xs[3]+xs[4]; result + total` | `python-bmf-lift.fk` (PY-BMF-LIST list-literal arm + PY-BMF-SUBSCRIPT postfix arm) | CPython `45` · Rust (bootstrap) `45` · `kernel-bmf-run` `45` |
| 2026-05-27 | `form/form-kernel-ts/seedbank/python-adapter/examples/python_imperative_demo.py` | while-loop accumulators — `def sum_to(n): total=0; i=1; while i<=n: total=total+i; i=i+1; return total` and a parallel `fact_loop`; result `sum_to(100) + fact_loop(8)`. Drives the WHILE statement-lift, multi-statement def-body wrapping, env threading through loop-body assignments | `python-bmf-lift.fk` (lift-while statement arm + always-wrap-MODULE def-body) | CPython `45370` · Rust (bootstrap) `45370` · `kernel-bmf-run` `45370` |
| 2026-05-31 | `form/form-kernel-ts/seedbank/python-adapter/examples/python_range_demo.py` | for-over-range accumulator — `def sq(n): return n*n; def sum_squares_plus_self(limit): total=0; for i in range(limit): total = total + sq(i) + i; return total; sum_squares_plus_self(50)`. Drives the FOR statement-lift over a `range(...)` iterator with a nested function call inside the loop body and env threading through the accumulator | `python-bmf-lift.fk` (`lift-for` PY-BMF-FOR statement arm) + `python-bmf-eval.fk` (PY-BMF-FOR interpreter arm + `range` builtin) | CPython `41650` · Rust (bootstrap) `41650` · `kernel-bmf-run` `41650` |
| 2026-05-31 | form/form-kernel-ts/seedbank/python-adapter/examples/python_builtins_demo.py | reducing builtins + augmented assignment — `def stats(values): return sum(values)+min(values)+max(values)` and `for v in values: d += abs(v - target)`; result `stats(vs) + absolute_distance_from_target(vs, 10)` over `[3, 17, 8, 22, 5, 14]`. Drives sum/min/max/len/abs builtins plus `+=`/`-=` accumulation in a for-body | `python-bmf-eval.fk` (reducing-builtin arm in py-eval CALL: `py-builtin` / `py-builtin?`, intercepted before env-lookup like `range`; int natives only — no lift change, no kernel change) | CPython `131` · Rust (bootstrap) `131` · `kernel-bmf-run` `131` |
| 2026-05-31 | form/form-kernel-ts/seedbank/python-adapter/examples/python_string_demo.py | string literals + polymorphic `+` + `len(s)` — `def greet(name): return "hello, " + name` and `def banner_length(name, decoration): msg = greet(name) + decoration; return len(msg)`; result `banner_length("world","!") + banner_length("substrate","!!!") + banner_length("kernel","")`. Drives string-literal lift, runtime string concat via Python's overloaded `+`, and `len()` over a string. `len(s)` already worked (the kernel `len` native is Str-aware); the gaps were the string-literal lift arm and numeric-only `+` | `python-bmf-lift.fk` (`tok-string?` predicate + PY-BMF-STRING arm in lift-primary, mirroring py-int) + `python-bmf-eval.fk` (MATH-PLUS arm routes to the kernel's polymorphic `_plus` native — present in rust/go/ts siblings — so `+` does numeric add AND string concat from one arm; no kernel change) | CPython `45` · Rust (bootstrap) `45` · `kernel-bmf-run` `45` |
| 2026-05-31 | form/form-kernel-ts/seedbank/python-adapter/examples/python_lambda_demo.py | lambda expressions — `double = lambda x: x * 2`, `add = lambda a, b: a + b`, `sq = lambda n: n * n`; `result = add(double(5), sq(6))`; lambdas stored in a list `fns = [double, sq, lambda x: x + 100]` and called through a `for f in fns: out += f(7)` loop; result `result + out`. The eval `PY-BMF-LAMBDA` arm (anonymous closure, self-name "") already existed — the only gap was the lift | `python-bmf-lift.fk` (`lambda` arm in lift-primary + `lift-lambda-params` helper — collect params to the colon, lift the body as a full expression, emit `PY-BMF-LAMBDA(params..., body)`; no eval change, no kernel change) | CPython `216` · Rust (bootstrap) `216` · `kernel-bmf-run` `216` |
| 2026-05-31 | form/form-kernel-ts/seedbank/python-adapter/examples/python_dict_demo.py | full dict surface — literal build from subscript values, subscript-read, subscript-**assign** (`out["weighted"] = ...`, `resp["scope"] = 4`), `in` membership (`"weighted" in resp`), key iteration (`for k in resp`), and `len(dict)` as pair-count; reduced to scalar 88 | `python-bmf-lift.fk` (`stmt-subscript-assign?` + `lift-subscript-assign` → `PY-BMF-SUB-ASSIGN`; `in` as comparison-level op in `tok-binop-prec`/`lift-binop-loop` → `PY-BMF-COMPARE` op "in") + `python-bmf-eval.fk` (`PY-BMF-SUB-ASSIGN` arm rebinds the name to a new dict via `py-dict-set` — immutable-value threading like ASSIGN; FOR yields `py-dict-keys` for dict iterables; `py-builtin` len reads pair count for dicts; `py-compare-apply` "in" → `py-member?`). No kernel change | CPython `88` · Rust (bootstrap) `88` · `kernel-bmf-run` `88` |
| 2026-06-01 | form/form-kernel-ts/seedbank/python-adapter/examples/endpoint_nodeid_distance_demo.py | NodeID-distance arithmetic — a function computing a structural distance over eight scalar NodeID-component args via comparison + arithmetic composition, called once at module top; `7`. **No new bridge code** — comparison (COMPARE-13) + arithmetic (MATH-12) + multi-arg CALL arms already shipped; reachability proven by isolated sequential measurement | `python-bmf-lift.fk` + `python-bmf-eval.fk` (COMPARE-13 + MATH-12 + PY-BMF-CALL prior arms; no lift/eval/kernel change) | CPython `7` · Rust (bootstrap) `7` · `kernel-bmf-run` `7` |
| 2026-06-01 | form/form-kernel-ts/seedbank/python-adapter/examples/endpoint_lattice_stats_demo.py | lattice-stats integer reduction — functions reducing fixed scalar inputs to a single aggregate through arithmetic + comparison composition, no list iteration over a variable; `1089`. **No new bridge code** — arithmetic + comparison + CALL arms already shipped; reachability proven by isolated sequential measurement | `python-bmf-lift.fk` + `python-bmf-eval.fk` (MATH-12 + COMPARE-13 + PY-BMF-CALL prior arms; no lift/eval/kernel change) | CPython `1089` · Rust (bootstrap) `1089` · `kernel-bmf-run` `1089` |
| 2026-06-01 | form/form-kernel-ts/seedbank/python-adapter/examples/python_float_demo.py | float literals + mixed int/float arithmetic + float comparison + float division — `lerp`, `coherence_score` (weighted average), `is_above`; `2 + 0.5`, `0.5*0.25 + 1.0*0.75`, `score - midpoint`, `(score + delta) / 2.0`; `4.875`. The gap was at the **source scanner**: it only emitted `py-int`, so `0.5` tokenized as `py-int 0` · `py-op .` · `py-int 5`; the lift read the `.` as attribute access (PY-BMF-ATTR) and eval did `record_get` on `Int(0)` — the `record_get: not a record: Int(...)` signature. The kernels already carried `Value::Float`, `intern_trivial_float64`, float-promoting `_plus`/`sub`/`mul`/`div`, float-aware compare, and `format_float_python`, but **no float-interning native was exposed to Form code**, so the lift could not build a float leaf. Closed by exposing `intern_trivial_float` (str→f64 NodeID, sibling of `intern_trivial_int`/`intern_trivial_string`) in all three kernels over the existing internal `intern_trivial_float64`, then a float-literal path through scanner + lift + eval | rust `form-kernel-rust/src/main.rs` + go `form-kernel-go/main.go` + ts `form-kernel-ts/src/kernel.ts` (`intern_trivial_float` native, ~3 lines each over the pre-existing interning primitive) · `form-stdlib/grammars/python-bmf.fk` (`python-source-scan-int` consumes `N.M` → `py-float`; a dot not followed by a digit stays `py-int`, so ATTR / method-call / subscript are untouched) · `python-bmf-lift.fk` (`tok-float?` + PY-BMF-FLOAT arm in `lift-primary`, mirroring py-int) · `python-bmf-eval.fk` (PY-BMF-FLOAT arm returns the leaf `node_value`; arithmetic rides MATH-12, comparison COMPARE-13). The `PY-BMF-FLOAT` ontology category already existed (python.bmf inst 564) | CPython `4.875` · Rust (bootstrap) `4.875` · `kernel-bmf-run` `4.875` |
| 2026-06-01 | form/form-kernel-ts/seedbank/python-adapter/examples/endpoint_weighted_average_demo.py | the body of `/api/utils/weighted_average` as pure Python — `dot` and `sum_floats` while-loop accumulators over float lists, then `numerator / denominator`; frozen input `[0.5, 0.75, 1.0]` / `[0.25, 0.25, 0.5]`; `0.8125`. Drives float list literals, float `*`/`+` accumulation in a while-body, and float division — all on the float-literal arm; the while-loop + subscript + len shapes were already shipped | scanner `py-float` + `python-bmf-lift.fk` PY-BMF-FLOAT arm + `python-bmf-eval.fk` PY-BMF-FLOAT arm + `intern_trivial_float` native in all three kernels (shared with python_float_demo); WHILE / SUBSCRIPT / len arms are prior | CPython `0.8125` · Rust (bootstrap) `0.8125` · `kernel-bmf-run` `0.8125` |
| 2026-06-01 | form/form-kernel-ts/seedbank/python-adapter/examples/python_substrate_demo.py | early-guard dispatch + accumulator-loop over a list — `weighted_score` returns from inside `if position == N:` guards (`return value * 100/50/25`, falling through to `return value * 10`); `coherence_score` / `count_above` accumulate over a `for v in values` body that guards `if v >= threshold:`; `above * 100 + coherence` over `[85, 42, 99, 60, 30, 75, 88, 50]` / threshold 50; `17680`. **Re-earned legitimately** — this was a #2261 false-green (`kernel-bmf-run` yielded `5170`) because a `return` inside an `if`/`for` body did not short-circuit the enclosing function. Closed by the return-signal threaded through `py-eval-body-loop` / the IF-STMT, FOR, WHILE arms / `py-eval-module-loop` (the function-body walker) — see the PROVEN return-signal note | `python-bmf-eval.fk` (return-signal: three-slot statement-result `(value env returned)`; `py-stmt-return` tags a RETURN; every block arm + the module-loop short-circuit on `returned=1`; no lift change, no kernel change) | CPython `17680` · Rust (bootstrap) `17680` · `kernel-bmf-run` `17680` |
| 2026-06-01 | form/form-kernel-ts/seedbank/python-adapter/examples/endpoint_coherence_weight_demo.py | the body of `/api/utils/coherence_weight` as pure Python — same early-guard `weighted_score` + `for`-accumulator shape as python_substrate_demo, wrapped in a top-level `coherence_weight` that sums `above * 100 + coherence`; `[72, 38, 91, 55, 28, 67, 84, 45, 95, 12]` / threshold 50; `16185`. **Re-earned legitimately** — this was a #2261 false-green (`kernel-bmf-run` yielded `5240`) for the same return-short-circuit gap; closed by the same return-signal breath | `python-bmf-eval.fk` (return-signal threading, shared with python_substrate_demo; no lift change, no kernel change) | CPython `16185` · Rust (bootstrap) `16185` · `kernel-bmf-run` `16185` |
| 2026-06-01 | form/form-kernel-ts/seedbank/python-adapter/examples/python_import_demo.py | the import arm — `import math` + `from math import sqrt, pi`, then `math.sqrt(2.25) + sqrt(0.25) + 2.0*math.pi + pi/2.0 + math.floor(3.7) + math.pow(2.0, 3.0)`; `20.853981633974485`. **Re-earned legitimately** — removed as the integrity-sweep third false-green (`kernel-bmf-run` errored `record_get: not a record: Null`, no value) because the Form-native lift/eval had no import surface. The light path: no new ontology category (PY-BMF-IMPORT 501 / FROM-IMPORT 502 already existed), no kernel parser change; the math natives are callable bare from Form in all three kernels. Lift `import`/`from` → PY-BMF-IMPORT / PY-BMF-FROM-IMPORT; eval binds a `py-module` marker (module) and `py-native-fn` markers / resolved consts (from-import); one resolution table `py-math-resolve` dispatched from the ATTR / METHOD-CALL / CALL arms. Bare-name path untouched (markers only exist post-import) | `python-bmf-lift.fk` (`lift-import` + `lift-from-import` + dispatch) · `python-bmf-eval.fk` (IMPORT / FROM-IMPORT statement arms + `py-module`/`py-native-fn` markers + `py-math-resolve` + ATTR/METHOD-CALL/CALL checks) | CPython `20.853981633974485` · Rust (bootstrap) `20.853981633974485` · `kernel-bmf-run` `20.853981633974485` |

**The first walking step:** with the G4 row recorded and G1+G3 now also
landed, the manifest's lifecycle is no longer a future-tense convention.
It has its first arrival in both columns. Every future Form-native parity
proof appends below; every Phase-A file whose proofs accumulate to
coverage moves to COMPOST READY; every composted file moves to RELEASED.

The body sees its first cell move through the discipline. The path becomes
walkable because the first step has been walked.

**Integrity sweep (2026-06-01) — every COMPOST READY row re-measured in
isolation.** After #2261 removed two false-greens, the *whole* COMPOST READY
set was re-verified: each demo measured in its **own `mktemp -d`** (its `.py`
copied in, `python-compile` → `.fk` + `form-kernel-rust` run there,
`kernel-bmf-run` using its own internal work-dir) so no `/tmp/*.fk` or
`examples/*.fk` bleed between runs. Extractions reproduced the suite's exact
method (CPython `ast`-eval of the final `Expr`, Rust-bootstrap `.fk`,
Form-native `kernel-bmf-run`). The harness was first validated by reproducing
the two known #2261 false-greens (`python_substrate_demo` `17680/17680/5170`,
`endpoint_coherence_weight_demo` `16185/16185/5240`).

Outcome: **13 of the rows are genuinely three-way green** at their recorded
values (CPython == Rust-bootstrap == kernel-bmf for every one):
`python_bridge_demo` `720`, `python_demo` `40949`, `python_assign_demo` `45`,
`python_imperative_demo` `45370`, `python_range_demo` `41650`,
`python_builtins_demo` `131`, `python_string_demo` `45`,
`python_lambda_demo` `216`, `python_dict_demo` `88`,
`endpoint_nodeid_distance_demo` `7`, `endpoint_lattice_stats_demo` `1089`,
`python_float_demo` `4.875`, `endpoint_weighted_average_demo` `0.8125`. One
**false-green** was found and removed — `python_import_demo` (`kernel-bmf-run`
errors `record_get: not a record: Null`; see the third-false-green note
above). One **duplicate** `endpoint_weighted_average_demo` row (a byte-twin of
the canonical row) was composted as ledger sediment — its value was correct,
it was just listed twice. The table now lists each green demo once and every
green is attested under isolation; the ledger is true at the count it honestly
reaches.

**Count climbs to 15 (2026-06-01, `claude/return-signal-fix`).** The
return-signal breath re-earned the two rows the #2261 sweep removed. Both
re-measured under the same isolated-tempdir method — `python_substrate_demo`
`17680/17680/17680`, `endpoint_coherence_weight_demo` `16185/16185/16185`,
CPython == Rust-bootstrap == kernel-bmf for each. The 13 rows above held green
through the change (the return-signal touches the shared body-eval paths, so
every one was re-spot-checked under isolation and none regressed). The ledger
now stands at 15 genuinely three-way green demos.

**19/20 green — false-green caught and corrected (2026-06-01,
`claude/parity-bmf-fix`).** A prior pass (PR #2275, since corrected) flipped the
default to `kernel-bmf` on a claim of 20/20. Re-measurement under isolated
tempdirs against freshly rebuilt Go + Rust kernels (main `d248767e`) showed the
claim false: **19 of the 20 demos are genuinely three-way green; one diverges.**
The flip was reverted and the count restored to honest.

| Demo | Three-way value | Demo | Three-way value |
|---|---|---|---|
| `python_bridge_demo` | `720` | `python_class_demo` | `176` |
| `python_demo` | `40949` | `python_dict_demo` | `88` |
| `python_assign_demo` | `45` | `endpoint_nodeid_distance_demo` | `7` |
| `python_imperative_demo` | `45370` | `endpoint_nodeid_compatibility_demo` | `2` |
| `python_substrate_demo` | `17680` | `endpoint_weighted_average_demo` | `0.8125` |
| `python_range_demo` | `41650` | `python_inheritance_demo` | `337` |
| `python_builtins_demo` | `131` | `endpoint_lattice_stats_demo` | `1089` |
| `python_lambda_demo` | `216` | `python_string_demo` | `45` |
| `python_import_demo` | `20.853981633974485` | `python_float_demo` | `4.875` |
| `endpoint_coherence_weight_demo` | `16185` | — | — |

The 19 above are confirmed three-way green (CPython == Rust-bootstrap ==
kernel-bmf), each at its true distinct value, with adversarial novel-expression
checks proving `kernel-bmf-run` computes Form-native rather than echoing CPython.
`./validate.sh` corroborates: 209 OK / 1 divergent (the pre-existing untracked
`seeded-bytes-recipe-band.fk`, excepted), with `python-bmf-arithmetic-band`,
`python-bmf-eval-band`, `python-bmf-lift-band`, and `python-class-band` all ok.

**The lone divergent demo — `python_typing_compose_demo`.** CPython `241` ==
Rust-bootstrap `241`, but `kernel-bmf-run` **errors** (`_plus: unsupported
operand types`, no value). The earlier "four-way incl kernel-bmf" claim
(commit #2272) does not hold under isolated measurement — it was a `/tmp/*.fk`
bleed false-green of the same shape as the #2261 incident above. The gate is
*not* the type annotations (bare `header: str`, `Optional[int]` returns,
`List[Bucket]` params all pass in isolation) and *not* annotated-assignment.
It is **multi-attribute-instance direct-attr-read composition**: a class whose
`__init__` stores two attributes, then two direct attribute reads combined.
Minimal repro (each in its own tempdir):

```
class B:
    def __init__(self, base, weight):
        self.base = base
        self.weight = weight
r = B(3, 4)
r.base + r.weight        # CPython 7; kernel-bmf errors _plus: unsupported operand types
```

Single-attribute instances pass, and attr-read composed with a *method* call
passes (`r.score() + r.base` → ok) — so the gap is specifically two direct
attribute reads off a multi-attribute record in `python-bmf-eval.fk`'s
record/attr storage (the second attr does not resolve to its int value). The
demo hits it via `red.base + blue.base + green.base`. Closing that eval arm
three-way is the remaining compost work; the default flips to `kernel-bmf` only
then. Until then `ts-eval` stays the default, and the Phase-A
Python-adapter bootstrap tissue (`lang-python.ts` and friends) is **not yet
residue** — it composts only when all 20 are green.

**What composts when a demo reaches COMPOST READY.** The `.py` input
**stays** — the parity suite reads it on every run (it's the substrate the
gate exercises). The emitter artifact that composts is the demo's checked-in
`.fk`: the parity suite regenerates it fresh on every run
(`parity_suite.sh` compiles `.py` → `.fk` immediately before executing it),
so the committed copy is pure residue. The four demos above had their `.fk`
emitter artifacts released — see the RELEASED section below for the first
arrival of the third lifecycle step.

---

## RELEASED — rows whose compostable tissue has actually been removed

A row appears here when a file named for compost is *removed from the tree*
in a merged PR. This is the third and final lifecycle step: tissue →
PROVEN → COMPOST READY → **RELEASED**. The body no longer carries the
weight; git remembers it if it's ever needed again.

| Date | PR | What released | Why it was safe | Regeneration path |
|---|---|---|---|---|
| 2026-05-31 | `claude/release-proven-bootstrap` | The four COMPOST-READY demos' emitter artifacts: `python_bridge_demo.fk`, `python_demo.fk`, `python_assign_demo.fk`, `python_imperative_demo.fk` (Phase B "emitted .fk files" tissue) | All four demos reached COMPOST READY (Form-native value proven three-way). The `.fk` files are emitter output nothing reads as a committed input — `parity_suite.sh` overwrites each one via `python-compile` immediately before running it; `form/validate.sh` (the three-way kernel gate) walks `form-samples/` + `form-stdlib/` and never references the seedbank examples; no CI workflow, doc link, or script consumes the committed `.fk` content | `parity_suite.sh` regenerates each on the next run; or `npx tsx src/main.ts python-compile examples/<name>.py examples/<name>.fk` from the adapter dir |
| 2026-05-31 | `claude/release-bootstrap-fk-artifacts` | 12 more emitter `.fk` artifacts (the rest of the regenerable residue): `endpoint_lattice_stats_demo`, `endpoint_nodeid_distance_demo`, `python_builtins_demo`, `python_class_demo`, `python_dict_demo`, `python_float_demo`, `python_import_demo`, `python_inheritance_demo`, `python_lambda_demo`, `python_range_demo`, `python_string_demo`, `python_substrate_demo` (all `.fk`) | Same safety shape as the first row: each has a `.py` sibling in `PARITY_FILES`, so `parity_suite.sh` overwrites it via `python-compile` before every run — committed emitter output with no live reader. **Deliberately KEPT** (not pure residue this pass): `endpoint_lattice_stats_live.fk` (no `.py` sibling — not regenerable, possibly hand-authored), `python_typeann_demo.fk` (has `.py` but not in PARITY_FILES — suite won't auto-recreate), and 4 demos with in-flight local edits from a live parity run (`endpoint_coherence_weight_demo`, `endpoint_nodeid_compatibility_demo`, `endpoint_weighted_average_demo`, `python_typing_compose_demo`) — never force-remove tissue someone is actively touching | `parity_suite.sh` regenerates each on the next run; or `npx tsx src/main.ts python-compile examples/<name>.py examples/<name>.fk` |

**The first composted cell.** With this row the lifecycle has walked its
full length once: a shape proved Form-native, its demo reached COMPOST
READY, and its emitter residue is gone from the tree. The `.py` inputs and
the bootstrap parser tissue (`lang-python.ts` and friends) stay — they
compost only when *all* `PARITY_FILES` rows reach COMPOST READY. What moved
here is exactly the residue that was safe to move: regenerable emitter
output with no live reader.
