"""Substrate boundary for Python — NodeID, intern, SourceSpan, .fkb i/o, Lens.

The body of this package is intentionally small. The architectural target
(specs/form-binary-to-native-python-emitter.md):

  Form-resident BMF compiler  (in Form recipes, walked by Go/Rust/TS kernels)
      ↓  parses Python source → Recipe tree
  form/form-stdlib/emits/python-native.fk  (a Form recipe; the Form-native
      adapter for Python — under construction)
      ↓  walks Recipe tree, emits idiomatic native Python
  emitted .py files  (idiomatic Python — class, def, regex, dict, generators)
      ↓  run under CPython
  same observable behavior as the Form-resident compiler

This package contains ONLY the substrate primitives Python lacks natively —
NodeID (content-addressed structural identity), intern (structural identity
by content), SourceSpan, .fkb binary i/o, Lens. Everything else either lives
on the Form side (the parser rules in python-bmf.fk, the emitter recipes
in emits/python-native.fk) or in the emitted Python that the Form-native
emitter produces.

See KNOWN_GAPS.md for what was learned and composted on 2026-05-25.
"""
