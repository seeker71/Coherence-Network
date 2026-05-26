# `kernels/python_bmf/` — known gaps

## What was learned and composted on 2026-05-25

The session built a Python BMF compiler in two wrong shapes before the user surfaced the architectural mismatch:

1. **Hand-written Python emitter** (`emit_python.py`) — translated `.fk` text to Python via Python `ast`. The spec explicitly forbids hand-written Python beyond `sdk.py`/`__init__.py`/`README.md`; the emitter must be a Form recipe (`form/form-stdlib/emits/python-native.fk`).

2. **Form recipes translated to Python syntax** (`emitted/*.py`) — the emitted modules used Form vocabulary (`bmf_object`, `make_nodeid`, `apply_object_rule`, `head`, `tail`, `cons`, `str_concat`, …) rather than Python natives. This is not native Python; it's Form-recipe-execution dressed in Python syntax. The user's framing: *"python is supposed to execute only python, it may use the SDK to generate a node id to talk to the substrate, that's it."*

3. **Tautological cross-runtime parity** — the harness claimed "same compiler, two runtimes, byte-identical output." What it actually proved: two walkers (form-kernel-go and CPython loading recipes-translated-to-Python-syntax) executing **the same recipes** produce the same output. That's not a comparison; it's a tautology. The real comparison: Form-resident BMF compiler vs. native Python BMF compiler producing the same Recipe trees from the same input.

4. **Wrong-direction `.py → .fk` lowering** (`kernel_fk_lowering.py`) — Python `ast` to `.fk` text. The goal is the opposite direction: `.fk → native Python`.

**Composted files** (commit list visible in git history):

- `emit_python.py`, `kernel_fk_lowering.py`, `runtime.py`, `host_primitives.py`
- `emitted/{engine,source_compiler,compiler,python_bmf}.py` + `emitted/__init__.py`
- Hand-written `compiler.py`, `decompiler.py`, `parser.py`, `rules.py`, `objects.py`, `form_action.py`, `section_parser.py` (the original "destination Python package" — all wrong shape)
- All wrong-shape tests
- `scripts/cross_runtime_bmf_compile.sh`, `scripts/regen_emitted_python.py`, `scripts/perf_compare_native_python.sh`, `form/scripts/cross_runtime_parity.sh`, `form/form-stdlib/emits/python-bmf-scan-driver.fk`

## What remains aligned

- `sdk.py` — content-addressed NodeID, intern, SourceSpan, .fkb i/o, Lens. The legitimate substrate boundary the spec explicitly allows.
- `form/form-stdlib/grammars/python-bmf.fk` — Form-side parser rules. Recent extensions (from-import family, class shapes, decorators, type annotations) cover ~155 rules; the substrate-Python upper-half gap list (attribute access, exception handling, comprehensions, f-strings, async/await, generators, walrus, pattern matching) remains open as ordinary forward work.
- `form/form-stdlib/tests/python-bmf-*-band.fk` — three-kernel parity tests for those rules.

## What needs to happen next

1. **Write the real Form-native Python emitter** at `form/form-stdlib/emits/python-native.fk` — a Form recipe that walks a source-compiled Recipe tree and writes **idiomatic native Python** to disk via the kernel's `write_file_text` host call. Idiomatic means: Python `class`, `def`, `if/else`, `while`/`for`, `xs[0]` (not `head(xs)`), `xs[1:]` (not `tail(xs)`), `[x, *xs]` (not `cons(x, xs)`), `a + b` (not `str_concat(a, b)`), regex for tokenization, dict for rule registries, generators for streams. Form vocabulary appears only at the substrate boundary, via `from kernels.python_bmf.sdk import NodeID, intern_trivial_int, intern_trivial_string`.

2. **Round-trip proof** — the emitted Python source is fed as compiler input to the Form-resident Python BMF compiler (via `python-bmf.fk` rules); the resulting `.fkb` is semantically equivalent to the `.fkb` produced from the original Form source. Differences are named and minimized.

3. **Comparison the goal actually names** — Form-resident BMF compiler vs. native Python BMF compiler producing the same Recipe trees from the same Python source. NodeID semantics, not text equality. Performance and resource use observed across two truly distinct implementations.

## Form kernel walker hits a scaling ceiling around 175+ rules (2026-05-25 evening — observation from the parallel merge)

Five parallel agents extended `python-bmf.fk` in disjoint worktrees. Each branch validated clean in isolation (three-kernel agreement on its own + base). The sequential merge surfaced a real kernel constraint:

| Merge state | Rules | `validate.sh` result |
|---|---|---|
| Base + class + decorator + type-ann + from-import (prior session) | ~150 | clean |
| + Form-native Python emitter (disjoint surface, `emits/`) | ~150 | clean |
| + attribute access (`attr-chain`, `attr-assign-*`, method calls, chained method calls) | 156 | clean |
| + comprehensions (`list-comp-simple`, `set-comp-simple`, dict/genexp variants) | 162 | clean |
| + exception handling with bodies (`try-except-stmt`, raise-call variants) | 169 | **stack overflow in form-kernel-go walker (1 GB stack ceiling)** |
| + f-strings/slicing (in place of exception) | 169 | **same stack overflow** |

**First guess (wrong)**: the BMF object engine's `match-object-pattern` lacked cut/stop semantics that BML's `grammar-chars.fk` has, so rule-search exploded across alternatives. I ported cut/stop into `engine.fk` (commit `5baa60d0`) and re-tested the merge. **The merge still overflows.** The cut/stop port is valid forward work (rule-side adoption can prune the BMF object-engine search), but it does NOT fix this symptom.

**Actual root cause** (from reading the Go stack trace, not from architectural reasoning):

The recursion frames cycle at `main.go:1525-1530-1572-1605` — that's `RBasicCond` (if/else) inside `RBasicFnCall` (function call into body). Tracing the calls into Form source:

- `form/form-stdlib/source-compiler.fk:231 fsc-rules-loop` — **non-tail recursion**. The body holds `(let rest (fsc-rules-loop dialect body (next-line)))` then `str_concat`. Every line of the section body adds a Go stack frame that lives until ALL recursive calls return.
- `form/form-stdlib/source-compiler.fk:205 fsc-rule-line` — calls `fsc-find-string-from` four times per rule.
- `form/form-stdlib/source-compiler.fk:21 fsc-find-string-from-len` — per-character recursion through the section body. For a 150KB section body, that's 150K-deep recursion per call.

The growth is multiplicative: rules-loop frames × per-rule find-string calls × per-character scan depth. The Go kernel walker performs no tail-call elimination, so every Form self-call costs a Go stack frame. The 1 GB stack limit hits when section body × rule count exceeds ~2 million Go frames.

**Three honest fixes** (each addresses a different layer):

1. **Source-compiler side** (`fsc-rules-loop`, `fsc-find-string-from-len`): rewrite accumulator-style. Helps only IF the Go walker does TCO or recognizes tail-position self-calls. Today it doesn't.

2. **Kernel-walker side** (`form-kernel-go/main.go walk()`): add tail-call elimination — when `RBasicFnCall` is in tail position, reuse the frame instead of recursing. The character-engine's `cm-match-sequence` is tail-recursive by design; the BMF engine's `match-object-sequence` is too, post-cut/stop port. Both would benefit. This is the real cross-kernel optimization the goal's loop names.

3. **Iterative primitive**: add a kernel-native `for-each-line` or `find-string` that loops in Go rather than recursing through Form. Cheapest fix but pollutes the substrate with host-language primitives.

The cut/stop port to `engine.fk` (commit `5baa60d0`) stays — it's correct forward work for runtime BMF rule-search pruning. It does not address the source-compile-time symptom. Naming this honestly so the next breath works on the actual problem, not the guess I made.

## Open Python-BMF rule gaps (Form side)

## Open Python-BMF rule gaps (Form side)

The recent multi-agent breath landed rules for `from … import …`, class shapes, decorators, and type annotations. Still open in `python-bmf.fk`:

- Attribute access / method-call chains (`obj.x`, `obj.method()`, `obj.x.y`, `obj.method().another()`)
- Attribute assignment (`obj.x = y`)
- Exception handling (full `try/except/finally` with bodies, not just `pass`)
- Comprehensions (list, dict, set, generator)
- f-strings (the existing `fstring`/`fstring-format` rules cover only the simplest shape)
- Async / await (existing rules cover only `async def name(): pass` and `async with/for`-`pass`)
- Generators (`yield` rules exist but `yield from` and generator-expression context need more)
- Walrus operator in non-bare expressions
- Pattern matching (`match` / `case` headers exist but body bindings need expansion)
- Slicing beyond `[int:int]`

Each is a small-to-medium Form-side breath; the pattern is settled by the merged class/decorator/type-annotation work.
