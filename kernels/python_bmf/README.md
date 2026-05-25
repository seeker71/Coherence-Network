# `kernels/python_bmf/` — native Python BMF compiler (emitted from Form)

The Python BMF compiler lives as Form recipes in
`form/form-stdlib/grammars/python-bmf.fk` (74+ object categories,
source scanner, rule book, section dispatcher, `form.action` lowering).
The Form kernel walks those recipes to parse Python source into Recipe
trees and emit `.fkb`.

This package is the **native Python expression** of that same compiler.
A developer can read `objects.py` and see the BMF category table as a
Python `IntEnum`; once parser/rules/section_parser/form_action/compiler
are emitted, the same reading works for the rest. The Form binary stays
the substrate source of truth — this package is its readable native
form, runnable under CPython with no Form runtime in the execution path.

## Files in this package

| File | How it got here |
|------|-----------------|
| `__init__.py` | hand-tuned (package marker + lineage) |
| `README.md` | hand-tuned (this file) |
| `sdk.py` | hand-tuned **SDK bridge** — NodeIDs, intern, `.fkb` i/o, Lens. The only place Form concepts surface in Python. Capped at 400 lines. |
| `objects.py` | **emitted** by `form/form-stdlib/emits/python-native.fk` via the kernel's `write_file_text` host call. Re-emit with `form/scripts/emit_native_python.sh`. |

**Honest gap**: `parser.py`, `rules.py`, `section_parser.py`,
`form_action.py`, `compiler.py` are not yet emitted. Each is one
additional `pn-emit-<module>` recipe away inside
`form/form-stdlib/emits/python-native.fk`. Until they land, this
package is a proof of path, not a working compiler.

## Constraint (spec):

> No handwritten Python in `kernels/python_bmf/` other than `__init__.py`,
> `README.md`, and `sdk.py`. Every other .py file MUST be Form-emitter
> output landed via the kernel's `write_file_text` host call. If a
> developer wants to add a new function, the addition goes in
> `emits/python-native.fk` first, and the emitter re-runs.

## Regenerating

```bash
form/scripts/emit_native_python.sh
```

This:
1. Builds `form-kernel-go` if needed.
2. Source-compiles `form-stdlib/core.fk` (same shape `validate.sh` uses).
3. Runs the kernel against `emits/python-native.fk` + `emits/python-native-driver.fk`.
4. The driver calls `pn-emit-all`, which calls `write_file_text` from inside the kernel for each target file.
5. Verifies the emitted Python compiles (`python3 -m py_compile`).

## Where this is going

`specs/form-binary-to-native-python-emitter.md` names the full destination:
every module emitted, parity proof against the Form-kernel pipeline,
performance comparison between CPython-via-emitted-package and
form-kernel-rust on the same workloads.
