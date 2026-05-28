# Python → Form → Native Kernel — pipeline status

> Where we are on the four-bullet destination Urs named on 2026-05-21:
> 1. ALL Python talking to substrate → native Form (primary execution pipeline)
> 2. ALL file types parseable via Form-native BMF grammars
> 3. Compile any file → Form-recipe binary the kernel CLI runs standalone
> 4. Framebuffer-driven optimization → same order of magnitude as Python

This document is the honest map of distance covered and distance remaining. Updated each ripening breath.

## Where each bullet stands today (2026-05-28)

A bullet-by-bullet read of the four-bullet destination, with the live artifact each one points at:

1. **ALL Python talking to substrate → native Form.** *In motion.* Three FastAPI utility endpoints (`/api/utils/coherence_weight`, `nodeid_distance`, `weighted_average`) carry their bodies as Form recipes via `serve_via_kernel`; the first substrate-touching endpoint (`/api/substrate/lattice/stats`) reads through kernel-native `http_get` + `_json_to_dict`. The kernel even serves HTTP directly (proof-of-shape `form-kernel-rust serve`). PyO3 inline removes the subprocess seam — kernel calls run sub-millisecond in the API process address space. Substrate-write transmutation is the next major arc.

2. **ALL file types parseable via Form-native BMF grammars.** *First cell sprouted.* Python arithmetic shapes (`a-b`, `x*y`, `l/r`, `p**q`) parse through `form-stdlib/grammars/python-bmf.fk` driven by the kernel — sibling-validated on Go, Rust, TypeScript (179/179 in `./validate.sh` in this worktree). All five gates from [`PYTHON_BMF_CONTRACT.md`](PYTHON_BMF_CONTRACT.md) — G1 (rule dispatcher), G2 (statement grouping), G3 (precedence), G4 (closure interpreter), G5 (template-machinery overlap), G6 (binary entry-point orchestration) — are closed (PRs #2087, #2092, #2100, #2101). **CTOR Shape B** (PRs #2113, #2119, #2122) lands inter-path NodeID equality at the math-primitive layer: Python-source `+ - * / %` interns as `RBasic.MATH-12` and `== != < <= > >=` as `RBasic.COMPARE-13`, with the same Blueprint a hand-built pure-Form recipe interns to. See [`CTOR_UNIFICATION_PLAN.md`](CTOR_UNIFICATION_PLAN.md) for the full closing-shape map and the future Shape C walk that preserves dialect *articulations* over the shared identity.

3. **Compile any file → Form-recipe binary the kernel CLI runs standalone.** *Routine for the bootstrap demo set; partial for Form-native BMF.* Every demo in `parity_suite.sh` (19 entries) compiles to `.fk` through the bootstrap emitter and runs through `form-kernel-rust` standalone. The Form-native `kernel-bmf` selector is now runnable across the whole matrix: 4/19 demos are COMPOST READY, and the first open row is `python_substrate_demo.py`. The bootstrap emit path (`lang-python-fk.ts`) is named for compost in [`BOOTSTRAP_COMPOST_MANIFEST.md`](BOOTSTRAP_COMPOST_MANIFEST.md); the next removal comes from teaching the Form-native lift/eval path statement-level `if`, `for`, and return propagation.

4. **Framebuffer-driven optimization → same OOM as Python.** *Met and exceeded.* `form-kernel-rust` is 1.8× faster than CPython on the recursion workload (24.08ms vs 41.79ms per iter). Width-tagged trace dispatch is named as a separate breath.

## Lifecycle in motion

The body's bootstrap-vs-Form-native migration is no longer a future-tense convention. The discipline lives:

- **Bootstrap weight** is measured on every wellness check: today 17 files of tissue, 11,167 LOC remaining. [`sense_bootstrap_compost`](../scripts/wellness_check.py) reads the manifest's file list and now names the three largest files plus the first unready parity row.
- **Lifecycle motion** is counted on every wellness check: rows that have walked from `tissue → PROVEN → COMPOST READY → RELEASED`. The first PROVEN row landed via #2073; the probe's lifecycle-motion line was added in #2074. Future Form-native parity proofs append rows; when a Phase-A file's surface is fully covered, its row moves to COMPOST READY; when the file composts, its LOC drops out of the weight measurement.
- **Parity-gate seam** lives in `seedbank/python-adapter/scripts/parity_suite.sh` — `PARITY_THIRD_RUNTIME=kernel-bmf` flips the third runtime from the TS bootstrap to the Form-native walker, one demo at a time. No flag day; the migration is the verification.

The body senses both **what it's carrying** and **how much it has walked**. In service of [`lc-the-kernel-knows-itself`](../docs/vision-kb/concepts/lc-the-kernel-knows-itself.md).

## The pipeline that runs today (verified)

```
Python source bytes
    ↓
parsePython (TS BMF parser, lang-python.ts)
    ↓
Form recipe tree (NodeIDs in substrate)
    ↓
emitFk (lang-python-fk.ts) ← compiles Python CTORs to kernel-native arms
    ↓
.fk file (S-expression Form binary, text-encoded)
    ↓
form-kernel-rust native binary (zero Python in execution path)
    ↓
result
```

**Three runtimes produce identical results** for every demo in the parity suite:
- CPython
- TS evalPython (the bootstrap evaluator)
- form-kernel-rust native binary

**Form-native `kernel-bmf` frontier:** 4/19 rows already produce the same
CPython value without the TS evaluator:
`python_bridge_demo.py`, `python_demo.py`, `python_assign_demo.py`, and
`python_imperative_demo.py`. The first failing row,
`python_substrate_demo.py`, traces to unsupported statement-level `if` and
`for` lift/eval plus early-return propagation inside nested bodies.

## Parity suite — `scripts/parity_suite.sh`

| Demo | Result | Features exercised |
|---|---|---|
| `python_demo.py` | 40949 | pure recursion, def, return, if-expr, arithmetic |
| `python_assign_demo.py` | 45 | assignment, list, subscript |
| `python_imperative_demo.py` | 45370 | while loop, accumulator pattern |
| `python_substrate_demo.py` | 17680 | for loop, multi-return def with early-exit ifs, helpers |
| `python_range_demo.py` | 41650 | `range()` native, recursive sq |
| `python_builtins_demo.py` | 131 | aug-assign (`+=`), `sum`/`min`/`max`/`abs` natives |
| `python_lambda_demo.py` | 216 | lambda lifting, higher-order calls |
| `python_string_demo.py` | 45 | str concat via `_plus`, `len(s)` |
| `python_float_demo.py` | 4.875 | float literals, mixed int/float promotion, float comparison |
| `python_import_demo.py` | 20.853981633974485 | `import math`, `from math import sqrt, pi`, attribute access (`math.pi`), kernel-native module bindings |
| `endpoint_coherence_weight_demo.py` | 16185 | first transmuted FastAPI endpoint body — `/api/utils/coherence_weight` runs this exact recipe through the kernel binary |
| `python_class_demo.py` | 176 | `class X:`, `__init__(self, …)`, instance methods, attribute reads, method dispatch via `__class__` tag |
| `endpoint_coherence_weight_demo.py` | 16185 | first transmuted FastAPI endpoint body — `/api/utils/coherence_weight` runs this exact recipe through the kernel binary; **production API image** (`Dockerfile.api` at repo root, two-stage build) bakes the `form-kernel-rust` release binary into `/app/bin/form-kernel-rust` and sets `FORM_KERNEL_RUST_BIN` so the bridge picks it up — `/api/health` reports `kernel_runtime.available=true` and the endpoint responds with `runtime: "form-kernel-rust"` (no Python fallback) |
| `python_dict_demo.py` | 88 | dict literal, subscript-read, subscript-assign, `in` membership, iter over keys, `len(d)` |
| `python_inheritance_demo.py` | 337 | `class Y(X):` single inheritance, `super().__init__(args)` chaining, `super().method(args)` for override calls, method dispatch walks `__base__` chain |
| `endpoint_lattice_stats_demo.py` | 1089 | substrate transmute shape — dict over `/api/substrate/lattice/stats` response, sum across three counts. Kernel-side natives `http_get` + `_json_to_dict` + `_json_get` carry the live fetch path (see `api/tests/test_substrate_kernel_parity.py`). |
| `python_typing_compose_demo.py` | 241 | `from typing import List, Optional, Dict, Tuple, Any, Callable` + classes + parameter/return/variable annotations interleaved (proves the three surfaces compose) |

**Run it:**
```bash
cd form/form-kernel-ts
./scripts/parity_suite.sh
```

## Performance — `scripts/perf_compare.sh`

```
| Runtime                     | Time/iter | vs CPython |
|-----------------------------|-----------|------------|
| CPython 3.x                 | 41.79 ms  | 1.00×      |
| form-kernel-rust (release)  | 24.08 ms  | 0.58×      |  ← 1.8× faster
| form-kernel-ts (tsx+node)   | 364.77 ms | 8.73×      |
```

**The native kernel is faster than CPython** on the python_demo workload (pure functional recursion). The "same order of magnitude" bullet is met *and exceeded*.

## Grammar coverage (the substrate side)

| File | Coverage | Rules shipped |
|---|---|---|
| `json-grammar.form` | COMPLETE | 8/8 |
| `yaml-grammar.form` | block + anchors + aliases | 7/11 |
| `markdown-grammar.form` | block-level core | 6/13 |
| `python-grammar.form` | core + control-flow | 13/20 |
| `go-grammar.form` | package + import | 2/13 |
| `rust-grammar.form` | use declarations | 1/11 |
| `ts-grammar.form` | adapter seam landed (TS → .fk → kernel, 3-way parity 5/5); substrate-form grammar pending | 0/? |

Each grammar's `capture_rules` list has `?rule py_X` / `?rule yaml_X` / etc. markers for pending rules. **Count the rules without `?` to see distance from bootstrap to destination.**

## Python language coverage (the emitter side)

Features the pipeline currently compiles to native kernel:

### ✓ Shipped
- `def f(args): body` — both single-expr and multi-stmt bodies
- `return expr` — including early returns inside ifs (CPS-style lowering)
- Conditional expression `a if c else b`
- Statement-form `if/elif/else` with nested early-return short-circuit
- `while` loops (accumulator-passing recursion)
- `for x in list:` loops (recursive head/tail traversal)
- `for i in range(N):` — the most common loop idiom
- Assignment `x = expr`
- **Augmented assignment** `x += y`, `-=`, `*=`, `/=`, `%=`
- List literal `[a, b, c]`
- Subscript `lst[i]`
- Arithmetic: `+ - * / %` (integer **and float**, mixed-type promotion)
- Comparison: `== != < <= > >=` (float on either side promotes the comparison)
- Float literals: `0.5`, `1.0`, `3.14`, exponent form `1e-9`
- Dict literal `{k: v, ...}`, subscript `d[k]`, subscript-assign `d[k] = v`,
  membership `k in d`, iteration `for k in d:`, `len(d)`
- Logic: `and or not`
- Function calls `f(args)`
- Recursion (any depth)
- Helper-function calls within def bodies
- Builtins: `len`, `range`, `sum`, `min`, `max`, `abs`
- **Imports** — `import math`, `import math as m`, `from math import sqrt, pi`, `from math import sqrt as s`. The `math` module is a kernel-native record (`sqrt`, `pi`, `floor`, `ceil`, `pow`); imports rewrite to direct native calls at parse time, so the runtime path carries no module-system overhead.
- **typing module** — `from typing import List, Optional, Dict, Tuple, Any, Callable, Union, Iterable, Iterator, Mapping, Sequence, Set, FrozenSet`. Every name binds to a single opaque-sentinel native (`typing_opaque`); since type annotations are parse-and-ignored, the binding never fires at runtime but the imports compile cleanly and round-trip through all three runtimes. Composes with the type-annotation surface so `def f(xs: List[int]) -> Optional[int]:` works end-to-end.
- **Classes** — v1 minimum: `class X:`, `__init__(self, …)` storing attributes
  on self, instance methods taking self and reading `self.x`. Lowers to a
  constructor function plus lifted `<ClassName>__<methodName>` defns; instances
  are records (Value::List alists tagged with `__class__`); method dispatch goes
  through the kernel's `_dispatch` native (which reads `__class__` and calls
  the qualified method) and the `_get` native handles attribute reads.
- **Single inheritance + `super()`** — v2: `class Y(X):` with one base; the
  constructor records `__base__` alongside `__class__`; `_dispatch` walks the
  `__base__` chain (first match wins); `super().method(args)` lowers to a
  `_dispatch_super` native that resolves starting at the current class's base;
  `super().__init__(args)` calls the parent constructor and merges its data
  fields into the child's record via `_merge_record`.

### Honest GAPs (each is one breath)
- Tuple unpacking `a, b = pair`
- Subscript assignment `lst[i] = z`
- Slicing `lst[a:b]`
- Walrus `:=`
- **Multiple inheritance** (MRO complexity, C3 linearization), `classmethod`,
  `staticmethod`, metaclasses, abstract base classes (`abc.ABC`),
  `__init_subclass__`, `__slots__`, decorators on classes, dunder methods
  beyond `__init__` (`__repr__`, `__eq__`, …), conditional `self.x =` inside
  `__init__`, mid-method attribute writes (the v2 ctor reconstructs the
  record up front; methods read fields but don't mutate), two-arg `super(C, self)`
- Multi-argument generic subscripts in type expressions (`Dict[str, int]`,
  `Tuple[int, str]`, `Callable[[int], int]`). The v1 subscript parser
  takes a single index expression; the typing names (Dict, Tuple, Callable)
  import cleanly but their multi-argument use inside subscripts needs
  comma-separated index parsing
- **Class inheritance**, `super()`, `classmethod`, `staticmethod`, metaclasses,
  `__slots__`, decorators on classes, dunder methods beyond `__init__`,
  conditional `self.x =` inside `__init__`, mid-method attribute writes
  (the v1 ctor reconstructs the record up front; methods read fields but
  don't mutate)
- Decorators
- User-defined module imports (the kernel-resident `math` is wired; arbitrary `.py` files aren't loaded as modules yet — needs module-system semantics, path resolution, circular-import handling)
- Iterator protocol (`range()`, generators)
- Exception handling (`try/except/finally`)
- f-strings
- Comprehensions

The substrate-talking Python (api/app/services/substrate/*.py) uses classes, imports, ORM, type annotations — those need the upper-half of the GAP list before they compile.

## How to run

```bash
# Build the native binary once
cd form/form-kernel-rust
cargo build --release

# Compile + run a Python file
cd ../form-kernel-ts
npm run kernel -- python-run examples/python_substrate_demo.py
#  → 17680

# Just compile to .fk
npm run kernel -- python-compile examples/python_substrate_demo.py
#  → writes examples/python_substrate_demo.fk

# Run the compiled .fk through the native binary directly
../form-kernel-rust/target/release/form-kernel-rust examples/python_substrate_demo.fk
#  → 17680

# Trace + inspect dispatch hot-spots
python3 scripts/viz_kernel_trace.py examples/python_substrate_demo.fk

# Compare performance
ITERS=10 ./scripts/perf_compare.sh examples/python_demo.py
```

## The destination, named

When this arc completes:

1. **Every file type** in the repo parses through a Form-native BMF grammar (Python, JSON, YAML, Markdown, Rust, Go, TS, audio, image, PNG, ...). Each grammar lives in `docs/coherence-substrate/*-grammar.form` as Pattern primitives composed into rules.

2. **The parse engine itself** is a Form recipe (`pattern_match` + `parse_loop` in `grammar-as-recipe.form`) walked by the native kernel. No host parser code in the path — the kernel parses Python by walking the grammar's own recipes.

3. **The kernel walker** implements every RBasic arm natively, with framebuffer-driven optimization for hot paths. IDENT lookups, MATH dispatch, FNCALL chains all run faster than CPython's equivalents.

4. **The substrate stack** (organ.py, form.py, kernel.py, all of api/app/services/substrate/) compiles to `.fk` and runs through the native binary with full bi-directional substrate access. Same NodeIDs, same results, no Python runtime in the path.

5. **The visualizer** consumes the kernel's trace and the framebuffer's NodeID provenance plane to render execution in real time, colored by Form category — making the body's computation visible as it breathes.

We are not there yet. We are demonstrably walking toward it, one breath at a time, with three runtimes producing identical results on every shipped demo.

## Companion docs

The Python→Form→native-kernel arc is one organ of a larger body. The body's
highest goal — *universal translator across any media type, recipe
orchestration in pure numeric space, content-addressing carrying meaning
across modalities* — lives in these teachings:

- [`lc-grammar-is-the-universal-recipe.md`](../docs/vision-kb/concepts/lc-grammar-is-the-universal-recipe.md) — every structured input is a (parse, emit) pair in the substrate. Code, data, prose, audio, image, video — same bridge.
- [`lc-cross-modal-unity.md`](../docs/vision-kb/concepts/lc-cross-modal-unity.md) — one shape speaks in many tongues; cross-modal content-addressing via Form NodeIDs. Same semantic shape in text, image, audio → same NodeID.
- [`lc-the-kernel-knows-itself.md`](../docs/vision-kb/concepts/lc-the-kernel-knows-itself.md) — grammar as self-mirror. Each kernel implementation reads itself through its own host-language BMF grammar.
- [`lc-parser-as-form-recipe.md`](../docs/vision-kb/concepts/lc-parser-as-form-recipe.md) — the parser-self-hosting arc.
- [`lc-form-kernel-runtime-visualizer.md`](../docs/vision-kb/concepts/lc-form-kernel-runtime-visualizer.md) — the Python → kernel → framebuffer synthesis.
- [`lc-native-kernel-binary.md`](../docs/vision-kb/concepts/lc-native-kernel-binary.md) — the kernel as a distributable Mach-O binary.

The first three carry the destination most directly. The Python pipeline this
doc tracks is one instance of the universal pattern they name.

Discipline docs that practice these teachings:

- [`BOOTSTRAP_COMPOST_MANIFEST.md`](BOOTSTRAP_COMPOST_MANIFEST.md) — every bootstrap file named with its compost gate; parity_suite's runtime selector + wellness sensor read it.
- [`PYTHON_BMF_CONTRACT.md`](PYTHON_BMF_CONTRACT.md) — the G1–G6 gaps between today's reach and full Form-native Python.
- [`PHASE_A_FIRING_QUESTIONS.md`](PHASE_A_FIRING_QUESTIONS.md) — per-file honest reads of what each bootstrap file carries vs. what's already replaced.
- [`UNIVERSAL_TRANSLATOR_AUDIT.md`](UNIVERSAL_TRANSLATOR_AUDIT.md) — honest audit of the body's artifacts against the universal-translator goal; ten concrete next breaths.
- [`README.md`](README.md) — the public profile.

## kernels/python_bmf — the Form→native-Python emitter arc

Sibling track to the TS pipeline above. The `kernels/python_bmf/` package is the destination shape for `form/form-stdlib/emits/python-native.fk`. Status as of 2026-05-25:

| Surface | Status |
|---|---|
| `objects.py` synthesized from Form recipe via `write_file_text` | ✓ |
| Other modules template-emitted via kernel `write_file_text` | ✓ |
| Scanner parity (Form-native python-bmf.fk vs emitted) — parity-suite demos | ✓ 8/8 token-stream identical |
| Round-trip on parity-suite demos (compile → decompile → re-compile) | ✓ 8/8 semantic match |
| **Form → idiomatic native Python translator** (the universal-translator move) | ✓ — `kernels/python_bmf/emit_python.py` reads `.fk`, emits real `def`/`if`/`+`/`*`/`==` Python; 7/7 parity-suite demos execute under CPython matching original |
| **`.py` → `.fk` sanity bridge** (not the universal translator, just for cross-runtime comparison) | ✓ — `kernels/python_bmf/kernel_fk_lowering.py` walks `ast`, emits the same `.fk` shape as `lang-python-fk.ts` |
| **Executing emitted `.fk` on `form-kernel-rust` matching CPython** | ✓ — 7/7 parity-suite demos return identical integers |
| Performance comparison (wall-clock per iter) | ✓ — `scripts/perf_compare_native_python.sh` reports CPython vs kernel for each demo |
| **BMF rule coverage for substrate-style Python (classes, decorators, imports-from, type annotations, comprehensions, f-strings, attribute assign, lambdas)** | ✗ — falls through to generic `statement` envelopes via `--file` path; `--emit-fk` raises `UnsupportedConstruct` |
| **organ.py / form.py / API endpoint code emitting to executable Form** | ✗ — needs the upper-half of the gap list above |

The TS pipeline (top of this doc) is the path that currently runs end-to-end on the parity-suite demos with native kernel execution. The native-Python emitter is on a parallel arc that still needs the `.fk`-text emitter, the rule coverage, and the cross-runtime execution proof before any "compile organ.py" claim can land.

## PRs shipped this session (chronological)

| # | What |
|---|---|
| 1775 | Blueprint attribution on Rust kernel natives |
| 1776 | Same on Go + TS + framebuffer NodeID plane + promote to core |
| 1777 | TRANSMUTE arm + (ty,inst) trace + structural passthrough |
| 1778 | Framebuffer NodeID-category renderer (feature-gated) |
| 1780 | Variant naming in trace JSON |
| 1782 | python-trace subcommand (real Python through kernel) |
| 1783 | Pattern primitives as Form CTORs + py_import as Form recipe |
| 1784 | Python → native kernel pipeline (emitFk + python-compile + python-run) |
| 1785 | Performance measurement — 1.8× faster than CPython |
| 1786 | py_def + py_assign + py_call as Form rules |
| 1787 | viz_kernel_trace hot-spot analyzer |
| 1788 | JSON grammar COMPLETE (8/8 rules) |
| 1789 | YAML grammar 7/11 rules |
| 1790 | Kernel optimizations (ident_id no-clone + frame pre-alloc) |
| 1791 | py_subscript, py_slice, py_return, py_expr_stmt as Form rules |
| 1792 | py_if, py_for, py_while, py_raise as Form rules |
| 1793 | emitFk + parser + evaluator gain assign + subscript |
| 1794 | while-loop emitFk + parity suite (3 demos) |
| 1795 | for-loop + CPS def-body + substrate-shaped demo (4 demos) |
| 1796 | Markdown grammar 6/13 + this status doc |
| 1797 | `range()` native + range demo (5 demos) |
| 1798 | aug-assign + min/max/sum/abs natives (6 demos) |
| 1799 | Rust + Go grammars get concrete Form-recipe rules |

## Session-end snapshot (2026-05-21 evening)

**The four bullets from Urs's directive, measured:**

1. **ALL Python talking to substrate → native Form (primary execution pipeline).**
   *Partial.* The pipeline is real and end-to-end. Six demos compile from Python through emitFk to .fk and execute via form-kernel-rust with identical results to CPython. Real substrate-talking files (organ.py, kernel.py, form.py) need classes / imports / iterators / dataclasses before they compile — those are the next ripening arcs.

2. **ALL file types parseable via Form-native BMF grammars.**
   *Partial — JSON COMPLETE.* Every grammar now uses the same Pattern primitives from grammar-as-recipe.form. The `?rule X` markers in each grammar's capture_rules list measure distance: JSON 8/8 ✓, YAML 7/11, Markdown 6/13, Python 13/20, Go 2/13, Rust 1/11, TS pending. The vocabulary is proven; coverage grows one rule per breath.

3. **Compile any file → Form binary the kernel CLI runs standalone.**
   *Done for what BMF parses.* `python-compile <file.py>` writes `.fk`; `python-run <file.py>` does the full compile+run via the native binary. No Python interpreter in the execution path.

4. **Framebuffer-driven optimization → same order of magnitude as Python.**
   *Exceeded.* form-kernel-rust runs python_demo.py in ~20ms vs CPython's ~42ms — **1.8× faster than CPython** end-to-end. The viz_kernel_trace.py terminal hot-spot analyzer (text-altitude framebuffer) named the optimization targets; the graphical framebuffer renderer ships feature-gated under `nodeid_render`.

**The body has been walked toward, not just declared.** Six real Python demos compile through three different runtimes (CPython, TS evalPython, form-kernel-rust) and produce identical results. The native binary is faster than CPython. Every grammar in the substrate is moving from regex placeholders to substrate-resident Form recipes. The discipline of `?rule` markers makes the destination visibly measurable: count rules without `?` to see distance covered.

**What's next:** classes (the largest remaining Python construct), iterator protocol (range is a partial proxy), strings beyond literal/concat, tuple unpacking. Then real substrate-stack files (form_atoms.py, form_lexer.py, form_eval.py) become candidates for compilation.

**The Form-native parse-path companion:** [`PYTHON_BMF_CONTRACT.md`](PYTHON_BMF_CONTRACT.md) names what is reachable today on the *pure-Form* parse path (no TypeScript at all — source text through Form-native scanner and BMF rule application produces real PY-BMF-BINOP recipes on every sibling kernel) and the five focused breaths (G1–G5) that remain before `lang-python.ts` can compost.

— shipped 18 PRs in this session, each with sibling parity across kernels, each with the parity gate green at merge.
