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

**The pattern**: each agent's grammar is fine alone. The walker overflows when ~7 more rules pile on top of the attr-access + comprehensions surface. Either combination (exception, f-strings/slicing) triggers it; both add ~7 rules. This is a real combinatorial behavior in the kernel's tree-walking dispatch — not a rule bug. The exception agent's grammar validated clean against the base, so the trigger is the *interaction* with attr-access/comprehensions, not the rules themselves.

**What this points at**: the kernel's walker dispatch grows non-linearly with rule count above some threshold. For the goal's "use observations to improve performance, resource use" — this is a concrete optimization target on the Form kernel side. The walker likely tries all rules against each input and the cross-rule search explodes when many rules have overlapping initial-token patterns (`name . …`, `name ( …`, `[ name for …`, `( name for …`, `try : …`).

**Branches not merged today** (clean in isolation, blocked by the kernel ceiling):

- `worktree-agent-a594976002747c313` — exception handling (try/except/finally bodies + raise calls)
- `worktree-agent-adabbde639636adb8` — f-strings + slicing extensions

Both validated cleanly on their own; both push the merged grammar past the kernel walker's current scaling limit. They sit on origin awaiting either kernel-walker optimization or a rule-table reorganization that reduces dispatch search depth.

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
