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
The bootstrap stays as the third runtime *until* `PARITY_THIRD_RUNTIME=kernel-bmf`
becomes the default — then the named files compost, one phase at a time.

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
(Go/Rust/TS can all read/write the same store). Possible shapes:

1. Kernel-native serialization to `.fkb` Form-binary artifacts as the
   canonical store (closest to the audit's #10 single-binary-distribution
   breath)
2. Kernel-native binding to PG/SQLite directly (replaces SQLAlchemy without
   changing the backend)
3. A hybrid — kernel-native primitives walk an underlying SQLAlchemy /
   PG / SQLite layer, but the *contract* is Form-side

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
| B | Adapter CLIs + scripts + emitted .fk files | **714** (~+20 .fk files) |
| C | Python bridge + form_runtime + self-host registry | **2,938** + utility-router rows |
| D | Foundational persistence + infrastructure | **TBD** (firing-questions in flight) |
| **Total** | | **~9,433 LOC + Phase D** of bootstrap tissue with named compost gates |

---

## The runtime-selector switch

`form/form-kernel-ts/seedbank/python-adapter/scripts/parity_suite.sh` carries
`PARITY_THIRD_RUNTIME` (env-var):

- `ts-eval` (default today) — the TS bootstrap evaluator. Backwards-compatible;
  every existing gate runs unchanged.
- `kernel-bmf` (the destination) — invokes `kernel-bmf-run <source.py>`,
  expecting the binary to read `.py` via `form-stdlib/grammars/python-bmf.fk`
  and execute via Form-native walker. **The binary doesn't exist yet.** The
  parity script prints a clear "deferred" message naming the file the
  Form-native path must learn to compile.

Switching the default from `ts-eval` to `kernel-bmf` is the single env-var
change that flips the third runtime. Each demo gets promoted individually
(file-by-file) as `kernel-bmf-run` learns to compile it. When all
`PARITY_FILES` are green under `kernel-bmf`, the Phase-A Python-adapter files
are residue.

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

**What G6 closes and what stays open.** G6 was the orchestration gap — the
pieces existed (Go compiler, Rust walker, Python BMF grammar) with no binary
on PATH to drive them together. That gap closes: `kernel-bmf-run` is the
walking shape. What G6 does NOT close: the parsed PY-BMF-* recipes are not
yet walked back to Python runtime values, so `kernel-bmf-run python_demo.py`
returns the statement count (15), not the program's CPython value (40949).
The driver swaps to a recipe-walking expression in the same script when G4
(closure interpreter) lands; the orchestration shape stays.

**Open contract for the next PROVEN rows:** `kernels/PYTHON_BMF_CONTRACT.md`
G1 (automatic rule dispatcher) unlocks composition of these arithmetic rules
into full expressions; G2 (statement grouping) unlocks `def` / `if` /
`return`; G3 (precedence climbing) makes `1 + 2 * 3` parse correctly; G4
(closure interpreter) is the gate that lets PROVEN rows progress to
**COMPOST READY** for the matching Phase-A file. With G6 closed, every
future G1–G4 increment is testable through `kernel-bmf-run` — no further
orchestration breath is needed.

**The first walking step:** with this row recorded, the manifest's lifecycle
is no longer a future-tense convention. It has its first arrival. Every
future Form-native parity proof appends below this row; every Phase-A file
whose proofs accumulate to coverage moves to COMPOST READY; every composted
file moves to RELEASED.

The body sees its first cell move through the discipline. The path becomes
walkable because the first step has been walked.
