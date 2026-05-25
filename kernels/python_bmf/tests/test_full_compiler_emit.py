"""The whole BMF compiler stack translates to readable native Python.

Every Form source the BMF compiler is built from — compiler.fk (compiler
cells), engine.fk (reversible BMF runtime), source-compiler.fk (source
section compiler), grammars/python-bmf.fk (the 74-category Python BMF
grammar + 50+ rules) — emits Python that compiles cleanly and contains
real Python idioms instead of leaked s-expression syntax.

This is the kernel-execution test's structural sibling: it does not yet
PROVE the emitted Python runs correctly (host-primitive bindings need
to land first), but it gates the readability claim with hard checks.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from kernels.python_bmf.emit_python import emit_python  # noqa: E402

SOURCES = [
    ("compiler",        REPO_ROOT / "form/form-stdlib/compiler.fk"),
    ("engine",          REPO_ROOT / "form/form-stdlib/engine.fk"),
    ("source_compiler", REPO_ROOT / "form/form-stdlib/source-compiler.fk"),
    ("python_bmf",      REPO_ROOT / "form/form-stdlib/grammars/python-bmf.fk"),
]


class FullBmfCompilerEmitsAsPython(unittest.TestCase):
    def test_every_form_source_emits_compilable_python(self):
        total_fk_lines = 0
        total_py_lines = 0
        for name, src in SOURCES:
            with self.subTest(source=name):
                self.assertTrue(src.exists(), f"missing {src}")
                fk_text = src.read_text()
                py_text = emit_python(fk_text)
                # Compiles as Python — SyntaxError if not.
                compile(py_text, f"<{name}>", "exec")
                total_fk_lines += fk_text.count("\n")
                total_py_lines += py_text.count("\n")
        self.assertGreater(total_py_lines, 5000,
                           "BMF compiler emit shrunk; investigate translator regression")
        self.assertGreater(total_fk_lines, 5000,
                           "BMF compiler sources shrunk; investigate Form-side regression")

    def test_emitted_python_uses_native_idioms_throughout(self):
        """Across all emitted compiler files, real Python idioms appear and
        Form s-expression syntax does not leak through as code (string
        literals carrying .fk-text templates from source-compiler.fk are
        a known shortcut surface; see KNOWN_GAPS.md)."""
        all_py = ""
        for _, src in SOURCES:
            all_py += emit_python(src.read_text())

        # 1. Real Python idioms present
        for marker in ["def ", "return ", " if ", " else", " == ", " + ", "[0]", "[1:]"]:
            self.assertIn(marker, all_py, f"BMF compiler emit missing {marker!r}")

        # 2. Form s-expression syntax must NOT appear as Python *code*.
        # A leak as code starts at column 0 or after indentation, never inside a quoted
        # string. We strip all string literals before scanning.
        import re
        code_only = re.sub(r"\"(?:\\.|[^\"\\])*\"", '""', all_py)
        code_only = re.sub(r"'(?:\\.|[^'\\])*'", "''", code_only)
        # Use word-boundary checks so identifiers that legitimately contain
        # these substrings (e.g. `bmf_compile_bmf_item_plus`) don't false-positive.
        for noise_pattern, label in [
            (r"\bdefn\(", "(defn syntax"),
            (r"^\s*\(defn\s", "(defn leading-form"),
            (r"\blet\(", "(let syntax"),
            (r"^\s*\(let\s", "(let leading-form"),
            (r"^\s*\(do\s", "(do leading-form"),
            (r"^\s*\(if\s", "(if leading-form"),
            (r"\b_plus\(", "_plus( call"),
            (r"\bmul\(", "mul( call"),
        ]:
            self.assertFalse(
                re.search(noise_pattern, code_only, re.MULTILINE),
                f"BMF compiler emit leaked s-expression {label} as code",
            )

        # 3. Compiler-specific identifier translations present
        for ident in ["compiler_object", "bmf_object", "python_source_scan_text",
                      "apply_python_bmf_rule", "compiler_rule", "compiler_section"]:
            self.assertIn(ident, all_py, f"expected BMF compiler symbol missing: {ident!r}")


if __name__ == "__main__":
    unittest.main()
