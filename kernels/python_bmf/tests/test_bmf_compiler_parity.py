"""Cross-runtime BMF compiler parity: emitted Python ↔ Form kernel.

The deliverable: same Form source compiled through both runtimes produces
byte-identical output. This proves the emitted Python BMF compiler is
semantically equivalent to the Form-kernel BMF compiler — the comparison
the universal-translator goal demands.

This test does NOT require the Form kernel binary to be present (skipped
if missing). When both runtimes ARE available, it asserts byte-identical
compile output on the core.fk workload.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

GO_BIN = REPO_ROOT / "form/form-kernel-go/bin-go"
SOURCE_COMPILER = REPO_ROOT / "form/form-stdlib/source-compiler.fk"
TARGETS = [
    REPO_ROOT / "form/form-stdlib/tests/lists.fk",
    REPO_ROOT / "form/form-stdlib/tests/numeric.fk",
    REPO_ROOT / "form/form-stdlib/tests/task-runtime.fk",
    REPO_ROOT / "form/form-stdlib/tests/higher.fk",
    REPO_ROOT / "form/form-stdlib/core.fk",
    REPO_ROOT / "form/form-stdlib/engine.fk",
]


class BmfCompilerCrossRuntimeParity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from kernels.python_bmf.runtime import load_bmf_compiler  # noqa: F401
        cls.rt = load_bmf_compiler()

    @unittest.skipUnless(GO_BIN.exists(), "form-kernel-go binary not built")
    def test_emitted_python_matches_form_kernel_byte_for_byte(self):
        for src in TARGETS:
            with self.subTest(src=src.name):
                # Form-kernel side
                with tempfile.NamedTemporaryFile(suffix=".fk", delete=False) as f_driver, \
                     tempfile.NamedTemporaryFile(suffix=".fk", delete=False) as f_form_out, \
                     tempfile.NamedTemporaryFile(suffix=".fk", delete=False) as f_py_out:
                    driver_path = f_driver.name
                    form_out = f_form_out.name
                    py_out = f_py_out.name
                f_driver_text = f'(do (form-source-compile-file "{src}" "{form_out}"))'
                Path(driver_path).write_text(f_driver_text)
                r = subprocess.run(
                    [str(GO_BIN), str(SOURCE_COMPILER), driver_path],
                    capture_output=True, timeout=60, cwd=str(REPO_ROOT),
                )
                self.assertEqual(r.returncode, 0,
                                 f"form-kernel-go failed: {r.stderr.decode()[:200]}")

                # Emitted-Python side
                self.rt.form_source_compile_file(str(src), py_out)

                # Byte-identical?
                form_bytes = Path(form_out).read_bytes()
                py_bytes = Path(py_out).read_bytes()
                self.assertEqual(
                    form_bytes, py_bytes,
                    f"{src.name}: form-kernel output != emitted-Python output\n"
                    f"  form size: {len(form_bytes)}\n"
                    f"  py   size: {len(py_bytes)}\n"
                )


if __name__ == "__main__":
    unittest.main()
