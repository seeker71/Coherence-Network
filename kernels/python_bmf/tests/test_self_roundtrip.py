"""Round-trip the emitted compiler's own source through itself.

The package compiles its own .py files into .fkb, then decompiles back
to Python. Semantic equivalence (whitespace + blank-line normalized) is
the target; byte-identical is the deeper destination.

Where divergence appears, the gap is logged in KNOWN_GAPS.md.
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


PACKAGE_DIR = REPO_ROOT / "kernels/python_bmf"


def _semantic_normalize(text):
    """Reduce text to a canonical shape: collapse multi-line bracketed
    expressions onto one line, drop blank lines, normalize whitespace
    and spacing around `:` and `*`.
    """
    # Phase 1 — collapse bracket-spanning newlines so multi-line and
    # single-line dict/list/call layouts compare equal. Handles both
    # single-quoted and triple-quoted strings, plus `#`-comments.
    collapsed = []
    depth = 0
    in_string = False
    triple = False
    quote = ""
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if in_string:
            collapsed.append(ch)
            if ch == "\\" and i + 1 < n:
                collapsed.append(text[i + 1])
                i += 2
                continue
            if triple and text[i:i + 3] == quote * 3:
                collapsed.append(text[i + 1])
                collapsed.append(text[i + 2])
                in_string = False
                triple = False
                i += 3
                continue
            if not triple and ch == quote:
                in_string = False
            i += 1
            continue
        # Skip `#`-comments to end of line (don't track brackets inside).
        if ch == "#":
            while i < n and text[i] != "\n":
                collapsed.append(text[i])
                i += 1
            continue
        if ch in ('"', "'") and text[i:i + 3] == ch * 3:
            in_string = True
            triple = True
            quote = ch
            collapsed.append(ch)
            collapsed.append(text[i + 1])
            collapsed.append(text[i + 2])
            i += 3
            continue
        if ch in ('"', "'"):
            in_string = True
            triple = False
            quote = ch
            collapsed.append(ch)
            i += 1
            continue
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth = max(0, depth - 1)
        if ch == "\n" and depth > 0:
            collapsed.append(" ")
        else:
            collapsed.append(ch)
        i += 1
    flat = "".join(collapsed)

    # Phase 2 — per-line normalization
    out = []
    for line in flat.splitlines():
        stripped = line.rstrip()
        if not stripped.strip():
            continue
        s = re.sub(r" +", " ", stripped)
        s = re.sub(r"\s*:\s*", ":", s)
        s = re.sub(r"([(\[{,=])\s*\*", r"\1*", s)
        # Trailing commas inside brackets are ignored by Python; treat them equivalently.
        s = re.sub(r",\s*([)\]}])", r"\1", s)
        # Tighten space immediately after open / before close brackets.
        s = re.sub(r"([(\[{])\s+", r"\1", s)
        s = re.sub(r"\s+([)\]}])", r"\1", s)
        out.append(s)
    return "\n".join(out)


class SelfRoundTripTests(unittest.TestCase):
    def test_emitted_modules_round_trip_semantically(self):
        compiler = Compiler()
        targets = sorted(
            p for p in PACKAGE_DIR.glob("*.py") if p.name not in ("__init__.py",)
        )
        results = {}
        for src in targets:
            with self.subTest(module=src.name):
                original = src.read_text()
                result = compiler.compile_file(src)
                decompiled = decompile_module(
                    result.nodes, module_id=str(result.module_id)
                )
                norm_orig = _semantic_normalize(original)
                norm_rt = _semantic_normalize(decompiled)
                results[src.name] = (norm_orig == norm_rt, len(decompiled.splitlines()))
        # Print a status table for visibility (test always passes —
        # gaps are logged in KNOWN_GAPS.md; this test surfaces them).
        for name, (ok, lines) in sorted(results.items()):
            tag = "ok" if ok else "diverged"
            print(f"  {name}: {tag} ({lines} lines)")
        # At least objects.py + sdk.py + decompiler.py + section_parser.py
        # should round-trip semantically today.
        target_modules = ("objects.py", "sdk.py", "decompiler.py", "section_parser.py")
        for name in target_modules:
            ok, _ = results.get(name, (False, 0))
            self.assertTrue(ok, f"{name} did not round-trip semantically")


if __name__ == "__main__":
    unittest.main()
