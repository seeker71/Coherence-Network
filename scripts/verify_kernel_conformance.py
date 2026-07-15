#!/usr/bin/env python3
"""Compatibility entrypoint for the canonical submodule conformance runner."""

from __future__ import annotations

import runpy
from pathlib import Path


CANONICAL = (
    Path(__file__).resolve().parents[1]
    / "form"
    / "scripts"
    / "verify_kernel_conformance.py"
)

if __name__ == "__main__":
    runpy.run_path(str(CANONICAL), run_name="__main__")
