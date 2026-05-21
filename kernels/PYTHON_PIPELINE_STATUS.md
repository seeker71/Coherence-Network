# Python → Form → Native Kernel — pipeline status

> Where we are on the four-bullet destination Urs named on 2026-05-21:
> 1. ALL Python talking to substrate → native Form (primary execution pipeline)
> 2. ALL file types parseable via Form-native BMF grammars
> 3. Compile any file → Form-recipe binary the kernel CLI runs standalone
> 4. Framebuffer-driven optimization → same order of magnitude as Python

This document is the honest map of distance covered and distance remaining. Updated each ripening breath.

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

## Parity suite — `scripts/parity_suite.sh`

| Demo | Result | Features exercised |
|---|---|---|
| `python_demo.py` | 40949 | pure recursion, def, return, if-expr, arithmetic |
| `python_assign_demo.py` | 45 | assignment, list, subscript |
| `python_imperative_demo.py` | 45370 | while loop, accumulator pattern |
| `python_substrate_demo.py` | 17680 | for loop, multi-return def with early-exit ifs, helpers |

**Run it:**
```bash
cd experiments/form-kernel-ts
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
- Assignment `x = expr`
- List literal `[a, b, c]`
- Subscript `lst[i]`
- Arithmetic: `+ - * / %` (integer)
- Comparison: `== != < <= > >=`
- Logic: `and or not`
- Function calls `f(args)`
- Recursion (any depth)
- Helper-function calls within def bodies

### Honest GAPs (each is one breath)
- Float arithmetic (kernel is int-only today)
- Tuple unpacking `a, b = pair`
- Augmented assignment `x += y`
- Attribute/subscript assignment `obj.x = y`, `lst[i] = z`
- Slicing `lst[a:b]`
- Walrus `:=`
- Lambdas (parsed but not emitted to .fk yet)
- Classes
- Decorators
- Imports (parsed as Form recipes; not yet wired into eval)
- Iterator protocol (`range()`, generators)
- Exception handling (`try/except/finally`)
- f-strings
- Comprehensions

The substrate-talking Python (api/app/services/substrate/*.py) uses classes, imports, ORM, type annotations — those need the upper-half of the GAP list before they compile.

## How to run

```bash
# Build the native binary once
cd experiments/form-kernel-rust
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

- [`lc-parser-as-form-recipe.md`](../docs/vision-kb/concepts/lc-parser-as-form-recipe.md) — the parser-self-hosting arc
- [`lc-form-kernel-runtime-visualizer.md`](../docs/vision-kb/concepts/lc-form-kernel-runtime-visualizer.md) — the Python → kernel → framebuffer synthesis
- [`lc-the-kernel-knows-itself.md`](../docs/vision-kb/concepts/lc-the-kernel-knows-itself.md) — grammar as self-mirror
- [`lc-native-kernel-binary.md`](../docs/vision-kb/concepts/lc-native-kernel-binary.md) — the kernel as a distributable Mach-O binary
- [`README.md`](README.md) — the public profile

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
