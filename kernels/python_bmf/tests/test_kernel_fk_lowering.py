"""Cross-runtime execution parity: emit .fk, run on form-kernel-rust, match CPython.

This is the proof the goal names: same Python program, two runtimes, same
integer. Until emit_fk landed, no emitted artifact had ever been executed
by a Form kernel.
"""

from __future__ import annotations

import ast
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from kernels.python_bmf.kernel_fk_lowering import emit_fk, UnsupportedConstruct  # noqa: E402


RUST_BIN = REPO_ROOT / "form/form-kernel-rust/target/release/form-kernel-rust"
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


@unittest.skipUnless(RUST_BIN.exists(), "form-kernel-rust not built (run cargo build --release)")
class EmitFkKernelExecution(unittest.TestCase):
    def test_parity_suite_demos_match_cpython_through_kernel(self):
        demos = sorted(DEMO_DIR.glob("python_*.py"))
        self.assertGreater(len(demos), 0)
        skipped = []
        for demo in demos:
            with self.subTest(demo=demo.name):
                try:
                    fk_text = emit_fk(demo.read_text())
                except UnsupportedConstruct as e:
                    skipped.append((demo.name, str(e)))
                    continue
                fk_path = REPO_ROOT / "form/.cache/test_emit_fk" / (demo.stem + ".fk")
                fk_path.parent.mkdir(parents=True, exist_ok=True)
                fk_path.write_text(fk_text + "\n")
                kernel_out = subprocess.run(
                    [str(RUST_BIN), str(fk_path)],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=60,
                ).stdout.strip()
                cpy = cpython_tail_eval(demo)
                self.assertEqual(
                    kernel_out, cpy,
                    f"{demo.name}: CPython={cpy} kernel={kernel_out}",
                )
        # Skipped demos are tracked as expected gaps until coverage extends.
        # Today: python_lambda_demo (Lambda unsupported).
        self.assertLessEqual(len(skipped), 1, f"unexpected skips: {skipped}")


if __name__ == "__main__":
    unittest.main()
