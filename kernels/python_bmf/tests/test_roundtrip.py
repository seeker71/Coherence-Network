"""Round-trip the parity-suite demos through the emitted compiler.

For every demo in form/form-kernel-ts/seedbank/python-adapter/examples/python_*.py:
1. Compile to .fkb
2. Decompile back to Python text
3. Compare semantically (whitespace-normalized, comments stripped)

Trailing # comments are stripped by the scanner — documented gap, see
kernels/python_bmf/KNOWN_GAPS.md.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from kernels.python_bmf.compiler import Compiler  # noqa: E402
from kernels.python_bmf.decompiler import decompile_module  # noqa: E402


DEMO_DIR = REPO_ROOT / "form/form-kernel-ts/seedbank/python-adapter/examples"


def _normalize(text):
    """Strip full-line and trailing comments, blank lines, runs of spaces."""
    out = []
    for line in text.splitlines():
        # remove trailing # comment (naive: any # after first non-string char)
        if "#" in line:
            line = re.split(r"\s*#", line, maxsplit=1)[0]
        line = line.rstrip()
        if not line.strip():
            continue
        line = re.sub(r"\s+", " ", line)
        # Normalize spacing around `:` (lambda inside brackets etc.)
        line = re.sub(r"\s*:\s*", ":", line)
        out.append(line)
    return "\n".join(out)


class RoundTripTests(unittest.TestCase):
    def test_demos_round_trip(self):
        demos = sorted(DEMO_DIR.glob("python_*.py"))
        self.assertGreater(len(demos), 0, "no demos found")
        failures = []
        for demo in demos:
            with self.subTest(demo=demo.name):
                compiler = Compiler()
                result = compiler.compile_file(demo)
                decompiled = decompile_module(
                    result.nodes, module_id=str(result.module_id)
                )
                original = demo.read_text()
                if _normalize(original) != _normalize(decompiled):
                    failures.append(demo.name)
        if failures:
            self.fail(f"semantic round-trip diverged for: {failures}")


if __name__ == "__main__":
    unittest.main()
