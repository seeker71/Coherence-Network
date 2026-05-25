"""The Form-written BMF compiler, emitted as readable native Python.

Each module here is the output of `kernels/python_bmf/emit_python.py` walking
the matching .fk Form source. The functions read as Python — real `def`,
`if/else`, `return`, `+`/`*`/`==`/`<=`, `[i]` subscript, `[a, b, c]` lists.

| Form source                                | Emitted Python                |
|--------------------------------------------|-------------------------------|
| form/form-stdlib/compiler.fk               | compiler.py                   |
| form/form-stdlib/engine.fk                 | engine.py                     |
| form/form-stdlib/source-compiler.fk        | source_compiler.py            |
| form/form-stdlib/grammars/python-bmf.fk    | python_bmf.py                 |

6218 lines of native Python emitted from 6657 lines of Form .fk.

Each module compiles cleanly (`python3 -m py_compile`). To execute, the
host primitives the Form code references — `cell`, `bmf_object`,
`str_concat`, `make_nodeid`, `intern_node`, file IO, etc. — must be
bound to Python implementations (see `kernels/python_bmf/host_primitives.py`,
which provides the substrate SDK glue).

These modules are READABLE as Python. They are NOT yet RUNNABLE end-to-end
without the host-primitives bindings — that wiring is the next breath.
"""
