"""Form kernel bridge — shell into form-kernel-rust for endpoint bodies.

The first transmutation gesture: a FastAPI endpoint's body is a Form
recipe compiled from Python. The route delegates to the kernel binary
instead of executing Python inline. FastAPI stays as the HTTP doorway;
the computation IS a Recipe.

Companion to form/form-kernel-ts/seedbank/python-adapter/examples/
endpoint_*_demo.py — every endpoint that transmutes its body lands a
.fk recipe next to a .py demo, both verified by parity_suite.sh.

If the kernel binary is unavailable (build missing in container), the
caller's fallback Python function runs. Same result either path —
parity_suite.sh is the regression gate.
"""
from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

_KERNEL_BIN_ENV = "FORM_KERNEL_RUST_BIN"
# Default path: repo-relative to api/app/services/, four levels up to repo
# root, then into form/form-kernel-rust/target/release/form-kernel-rust.
_DEFAULT_KERNEL_BIN = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "form"
    / "form-kernel-rust"
    / "target"
    / "release"
    / "form-kernel-rust"
)


def kernel_bin_path() -> Path:
    """Return the path to the form-kernel-rust binary."""
    override = os.environ.get(_KERNEL_BIN_ENV)
    if override:
        return Path(override)
    return _DEFAULT_KERNEL_BIN


def kernel_available() -> bool:
    """True when the kernel binary is on disk and executable."""
    p = kernel_bin_path()
    return p.is_file() and os.access(p, os.X_OK)


def run_recipe(fk_source: str, timeout: float = 10.0) -> str:
    """Run a Form recipe through form-kernel-rust, return stdout's last line.

    fk_source is the textual .fk content — a top-level (do ...) form whose
    final expression's value is the kernel's printed result.

    Raises RuntimeError if the kernel binary is missing or the run fails.
    """
    bin_path = kernel_bin_path()
    if not kernel_available():
        raise RuntimeError(f"form-kernel-rust binary not found at {bin_path}")

    with tempfile.NamedTemporaryFile("w", suffix=".fk", delete=False) as f:
        f.write(fk_source)
        fk_path = f.name

    try:
        proc = subprocess.run(
            [str(bin_path), fk_path],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    finally:
        try:
            os.unlink(fk_path)
        except OSError:
            pass

    if proc.returncode != 0:
        raise RuntimeError(
            f"form-kernel-rust failed (exit {proc.returncode}): {proc.stderr.strip()}"
        )
    out = proc.stdout.rstrip("\n").splitlines()
    if not out:
        raise RuntimeError("form-kernel-rust produced no output")
    return out[-1]


def run_with_fallback(
    fk_source: str,
    fallback: Callable[[], Any],
    parse: Callable[[str], Any] = lambda s: s,
    timeout: float = 10.0,
) -> tuple[Any, str]:
    """Run fk_source through the kernel; fall back to Python on missing binary.

    Returns (value, runtime) where runtime is "form-kernel-rust" or
    "python-fallback". Errors from the kernel beyond the binary-missing
    case propagate — the parity_suite guarantees the recipe matches
    Python; an actual kernel failure is a real problem worth surfacing.
    """
    if not kernel_available():
        logger.info(
            "form-kernel-rust binary missing at %s — falling back to Python",
            kernel_bin_path(),
        )
        return fallback(), "python-fallback"
    raw = run_recipe(fk_source, timeout=timeout)
    return parse(raw), "form-kernel-rust"
