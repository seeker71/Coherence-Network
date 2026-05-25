"""Native Python BMF compiler — readable Python expression of the Form-resident Python BMF compiler.

Lineage: form/form-stdlib/grammars/python-bmf.fk (the Form source of truth)
         → form/form-stdlib/emits/python-native.fk (Form-native emitter)
         → this package (the destination Python shape).

Only `sdk.py` is hand-tuned (the SDK bridge). Every other .py file in
this package is emitter output landed via the kernel's write_file_text
host call. To regenerate: form/scripts/emit_native_python.sh.

See specs/form-binary-to-native-python-emitter.md for the architecture
and proof loop. Today emitted: objects.py. Honest gaps: parser.py,
rules.py, section_parser.py, form_action.py, compiler.py.
"""
