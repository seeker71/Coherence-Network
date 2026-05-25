"""Cross-runtime scanner parity — Form-native python-bmf.fk vs emitted Python.

Both runtimes scan the same Python file. Token streams should match
exactly (modulo additive Python-side features like py-blank and the
quote-style suffix on string atoms, which are excluded from comparison).

Divergence is the signal — it shows where one runtime has features the
other doesn't, which is part of the Universal Translator's learning loop.
"""

from __future__ import annotations

import re
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from kernels.python_bmf.parser import scan_python_source  # noqa: E402


PARITY_SCRIPT = REPO_ROOT / "form/scripts/cross_runtime_parity.sh"
DEMO_DIR = REPO_ROOT / "form/form-kernel-ts/seedbank/python-adapter/examples"


@unittest.skipUnless(
    PARITY_SCRIPT.exists() and (REPO_ROOT / "form/form-kernel-go/bin-go").exists(),
    "form-kernel-go required; build via cross_runtime_parity.sh once before running",
)
class CrossRuntimeParityTests(unittest.TestCase):
    def test_demos_token_parity(self):
        demos = sorted(DEMO_DIR.glob("python_*.py"))
        self.assertGreater(len(demos), 0)
        failures = []
        for demo in demos:
            with self.subTest(demo=demo.name):
                result = subprocess.run(
                    [str(PARITY_SCRIPT), str(demo)],
                    capture_output=True,
                    text=True,
                    cwd=str(REPO_ROOT),
                    timeout=120,
                )
                tail = (result.stdout or "").splitlines()[-1]
                if "PARITY" not in tail:
                    failures.append((demo.name, tail))
        if failures:
            msg = "\n".join(f"  {name}: {tail[:120]}" for name, tail in failures)
            self.fail(f"cross-runtime scanner parity broken:\n{msg}")


if __name__ == "__main__":
    unittest.main()
