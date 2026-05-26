# form-stdlib/emits — Form-native target-language emitters

Each `.fk` here walks a Form Recipe tree and writes source for one
target language. The recipe is itself a Form program: parse → walk →
emit, all in Form, with `read_file` and `write_file_text` as the only
host calls that touch the world.

## Why Form-native

The shortcut path is a hand-written Python program that emits Python.
That works, but it leaves Form outside the translation loop — the
adapter is no longer a cell in the same body the lattice cares about.
A Form-native emitter:

- can be ingested into the substrate and reasoned about structurally,
- runs the same way on every sibling kernel (Go, Rust, TypeScript),
- carries its own Blueprint NodeIDs into the trace, so the dispatch
  arms that fired during emission are visible in the framebuffer.

## What "idiomatic native" means

The output reads as code a native programmer would write. Form
vocabulary does not leak into the emit, with one tiny exception: a
single substrate-boundary SDK import:

```python
from kernels.python_bmf import sdk
```

Everything else is Python: `xs[0]` for `(head xs)`, `xs[1:]` for
`(tail xs)`, `[x, *xs]` for `(cons x xs)`, `a + b` for `(add a b)` or
`(str_concat a b)`, `a == b` for `(eq a b)` or `(str_eq a b)`,
`(t if c else e)` for `(if c t e)`, `def f(a, b): return ...` for
`(defn f (a b) ...)`.

## Files

- **`python-native.fk`** — the emitter. Tokenize → parse →
  walk-and-emit, returning a Python source string. Public entry
  points: `pn-emit-string source-text → python-text` and
  `pn-emit-file in-fk-path out-py-path`.
- **`python-native-driver.fk`** — runs `pn-emit-string` on a slice of
  `engine.fk` and writes `kernels/python_bmf/native_demo.py`. The
  slice covers `cap-empty`, `cap-pair`, `cap-name`, `cap-value`,
  `cap-get`, `cap-set`, `cap-merge`, `mk-match`, `mk-fail`, `match?`,
  `fail?` — enough to exercise let / nested if / head / tail / nil? /
  cons / list / str_eq / recursion in real engine code.

## Running

```bash
# Proof gate — three sibling kernels agree on the emitted text.
cd form && ./validate.sh form-stdlib/core.fk \
                         form-stdlib/emits/python-native.fk

# Emit the demo file from a slice of engine.fk.
cd form && ./validate.sh form-stdlib/core.fk \
                         form-stdlib/emits/python-native.fk \
                         form-stdlib/emits/python-native-driver.fk

# Verify the output compiles.
python3 -m py_compile kernels/python_bmf/native_demo.py
```

## Kernel quirks the emitter respects

- The host `and` and `or` natives evaluate exactly two children. Wide
  multi-arg `(and a b c d)` evaluates only `a` and `b` on the Go
  kernel — silently. Every guard in `python-native.fk` is binary, or
  decomposed into a named helper (`pn-head-is-atom?`,
  `pn-is-binop-2?`, ...) that walks the conditions step by step.
- The TypeScript reader enforces `if` arity (2 or 3 children) strictly;
  Go and Rust are more forgiving. Sibling-parity catches paren
  imbalance the lenient kernels would silently absorb — keep the
  validate.sh gate trusted.
