"""Form → idiomatic native Python translator parity.

The universal-translator move: take a Form recipe (parity-suite .fk), emit
real native Python (`def`/`if`/`+`/`*`/`==`/`<=`, real names, real control
flow), run that Python under CPython, get the same integer the original
Python source produces.

Scope today: parity-suite feature surface (def, recursion, conditional
expr, arithmetic, comparison, logic, while via CPS-recursion, for via
CPS-recursion, list, subscript, nth/sum/range preludes). Real substrate
code (organ.py / form.py / API endpoints) needs more on BOTH sides — Form
.fk lowering AND this translator. That coverage grows in subsequent
breaths; this test gates the surface we DO claim.
"""

from __future__ import annotations

import ast
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from kernels.python_bmf.emit_python import emit_python, UnsupportedForm  # noqa: E402
from kernels.python_bmf.kernel_fk_lowering import emit_fk, UnsupportedConstruct  # noqa: E402

DEMO_DIR = REPO_ROOT / "form/form-kernel-ts/seedbank/python-adapter/examples"


def cpython_tail_eval(path: Path) -> str:
    src = path.read_text()
    tree = ast.parse(src)
    body, last = tree.body[:-1], tree.body[-1]
    ns: dict = {}
    if body:
        exec(compile(ast.Module(body=body, type_ignores=[]), str(path), "exec"), ns)
    if isinstance(last, ast.Expr):
        return str(eval(compile(ast.Expression(body=last.value), str(path), "eval"), ns))
    raise RuntimeError(f"{path.name}: tail is not an expression")


class FkToPythonTranslator(unittest.TestCase):
    def test_demos_emit_real_python_matching_cpython(self):
        demos = sorted(DEMO_DIR.glob("python_*.py"))
        skipped: list[str] = []
        for py in demos:
            with self.subTest(demo=py.name):
                try:
                    fk_text = emit_fk(py.read_text())  # .py → .fk (sanity bridge)
                except UnsupportedConstruct as e:
                    skipped.append(f"{py.name}: .py→.fk {e}")
                    continue
                try:
                    py_emitted = emit_python(fk_text)  # .fk → idiomatic Python
                except UnsupportedForm as e:
                    self.fail(f"{py.name}: .fk→.py emit failed: {e}")

                # The emitted Python must be syntactically real Python and
                # produce the same integer the original CPython source does.
                compile(py_emitted, f"<{py.name}>", "exec")  # SyntaxError if not real Python
                proc = subprocess.run(
                    [sys.executable, "-c", py_emitted],
                    capture_output=True, text=True, check=False, timeout=30,
                )
                emitted_out = proc.stdout.strip()
                expected = cpython_tail_eval(py)
                self.assertEqual(
                    emitted_out, expected,
                    f"{py.name}: CPython={expected} emitted-Python={emitted_out}\n"
                    f"emitted:\n{py_emitted[:600]}",
                )
        # Allow exactly one skip (lambda) for now; surface any more.
        self.assertLessEqual(len(skipped), 1, f"unexpected skips: {skipped}")

    def test_emitted_python_is_readable_not_sexpressions(self):
        """The output must contain real Python idioms, not Form s-expression syntax."""
        fk = emit_fk((DEMO_DIR / "python_demo.py").read_text())
        py = emit_python(fk)
        # Must contain real Python keywords/operators
        for marker in ["def ", "return ", " if ", " else", " + ", " * ", " < ", " == "]:
            self.assertIn(marker, py, f"missing native Python idiom: {marker!r}")
        # Must NOT contain Form s-expression operator names
        for noise in ["_plus", "(mul ", "(sub ", " ge ", " le ", "(defn ", "(let "]:
            self.assertNotIn(noise, py, f"leaked Form s-expression syntax: {noise!r}")


if __name__ == "__main__":
    unittest.main()
