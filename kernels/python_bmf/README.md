# `kernels/python_bmf/` — native Python BMF compiler (emitted from Form)

The Python BMF compiler lives as Form recipes in
`form/form-stdlib/grammars/python-bmf.fk`. This package is its native
Python expression, materialized by the Form emitter
(`form/form-stdlib/emits/python-native.fk`) through the kernel's
`write_file_text` host call.

## Files

| File | Source | Role |
|------|--------|------|
| `__init__.py` | hand-tuned | package marker + lineage |
| `README.md` | hand-tuned | this file |
| `sdk.py` | hand-tuned | **SDK bridge** — NodeIDs, intern, SourceSpan, `.fkb` i/o, Lens. The only place Form concepts surface in Python. |
| `objects.py` | **synthesized** | walked from a Form-side category table + atom helpers; rendered by Form recipes via `str_concat` and written via `write_file_text` |
| `parser.py` | **template-emitted** | scanner + layout + module parser; canonical source at `form/form-stdlib/emits/python-native-templates/parser.py`, the kernel reads it and writes it here |
| `rules.py` | **template-emitted** | BMF rule registry (12 rules in the first slice); same path |
| `section_parser.py` | **template-emitted** | section header detection + dialect dispatch |
| `form_action.py` | **template-emitted** | Action IR + evaluator + `compile_form_action` |
| `compiler.py` | **template-emitted** | `Compiler` class + CLI (`--self-test`, `--self-compile`, `--roundtrip`) |
| `decompiler.py` | **template-emitted** | `.fkb` → Python source for round-trip testing |

## Two emission shapes

1. **Synthesized** (the deep emit shape): `objects.py` is built from Form-side data (category list, atom kinds, keyword/operator vocabularies) via composed `str_concat` recipes. Re-emit edits the recipe and the data — the Form file is authoritative.

2. **Template-emitted** (the bridge shape): for files too large to synthesize from primitives in one breath, the canonical Python source lives at `form/form-stdlib/emits/python-native-templates/*.py`. The Form emitter calls `read_file` then `write_file_text`. The kernel is still the sole materializer; the substrate side holds the source-of-truth Python.

The destination state: every module synthesized from a `.fkb` walked by Form recipes + a lens layer. Templates compost into synthesis as the lens layer lands.

## Constraint

> No handwritten Python in `kernels/python_bmf/` other than `__init__.py`, `README.md`, and `sdk.py`. Every other .py file MUST be Form-emitter output landed via the kernel's `write_file_text` host call. If a developer wants to add a new function, the addition goes in either the Form recipe (`emits/python-native.fk`) or the canonical template (`emits/python-native-templates/*.py`) first, and the emitter re-runs.

## Regenerating

```bash
form/scripts/emit_native_python.sh
```

This builds `form-kernel-go` if needed, source-compiles `core.fk`,
runs the kernel against `emits/python-native.fk` +
`emits/python-native-driver.fk`, the driver calls `pn-emit-all`, which
calls `write_file_text` from inside the kernel for each target file,
then verifies the emitted Python compiles.

## Round-trip status

`python3 -m unittest kernels.python_bmf.tests` round-trips every demo in `form/form-kernel-ts/seedbank/python-adapter/examples/python_*.py`. **8/8 semantic round-trip.** See `KNOWN_GAPS.md` for what's lost (trailing comments, alignment whitespace, quote-style) and what's next.

## Where this is going

`specs/form-binary-to-native-python-emitter.md` names the full destination — every module emitted, parity proof against the Form-kernel pipeline, performance comparison between CPython-via-emitted-package and form-kernel-rust on the same workloads. The Universal Translator path:

1. **Step 1 — round-trip in a single language** (Python ↔ Form): the current arc.
2. **Step 2 — round-trip across languages**: sibling `emits/<lang>-native.fk` for Go, Rust, TypeScript, C++ reusing `semantic-lowerer.fk`.
3. **Step 3 — round-trip across domains**: the substrate's deeper promise.

Each gap surfaced by round-trip testing is mapped in `KNOWN_GAPS.md`. The body learns by trying.
