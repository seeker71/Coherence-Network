#!/usr/bin/env python3
"""Coherence Network runner — thin shim.

All logic lives in api/scripts/local_runner.py.
This shim exists for backward compatibility with launchd and documentation.
"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "api"))
sys.path.insert(0, str(_ROOT / "api" / "scripts"))

from local_runner import main

if __name__ == "__main__":
    main()
