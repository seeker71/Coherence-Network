# `kernels/python_bmf/` — substrate boundary for Python

The architectural target (`specs/form-binary-to-native-python-emitter.md`):

```
Form-resident BMF compiler  (Form recipes, walked by Go/Rust/TS kernels)
    ↓  parses Python source → Recipe tree
form/form-stdlib/emits/python-native.fk  (the Form-native adapter for Python)
    ↓  walks Recipe tree, emits idiomatic native Python
emitted .py files  (real Python — class, def, regex, dict, generators)
    ↓  run under CPython
same observable behavior as the Form-resident compiler
```

## What lives here

Only the substrate primitives Python lacks natively:

| File | Role |
|------|------|
| `__init__.py` | package marker + lineage |
| `README.md` | this file |
| `sdk.py` | `NodeID`, `intern_trivial_int/string`, `SourceSpan`, `.fkb` read/write, `Lens` |
| `KNOWN_GAPS.md` | honest map of what's open |

## What does NOT live here

- The emitter itself (`form/form-stdlib/emits/python-native.fk` — Form recipe, under construction)
- The emitted Python (none today; the Form-native emitter must produce it)
- Hand-written Python that emits Python (composted; was the shortcut)
- Hand-written Python that walks Form recipes in Python syntax (composted; same shortcut)
- Python `ast`-based `.fk` lowering (composted; wrong direction)

## What the SDK is for

Content-addressed structural identity is not native to Python. When emitted
Python code needs to talk to the substrate (build a node with a stable
NodeID, intern a value, read a `.fkb` artifact, attach a source span), it
imports from `sdk.py`. That import is the **only** Form vocabulary in
emitted Python — every other operation uses Python's natives (lists,
dicts, regex, classes, generators, operators).

## Status

Today (2026-05-25):

- The Form-resident BMF compiler exists and parses Python via `form/form-stdlib/grammars/python-bmf.fk` — 150+ rules now, recent extensions cover `from … import …`, `class …`, decorators (multiple shapes), and type annotations.
- The Form-native Python emitter (`form/form-stdlib/emits/python-native.fk`) is under construction. When it lands, it walks a Recipe tree and writes idiomatic Python via the kernel's `write_file_text` host call.
- The wrong-shape work created earlier today — hand-written Python emitter, Form-recipes-translated-to-Python-syntax, tautological cross-runtime parity claims — was composted. See `KNOWN_GAPS.md` for what was learned.

## Spec

`specs/form-binary-to-native-python-emitter.md` carries the contract.
